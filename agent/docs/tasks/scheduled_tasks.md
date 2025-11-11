# Scheduled Tasks

The Sparky agent can be configured to run tasks periodically based on a schedule. This is useful for automating routine maintenance, analysis, and self-improvement tasks.

## Configuration

Scheduled tasks are defined in the `scheduled_tasks.yaml` file in the root of the project directory. This file contains a list of tasks, each with its own schedule, prompt, and metadata.

### Task Structure

Each task in the `scheduled_tasks` list is a dictionary with the following keys:

*   **`name`**: A unique name for the task (e.g., `reflection`, `curiosity`).
*   **`interval`**: The schedule for the task. This can be specified in one of three ways:
    *   **Cycles**: A simple integer representing the number of agent loops to wait between runs (e.g., `50`).
    *   **Time-based**: A string in the format `every(X unit)`, where `X` is a number and `unit` is `second`, `minute`, `hour`, or `day` (e.g., `every(1 hour)`).
    *   **Cron Expression**: A standard cron expression in the format `cron(MINUTE HOUR DAY MONTH DAY_OF_WEEK)` (e.g., `cron(0 */2 * * *)`).
*   **`prompt`**: The instructions for the task. This can be either:
    *   An inline string.
    *   A reference to a file containing the prompt, using the format `file(path/to/prompt.md)`.
*   **`metadata`**: An optional dictionary of key-value pairs to attach to the task.
*   **`enabled`**: A boolean (`true` or `false`) to enable or disable the task.

### Example Configuration

```yaml
scheduled_tasks:
  - name: reflection
    interval: every(1 hour)
    prompt: file(prompts/reflection_prompt.md)
    metadata:
      source: self_reflection
    enabled: true

  - name: integrated_reflection
    interval: cron(0 0 * * *) # Run daily at midnight
    prompt: "Summarize the previous day's activities and learnings."
    metadata:
      source: daily_summary
    enabled: true
```

## How it Works

The agent's main loop in `task_server.py` loads the scheduled tasks from `scheduled_tasks.yaml` using the `load_scheduled_tasks` function from `scheduled_tasks.py`.

For each task, the `should_run()` method of the `ScheduledTask` class is called on every cycle of the agent loop. This method checks the task's interval and determines if it's time to run the task.

If `should_run()` returns `true`, the task's prompt is resolved, and a new task is added to the main task queue for execution.
