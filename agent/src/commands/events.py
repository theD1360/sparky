"""Publish task events to Redis for chat-server WebSocket fan-out."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def publish_task_event(
    *,
    user_id: str,
    chat_id: str,
    message_type: str,
    data: Dict[str, Any],
    task_id: Optional[str] = None,
) -> None:
    """Publish a WS-shaped event envelope to REDIS_EVENTS_CHANNEL.

    Chat server subscribers forward this to the user's active WebSocket.
    Failures are logged and do not raise.
    """
    try:
        from commands.bus_config import get_redis_client, get_redis_events_channel

        envelope = {
            "user_id": user_id,
            "chat_id": chat_id,
            "task_id": task_id,
            "type": message_type,
            "data": data,
        }
        body = json.dumps(envelope, separators=(",", ":"), default=str)
        channel = get_redis_events_channel()
        get_redis_client().publish(channel, body)
        logger.debug(
            "Published task event type=%s user=%s chat=%s task=%s",
            message_type,
            user_id,
            chat_id,
            task_id,
        )
    except Exception as e:
        logger.warning("Failed to publish task event %s: %s", message_type, e)


class RedisTaskEventSink:
    """Event sink mimicking WebSocketForwarder methods via Redis pub/sub."""

    def __init__(
        self,
        user_id: str,
        chat_id: str,
        task_id: Optional[str] = None,
    ):
        self.user_id = user_id
        self.chat_id = chat_id
        self.task_id = task_id

    async def forward_tool_use(self, tool_name: str, tool_args: dict) -> bool:
        publish_task_event(
            user_id=self.user_id,
            chat_id=self.chat_id,
            task_id=self.task_id,
            message_type="tool_use",
            data={"name": tool_name, "args": tool_args, "task_id": self.task_id},
        )
        return True

    async def forward_tool_result(
        self, tool_name: str, result: str, status: str = None
    ) -> bool:
        publish_task_event(
            user_id=self.user_id,
            chat_id=self.chat_id,
            task_id=self.task_id,
            message_type="tool_result",
            data={
                "name": tool_name,
                "result": result,
                "status": status,
                "task_id": self.task_id,
            },
        )
        return True

    async def forward_thought(self, thought: str) -> bool:
        publish_task_event(
            user_id=self.user_id,
            chat_id=self.chat_id,
            task_id=self.task_id,
            message_type="thought",
            data={"text": thought, "task_id": self.task_id},
        )
        return True

    async def forward_message(self, text: str) -> bool:
        publish_task_event(
            user_id=self.user_id,
            chat_id=self.chat_id,
            task_id=self.task_id,
            message_type="message",
            data={"text": text, "task_id": self.task_id},
        )
        return True

    async def forward_status(self, status: str) -> bool:
        publish_task_event(
            user_id=self.user_id,
            chat_id=self.chat_id,
            task_id=self.task_id,
            message_type="status",
            data={"message": status, "task_id": self.task_id},
        )
        return True

    async def forward_error(self, error: str) -> bool:
        publish_task_event(
            user_id=self.user_id,
            chat_id=self.chat_id,
            task_id=self.task_id,
            message_type="error",
            data={"message": error, "task_id": self.task_id},
        )
        return True
