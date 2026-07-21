"""Handler registration for the Sparky command bus."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_handlers_registered = False


def register_handlers() -> None:
    """Register command handlers idempotently."""
    global _handlers_registered
    if _handlers_registered:
        return

    from commands.bus_config import _ensure_router
    from commands.commands import RunAgentTaskCommand
    from commands.handlers.run_agent_task import RunAgentTaskHandler

    router = _ensure_router()
    router.register(RunAgentTaskCommand, RunAgentTaskHandler)
    _handlers_registered = True
    logger.info("Command handlers registered (RunAgentTask)")
