"""Task queue for Sparky using knowledge graph for storage.

This module provides a TaskQueue class to manage background tasks that can be
executed by the agent loop. Tasks are stored as nodes in the knowledge graph,
enabling efficient SQL-based querying and support for task relationships.

Tasks can be in states: pending, in_progress, completed, or failed.
Tasks support relationships including dependencies (DEPENDS_ON), parent/child
relationships (PARENT_OF, CHILD_OF), and custom relationships (RELATES_TO, BLOCKS).
"""

import os
import uuid
from datetime import datetime, timezone
from logging import getLogger
from typing import Any, Dict, List, Optional

from sparky.event_types import TaskEvents
from database.database import get_database_manager
from database.repository import KnowledgeRepository
from utils.events import Events

logger = getLogger(__name__)


class TaskQueue:
    """Task queue manager using knowledge graph for storage.

    This class provides methods to manage background tasks stored as nodes
    in the knowledge graph. Tasks support dependencies and relationships.
    """

    def __init__(self, repository: KnowledgeRepository):
        """Initialize the task queue with a knowledge repository.

        Args:
            repository: KnowledgeRepository instance for graph operations
        """
        self.repository = repository
        self.events = Events()
        logger.debug("TaskQueue initialized with event system")

    def _ensure_task_concept(self) -> None:
        """Ensure the concept:tasks node exists in the graph.

        This is called automatically by add_task to set up the ontology.
        """
        try:
            self.repository.add_node(
                node_id="concept:tasks",
                node_type="Concept",
                label="Tasks",
                properties={"description": "Active tasks and work items"},
            )
        except Exception as e:
            logger.debug(f"Task concept may already exist: {e}")

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific task by ID.

        Args:
            task_id: Task ID (without 'task:' prefix)

        Returns:
            Task dictionary if found, None otherwise
        """
        try:
            node_id = f"task:{task_id}"
            node = self.repository.get_node(node_id)

            if not node:
                logger.debug(f"Task {task_id} not found")
                return None

            # Convert node to task dictionary
            properties = node.properties or {}
            return {
                "id": task_id,
                "instruction": properties.get("instruction", ""),
                "metadata": properties.get("metadata", {}),
                "status": properties.get("status", "pending"),
                "created_at": (node.created_at.isoformat() if node.created_at else ""),
                "updated_at": (node.updated_at.isoformat() if node.updated_at else ""),
                "response": properties.get("response"),
                "error": properties.get("error"),
            }
        except Exception as e:
            logger.error(f"Error retrieving task {task_id}: {e}", exc_info=True)
            return None

    async def _save_task(self, task: Dict[str, Any]) -> None:
        """Save a task to the graph.

        Args:
            task: Task dictionary with all fields
        """
        node_id = f"task:{task['id']}"

        # Prepare properties - store all task fields as properties
        properties = {
            "instruction": task["instruction"],
            "metadata": task.get("metadata", {}),
            "status": task["status"],
            "created_at": task["created_at"],
            "updated_at": task["updated_at"],
            "response": task.get("response"),
            "error": task.get("error"),
        }

        try:
            self.repository.add_node(
                node_id=node_id,
                node_type="Task",
                label=(
                    task["instruction"][:50] + "..."
                    if len(task["instruction"]) > 50
                    else task["instruction"]
                ),
                properties=properties,
            )
            logger.debug(f"Successfully saved task {task['id']}")
        except Exception as e:
            logger.error(f"Error saving task {task['id']} to graph: {e}", exc_info=True)
            raise

    async def search_tasks(
        self,
        query: str,
        status_filter: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Search for tasks by instruction text.

        Args:
            query: Search query to match against task instructions
            status_filter: Optional status filter ('pending', 'in_progress', 'completed', 'failed')
            limit: Optional limit on number of results

        Returns:
            List of matching task dictionaries, ordered by relevance (exact matches first)
        if not instruction or not instruction.strip():
            raise ValueError("Task instruction cannot be empty.")
        """
        try:
            # Get all Task nodes
            task_nodes = self.repository.get_nodes(node_type="Task")

            # Filter and score tasks
            results = []
            query_lower = query.lower()

            for node in task_nodes:
                properties = node.properties or {}
                instruction = properties.get("instruction", "")
                status = properties.get("status", "pending")

                # Apply status filter if specified
                if status_filter and status != status_filter:
                    continue

                # Check if query matches instruction
                instruction_lower = instruction.lower()
                if query_lower in instruction_lower:
                    # Extract task ID
                    node_id = node.id
                    task_id = (
                        node_id.replace("task:", "")
                        if node_id.startswith("task:")
                        else node_id
                    )

                    # Calculate relevance score (exact match = 1.0, partial match < 1.0)
                    if instruction_lower == query_lower:
                        relevance = 1.0
                    else:
                        relevance = len(query_lower) / len(instruction_lower)

                    results.append(
                        {
                            "id": task_id,
                            "instruction": instruction,
                            "metadata": properties.get("metadata", {}),
                            "status": status,
                            "created_at": (
                                node.created_at.isoformat() if node.created_at else ""
                            ),
                            "updated_at": (
                                node.updated_at.isoformat() if node.updated_at else ""
                            ),
                            "response": properties.get("response"),
                            "error": properties.get("error"),
                            "relevance": relevance,
                        }
                    )

            # Sort by relevance (highest first), then by creation time (newest first)
            results.sort(
                key=lambda t: (-t["relevance"], t.get("created_at", "")), reverse=True
            )

            # Remove relevance score from final results
            for task in results:
                del task["relevance"]

            # Apply limit if specified
            if limit:
                results = results[:limit]

            return results
        except Exception as e:
            logger.error(f"Error searching tasks: {e}", exc_info=True)
            return []

    async def add_task(
        self,
        instruction: str,
        metadata: Optional[Dict[str, Any]] = None,
        depends_on: Optional[List[str]] = None,
        allow_duplicates: bool = False,
    ) -> Dict[str, Any]:
        """Add a new task to the queue.

        Args:
            instruction: Natural language instruction for the bot to execute
            metadata: Optional metadata about the task (e.g., source, priority)
            depends_on: Optional list of task IDs this task depends on
            allow_duplicates: If False, prevents duplicate tasks that are pending or in_progress

        Returns:
            The newly created task dictionary
        """
        # Check for duplicates only if not explicitly allowed
        if not allow_duplicates:
            # Search for similar tasks with exact instruction match
            similar_tasks = await self.search_tasks(instruction, limit=10)

            for task in similar_tasks:
                # Only block if there's an active task (pending or in_progress) with same instruction
                if (
                    task["instruction"] == instruction
                    and task["metadata"] == (metadata or {})
                    and task["status"] in ["pending", "in_progress"]
                ):
                    logger.warning(
                        f"Task {task['id']} is already {task['status']} with the same instruction and metadata. "
                        f"Returning existing task instead of creating duplicate."
                    )
                    return task
        task_id = str(uuid.uuid4())

        try:
            # Use get_current_datetime tool
            datetime_result = await self.repository.get_current_datetime()
            if "result" in datetime_result:
                now = datetime_result["result"]
            else:
                logger.error(f"get_current_datetime tool failed: {datetime_result.get('message')}. Using fallback datetime.")
                now = datetime.now(timezone.utc).isoformat()  # Fallback
        except Exception as e:
            logger.error(f"Error calling get_current_datetime: {e}. Using fallback datetime.")
            now = datetime.now(timezone.utc).isoformat()  # Fallback

        task = {
            "id": task_id,
            "instruction": instruction,
            "metadata": metadata or {},
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "response": None,
            "error": None,
        }

        try:
            # Ensure concept:tasks exists
            self._ensure_task_concept()

            # Save the task as a graph node
            await self._save_task(task)

            # Verify the task was actually saved by trying to retrieve it
            try:
                verify_task = await self.get_task(task_id)
                if verify_task:
                    logger.debug(f"Verified task {task_id} exists in graph")
                    logger.info(f"Task {task_id} saved successfully to graph")
                else:
                    logger.warning(
                        f"Task verification failed: task {task_id} not found"
                    )
            except Exception as e:
                logger.warning(f"Could not verify task {task_id} was saved: {e}")

            # Link task to concept:tasks
            try:
                self.repository.add_edge(
                    source_id=f"task:{task_id}",
                    target_id="concept:tasks",
                    edge_type="INSTANCE_OF",
                )
            except Exception as e:
                logger.debug(f"Failed to link task to concept: {e}")

        except Exception as e:
            logger.error(f"Failed to add task {task_id} to graph: {e}", exc_info=True)
            # Re-raise to prevent silent failures
            raise

        # Add dependencies if specified
        if depends_on:
            for dep_id in depends_on:
                try:
                    await self.add_task_dependency(task_id, dep_id)
                except Exception as e:
                    logger.warning(
                        f"Failed to add dependency {dep_id} to task {task_id}: {e}"
                    )

        logger.info(f"Added task {task_id}: {instruction[:60]}...")

        # Emit TASK_ADDED event
        await self.events.async_dispatch(TaskEvents.TASK_ADDED, task)

        return task

    async def get_all_tasks(
        self, limit: Optional[int] = None, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve all tasks from the queue.

        Args:
            limit: Maximum number of tasks to return
            offset: Number of tasks to skip

        Returns:
            List of task dictionaries, ordered by creation time
        """
        try:
            # Get all Task nodes (we need to sort in Python, so get all first)
            task_nodes = self.repository.get_nodes(node_type="Task")

            # Convert to task dictionaries and sort by created_at
            tasks = []
            for node in task_nodes:
                # Extract task ID from node ID (remove 'task:' prefix)
                node_id = node.id
                task_id = (
                    node_id.replace("task:", "")
                    if node_id.startswith("task:")
                    else node_id
                )

                properties = node.properties or {}
                tasks.append(
                    {
                        "id": task_id,
                        "instruction": properties.get("instruction", ""),
                        "metadata": properties.get("metadata", {}),
                        "status": properties.get("status", "pending"),
                        "created_at": (
                            node.created_at.isoformat() if node.created_at else ""
                        ),
                        "updated_at": (
                            node.updated_at.isoformat() if node.updated_at else ""
                        ),
                        "response": properties.get("response"),
                        "error": properties.get("error"),
                    }
                )

            # Sort by created_at
            tasks.sort(key=lambda t: t.get("created_at", ""))

            # Apply pagination
            if offset or limit:
                end_index = offset + limit if limit else None
                tasks = tasks[offset:end_index]

            return tasks
        except Exception as e:
            logger.error(f"Error retrieving all tasks: {e}")
            return []

    def get_tasks_count(self) -> int:
        """Get count of all tasks in the queue.

        Returns:
            Count of tasks
        """
        try:
            return self.repository.get_nodes_count(node_type="Task")
        except Exception as e:
            logger.error(f"Error getting tasks count: {e}")
            return 0

    async def get_next_pending_task(self) -> Optional[Dict[str, Any]]:
        """Find and mark the next pending task as in_progress.

        Returns:
            The task dictionary if found, None otherwise
        """
        try:
            # Get all Task nodes
            task_nodes = self.repository.get_nodes(node_type="Task")

            # Find oldest pending task
            pending_tasks = [
                t
                for t in task_nodes
                if (t.properties or {}).get("status", "pending") == "pending"
            ]

            if not pending_tasks:
                return None

            # Sort by created_at and get the oldest
            pending_tasks.sort(
                key=lambda t: t.created_at if t.created_at else datetime.min
            )
            oldest_node = pending_tasks[0]

            # Extract task ID
            node_id = oldest_node.id
            task_id = (
                node_id.replace("task:", "") if node_id.startswith("task:") else node_id
            )

            # Get current task data
            task = await self.get_task(task_id)
            if not task:
                return None

            # Update status to in_progress
            task["status"] = "in_progress"
            task["updated_at"] = datetime.now(timezone.utc).isoformat()
            await self._save_task(task)

            instruction_preview = task.get("instruction", "")[:60]
            logger.info(
                f"Dequeued task {task['id']} for processing: {instruction_preview}..."
            )
            return task

        except Exception as e:
            logger.error(f"Error getting next pending task: {e}")
            return None

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        response: Optional[str] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update the status of a task.

        Args:
            task_id: ID of the task to update
            status: New status ('pending', 'in_progress', 'completed', 'failed')
            response: Optional bot response to the instruction
            error: Optional error message (for failed tasks)

        Returns:
            True if successful, False otherwise
        """
        try:
            task = await self.get_task(task_id)
            if not task:
                logger.warning(f"Task {task_id} not found for status update")
                return False

            if task["status"] not in ["pending", "in_progress", "completed", "failed"]:
                logger.warning(f"Invalid status {status} for task {task_id}")
                return False

            task["status"] = status
            task["updated_at"] = datetime.now(timezone.utc).isoformat()

            if response is not None:
                task["response"] = response
            if error is not None:
                task["error"] = error

            await self._save_task(task)
            logger.info(f"Updated task {task_id} status to '{status}'")

            # Emit TASK_STATUS_CHANGED event
            await self.events.async_dispatch(
                TaskEvents.TASK_STATUS_CHANGED,
                task_id,
                status,
                response=response,
                error=error,
            )

            return True
        except Exception as e:
            logger.error(f"Error updating task status: {e}", exc_info=True)
            return False


    async def delete_task(self, task_id: str) -> bool:
        """Delete a task from the queue.

        Edges are automatically cascade deleted by the graph database.

        Args:
            task_id: ID of the task to delete

        Returns:
            True if successful, False otherwise
        """
        node_id = f"task:{task_id}"

        try:
            success = self.repository.delete_node(node_id)
            if success:
                logger.info(f"Deleted task {task_id}")
            else:
                logger.warning(f"Failed to delete task {task_id}: node not found")
            return success
        except Exception as e:
            logger.error(f"Error deleting task {task_id}: {e}")
            return False

    async def clear_completed_tasks(self, keep_failed: bool = True) -> int:
        """Clear completed tasks from the queue.

        Args:
            keep_failed: If True, keep failed tasks for debugging

        Returns:
            Number of tasks cleared
        """
        try:
            # Get all Task nodes
            task_nodes = self.repository.get_nodes(node_type="Task")

            cleared = 0
            for node in task_nodes:
                properties = node.properties or {}
                status = properties.get("status", "pending")

                # Check if we should delete this task
                should_delete = False
                if status == "completed":
                    should_delete = True
                elif status == "failed" and not keep_failed:
                    should_delete = True

                if should_delete:
                    node_id = node.id
                    task_id = (
                        node_id.replace("task:", "")
                        if node_id.startswith("task:")
                        else node_id
                    )
                    if await self.delete_task(task_id):
                        cleared += 1

            logger.info(f"Cleared {cleared} tasks")
            return cleared
        except Exception as e:
            logger.error(f"Error clearing completed tasks: {e}")
            return 0

    async def get_task_stats(self) -> Dict[str, int]:
        """Get statistics about tasks in the queue.

        Returns:
            Dictionary with counts for each status
        """
        try:
            # Get all Task nodes
            task_nodes = self.repository.get_nodes(node_type="Task")

            stats = {
                "pending": 0,
                "in_progress": 0,
                "completed": 0,
                "failed": 0,
                "total": 0,
            }

            for node in task_nodes:
                properties = node.properties or {}
                status = properties.get("status", "pending")
                if status in stats:
                    stats[status] += 1
                    stats["total"] += 1

            return stats
        except Exception as e:
            logger.error(f"Error getting task stats: {e}")
            return {
                "pending": 0,
                "in_progress": 0,
                "completed": 0,
                "failed": 0,
                "total": 0,
            }

    # ============================================================================
    # TASK RELATIONSHIP METHODS
    # ============================================================================

    async def add_task_dependency(self, task_id: str, depends_on_id: str) -> bool:
        """Add a dependency relationship between tasks.

        Creates a DEPENDS_ON edge from task_id to depends_on_id, indicating
        that task_id depends on (and should wait for) depends_on_id.

        Args:
            task_id: ID of the dependent task
            depends_on_id: ID of the task this depends on

        Returns:
            True if successful, False otherwise
        """
        try:
            # Verify both tasks exist
            task = await self.get_task(task_id)
            dependency = await self.get_task(depends_on_id)

            if not task:
                logger.warning(f"Task {task_id} not found")
                return False
            if not dependency:
                logger.warning(f"Dependency task {depends_on_id} not found")
                return False

            # Create the edge
            self.repository.add_edge(
                source_id=f"task:{task_id}",
                target_id=f"task:{depends_on_id}",
                edge_type="DEPENDS_ON",
            )

            logger.info(f"Added dependency: task {task_id} depends on {depends_on_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding task dependency: {e}")
            return False

    async def get_task_dependencies(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all tasks that this task depends on.

        Args:
            task_id: ID of the task

        Returns:
            List of task dictionaries this task depends on
        """
        try:
            node_id = f"task:{task_id}"
            # Get outgoing DEPENDS_ON edges
            edges = self.repository.get_edges(source_id=node_id, edge_type="DEPENDS_ON")

            tasks = []
            for edge in edges:
                target_id = edge.target_id
                dep_task_id = (
                    target_id.replace("task:", "")
                    if target_id.startswith("task:")
                    else target_id
                )
                dep_task = await self.get_task(dep_task_id)
                if dep_task:
                    tasks.append(dep_task)

            return tasks
        except Exception as e:
            logger.error(f"Error getting task dependencies: {e}")
            return []

    async def get_dependent_tasks(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all tasks that depend on this task.

        Args:
            task_id: ID of the task

        Returns:
            List of task dictionaries that depend on this task
        """
        try:
            node_id = f"task:{task_id}"
            # Get incoming DEPENDS_ON edges
            edges = self.repository.get_edges(target_id=node_id, edge_type="DEPENDS_ON")

            tasks = []
            for edge in edges:
                source_id = edge.source_id
                dep_task_id = (
                    source_id.replace("task:", "")
                    if source_id.startswith("task:")
                    else source_id
                )
                dep_task = await self.get_task(dep_task_id)
                if dep_task:
                    tasks.append(dep_task)

            return tasks
        except Exception as e:
            logger.error(f"Error getting dependent tasks: {e}")
            return []

    async def add_related_task(
        self,
        task_id: str,
        related_task_id: str,
        relationship_type: str = "RELATES_TO",
    ) -> bool:
        """Add a custom relationship between tasks.

        Supports various relationship types:
        - RELATES_TO: General relationship
        - PARENT_OF: task_id is parent of related_task_id
        - CHILD_OF: task_id is child of related_task_id
        - BLOCKS: task_id blocks related_task_id
        - BLOCKED_BY: task_id is blocked by related_task_id

        Args:
            task_id: ID of the first task
            related_task_id: ID of the related task
            relationship_type: Type of relationship (default: RELATES_TO)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Verify both tasks exist
            task = await self.get_task(task_id)
            related = await self.get_task(related_task_id)

            if not task:
                logger.warning(f"Task {task_id} not found")
                return False
            if not related:
                logger.warning(f"Related task {related_task_id} not found")
                return False

            # Create the edge
            self.repository.add_edge(
                source_id=f"task:{task_id}",
                target_id=f"task:{related_task_id}",
                edge_type=relationship_type,
            )

            logger.info(
                f"Added relationship: task {task_id} -{relationship_type}-> {related_task_id}"
            )
            return True
        except Exception as e:
            logger.error(f"Error adding task relationship: {e}")
            return False

    async def get_related_tasks(
        self, task_id: str, relationship_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all tasks related to this task, optionally filtered by relationship type.

        Args:
            task_id: ID of the task
            relationship_type: Optional filter by relationship type

        Returns:
            List of related task dictionaries
        """
        try:
            node_id = f"task:{task_id}"

            # Get outgoing edges (excluding INSTANCE_OF)
            if relationship_type:
                edges = self.repository.get_edges(
                    source_id=node_id, edge_type=relationship_type
                )
            else:
                all_edges = self.repository.get_edges(source_id=node_id)
                edges = [e for e in all_edges if e.edge_type != "INSTANCE_OF"]

            tasks = []
            for edge in edges:
                target_id = edge.target_id
                # Only process task nodes
                if not target_id.startswith("task:"):
                    continue

                rel_task_id = target_id.replace("task:", "")
                rel_task = await self.get_task(rel_task_id)
                if rel_task:
                    tasks.append(rel_task)

            return tasks
        except Exception as e:
            logger.error(f"Error getting related tasks: {e}")
            return []

    async def get_last_scheduled_task_execution(
        self, scheduled_task_name: str
    ) -> Optional[datetime]:
        """Get the creation time of the last task for a scheduled task name.

        Args:
            scheduled_task_name: The name of the scheduled task from metadata

        Returns:
            The datetime of the last task creation, or None if no task found
        """
        try:
            # Get all Task nodes
            task_nodes = self.repository.get_nodes(node_type="Task")

            # Filter by scheduled_task_name in metadata and sort by created_at
            matching_tasks = []
            for node in task_nodes:
                properties = node.properties or {}
                metadata = properties.get("metadata", {})
                if metadata.get("scheduled_task_name") == scheduled_task_name:
                    matching_tasks.append(node)

            if not matching_tasks:
                return None

            # Sort by created_at descending (most recent first)
            matching_tasks.sort(key=lambda n: n.created_at or datetime.min, reverse=True)

            # Return the most recent task's creation time
            return matching_tasks[0].created_at

        except Exception as e:
            logger.error(
                f"Error getting last scheduled task execution for '{scheduled_task_name}': {e}",
                exc_info=True,
            )
            return None


def create_task_queue() -> TaskQueue:
    """Create a TaskQueue instance using repository from environment variables.

    This is a convenience function for creating a TaskQueue when you don't
    have a repository instance available. It reads SPARKY_DB_URL from
    environment and creates the repository automatically.

    Returns:
        TaskQueue instance initialized with repository from environment

    Raises:
        RuntimeError: If SPARKY_DB_URL environment variable is not set
    """
    # Get database URL from environment (required for PostgreSQL)
    db_url = os.getenv("SPARKY_DB_URL")
    if not db_url:
        raise RuntimeError(
            "SPARKY_DB_URL environment variable is required for database connection"
        )

    # Mask password in log for security
    safe_db_url = db_url.split("@")[-1] if "@" in db_url else db_url[:50]
    logger.info(f"Task queue: Connecting to database: ...@{safe_db_url}")

    db_manager = get_database_manager(db_url=db_url)
    db_manager.connect()
    repository = KnowledgeRepository(db_manager)
    logger.debug("Task queue: Repository initialized")

    return TaskQueue(repository)
