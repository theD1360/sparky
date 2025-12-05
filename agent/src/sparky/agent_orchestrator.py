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
    ChatService,
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
        # Required services (must be injected via dependency injection)
        message_service: MessageService,
        user_service: UserService,
        identity_service: IdentityService,
        file_service: FileService,
        chat_service: ChatService,
        token_service: Any,
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
            message_service: MessageService instance (required)
            user_service: UserService instance (required)
            identity_service: IdentityService instance (required)
            file_service: FileService instance (required)
            chat_service: ChatService instance (required)
            token_service: TokenUsageService instance (required)
        """
        self._session_id = None  # Will be set in start_chat
        self._chat_id = None  # Will be set in start_chat if provided
        self._event_handlers_registered = (
            False  # Track if event handlers are registered
        )
        self._current_file_id = (
            None  # Temporary storage for file_id during message processing
        )
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

        # Services injected via constructor (required)
        self.message_service = message_service
        self.user_service = user_service
        self.identity_service = identity_service
        self.file_service = file_service
        self.chat_service = chat_service
        self.token_service = token_service

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

        # Register event handlers for storing messages to the knowledge graph
        # These handlers will save and link messages when events are dispatched
        # Note: _chat_id will be set later in start_chat(), handlers check for it
        self._register_event_handlers()

    def add_task(self, instruction: str, metadata: dict | None = None):
        # Implement rate limiting
        if (
            self._last_add_task_time is not None
            and (time.time() - self._last_add_task_time) < 30
        ):
            logger.warning("Rate limiting add_task calls.")
            return

        self._last_add_task_time = time.time()

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

        # Subscribe async handlers directly - async_dispatch will detect and await them
        self.events.subscribe(BotEvents.MESSAGE_SENT, self._handle_message_sent)
        self.events.subscribe(BotEvents.MESSAGE_RECEIVED, self._handle_message_received)
        self.events.subscribe(BotEvents.TOOL_USE, self._handle_tool_use)
        self.events.subscribe(BotEvents.TOOL_RESULT, self._handle_tool_result)
        self.events.subscribe(BotEvents.THOUGHT, self._handle_thought)
        self.events.subscribe(BotEvents.SUMMARIZED, self._handle_summarized)

        self._event_handlers_registered = True
        logger.info(
            f"Registered event handlers for graph message storage. "
            f"Chat ID will be set in start_chat(). Events subscribed: "
            f"MESSAGE_SENT={BotEvents.MESSAGE_SENT}, "
            f"MESSAGE_RECEIVED={BotEvents.MESSAGE_RECEIVED}"
        )

    async def _handle_message_sent(self, message: str):
        """Handle MESSAGE_SENT event by saving and linking message."""
        try:
            logger.info(
                f"Event handler: MESSAGE_SENT for chat {self._chat_id}, message: {message[:50]}..."
            )
            await self._save_and_link_message(
                content=message,
                role="user",
                message_type="message",
                file_node_id=getattr(self, "_current_file_id", None),
            )
            logger.info(
                f"Successfully saved and linked user message for chat {self._chat_id}"
            )
        except Exception as e:
            logger.error(
                f"Error in _handle_message_sent for chat {self._chat_id}: {e}",
                exc_info=True,
            )

    async def _handle_message_received(self, message: str):
        """Handle MESSAGE_RECEIVED event by saving and linking message."""
        try:
            logger.info(
                f"Event handler: MESSAGE_RECEIVED for chat {self._chat_id}, message: {message[:50]}..."
            )
            await self._save_and_link_message(
                content=message,
                role="model",
                message_type="message",
            )
            logger.info(
                f"Successfully saved and linked model message for chat {self._chat_id}"
            )
        except Exception as e:
            logger.error(
                f"Error in _handle_message_received for chat {self._chat_id}: {e}",
                exc_info=True,
            )

    async def _handle_tool_use(self, tool_name: str, args: dict):
        """Handle TOOL_USE event by saving and linking message."""
        await self._save_and_link_message(
            content=f"Using tool: {tool_name} with args: {args}",
            role="model",
            message_type="tool_use",
            tool_name=tool_name,
            tool_args=args,
        )

    async def _handle_tool_result(
        self, tool_name: str, result: Any, status: str = None
    ):
        """Handle TOOL_RESULT event by saving and linking message."""
        await self._save_and_link_message(
            content=f"Tool {tool_name} result: {result}",
            role="model",
            message_type="tool_result",
            tool_name=tool_name,
        )

    async def _handle_thought(self, thought: str):
        """Handle THOUGHT event by saving and linking message."""
        await self._save_and_link_message(
            content=thought,
            role="model",
            message_type="thought",
        )

    async def _handle_summarized(self, summary: str, turn_count: int = None):
        """Handle SUMMARIZED event by saving and linking message.

        Args:
            summary: The conversation summary
            turn_count: Optional turn count (not used but kept for compatibility)
        """
        await self._save_and_link_message(
            content=summary,
            role="user",
            internal=True,
            message_type="summary",
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
        if not self._chat_id:
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
        return await self.file_service.upload_file(
            file_content=file_content,
            filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            user_id=user_id,
            session_id=self._session_id,
            ai_description_callback=ai_description_callback,
        )

    async def _save_and_link_message(
        self,
        content: str,
        role: str,
        internal: bool = False,
        message_type: str = "message",
        tool_name: Optional[str] = None,
        tool_args: Optional[dict] = None,
        file_node_id: Optional[str] = None,
    ) -> None:
        """Save a message and link it to the current chat.

        This ensures the order: create message, then link to chat.

        Args:
            content: The message content
            role: The role of the speaker (e.g., 'user', 'model')
            internal: Whether this is an internal/system message
            message_type: The type of message
            tool_name: Optional tool name for tool_use and tool_result messages
            tool_args: Optional tool arguments for tool_use messages
            file_node_id: Optional file node ID for attachments
        """
        logger.info(
            f"_save_and_link_message called: role={role}, chat_id={self._chat_id}, "
            f"internal={internal}, message_type={message_type}"
        )
        # Step 1: Create message (agnostic of chat)
        message_node_id = await self.message_service.save_message(
            content=content,
            role=role,
            internal=internal,
            message_type=message_type,
            tool_name=tool_name,
            tool_args=tool_args,
            file_node_id=file_node_id,
        )

        # Step 2: Link message to chat if chat_id is available
        if message_node_id and self._chat_id:
            try:
                linked = await self.chat_service.link_message(
                    chat_id=self._chat_id,
                    message_node_id=message_node_id,
                )
                if not linked:
                    logger.warning(
                        f"Failed to link message {message_node_id} to chat {self._chat_id}"
                    )
            except Exception as e:
                logger.error(
                    f"Error linking message {message_node_id} to chat {self._chat_id}: {e}",
                    exc_info=True,
                )
        elif message_node_id and not self._chat_id:
            logger.warning(
                f"Message {message_node_id} created but no chat_id available to link it"
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
        to _save_and_link_message.

        Args:
            message: The message content
            role: The role of the speaker (e.g., 'user', 'model')
            internal: Whether this is an internal/system message that shouldn't be displayed to users
            message_type: The type of message (e.g., 'message', 'tool_use', 'tool_result', 'thought', 'summary', 'internal')
            tool_name: Optional tool name for tool_use and tool_result messages
            tool_args: Optional tool arguments for tool_use messages
            file_node_id: Optional file node ID for attachments
        """
        await self._save_and_link_message(
            content=message,
            role=role,
            internal=internal,
            message_type=message_type,
            tool_name=tool_name,
            tool_args=tool_args,
            file_node_id=file_node_id,
        )

    async def start_chat(
        self,
        history: Optional[list] = None,
        user_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        chat_name: Optional[str] = None,
    ):
        """Asynchronously initializes the chat.


        Args:
            history: Optional initial chat history
            user_id: User identifier for this chat. If None, uses 'default'.
            chat_id: Optional chat identifier. If provided, creates a Chat node.
            chat_name: Optional chat name. Used when creating a Chat node.
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
            self.knowledge._mem_summary_key = f"chat:{self._session_id}:summary"
            # Reset turn index for new session
            self.knowledge._turn_index = 0
            # Clear associated memories tracking for new session
            self.knowledge._associated_memories = set()

        # Verify user exists and get user node
        try:

            user_node = await self.user_service.get_user(user_id)
            if not user_node:
                raise ValueError(
                    f"User {user_id} not found in knowledge graph. "
                    "User should be created during registration."
                )

            logger.debug(f"Retrieved user node for user {user_id}")

            # Get or create Chat node if chat_id is provided
            if chat_id:
                # Use chat_service to get or create the chat
                display_name = chat_name or f"Chat {chat_id[:8]}"
                chat_node = await self.chat_service.get_or_create_chat(
                    chat_id=chat_id,
                    chat_name=display_name,
                    user_id=user_id,
                )

                if chat_node:
                    logger.info(
                        f"Got or created Chat node {chat_id} for user {user_id}"
                    )
                    # Ensure the chat is linked to the user
                    # (link_chat handles checking if edge already exists)
                    link_success = await self.chat_service.link_chat(
                        chat_id=chat_id, user_id=user_id
                    )
                    if not link_success:
                        logger.warning(
                            f"Failed to link chat {chat_id} to user {user_id}"
                        )

                else:
                    logger.warning(f"Failed to get or create chat node {chat_id}")

        except Exception as e:
            logger.error(
                f"Failed to create session/user/chat nodes or edges: {e}",
                exc_info=True,
            )

        # Provide model to knowledge module
        if self.knowledge:
            self.knowledge.model = self.model

        history = history or []

        # Load identity using services
        identity_memory = None
        identity_summary = None

        # Use IdentityService for loading identity
        try:
            identity_memory = await self.identity_service.get_identity_memory()
            logger.info(f"Identity loaded successfully: {len(identity_memory)} chars")
        except Exception as e:
            logger.error(f"Failed to load identity: {e}", exc_info=True)
            identity_memory = "## Identity Loading Failed\n\nCannot load identity."

        # Summarize the identity to reduce token usage using IdentityService
        if identity_memory and not identity_memory.startswith(
            "## Identity Loading Failed"
        ):

            try:
                identity_summary = await self.identity_service.summarize_identity(
                    identity_memory, self.generate
                )
                logger.info(f"Identity summarized: {len(identity_summary)} chars")
            except Exception as e:
                logger.error(f"Failed to summarize identity: {e}", exc_info=True)
                # Fallback to direct summarization
                identity_summary_prompt = f"Summarize the following identity document into a concise paragraph, retaining the core concepts, purpose, and values:\n\n{identity_memory}"
                identity_summary = await self.generate(identity_summary_prompt)

        # Format identity instruction
        if identity_summary and not identity_summary.startswith("Identity unavailable"):

            identity_instruction = self.identity_service.format_identity_instruction(
                identity_summary
            )

            logger.info(
                f"Adding identity instruction to chat: {len(identity_instruction)} chars"
            )
        else:
            logger.warning(
                "No identity summary available, skipping identity instruction"
            )
            identity_instruction = None

        if not self.initial_context_added:
            if identity_instruction:
                await self._add_message_with_chat_node(
                    identity_instruction, "user", internal=True, message_type="internal"
                )
                logger.info("Identity instruction added to chat")
            else:
                logger.warning("Skipping identity instruction - no identity available")
            await self._add_message_with_chat_node(
                "I understand my identity and purpose. I'm ready to help you.",
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
        # Identity messages are already in the graph and will be included here
        truncated_history = await self._get_recent_messages()

        # Estimate tokens for initial history and dispatch estimate event
        if truncated_history:
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
        logger.info(
            f"Dispatching MESSAGE_SENT event for chat {self._chat_id}, "
            f"message: {message[:50]}..., handlers registered: {self._event_handlers_registered}"
        )
        await self.events.async_dispatch(BotEvents.MESSAGE_SENT, message)

        # Estimate tokens for user message and expected response
        try:
            # Estimate user message tokens
            message_tokens = self.token_service.estimate_user_message(message)
            await self.token_service.emit_estimate(message_tokens, "message")

            # Estimate expected response tokens
            is_complex = self.token_service.detect_complexity(message)
            response_tokens = self.token_service.estimate_expected_response(
                message, is_complex
            )
            await self.token_service.emit_estimate(response_tokens, "expected_response")

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

            # Log to knowledge graph
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
        logger.info(
            f"Dispatching MESSAGE_RECEIVED event for chat {self._chat_id}, "
            f"response: {text[:50]}..., handlers registered: {self._event_handlers_registered}"
        )
        await self.events.async_dispatch(BotEvents.MESSAGE_RECEIVED, text)

        # Extract and dispatch token usage
        token_usage = self.token_service.extract_actual_usage(response)
        if token_usage:
            await self.token_service.emit_usage(token_usage)

        # Let Knowledge module handle turn completion
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
        if not self._chat_id:
            return ""

        return await self.message_service.format_for_summary(
            chat_id=self._chat_id, since_last_summary=True
        )

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

        # Create services (required for dependency injection)
        from database.database import get_database_manager
        from database.repository import KnowledgeRepository
        from services import create_services
        from utils.events import Events

        db_manager = get_database_manager()
        db_manager.connect()
        repository = KnowledgeRepository(db_manager)

        events = Events()
        services = create_services(
            repository=repository,
            identity_search_terms=None,
            events=events,
            provider=provider,
        )

        orchestrator = AgentOrchestrator(
            provider=provider,
            message_service=services["message_service"],
            user_service=services["user_service"],
            identity_service=services["identity_service"],
            file_service=services["file_service"],
            chat_service=services["chat_service"],
            token_service=services["token_service"],
        )
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
