# Task Server Documentation

## Overview

The Sparky tasking system is an integrated component responsible for managing and executing background tasks. It is not a standalone microservice but is built into the main application's event loop. The system is comprised of two key modules: the `AgentLoop` and the `TaskQueue`.

**Locations:**
- AgentLoop: `src/servers/task/task_server.py`
- TaskQueue: `src/sparky/task_queue.py`

## Architecture

### AgentLoop (`src/servers/task/task_server.py`)

The `AgentLoop` acts as the primary worker for the tasking system. It operates as a continuous, asynchronous loop that performs the following functions:

- **Polling:** It periodically polls the `TaskQueue` for new tasks in the `pending` state.
- **Execution:** When a new task is retrieved, the `AgentLoop` uses a persistent, internal instance of the `Bot` to execute the task's instructions. This means the background agent has access to the same set of tools as the interactive bot.
- **Scheduled Tasks:** It manages tasks that are scheduled to run at specific intervals or times, as defined in `scheduled_tasks.yaml`.
- **State Management:** It updates the task's status from `pending` to `in_progress` upon starting and to `completed` or `failed` upon completion.

### TaskQueue (`src/sparky/task_queue.py`)

The `TaskQueue` is responsible for the storage and management of all tasks.

- **Knowledge Graph Integration:** Tasks are not stored in a traditional in-memory queue. Instead, each task is a node in the knowledge graph with the `node_type` of `Task`. This provides persistence, scalability, and the ability to form complex relationships.
- **Persistent Storage:** Storing tasks in the graph ensures that they are not lost if the application restarts.
- **Task Relationships:** The system leverages the graph structure to define dependencies and other relationships between tasks. For example, a `DEPENDS_ON` edge can be created between two tasks to ensure one completes before the other begins. Other supported relationships include `PARENT_OF`, `CHILD_OF`, and `BLOCKS`.

## Tool Interface

The task management tools (`add_task`, `get_task`, `list_tasks`, `update_task`, `delete_task`, `get_task_stats`) are exposed to the bot via the `miscellaneous` tool server, as defined in `mcp.json`. These tools provide the interface for the bot to interact with the underlying `TaskQueue`.
