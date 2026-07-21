"""Tests for command-bus enqueue, claim, and RunAgentTask handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from commands.commands import RunAgentTaskCommand
from commands.handlers.run_agent_task import RunAgentTaskHandler, set_executor


@pytest.mark.asyncio
async def test_enqueue_agent_task_persists_and_dispatches():
    from commands.enqueue import enqueue_agent_task

    mock_queue = MagicMock()
    mock_queue.add_task = AsyncMock(
        return_value={
            "id": "task-1",
            "instruction": "do thing",
            "status": "pending",
            "metadata": {},
        }
    )

    with patch(
        "commands.enqueue.dispatch_run_agent_task", new_callable=AsyncMock
    ) as mock_dispatch:
        task = await enqueue_agent_task(
            instruction="do thing",
            task_queue=mock_queue,
            dispatch=True,
        )

    assert task["id"] == "task-1"
    mock_queue.add_task.assert_awaited_once()
    mock_dispatch.assert_awaited_once_with("task-1")


@pytest.mark.asyncio
async def test_enqueue_skips_dispatch_when_not_pending():
    from commands.enqueue import enqueue_agent_task

    mock_queue = MagicMock()
    mock_queue.add_task = AsyncMock(
        return_value={
            "id": "task-dup",
            "instruction": "do thing",
            "status": "in_progress",
            "metadata": {},
        }
    )

    with patch(
        "commands.enqueue.dispatch_run_agent_task", new_callable=AsyncMock
    ) as mock_dispatch:
        task = await enqueue_agent_task(
            instruction="do thing",
            task_queue=mock_queue,
            dispatch=True,
        )

    assert task["status"] == "in_progress"
    mock_dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_task_pending_to_in_progress():
    from sparky.task_queue import TaskQueue

    repo = MagicMock()
    queue = TaskQueue(repo)

    pending = {
        "id": "abc",
        "instruction": "x",
        "status": "pending",
        "metadata": {},
        "created_at": "",
        "updated_at": "",
        "response": None,
        "error": None,
    }
    queue.get_task = AsyncMock(return_value=dict(pending))
    queue._save_task = AsyncMock()

    claimed = await queue.claim_task("abc")
    assert claimed is not None
    assert claimed["status"] == "in_progress"
    queue._save_task.assert_awaited_once()


@pytest.mark.asyncio
async def test_claim_task_skips_non_pending():
    from sparky.task_queue import TaskQueue

    queue = TaskQueue(MagicMock())
    queue.get_task = AsyncMock(
        return_value={"id": "abc", "status": "completed", "instruction": "x"}
    )
    queue._save_task = AsyncMock()

    assert await queue.claim_task("abc") is None
    queue._save_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_handler_skips_completed_task():
    executor = MagicMock()
    executor.task_queue = MagicMock()
    executor.task_queue.get_task = AsyncMock(
        return_value={"id": "t1", "status": "completed", "instruction": "done"}
    )
    executor.task_queue.claim_task = AsyncMock()
    executor.execute = AsyncMock()
    set_executor(executor)

    handler = RunAgentTaskHandler()
    result = await handler.process(RunAgentTaskCommand(task_id="t1"))

    assert result["status"] == "skipped"
    assert result["reason"] == "completed"
    executor.task_queue.claim_task.assert_not_awaited()
    executor.execute.assert_not_awaited()
    set_executor(None)


@pytest.mark.asyncio
async def test_handler_claims_and_executes():
    executor = MagicMock()
    executor.task_queue = MagicMock()
    executor.task_queue.get_task = AsyncMock(
        return_value={"id": "t2", "status": "pending", "instruction": "go"}
    )
    claimed = {"id": "t2", "status": "in_progress", "instruction": "go"}
    executor.task_queue.claim_task = AsyncMock(return_value=claimed)
    executor.execute = AsyncMock(
        return_value={"status": "completed", "response": "ok"}
    )
    set_executor(executor)

    handler = RunAgentTaskHandler()
    result = await handler.process(RunAgentTaskCommand(task_id="t2"))

    assert result["status"] == "completed"
    assert result["task_id"] == "t2"
    executor.task_queue.claim_task.assert_awaited_once_with("t2")
    executor.execute.assert_awaited_once_with(claimed)
    set_executor(None)


@pytest.mark.asyncio
async def test_handler_marks_path_when_executor_fails():
    executor = MagicMock()
    executor.task_queue = MagicMock()
    executor.task_queue.get_task = AsyncMock(
        return_value={"id": "t3", "status": "pending", "instruction": "go"}
    )
    claimed = {"id": "t3", "status": "in_progress", "instruction": "go"}
    executor.task_queue.claim_task = AsyncMock(return_value=claimed)
    executor.execute = AsyncMock(
        return_value={"status": "failed", "error": "boom"}
    )
    set_executor(executor)

    handler = RunAgentTaskHandler()
    result = await handler.process(RunAgentTaskCommand(task_id="t3"))

    assert result["status"] == "failed"
    assert result["error"] == "boom"
    set_executor(None)


@pytest.mark.asyncio
async def test_handler_requires_executor():
    set_executor(None)
    handler = RunAgentTaskHandler()
    with pytest.raises(RuntimeError, match="AgentTaskExecutor not initialized"):
        await handler.process(RunAgentTaskCommand(task_id="x"))
