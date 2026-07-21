# Task Server / Agent Worker

## Overview

Background agent tasks are executed by a **dedicated worker process** via a Redis-backed command bus (`deegzlibs-command-bus`). Knowledge-graph `Task` nodes remain the durable ledger; Redis only transports `RunAgentTask` wakeups.

## Running

```bash
# Docker Compose (recommended)
docker compose up worker

# Or locally (requires Redis + SPARKY_DB_URL)
export REDIS_URL=redis://localhost:6379/0
sparky agent worker
# equivalent: python -m commands.worker
```

Chat server still hosts the WebSocket API and relays worker events from `REDIS_EVENTS_CHANNEL` to connected clients.

## Architecture

1. Producers (CLI, MCP `add_task`, scheduler) call `enqueue_agent_task` → persist pending Task → `dispatch_async(RunAgentTaskCommand)`.
2. Worker BRPOPs the Redis queue, claims the Task (`pending` → `in_progress`), runs `AgentTaskExecutor`.
3. Progress events publish to Redis pub/sub; chat server forwards to WebSockets.
4. Worker also ticks `scheduled_tasks.yaml` and periodically reconciles stuck pending Tasks.

## Key modules

| Module | Role |
|--------|------|
| `commands/` | Bus DTOs, dispatch, worker loop, handlers |
| `services/agent_task_executor.py` | Bot execution for a claimed task |
| `sparky/task_queue.py` | KG Task CRUD + `claim_task` |
| `servers/chat/task_events_subscriber.py` | Redis → WebSocket fan-out |

## Deprecated

`AgentLoop` / `SPARKY_ENABLE_AGENT_LOOP` (in-process poll inside chat) is retired. Use the worker service instead.
