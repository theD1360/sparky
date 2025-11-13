"""WebSocket event forwarder for agent task execution.

This module provides utilities to forward AgentOrchestrator events
to WebSocket clients for real-time updates.
"""

import logging
from typing import Any, Optional

from models import (
    ChatMessagePayload,
    ErrorPayload,
    MessageType,
    StatusPayload,
    ThoughtPayload,
    ToolResultPayload,
    ToolUsePayload,
    WSMessage,
)

logger = logging.getLogger(__name__)


class WebSocketForwarder:
    """Forwards bot events to WebSocket connections."""

    def __init__(
        self,
        websocket: Any,
        session_id: str,
        user_id: str,
        chat_id: str,
        task_id: Optional[str] = None,
    ):
        """Initialize the WebSocket forwarder.

        Args:
            websocket: WebSocket connection to send messages to
            session_id: Session identifier
            user_id: User identifier
            chat_id: Chat identifier
            task_id: Optional task identifier to mark messages as task-related
        """
        self.websocket = websocket
        self.session_id = session_id
        self.user_id = user_id
        self.chat_id = chat_id
        self.task_id = task_id

    async def send_message(
        self,
        message_type: MessageType,
        data: Any,
    ) -> bool:
        """Send a WebSocket message.

        Args:
            message_type: Type of message to send
            data: Message payload

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            ws_msg = WSMessage(
                type=message_type,
                data=data,
                session_id=self.session_id,
                user_id=self.user_id,
                chat_id=self.chat_id,
            )
            message_text = ws_msg.to_text()
            await self.websocket.send_text(message_text)
            logger.info(
                f"📤 Sent {message_type.value} message to user={self.user_id}, session={self.session_id}, chat={self.chat_id}"
            )
            # Log the actual data for debugging
            if message_type in [MessageType.status, MessageType.error]:
                logger.debug(f"   Content: {data}")
            return True
        except RuntimeError as e:
            # WebSocket was closed (user refreshed page, disconnected, etc.)
            if "websocket.close" in str(e).lower() or "already completed" in str(e).lower():
                logger.debug(
                    f"🔌 WebSocket closed for user={self.user_id}, chat={self.chat_id} - skipping {message_type.value} message"
                )
                return False
            # Other RuntimeError, log it
            logger.error(
                f"RuntimeError sending {message_type.value} message to WebSocket: {e}",
                exc_info=True,
            )
            return False
        except Exception as e:
            logger.error(
                f"Error sending {message_type.value} message to WebSocket: {e}",
                exc_info=True,
            )
            return False

    async def forward_tool_use(self, tool_name: str, tool_args: dict) -> bool:
        """Forward a tool use event.

        Args:
            tool_name: Name of the tool being used
            tool_args: Arguments passed to the tool

        Returns:
            True if sent successfully, False otherwise
        """
        payload = ToolUsePayload(name=tool_name, args=tool_args, task_id=self.task_id)
        return await self.send_message(MessageType.tool_use, payload)

    async def forward_tool_result(self, tool_name: str, result: str) -> bool:
        """Forward a tool result event.

        Args:
            tool_name: Name of the tool that was used
            result: Result from the tool

        Returns:
            True if sent successfully, False otherwise
        """
        payload = ToolResultPayload(name=tool_name, result=result, task_id=self.task_id)
        return await self.send_message(MessageType.tool_result, payload)

    async def forward_thought(self, thought: str) -> bool:
        """Forward a thought event.

        Args:
            thought: The AI's thought/reasoning text

        Returns:
            True if sent successfully, False otherwise
        """
        payload = ThoughtPayload(text=thought, task_id=self.task_id)
        return await self.send_message(MessageType.thought, payload)

    async def forward_message(self, text: str) -> bool:
        """Forward a message event.

        Args:
            text: Message text

        Returns:
            True if sent successfully, False otherwise
        """
        payload = ChatMessagePayload(text=text, task_id=self.task_id)
        return await self.send_message(MessageType.message, payload)

    async def forward_status(self, status: str) -> bool:
        """Forward a status update.

        Args:
            status: Status message

        Returns:
            True if sent successfully, False otherwise
        """
        payload = StatusPayload(message=status, task_id=self.task_id)
        return await self.send_message(MessageType.status, payload)

    async def forward_error(self, error: str) -> bool:
        """Forward an error message.

        Args:
            error: Error message

        Returns:
            True if sent successfully, False otherwise
        """
        payload = ErrorPayload(message=error, task_id=self.task_id)
        return await self.send_message(MessageType.error, payload)


async def create_websocket_forwarder(
    connection_manager: Any,
    user_id: str,
    chat_id: str,
    task_id: Optional[str] = None,
) -> Optional[WebSocketForwarder]:
    """Create a WebSocket forwarder for a user if they have an active connection.

    Args:
        connection_manager: ConnectionManager instance
        user_id: User identifier to lookup
        chat_id: Chat identifier for the messages
        task_id: Optional task identifier to mark messages as task-related

    Returns:
        WebSocketForwarder instance if user has active connection, None otherwise
    """
    if not connection_manager:
        logger.debug("No connection manager available, skipping WebSocket forwarding")
        return None

    # Look up active connection for the user
    connection_info = connection_manager.get_active_connection_by_user(user_id)
    if not connection_info:
        logger.debug(f"No active WebSocket connection for user {user_id}")
        return None

    session_id, websocket, _ = connection_info

    logger.info(
        f"Creating WebSocket forwarder for user {user_id} (session={session_id}, chat={chat_id}, task={task_id})"
    )

    return WebSocketForwarder(
        websocket=websocket,
        session_id=session_id,
        user_id=user_id,
        chat_id=chat_id,
        task_id=task_id,
    )

