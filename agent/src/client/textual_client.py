from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from typing import Any, Optional

import websockets
from rich.console import Group
from rich.markdown import Markdown
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Footer, Static, TextArea

from models import MessageType, WSMessage


# Set up client-specific logger
def setup_client_logger():
    """Configure a dedicated logger for the chat client."""
    log_dir = os.getenv("LOG_DIR", "logs")
    log_file_path = os.path.join(log_dir, "client.log")

    # Create log directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)

    # Get log level from environment, default to INFO
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    log_level = log_level_map.get(log_level_str, logging.INFO)

    # Create logger for client
    logger = logging.getLogger("sparky.client")
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create file handler with rotation
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=1024 * 1024 * 5,  # 5 MB
        backupCount=5,
    )
    file_handler.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False

    return logger


# Initialize client logger
_client_logger = setup_client_logger()


@dataclass
class ChatEvent:
    kind: str  # 'bot', 'user', 'status', 'error', 'thought'
    text: str


class ChatLog(Static):
    """A scrollable chat log that appends messages."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._messages = []

    def append_line(self, text: str, role: str = "bot") -> None:
        """Append a line to the chat log."""
        # Color-coded prefixes for different roles
        if role == "user":
            prefix_text = Text("You ", style="bold spring_green3")
        elif role == "status":
            prefix_text = Text("Status ", style="yellow")
        elif role == "thought":
            prefix_text = Text("Thinking ", style="yellow italic")
        elif role == "error":
            prefix_text = Text("Error ", style="bold red")
        else:
            prefix_text = Text("Bot ", style="bold sky_blue1")

        # Render the message text as markdown
        message_md = Markdown(text)

        # Combine prefix and markdown content
        combined = Text.assemble(prefix_text)
        self._messages.append((combined, message_md))

        # Build the full content from all messages
        renderables = []
        for i, (prefix, md) in enumerate(self._messages):
            if i > 0:
                renderables.append(Text("\n"))
            renderables.append(prefix)
            renderables.append(md)

        self.update(Group(*renderables))
        # Scroll the parent VerticalScroll container to the bottom
        parent = self.parent
        if parent:
            self.call_later(lambda: parent.scroll_end(animate=False))


class InfoLog(Static):
    """A scrollable log for tool usage and results."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._messages = []

    def append_line(self, text: str, kind: str = "tool_use") -> None:
        """Append a line to the info log."""
        # Color-coded prefixes for tool events
        if kind == "tool_use":
            prefix_text = Text("[Tool] ", style="magenta")
        elif kind == "tool_result":
            prefix_text = Text("[Result] ", style="cyan")
        elif kind == "thought":
            prefix_text = Text("[Thinking] 💭 ", style="yellow italic")
        else:
            prefix_text = Text(f"{kind.capitalize()} ", style="white")

        # Render the message text as markdown
        message_md = Markdown(text)

        # Combine prefix and markdown content
        combined = Text.assemble(prefix_text)
        self._messages.append((combined, message_md))

        # Build the full content from all messages
        renderables = []
        for i, (prefix, md) in enumerate(self._messages):
            if i > 0:
                renderables.append(Text("\n"))
            renderables.append(prefix)
            renderables.append(md)

        self.update(Group(*renderables))
        # Scroll the parent VerticalScroll container to the bottom
        parent = self.parent
        if parent:
            self.call_later(lambda: parent.scroll_end(animate=False))


class ChatApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    # Root horizontal split: chat (left) and info (right)
    Horizontal#root {
        height: 1fr;
    }
    Vertical#main {
        width: 2fr;
        height: 1fr;
    }
    VerticalScroll {
        height: 1fr;
        border: round $secondary;
        border-title-align: center;
        border-title-color: $secondary;
        border-title-background: $panel;
        border-title-style: bold;
        background: $panel;
    }
    VerticalScroll#info_scroll {
        width: 1fr;
        border: round $primary;
        border-title-align: center;
        border-title-color: $primary;
        border-title-background: $boost;
        border-title-style: bold;
        background: $boost;
    }
    Static#chatlog {
        padding: 1 1;
        content-align: left top;
        width: 100%;
    }
    Horizontal#input_row {
        height: 6;
    }
    TextArea#chat_input {
        width: 1fr;
        height: 4;
    }
    Static#infolog {
        padding: 1 1;
        content-align: left top;
        width: 100%;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+s", "submit_text", "Send Message"),
    ]

    host: str
    port: int
    personality: Optional[str]
    session_id: Optional[str]

    # Reactive connection state
    connected: reactive[bool] = reactive(False)

    def __init__(
        self,
        host: str,
        port: int,
        personality: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self.personality = personality
        self.session_id = session_id
        self._ws: Any | None = None  # WebSocket connection
        self._incoming: asyncio.Queue[ChatEvent] = asyncio.Queue()
        self._receiver_task: asyncio.Task | None = None
        self._sender_lock = asyncio.Lock()
        self._stop = asyncio.Event()
        _client_logger.info(
            f"Chat client initialized: host={host}, port={port}, session_id={session_id}"
        )

    def compose(self) -> ComposeResult:
        # Create the chat scroll container with a title
        chat_scroll = VerticalScroll(
            ChatLog(id="chatlog"),
        )
        chat_scroll.border_title = "Chat"

        # Create the info scroll container with a title
        info_scroll = VerticalScroll(
            InfoLog(id="infolog"),
            id="info_scroll",
        )
        info_scroll.border_title = "Tool Activity"

        yield Horizontal(
            Vertical(
                chat_scroll,
                Horizontal(
                    TextArea(text="", id="chat_input"),
                    id="input_row",
                ),
                id="main",
            ),
            info_scroll,
            id="root",
        )
        yield Footer()

    async def on_mount(self) -> None:
        self.call_after_refresh(self.query_one(TextArea).focus)
        # Start background worker
        self._receiver_task = asyncio.create_task(self._connect_and_run())
        # Periodically drain incoming queue to update UI
        self.set_interval(0.05, self._drain_incoming)

    async def action_quit(self) -> None:
        await self._shutdown()
        await super().action_quit()

    async def action_submit_text(self) -> None:
        """Submit the current text in the textarea."""
        textarea = self.query_one(TextArea)
        text = textarea.text.strip()
        if not text:
            return

        _client_logger.info(f"User message: {text}")

        # Echo user message to the chat log
        await self._incoming.put(ChatEvent("user", text))

        # Send to server
        async with self._sender_lock:
            try:
                if self._ws is not None:
                    await self._ws.send(json.dumps({"type": "message", "data": text}))
                    _client_logger.debug(f"Message sent to server: {text[:100]}...")
                    # Clear input only on successful send
                    textarea.text = ""
                else:
                    error_msg = "Not connected. Message not sent."
                    _client_logger.error(error_msg)
                    await self._incoming.put(ChatEvent("error", error_msg))
            except websockets.exceptions.ConnectionClosed:
                error_msg = "Connection closed. Message not sent."
                _client_logger.error(error_msg)
                await self._incoming.put(ChatEvent("error", error_msg))
            except Exception as e:
                error_msg = f"Send failed: {e}"
                _client_logger.error(error_msg, exc_info=True)
                await self._incoming.put(ChatEvent("error", error_msg))

    async def _shutdown(self) -> None:
        _client_logger.info("Shutting down chat client")
        self._stop.set()
        if self._receiver_task and not self._receiver_task.done():
            self._receiver_task.cancel()
        if self._ws:
            try:
                await self._ws.close(code=1000)
                _client_logger.debug("WebSocket connection closed")
            except Exception as e:
                _client_logger.warning(f"Error closing WebSocket: {e}")
        self._ws = None

    async def _send_heartbeat(self, ws):
        try:
            while not self._stop.is_set():
                await asyncio.sleep(10)
                try:
                    await ws.send(json.dumps({"type": "ping"}))
                    _client_logger.debug("Heartbeat ping sent")
                except Exception as e:
                    _client_logger.warning(f"Heartbeat failed: {e}")
                    break
        except Exception:
            pass

    async def _connect_and_run(self) -> None:
        uri = f"ws://{self.host}:{self.port}/ws/chat"
        _client_logger.info(f"Attempting to connect to {uri}")

        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with websockets.connect(uri) as ws:
                    self._ws = ws
                    self.connected = True
                    _client_logger.info(f"Successfully connected to {uri}")
                    await self._incoming.put(ChatEvent("status", f"Connected to {uri}"))

                    # Send connect message with session_id and personality
                    import uuid
                    import os

                    USER_ID_FILE = "user_id.txt"
                    def get_user_id():
                        if os.path.exists(USER_ID_FILE):
                            with open(USER_ID_FILE, "r") as f:
                                user_id = f.read().strip()
                        else:
                            user_id = str(uuid.uuid4())
                            with open(USER_ID_FILE, "w") as f:
                                f.write(user_id)
                        return user_id

                    user_id = get_user_id()

                    connect_data = {
                        "session_id": self.session_id,
                        "personality": self.personality,
                        "user_id": user_id
                    }
                    message = WSMessage(type=MessageType.connect, data=connect_data)

                    _client_logger.debug(
                        f"Sending connect message: session_id={self.session_id}, has_personality={self.personality is not None}, user_id={user_id}"
                    )
                    await ws.send(message.json())
                    await self._incoming.put(ChatEvent("status", "Handshake sent"))
                    _client_logger.info("Connect handshake sent")

                    # Wait for session_info response
                    try:
                        await self._incoming.put(
                            ChatEvent("status", "Waiting for session info...")
                        )
                        response = await asyncio.wait_for(ws.recv(), timeout=30.0)
                        ws_msg = WSMessage.from_text(response)
                        if ws_msg.type == MessageType.session_info:
                            session_info = ws_msg.data
                            self.session_id = session_info.session_id
                            _client_logger.info(
                                f"Received session info: session_id={session_info.session_id}, is_new={session_info.is_new}, reconnected={session_info.reconnected}"
                            )
                            if session_info.is_new:
                                await self._incoming.put(
                                    ChatEvent(
                                        "status",
                                        f"New session: {self.session_id[:8]}...",
                                    )
                                )
                            elif session_info.reconnected:
                                await self._incoming.put(
                                    ChatEvent(
                                        "status",
                                        f"Reconnected to: {self.session_id[:8]}...",
                                    )
                                )
                        elif ws_msg.type == MessageType.error:
                            error_msg = f"Connection error: {ws_msg.data.message}"
                            _client_logger.error(error_msg)
                            await self._incoming.put(ChatEvent("error", error_msg))
                            return
                    except asyncio.TimeoutError:
                        error_msg = "Timeout waiting for session info (30s). The server may be initializing slowly due to knowledge system loading."
                        _client_logger.error(error_msg)
                        await self._incoming.put(ChatEvent("error", error_msg))
                        return

                    # Clear personality after sending in connect message
                    self.personality = None

                    # Receiver loop
                    async for message in ws:
                        try:
                            ws_msg = WSMessage.from_text(message)
                            if ws_msg.type == MessageType.message:
                                _client_logger.info(f"Bot response: {ws_msg.data.text}")
                                await self._incoming.put(
                                    ChatEvent("bot", ws_msg.data.text)
                                )
                            elif ws_msg.type == MessageType.status:
                                _client_logger.debug(
                                    f"Received status: {ws_msg.data.message}"
                                )
                                await self._incoming.put(
                                    ChatEvent("status", ws_msg.data.message)
                                )
                            elif ws_msg.type == MessageType.error:
                                error_msg = ws_msg.data.message
                                _client_logger.error(
                                    f"Received error from server: {error_msg}"
                                )
                                await self._incoming.put(ChatEvent("error", error_msg))
                            elif ws_msg.type == MessageType.tool_use:
                                try:
                                    tool_name = ws_msg.data.name
                                    tool_args = ws_msg.data.args
                                except Exception:
                                    dd = getattr(ws_msg, "data", {})
                                    tool_name = (
                                        dd.get("name") if isinstance(dd, dict) else None
                                    )
                                    tool_args = (
                                        dd.get("args") if isinstance(dd, dict) else None
                                    )
                                _client_logger.debug(
                                    f"Tool use: {tool_name}({tool_args})"
                                )
                                await self._incoming.put(
                                    ChatEvent("tool_use", f"{tool_name}({tool_args})")
                                )
                            elif ws_msg.type == MessageType.tool_result:
                                try:
                                    tool_name = ws_msg.data.name
                                    result_text = ws_msg.data.result
                                except Exception:
                                    dd = getattr(ws_msg, "data", {})
                                    tool_name = (
                                        dd.get("name") if isinstance(dd, dict) else None
                                    )
                                    result_text = (
                                        dd.get("result")
                                        if isinstance(dd, dict)
                                        else None
                                    )
                                _client_logger.debug(
                                    f"Tool result: {tool_name} → {result_text}"
                                )
                                await self._incoming.put(
                                    ChatEvent(
                                        "tool_result", f"{tool_name} → {result_text}"
                                    )
                                )
                            elif ws_msg.type == MessageType.thought:
                                try:
                                    thought_text = ws_msg.data.text
                                except Exception:
                                    dd = getattr(ws_msg, "data", {})
                                    thought_text = (
                                        dd.get("text")
                                        if isinstance(dd, dict)
                                        else str(dd)
                                    )
                                _client_logger.debug(
                                    f"Thought: {thought_text[:100]}..."
                                )
                                await self._incoming.put(
                                    ChatEvent("thought", thought_text)
                                )
                            elif ws_msg.type == MessageType.session_info:
                                # Additional session_info messages (shouldn't normally happen)
                                session_info = ws_msg.data
                                await self._incoming.put(
                                    ChatEvent(
                                        "status",
                                        f"Session: {session_info.session_id[:8]}...",
                                    )
                                )
                            else:
                                await self._incoming.put(
                                    ChatEvent("status", str(message))
                                )
                        except Exception as e:
                            _client_logger.warning(
                                f"Error processing message: {e}", exc_info=True
                            )
                            await self._incoming.put(ChatEvent("status", str(message)))
            except (websockets.exceptions.ConnectionClosedError, OSError) as e:
                self.connected = False
                _client_logger.warning(
                    f"Connection lost: {e}. Attempting to reconnect..."
                )
                jitter = random.uniform(0, 0.5)
                wait_time = backoff + jitter
                await self._incoming.put(
                    ChatEvent(
                        "status",
                        f"Connection lost. Reconnecting in {wait_time:.1f}s...",
                    )
                )
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=wait_time)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 1.5, 10.0)
                _client_logger.info(f"Reconnecting with backoff: {wait_time:.1f}s")
                continue
            except websockets.exceptions.ConnectionClosedOK:
                # Normal close; exit loop
                _client_logger.info("Connection closed normally")
                break
            except Exception as e:
                error_msg = f"Client error: {e}"
                _client_logger.error(error_msg, exc_info=True)
                await self._incoming.put(ChatEvent("error", error_msg))
                # Brief pause to avoid tight loop on persistent errors
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
            finally:
                self.connected = False
                self._ws = None

    async def _drain_incoming(self) -> None:
        chatlog = self.query_one(ChatLog)
        infolog = self.query_one(InfoLog)
        while not self._incoming.empty():
            evt = await self._incoming.get()
            if evt.kind == "user":
                chatlog.append_line(evt.text, role="user")
            elif evt.kind == "status":
                chatlog.append_line(evt.text, role="status")
            elif evt.kind == "error":
                chatlog.append_line(evt.text, role="error")
            elif evt.kind == "tool_use":
                infolog.append_line(evt.text, kind="tool_use")
            elif evt.kind == "tool_result":
                infolog.append_line(evt.text, kind="tool_result")
            elif evt.kind == "thought":
                # Display thoughts in both panels
                chatlog.append_line(f"💭 {evt.text}", role="thought")
                infolog.append_line(evt.text, kind="thought")
            else:
                chatlog.append_line(evt.text, role="bot")

    async def on_text_area_submitted(self, event: TextArea.Submitted) -> None:
        text = (event.text_area.text or "").strip()
        if not text:
            return

        _client_logger.info(f"User message: {text}")

        # Echo user message to the chat log
        await self._incoming.put(ChatEvent("user", text))

        # Send to server
        async with self._sender_lock:
            try:
                if self._ws is not None:
                    await self._ws.send(json.dumps({"type": "message", "data": text}))
                    _client_logger.debug(f"Message sent to server: {text[:100]}...")
                    # Clear input only on successful send
                    event.text_area.text = ""
                else:
                    error_msg = "Not connected. Message not sent."
                    _client_logger.error(error_msg)
                    await self._incoming.put(ChatEvent("error", error_msg))
            except websockets.exceptions.ConnectionClosed:
                error_msg = "Connection closed. Message not sent."
                _client_logger.error(error_msg)
                await self._incoming.put(ChatEvent("error", error_msg))
            except Exception as e:
                error_msg = f"Send failed: {e}"
                _client_logger.error(error_msg, exc_info=True)
                await self._incoming.put(ChatEvent("error", error_msg))


async def run_textual_client(
    host: str,
    port: int,
    personality: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    _client_logger.info(f"Starting textual client: host={host}, port={port}")
    app = ChatApp(host=host, port=port, personality=personality, session_id=session_id)
    await app.run_async()  # Allows running from within Typer/async context
    _client_logger.info("Textual client stopped")
