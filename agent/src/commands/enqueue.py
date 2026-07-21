"""Enqueue helper: persist Task in KG then dispatch RunAgentTask to the worker."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def enqueue_agent_task(
    instruction: str,
    metadata: Optional[Dict[str, Any]] = None,
    depends_on: Optional[List[str]] = None,
    allow_duplicates: bool = False,
    chat_id: Optional[str] = None,
    task_queue=None,
    dispatch: bool = True,
) -> Dict[str, Any]:
    """Create a pending Task node and enqueue RunAgentTaskCommand.

    This is the single choke point for producers (CLI, MCP tools, scheduler).
    """
    if task_queue is None:
        from sparky.task_queue import create_task_queue

        task_queue = await create_task_queue()

    task = await task_queue.add_task(
        instruction=instruction,
        metadata=metadata,
        depends_on=depends_on,
        allow_duplicates=allow_duplicates,
        chat_id=chat_id,
    )

    # Duplicate detection may return an already in-progress/pending task —
    # still re-dispatch pending ones so a lost Redis message can be recovered.
    if dispatch and task.get("status") == "pending":
        try:
            await dispatch_run_agent_task(task["id"])
        except Exception as e:
            # Task is durable in KG; worker reconcile will re-dispatch later.
            logger.error(
                "Task %s saved but command-bus dispatch failed (will reconcile): %s",
                task["id"],
                e,
                exc_info=True,
            )

    return task


async def dispatch_run_agent_task(task_id: str) -> None:
    """Fire-and-forget RunAgentTaskCommand for an existing task id."""
    from commands.bus import dispatch_async
    from commands.commands import RunAgentTaskCommand

    try:
        await dispatch_async(RunAgentTaskCommand(task_id=task_id), wait=False)
    except Exception as e:
        logger.error(
            "Failed to dispatch RunAgentTask for %s (task remains pending in KG): %s",
            task_id,
            e,
            exc_info=True,
        )
        raise
