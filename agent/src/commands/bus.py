"""Command bus dispatch helpers — enqueue work for the agent worker."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def dispatch_async(
    command: Any,
    wait: bool = False,
    timeout_seconds: int = 300,
    queue_name: Optional[str] = None,
) -> Any:
    """Dispatch a command through Redis to the worker.

    Args:
        command: CommandMessage instance
        wait: If True, poll response store until done (rarely used for agent tasks)
        timeout_seconds: Client wait bound when wait=True
        queue_name: Optional Redis list override

    Returns:
        Handler result when wait=True, otherwise None
    """
    from commands.bus_config import create_bus, get_redis_client

    bus = create_bus(queue_name=queue_name)
    logger.info(
        "Dispatching %s to queue %s (wait=%s)",
        type(command).__name__,
        bus.queue_adapter.queue_name,
        wait,
    )
    result = await bus.execute(command, wait=wait, timeout_seconds=timeout_seconds)

    if not wait:
        try:
            rc = get_redis_client()
            qn = bus.queue_adapter.queue_name
            depth = rc.llen(qn)
            logger.info(
                "Queue verify after enqueue: key=%r LLEN=%s",
                qn,
                depth,
            )
        except Exception as e:
            logger.warning("Could not LLEN queue after enqueue: %s", e)
        return None

    if isinstance(result, dict) and result.get("error") is True:
        error_type = result.get("error_type", "Exception")
        error_message = result.get("error_message", "Unknown error")
        raise RuntimeError(f"{error_type}: {error_message}")

    return result
