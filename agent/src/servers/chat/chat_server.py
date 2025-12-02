import asyncio
import json
import os
import signal
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from logging import getLogger
from typing import Any, Dict, Optional, Tuple

import aiofiles
from badmcp.tool_chain import ToolChain

# Import the necessary components for the agent orchestrator
from database.database import get_database_manager
from database.repository import KnowledgeRepository
from dotenv import load_dotenv
from fastapi import FastAPI, File, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from models import (
    ChatMessagePayload,
    ChatReadyPayload,
    ConnectPayload,
    ErrorPayload,
    MessageType,
    ReadyPayload,
    StartChatPayload,
    StatusPayload,
    SwitchChatPayload,
    ThoughtPayload,
    TokenUsagePayload,
    ToolLoadingProgressPayload,
    ToolResultPayload,
    ToolUsePayload,
    WSMessage,
)
from pydantic import BaseModel

# Import routers
from servers.chat.routes import (
    admin_router,
    auth_router,
    chats_router,
    health_router,
    prompts_router,
    resources_router,
    user_management_router,
    user_router,
)
from services import KnowledgeService
from sparky import AgentOrchestrator
from sparky.constants import SPARKY_CHAT_PID_FILE
from sparky.logging_config import setup_logging
from sparky.middleware import (
    CommandPromptMiddleware,
    FileAttachmentMiddleware,
    ResourceFetchingMiddleware,
    SelfModificationGuard,
)
from sparky.providers import GeminiProvider, ProviderConfig
from sparky.toolchain_cache import get_toolchain_cache


class ToolUsageData(BaseModel):
    user_id: str
    chat_id: Optional[str] = None
    tool_name: str
    tool_args: dict
    result: Optional[str] = None


# --- Application Setup ---
load_dotenv()
setup_logging()

# Shared resources loaded once at server startup
_app_toolchain: ToolChain | None = None
_app_knowledge: KnowledgeService | None = None
_startup_error: str | None = None
_connection_manager: "ConnectionManager | None" = None
_agent_loop_instance = None
_agent_loop_task = None

logger = getLogger(__name__)


