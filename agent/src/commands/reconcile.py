"""Reconcile pending KG tasks that may have lost their Redis command."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


async def reconcile_pending_tasks(
    task_queue,
    min_age_seconds: int = 30,
    limit: int = 50,
) -> int:
    """Re-dispatch pending tasks older than min_age_seconds.

    Returns:
        Number of tasks re-dispatched
    """
    from commands.enqueue import dispatch_run_agent_task

    tasks = await task_queue.get_all_tasks()
    now = datetime.now(timezone.utc)
    dispatched = 0

    for task in tasks:
        if dispatched >= limit:
            break
        if task.get("status") != "pending":
            continue

        created_at = task.get("created_at") or ""
        age = _age_seconds(created_at, now)
        if age is not None and age < min_age_seconds:
            continue

        task_id = task["id"]
        try:
            await dispatch_run_agent_task(task_id)
            dispatched += 1
            logger.info("Reconcile: re-dispatched pending task %s", task_id)
        except Exception as e:
            logger.warning("Reconcile: failed to dispatch %s: %s", task_id, e)

    return dispatched


def _age_seconds(created_at: str, now: datetime) -> Optional[float]:
    if not created_at:
        return None
    try:
        # Handle Z suffix and naive ISO
        ts = created_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).total_seconds()
    except Exception:
        return None
