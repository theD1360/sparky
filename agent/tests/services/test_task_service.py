# tests/test_task_service.py

import pytest
from unittest import mock
import re
import asyncio

from services.task_service import TaskService

@pytest.fixture
async def mock_task_queue():
    """Create a mock TaskQueue."""
    mock_queue = mock.AsyncMock()
    mock_queue.add_task.return_value = {"id": "new_task_id", "instruction": "Test instruction"}
    mock_queue.get_task.return_value = {"id": "test_task", "instruction": "Test instruction"}
    mock_queue.update_task_status.return_value = True
    mock_queue.delete_task.return_value = True
    return mock_queue

@pytest.fixture
def task_service(mock_task_queue):
    """Create a TaskService instance with the mock task queue."""
    return TaskService(task_queue=mock_task_queue)

@pytest.mark.asyncio
async def test_create_task_success(task_service, mock_task_queue):
    """Test creating a task successfully."""
    instruction = "Test instruction"
    metadata = {"key": "value"}
    depends_on = ["task1", "task2"]

    created_task = await task_service.create_task(
        instruction=instruction, metadata=metadata, depends_on=depends_on
    )

    mock_task_queue.add_task.assert_called_with(instruction=instruction, metadata=metadata, depends_on=depends_on, allow_duplicates=False)
    assert created_task == {"id": "new_task_id", "instruction": "Test instruction"}


@pytest.mark.asyncio
async def test_get_task_success(task_service, mock_task_queue):
    """Test getting a task successfully."""
    task_id = "test_task"

    task = await task_service.get_task(task_id=task_id)

    assert mock_task_queue.get_task.await_args == mock.call(task_id=task_id)
    assert task == {"id": "test_task", "instruction": "Test instruction"}

@pytest.mark.asyncio
async def test_update_task_status_success(task_service, mock_task_queue):
    """Test updating a task status successfully."""
    task_id = "test_task"
    status = "completed"
    response = "Task completed successfully"

    success = await task_service.update_task_status(task_id=task_id, status=status, response=response)

    assert mock_task_queue.update_task_status.assert_called_with(task_id=task_id, status=status, response=response, error=None)
    assert success is True

@pytest.mark.asyncio
async def test_delete_task_success(task_service, mock_task_queue):
    """Test deleting a task successfully."""
    task_id = "test_task"

    success = await task_service.delete_task(task_id=task_id)

    assert mock_task_queue.delete_task.await_args ==  mock.call(task_id=task_id)
    assert success is True