"""Tests for the graph-based task queue."""

import pytest
from database.repository import KnowledgeRepository
from sparky.task_queue import TaskQueue


@pytest.fixture
def task_queue():
    """Create a TaskQueue instance for testing."""
    from database.database import get_database_manager
    from database.models import Base
    db_url = "sqlite:///:memory:"
    db_manager = get_database_manager(db_url=db_url)
    db_manager.connect()
    Base.metadata.create_all(db_manager.engine)
    repository = KnowledgeRepository(db_manager)
    task_queue = TaskQueue(repository)
    yield task_queue
    db_manager.close()


async def test_add_and_get_task(task_queue):
    """Test adding and retrieving a task."""
    # Add a task
    task = await task_queue.add_task(
        "Test task instruction",
        metadata={"priority": "high", "source": "test"},
    )

    assert task["id"] is not None
    assert task["instruction"] == "Test task instruction"
    assert task["status"] == "pending"
    assert task["metadata"]["priority"] == "high"

    # Retrieve the task
    retrieved = await task_queue.get_task(task["id"])
    assert retrieved is not None
    assert retrieved["id"] == task["id"]
    assert retrieved["instruction"] == task["instruction"]


async def test_get_all_tasks(task_queue):
    """Test retrieving all tasks."""
    # Add multiple tasks
    task1 = await task_queue.add_task("Task 1")
    task2 = await task_queue.add_task("Task 2")
    task3 = await task_queue.add_task("Task 3")

    # Get all tasks
    all_tasks = await task_queue.get_all_tasks()

    assert len(all_tasks) >= 3
    task_ids = [t["id"] for t in all_tasks]
    assert task1["id"] in task_ids
    assert task2["id"] in task_ids
    assert task3["id"] in task_ids


async def test_update_task_status(task_queue):
    """Test updating task status."""
    # Add a task
    task = await task_queue.add_task("Test task")

    # Update to in_progress
    success = await task_queue.update_task_status(task["id"], "in_progress")
    assert success

    # Verify update
    updated = await task_queue.get_task(task["id"])
    assert updated["status"] == "in_progress"

    # Update to completed with response
    success = await task_queue.update_task_status(
        task["id"], "completed", response="Task completed successfully"
    )
    assert success

    # Verify update
    completed = await task_queue.get_task(task["id"])
    assert completed["status"] == "completed"
    assert completed["response"] == "Task completed successfully"


async def test_get_next_pending_task(task_queue):
    """Test getting the next pending task."""
    # Add multiple tasks
    task1 = await task_queue.add_task("First task")
    task2 = await task_queue.add_task("Second task")
    await task_queue.add_task("Third task")

    # Get next pending (should be oldest)
    next_task = await task_queue.get_next_pending_task()
    assert next_task is not None
    assert next_task["id"] == task1["id"]
    assert next_task["status"] == "in_progress"

    # Get next pending (should be task2 now)
    next_task = await task_queue.get_next_pending_task()
    assert next_task is not None
    assert next_task["id"] == task2["id"]


async def test_delete_task(task_queue):
    """Test deleting a task."""
    # Add a task
    task = await task_queue.add_task("Task to delete")

    # Delete the task
    success = await task_queue.delete_task(task["id"])
    assert success

    # Verify deletion
    deleted = await task_queue.get_task(task["id"])
    assert deleted is None


async def test_get_task_stats(task_queue):
    """Test getting task statistics."""
    # Add tasks with different statuses
    await task_queue.add_task("Pending task 1")
    await task_queue.add_task("Pending task 2")
    task3 = await task_queue.add_task("In progress task")
    await task_queue.update_task_status(task3["id"], "in_progress")
    task4 = await task_queue.add_task("Completed task")
    await task_queue.update_task_status(task4["id"], "completed")

    # Get stats
    stats = await task_queue.get_task_stats()

    assert stats["pending"] >= 2
    assert stats["in_progress"] >= 1
    assert stats["completed"] >= 1
    assert stats["total"] >= 4


