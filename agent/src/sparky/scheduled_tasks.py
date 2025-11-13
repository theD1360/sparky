"""Scheduled tasks configuration and management for Sparky.

This module provides a YAML-based configuration system for scheduling periodic
tasks in the agent loop. Tasks can be scheduled using cycles, time intervals,
or cron expressions.
"""

import re
from datetime import datetime
from logging import getLogger
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from croniter import croniter

logger = getLogger(__name__)


class ScheduledTask:
    """Represents a scheduled task configuration."""

    def __init__(
        self,
        name: str,
        interval: Union[int, str],
        prompt: str,
        metadata: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
    ):
        """Initialize a scheduled task.

        Args:
            name: Unique identifier for the task
            interval: Interval specification (cycles, every(), or cron())
            prompt: Prompt string or file() reference
            metadata: Optional metadata to attach to the task
            enabled: Whether the task is enabled
        """
        self.name = name
        self.interval_spec = interval
        self.prompt_spec = prompt
        self.metadata = metadata or {}
        self.enabled = enabled

        # Parse interval
        self.interval_type, self.interval_value = self._parse_interval(interval)

        # Track last execution time for time-based and cron intervals
        self.last_execution: Optional[datetime] = None

    def _parse_interval(self, interval: Union[int, str]) -> tuple[str, Any]:
        """Parse interval specification into type and value.

        Args:
            interval: Interval specification

        Returns:
            Tuple of (interval_type, interval_value)
        """
        # Plain number = cycles
        if isinstance(interval, int):
            return ("cycles", interval)

        # String-based intervals
        interval_str = str(interval).strip()

        # Check for every() syntax
        every_match = re.match(r"every\((.+)\)", interval_str)
        if every_match:
            time_spec = every_match.group(1).strip()
            seconds = self._parse_time_spec(time_spec)
            return ("time", seconds)

        # Check for cron() syntax
        cron_match = re.match(r"cron\((.+)\)", interval_str)
        if cron_match:
            cron_expr = cron_match.group(1).strip()
            # Validate cron expression
            try:
                croniter(cron_expr)
                return ("cron", cron_expr)
            except Exception as e:
                logger.error("Invalid cron expression '%s': %s", cron_expr, e)
                raise ValueError(f"Invalid cron expression: {cron_expr}") from e

        # Try to parse as plain number string
        try:
            cycles = int(interval_str)
            return ("cycles", cycles)
        except ValueError:
            pass

        raise ValueError(f"Invalid interval specification: {interval}")

    def _parse_time_spec(self, time_spec: str) -> int:
        """Parse a time specification into seconds.

        Args:
            time_spec: Time specification like "1 minute", "2 hours", "30 seconds"

        Returns:
            Number of seconds
        """
        # Match pattern like "1 minute", "2 hours", etc.
        match = re.match(r"(\d+)\s*(second|minute|hour|day)s?", time_spec.lower())
        if not match:
            raise ValueError(f"Invalid time specification: {time_spec}")

        amount = int(match.group(1))
        unit = match.group(2)

        multipliers = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400,
        }

        return amount * multipliers[unit]

    def should_run(
        self, cycle_count: int, current_time: Optional[datetime] = None
    ) -> bool:
        """Check if the task should run based on its interval.

        Args:
            cycle_count: Current cycle count
            current_time: Current time (defaults to now)

        Returns:
            True if the task should run
        """
        if not self.enabled:
            return False

        if current_time is None:
            current_time = datetime.now()

        if self.interval_type == "cycles":
            # Simple modulo check for cycle-based intervals
            return cycle_count % self.interval_value == 0

        if self.interval_type == "time":
            # Check if enough time has passed since last execution
            if self.last_execution is None:
                return True
            elapsed = (current_time - self.last_execution).total_seconds()
            return elapsed >= self.interval_value

        if self.interval_type == "cron":
            # Check if cron schedule indicates we should run
            if self.last_execution is None:
                # First run - check if we're past the schedule
                cron = croniter(self.interval_value, current_time)
                prev_time = cron.get_prev(datetime)
                # Run if the previous scheduled time was less than a minute ago
                # This prevents running immediately on startup for past schedules
                elapsed = (current_time - prev_time).total_seconds()
                return elapsed < 60

            # Check if we've passed a scheduled time since last execution
            cron = croniter(self.interval_value, self.last_execution)
            next_time = cron.get_next(datetime)
            return current_time >= next_time

        return False

    def mark_executed(self, current_time: Optional[datetime] = None):
        """Mark the task as executed.

        Args:
            current_time: Execution time (defaults to now)
        """
        if current_time is None:
            current_time = datetime.now()
        self.last_execution = current_time

    def resolve_prompt(self, base_path: Optional[Path] = None) -> str:
        """Resolve the prompt specification to actual prompt text.

        Args:
            base_path: Base path for resolving relative file paths

        Returns:
            The resolved prompt text

        Raises:
            ValueError: If the prompt is empty or cannot be resolved
        """
        prompt = self.prompt_spec.strip()

        # Check for file() syntax
        file_match = re.match(r"file\((.+)\)", prompt)
        if file_match:
            file_path = file_match.group(1).strip()

            # Resolve relative to base_path if provided
            if base_path:
                full_path = base_path / file_path
            else:
                full_path = Path(file_path)

            # Read the file
            try:
                content = full_path.read_text(encoding="utf-8").strip()
                if not content:
                    raise ValueError(f"Prompt file is empty: {full_path}")
                return content
            except Exception as e:
                logger.error("Error reading prompt file '%s': %s", full_path, e)
                raise ValueError(f"Failed to read prompt file: {full_path}") from e

        # Plain string prompt - validate it's not empty
        if not prompt:
            raise ValueError(f"Task '{self.name}' has empty prompt specification")

        return prompt


