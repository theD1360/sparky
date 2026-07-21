"""Execute agent tasks (extracted from the former in-process AgentLoop)."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional
from uuid import uuid4

from events import BotEvents, TaskEvents
from services import TaskService, create_services
from sparky import AgentOrchestrator
from sparky.langchain_toolchain import LangChainToolchain
from sparky.middleware import (
    CommandPromptMiddleware,
    ResourceFetchingMiddleware,
    SelfModificationGuard,
)
from sparky.providers import GeminiProvider, ProviderConfig
from sparky.task_queue import TaskQueue
from utils.events import Events

logger = logging.getLogger(__name__)


class AgentTaskExecutor:
    """Runs a claimed agent task with a Bot instance and optional event sink."""

    def __init__(
        self,
        toolchain: LangChainToolchain,
        task_queue: TaskQueue,
        task_service: Optional[TaskService] = None,
    ):
        self.toolchain = toolchain
        self.task_queue = task_queue
        self.task_service = task_service or TaskService(task_queue=task_queue)
        self.events = Events()
        self.session_id = str(uuid4())
        self.user_id = "agent"
        self.tasks_processed = 0

        self.initial_system_message = """
You are the agent's subconscious, responsible for handling background tasks autonomously. Use all available tools and resources to achieve your objectives efficiently and independently. 
Before starting any task, consult your knowledge graph to gather relevant context. Do not duplicate tasks you have previously completed. 
Upon task completion, update your knowledge graph with your results and insights.
        """
        self.initial_system_response = """