async def test_clear_completed_tasks(task_queue):
    """Test clearing completed tasks."""
    # Add and complete some tasks
    task1 = await task_queue.add_task("Completed task 1")
    await task_queue.update_task_status(task1["id"], "completed")
    task2 = await task_queue.add_task("Completed task 2")
    await task_queue.update_task_status(task2["id"], "completed")
    task3 = await task_queue.add_task("Failed task")
    await task_queue.update_task_status(task3["id"], "failed")

    # Clear completed tasks (keep failed)
    cleared = await task_queue.clear_completed_tasks(keep_failed=True)
    assert cleared >= 2

    # Verify failed task still exists
    failed_task = await task_queue.get_task(task3["id"])
    assert failed_task is not None
    assert failed_task["status"] == "failed"


async def test_task_dependencies(task_queue):
    """Test task dependency relationships."""
    # Create tasks with dependencies
    task_a = await task_queue.add_task("Task A")
    task_b = await task_queue.add_task("Task B", depends_on=[task_a["id"]])

    # Verify dependency was created
    deps = await task_queue.get_task_dependencies(task_b["id"])
    assert len(deps) == 1
    assert deps[0]["id"] == task_a["id"]

    # Check reverse lookup
    dependents = await task_queue.get_dependent_tasks(task_a["id"])
    assert len(dependents) == 1
    assert dependents[0]["id"] == task_b["id"]


async def test_add_task_dependency(task_queue):
    """Test adding dependencies after task creation."""
    # Create tasks
    task_a = await task_queue.add_task("Task A")
    task_b = await task_queue.add_task("Task B")

    # Add dependency
    success = await task_queue.add_task_dependency(task_b["id"], task_a["id"])
    assert success

    # Verify dependency
    deps = await task_queue.get_task_dependencies(task_b["id"])
    assert len(deps) == 1
    assert deps[0]["id"] == task_a["id"]


async def test_related_tasks(task_queue):
    """Test custom task relationships."""
    # Create parent and child tasks
    parent = await task_queue.add_task("Parent task")
    child1 = await task_queue.add_task("Child task 1")
    child2 = await task_queue.add_task("Child task 2")

    # Add parent-child relationships
    await task_queue.add_related_task(parent["id"], child1["id"], "PARENT_OF")
    await task_queue.add_related_task(parent["id"], child2["id"], "PARENT_OF")

    # Query children
    children = await task_queue.get_related_tasks(parent["id"], "PARENT_OF")
    assert len(children) == 2
    child_ids = [c["id"] for c in children]
    assert child1["id"] in child_ids
    assert child2["id"] in child_ids


async def test_blocking_relationships(task_queue):
    """Test blocking relationships."""
    # Create tasks with blocking relationship
    blocker = await task_queue.add_task("Blocker task")
    blocked = await task_queue.add_task("Blocked task")

    # Add blocking relationship
    success = await task_queue.add_related_task(blocker["id"], blocked["id"], "BLOCKS")
    assert success

    # Verify relationship
    blocked_tasks = await task_queue.get_related_tasks(blocker["id"], "BLOCKS")
    assert len(blocked_tasks) == 1
    assert blocked_tasks[0]["id"] == blocked["id"]


async def test_multiple_dependencies(task_queue):
    """Test task with multiple dependencies."""
    # Create tasks
    dep1 = await task_queue.add_task("Dependency 1")
    dep2 = await task_queue.add_task("Dependency 2")
    dep3 = await task_queue.add_task("Dependency 3")

    # Create task that depends on all three
    task = await task_queue.add_task(
        "Task with multiple dependencies",
        depends_on=[dep1["id"], dep2["id"], dep3["id"]],
    )

    # Verify all dependencies
    deps = await task_queue.get_task_dependencies(task["id"])
    assert len(deps) == 3
    dep_ids = [d["id"] for d in deps]
    assert dep1["id"] in dep_ids
    assert dep2["id"] in dep_ids
    assert dep3["id"] in dep_ids


async def test_task_not_found(task_queue):
    """Test handling of non-existent task."""
    # Try to get non-existent task
    task = await task_queue.get_task("non-existent-id")
    assert task is None

    # Try to update non-existent task
    success = await task_queue.update_task_status("non-existent-id", "completed")
    assert not success

    # Try to delete non-existent task
    success = await task_queue.delete_task("non-existent-id")
    assert not success


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