def get_config_path(config_path: Optional[Path] = None) -> Path:
    """Get the path to the scheduled tasks configuration file.

    Args:
        config_path: Optional explicit path to config file

    Returns:
        Path to the configuration file
    """
    if config_path is None:
        # Default to project root
        config_path = Path(__file__).parent.parent.parent / "scheduled_tasks.yaml"
    return config_path


def load_scheduled_tasks(config_path: Optional[Path] = None) -> List[ScheduledTask]:
    """Load scheduled tasks from YAML configuration.

    Args:
        config_path: Path to the YAML config file (defaults to scheduled_tasks.yaml
                    in the project root)

    Returns:
        List of ScheduledTask objects
    """
    config_path = get_config_path(config_path)

    if not config_path.exists():
        logger.warning("Scheduled tasks config not found: %s", config_path)
        return []

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config or "scheduled_tasks" not in config:
            logger.warning("No 'scheduled_tasks' found in config")
            return []

        tasks = []
        for task_config in config["scheduled_tasks"]:
            try:
                # Disable curation, metacognition, and alignment tasks
                if task_config.get("metadata", {}).get("scheduled_task_name") in ["curation", "metacognition", "alignment"]:
                    task_config["enabled"] = False

                task = ScheduledTask(
                    name=task_config["name"],
                    interval=task_config["interval"],
                    prompt=task_config["prompt"],
                    metadata=task_config.get("metadata"),
                    enabled=task_config.get("enabled", True),
                )
                tasks.append(task)
                logger.info(
                    "Loaded scheduled task '%s' (%s: %s)",
                    task.name,
                    task.interval_type,
                    task.interval_value,
                )
            except (KeyError, ValueError) as e:
                logger.error(
                    "Error loading task '%s': %s",
                    task_config.get("name", "unknown"),
                    e,
                    exc_info=True,
                )

        logger.info("Loaded %d scheduled tasks from %s", len(tasks), config_path)
        return tasks

    except (OSError, yaml.YAMLError) as e:
        logger.error("Error loading scheduled tasks config: %s", e, exc_info=True)
        return []


