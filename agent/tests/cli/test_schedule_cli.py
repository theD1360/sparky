"""Tests for the schedule CLI commands."""

import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

# Import the CLI app
from cli.agent import agent, schedule


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_scheduled_tasks():
    """Create mock scheduled tasks."""
    return [
        {
            "name": "test_task",
            "interval": "every(1 hour)",
            "prompt": "file(prompts/test.md)",
            "metadata": {"source": "test"},
            "enabled": True,
        },
        {
            "name": "disabled_task",
            "interval": "every(2 hours)",
            "prompt": "Test prompt",
            "metadata": {},
            "enabled": False,
        },
    ]


def test_schedule_subcommand_registered(runner):
    """Test that the schedule subcommand is properly registered."""
    result = runner.invoke(agent, ["schedule", "--help"])
    assert result.exit_code == 0
    assert "Manage scheduled tasks" in result.output


def test_schedule_list_command_exists(runner):
    """Test that the list command exists under schedule."""
    result = runner.invoke(agent, ["schedule", "list", "--help"])
    assert result.exit_code == 0
    assert "List all scheduled tasks" in result.output


def test_schedule_show_command_exists(runner):
    """Test that the show command exists under schedule."""
    result = runner.invoke(agent, ["schedule", "show", "--help"])
    assert result.exit_code == 0
    assert "Show detailed information" in result.output


def test_schedule_run_command_exists(runner):
    """Test that the run command exists under schedule."""
    result = runner.invoke(agent, ["schedule", "run", "--help"])
    assert result.exit_code == 0
    assert "Submit scheduled tasks" in result.output


def test_schedule_add_command_exists(runner):
    """Test that the add command exists under schedule."""
    result = runner.invoke(agent, ["schedule", "add", "--help"])
    assert result.exit_code == 0
    assert "Add a new scheduled task" in result.output


def test_schedule_delete_command_exists(runner):
    """Test that the delete command exists under schedule."""
    result = runner.invoke(agent, ["schedule", "delete", "--help"])
    assert result.exit_code == 0
    assert "Delete a scheduled task" in result.output


def test_schedule_enable_command_exists(runner):
    """Test that the enable command exists under schedule."""
    result = runner.invoke(agent, ["schedule", "enable", "--help"])
    assert result.exit_code == 0
    assert "Enable a scheduled task" in result.output


def test_schedule_disable_command_exists(runner):
    """Test that the disable command exists under schedule."""
    result = runner.invoke(agent, ["schedule", "disable", "--help"])
    assert result.exit_code == 0
    assert "Disable a scheduled task" in result.output


@patch("cli.agent.load_raw_config")
def test_schedule_list(mock_load_config, runner, mock_scheduled_tasks):
    """Test listing scheduled tasks."""
    mock_load_config.return_value = mock_scheduled_tasks
    
    result = runner.invoke(agent, ["schedule", "list"])
    
    assert result.exit_code == 0
    mock_load_config.assert_called_once()


@patch("cli.agent.load_raw_config")
def test_schedule_show(mock_load_config, runner, mock_scheduled_tasks):
    """Test showing a specific scheduled task."""
    mock_load_config.return_value = mock_scheduled_tasks
    
    result = runner.invoke(agent, ["schedule", "show", "test_task"])
    
    assert result.exit_code == 0
    assert "test_task" in result.output
    mock_load_config.assert_called_once()


@patch("cli.agent.load_raw_config")
def test_schedule_show_not_found(mock_load_config, runner, mock_scheduled_tasks):
    """Test showing a non-existent scheduled task."""
    mock_load_config.return_value = mock_scheduled_tasks
    
    result = runner.invoke(agent, ["schedule", "show", "nonexistent"])
    
    assert result.exit_code != 0
    assert "not found" in result.output


@patch("cli.agent.add_scheduled_task")
def test_schedule_add(mock_add, runner):
    """Test adding a scheduled task."""
    mock_add.return_value = True
    
    result = runner.invoke(agent, [
        "schedule", "add", 
        "new_task",
        "every(1 hour)",
        "file(prompts/test.md)",
        "--metadata", "source=test"
    ])
    
    assert result.exit_code == 0
    assert "Added scheduled task" in result.output
    mock_add.assert_called_once()


@patch("cli.agent.add_scheduled_task")
def test_schedule_add_disabled(mock_add, runner):
    """Test adding a disabled scheduled task."""
    mock_add.return_value = True
    
    result = runner.invoke(agent, [
        "schedule", "add",
        "new_task",
        "every(1 hour)",
        "Test prompt",
        "--disabled"
    ])
    
    assert result.exit_code == 0
    # Verify enabled=False was passed
    call_args = mock_add.call_args
    assert call_args.kwargs["enabled"] == False


@patch("cli.agent.load_raw_config")
@patch("cli.agent.delete_scheduled_task")
def test_schedule_delete_with_force(mock_delete, mock_load_config, runner, mock_scheduled_tasks):
    """Test deleting a scheduled task with force flag."""
    mock_load_config.return_value = mock_scheduled_tasks
    mock_delete.return_value = True
    
    result = runner.invoke(agent, [
        "schedule", "delete", "test_task", "--force"
    ])
    
    assert result.exit_code == 0
    assert "Deleted scheduled task" in result.output
    mock_delete.assert_called_once_with("test_task")


@patch("cli.agent.update_scheduled_task")
def test_schedule_enable(mock_update, runner):
    """Test enabling a scheduled task."""
    mock_update.return_value = True
    
    result = runner.invoke(agent, ["schedule", "enable", "test_task"])
    
    assert result.exit_code == 0
    assert "Enabled scheduled task" in result.output
    mock_update.assert_called_once_with("test_task", enabled=True)


@patch("cli.agent.update_scheduled_task")
def test_schedule_disable(mock_update, runner):
    """Test disabling a scheduled task."""
    mock_update.return_value = True
    
    result = runner.invoke(agent, ["schedule", "disable", "test_task"])
    
    assert result.exit_code == 0
    assert "Disabled scheduled task" in result.output
    mock_update.assert_called_once_with("test_task", enabled=False)


@patch("cli.agent.update_scheduled_task")
def test_schedule_enable_not_found(mock_update, runner):
    """Test enabling a non-existent task."""
    mock_update.return_value = False
    
    result = runner.invoke(agent, ["schedule", "enable", "nonexistent"])
    
    assert result.exit_code != 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

