"""Tests for task chat reuse functionality with TaskService."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from services import TaskService


@pytest.fixture
def mock_repository():
    """Create a mock knowledge repository."""
    mock_repo = MagicMock()
    return mock_repo


@pytest.fixture
def mock_task_queue(mock_repository):
    """Create a mock task queue."""
    mock_queue = MagicMock()
    mock_queue.repository = mock_repository
    mock_queue.add_task = AsyncMock()
    mock_queue.get_task = AsyncMock()
    mock_queue.update_task_status = AsyncMock()
    mock_queue.delete_task = AsyncMock()
    mock_queue.get_all_tasks = AsyncMock()
    mock_queue.get_next_pending_task = AsyncMock()
    mock_queue.search_tasks = AsyncMock()
    mock_queue.get_task_stats = MagicMock(return_value={})
    mock_queue.get_last_scheduled_task_execution = AsyncMock()
    return mock_queue


@pytest.fixture
def task_service(mock_task_queue):
    """Create a TaskService instance with mock dependencies."""
    return TaskService(task_queue=mock_task_queue)


async def test_task_service_initialization(task_service):
    """Test that TaskService initializes with proper storage."""
    assert task_service is not None
    assert hasattr(task_service, 'scheduled_task_chats')
    assert isinstance(task_service.scheduled_task_chats, dict)
    assert len(task_service.scheduled_task_chats) == 0
    assert hasattr(task_service, 'bot_instances')
    assert isinstance(task_service.bot_instances, dict)
    assert len(task_service.bot_instances) == 0


async def test_create_task(task_service, mock_task_queue):
    """Test creating a task through TaskService."""
    # Setup mock return value
    mock_task_queue.add_task.return_value = {
        "id": "task-123",
        "instruction": "Test task",
        "metadata": {"scheduled_task_name": "test", "source": "test"},
        "status": "pending"
    }
    
    # Create task
    task = await task_service.create_task(
        "Test task",
        metadata={"scheduled_task_name": "test", "source": "test"}
    )
    
    # Verify
    assert task["id"] == "task-123"
    assert task["instruction"] == "Test task"
    mock_task_queue.add_task.assert_called_once()


async def test_get_task(task_service, mock_task_queue):
    """Test getting a task through TaskService."""
    # Setup mock
    mock_task_queue.get_task.return_value = {
        "id": "task-123",
        "instruction": "Test task",
        "status": "completed"
    }
    
    # Get task
    task = await task_service.get_task("task-123")
    
    # Verify
    assert task["id"] == "task-123"
    mock_task_queue.get_task.assert_called_once_with("task-123")


async def test_update_task_status(task_service, mock_task_queue):
    """Test updating task status through TaskService."""
    mock_task_queue.update_task_status.return_value = True
    
    result = await task_service.update_task_status("task-123", "completed", response="Done")
    
    assert result is True
    mock_task_queue.update_task_status.assert_called_once_with(
        task_id="task-123",
        status="completed",
        response="Done",
        error=None
    )


def test_is_scheduled_task(task_service):
    """Test identification of scheduled tasks vs manual tasks."""
    # Scheduled task with scheduled_task_name
    scheduled_task = {
        "id": "task-123",
        "instruction": "Test instruction",
        "metadata": {
            "scheduled_task_name": "smart_maintenance",
            "source": "smart_maintenance"
        }
    }
    
    assert task_service.is_scheduled_task(scheduled_task) is True
    assert task_service.get_scheduled_task_name(scheduled_task) == "smart_maintenance"
    
    # Manual task without scheduled_task_name
    manual_task = {
        "id": "task-456",
        "instruction": "Test manual task",
        "metadata": {
            "source": "manual"
        }
    }
    
    assert task_service.is_scheduled_task(manual_task) is False
    assert task_service.get_scheduled_task_name(manual_task) is None


def test_get_task_chat_name(task_service):
    """Test that chat names are generated correctly based on task type."""
    # Scheduled task naming
    scheduled_task = {
        "id": "task-123",
        "metadata": {
            "scheduled_task_name": "smart_maintenance"
        }
    }
    
    chat_name = task_service.get_task_chat_name(scheduled_task)
    assert chat_name == "Task: smart_maintenance"
    
    # Manual task naming
    manual_task = {
        "id": "task-456",
        "metadata": {}
    }
    
    chat_name = task_service.get_task_chat_name(manual_task)
    assert chat_name == "Task: task-456"


def test_get_or_create_task_chat_new(task_service):
    """Test creating a new chat for a task."""
    task = {
        "id": "task-123",
        "metadata": {
            "scheduled_task_name": "smart_maintenance"
        }
    }
    
    mock_bot = MagicMock()
    
    # First call should create new chat
    chat_id, bot, is_reused = task_service.get_or_create_task_chat(task, mock_bot)
    
    assert chat_id is not None
    assert bot == mock_bot
    assert is_reused is False
    assert "smart_maintenance" in task_service.scheduled_task_chats
    assert task_service.scheduled_task_chats["smart_maintenance"] == (chat_id, mock_bot)


def test_get_or_create_task_chat_reuse(task_service):
    """Test reusing existing chat for scheduled task."""
    task = {
        "id": "task-123",
        "metadata": {
            "scheduled_task_name": "smart_maintenance"
        }
    }
    
    mock_bot = MagicMock()
    
    # First call creates chat
    chat_id_1, bot_1, is_reused_1 = task_service.get_or_create_task_chat(task, mock_bot)
    assert is_reused_1 is False
    
    # Second call reuses chat
    chat_id_2, bot_2, is_reused_2 = task_service.get_or_create_task_chat(task)
    
    assert chat_id_2 == chat_id_1
    assert bot_2 == bot_1
    assert is_reused_2 is True


def test_get_or_create_task_chat_manual_always_new(task_service):
    """Test that manual tasks always create new chats."""
    manual_task_1 = {
        "id": "task-456",
        "metadata": {"source": "manual"}
    }
    
    manual_task_2 = {
        "id": "task-789",
        "metadata": {"source": "manual"}
    }
    
    mock_bot_1 = MagicMock()
    mock_bot_2 = MagicMock()
    
    # First manual task
    chat_id_1, bot_1, is_reused_1 = task_service.get_or_create_task_chat(manual_task_1, mock_bot_1)
    assert is_reused_1 is False
    
    # Second manual task should create new chat
    chat_id_2, bot_2, is_reused_2 = task_service.get_or_create_task_chat(manual_task_2, mock_bot_2)
    
    assert chat_id_2 != chat_id_1
    assert bot_2 == mock_bot_2
    assert is_reused_2 is False


def test_get_scheduled_task_chat_stats(task_service):
    """Test getting chat statistics."""
    # Add some scheduled task chats
    task_service.scheduled_task_chats["smart_maintenance"] = ("chat-1", MagicMock())
    task_service.scheduled_task_chats["integrated_reflection"] = ("chat-2", MagicMock())
    task_service.bot_instances["chat-1"] = MagicMock()
    task_service.bot_instances["chat-2"] = MagicMock()
    task_service.bot_instances["chat-3"] = MagicMock()  # Manual task chat
    
    stats = task_service.get_scheduled_task_chat_stats()
    
    assert stats["scheduled_chats"] == 2
    assert stats["total_bot_instances"] == 3
    assert "smart_maintenance" in stats["scheduled_task_names"]
    assert "integrated_reflection" in stats["scheduled_task_names"]


def test_remove_scheduled_task_chat(task_service):
    """Test removing a scheduled task's chat."""
    mock_bot = MagicMock()
    task_service.scheduled_task_chats["test_task"] = ("chat-123", mock_bot)
    task_service.bot_instances["chat-123"] = mock_bot
    
    # Remove the chat
    result = task_service.remove_scheduled_task_chat("test_task")
    
    assert result is True
    assert "test_task" not in task_service.scheduled_task_chats
    assert "chat-123" not in task_service.bot_instances
    
    # Try to remove non-existent chat
    result = task_service.remove_scheduled_task_chat("non_existent")
    assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