class ConnectionManager:
    """Manages agent orchestrator instances and websocket connections per user."""

    def __init__(
        self, session_timeout_minutes: int = 60, toolchain: Optional[ToolChain] = None
    ):
        """Initialize the connection manager.

        Args:
            session_timeout_minutes: Timeout for inactive connections in minutes
            toolchain: Optional toolchain for tool loading
        """
        # user_id -> chat_id -> agent orchestrator instance
        self.bot_sessions: Dict[str, Dict[str, AgentOrchestrator]] = {}
        # user_id -> chat_id -> Knowledge instance (isolated per chat)
        self.knowledge_instances: Dict[str, Dict[str, KnowledgeService]] = {}
        # user_id -> current active chat_id
        self.current_chat: Dict[str, str] = {}
        # user_id -> last activity timestamp
        self.last_activity: Dict[str, datetime] = {}
        # user_id -> current websocket (if connected)
        self.active_connections: Dict[str, WebSocket] = {}
        # user_id -> tools initialized flag
        self.tools_initialized: Dict[str, bool] = {}
        # user_id -> (identity_memory, identity_summary) cached at user level
        self.user_identity_cache: Dict[str, Tuple[str, str]] = {}
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.toolchain = toolchain

    async def initialize_tools_for_user(
        self, user_id: str, websocket: WebSocket
    ) -> Tuple[Optional[ToolChain], Optional[str]]:
        """Initialize tools for a user and send progress updates via WebSocket.

        This uses the global toolchain cache to lazily load MCP servers on first connection.
        Subsequent connections will use cached toolchain if still valid.

        Args:
            user_id: User identifier
            websocket: WebSocket connection for sending progress updates

        Returns:
            Tuple of (toolchain, error_message)
        """
        if self.tools_initialized.get(user_id, False) and self.toolchain:
            logger.info(
                f"[{user_id}] Tools already initialized for user, using cached toolchain"
            )
            return self.toolchain, None

        logger.info(f"[{user_id}] Initializing tools for first time...")

        # Get toolchain cache
        cache = get_toolchain_cache()

        # Define progress callback to send updates to client
        async def progress_callback(server_name: str, status: str, message: str):
            """Send tool loading progress to WebSocket client."""
            try:
                await websocket.send_text(
                    WSMessage(
                        type=MessageType.tool_loading_progress,
                        data=ToolLoadingProgressPayload(
                            tool_name=server_name,
                            status=status,
                            message=message,
                        ),
                    ).to_text()
                )
                # Small delay for visual feedback
                if status == "loading":
                    await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"[{user_id}] Error sending progress update: {e}")

        try:
            # Load or get cached toolchain
            toolchain, error = await cache.get_or_load_toolchain(progress_callback)

            if error:
                logger.error(f"[{user_id}] Failed to load toolchain: {error}")
                return None, error

            if toolchain:
                # Update connection manager's toolchain reference
                self.toolchain = toolchain
                self.tools_initialized[user_id] = True

                tools_count = len(toolchain.tool_clients) if toolchain else 0
                logger.info(
                    f"[{user_id}] Tools initialized successfully: {tools_count} tool server(s)"
                )

                # Log cache status
                cache_status = cache.get_cache_status()
                logger.debug(f"[{user_id}] Tool cache status: {cache_status}")

                # Start agent loop on first toolchain initialization if enabled
                await self._maybe_start_agent_loop(toolchain)

                return toolchain, None
            else:
                error_msg = "Toolchain loaded but is None"
                logger.error(f"[{user_id}] {error_msg}")
                return None, error_msg

        except Exception as e:
            error_msg = f"Error initializing tools: {e}"
            logger.error(f"[{user_id}] {error_msg}")
            logger.error(f"[{user_id}] Traceback: {traceback.format_exc()}")
            return None, error_msg

    async def _maybe_start_agent_loop(self, toolchain: ToolChain):
        """Start agent loop if enabled and not already running.

        Args:
            toolchain: Initialized toolchain to use
        """
        global _agent_loop_instance, _agent_loop_task

        # Check if already running
        if _agent_loop_instance is not None:
            logger.info("Agent loop already running, skipping startup")
            return

        # Check if enabled
        enable_agent_loop = (
            os.getenv("SPARKY_ENABLE_AGENT_LOOP", "false").lower() == "true"
        )
        if not enable_agent_loop:
            logger.debug("Agent loop not enabled (SPARKY_ENABLE_AGENT_LOOP=false)")
            return

        try:
            logger.info("Starting agent loop after toolchain initialization...")
            from servers.task import AgentLoop

            poll_interval = int(os.getenv("SPARKY_AGENT_POLL_INTERVAL", "10"))
            _agent_loop_instance = AgentLoop(
                toolchain=toolchain,
                poll_interval=poll_interval,
                enable_scheduled_tasks=True,
                connection_manager=self,
            )
            _agent_loop_task = _agent_loop_instance.start_background()
            logger.info(
                f"Agent loop started in background (poll interval: {poll_interval}s)"
            )
        except Exception as e:
            logger.error(f"Failed to start agent loop: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    async def load_and_cache_identity(
        self,
        user_id: str,
        knowledge: KnowledgeService,
        generate_fn: Any,
    ) -> Tuple[str, str]:
        """Load identity and cache it at user level.

        Args:
            user_id: User identifier
            knowledge: Knowledge instance to load identity from
            generate_fn: LLM generate function for identity summarization

        Returns:
            Tuple of (identity_memory, identity_summary)
        """
        # Check if identity is already cached for this user
        if user_id in self.user_identity_cache:
            logger.info(f"[{user_id}] Using cached identity from user")
            return self.user_identity_cache[user_id]

        logger.info(f"[{user_id}] Loading identity for user (first time)")

        # Load identity using the identity service
        from services import IdentityService

        identity_service = IdentityService(
            repository=knowledge.repository if knowledge else None,
        )

        # Load identity
        try:
            identity_memory = await identity_service.get_identity_memory()
        except Exception as e:
            logger.error(f"Failed to load identity: {e}")
            identity_memory = "## Identity Loading Failed\n\nCannot load identity."

        # Summarize identity
        try:
            identity_summary = await identity_service.summarize_identity(
                identity_memory, generate_fn
            )
        except Exception as e:
            logger.error(f"Failed to summarize identity: {e}")
            identity_summary_prompt = f"Summarize the following identity document into a concise paragraph, retaining the core concepts, purpose, and values:\n\n{identity_memory}"
            identity_summary = await generate_fn(identity_summary_prompt)

        # Cache for this user
        self.user_identity_cache[user_id] = (identity_memory, identity_summary)
        logger.info(f"[{user_id}] Identity loaded and cached for user")

        return identity_memory, identity_summary

    async def create_bot_for_chat(
        self,
        user_id: str,
        chat_id: str,
        chat_name: Optional[str] = None,
    ) -> AgentOrchestrator:
        """Create or retrieve agent orchestrator for a specific chat.

        Args:
            user_id: User identifier
            chat_id: Chat identifier
            chat_name: Optional display name for the chat

        Returns:
            AgentOrchestrator instance for the chat
        """
        # Check if bot already exists for this chat
        if user_id in self.bot_sessions and chat_id in self.bot_sessions[user_id]:
            bot = self.bot_sessions[user_id][chat_id]
            logger.info(f"[{user_id}:{chat_id}] Reusing existing bot instance")
            return bot

        # Create new bot instance for this chat
        logger.info(f"[{user_id}:{chat_id}] Creating new bot instance")

        # Ensure user exists in our data structures
        if user_id not in self.bot_sessions:
            self.bot_sessions[user_id] = {}
            self.knowledge_instances[user_id] = {}

        # Create isolated Knowledge instance for this chat
        logger.info(f"[{user_id}:{chat_id}] Creating isolated Knowledge instance")

        # Create repository first
        db_url = os.getenv("SPARKY_DB_URL")
        if not db_url:
            logger.warning(
                f"[{user_id}:{chat_id}] SPARKY_DB_URL not set, KnowledgeService will not be initialized"
            )
            knowledge = None
        else:
            try:
                db_manager = get_database_manager(db_url=db_url)
                db_manager.connect()
                repository = KnowledgeRepository(db_manager)

                # Use chat_id as the session identifier for Knowledge (each chat has its own memory context)
                knowledge = KnowledgeService(
                    repository=repository,
                    session_id=chat_id,
                    model=None,
                )
                logger.info(
                    f"[{user_id}:{chat_id}] Initialized KnowledgeService with repository"
                )
            except Exception as e:
                logger.error(
                    f"[{user_id}:{chat_id}] Failed to initialize KnowledgeService: {e}",
                    exc_info=True,
                )
                knowledge = None

        self.knowledge_instances[user_id][chat_id] = knowledge

        # Create bot with user-specific callbacks
        logger.info(f"[{user_id}:{chat_id}] Creating bot instance with callbacks")

        async def send_tool_use_notification(tool_name, tool_args):
            ws = self.active_connections.get(user_id)
            if ws:
                try:
                    # Ensure args are JSON-serializable (best effort)
                    def _to_plain(x):
                        if isinstance(x, (str, int, float, bool)) or x is None:
                            return x
                        if isinstance(x, dict) or hasattr(x, "items"):
                            try:
                                items = x.items() if hasattr(x, "items") else x
                                return {str(k): _to_plain(v) for k, v in items}
                            except Exception:
                                return {
                                    str(k): _to_plain(v) for k, v in dict(x).items()
                                }
                        if isinstance(x, (list, tuple, set)) or (
                            hasattr(x, "__iter__")
                            and not isinstance(x, (str, bytes, bytearray))
                        ):
                            try:
                                return [_to_plain(v) for v in list(x)]
                            except Exception:
                                return [_to_plain(v) for v in x]
                        try:
                            return json.loads(json.dumps(x))
                        except Exception:
                            return str(x)

                    payload = ToolUsePayload(
                        name=str(tool_name), args=_to_plain(tool_args)
                    )
                    msg = WSMessage(
                        type=MessageType.tool_use,
                        data=payload,
                        user_id=user_id,
                        chat_id=chat_id,
                    )
                    await ws.send_text(msg.to_text())
                except Exception:
                    # Fallback to a simple status message if anything goes wrong
                    fallback = WSMessage(
                        type=MessageType.status,
                        data=StatusPayload(message=f"Using tool {tool_name}"),
                        user_id=user_id,
                        chat_id=chat_id,
                    )
                    await ws.send_text(fallback.to_text())

        async def send_tool_result_notification(tool_name, result_text, status=None):
            ws = self.active_connections.get(user_id)
            if ws:
                try:
                    # Ensure result is a string
                    if not isinstance(result_text, str):
                        result_text = "" if result_text is None else str(result_text)

                    # Parse structured data from result
                    result_content = None
                    messages = None
                    try:
                        # Try to parse as JSON to extract structured data
                        parsed_result = json.loads(result_text) if result_text else None
                        if isinstance(parsed_result, dict):
                            result_content = (
                                parsed_result.get("result")
                                or parsed_result.get("content")
                                or parsed_result
                            )
                            messages = parsed_result.get(
                                "messages"
                            ) or parsed_result.get("message")
                            if messages and not isinstance(messages, list):
                                messages = [messages]
                    except (json.JSONDecodeError, TypeError):
                        # Not JSON, use as-is
                        pass

                    payload = ToolResultPayload(
                        name=str(tool_name),
                        result=result_text,
                        status=status,
                        result_content=result_content,
                        messages=messages,
                    )
                    msg = WSMessage(
                        type=MessageType.tool_result,
                        data=payload,
                        user_id=user_id,
                        chat_id=chat_id,
                    )
                    await ws.send_text(msg.to_text())
                except Exception:
                    # Fallback to status message
                    fallback = WSMessage(
                        type=MessageType.status,
                        data=StatusPayload(message=f"Tool {tool_name} finished."),
                        user_id=user_id,
                        chat_id=chat_id,
                    )
                    await ws.send_text(fallback.to_text())

        async def send_thought_notification(thought_text):
            ws = self.active_connections.get(user_id)
            if ws:
                try:
                    # Ensure thought is a string
                    if not isinstance(thought_text, str):
                        thought_text = "" if thought_text is None else str(thought_text)
                    payload = ThoughtPayload(text=thought_text)
                    msg = WSMessage(
                        type=MessageType.thought,
                        data=payload,
                        user_id=user_id,
                        chat_id=chat_id,
                    )
                    await ws.send_text(msg.to_text())
                except Exception:
                    # Fallback to status message
                    fallback = WSMessage(
                        type=MessageType.status,
                        data=StatusPayload(message="Thinking..."),
                        user_id=user_id,
                        chat_id=chat_id,
                    )
                    await ws.send_text(fallback.to_text())

        async def send_token_usage_notification(usage_dict):
            ws = self.active_connections.get(user_id)
            if ws:
                try:
                    # Validate and extract token counts from the usage dict
                    input_tokens = usage_dict.get("input_tokens", 0)
                    output_tokens = usage_dict.get("output_tokens", 0)
                    total_tokens = usage_dict.get(
                        "total_tokens", input_tokens + output_tokens
                    )
                    cached_tokens = usage_dict.get("cached_tokens")

                    payload = TokenUsagePayload(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        cached_tokens=cached_tokens,
                    )
                    msg = WSMessage(
                        type=MessageType.token_usage,
                        data=payload,
                        user_id=user_id,
                        chat_id=chat_id,
                    )
                    await ws.send_text(msg.to_text())
                except Exception as e:
                    logger.warning(f"Failed to send token usage: {e}")

        async def send_token_estimate_notification(estimated_tokens, source):
            ws = self.active_connections.get(user_id)
            if ws:
                try:
                    from models import TokenEstimatePayload

                    payload = TokenEstimatePayload(
                        estimated_tokens=estimated_tokens,
                        source=source,
                    )
                    msg = WSMessage(
                        type=MessageType.token_estimate,
                        data=payload,
                        user_id=user_id,
                        chat_id=chat_id,
                    )
                    await ws.send_text(msg.to_text())
                except Exception as e:
                    logger.warning(f"Failed to send token estimate: {e}")

        # Create LLM provider
        model_name = os.getenv("AGENT_MODEL", "gemini-2.0-flash")
        config = ProviderConfig(model_name=model_name)
        provider = GeminiProvider(config)

        bot = AgentOrchestrator(
            provider=provider,
            middlewares=[
                SelfModificationGuard(),
                FileAttachmentMiddleware(),
                ResourceFetchingMiddleware(),
                CommandPromptMiddleware(),
            ],
            toolchain=self.toolchain,
            knowledge=knowledge,
        )

        # Subscribe to all bot events using consistent event subscription pattern
        from events import BotEvents

        # WebSocket notifications
        bot.events.subscribe(BotEvents.TOOL_USE, send_tool_use_notification)
        bot.events.subscribe(BotEvents.TOOL_RESULT, send_tool_result_notification)
        bot.events.subscribe(BotEvents.THOUGHT, send_thought_notification)
        bot.events.subscribe(BotEvents.TOKEN_USAGE, send_token_usage_notification)
        bot.events.subscribe(BotEvents.TOKEN_ESTIMATE, send_token_estimate_notification)

        # Note: Message persistence is handled automatically by AgentOrchestrator's
        # internal event handlers (_register_event_handlers), so no additional
        # subscriptions are needed here to avoid duplicate saves.

        # Store bot instance for this chat
        self.bot_sessions[user_id][chat_id] = bot

        # Load and cache identity at user level (only loads once per user)
        identity_memory, identity_summary = await self.load_and_cache_identity(
            user_id=user_id,
            knowledge=knowledge,
            generate_fn=bot.generate,
        )

        # Start the chat for this bot with pre-loaded identity
        await bot.start_chat(
            user_id=user_id,
            chat_id=chat_id,
            chat_name=chat_name or f"Chat {chat_id[:8]}",
            preloaded_identity=identity_memory,
            preloaded_identity_summary=identity_summary,
        )

        # Update current chat tracking
        self.current_chat[user_id] = chat_id

        logger.info(f"[{user_id}:{chat_id}] Bot instance created and chat started")
        return bot

    async def switch_chat(self, user_id: str, chat_id: str) -> AgentOrchestrator:
        """Switch to a different chat for a user.

        Args:
            user_id: User identifier
            chat_id: Chat identifier to switch to

        Returns:
            AgentOrchestrator instance for the chat
        """
        logger.info(f"[{user_id}] Switching to chat {chat_id}")

        # Update current chat tracking
        self.current_chat[user_id] = chat_id
        self.last_activity[user_id] = datetime.utcnow()

        # Get or create bot for this chat
        if user_id in self.bot_sessions and chat_id in self.bot_sessions[user_id]:
            bot = self.bot_sessions[user_id][chat_id]
            # Check if chat is initialized - if not, initialize it
            if not bot.chat:
                logger.info(
                    f"[{user_id}:{chat_id}] Bot exists but chat not initialized, initializing..."
                )
                await bot.start_chat(
                    user_id=user_id,
                    chat_id=chat_id,
                    chat_name=None,  # Will use existing chat name
                )
            logger.info(f"[{user_id}:{chat_id}] Reusing existing bot for chat")
            return bot
        else:
            # Create new bot for this chat
            logger.info(f"[{user_id}:{chat_id}] Creating new bot for chat")
            return await self.create_bot_for_chat(user_id, chat_id)

    def connect(self, user_id: str, websocket: WebSocket):
        """Register active websocket connection for a user.

        Args:
            user_id: User identifier
            websocket: WebSocket connection
        """
        self.active_connections[user_id] = websocket
        self.last_activity[user_id] = datetime.utcnow()
        logger.info(f"[{user_id}] WebSocket connected")

    def disconnect(self, user_id: str):
        """Remove websocket connection but keep bot instances.

        Args:
            user_id: User identifier
        """
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            self.last_activity[user_id] = datetime.utcnow()
            logger.info(f"[{user_id}] WebSocket disconnected (bot instances preserved)")

    def get_active_connection_by_user(
        self, user_id: str
    ) -> Optional[Tuple[WebSocket, Optional[str]]]:
        """Get active WebSocket connection for a user.

        Args:
            user_id: User identifier to lookup

        Returns:
            Tuple of (websocket, current_chat_id) if user has active connection, None otherwise
        """
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            current_chat_id = self.current_chat.get(user_id)
            logger.debug(
                f"Found active connection for user {user_id}, chat={current_chat_id}"
            )
            return websocket, current_chat_id
        logger.debug(f"No active connection found for user {user_id}")
        return None

    def cleanup_expired_sessions(self):
        """Remove bot sessions that have been inactive too long."""
        now = datetime.utcnow()
        expired = [
            sid
            for sid, last_active in self.last_activity.items()
            if now - last_active > self.session_timeout
        ]
        for sid in expired:
            logger.info(f"[{sid}] Cleaning up expired session")
            self.bot_sessions.pop(sid, None)
            self.knowledge_instances.pop(sid, None)
            self.current_chat.pop(sid, None)
            self.tools_initialized.pop(sid, None)
            self.last_activity.pop(sid, None)
            self.active_connections.pop(sid, None)
            self.session_to_user.pop(sid, None)

    def get_session_info(self) -> dict:
        """Get info about all sessions (for future admin endpoints).

        Returns:
            Dictionary with session information
        """
        return {
            "total_sessions": len(self.bot_sessions),
            "active_connections": len(self.active_connections),
            "sessions": {
                sid: {
                    "connected": sid in self.active_connections,
                    "last_activity": self.last_activity[sid].isoformat(),
                    "current_chat": self.current_chat.get(sid),
                    "total_chats": len(self.bot_sessions.get(sid, {})),
                    "tools_initialized": self.tools_initialized.get(sid, False),
                }
                for sid in self.bot_sessions.keys()
            },
        }


