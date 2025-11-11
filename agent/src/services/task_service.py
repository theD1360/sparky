"""Task service for handling task operations and chat management.

Handles task CRUD operations, scheduled task chat lifecycle, and task execution coordination.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from uuid import uuid4

if TYPE_CHECKING:
    from sparky.task_queue import TaskQueue
    from database.repository import KnowledgeRepository

logger = logging.getLogger(__name__)


class TaskService:
    """Service for managing tasks and their associated chats.

    Provides high-level task operations, scheduled task chat reuse,
    and coordination between tasks and their execution contexts.
    """

    def __init__(
        self,
        task_queue: "TaskQueue",
        repository: Optional["KnowledgeRepository"] = None,
    ):
        """Initialize the task service.

        Args:
            task_queue: TaskQueue instance for low-level task operations
            repository: Optional knowledge graph repository instance
        """
        self.task_queue = task_queue
        self.repository = repository or task_queue.repository

        # Storage for persistent chats per scheduled task
        # Maps scheduled_task_name -> (chat_id, bot_instance)
        self.scheduled_task_chats: Dict[str, Tuple[str, Any]] = {}

        # Storage for all bot instances by chat_id
        self.bot_instances: Dict[str, Any] = {}

    # ===========================
    # Task CRUD Operations
    # ===========================

    async def create_task(
        self,
        instruction: str,
        metadata: Optional[Dict[str, Any]] = None,
        depends_on: Optional[List[str]] = None,
        allow_duplicates: bool = False,
    ) -> Dict[str, Any]:
        """Create a new task.

        Args:
            instruction: Natural language instruction for the task
            metadata: Optional metadata about the task
            depends_on: Optional list of task IDs this task depends on
            allow_duplicates: If False, prevents duplicate tasks

        Returns:
            The newly created task dictionary
        """
        return await self.task_queue.add_task(
            instruction=instruction,
            metadata=metadata,
            depends_on=depends_on,
            allow_duplicates=allow_duplicates,
        )

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID.

        Args:
            task_id: The task ID

        Returns:
            Task dictionary or None if not found
        """
        return await self.task_queue.get_task(task_id)

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        response: Optional[str] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update a task's status.

        Args:
            task_id: The task ID
            status: New status ('pending', 'in_progress', 'completed', 'failed')
            response: Optional response for completed tasks
            error: Optional error message for failed tasks

        Returns:
            True if successful, False otherwise
        """
        return await self.task_queue.update_task_status(
            task_id=task_id,
            status=status,
            response=response,
            error=error,
        )

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task.

        Args:
            task_id: The task ID

        Returns:
            True if successful, False otherwise
        """
        return await self.task_queue.delete_task(task_id)

    async def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks.

        Returns:
            List of task dictionaries
        """
        return await self.task_queue.get_all_tasks()

    async def get_next_pending_task(self) -> Optional[Dict[str, Any]]:
        """Get the next pending task and mark it as in_progress.

        Returns:
            Task dictionary or None if no pending tasks
        """
        return await self.task_queue.get_next_pending_task()

    async def search_tasks(
        self,
        query: str,
        status_filter: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Search for tasks by instruction text.

        Args:
            query: Search query to match against task instructions
            status_filter: Optional status filter
            limit: Optional limit on number of results

        Returns:
            List of matching task dictionaries
        """
        return await self.task_queue.search_tasks(
            query=query,
            status_filter=status_filter,
            limit=limit,
        )

    async def get_task_stats(self) -> Dict[str, int]:
        """Get task statistics.

        Returns:
            Dictionary with task counts by status
        """
        return self.task_queue.get_task_stats()

    # ===========================
    # Scheduled Task Management
    # ===========================

    def is_scheduled_task(self, task: Dict[str, Any]) -> bool:
        """Check if a task is a scheduled task.

        Args:
            task: Task dictionary

        Returns:
            True if the task has a scheduled_task_name in metadata
        """
        metadata = task.get("metadata", {})
        return metadata.get("scheduled_task_name") is not None

    def get_scheduled_task_name(self, task: Dict[str, Any]) -> Optional[str]:
        """Get the scheduled task name from a task.

        Args:
            task: Task dictionary

        Returns:
            Scheduled task name or None if not a scheduled task
        """
        metadata = task.get("metadata", {})
        return metadata.get("scheduled_task_name")

    async def get_last_scheduled_task_execution(
        self, scheduled_task_name: str
    ) -> Optional[datetime]:
        """Get the creation time of the last task for a scheduled task name.

        Args:
            scheduled_task_name: The name of the scheduled task

        Returns:
            The datetime of the last task creation, or None if no task found
        """
        return await self.task_queue.get_last_scheduled_task_execution(
            scheduled_task_name
        )

    # ===========================
    # Chat Management for Tasks
    # ===========================

    def get_or_create_task_chat(
        self, task: Dict[str, Any], bot_instance: Any = None
    ) -> Tuple[str, Optional[Any], bool]:
        """Get or create a chat for a task.

        For scheduled tasks, reuses existing chat if available.
        For manual tasks, always creates a new chat.

        Args:
            task: Task dictionary
            bot_instance: Optional bot instance (required if creating new chat)

        Returns:
            Tuple of (chat_id, bot_instance, is_reused)
        """
        scheduled_task_name = self.get_scheduled_task_name(task)

        # Check if we should reuse an existing chat
        if scheduled_task_name and scheduled_task_name in self.scheduled_task_chats:
            chat_id, bot = self.scheduled_task_chats[scheduled_task_name]
            logger.info(
                f"Reusing existing chat {chat_id} for scheduled task '{scheduled_task_name}'"
            )
            return chat_id, bot, True

        # Create new chat
        chat_id = str(uuid4())
        logger.info(f"Creating new chat {chat_id} for task {task['id']}")

        # Store the chat for scheduled tasks
        if scheduled_task_name and bot_instance:
            self.scheduled_task_chats[scheduled_task_name] = (chat_id, bot_instance)
            logger.info(
                f"Stored chat {chat_id} for scheduled task '{scheduled_task_name}' for future reuse"
            )

        # Store in bot_instances
        if bot_instance:
            self.bot_instances[chat_id] = bot_instance

        return chat_id, bot_instance, False

    def get_task_chat_name(self, task: Dict[str, Any]) -> str:
        """Get the chat name for a task.

        Args:
            task: Task dictionary

        Returns:
            Chat name string
        """
        scheduled_task_name = self.get_scheduled_task_name(task)
        if scheduled_task_name:
            return f"Task: {scheduled_task_name}"
        return f"Task: {task['id']}"

    def get_bot_instance(self, chat_id: str) -> Optional[Any]:
        """Get a bot instance by chat ID.

        Args:
            chat_id: The chat ID

        Returns:
            Bot instance or None if not found
        """
        return self.bot_instances.get(chat_id)

    def remove_scheduled_task_chat(self, scheduled_task_name: str) -> bool:
        """Remove a scheduled task's chat from cache.

        Args:
            scheduled_task_name: The scheduled task name

        Returns:
            True if removed, False if not found
        """
        if scheduled_task_name in self.scheduled_task_chats:
            chat_id, _ = self.scheduled_task_chats[scheduled_task_name]
            del self.scheduled_task_chats[scheduled_task_name]
            if chat_id in self.bot_instances:
                del self.bot_instances[chat_id]
            logger.info(f"Removed chat for scheduled task '{scheduled_task_name}'")
            return True
        return False

    def get_scheduled_task_chat_stats(self) -> Dict[str, Any]:
        """Get statistics about scheduled task chats.

        Returns:
            Dictionary with chat statistics
        """
        return {
            "scheduled_chats": len(self.scheduled_task_chats),
            "total_bot_instances": len(self.bot_instances),
            "scheduled_task_names": list(self.scheduled_task_chats.keys()),
        }

    # ===========================
    # Task Dependencies
    # ===========================

    async def add_task_dependency(
        self, task_id: str, depends_on_task_id: str
    ) -> bool:
        """Add a dependency between tasks.

        Args:
            task_id: The task that has the dependency
            depends_on_task_id: The task it depends on

        Returns:
            True if successful, False otherwise
        """
        return await self.task_queue.add_task_dependency(task_id, depends_on_task_id)

    async def get_task_dependencies(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all tasks that a task depends on.

        Args:
            task_id: The task ID

        Returns:
            List of task dictionaries that this task depends on
        """
        return await self.task_queue.get_task_dependencies(task_id)

    async def get_dependent_tasks(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all tasks that depend on a task.

        Args:
            task_id: The task ID

        Returns:
            List of task dictionaries that depend on this task
        """
        return await self.task_queue.get_dependent_tasks(task_id)

    # ===========================
    # Task Cleanup
    # ===========================

    async def clear_completed_tasks(self, keep_failed: bool = True) -> int:
        """Clear completed tasks from the queue.

        Args:
            keep_failed: If True, keeps failed tasks

        Returns:
            Number of tasks cleared
        """
        return await self.task_queue.clear_completed_tasks(keep_failed=keep_failed)

