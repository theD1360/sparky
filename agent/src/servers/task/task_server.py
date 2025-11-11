"""Proactive agent loop for Sparky.

This module provides an async agent loop that continuously processes tasks from
the task queue in the background. Tasks are executed by the AgentOrchestrator instance using
natural language instructions, and results are stored back in memory.
"""

import asyncio
import os
from datetime import datetime
from logging import getLogger
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from badmcp.control import Control
from badmcp.tool_chain import ToolChain
from sparky import AgentOrchestrator
from sparky.event_types import TaskEvents
from sparky.middleware import (
    CommandPromptMiddleware,
    ResourceFetchingMiddleware,
    SelfModificationGuard,
)
from sparky.providers import GeminiProvider, ProviderConfig
from sparky.scheduled_tasks import load_scheduled_tasks
from sparky.task_queue import create_task_queue
from services import TaskService
from utils.events import Events

logger = getLogger(__name__)


class AgentLoop:
    """Proactive agent loop for processing background tasks."""

    def __init__(
        self,
        toolchain: ToolChain,
        control: Optional[Control] = None,
        poll_interval: int = 10,
        enable_scheduled_tasks: bool = True,
        config_path: Optional[Path] = None,
    ):
        """Initialize the agent loop.

        Args:
            toolchain: The MCP toolchain to use for executing tasks
            control: Optional Control instance for managing tool servers
            poll_interval: Seconds to wait between polling for new tasks
            enable_scheduled_tasks: Whether to enable scheduled tasks
            config_path: Optional path to scheduled tasks config file
        """
        self.toolchain = toolchain
        self.control = control
        self.poll_interval = poll_interval
        self.enable_scheduled_tasks = enable_scheduled_tasks
        self.running = False
        self._task = None
        self._cycle_count = 0
        self._tasks_processed = 0

        # Load scheduled tasks from YAML config
        self.scheduled_tasks = []
        if enable_scheduled_tasks:
            self.scheduled_tasks = load_scheduled_tasks(config_path)
            logger.info(f"Loaded {len(self.scheduled_tasks)} scheduled tasks")

        # Initialize task queue
        self.task_queue = create_task_queue()

        # Initialize task service
        self.task_service = TaskService(task_queue=self.task_queue)

        # Initialize event system
        self.events = Events()

        # Subscribe to task queue events
        self.task_queue.events.subscribe(TaskEvents.TASK_ADDED, self._on_task_added)

        # Subscribe to our own events for task processing
        self.events.subscribe(TaskEvents.TASK_AVAILABLE, self._on_task_available)

        # Create persistent session_id and user_id for the agent loop
        # Use regular UUIDs so the agent appears as a normal user in the UI
        self.session_id = str(uuid4())
        self.user_id = "agent"  # Hardcoded user_id for the task agent
        logger.info(
            f"Created agent loop session: {self.session_id} for user: {self.user_id}"
        )

        # Initialize persistent AgentOrchestrator instance for task execution
        model_name = os.getenv("AGENT_MODEL", "gemini-2.0-flash")
        config = ProviderConfig(model_name=model_name)
        provider = GeminiProvider(config)

        self.bot = AgentOrchestrator(
            provider=provider,
            toolchain=toolchain,
            middlewares=[
                SelfModificationGuard(),
                ResourceFetchingMiddleware(),
                CommandPromptMiddleware(),
            ],
        )

        # Store refined initial system message to be added when chat starts
        self.initial_system_message = """
You are the agent's subconscious, responsible for handling background tasks autonomously. Use all available tools and resources to achieve your objectives efficiently and independently. 
Before starting any task, consult your knowledge graph to gather relevant context. Do not duplicate tasks you have previously completed. 
Upon task completion, update your knowledge graph with your results and insights.
        """
        self.initial_system_response = """
Acknowledged. I will independently complete background tasks using all resources at my disposal, always consulting my knowledge graph before starting. 
I will avoid duplicating prior work, and I will update my knowledge graph upon completion to reflect task outcomes.
        """

        # Cache identity at session level (loaded once, reused for all tasks)
        self._identity_memory: Optional[str] = None
        self._identity_summary: Optional[str] = None

        logger.info("Agent loop initialized with TaskService")

    async def _load_and_cache_identity(self, bot: AgentOrchestrator) -> tuple[str, str]:
        """Load identity once and cache it for all tasks in this session.

        Args:
            bot: Bot instance to use for loading and summarizing identity

        Returns:
            Tuple of (identity_memory, identity_summary)
        """
        # Return cached identity if available
        if self._identity_memory and self._identity_summary:
            logger.info(f"[{self.session_id}] Using cached identity for task")
            return self._identity_memory, self._identity_summary

        logger.info(
            f"[{self.session_id}] Loading identity for task server session (first time)"
        )

        # Load identity using the identity service
        from services import IdentityService

        # Get knowledge instance from the bot
        if not bot.knowledge or not bot.knowledge.repository:
            logger.warning("No knowledge repository available, using default identity")
            self._identity_memory = (
                "## Task Server Identity\n\nBackground task processing agent."
            )
            self._identity_summary = "You are a background task processing agent."
            return self._identity_memory, self._identity_summary

        identity_service = IdentityService(
            repository=bot.knowledge.repository,
        )

        # Load identity
        try:
            self._identity_memory = await identity_service.get_identity_memory()
        except Exception as e:
            logger.error(f"Failed to load identity: {e}")
            self._identity_memory = (
                "## Identity Loading Failed\n\nCannot load identity."
            )

        # Summarize identity
        try:
            self._identity_summary = await identity_service.summarize_identity(
                self._identity_memory, bot.generate
            )
        except Exception as e:
            logger.error(f"Failed to summarize identity: {e}")
            identity_summary_prompt = f"Summarize the following identity document into a concise paragraph, retaining the core concepts, purpose, and values:\n\n{self._identity_memory}"
            self._identity_summary = await bot.generate(identity_summary_prompt)

        logger.info(
            f"[{self.session_id}] Identity loaded and cached for task server session"
        )
        return self._identity_memory, self._identity_summary

    async def _on_task_added(self, task: Dict[str, Any]):
        """Handle TASK_ADDED event."""
        logger.debug(f"Task added to queue: {task['id']}")
        # Could trigger immediate processing here if desired

    async def _on_task_available(self, task: Dict[str, Any]):
        """Handle TASK_AVAILABLE event and process the task."""
        task_id = task["id"]
        instruction = task["instruction"]

        # Validate instruction is not empty
        if not instruction or not instruction.strip():
            error_msg = f"Task {task_id} has empty instruction"
            logger.error(error_msg)
            await self.task_queue.update_task_status(task_id, "failed", error=error_msg)
            await self.events.async_dispatch(TaskEvents.TASK_FAILED, task_id, error_msg)
            return

        logger.info(f"Executing task {task_id}: {instruction[:80]}...")

        try:
            # Emit TASK_STARTED event
            await self.events.async_dispatch(TaskEvents.TASK_STARTED, task)

            # Get or create chat for this task using TaskService
            chat_id, bot, is_reused = self.task_service.get_or_create_task_chat(task)

            if not is_reused:
                # Need to create a new bot instance
                chat_name = self.task_service.get_task_chat_name(task)

                # Create a new bot instance for this task (aligned with new architecture)
                logger.info(
                    f"Creating bot instance for task {task_id} with chat_id={chat_id}"
                )
                model_name = os.getenv("AGENT_MODEL", "gemini-2.0-flash")
                config = ProviderConfig(model_name=model_name)
                provider = GeminiProvider(config)

                bot = AgentOrchestrator(
                    provider=provider,
                    toolchain=self.toolchain,
                    middlewares=[
                        SelfModificationGuard(),
                        ResourceFetchingMiddleware(),
                        CommandPromptMiddleware(),
                    ],
                )

                # Store bot instance using TaskService
                scheduled_task_name = self.task_service.get_scheduled_task_name(task)
                if scheduled_task_name:
                    self.task_service.scheduled_task_chats[scheduled_task_name] = (
                        chat_id,
                        bot,
                    )
                    logger.info(
                        f"Stored chat {chat_id} for scheduled task '{scheduled_task_name}' for future reuse"
                    )
                self.task_service.bot_instances[chat_id] = bot

                # Load and cache identity (only happens once per session)
                identity_memory, identity_summary = await self._load_and_cache_identity(
                    bot
                )

                # Start chat for this task with user_id and pre-loaded identity
                logger.info(f"Starting chat for task {task_id} with chat_id={chat_id}")
                await bot.start_chat(
                    session_id=self.session_id,
                    user_id=self.user_id,
                    chat_id=chat_id,
                    chat_name=chat_name,
                    preloaded_identity=identity_memory,
                    preloaded_identity_summary=identity_summary,
                )

                # Add initial system messages for this task
                bot._add_message_with_chat_node(
                    self.initial_system_message,
                    "user",
                    internal=True,
                    message_type="internal",
                )
                bot._add_message_with_chat_node(
                    self.initial_system_response,
                    "model",
                    internal=True,
                    message_type="internal",
                )
                logger.info(
                    f"Bot chat initialized with system messages for task {task_id}"
                )

            # Execute task instruction using the Bot
            response = await bot.send_message(instruction, task_id)

            # Update task status
            await self.task_queue.update_task_status(
                task_id, "completed", response=response
            )

            # Emit TASK_COMPLETED event
            await self.events.async_dispatch(
                TaskEvents.TASK_COMPLETED, task_id, response
            )

            logger.info(f"Task {task_id} completed successfully")
            self._tasks_processed += 1

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)

            # Update task status
            await self.task_queue.update_task_status(task_id, "failed", error=str(e))

            # Emit TASK_FAILED event
            await self.events.async_dispatch(TaskEvents.TASK_FAILED, task_id, str(e))

            # Note: For scheduled tasks, we keep the bot instance for retry
            # For manual tasks, the bot instance will be cleaned up naturally
            scheduled_task_name = self.task_service.get_scheduled_task_name(task)
            if scheduled_task_name:
                logger.warning(
                    f"Task {task_id} failed, but chat will be retained for scheduled task '{scheduled_task_name}'"
                )
            else:
                logger.warning(f"Task {task_id} failed, bot instance will be discarded")

    async def run_once(self) -> bool:
        """Check for pending task and emit TASK_AVAILABLE event if found.

        Returns:
            True if a task was found, False if no pending tasks
        """
        task = await self.task_queue.get_next_pending_task()
        if not task:
            return False

        # Emit TASK_AVAILABLE event - handler will process it
        await self.events.async_dispatch(TaskEvents.TASK_AVAILABLE, task)
        return True

    async def run(self):
        """Run the agent loop continuously until stopped.

        This is the main loop that continuously polls for and executes tasks.
        """
        logger.info(
            f"Agent loop starting with {len(self.scheduled_tasks)} scheduled tasks..."
        )
        self.running = True

        try:
            while self.running:
                try:
                    # Increment cycle counter FIRST
                    self._cycle_count += 1
                    logger.info(f"Cycle count: {self._cycle_count}")
                    logger.info(
                        f"Enable scheduled tasks: {self.enable_scheduled_tasks}"
                    )
                    logger.info(f"Poll interval: {self.poll_interval}")
                    logger.info(f"Tasks processed: {self._tasks_processed}")
                    logger.info(f"Running: {self.running}")

                    # Check and add scheduled tasks
                    if self.enable_scheduled_tasks:
                        current_time = datetime.now()
                        base_path = Path(__file__).parent.parent.parent.parent

                        for scheduled_task in self.scheduled_tasks:
                            # Check if task should run based on its interval
                            if not scheduled_task.should_run(
                                self._cycle_count, current_time
                            ):
                                continue

                            # Get the last execution time from the database
                            scheduled_task_name = scheduled_task.metadata.get(
                                "scheduled_task_name", scheduled_task.name
                            )
                            last_execution = (
                                await self.task_queue.get_last_scheduled_task_execution(
                                    scheduled_task_name
                                )
                            )

                            # Determine if we should add based on interval
                            should_add = False
                            if last_execution is None:
                                # Never run before, add it
                                should_add = True
                                logger.info(
                                    f"Scheduled task '{scheduled_task.name}' has never run, will add"
                                )
                            else:
                                # Check if enough time has passed
                                elapsed = (
                                    current_time - last_execution
                                ).total_seconds()

                                if scheduled_task.interval_type == "time":
                                    required_interval = scheduled_task.interval_value
                                    should_add = elapsed >= required_interval
                                    logger.debug(
                                        f"Scheduled task '{scheduled_task.name}': "
                                        f"elapsed={elapsed}s, required={required_interval}s, should_add={should_add}"
                                    )
                                elif scheduled_task.interval_type == "cron":
                                    # For cron, check if we've passed the next scheduled time
                                    from croniter import croniter

                                    cron = croniter(
                                        scheduled_task.interval_value, last_execution
                                    )
                                    next_time = cron.get_next(datetime)
                                    should_add = current_time >= next_time
                                    logger.debug(
                                        f"Scheduled task '{scheduled_task.name}': "
                                        f"last={last_execution}, next={next_time}, should_add={should_add}"
                                    )
                                elif scheduled_task.interval_type == "cycles":
                                    # For cycle-based tasks, use the should_run check
                                    should_add = True
                                    logger.debug(
                                        f"Scheduled task '{scheduled_task.name}': cycle-based, will add"
                                    )

                            if not should_add:
                                logger.debug(
                                    f"Skipping scheduled task '{scheduled_task.name}' - not enough time elapsed"
                                )
                                continue

                            logger.info(
                                f"Adding scheduled task '{scheduled_task.name}' "
                                f"(cycle {self._cycle_count})"
                            )
                            try:
                                # Resolve the prompt (file or string)
                                prompt = scheduled_task.resolve_prompt(base_path)

                                # Add to task queue with scheduled_task_name in metadata
                                await self.task_queue.add_task(
                                    instruction=prompt,
                                    metadata={
                                        "scheduled_task_name": scheduled_task.name,
                                        **scheduled_task.metadata,
                                    },
                                )

                                # Mark as executed
                                scheduled_task.mark_executed(current_time)

                                logger.info(
                                    f"Scheduled task '{scheduled_task.name}' added to queue"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error adding scheduled task '{scheduled_task.name}': {e}",
                                    exc_info=True,
                                )

                    # Try to process one task
                    processed = await self.run_once()

                    if processed:
                        self._tasks_processed += 1

                    if not processed:
                        # No tasks available, wait before polling again
                        await asyncio.sleep(self.poll_interval)
                    else:
                        # Task was processed, check for more immediately
                        await asyncio.sleep(0.1)

                except asyncio.CancelledError:
                    logger.info("Agent loop cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in agent loop: {e}", exc_info=True)
                    # Sleep before retrying to prevent rapid-fire errors
                    await asyncio.sleep(30)

        finally:
            self.running = False
            logger.info(
                f"Agent loop stopped (processed {self._tasks_processed} tasks "
                f"in {self._cycle_count} cycles)"
            )

    def start_background(self):
        """Start the agent loop as a background task.

        Returns:
            The asyncio Task object
        """
        if self._task is not None and not self._task.done():
            logger.warning("Agent loop is already running")
            return self._task

        self._task = asyncio.create_task(self.run())
        logger.info("Agent loop started as background task")
        return self._task

    async def stop(self):
        """Stop the agent loop gracefully."""
        logger.info("Stopping agent loop...")
        self.running = False

        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Agent loop stopped")

    async def get_stats(self):
        """Get current task queue statistics.

        Returns:
            Dictionary with task counts by status and loop stats
        """
        queue_stats = self.task_queue.get_task_stats()
        queue_stats["loop_cycles"] = self._cycle_count
        queue_stats["tasks_processed"] = self._tasks_processed
        queue_stats["scheduled_tasks_enabled"] = self.enable_scheduled_tasks
        queue_stats["scheduled_tasks_count"] = len(self.scheduled_tasks)
        queue_stats["scheduled_tasks"] = [
            {
                "name": task.name,
                "enabled": task.enabled,
                "interval_type": task.interval_type,
                "last_execution": (
                    task.last_execution.isoformat() if task.last_execution else None
                ),
            }
            for task in self.scheduled_tasks
        ]
        return queue_stats


async def run_agent_loop(
    toolchain: ToolChain,
    control: Optional[Control] = None,
    poll_interval: int = 1,
):
    """Convenience function to run the agent loop.

    Args:
        toolchain: The MCP toolchain to use
        control: Optional Control instance
        poll_interval: Seconds between polls
    """
    loop = AgentLoop(toolchain, control, poll_interval)
    await loop.run()
