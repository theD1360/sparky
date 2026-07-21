"""Shared command bus configuration (Redis-backed)."""

from __future__ import annotations

import logging
import os
from typing import Optional

from command_bus import CommandBus, CommandBusRouter
from command_bus.adapters import RedisCommandBusAdapter, RedisResponseStore

logger = logging.getLogger(__name__)

_router: Optional[CommandBusRouter] = None
_redis_client = None


def get_redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


def get_redis_queue_name() -> str:
    return os.getenv("REDIS_QUEUE_NAME", "sparky:commands")


def get_redis_events_channel() -> str:
    return os.getenv("REDIS_EVENTS_CHANNEL", "sparky:events")


def get_response_ttl_seconds() -> int:
    return int(os.getenv("REDIS_COMMAND_BUS_RESPONSE_TTL_SECONDS", "3600"))


def _ensure_router() -> CommandBusRouter:
    global _router
    if _router is None:
        _router = CommandBusRouter()
    return _router


def get_router() -> CommandBusRouter:
    """Return the shared command router with handlers registered."""
    from commands.handlers.register import register_handlers

    register_handlers()
    return _ensure_router()


def reset_redis_client() -> None:
    """Drop cached Redis client (e.g. after env override in worker)."""
    global _redis_client
    _redis_client = None


def get_redis_client():
    """Shared sync Redis client for queue, response store, and pub/sub."""
    global _redis_client
    if _redis_client is None:
        import redis

        _redis_client = redis.from_url(get_redis_url(), decode_responses=False)
    return _redis_client


def create_bus(queue_name: Optional[str] = None) -> CommandBus:
    """Create a Redis-backed command bus."""
    from commands.handlers.register import register_handlers

    register_handlers()
    router = _ensure_router()
    qn = queue_name or get_redis_queue_name()
    ttl = get_response_ttl_seconds()
    rc = get_redis_client()
    adapter = RedisCommandBusAdapter(redis_client=rc, queue_name=qn)
    response_store = RedisResponseStore(
        redis_client=rc,
        key_prefix=f"{qn}:response:",
        default_ttl_seconds=ttl,
    )
    logger.debug("Created Redis command bus queue=%s", qn)
    return CommandBus(
        queue_adapter=adapter,
        command_router=router,
        response_store=response_store,
        response_ttl_seconds=ttl,
    )