def save_scheduled_tasks(tasks: List[Dict[str, Any]], config_path: Optional[Path] = None) -> bool:
    """Save scheduled tasks to YAML configuration.

    Args:
        tasks: List of task dictionaries to save
        config_path: Path to the YAML config file

    Returns:
        True if successful, False otherwise
    """
    config_path = get_config_path(config_path)

    try:
        config = {"scheduled_tasks": tasks}
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
        logger.info("Saved %d scheduled tasks to %s", len(tasks), config_path)
        return True
    except (OSError, yaml.YAMLError) as e:
        logger.error("Error saving scheduled tasks config: %s", e, exc_info=True)
        return False


def load_raw_config(config_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load raw task configurations from YAML.

    Args:
        config_path: Path to the YAML config file

    Returns:
        List of raw task configuration dictionaries
    """
    config_path = get_config_path(config_path)

    if not config_path.exists():
        logger.warning("Scheduled tasks config not found: %s", config_path)
        return []

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config or "scheduled_tasks" not in config:
            return []

        return config["scheduled_tasks"]
    except (OSError, yaml.YAMLError) as e:
        logger.error("Error loading scheduled tasks config: %s", e, exc_info=True)
        return []


def add_scheduled_task(
    name: str,
    interval: str,
    prompt: str,
    metadata: Optional[Dict[str, Any]] = None,
    enabled: bool = True,
    config_path: Optional[Path] = None,
) -> bool:
    """Add a new scheduled task to the configuration.

    Args:
        name: Unique name for the task
        interval: Interval specification
        prompt: Prompt text or file() reference
        metadata: Optional metadata dictionary
        enabled: Whether the task is enabled
        config_path: Path to the YAML config file

    Returns:
        True if successful, False otherwise
    """
    # Validate inputs by creating a ScheduledTask
    try:
        ScheduledTask(name, interval, prompt, metadata, enabled)
    except ValueError as e:
        logger.error("Invalid task configuration: %s", e)
        return False

    # Load existing tasks
    tasks = load_raw_config(config_path)

    # Check for duplicate name
    if any(t.get("name") == name for t in tasks):
        logger.error("Task with name '%s' already exists", name)
        return False

    # Add new task
    new_task = {
        "name": name,
        "interval": interval,
        "prompt": prompt,
        "metadata": metadata or {},
        "enabled": enabled,
    }
    tasks.append(new_task)

    return save_scheduled_tasks(tasks, config_path)


def update_scheduled_task(
    name: str,
    enabled: Optional[bool] = None,
    interval: Optional[str] = None,
    prompt: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    config_path: Optional[Path] = None,
) -> bool:
    """Update an existing scheduled task.

    Args:
        name: Name of the task to update
        enabled: Optional new enabled status
        interval: Optional new interval
        prompt: Optional new prompt
        metadata: Optional new metadata (will replace existing)
        config_path: Path to the YAML config file

    Returns:
        True if successful, False otherwise
    """
    tasks = load_raw_config(config_path)

    # Find and update the task
    task_found = False
    for task in tasks:
        if task.get("name") == name:
            task_found = True
            if enabled is not None:
                task["enabled"] = enabled
            if interval is not None:
                task["interval"] = interval
            if prompt is not None:
                task["prompt"] = prompt
            if metadata is not None:
                task["metadata"] = metadata
            break

    if not task_found:
        logger.error("Task '%s' not found", name)
        return False

    return save_scheduled_tasks(tasks, config_path)


def delete_scheduled_task(name: str, config_path: Optional[Path] = None) -> bool:
    """Delete a scheduled task from the configuration.

    Args:
        name: Name of the task to delete
        config_path: Path to the YAML config file

    Returns:
        True if successful, False otherwise
    """
    tasks = load_raw_config(config_path)

    # Filter out the task to delete
    original_count = len(tasks)
    tasks = [t for t in tasks if t.get("name") != name]

    if len(tasks) == original_count:
        logger.error("Task '%s' not found", name)
        return False

    return save_scheduled_tasks(tasks, config_path)