async def _periodic_cleanup():
    """Periodically clean up expired sessions."""
    global _connection_manager
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        if _connection_manager:
            logger.debug("Running periodic session cleanup")
            _connection_manager.cleanup_expired_sessions()


def _create_pid_file():
    """Create the PID file for the server process."""
    try:
        with open(SPARKY_CHAT_PID_FILE, "w") as f:
            f.write(str(os.getpid()))
        logger.info(f"Created PID file: {SPARKY_CHAT_PID_FILE}")
    except Exception as e:
        logger.error(f"Failed to create PID file: {e}")


def _remove_pid_file():
    """Remove the PID file."""
    try:
        if os.path.exists(SPARKY_CHAT_PID_FILE):
            os.remove(SPARKY_CHAT_PID_FILE)
            logger.info(f"Removed PID file: {SPARKY_CHAT_PID_FILE}")
    except Exception as e:
        logger.error(f"Failed to remove PID file: {e}")


def _setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        _remove_pid_file()
        os._exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


@asynccontextmanager
async def cleanup_server(app: FastAPI):
    """Cleanup the server process when the app is shut down."""
    cleanup_task = None
    try:
        global _app_toolchain, _app_knowledge, _startup_error, _connection_manager
        global _agent_loop_instance, _agent_loop_task

        # Create PID file and setup signal handlers
        _create_pid_file()
        _setup_signal_handlers()

        # Initialize connection manager
        _connection_manager = ConnectionManager(session_timeout_minutes=60)
        logger.info("Connection manager initialized")

        # Check if agent loop is enabled
        enable_agent_loop = (
            os.getenv("SPARKY_ENABLE_AGENT_LOOP", "false").lower() == "true"
        )

        if enable_agent_loop:
            # If agent loop is enabled, load toolchain at startup
            logger.info("Agent loop is enabled - loading toolchain at startup")
            from sparky.toolchain_cache import get_toolchain_cache

            cache = get_toolchain_cache()
            toolchain, error = await cache.get_or_load_toolchain()

            if error:
                logger.error(f"Failed to load toolchain at startup: {error}")
                _startup_error = error
            elif toolchain:
                _connection_manager.toolchain = toolchain
                logger.info(
                    f"Toolchain loaded at startup: {len(toolchain.tool_clients)} tool server(s)"
                )

                # Start agent loop immediately
                try:
                    from servers.task import AgentLoop

                    poll_interval = int(os.getenv("SPARKY_AGENT_POLL_INTERVAL", "10"))
                    _agent_loop_instance = AgentLoop(
                        toolchain=toolchain,
                        poll_interval=poll_interval,
                        enable_scheduled_tasks=True,
                        connection_manager=_connection_manager,
                    )
                    _agent_loop_task = _agent_loop_instance.start_background()
                    logger.info(
                        f"Agent loop started at startup (poll interval: {poll_interval}s)"
                    )
                except Exception as e:
                    logger.error(f"Failed to start agent loop: {e}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
        else:
            logger.info(
                "Agent loop is disabled - toolchain will be loaded on first client connection"
            )
            logger.info("Set SPARKY_ENABLE_AGENT_LOOP=true to enable agent loop")

        # Start periodic cleanup task
        cleanup_task = asyncio.create_task(_periodic_cleanup())
        logger.info("Periodic session cleanup task started")
        logger.info("Server ready")

        yield

        # Cleanup on shutdown
        if _agent_loop_instance:
            logger.info("Stopping agent loop...")
            await _agent_loop_instance.stop()

        if _agent_loop_task:
            _agent_loop_task.cancel()
            try:
                await _agent_loop_task
            except asyncio.CancelledError:
                pass

        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

        # Cleanup toolchain cache
        try:
            logger.info("Cleaning up toolchain cache...")
            cache = get_toolchain_cache()
            await cache.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up toolchain cache: {e}")

        _remove_pid_file()

    except Exception as e:
        logger.error(f"Error cleaning up server: {e}")
        _remove_pid_file()


app = FastAPI(
    title="Sparky Chat Server",
    description="This server manages the bot's logic, history, and tool connections.",
    version="1.0.0",
    lifespan=cleanup_server,
)

# Register routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(resources_router)
app.include_router(prompts_router)
app.include_router(user_router)
app.include_router(chats_router)
app.include_router(admin_router)
app.include_router(user_management_router)


# File analysis function
async def _analyze_file(
    file_path: str, filename: str, content_type: str, file_size: int, content: bytes
) -> str:
    """Analyze file content using AI and return a description."""
    try:
        from sparky.providers import GeminiProvider, ProviderConfig

        # Use lightweight model for analysis
        config = ProviderConfig(model_name="gemini-2.0-flash-exp")
        provider = GeminiProvider(config)
        provider.initialize_model()  # Initialize the model

        file_ext = filename.split(".")[-1].lower() if "." in filename else ""

        # Image analysis
        if content_type and content_type.startswith("image/"):
            try:
                import base64

                # Convert image to base64
                base64_image = base64.b64encode(content).decode("utf-8")

                prompt = """Analyze this image and provide a detailed but concise description. 
Include:
- What the image shows
- Key objects, people, or elements
- Colors, style, or notable features
- Any text visible in the image

Keep it under 100 words."""

                # Use Gemini's vision capabilities
                response = await provider.generate_content_with_image(
                    prompt, base64_image, content_type
                )
                return response.strip()
            except Exception as e:
                logger.error(f"Error analyzing image: {e}")
                return f"Image file ({content_type})"

        # Text/code file analysis
        text_extensions = {
            "txt",
            "md",
            "json",
            "xml",
            "html",
            "css",
            "js",
            "ts",
            "py",
            "java",
            "c",
            "cpp",
            "h",
            "hpp",
            "go",
            "rs",
            "rb",
            "php",
            "yaml",
            "yml",
            "toml",
            "ini",
            "cfg",
            "conf",
            "sh",
            "bash",
            "sql",
            "csv",
        }

        if file_ext in text_extensions and file_size < 100000:  # Under 100KB
            try:
                text_content = content.decode("utf-8")

                prompt = f"""Analyze this {file_ext} file and provide a brief summary (under 50 words).
What does it contain? What is its purpose?

File: {filename}
Content preview (first 500 chars):
{text_content[:500]}"""

                response = await provider.generate_content(prompt)
                return response.strip()
            except UnicodeDecodeError:
                pass
            except Exception as e:
                logger.error(f"Error analyzing text file: {e}")

        # Default description for other files
        size_mb = file_size / (1024 * 1024)
        if size_mb < 1:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{size_mb:.1f} MB"

        return f"{content_type or 'Unknown'} file, {size_str}"

    except Exception as e:
        logger.error(f"Error in file analysis: {e}")
        return None


@app.get("/file_thumbnail/{file_id:path}")
async def get_file_thumbnail(file_id: str, max_size: int = 200):
    """Get a thumbnail for an image file."""
    from urllib.parse import unquote

    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    try:
        # URL decode the file_id
        file_id = unquote(file_id)
        logger.info(f"Serving thumbnail for file: {file_id}")

        # Validate file_id format
        if not file_id.startswith("file:"):
            logger.error(f"Invalid file ID format: {file_id}")
            raise HTTPException(status_code=400, detail="Invalid file ID")

        # Extract the actual filename
        filename = file_id.replace("file:", "")
        file_path = f"uploads/{filename}"

        logger.info(f"Looking for file at: {file_path}")

        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")

        # Determine MIME type from file extension
        file_ext = filename.split(".")[-1].lower() if "." in filename else ""
        mime_type_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "bmp": "image/bmp",
        }

        if file_ext not in mime_type_map:
            logger.error(f"Not a supported image type: {file_ext}")
            raise HTTPException(status_code=400, detail="Not a supported image file")

        mime_type = mime_type_map[file_ext]
        logger.info(f"Serving image: {file_path} as {mime_type}")
        return FileResponse(file_path, media_type=mime_type)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving thumbnail for {file_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload_file")
async def upload_file(chat_id: str, user_id: str, file: UploadFile = File(...)):
    """Upload a file and store it, creating a corresponding node in the knowledge graph."""
    import re

    from fastapi import HTTPException

    if not chat_id or not user_id:
        raise HTTPException(status_code=400, detail="chat_id and user_id are required")

    # Security: File size limit (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes

    # Security: Allowed file types
    ALLOWED_EXTENSIONS = {
        "txt",
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "csv",
        "jpg",
        "jpeg",
        "png",
        "gif",
        "bmp",
        "webp",
        "mp3",
        "wav",
        "mp4",
        "avi",
        "mov",
        "zip",
        "tar",
        "gz",
        "json",
        "xml",
        "yaml",
        "yml",
        "py",
        "js",
        "ts",
        "java",
        "c",
        "cpp",
        "h",
        "hpp",
        "html",
        "css",
        "md",
        "rst",
    }

    try:
        # 1. Security: Validate filename and sanitize
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Remove any directory path from filename
        safe_original_name = os.path.basename(file.filename)
        # Remove any special characters that could be dangerous
        safe_original_name = re.sub(r"[^\w\s\-\.]", "_", safe_original_name)

        # Check file extension
        file_extension = (
            safe_original_name.split(".")[-1].lower()
            if "." in safe_original_name
            else ""
        )
        if not file_extension or file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        # 2. Read file content and check size
        content = await file.read()
        file_size = len(content)

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE / (1024 * 1024)}MB",
            )

        if file_size == 0:
            raise HTTPException(status_code=400, detail="File is empty")

        # 3. Generate a unique filename and save
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        upload_dir = "uploads"
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir, mode=0o755)
        file_path = os.path.join(upload_dir, unique_filename)

        async with aiofiles.open(file_path, "wb") as out_file:
            await out_file.write(content)

        # 4. Create a File node in the knowledge graph
        file_node_id = f"file:{unique_filename}"
        file_node_properties = {
            "file_name": safe_original_name,
            "file_size": file_size,
            "file_type": file.content_type or f"application/{file_extension}",
            "storage_path": file_path,
            "upload_timestamp": datetime.utcnow().isoformat(),
        }

        # Get the knowledge repository
        if (
            not _connection_manager
            or not _connection_manager.knowledge_instances
            or user_id not in _connection_manager.knowledge_instances
            or chat_id not in _connection_manager.knowledge_instances[user_id]
        ):
            raise HTTPException(
                status_code=404,
                detail=f"No knowledge graph found for user {user_id} and chat {chat_id}",
            )

        knowledge = _connection_manager.knowledge_instances[user_id][chat_id]

        if not knowledge or not knowledge.repository:
            raise HTTPException(
                status_code=500, detail="Knowledge repository not initialized"
            )

        try:
            knowledge.repository.add_node(
                node_id=file_node_id,
                node_type="File",
                label=safe_original_name,
                content=f"File uploaded to {file_path}",
                properties=file_node_properties,
            )

            # 5. Associate the file node with user and chat
            user_node_id = f"user:{user_id}"
            knowledge.repository.add_edge(
                source_id=user_node_id, target_id=file_node_id, edge_type="UPLOADED"
            )
            chat_node_id = f"chat:{chat_id}"
            knowledge.repository.add_edge(
                source_id=chat_node_id, target_id=file_node_id, edge_type="CONTAINS"
            )
            knowledge.repository.add_edge(
                source_id=f"chat:{chat_id}",
                target_id=file_node_id,
                edge_type="HAS_FILE",
            )

            # 6. Analyze file content and add description (async in background)
            file_description = await _analyze_file(
                file_path, safe_original_name, file.content_type, file_size, content
            )

            if file_description:
                # Update node with description
                file_node_properties["ai_description"] = file_description
                knowledge.repository.add_node(
                    node_id=file_node_id,
                    node_type="File",
                    label=safe_original_name,
                    content=f"File uploaded to {file_path}. AI Analysis: {file_description}",
                    properties=file_node_properties,
                )
                logger.info(f"Added AI description to file {safe_original_name}")

            logger.info(
                f"File uploaded successfully: {safe_original_name} -> {file_path} (node: {file_node_id})"
            )
            return {
                "file_id": file_node_id,
                "file_name": safe_original_name,
                "description": file_description,
            }

        except Exception as e:
            logger.error(f"Error creating file node in knowledge graph: {e}")
            # Clean up the file if knowledge graph operation fails
            try:
                os.remove(file_path)
            except Exception:
                pass
            raise HTTPException(
                status_code=500, detail=f"Error creating file node: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- WebSocket Chat Logic ---


@app.websocket("/ws/chat")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT authentication token"),
):
    """WebSocket endpoint with two-phase architecture:

    Phase 1: Initial connection and tool initialization
    Phase 2: Chat operations (start_chat, switch_chat, messages)
    """
    await websocket.accept()
    logger.info("Client connected to chat WebSocket.")

    user_id: Optional[str] = None
    current_chat_id: Optional[str] = None
    current_bot: Optional[AgentOrchestrator] = None
    current_bot_task: Optional[asyncio.Task] = None

    try:
        # Check server resources - only connection manager is needed at this point
        # Toolchain will be loaded lazily
        if _connection_manager is None:
            err = _startup_error or "Server resources not initialized"
            await websocket.send_text(
                WSMessage(
                    type=MessageType.error,
                    data=ErrorPayload(message=f"Server not ready: {err}"),
                ).to_text()
            )
            await websocket.close()
            return

        # ==================== PHASE 1: Initial Connection ====================

        # Wait for initial connect message
        raw_data = await websocket.receive_text()
        logger.info(f"Received initial message: {raw_data}")

        try:
            ws_msg = WSMessage.from_text(raw_data)
        except Exception as ve:
            await websocket.send_text(
                WSMessage(
                    type=MessageType.error,
                    data=ErrorPayload(message=f"Invalid message format: {ve}"),
                ).to_text()
            )
            await websocket.close()
            return

        # First message must be connect type
        if ws_msg.type != MessageType.connect:
            await websocket.send_text(
                WSMessage(
                    type=MessageType.error,
                    data=ErrorPayload(message="First message must be 'connect' type"),
                ).to_text()
            )
            await websocket.close()
            return

        # Handle session creation/reconnection
        connect_payload = ws_msg.data
        assert isinstance(connect_payload, ConnectPayload)

        # Get JWT token from query param or connect payload
        jwt_token = token or connect_payload.token

        # Authenticate user via JWT token
        from middleware.auth_middleware import get_user_from_websocket_token

        authenticated_user = None
        user_id = None

        if jwt_token:
            authenticated_user = get_user_from_websocket_token(jwt_token)
            if authenticated_user:
                user_id = authenticated_user.id
                logger.info(
                    f"Authenticated user via JWT: {user_id} ({authenticated_user.username})"
                )
            else:
                await websocket.send_text(
                    WSMessage(
                        type=MessageType.error,
                        data=ErrorPayload(
                            message="Invalid or expired authentication token"
                        ),
                    ).to_text()
                )
                await websocket.close()
                return
        elif connect_payload.user_id:
            # Fallback to user_id for backward compatibility (deprecated)
            user_id = connect_payload.user_id
            logger.warning(f"Using deprecated user_id parameter: {user_id}")
        else:
            await websocket.send_text(
                WSMessage(
                    type=MessageType.error,
                    data=ErrorPayload(message="Authentication token is required"),
                ).to_text()
            )
            await websocket.close()
            return

        # Register connection with user_id
        _connection_manager.connect(user_id, websocket)

        # Initialize tools with progress updates (lazy loading on first connection)
        logger.info(f"[{user_id}] Initializing tools...")
        toolchain, tool_error = await _connection_manager.initialize_tools_for_user(
            user_id, websocket
        )

        if tool_error or not toolchain:
            error_msg = tool_error or "Failed to initialize tools"
            logger.error(f"[{user_id}] Tool initialization failed: {error_msg}")
            await websocket.send_text(
                WSMessage(
                    type=MessageType.error,
                    data=ErrorPayload(
                        message=f"Tool initialization failed: {error_msg}"
                    ),
                    user_id=user_id,
                ).to_text()
            )
            await websocket.close()
            return

        # Send ready message
        tools_loaded = len(toolchain.tool_clients) if toolchain else 0
        logger.info(
            f"[{user_id}] User ready with {tools_loaded} tool(s), sending ready message"
        )
        await websocket.send_text(
            WSMessage(
                type=MessageType.ready,
                data=ReadyPayload(
                    tools_loaded=tools_loaded,
                ),
                user_id=user_id,
            ).to_text()
        )

        logger.info(f"[{user_id}] Phase 1 complete - user ready for chats")

        # ==================== PHASE 2: Chat Operations ====================

        # Track first message per chat for auto-naming
        first_message_processed = {}  # chat_id -> bool

        async def process_bot_message(user_message: str, file_id: Optional[str] = None):
            """Process a bot message and send the response."""
            if not current_bot or not current_chat_id:
                await websocket.send_text(
                    WSMessage(
                        type=MessageType.error,
                        data=ErrorPayload(
                            message="No active chat. Start a chat first."
                        ),
                        user_id=user_id,
                        chat_id=current_chat_id,
                    ).to_text()
                )
                return

            try:
                file_info = f" (with file: {file_id})" if file_id else ""
                logger.info(
                    f"[{user_id}:{current_chat_id}] Processing: {user_message[:50]}...{file_info}"
                )

                # Auto-generate chat name from first message if chat hasn't been named
                if not first_message_processed.get(current_chat_id, False):
                    first_message_processed[current_chat_id] = True

                    # Check if chat already has a custom name
                    should_generate_name = False
                    try:
                        from database.database import get_database_manager
                        from database.repository import KnowledgeRepository

                        db_manager = get_database_manager()
                        if not db_manager.engine:
                            db_manager.connect()
                        repository = KnowledgeRepository(db_manager)

                        chat_node = repository.get_chat(current_chat_id)
                        if chat_node:
                            # Check if chat has a name
                            current_name = (
                                chat_node.properties.get("chat_name")
                                if chat_node.properties
                                else chat_node.label
                            )

                            # Only generate name if chat doesn't have one or has default name
                            if (
                                not current_name
                                or current_name.startswith("Chat ")
                                or current_name.startswith("New Chat")
                            ):
                                should_generate_name = True
                                logger.info(
                                    f"[{user_id}:{current_chat_id}] Chat has no custom name, will auto-generate"
                                )
                            else:
                                logger.info(
                                    f"[{user_id}:{current_chat_id}] Chat already has name '{current_name}', skipping auto-generation"
                                )
                        else:
                            # Chat doesn't exist yet, will be created with auto-name
                            should_generate_name = True
                    except Exception as e:
                        logger.warning(
                            f"[{user_id}:{current_chat_id}] Error checking existing chat name: {e}"
                        )
                        # Default to generating name on error
                        should_generate_name = True

                    if should_generate_name:
                        # Generate chat name using LLM summarization
                        auto_name = None
                        try:
                            # Use LLM to generate a concise title
                            summarization_prompt = f"""Generate a brief, descriptive 3-5 word title for a chat conversation that starts with this message. 

Message: {user_message[:200]}

Respond with ONLY the title, no quotes or extra text. Keep it under 50 characters."""

                            logger.info(
                                f"[{user_id}:{current_chat_id}] Requesting LLM chat name summary..."
                            )
                            summary_response = (
                                await current_bot.provider.generate_content(
                                    summarization_prompt
                                )
                            )
                            auto_name = summary_response.strip()[
                                :50
                            ]  # Limit to 50 chars
                            logger.info(
                                f"[{user_id}:{current_chat_id}] LLM-generated chat name: '{auto_name}'"
                            )
                        except Exception as e:
                            # Fallback to first 50 chars if LLM fails
                            logger.warning(
                                f"[{user_id}:{current_chat_id}] LLM summarization failed: {e}, using fallback"
                            )
                            auto_name = user_message[:50].strip()
                            if len(user_message) > 50:
                                auto_name += "..."

                        # Update chat name in background
                        if auto_name:
                            try:
                                from database.database import get_database_manager
                                from database.repository import KnowledgeRepository

                                db_manager = get_database_manager()
                                if not db_manager.engine:
                                    db_manager.connect()
                                repository = KnowledgeRepository(db_manager)

                                # Check if chat exists first
                                chat_node = repository.get_chat(current_chat_id)
                                if chat_node:
                                    repository.update_chat_name(
                                        current_chat_id, auto_name
                                    )
                                    logger.info(
                                        f"[{user_id}:{current_chat_id}] Updated chat name to: '{auto_name}'"
                                    )
                                else:
                                    logger.warning(
                                        f"[{user_id}:{current_chat_id}] Chat not found, skipping auto-name"
                                    )
                            except Exception as e:
                                logger.warning(
                                    f"[{user_id}:{current_chat_id}] Failed to update chat name: {e}"
                                )

                response = await current_bot.send_message(user_message, file_id=file_id)
                logger.info(
                    f"[{user_id}:{current_chat_id}] Sending response: {response[:50]}..."
                )
                await websocket.send_text(
                    WSMessage(
                        type=MessageType.message,
                        data=ChatMessagePayload(text=response),
                        user_id=user_id,
                        chat_id=current_chat_id,
                    ).to_text()
                )
            except Exception as e:
                error_msg = str(e)
                logger.error(
                    f"[{user_id}:{current_chat_id}] Error processing message: {e}"
                )
                await websocket.send_text(
                    WSMessage(
                        type=MessageType.error,
                        data=ErrorPayload(
                            message=f"Error processing message: {error_msg}"
                        ),
                        user_id=user_id,
                        chat_id=current_chat_id,
                    ).to_text()
                )

        # Main message loop
        while True:
            raw_data = await websocket.receive_text()
            logger.info(f"[{user_id}] Received: {raw_data[:100]}...")

            try:
                ws_msg = WSMessage.from_text(raw_data)
            except Exception as ve:
                err = WSMessage(
                    type=MessageType.error,
                    data=ErrorPayload(message=f"Invalid message: {ve}"),
                    user_id=user_id,
                    chat_id=current_chat_id,
                )
                await websocket.send_text(err.to_text())
                continue

            if ws_msg.type == MessageType.start_chat:
                # Start or create a new chat
                payload = ws_msg.data
                assert isinstance(payload, StartChatPayload)
                logger.info(f"[{user_id}] Starting chat: {payload.chat_id}")

                try:
                    # Create/get bot for this chat
                    current_bot = await _connection_manager.create_bot_for_chat(
                        user_id=user_id,
                        chat_id=payload.chat_id,
                        chat_name=payload.chat_name,
                    )
                    current_chat_id = payload.chat_id

                    # Send chat_ready message
                    await websocket.send_text(
                        WSMessage(
                            type=MessageType.chat_ready,
                            data=ChatReadyPayload(
                                chat_id=payload.chat_id,
                                is_new=True,  # Could check if chat already existed
                            ),
                            user_id=user_id,
                            chat_id=payload.chat_id,
                        ).to_text()
                    )
                    logger.info(f"[{user_id}:{current_chat_id}] Chat ready")
                except Exception as e:
                    logger.error(f"[{user_id}] Error starting chat: {e}")
                    await websocket.send_text(
                        WSMessage(
                            type=MessageType.error,
                            data=ErrorPayload(message=f"Error starting chat: {e}"),
                            user_id=user_id,
                            chat_id=current_chat_id,
                        ).to_text()
                    )

            elif ws_msg.type == MessageType.switch_chat:
                # Switch to a different chat
                payload = ws_msg.data
                assert isinstance(payload, SwitchChatPayload)
                logger.info(f"[{user_id}] Switching to chat: {payload.chat_id}")

                try:
                    # Get or create bot for this chat
                    current_bot = await _connection_manager.switch_chat(
                        user_id=user_id,
                        chat_id=payload.chat_id,
                    )
                    current_chat_id = payload.chat_id

                    # Send chat_ready message
                    await websocket.send_text(
                        WSMessage(
                            type=MessageType.chat_ready,
                            data=ChatReadyPayload(
                                chat_id=payload.chat_id,
                                is_new=False,
                            ),
                            user_id=user_id,
                            chat_id=payload.chat_id,
                        ).to_text()
                    )
                    logger.info(f"[{user_id}:{current_chat_id}] Switched to chat")
                except Exception as e:
                    logger.error(f"[{user_id}] Error switching chat: {e}")
                    await websocket.send_text(
                        WSMessage(
                            type=MessageType.error,
                            data=ErrorPayload(message=f"Error switching chat: {e}"),
                            user_id=user_id,
                            chat_id=current_chat_id,
                        ).to_text()
                    )

            elif ws_msg.type == MessageType.message:
                # Regular chat message
                payload = ws_msg.data
                assert isinstance(payload, ChatMessagePayload)
                file_info = f" with file: {payload.file_id}" if payload.file_id else ""
                logger.info(
                    f"[{user_id}:{current_chat_id}] Received message: {payload.text[:50]}...{file_info}"
                )

                # If there's a current task, cancel it (new message cancels old)
                if current_bot_task and not current_bot_task.done():
                    logger.info(
                        f"[{user_id}:{current_chat_id}] Cancelling previous message"
                    )
                    current_bot_task.cancel()
                    try:
                        await current_bot_task
                    except asyncio.CancelledError:
                        logger.info(
                            f"[{user_id}:{current_chat_id}] Previous task cancelled"
                        )

                # Start processing in background (don't await)
                current_bot_task = asyncio.create_task(
                    process_bot_message(payload.text, payload.file_id)
                )

    except WebSocketDisconnect:
        logger.info(f"[{user_id}] Client disconnected.")
    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        logger.error(f"[{user_id}] Error in WebSocket: {e}")
        logger.error(f"[{user_id}] Traceback: {error_details}")
    finally:
        # Cancel any ongoing bot processing
        if current_bot_task and not current_bot_task.done():
            logger.info(f"[{user_id}] Cancelling ongoing bot task")
            current_bot_task.cancel()
            try:
                await current_bot_task
            except asyncio.CancelledError:
                pass

        # Disconnect but preserve bot instances for reconnection
        if user_id and _connection_manager:
            _connection_manager.disconnect(user_id)
        logger.info(f"[{user_id}] Connection closed (bot instances preserved).")


