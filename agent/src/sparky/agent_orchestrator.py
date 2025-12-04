"""Agent orchestrator for coordinating chat interactions across multiple LLM providers."""

import asyncio
import datetime
import logging.handlers
import os
import time
import traceback
from typing import Any, Coroutine, List, Optional
from uuid import uuid4

from badmcp.tool_chain import ToolChain
from database.database import get_database_manager
from database.repository import KnowledgeRepository
from events import BotEvents
from services import (
    FileService,
    IdentityService,
    KnowledgeService,
    MessageService,
    UserService,
)
from utils.async_util import run_async
from utils.events import Events

from .history_utils import convert_nodes_to_llm_format, format_nodes_for_summary
from .logging_config import setup_logging
from .middleware import BaseMiddleware, MiddlewareRegistry, ToolCallContext
from .providers import GeminiProvider, LLMProvider, ProviderConfig
from .tool_registry import ToolResult

setup_logging()
logger = logging.getLogger(__name__)


class AgentOrchestrator:
    _last_add_task_time = None
    """Agent orchestrator that coordinates chat interactions with LLM providers.

    This class serves as the orchestration layer, tying together:
    - LLM providers (Gemini, Claude, OpenAI, etc.)
    - Tool execution via MCP toolchain
    - Middleware for message/tool processing
    - Knowledge graph integration
    - Event system for lifecycle hooks
    - Chat history management

    The orchestrator is LLM-agnostic and delegates provider-specific operations
    to the configured LLMProvider implementation.
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        provider: LLMProvider,
        middlewares: Optional[List[BaseMiddleware]] = None,
        initial_context_added: bool = False,
        on_load: Optional[Coroutine] = None,
        on_tool_use: Optional[Coroutine] = None,
        on_tool_result: Optional[Coroutine] = None,
        on_thought: Optional[Coroutine] = None,
        toolchain: Optional[ToolChain] = None,
        knowledge: Optional[Any] = None,
        identity_search_terms: Optional[List[str]] = None,
        identity_max_depth: int = 2,
    ):
        """Initialize the agent orchestrator.

        Args:
            provider: LLMProvider instance (required) for handling LLM interactions
            middlewares: List of middleware to apply to messages and tools
            on_load: Deprecated. Use events.subscribe(BotEvents.LOAD, handler) instead.
            on_tool_use: Deprecated. Use events.subscribe(BotEvents.TOOL_USE, handler) instead.
            on_tool_result: Deprecated. Use events.subscribe(BotEvents.TOOL_RESULT, handler) instead.
            on_thought: Deprecated. Use events.subscribe(BotEvents.THOUGHT, handler) instead.
            toolchain: ToolChain instance with available tools.
            knowledge: Knowledge module instance. If None, creates default Knowledge module in start_chat.
            identity_search_terms: Custom search terms for finding identity memories.
            identity_max_depth: Maximum graph traversal depth when loading identity. (Unused - kept for backward compatibility)
            enable_turn_summarization: DEPRECATED. Token-based summarization is now used automatically.
            summary_turn_threshold: DEPRECATED. Use SPARKY_SUMMARY_TOKEN_THRESHOLD instead.
        """
        self._session_id = None  # Will be set in start_chat
        self._chat_id = None  # Will be set in start_chat if provided
        self.identity_max_depth = identity_max_depth
        self._last_add_task_time = None
        self.identity_search_terms = identity_search_terms
        self.initial_context_added = initial_context_added

        # Initialize event system
        self.events = Events()

        self.provider = provider
        self.toolchain = toolchain

        # Fallback message count limit (only used when token limit is disabled)
        # Token budget is the primary mechanism for limiting context
        self.fallback_message_limit = 200  # Reasonable default for count-based fallback

        # Token-based summarization configuration
        # Default to 90% (increased from 85% to reduce aggressive summarization)
        summary_threshold_env = os.getenv("SPARKY_SUMMARY_TOKEN_THRESHOLD")
        if summary_threshold_env:
            try:
                self.summary_token_threshold = float(summary_threshold_env)
                # Clamp between 0.5 and 0.95
                self.summary_token_threshold = max(
                    0.5, min(0.95, self.summary_token_threshold)
                )
                logger.info(
                    "Summary will trigger at %.1f%% of token budget",
                    self.summary_token_threshold * 100,
                )
            except ValueError:
                logger.warning(
                    "Invalid SPARKY_SUMMARY_TOKEN_THRESHOLD value '%s', using default 0.90",
                    summary_threshold_env,
                )
                self.summary_token_threshold = 0.90
        else:
            # Default to 90% threshold to reduce aggressive summarization
            self.summary_token_threshold = 0.90
            logger.info(
                "Using default summary threshold: %.1f%% of token budget",
                self.summary_token_threshold * 100,
            )

        # Warn about deprecated environment variable

        # Token budget configuration
        # Get token budget percentage from environment or use provider's default
        token_budget_env = os.getenv("SPARKY_TOKEN_BUDGET_PERCENT")
        if token_budget_env:
            try:
                token_budget_percent = float(token_budget_env)
                # Clamp between 0.1 and 1.0
                token_budget_percent = max(0.1, min(1.0, token_budget_percent))
                self.provider.config.token_budget_percent = token_budget_percent
                logger.info(
                    "Using token budget: %.1f%% of context window",
                    token_budget_percent * 100,
                )
            except ValueError:
                logger.warning(
                    "Invalid SPARKY_TOKEN_BUDGET_PERCENT value '%s', using default %.1f%%",
                    token_budget_env,
                    self.provider.config.token_budget_percent * 100,
                )

        # Initialize services (will be set up in start_chat when repository is available)
        self.message_service: Optional[MessageService] = None
        self.user_service: Optional[UserService] = None
        self.identity_service: Optional[IdentityService] = None
        self.file_service: Optional[FileService] = None

        # Keep old callbacks for backward compatibility
        self.on_tool_use = on_tool_use
        self.on_tool_result = on_tool_result
        self.on_thought = on_thought
        self.on_load = on_load

        # If old-style callbacks are provided, automatically subscribe them
        if on_tool_use:
            self.events.subscribe(BotEvents.TOOL_USE, on_tool_use)
        if on_tool_result:
            self.events.subscribe(BotEvents.TOOL_RESULT, on_tool_result)
        if on_thought:
            self.events.subscribe(BotEvents.THOUGHT, on_thought)
        if on_load:
            self.events.subscribe(BotEvents.LOAD, on_load)

        # Configure and initialize the provider
        self.provider.configure()
        self.model, self._safe_to_original = self.provider.initialize_model(toolchain)

        self.chat = None

        # Store the knowledge instance if provided
        # Otherwise, it will be created in start_chat with the session_id
        self.knowledge = knowledge

        # Initialize the middleware registry (handles all dispatcher creation and routing)

        self.middleware_registry = MiddlewareRegistry(self)

        # Register middlewares using the registry
        if middlewares:
            self.middleware_registry.register_many(middlewares)

        # Expose dispatchers for direct access (backward compatibility)
        self.tool_dispatcher = self.middleware_registry.tool_dispatcher
        self.message_dispatcher = self.middleware_registry.message_dispatcher
        self.response_dispatcher = self.middleware_registry.response_dispatcher

        # Subscribe knowledge module to bot events if present
        if self.knowledge:
            self.knowledge.subscribe_to_bot_events(self.events)

    def add_task(self, instruction: str, metadata: dict | None = None):
        # Implement rate limiting
        if (
            self._last_add_task_time is not None
            and (time.time() - self._last_add_task_time) < 30
        ):
            logger.warning("Rate limiting add_task calls.")
            return

        self._last_add_task_time = time.time()

        # Register event handlers for graph message storage
        self._register_event_handlers()

        # Dispatch load event synchronously for backward compatibility
        if self.on_load:
            self.on_load(self)

    @property
    def session_id(self) -> Optional[str]:
        """Returns the current session_id, or None if chat hasn't been started."""
        return self._session_id

    def _run_async(self, coro):
        """Helper to run async function from sync context."""
        try:
            loop = asyncio.get_running_loop()
            # If we're in an async context, create a task
            asyncio.create_task(coro)
        except RuntimeError:
            # No event loop running, create a new one
            asyncio.run(coro)

    def _register_event_handlers(self):
        """Register event handlers for storing messages to the knowledge graph.

        This method is called automatically during start_chat() to ensure messages are
        properly stored. It's idempotent - safe to call multiple times.
        """
        # Check if already registered to avoid duplicate subscriptions
        if (
            hasattr(self, "_event_handlers_registered")
            and self._event_handlers_registered
        ):
            logger.debug("Event handlers already registered, skipping")
            return

        self.events.subscribe(
            BotEvents.MESSAGE_SENT,
            lambda message: self._handle_message_sent(message),
        )
        self.events.subscribe(
            BotEvents.MESSAGE_RECEIVED,
            lambda message: self._handle_message_received(message),
        )
        self.events.subscribe(
            BotEvents.TOOL_USE,
            lambda tool_name, args: self._handle_tool_use(tool_name, args),
        )
        self.events.subscribe(
            BotEvents.TOOL_RESULT,
            lambda tool_name, result, status=None: self._handle_tool_result(
                tool_name, result, status
            ),
        )
        self.events.subscribe(
            BotEvents.THOUGHT,
            lambda thought: self._handle_thought(thought),
        )
        self.events.subscribe(
            BotEvents.SUMMARIZED,
            lambda summary, turn_count: self._handle_summarized(summary, turn_count),
        )

        self._event_handlers_registered = True
        logger.debug("Registered event handlers for graph message storage")

    def _handle_message_sent(self, message: str):
        """Handle MESSAGE_SENT event by delegating to message service."""
        if self.message_service:
            self._run_async(
                self.message_service.save_message(
                    content=message,
                    role="user",
                    session_id=self._session_id,
                    chat_id=self._chat_id,
                    message_type="message",
                    file_node_id=getattr(self, "_current_file_id", None),
                )
            )

    def _handle_message_received(self, message: str):
        """Handle MESSAGE_RECEIVED event by delegating to message service."""
        if self.message_service:
            self._run_async(
                self.message_service.save_message(
                    content=message,
                    role="model",
                    session_id=self._session_id,
                    chat_id=self._chat_id,
                    message_type="message",
                )
            )

    def _handle_tool_use(self, tool_name: str, args: dict):
        """Handle TOOL_USE event by delegating to message service."""
        if self.message_service:
            self._run_async(
                self.message_service.save_message(
                    content=f"Using tool: {tool_name} with args: {args}",
                    role="model",
                    session_id=self._session_id,
                    chat_id=self._chat_id,
                    message_type="tool_use",
                    tool_name=tool_name,
                    tool_args=args,
                )
            )

    def _handle_tool_result(self, tool_name: str, result: Any, status: str = None):
        """Handle TOOL_RESULT event by delegating to message service."""
        if self.message_service:
            self._run_async(
                self.message_service.save_message(
                    content=f"Tool {tool_name} result: {result}",
                    role="model",
                    session_id=self._session_id,
                    chat_id=self._chat_id,
                    message_type="tool_result",
                    tool_name=tool_name,
                )
            )

    def _handle_thought(self, thought: str):
        """Handle THOUGHT event by delegating to message service."""
        if self.message_service:
            self._run_async(
                self.message_service.save_message(
                    content=thought,
                    role="model",
                    session_id=self._session_id,
                    chat_id=self._chat_id,
                    message_type="thought",
                )
            )

    def _handle_summarized(self, summary: str):
        """Handle SUMMARIZED event by delegating to message service.

        Args:
            summary: The conversation summary
        """

        if self.message_service:
            self._run_async(
                self.message_service.save_message(
                    content=summary,
                    role="user",
                    session_id=self._session_id,
                    chat_id=self._chat_id,
                    internal=True,
                    message_type="summary",
                )
            )

    def get_effective_token_budget(self) -> int:
        """Get the effective token budget based on model's context window and configured percentage.

        Returns:
            Effective token budget in tokens
        """
        context_window = self.provider.get_model_context_window()
        effective_budget = int(
            context_window * self.provider.config.token_budget_percent
        )
        logger.debug(
            "Token budget: %d tokens (%.1f%% of %d)",
            effective_budget,
            self.provider.config.token_budget_percent * 100,
            context_window,
        )
        return effective_budget

    async def _should_summarize(self) -> bool:
        """Check if conversation should be summarized based on token usage.

        Returns True if messages since last summary exceed the token threshold.
        Includes safeguards to prevent premature summarization:
        - Requires minimum of 10 message exchanges (20 total messages)
        - Requires conversation to be at least 5 minutes old
        - Requires token threshold to be exceeded

        Returns:
            True if summarization is needed, False otherwise
        """
        if not self.message_service or not self._chat_id:
            return False

        try:
            # Get all messages from the graph
            nodes = await self.knowledge.repository.get_chat_messages(
                chat_id=self._chat_id, limit=None
            )

            if not nodes:
                logger.debug("No messages found, skipping summarization check")
                return False

            # Find the most recent summary
            most_recent_summary_idx = -1
            for i in range(len(nodes) - 1, -1, -1):
                node = nodes[i]
                if node.properties and node.properties.get("message_type") == "summary":
                    most_recent_summary_idx = i
                    break

            # Get messages since last summary (or all if no summary exists)
            if most_recent_summary_idx >= 0:
                messages_to_check = nodes[most_recent_summary_idx + 1 :]
            else:
                messages_to_check = nodes

            # Safeguard 1: Minimum message count (at least 20 messages = ~10 exchanges)
            # Don't summarize very short conversations
            if len(messages_to_check) < 20:
                logger.debug(
                    "Skipping summarization: only %d messages (need at least 20)",
                    len(messages_to_check),
                )
                return False

            # Safeguard 2: Conversation age check (at least 5 minutes old)
            # Don't summarize very recent conversations
            if messages_to_check:
                first_message = messages_to_check[0]
                if first_message.created_at:
                    conversation_age = (
                        datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
                        - first_message.created_at
                    )
                    min_age_minutes = 5
                    if conversation_age.total_seconds() < min_age_minutes * 60:
                        logger.debug(
                            "Skipping summarization: conversation only %.1f minutes old (need at least %d)",
                            conversation_age.total_seconds() / 60,
                            min_age_minutes,
                        )
                        return False

            # Convert to LLM format for token estimation
            # Note: Using internal method as MessageService doesn't expose this publicly
            # pylint: disable=protected-access
            messages = self.message_service._convert_nodes_to_llm_format(
                messages_to_check
            )
            # pylint: enable=protected-access

            if not messages:
                logger.debug(
                    "No messages to check after conversion, skipping summarization"
                )
                return False

            # Estimate tokens
            estimated_tokens = self.message_service.estimate_tokens(messages)

            # Get effective budget and threshold
            effective_budget = self.get_effective_token_budget()
            threshold_tokens = int(effective_budget * self.summary_token_threshold)

            should_summarize = estimated_tokens >= threshold_tokens

            if should_summarize:
                logger.info(
                    "Summarization needed: %d messages, %d tokens >= %d threshold (%.1f%% of %d budget)",
                    len(messages_to_check),
                    estimated_tokens,
                    threshold_tokens,
                    self.summary_token_threshold * 100,
                    effective_budget,
                )
            else:
                logger.debug(
                    "No summarization needed: %d tokens < %d threshold (%d messages)",
                    estimated_tokens,
                    threshold_tokens,
                    len(messages_to_check),
                )

            return should_summarize
        # pylint: disable=broad-except
        except Exception as e:
            # pylint: enable=broad-except
            logger.warning("Failed to check if summarization needed: %s", e)
            return False

    async def _get_recent_messages(
        self, limit: Optional[int] = None, use_token_limit: bool = True
    ) -> List[dict]:
        """Retrieve recent messages from the knowledge graph and convert to LLM format.

        Prioritizes summaries over old chat history to reduce token usage:
        - If summaries exist, only includes messages after the most recent summary
        - Includes the summary itself to provide context
        - This prevents loading all historical messages when they've been summarized

        Args:
            limit: Maximum number of messages to retrieve. If None, uses fallback_message_limit.
            use_token_limit: If True, uses token budget to limit messages instead of count.

        Returns:
            List of messages in LLM format: [{"role": "user/model", "parts": ["content"]}]
        """
        # Delegate to message service if available
        if self.message_service:
            # If using token limits, get messages within budget
            if use_token_limit:
                token_budget = self.get_effective_token_budget()
                return await self.message_service.get_messages_within_token_limit(
                    chat_id=self._chat_id,
                    max_tokens=token_budget,
                    prefer_summaries=True,
                )

            # Otherwise use count-based limit
            if limit is None:
                limit = self.fallback_message_limit

            return await self.message_service.get_recent_messages(
                chat_id=self._chat_id, limit=limit, prefer_summaries=True
            )

        # Fallback to old implementation if service not available
        if not self.knowledge or not self.knowledge.repository:
            logger.warning(
                "Cannot retrieve messages: knowledge module or repository is None"
            )
            return []

        if not self._chat_id:
            logger.debug("No chat_id provided - starting fresh chat with no history")
            return []

        # Calculate limit if not provided
        if limit is None:
            limit = self.fallback_message_limit

        try:
            # Get all messages from the graph
            nodes = await self.knowledge.repository.get_chat_messages(
                chat_id=self._chat_id, limit=None
            )

            # Find the most recent summary
            most_recent_summary_idx = -1
            for i in range(len(nodes) - 1, -1, -1):
                node = nodes[i]
                if node.properties and node.properties.get("message_type") == "summary":
                    most_recent_summary_idx = i
                    break

            # If we found a summary, only include messages from that point forward
            if most_recent_summary_idx >= 0:
                nodes = nodes[most_recent_summary_idx:]
                logger.info(
                    f"Found summary at index {most_recent_summary_idx}, "
                    f"using {len(nodes)} messages from that point forward"
                )
            else:
                # No summary found, take the last N messages to stay within context window
                nodes = nodes[-limit:] if len(nodes) > limit else nodes
                logger.info(f"No summary found, using last {len(nodes)} messages")

            # Convert to LLM format
            messages = convert_nodes_to_llm_format(nodes)

            logger.info(
                f"Retrieved {len(messages)} messages from graph for chat {self._chat_id}"
            )
            return messages

        except Exception as e:
            logger.error(f"Failed to retrieve messages from graph: {e}", exc_info=True)
            return []

    async def list_prompts(self):
        """List available prompts from the toolchain.

        Returns:
            List of (client_index, prompt) tuples
        """
        if not self.toolchain:
            return []
        return await self.toolchain.list_all_prompts()

    async def get_prompt(self, name: str, arguments: Optional[dict] = None):
        """Get and render a prompt by name.

        Args:
            name: Prompt name
            arguments: Optional arguments for the prompt

        Returns:
            Rendered prompt text
        """
        if not self.toolchain:
            raise ValueError("No toolchain available for prompts")
        return await self.toolchain.get_prompt(name, arguments or {})

    async def list_resources(self):
        """List available resources from the toolchain.

        Returns:
            List of (client_index, resource) tuples
        """
        if not self.toolchain:
            return []
        return await self.toolchain.list_all_resources()

    async def read_resource(self, uri: str):
        """Read a resource by URI.

        Args:
            uri: Resource URI

        Returns:
            Resource content as string
        """
        if not self.toolchain:
            raise ValueError("No toolchain available for resources")
        return await self.toolchain.read_resource(uri)

    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str,
        file_size: int,
        user_id: Optional[str] = None,
        ai_description_callback: Optional[Any] = None,
    ) -> Optional[str]:
        """Upload a file through the file service.

        Args:
            file_content: Binary file content
            filename: Original filename
            mime_type: MIME type of the file
            file_size: Size of the file in bytes
            user_id: Optional user ID who uploaded the file
            ai_description_callback: Optional async function to generate AI description

        Returns:
            File node ID if successful, None otherwise
        """
        if not self.file_service:
            logger.error("File service not initialized, cannot upload file")
            return None

        return await self.file_service.upload_file(
            file_content=file_content,
            filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            user_id=user_id,
            session_id=self._session_id,
            ai_description_callback=ai_description_callback,
        )

    async def _add_message_with_chat_node(
        self,
        message: str,
        role: str = "user",
        internal: bool = False,
        message_type: str = "message",
        tool_name: Optional[str] = None,
        tool_args: Optional[dict] = None,
        file_node_id: Optional[str] = None,
    ) -> None:
        """Create a corresponding ChatMessage node in the knowledge graph.

        DEPRECATED: This method is kept for backward compatibility but delegates
        to MessageService when available.

        Args:
            message: The message content
            role: The role of the speaker (e.g., 'user', 'model')
            internal: Whether this is an internal/system message that shouldn't be displayed to users
            message_type: The type of message (e.g., 'message', 'tool_use', 'tool_result', 'thought', 'summary', 'internal')
            tool_name: Optional tool name for tool_use and tool_result messages
            tool_args: Optional tool arguments for tool_use messages
            file_node_id: Optional file node ID for attachments
        """
        # Delegate to message service if available
        if self.message_service and self._session_id:
            self._run_async(
                self.message_service.save_message(
                    content=message,
                    role=role,
                    session_id=self._session_id,
                    chat_id=self._chat_id,
                    internal=internal,
                    message_type=message_type,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    file_node_id=file_node_id,
                )
            )
            return

        # Fallback to direct implementation if service not available
        if not self.knowledge:
            logger.warning(
                f"Cannot save message to graph: knowledge module is None (role={role})"
            )
            return

        if not self._session_id:
            logger.warning(
                f"Cannot save message to graph: session_id is None (role={role})"
            )
            return

        try:
            # Get current message count from graph for this chat
            if self._chat_id:
                current_messages = await self.knowledge.repository.get_chat_messages(
                    chat_id=self._chat_id
                )
                message_num = len(current_messages) + 1
            else:
                # Fallback: use timestamp-based ID
                message_num = int(datetime.datetime.utcnow().timestamp() * 1000)

            chat_node_id = f"chat:{self._session_id}:{message_num}"

            logger.info(
                f"Saving message to graph: node_id={chat_node_id}, role={role}, chat_id={self._chat_id}, internal={internal}, message_type={message_type}"
            )

            # Build properties with role, internal flag, message type, and optional tool data
            properties = {
                "role": role,
                "internal": internal,
                "message_type": message_type,
            }

            # Add tool-specific properties if provided
            if tool_name:
                properties["tool_name"] = tool_name
            if tool_args:
                properties["tool_args"] = tool_args

            await self.knowledge.repository.add_node(
                node_id=chat_node_id,
                node_type="ChatMessage",
                label=f"Chat Message {message_num}",
                content=message,
                properties=properties,
            )
            await self.knowledge.repository.add_edge(
                source_id=self._session_id,
                target_id=chat_node_id,
                edge_type="CONTAINS",
            )

            # Also link from chat node if chat_id is available
            if self._chat_id:
                logger.info(
                    f"Linking message to chat node: chat:{self._chat_id} -> {chat_node_id}"
                )
                await self.knowledge.repository.add_edge(
                    source_id=f"chat:{self._chat_id}",
                    target_id=chat_node_id,
                    edge_type="CONTAINS",
                )
            else:
                logger.info("No chat_id available, skipping chat-to-message link")

            # Link file attachment if provided
            if file_node_id:
                logger.info(
                    f"Linking file to message: {chat_node_id} -> {file_node_id}"
                )
                await self.knowledge.repository.add_edge(
                    source_id=chat_node_id,
                    target_id=file_node_id,
                    edge_type="HAS_ATTACHMENT",
                )

            logger.info(f"Successfully saved message to graph: {chat_node_id}")
        except Exception as e:
            logger.error(f"Failed to create chat node: {e}", exc_info=True)

    async def start_chat(
        self,
        history: Optional[list] = None,
        user_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        chat_name: Optional[str] = None,
        preloaded_identity: Optional[str] = None,
        preloaded_identity_summary: Optional[str] = None,
    ):
        """Asynchronously initializes the chat.


        Args:
            history: Optional initial chat history
            user_id: User identifier for this chat. If None, uses 'default'.
            chat_id: Optional chat identifier. If provided, creates a Chat node.
            chat_name: Optional chat name. Used when creating a Chat node.
            preloaded_identity: Optional pre-loaded identity memory (to avoid reloading)
            preloaded_identity_summary: Optional pre-loaded identity summary (to avoid re-summarizing)
        """
        # Store chat_id for linking messages to the chat node
        self._chat_id = chat_id
        # Use chat_id as session identifier for Knowledge (backward compatibility with Knowledge class)
        self._session_id = (
            chat_id
            if chat_id
            else f"{user_id}:{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        )

        # Use provided user_id or default
        if not user_id:
            user_id = "default"
            logger.info("No user_id provided, using default")
        else:
            logger.info(f"Starting chat with user_id: {user_id}")

        user_node_id = f"user:{user_id}"

        # Initialize or update Knowledge module with the chat_id
        if self.knowledge is None and self.toolchain is not None:
            # Create repository first
            db_url = os.getenv("SPARKY_DB_URL")
            if not db_url:
                logger.warning(
                    "SPARKY_DB_URL not set, KnowledgeService will not be initialized"
                )
            else:
                try:
                    db_manager = get_database_manager(db_url=db_url)
                    db_manager.connect()
                    repository = KnowledgeRepository(db_manager)

                    # Use chat_id as the session identifier for Knowledge (each chat has its own memory context)
                    self.knowledge = KnowledgeService(
                        repository=repository,
                        session_id=self._session_id,
                        model=None,
                        identity_search_terms=self.identity_search_terms,
                    )
                    # Subscribe to bot events
                    self.knowledge.subscribe_to_bot_events(self.events)
                    logger.info("Initialized KnowledgeService with repository")
                except Exception as e:
                    logger.error(
                        f"Failed to initialize KnowledgeService: {e}", exc_info=True
                    )

        elif self.knowledge is not None:
            # Update existing Knowledge module with new chat_id
            # This requires recreating certain session-specific components
            self.knowledge.session_id = self._session_id
            self.knowledge._mem_transcript_key = (
                f"chat:session:{self._session_id}:transcript"
            )
            self.knowledge._mem_summary_key = f"chat:session:{self._session_id}:summary"
            # Reset turn index for new session
            self.knowledge._turn_index = 0
            # Clear associated memories tracking for new session
            self.knowledge._associated_memories = set()

        # Initialize services now that we have access to the repository
        if self.knowledge and self.knowledge.repository:
            # Initialize file service first since message service depends on it
            if not self.file_service:
                self.file_service = FileService(self.knowledge.repository)
                logger.debug("Initialized FileService")

            if not self.message_service:
                self.message_service = MessageService(
                    self.knowledge.repository, file_service=self.file_service
                )
                logger.debug("Initialized MessageService")

            if not self.user_service:
                self.user_service = UserService(self.knowledge.repository)
                logger.debug("Initialized UserService")

            if not self.identity_service:
                self.identity_service = IdentityService(
                    self.knowledge.repository,
                    identity_search_terms=self.identity_search_terms,
                )
                logger.debug("Initialized IdentityService")

            # Initialize token usage service with message service's token estimator
            # Pass provider so service can monitor it (inversion of control)
            if not hasattr(self, "token_service"):
                from services.token_usage import TokenUsageService

                self.token_service = TokenUsageService(
                    token_estimator=self.message_service.token_estimator,
                    events=self.events,
                    provider=self.provider,
                )
                logger.debug("Initialized TokenUsageService")

            # Register event handlers for database persistence
            # This ensures thoughts, tool calls, etc. are saved to the knowledge graph
            self._register_event_handlers()

        # Create nodes and edges in the knowledge graph
        if self.knowledge and self.knowledge.repository:
            try:
                # Create user node using UserService
                if self.user_service:
                    await self.user_service.create_user(user_id)
                else:
                    # Fallback to direct creation
                    await self.knowledge.repository.add_node(
                        node_id=user_node_id,
                        node_type="User",
                        label=f"User {user_id}",
                        content=f"User with ID {user_id}",
                        properties={"user_id": user_id},
                    )
                    logger.info(f"Created User node: {user_node_id}")

                # Create Chat node if chat_id is provided
                if chat_id:
                    chat_node_id = f"chat:{chat_id}"

                    # CHECK IF CHAT ALREADY EXISTS to prevent duplicates
                    existing_chat = await self.knowledge.repository.get_node(
                        chat_node_id
                    )

                    if existing_chat:
                        logger.info(f"Chat {chat_node_id} already exists, reusing it")
                        # Verify the edge exists
                        try:
                            edges = await self.knowledge.repository.get_edges(
                                source_id=chat_node_id,
                                target_id=user_node_id,
                                edge_type="BELONGS_TO",
                            )
                            if not edges:
                                # Edge missing, recreate it
                                await self.knowledge.repository.add_edge(
                                    source_id=chat_node_id,
                                    target_id=user_node_id,
                                    edge_type="BELONGS_TO",
                                )
                                logger.info("Recreated missing BELONGS_TO edge")
                        except Exception as e:
                            logger.warning(f"Failed to verify chat edge: {e}")
                    else:
                        # Only create if it doesn't exist - use repository.create_chat
                        display_name = chat_name or f"Chat {chat_id[:8]}"
                        chat_node = await self.knowledge.repository.create_chat(
                            chat_id=chat_id,
                            chat_name=display_name,
                            user_id=user_id,
                        )
                        if chat_node:
                            logger.info(f"Created NEW Chat node: {chat_node_id}")
                        else:
                            logger.warning(
                                f"Failed to create chat node: {chat_node_id}"
                            )

            except Exception as e:
                logger.error(
                    f"Failed to create session/user/chat nodes or edges: {e}",
                    exc_info=True,
                )

        # Provide model to knowledge module
        if self.knowledge:
            self.knowledge.model = self.model

        history = history or []

        # Use preloaded identity if provided, otherwise load it
        if preloaded_identity and preloaded_identity_summary:
            logger.info("Using pre-loaded identity from session cache")
            identity_memory = preloaded_identity
            identity_summary = preloaded_identity_summary
        else:
            # Load identity and session context in parallel using services
            if self.identity_service:
                # Use IdentityService for loading identity
                identity_memory = await self.identity_service.get_identity_memory()
            elif self.knowledge:
                # Fallback to identity service if service not available
                identity_memory = await self.identity_service.get_identity_memory()
            else:
                identity_memory = "Error: No knowledge module available"

            # Handle exceptions
            if isinstance(identity_memory, Exception):
                logger.error("Failed to load identity: %s", identity_memory)
                identity_memory = "## Identity Loading Failed\n\nCannot load identity."

            # Summarize the identity to reduce token usage using IdentityService
            if self.identity_service:
                identity_summary = await self.identity_service.summarize_identity(
                    identity_memory, self.generate
                )
            else:
                # Fallback to direct summarization
                identity_summary_prompt = f"Summarize the following identity document into a concise paragraph, retaining the core concepts, purpose, and values:\n\n{identity_memory}"
                identity_summary = await self.generate(identity_summary_prompt)

        # Load session context (always fresh per chat)
        if self.identity_service:
            session_context = await self.identity_service.get_session_context(
                self._session_id
            )
        elif self.knowledge:
            session_context = await self.identity_service.get_session_context(
                self._session_id
            )
        else:
            session_context = None

        # Handle session context exceptions
        if isinstance(session_context, Exception):
            logger.warning("Failed to load session context: %s", session_context)
            session_context = None

        # Format identity instruction
        if self.identity_service:
            identity_instruction = self.identity_service.format_identity_instruction(
                identity_summary
            )
        else:
            identity_instruction = f"# Your Identity\n\n{identity_summary}\n\nPlease remember this is who you are and act accordingly in all responses."

        if not self.initial_context_added:
            await self._add_message_with_chat_node(
                identity_instruction, "user", internal=True, message_type="internal"
            )
            await self._add_message_with_chat_node(
                "I understand my identity and purpose. I'm ready to help you.",
                "model",
                internal=True,
                message_type="internal",
            )
            await self._add_message_with_chat_node(
                f"# Session Context\n\n{session_context}",
                "user",
                internal=True,
                message_type="internal",
            )
            await self._add_message_with_chat_node(
                "I understand my session context. I'm ready to help you.",
                "model",
                internal=True,
                message_type="internal",
            )
            self.initial_context_added = True

        # Check if summarization is needed before loading messages
        if await self._should_summarize():
            logger.info("Proactively summarizing conversation before loading messages")
            await self._summarize_conversation()

        # Get truncated history from the graph (last N messages)
        truncated_history = await self._get_recent_messages()

        # Estimate tokens for initial history and dispatch estimate event
        if truncated_history and hasattr(self, "token_service"):
            try:
                history_tokens = self.token_service.estimate_messages_list(
                    truncated_history
                )
                logger.info(f"Estimated {history_tokens} tokens for chat history")
                await self.token_service.emit_estimate(history_tokens, "history")
            except Exception as e:
                logger.warning(f"Failed to estimate history tokens: {e}")

        enable_auto_fc = self.toolchain is None
        self.chat = await self.provider.start_chat(
            history=truncated_history,
            enable_auto_function_calling=enable_auto_fc,
        )

        # Dispatch chat started event
        await self.events.async_dispatch(BotEvents.CHAT_STARTED, self.chat)

        return self.chat

    async def execute_tool_call(self, tool_name: str, tool_args: dict) -> ToolResult:
        """
        Executes a tool call through the middleware dispatcher.
        NOTE: DO NOT SHIM TOOL CALLS HERE. ALL TOOL CALLS SHOULD BE HANDLED BY THE ToolDispatcher!
        """
        context = ToolCallContext(
            tool_name=tool_name, tool_args=tool_args, bot_instance=self
        )

        return await self.tool_dispatcher.dispatch(context)

    async def send_message(
        self, message: str, task_id: Optional[str] = None, file_id: Optional[str] = None
    ) -> str:
        """Send a message and get a response.


        Args:
            message: The message text to send
            task_id: Optional task identifier
            file_id: Optional file node ID if message has an attachment

        Note: This can be cancelled via asyncio.Task.cancel() from outside.
        Raises asyncio.CancelledError if cancelled.
        """
        if not self.chat:
            raise ValueError("Chat not initialized")

        # Store file_id temporarily for use by event handlers
        self._current_file_id = file_id

        # Process message through middleware chain
        message_context = await self.message_dispatcher.dispatch(message)

        # Check if middleware wants to skip model and provide direct response
        if message_context.skip_model:
            if message_context.response:
                return message_context.response
            else:
                logger.warning(
                    "Middleware set skip_model=True but provided no response"
                )

        # Use modified message if middleware changed it, otherwise use original
        processed_message = message_context.modified_message or message_context.message

        # Dispatch message sent event WITH ORIGINAL MESSAGE (for storage)
        # The processed_message goes to LLM, but we save the original to keep history clean
        await self.events.async_dispatch(BotEvents.MESSAGE_SENT, message)

        # Estimate tokens for user message and expected response
        if self.message_service and hasattr(self, "token_service"):
            try:
                # Estimate user message tokens
                message_tokens = self.token_service.estimate_user_message(message)
                await self.token_service.emit_estimate(message_tokens, "message")

                # Estimate expected response tokens
                is_complex = self.token_service.detect_complexity(message)
                response_tokens = self.token_service.estimate_expected_response(
                    message, is_complex
                )
                await self.token_service.emit_estimate(
                    response_tokens, "expected_response"
                )

                logger.debug(
                    f"Estimated {message_tokens} tokens for message, "
                    f"{response_tokens} for expected response (complex={is_complex})"
                )
            except Exception as e:
                logger.warning(f"Failed to estimate message tokens: {e}")

        executed_tool_calls = []

        try:
            response = await self.provider.send_message(processed_message)
        except Exception as e:
            # Handle provider-specific initial errors
            logger.error(f"Initial message resulted in error: {e}", exc_info=True)

            # Log to knowledge graph if available
            if self.knowledge:
                try:
                    error_node_id = f"error:{task_id}:initial_error:{datetime.datetime.utcnow().timestamp()}"
                    await self.knowledge.repository.add_node(
                        node_id=error_node_id,
                        node_type="Error",
                        label="Initial Message Error",
                        properties={
                            "task_id": task_id,
                            "error_type": type(e).__name__,
                            "message": str(e),
                            "original_message": processed_message[:500],
                            "timestamp": datetime.datetime.utcnow().isoformat(),
                        },
                    )
                except Exception as log_exc:
                    logger.warning(f"Failed to log error to knowledge graph: {log_exc}")

            # Try to recover
            logger.info("Attempting recovery by asking for a simpler response")
            try:
                recovery_message = (
                    "I encountered an error with that request. Please provide a text response "
                    "explaining what you would do, without attempting to call any functions yet. "
                    "Just describe your approach."
                )
                response = await self.provider.send_message(recovery_message)
            except Exception as recovery_error:
                logger.error(
                    f"Recovery attempt failed: {recovery_error}", exc_info=True
                )
                return (
                    f"I encountered an error and was unable to recover. "
                    f"Error details: {str(e)}"
                )

        if self.toolchain:
            response = await self.provider.handle_tool_calls(
                response=response,
                execute_tool_callback=self.execute_tool_call,
                events=self.events,
                safe_to_original=self._safe_to_original or {},
                task_id=task_id,
                executed_tool_calls=executed_tool_calls,
                knowledge=self.knowledge,
            )

        text = self.provider.extract_text(response)

        # Dispatch message received event
        await self.events.async_dispatch(BotEvents.MESSAGE_RECEIVED, text)

        # Extract and dispatch token usage if available
        # Token service will handle this automatically if configured
        if hasattr(self, "token_service"):
            token_usage = self.token_service.extract_actual_usage(response)
            if token_usage:
                await self.token_service.emit_usage(token_usage)
        else:
            # Fallback for backward compatibility
            token_usage = self.provider.extract_token_usage(response)
            if token_usage:
                await self.events.async_dispatch(BotEvents.TOKEN_USAGE, token_usage)

        # Let Knowledge module handle turn completion
        if self.knowledge:
            try:
                await self.knowledge.handle_turn_complete(
                    user_message=message,
                    assistant_message=text,
                    tool_calls=executed_tool_calls,
                )
            except Exception as e:
                logger.error("Knowledge processing failed: %s", e)
                logger.error(traceback.format_exc())

        # Clear file_id after processing
        self._current_file_id = None

        return text

    async def generate(self, prompt: str) -> str:
        """Generate a one-off response without chat history."""
        return await self.provider.generate_content(prompt)

    async def _format_history_for_summary(self) -> str:
        """Create a concise text dump of recent conversation for summarization.

        Only summarizes messages since the last summary to avoid re-summarizing
        already summarized content and to stay within token limits.
        """
        # Delegate to message service if available
        if self.message_service and self._chat_id:
            return await self.message_service.format_for_summary(
                chat_id=self._chat_id, since_last_summary=True
            )

        # Fallback to direct implementation
        if self.knowledge and self.knowledge.repository and self._chat_id:
            try:
                nodes = await self.knowledge.repository.get_chat_messages(
                    chat_id=self._chat_id
                )

                # Find the most recent summary to avoid re-summarizing old content
                most_recent_summary_idx = -1
                for i in range(len(nodes) - 1, -1, -1):
                    node = nodes[i]
                    if (
                        node.properties
                        and node.properties.get("message_type") == "summary"
                    ):
                        most_recent_summary_idx = i
                        break

                # Only format messages after the last summary
                if most_recent_summary_idx >= 0:
                    # Skip the summary itself, only get messages after it
                    nodes = nodes[most_recent_summary_idx + 1 :]
                    logger.info(
                        f"Formatting {len(nodes)} messages for summary "
                        f"(since last summary at index {most_recent_summary_idx})"
                    )

                if nodes:
                    return format_nodes_for_summary(nodes)
            except Exception as e:
                logger.warning(f"Failed to format history from graph: {e}")

        # Fallback to SDK chat history if available
        if (
            self.chat
            and hasattr(self.chat, "history")
            and self.chat.history is not None
        ):
            # For SDK history, we need a different formatter since it's not Node objects
            # Just create a simple text dump
            lines = []
            try:
                for item in self.chat.history:
                    role = getattr(
                        getattr(item, "role", None), "name", None
                    ) or getattr(item, "role", "")
                    parts = getattr(item, "parts", [])
                    texts = []
                    for p in parts:
                        txt = getattr(p, "text", None)
                        if txt:
                            texts.append(txt)
                    if texts:
                        lines.append(f"{role}: {' '.join(texts)}")
                return "\n".join(lines[-400:])
            except Exception as e:
                logger.warning(f"Failed to format SDK history: {e}")

        return ""

    async def _summarize_conversation(self) -> None:
        """Summarize the conversation to reduce token usage.

        Summarizes messages since the last summary and saves the result to the
        knowledge graph. The summary will be automatically included when loading
        messages for future chat sessions.

        Returns:
            None
        """
        try:
            logger.info("Summarizing conversation...")
            history_text = await self._format_history_for_summary()
            prompt = (
                "Summarize the key points of this conversation. Focus on tasks, decisions, and outcomes. Be concise.\n\n"
                + history_text
            )
            summary = await self.generate(prompt)

            if not (summary or "").strip():
                logger.warning("Empty summary generated; using fallback text")
                summary = "No conversation content to summarize yet."

            # Fire summarized event to save summary to knowledge graph
            await self.events.async_dispatch(BotEvents.SUMMARIZED, summary)

            logger.info("Conversation summarized successfully")
        # pylint: disable=broad-except
        except Exception as e:
            # pylint: enable=broad-except
            logger.warning("Failed to summarize conversation: %s", e)


def main():
    """Example usage of the AgentOrchestrator class."""
    try:
        # Create provider
        config = ProviderConfig(model_name="gemini-1.5-pro")
        provider = GeminiProvider(config)
        orchestrator = AgentOrchestrator(provider=provider)
        logger.info("Sparky initialized! Type 'quit' to exit.\n")
        run_async(orchestrator.start_chat())

        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ["quit", "exit", "q"]:
                logger.info("Goodbye!")
                break
            if not user_input:
                continue

            try:
                response = run_async(
                    orchestrator.send_message(user_input, "default_task_id")
                )
                logger.info("Bot: %s\n", response)
            except KeyboardInterrupt:
                logger.info(
                    "\nOperation cancelled by user. You can enter a new prompt."
                )
                continue

    except ValueError as e:
        logger.error("Error: %s", e)
        logger.info("\nPlease create a .env file with your API key")
    except Exception as e:
        logger.error("An error occurred: %s", e)


if __name__ == "__main__":
    main()
