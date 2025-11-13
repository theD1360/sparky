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

### Agent Lifecycle Commands

#### `sparky agent start`

Start the proactive agent loop to process background tasks.

**Usage:**

```
sparky agent start [OPTIONS]
```

**Options:**

*   `--daemon / -d`: Run the agent in the background as a daemon.
*   `--interval / -i INTEGER`: Seconds to wait between polling for tasks. Defaults to `10`.

#### `sparky agent stop`

Stop the background agent loop.

**Usage:**

```
sparky agent stop
```

#### `sparky agent status`

Check if the agent is running and show task statistics.

**Usage:**

```
sparky agent status
```

#### `sparky agent schedule`

Manage scheduled tasks from `scheduled_tasks.yaml`. All schedule operations are organized under `sparky agent schedule`.

#### `sparky agent stats`

Show detailed agent loop statistics including curiosity cycles.

**Usage:**

```
sparky agent stats
```

### Task Management Commands

All task management commands are organized under `sparky agent tasks`.

#### `sparky agent tasks list`

List all tasks in the agent's queue with optional filtering.

**Usage:**

```
sparky agent tasks list [OPTIONS]
```

**Options:**

*   `--status / -s TEXT`: Filter by status (pending, in_progress, completed, failed).
*   `--limit / -l INTEGER`: Maximum number of tasks to display.

**Example:**

```bash
sparky agent tasks list --status pending --limit 10
```

#### `sparky agent tasks add`

Add a new task to the agent's queue.

**Usage:**

```
sparky agent tasks add <INSTRUCTION> [OPTIONS]
```

**Arguments:**

*   `INSTRUCTION`: A prompt that describes the task to be performed.

**Options:**

*   `--metadata / -m TEXT`: Metadata in key=value format (can be specified multiple times).

**Example:**

```bash
sparky agent tasks add "Review the codebase" --metadata priority=high --metadata source=manual
```

#### `sparky agent tasks get`

Get detailed information about a specific task.

**Usage:**

```
sparky agent tasks get <TASK_ID>
```

**Arguments:**

*   `TASK_ID`: ID of the task to retrieve.

**Example:**

```bash
sparky agent tasks get abc123def
```

#### `sparky agent tasks update`

Update one or more fields of a task atomically.

**Usage:**

```
sparky agent tasks update <TASK_ID> [OPTIONS]
```

**Arguments:**

*   `TASK_ID`: ID of the task to update.

**Options:**

*   `--status / -s TEXT`: New status (pending, in_progress, completed, failed).
*   `--instruction / -i TEXT`: New instruction text.
*   `--metadata / -m TEXT`: Metadata to update in key=value format (can be specified multiple times).
*   `--response / -r TEXT`: Task response.
*   `--error / -e TEXT`: Error message.

**Example:**

```bash
sparky agent tasks update abc123def --status completed --response "Task finished successfully"
```

#### `sparky agent tasks delete`

Delete a specific task from the queue.

**Usage:**

```
sparky agent tasks delete <TASK_ID> [OPTIONS]
```

**Arguments:**

*   `TASK_ID`: ID of the task to delete.

**Options:**

*   `--force / -f`: Skip confirmation prompt.

**Example:**

```bash
sparky agent tasks delete abc123def --force
```

#### `sparky agent tasks clear`

Clear tasks from the queue with flexible filtering.

**Usage:**

```
sparky agent tasks clear [OPTIONS]
```

**Options:**

*   `--status / -s TEXT`: Filter by status (pending, in_progress, completed, failed).
*   `--created-before TEXT`: Clear tasks created before this date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).
*   `--created-after TEXT`: Clear tasks created after this date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).
*   `--metadata / -m TEXT`: Filter by metadata in key=value format (can be specified multiple times).
*   `--all`: Clear all tasks (required if no other filters specified).
*   `--force / -f`: Skip confirmation prompt.

**Examples:**

```bash
# Clear all completed tasks
sparky agent tasks clear --status completed

# Clear old failed tasks
sparky agent tasks clear --status failed --created-before 2024-01-01

# Clear tasks with specific metadata
sparky agent tasks clear --metadata source=manual --force

# Clear all tasks (requires --all flag)
sparky agent tasks clear --all --force
```

### Scheduled Task Management Commands

All scheduled task management commands are organized under `sparky agent schedule`.

#### `sparky agent schedule list`

List all scheduled tasks from the configuration file.

**Usage:**

```
sparky agent schedule list
```

**Example:**

```bash
sparky agent schedule list
```

#### `sparky agent schedule show`

Show detailed information about a specific scheduled task.

**Usage:**

```
sparky agent schedule show <NAME>
```

**Arguments:**

*   `NAME`: Name of the scheduled task to show.

**Example:**

```bash
sparky agent schedule show smart_maintenance
```

#### `sparky agent schedule run`

Submit scheduled tasks to the agent queue for execution.

**Usage:**

```
sparky agent schedule run [OPTIONS] [TASK_NAMES]...
```

**Options:**

*   `--all / -a`: Run all enabled tasks from `scheduled_tasks.yaml`.

**Arguments:**

*   `TASK_NAMES...`: Names of tasks to run.

**Examples:**

```bash
# Run a specific scheduled task
sparky agent schedule run smart_maintenance

# Run multiple scheduled tasks
sparky agent schedule run curiosity gardener

# Run all enabled scheduled tasks
sparky agent schedule run --all
```

#### `sparky agent schedule add`

Add a new scheduled task to the configuration.

**Usage:**

```
sparky agent schedule add <NAME> <INTERVAL> <PROMPT> [OPTIONS]
```

**Arguments:**

*   `NAME`: Unique name for the scheduled task.
*   `INTERVAL`: Interval specification (e.g., `every(1 hour)`, `cron(0 * * * *)`, or cycles).
*   `PROMPT`: Prompt text or file reference (e.g., `file(prompts/task.md)`).

**Options:**

*   `--metadata / -m TEXT`: Metadata in key=value format (can be specified multiple times).
*   `--disabled`: Create the task in disabled state.

**Examples:**

```bash
# Add a new scheduled task with time-based interval
sparky agent schedule add my_task "every(2 hours)" "file(prompts/my_task.md)" --metadata source=auto

# Add a task with cron schedule
sparky agent schedule add daily_task "cron(0 0 * * *)" "Daily maintenance task"

# Add a disabled task
sparky agent schedule add future_task "every(1 day)" "file(prompts/future.md)" --disabled
```

#### `sparky agent schedule delete`

Delete a scheduled task from the configuration.

**Usage:**

```
sparky agent schedule delete <NAME> [OPTIONS]
```

**Arguments:**

*   `NAME`: Name of the scheduled task to delete.

**Options:**

*   `--force / -f`: Skip confirmation prompt.

**Example:**

```bash
sparky agent schedule delete old_task --force
```

#### `sparky agent schedule enable`

Enable a scheduled task.

**Usage:**

```
sparky agent schedule enable <NAME>
```

**Arguments:**

*   `NAME`: Name of the scheduled task to enable.

**Example:**

```bash
sparky agent schedule enable curiosity
```

#### `sparky agent schedule disable`

Disable a scheduled task.

**Usage:**

```
sparky agent schedule disable <NAME>
```

**Arguments:**

*   `NAME`: Name of the scheduled task to disable.

**Example:**

```bash
sparky agent schedule disable smart_maintenance
```
