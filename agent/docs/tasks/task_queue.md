# Task Queue (`task_queue.py`)

This module provides a sophisticated, persistent task queue system that is built directly on top of the knowledge graph. Instead of using a traditional message broker or a separate database, tasks are stored as `Task` nodes within the graph, which allows them to be queried, related, and managed using the same mechanisms as any other piece of knowledge.

## Core Concepts

*   **Tasks as Nodes:** Each task is a node in the knowledge graph with a `node_type` of `Task`. The task's details (instruction, status, etc.) are stored in the node's `properties`.
*   **Centralized Management:** The `TaskQueue` class is the primary interface for all task-related operations.
*   **Persistence:** Because tasks are stored in the main database, they persist across application restarts.
*   **Relationships:** Tasks can be linked to each other with edges to represent dependencies (`DEPENDS_ON`), parent/child relationships, or other custom relations.
*   **Event-Driven:** The queue emits events (using `TaskEvents`) when tasks are added or change state, allowing other parts of the system to react accordingly.

## The `TaskQueue` Class

This class orchestrates all interactions with the task system.

### Initialization (`__init__`)

The `TaskQueue` is initialized with a `KnowledgeRepository` instance, which it uses to perform all graph operations.

### Key Methods

*   `add_task()`: Creates a new task. It generates a unique ID, saves the task as a `Task` node, and links it to the `concept:tasks` node with an `INSTANCE_OF` edge. It also checks for duplicate tasks to avoid redundancy.
*   `get_task()`: Retrieves a single task by its ID.
*   `get_all_tasks()`: Fetches all tasks, with support for pagination.
*   `get_next_pending_task()`: This is the core method for a worker to get the next available job. It finds the oldest task with a `pending` status, atomically updates its status to `in_progress`, and returns it.
*   `update_task_status()`: Changes the status of a task (e.g., to `completed` or `failed`) and can optionally store a final response or error message.
*   `delete_task()`: Removes a task node from the graph.
*   `clear_completed_tasks()`: A maintenance method to remove finished tasks from the queue.
*   `get_task_stats()`: Provides a summary of how many tasks are in each state (pending, completed, etc.).

### Relationship Management

The `TaskQueue` also includes methods for managing the relationships between tasks:

*   `add_task_dependency()`: Creates a `DEPENDS_ON` edge between two tasks.
*   `get_task_dependencies()`: Finds all tasks that a given task depends on.
*   `get_dependent_tasks()`: Finds all tasks that depend on a given task.
*   `add_related_task()`: Creates other types of relationships, such as `PARENT_OF`, `CHILD_OF`, or `BLOCKS`.
*   `get_related_tasks()`: Retrieves all tasks connected to a given task.

## `create_task_queue()` Function

This is a convenience factory function that simplifies the creation of a `TaskQueue` instance. It reads the `SPARKY_DB_URL` from the environment, sets up the database connection and `KnowledgeRepository`, and returns a fully initialized `TaskQueue`. This is the preferred way to get a `TaskQueue` instance in most parts of the application.
