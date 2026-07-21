"""Redis pub/sub subscriber: forward worker task events to WebSocket clients."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Optional

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from servers.chat.chat_server import ConnectionManager


async def run_task_events_subscriber(
    connection_manager: "ConnectionManager",
) -> None:
    """Listen on REDIS_EVENTS_CHANNEL and forward envelopes to user WebSockets."""
    try:
        import redis.asyncio as aioredis
    except ImportError:
        logger.error("redis.asyncio not available; task event subscriber not started")
        return

    from commands.bus_config import get_redis_events_channel, get_redis_url
    from models import MessageType, WSMessage

    url = get_redis_url()
    channel = get_redis_events_channel()
    redis_client = None
    pubsub = None

    try:
        redis_client = aioredis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=5.0,
            socket_timeout=5.0,
        )
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)
        logger.info("Task events subscriber listening on %s", channel)

        while True:
            try:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
            except asyncio.CancelledError:
                break
            if msg is None:
                continue
            if msg.get("type") != "message":
                continue
            data = msg.get("data")
            if not isinstance(data, str):
                continue
            await _forward_envelope(connection_manager, data, MessageType, WSMessage)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.warning("Task events subscriber stopped: %s", e, exc_info=True)
    finally:
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            except Exception:
                pass
        if redis_client is not None:
            try:
                await redis_client.aclose()
            except Exception:
                pass


async def _forward_envelope(
    connection_manager: Any,
    raw: str,
    MessageType: Any,
    WSMessage: Any,
) -> None:
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid task event JSON: %s", raw[:200])
        return

    user_id = envelope.get("user_id")
    chat_id = envelope.get("chat_id")
    msg_type = envelope.get("type")
    payload_data = envelope.get("data") or {}

    if not user_id or not msg_type:
        return

    websocket = connection_manager.active_connections.get(user_id)
    if websocket is None:
        logger.debug("No active WS for user %s; dropping task event %s", user_id, msg_type)
        return

    try:
        mt = MessageType(msg_type)
        ws_msg = WSMessage.from_dict(
            {
                "type": mt.value if hasattr(mt, "value") else msg_type,
                "data": payload_data,
                "user_id": user_id,
                "chat_id": chat_id,
            }
        )
        await websocket.send_text(ws_msg.to_text())
    except Exception as e:
        err = str(e).lower()
        if "close" in err or "disconnect" in err:
            logger.debug("WS closed while forwarding task event to %s", user_id)
        else:
            logger.warning(
                "Failed to forward task event to user %s: %s", user_id, e
            )