# --- Static Files (Web UI) ---
# Only mount static files if the build directory exists
# Try multiple paths to support both dev and Docker environments
BUILD_DIR_CANDIDATES = [
    "/app/agent/src/client/web_ui",  # Docker absolute path
    "src/client/web_ui",  # Relative from /app/agent working dir
    "agent/src/client/web_ui",  # Relative from /app
]

BUILD_DIR = None
for candidate in BUILD_DIR_CANDIDATES:
    if os.path.exists(candidate):
        BUILD_DIR = candidate
        break

if BUILD_DIR:
    logger.info(f"Frontend build directory found at {BUILD_DIR}, mounting static files")

    # Mount static files for assets (CSS, JS)
    static_dir = os.path.join(BUILD_DIR, "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static_assets")

    # Serve other static files (like manifest.json, robots.txt, etc.)
    @app.get("/manifest.json")
    async def manifest():
        """Serve manifest.json."""
        return FileResponse(os.path.join(BUILD_DIR, "manifest.json"))

    @app.get("/robots.txt")
    async def robots():
        """Serve robots.txt."""
        return FileResponse(os.path.join(BUILD_DIR, "robots.txt"))

    @app.get("/favicon.ico")
    async def favicon():
        """Serve favicon."""
        return FileResponse(os.path.join(BUILD_DIR, "favicon.ico"))

    @app.get("/robot-logo.svg")
    async def logo():
        """Serve logo."""
        return FileResponse(os.path.join(BUILD_DIR, "robot-logo.svg"))

    # Explicit root route for the main page
    @app.get("/")
    async def serve_root():
        """Serve the main index.html."""
        index_path = os.path.join(BUILD_DIR, "index.html")
        if not os.path.exists(index_path):
            logger.error(f"index.html not found at {index_path}")
            return {"error": "UI not available", "expected_path": index_path}
        return FileResponse(index_path)

    # Catch-all route for SPA - must be LAST
    # This handles all paths not matched above (like /chat/:chatId)
    # BUT exclude API routes to avoid intercepting backend endpoints
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve index.html for all unmatched routes (SPA routing)."""
        # Don't serve SPA for API routes - let them 404 naturally
        if full_path.startswith("api/"):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=404, detail=f"API endpoint not found: /{full_path}"
            )

        index_path = os.path.join(BUILD_DIR, "index.html")
        if not os.path.exists(index_path):
            logger.error(f"index.html not found at {index_path}")
            return {"error": "UI not available", "expected_path": index_path}
        return FileResponse(index_path)

else:
    logger.warning(
        f"Frontend build directory not found at {BUILD_DIR}. "
        "Run 'make build-ui deploy-ui' from the project root to build and deploy the frontend. "
        "API routes will still work, but the web UI will not be available."
    )
