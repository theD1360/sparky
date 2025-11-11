# Sparky CLI

The Sparky Command-Line Interface (CLI) is used to manage the chat server and launch the client.

## Server Commands

The server commands are used to start, stop, and restart the Sparky chat server.

### `sparky server start`

This command starts the chat server.

**Usage:**

```
sparky server start [OPTIONS]
```

**Options:**

*   `--host TEXT`: The host to bind the server to. Defaults to `127.0.0.1`.
*   `--port INTEGER`: The port to bind the server to. Defaults to `8000`.
*   `--daemon`: Run the server in the background.
*   `--pidfile TEXT`: The path to the PID file. Defaults to `bot.pid`.

### `sparky server stop`

This command stops the chat server.

**Usage:**

```
sparky server stop [OPTIONS]
```

**Options:**

*   `--pidfile TEXT`: The path to the PID file. Defaults to `bot.pid`.

### `sparky server restart`

This command restarts the chat server.

**Usage:**

```
sparky server restart [OPTIONS]
```

**Options:**

*   `--host TEXT`: The host to bind the server to. Defaults to `127.0.0.1`.
*   `--port INTEGER`: The port to bind the server to. Defaults to `8000`.
*   `--daemon`: Run the server in the background.
*   `--pidfile TEXT`: The path to the PID file. Defaults to `bot.pid`.

## Client Commands

The client commands are used to launch the Sparky chat client.

### `sparky client start`

This command starts the chat client.

**Usage:**

```
sparky client start [OPTIONS]
```

**Options:**

*   `--host TEXT`: The host to connect to. Defaults to `127.0.0.1`.
*   `--port INTEGER`: The port to connect to. Defaults to `8000`.
*   `--personality TEXT`: An optional personality to set for the bot on connection.
*   `--session-id TEXT`: An optional session ID to reconnect to an existing session.


## Agent Commands

The agent commands are used to manage the proactive agent background tasks.

### `sparky agent start`

This command starts the proactive agent loop to process background tasks.

**Usage:**

```
sparky agent start [OPTIONS]
```

**Options:**

*   `--daemon / -d`: Run the agent in the background as a daemon.
*   `--interval / -i INTEGER`: Seconds to wait between polling for tasks. Defaults to `10`.

### `sparky agent stop`

This command stops the background agent loop.

**Usage:**

```
sparky agent stop
```

### `sparky agent status`

This command checks if the agent is running and shows task statistics.

**Usage:**

```
sparky agent status
```

### `sparky agent list-tasks`

This command lists all tasks in the agent's queue.

**Usage:**

```
sparky agent list-tasks [OPTIONS]
```

**Options:**

*   `--status / -s TEXT`: Filter by status (pending, in_progress, completed, failed).

### `sparky agent add-task`

This command adds a new task to the agent's queue.

**Usage:**

```
sparky agent add-task <INSTRUCTIONS>
```

**Arguments:**

*   `INSTRUCTIONS`: A prompt that describes the task to be performed.

### `sparky agent clear-completed`

This command clears completed tasks from the queue.

**Usage:**

```
sparky agent clear-completed
```

**Options:**
*   `--keep-failed`: Keep failed tasks for debugging. Defaults to True.

### `sparky agent schedule`

This command schedules tasks from `scheduled_tasks.yaml` to run in the agent queue.

**Usage:**

```
sparky agent schedule [OPTIONS] [TASK_NAMES]...
```

**Options:**

*   `--all / -a`: Schedule all enabled tasks from `scheduled_tasks.yaml`.

**Arguments:**

*   `TASK_NAMES...`: Names of tasks to schedule.

### `sparky agent stats`

This command shows detailed agent loop statistics including curiosity cycles.

**Usage:**

```
sparky agent stats
```
