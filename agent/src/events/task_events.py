"""Event names for task queue operations."""


class TaskEvents:
    """Event names for task queue operations."""

    TASK_ADDED = "task:added"
    TASK_AVAILABLE = "task:available"
    TASK_STARTED = "task:started"
    TASK_COMPLETED = "task:completed"
    TASK_FAILED = "task:failed"
    TASK_STATUS_CHANGED = "task:status_changed"

