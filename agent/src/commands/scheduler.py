"""Scheduled-task ticker for the agent worker."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


async def tick_scheduled_tasks(
    task_queue,
    scheduled_tasks: List[Any],
    cycle_count: int,
    base_path: Optional[Path] = None,
) -> int:
    """Check due scheduled tasks and enqueue them via the command bus.

    Returns:
        Number of tasks enqueued this tick
    """
    if not scheduled_tasks:
        return 0

    from commands.enqueue import enqueue_agent_task

    if base_path is None:
        # agent/ directory (parent of src/)
        base_path = Path(__file__).resolve().parents[2]

    current_time = datetime.now()
    enqueued = 0

    for scheduled_task in scheduled_tasks:
        if not scheduled_task.should_run(cycle_count, current_time):
            continue

        scheduled_task_name = scheduled_task.metadata.get(
            "scheduled_task_name", scheduled_task.name
        )
        last_execution = await task_queue.get_last_scheduled_task_execution(
            scheduled_task_name
        )

        should_add = False
        if last_execution is None:
            should_add = True
            logger.info(
                "Scheduled task '%s' has never run, will add", scheduled_task.name
            )
        else:
            elapsed = (current_time - last_execution).total_seconds()
            if scheduled_task.interval_type == "time":
                should_add = elapsed >= scheduled_task.interval_value
            elif scheduled_task.interval_type == "cron":
                from croniter import croniter

                cron = croniter(scheduled_task.interval_value, last_execution)
                next_time = cron.get_next(datetime)
                should_add = current_time >= next_time
            elif scheduled_task.interval_type == "cycles":
                should_add = True

        if not should_add:
            continue

        try:
            prompt = scheduled_task.resolve_prompt(base_path)
            await enqueue_agent_task(
                instruction=prompt,
                metadata={
                    "scheduled_task_name": scheduled_task.name,
                    **scheduled_task.metadata,
                },
                allow_duplicates=True,
                task_queue=task_queue,
            )
            scheduled_task.mark_executed(current_time)
            enqueued += 1
            logger.info("Scheduled task '%s' enqueued", scheduled_task.name)
        except Exception as e:
            logger.error(
                "Error enqueueing scheduled task '%s': %s",
                scheduled_task.name,
                e,
                exc_info=True,
            )

    return enqueued