Acknowledged. I will independently complete background tasks using all resources at my disposal, always consulting my knowledge graph before starting. 
I will avoid duplicating prior work, and I will update my knowledge graph upon completion to reflect task outcomes.
        """

    async def execute(
        self,
        task: Dict[str, Any],
        event_sink: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Execute a task that has already been claimed (status=in_progress).

        Args:
            task: Task dictionary
            event_sink: Optional sink with forward_* methods (RedisTaskEventSink)

        Returns:
            Result dict with status and optional response/error
        """
        task_id = task["id"]
        instruction = task.get("instruction") or ""
        metadata = task.get("metadata") or {}
        task_chat_id = metadata.get("chat_id")
        task_user_id = self.user_id

        if not instruction.strip():
            error_msg = f"Task {task_id} has empty instruction"
            await self.task_queue.update_task_status(task_id, "failed", error=error_msg)
            await self.events.async_dispatch(TaskEvents.TASK_FAILED, task_id, error_msg)
            return {"status": "failed", "error": error_msg}

        logger.info("Executing task %s: %s...", task_id, instruction[:80])

        if task_chat_id:
            try:
                from database.database import get_database_manager
                from database.repository import KnowledgeRepository

                db_manager = get_database_manager()
                if not db_manager.engine:
                    await db_manager.connect()
                repository = KnowledgeRepository(db_manager)
                chat_node = await repository.get_chat(task_chat_id)
                if chat_node and chat_node.properties:
                    chat_user_id = chat_node.properties.get("user_id")
                    if chat_user_id:
                        task_user_id = chat_user_id
                        logger.info(
                            "Task %s will execute in chat %s as user %s",
                            task_id,
                            task_chat_id,
                            task_user_id,
                        )
                    else:
                        logger.warning(
                            "Chat %s has no user_id, using default agent user",
                            task_chat_id,
                        )
                else:
                    logger.warning(
                        "Chat %s not found, task will create new chat", task_chat_id
                    )
                    task_chat_id = None
            except Exception as e:
                logger.error("Error looking up chat %s: %s", task_chat_id, e)
                task_chat_id = None

        try:
            await self.events.async_dispatch(TaskEvents.TASK_STARTED, task)

            if task_chat_id:
                chat_id = task_chat_id
                is_reused = False
                bot = None
            else:
                chat_id, bot, is_reused = self.task_service.get_or_create_task_chat(task)

            if event_sink is None:
                from commands.events import RedisTaskEventSink

                event_sink = RedisTaskEventSink(
                    user_id=task_user_id,
                    chat_id=chat_id,
                    task_id=task_id,
                )

            await event_sink.forward_status(
                f"Task {task_id}: Starting execution..."
            )

            if not is_reused or task_chat_id:
                chat_name = (
                    f"Task: {task_id[:8]}"
                    if task_chat_id
                    else self.task_service.get_task_chat_name(task)
                )
                logger.info(
                    "Creating bot for task %s chat_id=%s user=%s",
                    task_id,
                    chat_id,
                    task_user_id,
                )
                model_name = os.getenv("AGENT_MODEL", "gemini-2.5-flash")
                config = ProviderConfig(model_name=model_name)
                provider = GeminiProvider(config)

                from database.database import get_database_manager
                from database.repository import KnowledgeRepository

                db_manager = get_database_manager()
                if not db_manager.engine:
                    await db_manager.connect()
                repository = KnowledgeRepository(db_manager)
                events = Events()
                services = create_services(
                    repository=repository,
                    identity_search_terms=None,
                    events=events,
                    provider=provider,
                )

                bot = AgentOrchestrator(
                    provider=provider,
                    message_service=services["message_service"],
                    user_service=services["user_service"],
                    identity_service=services["identity_service"],
                    file_service=services["file_service"],
                    chat_service=services["chat_service"],
                    token_service=services["token_service"],
                    langchain_toolchain=self.toolchain,
                    middlewares=[
                        SelfModificationGuard(),
                        ResourceFetchingMiddleware(),
                        CommandPromptMiddleware(),
                    ],
                )

                if not task_chat_id:
                    scheduled_task_name = self.task_service.get_scheduled_task_name(
                        task
                    )
                    if scheduled_task_name:
                        self.task_service.scheduled_task_chats[scheduled_task_name] = (
                            chat_id,
                            bot,
                        )
                    self.task_service.bot_instances[chat_id] = bot

                await bot.start_chat(
                    user_id=task_user_id,
                    chat_id=chat_id,
                    chat_name=chat_name,
                )
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
                self._subscribe_bot_events(bot, event_sink, chat_id)

            await event_sink.forward_status(
                f"Executing task: {instruction[:80]}..."
            )
            response = await bot.send_message(instruction, task_id)

            await self.task_queue.update_task_status(
                task_id, "completed", response=response
            )
            await self.events.async_dispatch(
                TaskEvents.TASK_COMPLETED, task_id, response
            )
            await event_sink.forward_status(
                f"Task {task_id} completed successfully"
            )
            self.tasks_processed += 1
            logger.info("Task %s completed successfully", task_id)
            return {"status": "completed", "response": response, "chat_id": chat_id}

        except Exception as e:
            logger.error("Task %s failed: %s", task_id, e, exc_info=True)
            await self.task_queue.update_task_status(task_id, "failed", error=str(e))
            await self.events.async_dispatch(TaskEvents.TASK_FAILED, task_id, str(e))
            if event_sink is not None:
                try:
                    await event_sink.forward_error(f"Task {task_id} failed: {e}")
                except Exception:
                    pass
            return {"status": "failed", "error": str(e)}

    def _subscribe_bot_events(
        self, bot: AgentOrchestrator, event_sink: Any, chat_id: str
    ) -> None:
        async def on_tool_use(tool_name: str, tool_args: dict):
            await event_sink.forward_tool_use(tool_name, tool_args)

        async def on_tool_result(tool_name: str, result: str, status: str = None):
            await event_sink.forward_tool_result(tool_name, result, status)

        async def on_thought(thought: str):
            await event_sink.forward_thought(thought)

        async def on_message_sent(message: str):
            if not message.strip().startswith("You are the agent's subconscious"):
                await event_sink.forward_message(message)

        async def on_message_received(message: str):
            await event_sink.forward_message(message)

        bot.events.subscribe(BotEvents.TOOL_USE, on_tool_use)
        bot.events.subscribe(BotEvents.TOOL_RESULT, on_tool_result)
        bot.events.subscribe(BotEvents.THOUGHT, on_thought)
        bot.events.subscribe(BotEvents.MESSAGE_SENT, on_message_sent)
        bot.events.subscribe(BotEvents.MESSAGE_RECEIVED, on_message_received)
        logger.info("Subscribed to bot events for task chat %s", chat_id)
