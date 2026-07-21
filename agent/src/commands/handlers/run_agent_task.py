"""RunAgentTask command handler."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from command_bus import CommandHandler

from commands.commands import RunAgentTaskCommand

logger = logging.getLogger(__name__)

# Set by the worker process after toolchain bootstrap
_executor = None


def set_executor(executor) -> None:
    """Attach the shared AgentTaskExecutor used by this process."""
    global _executor
    _executor = executor


def get_executor():
    return _executor


class RunAgentTaskHandler(CommandHandler):
    """Claim a pending Task and execute it via AgentTaskExecutor."""

    async def process(self, message: RunAgentTaskCommand) -> Dict[str, Any]:
        task_id = message.task_id
        executor = get_executor()
        if executor is None:
            raise RuntimeError(
                "AgentTaskExecutor not initialized in worker; cannot run task"
            )

        task_queue = executor.task_queue
        task = await task_queue.get_task(task_id)
        if not task:
            logger.warning("RunAgentTask: task %s not found", task_id)
            return {"status": "skipped", "reason": "not_found", "task_id": task_id}

        status = task.get("status")
        if status in ("completed", "failed"):
            logger.info(
                "RunAgentTask: task %s already %s, skipping", task_id, status
            )
            return {"status": "skipped", "reason": status, "task_id": task_id}

        if status == "in_progress":
            logger.info(
                "RunAgentTask: task %s already in_progress, skipping redelivery",
                task_id,
            )
            return {"status": "skipped", "reason": "in_progress", "task_id": task_id}

        claimed = await task_queue.claim_task(task_id)
        if not claimed:
            logger.info(
                "RunAgentTask: could not claim task %s (race), skipping", task_id
            )
            return {"status": "skipped", "reason": "claim_failed", "task_id": task_id}

        result = await executor.execute(claimed)
        return {"task_id": task_id, **result}
