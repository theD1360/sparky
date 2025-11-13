"""Tests for the agent CLI commands."""

import pytest
from typer.testing import CliRunner
from unittest.mock import AsyncMock, MagicMock, patch

# Import the CLI app
from cli.agent import agent, tasks


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_task_queue():
    """Create a mock TaskQueue."""
    mock = MagicMock()
    mock.get_task = AsyncMock()
    mock.get_all_tasks = AsyncMock(return_value=[])
    mock.add_task = AsyncMock(return_value={
        "id": "test-id",
        "instruction": "test instruction",
        "status": "pending",
        "metadata": {},
    })
    mock.update_task = AsyncMock(return_value=True)
    mock.delete_task = AsyncMock(return_value=True)
    mock.get_task_stats = AsyncMock(return_value={
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "failed": 0,
        "total": 0,
    })
    return mock


def test_tasks_subcommand_registered(runner):
    """Test that the tasks subcommand is properly registered."""
    result = runner.invoke(agent, ["tasks", "--help"])
    assert result.exit_code == 0
    assert "Manage agent task queue" in result.output


def test_tasks_list_command_exists(runner):
    """Test that the list command exists under tasks."""
    result = runner.invoke(agent, ["tasks", "list", "--help"])
    assert result.exit_code == 0
    assert "List all tasks" in result.output


def test_tasks_add_command_exists(runner):
    """Test that the add command exists under tasks."""
    result = runner.invoke(agent, ["tasks", "add", "--help"])
    assert result.exit_code == 0
    assert "Add a new task" in result.output


def test_tasks_get_command_exists(runner):
    """Test that the get command exists under tasks."""
    result = runner.invoke(agent, ["tasks", "get", "--help"])
    assert result.exit_code == 0
    assert "Get detailed information" in result.output


def test_tasks_update_command_exists(runner):
    """Test that the update command exists under tasks."""
    result = runner.invoke(agent, ["tasks", "update", "--help"])
    assert result.exit_code == 0
    assert "Update one or more fields" in result.output


def test_tasks_delete_command_exists(runner):
    """Test that the delete command exists under tasks."""
    result = runner.invoke(agent, ["tasks", "delete", "--help"])
    assert result.exit_code == 0
    assert "Delete a specific task" in result.output


def test_tasks_clear_command_exists(runner):
    """Test that the clear command exists under tasks."""
    result = runner.invoke(agent, ["tasks", "clear", "--help"])
    assert result.exit_code == 0
    assert "Clear tasks from the queue" in result.output


@patch("cli.agent.create_task_queue")
def test_tasks_add_with_metadata(mock_create_queue, runner, mock_task_queue):
    """Test adding a task with metadata."""
    mock_create_queue.return_value = mock_task_queue
    
    result = runner.invoke(agent, [
        "tasks", "add", "Test task",
        "--metadata", "priority=high",
        "--metadata", "source=test"
    ])
    
    assert result.exit_code == 0
    assert "Added task" in result.output
    mock_task_queue.add_task.assert_called_once()


@patch("cli.agent.create_task_queue")
def test_tasks_list_with_status_filter(mock_create_queue, runner, mock_task_queue):
    """Test listing tasks with status filter."""
    mock_create_queue.return_value = mock_task_queue
    mock_task_queue.get_all_tasks.return_value = [
        {
            "id": "task1",
            "instruction": "Test task",
            "status": "pending",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
    ]
    
    result = runner.invoke(agent, ["tasks", "list", "--status", "pending"])
    
    assert result.exit_code == 0
    mock_task_queue.get_all_tasks.assert_called_once()


@patch("cli.agent.create_task_queue")
def test_tasks_update_status(mock_create_queue, runner, mock_task_queue):
    """Test updating a task status."""
    mock_create_queue.return_value = mock_task_queue
    
    result = runner.invoke(agent, [
        "tasks", "update", "test-id",
        "--status", "completed"
    ])
    
    assert result.exit_code == 0
    mock_task_queue.update_task.assert_called_once()


@patch("cli.agent.create_task_queue")
def test_tasks_delete_with_force(mock_create_queue, runner, mock_task_queue):
    """Test deleting a task with force flag."""
    mock_create_queue.return_value = mock_task_queue
    mock_task_queue.get_task.return_value = {
        "id": "test-id",
        "instruction": "Test task",
        "status": "pending",
    }
    
    result = runner.invoke(agent, [
        "tasks", "delete", "test-id", "--force"
    ])
    
    assert result.exit_code == 0
    mock_task_queue.delete_task.assert_called_once_with("test-id")


def test_tasks_clear_requires_filter(runner):
    """Test that clear command requires at least one filter."""
    result = runner.invoke(agent, ["tasks", "clear"])
    
    # Should fail without filters
    assert result.exit_code != 0
    assert "Must specify at least one filter" in result.output or result.exit_code == 1


def test_tasks_update_requires_field(runner):
    """Test that update command requires at least one field."""
    result = runner.invoke(agent, ["tasks", "update", "test-id"])
    
    # Should fail without any fields to update
    assert result.exit_code != 0


def test_agent_status_command_exists(runner):
    """Test that status command still exists at agent level."""
    result = runner.invoke(agent, ["status", "--help"])
    assert result.exit_code == 0


def test_agent_schedule_command_exists(runner):
    """Test that schedule command still exists at agent level."""
    result = runner.invoke(agent, ["schedule", "--help"])
    assert result.exit_code == 0


def test_agent_stats_command_exists(runner):
    """Test that stats command still exists at agent level."""
    result = runner.invoke(agent, ["stats", "--help"])
    assert result.exit_code == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

