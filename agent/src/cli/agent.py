"""Agent management commands for Sparky CLI."""

from pathlib import Path
from typing import List, Optional

import typer
from cli.common import console, logger
from rich.table import Table
from sparky.scheduled_tasks import (
    add_scheduled_task,
    delete_scheduled_task,
    load_raw_config,
    load_scheduled_tasks,
    update_scheduled_task,
)
from sparky.task_queue import create_task_queue
from utils.async_util import run_async

agent = typer.Typer(name="agent", help="Manage the proactive agent background tasks")
tasks = typer.Typer(name="tasks", help="Manage agent task queue")
schedule = typer.Typer(name="schedule", help="Manage scheduled tasks")


@agent.command("status")
def agent_status():
    """Show task queue statistics."""
    logger.info("ℹ️  Agent loop runs within the chat server")
    logger.info("   Start with: SPARKY_ENABLE_AGENT_LOOP=true sparky chat")
    logger.info("")

    # Show task statistics
    try:

        async def _get_stats():
            task_queue = await create_task_queue()
            return await task_queue.get_task_stats()

        stats = run_async(_get_stats())
        logger.info("\nTask Queue Statistics:")
        logger.info(f"  Pending:     {stats['pending']}")
        logger.info(f"  In Progress: {stats['in_progress']}")
        logger.info(f"  Completed:   {stats['completed']}")
        logger.info(f"  Failed:      {stats['failed']}")
        logger.info(f"  Total:       {stats['total']}")
    except Exception as e:
        logger.error(f"Error retrieving task statistics: {e}")


@tasks.command("list")
def list_tasks(
    status_filter: Optional[str] = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (pending, in_progress, completed, failed)",
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        "-l",
        help="Maximum number of tasks to display",
    ),
):
    """List all tasks in the agent's queue."""

    try:

        async def _get_tasks():
            task_queue = await create_task_queue()
            return await task_queue.get_all_tasks()

        all_tasks = run_async(_get_tasks())

        if status_filter:
            all_tasks = [t for t in all_tasks if t.get("status") == status_filter]

        if limit:
            all_tasks = all_tasks[:limit]

        if not all_tasks:
            logger.info("No tasks found.")
            return

        table = Table(title="Agent Task Queue")
        table.add_column("ID", style="cyan", no_wrap=True, max_width=36)
        table.add_column("Instruction", style="white", max_width=50)
        table.add_column("Status", style="yellow")
        table.add_column("Created", style="green")
        table.add_column("Updated", style="blue")

        for task in all_tasks:
            instruction = task.get("instruction", "")
            if len(instruction) > 47:
                instruction = instruction[:47] + "..."

            table.add_row(
                task.get("id", "")[:36],
                instruction,
                task.get("status", ""),
                task.get("created_at", "")[:19] if task.get("created_at") else "",
                task.get("updated_at", "")[:19] if task.get("updated_at") else "",
            )

        console.print(table)
        logger.info(f"\nTotal: {len(all_tasks)} task(s)")

    except Exception as e:
        logger.error(f"Error retrieving tasks: {e}")
        raise typer.Exit(1)


@tasks.command("add")
def add_task(
    instruction: str = typer.Argument(
        ..., help="A prompt that describes the task to be performed"
    ),
    metadata_pairs: Optional[List[str]] = typer.Option(
        None,
        "--metadata",
        "-m",
        help="Metadata in key=value format (can be specified multiple times)",
    ),
    chat_id: Optional[str] = typer.Option(
        None,
        "--chat",
        "-c",
        help="Chat ID to execute the task in (task will appear in that chat)",
    ),
):
    """Add a new task to the agent's queue."""

    # Parse metadata if provided
    metadata = {}
    if metadata_pairs:
        for pair in metadata_pairs:
            if "=" not in pair:
                logger.error(f"Invalid metadata format: {pair}. Use key=value")
                raise typer.Exit(1)
            key, value = pair.split("=", 1)
            metadata[key.strip()] = value.strip()

    async def _add_task():
        task_queue = await create_task_queue()
        return await task_queue.add_task(
            instruction=instruction,
            metadata=metadata if metadata else None,
            chat_id=chat_id,
        )

    try:
        task = run_async(_add_task())
    except Exception as e:
        logger.error(f"Error adding task: {e}")
        raise typer.Exit(1)
    logger.info(f"✓ Added task {task['id']}")
    logger.info(f"  Status: {task['status']}")
    if chat_id:
        logger.info(f"  Chat ID: {chat_id}")
    if metadata:
        logger.info(f"  Metadata: {metadata}")


@tasks.command("get")
def get_task(
    task_id: str = typer.Argument(..., help="ID of the task to retrieve"),
):
    """Get detailed information about a specific task."""

    async def _get_task():
        task_queue = await create_task_queue()
        return await task_queue.get_task(task_id)

    try:
        task = run_async(_get_task())
        if not task:
            logger.error(f"Task {task_id} not found")
            raise typer.Exit(1)

        logger.info(f"\n📋 Task Details:")
        logger.info(f"  ID:          {task['id']}")
        logger.info(f"  Status:      {task['status']}")
        logger.info(f"  Instruction: {task['instruction']}")
        logger.info(f"  Created:     {task.get('created_at', 'N/A')}")
        logger.info(f"  Updated:     {task.get('updated_at', 'N/A')}")

        if task.get("metadata"):
            logger.info(f"  Metadata:")
            for key, value in task["metadata"].items():
                logger.info(f"    {key}: {value}")

        if task.get("response"):
            logger.info(f"  Response:    {task['response'][:100]}...")

        if task.get("error"):
            logger.info(f"  Error:       {task['error']}")

    except Exception as e:
        logger.error(f"Error retrieving task: {e}")
        raise typer.Exit(1)


@tasks.command("update")
def update_task(
    task_id: str = typer.Argument(..., help="ID of the task to update"),
    status: Optional[str] = typer.Option(
        None,
        "--status",
        "-s",
        help="New status (pending, in_progress, completed, failed)",
    ),
    instruction: Optional[str] = typer.Option(
        None,
        "--instruction",
        "-i",
        help="New instruction text",
    ),
    metadata_pairs: Optional[List[str]] = typer.Option(
        None,
        "--metadata",
        "-m",
        help="Metadata to update in key=value format (can be specified multiple times)",
    ),
    response: Optional[str] = typer.Option(
        None,
        "--response",
        "-r",
        help="Task response",
    ),
    error: Optional[str] = typer.Option(
        None,
        "--error",
        "-e",
        help="Error message",
    ),
):
    """Update one or more fields of a task atomically."""

    # Check that at least one field is being updated
    if not any([status, instruction, metadata_pairs, response, error]):
        logger.error("Must specify at least one field to update")
        raise typer.Exit(1)

    # Parse metadata if provided
    metadata = {}
    if metadata_pairs:
        for pair in metadata_pairs:
            if "=" not in pair:
                logger.error(f"Invalid metadata format: {pair}. Use key=value")
                raise typer.Exit(1)
            key, value = pair.split("=", 1)
            metadata[key.strip()] = value.strip()

    async def _update_task():
        task_queue = await create_task_queue()
        return await task_queue.update_task(
            task_id=task_id,
            status=status,
            instruction=instruction,
            metadata=metadata if metadata else None,
            response=response,
            error=error,
        )

    try:
        success = run_async(_update_task())
        if success:
            logger.info(f"✓ Updated task {task_id}")
            if status:
                logger.info(f"  Status: {status}")
            if instruction:
                logger.info(f"  Instruction: {instruction[:50]}...")
            if metadata:
                logger.info(f"  Metadata: {metadata}")
        else:
            logger.error(f"Failed to update task {task_id}")
            raise typer.Exit(1)
    except Exception as e:
        logger.error(f"Error updating task: {e}")
        raise typer.Exit(1)


@tasks.command("delete")
def delete_task(
    task_id: str = typer.Argument(..., help="ID of the task to delete"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
):
    """Delete a specific task from the queue."""

    async def _get_task():
        task_queue = await create_task_queue()
        return await task_queue.get_task(task_id), task_queue

    try:
        task, task_queue = run_async(_get_task())
        if not task:
            logger.error(f"Task {task_id} not found")
            raise typer.Exit(1)

        # Show task details
        logger.info(f"\nTask to delete:")
        logger.info(f"  ID:          {task['id']}")
        logger.info(f"  Status:      {task['status']}")
        logger.info(f"  Instruction: {task['instruction'][:50]}...")

        # Confirm deletion unless --force
        if not force:
            confirm = typer.confirm("\nAre you sure you want to delete this task?")
            if not confirm:
                logger.info("Cancelled.")
                return

        # Delete the task
        async def _delete_task():
            return await task_queue.delete_task(task_id)

        success = run_async(_delete_task())
        if success:
            logger.info(f"✓ Deleted task {task_id}")
        else:
            logger.error(f"Failed to delete task {task_id}")
            raise typer.Exit(1)

    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        raise typer.Exit(1)


@tasks.command("clear")
def clear_tasks(
    status: Optional[str] = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (pending, in_progress, completed, failed)",
    ),
    created_before: Optional[str] = typer.Option(
        None,
        "--created-before",
        help="Clear tasks created before this date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    ),
    created_after: Optional[str] = typer.Option(
        None,
        "--created-after",
        help="Clear tasks created after this date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    ),
    metadata_pairs: Optional[List[str]] = typer.Option(
        None,
        "--metadata",
        "-m",
        help="Filter by metadata in key=value format (can be specified multiple times)",
    ),
    all_tasks: bool = typer.Option(
        False,
        "--all",
        help="Clear all tasks (required if no other filters specified)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
):
    """Clear tasks from the queue with flexible filtering."""

    # Parse metadata filters if provided
    metadata_filters = {}
    if metadata_pairs:
        for pair in metadata_pairs:
            if "=" not in pair:
                logger.error(f"Invalid metadata format: {pair}. Use key=value")
                raise typer.Exit(1)
            key, value = pair.split("=", 1)
            metadata_filters[key.strip()] = value.strip()

    # Check that at least one filter is specified
    has_filters = status or created_before or created_after or metadata_filters
    if not has_filters and not all_tasks:
        logger.error(
            "Must specify at least one filter (--status, --created-before, --created-after, --metadata) or --all"
        )
        raise typer.Exit(1)

    async def _clear_tasks():
        task_queue = await create_task_queue()
        all_tasks_list = await task_queue.get_all_tasks()

        # Apply filters
        tasks_to_delete = []
        for task in all_tasks_list:
            # Apply status filter
            if status and task.get("status") != status:
                continue

            # Apply created_before filter
            if created_before:
                task_created = task.get("created_at", "")
                if task_created >= created_before:
                    continue

            # Apply created_after filter
            if created_after:
                task_created = task.get("created_at", "")
                if task_created <= created_after:
                    continue

            # Apply metadata filters
            if metadata_filters:
                task_metadata = task.get("metadata", {})
                matches = all(
                    task_metadata.get(k) == v for k, v in metadata_filters.items()
                )
                if not matches:
                    continue

            tasks_to_delete.append(task)

        return tasks_to_delete, task_queue

    try:
        tasks_to_delete, task_queue = run_async(_clear_tasks())

        if not tasks_to_delete:
            logger.info("No tasks match the specified filters.")
            return

        # Show what will be deleted
        logger.info(f"\n{len(tasks_to_delete)} task(s) will be deleted:")
        for task in tasks_to_delete[:5]:  # Show first 5
            logger.info(
                f"  - {task['id'][:8]}... ({task['status']}): {task['instruction'][:50]}..."
            )
        if len(tasks_to_delete) > 5:
            logger.info(f"  ... and {len(tasks_to_delete) - 5} more")

        # Confirm deletion unless --force
        if not force:
            confirm = typer.confirm("\nAre you sure you want to delete these tasks?")
            if not confirm:
                logger.info("Cancelled.")
                return

        # Delete tasks
        async def _delete_tasks():
            deleted = 0
            for task in tasks_to_delete:
                if await task_queue.delete_task(task["id"]):
                    deleted += 1
            return deleted

        deleted_count = run_async(_delete_tasks())
        logger.info(f"✓ Cleared {deleted_count} task(s)")

    except Exception as e:
        logger.error(f"Error clearing tasks: {e}")
        raise typer.Exit(1)


@schedule.command("list")
def list_scheduled_tasks():
    """List all scheduled tasks from configuration."""
    try:
        tasks = load_raw_config()

        if not tasks:
            logger.info("No scheduled tasks found.")
            return

        table = Table(title="Scheduled Tasks")
        table.add_column("Name", style="cyan")
        table.add_column("Interval", style="yellow")
        table.add_column("Status", style="green")
        table.add_column("Prompt", style="white", max_width=50)

        for task in tasks:
            status = "✓ enabled" if task.get("enabled", True) else "✗ disabled"
            prompt = task.get("prompt", "")
            if len(prompt) > 47:
                prompt = prompt[:47] + "..."

            table.add_row(
                task.get("name", ""),
                str(task.get("interval", "")),
                status,
                prompt,
            )

        console.print(table)
        logger.info(f"\nTotal: {len(tasks)} scheduled task(s)")

    except Exception as e:
        logger.error(f"Error listing scheduled tasks: {e}")
        raise typer.Exit(1)


@schedule.command("show")
def show_scheduled_task(
    name: str = typer.Argument(..., help="Name of the scheduled task to show"),
):
    """Show detailed information about a specific scheduled task."""
    try:
        tasks = load_raw_config()
        task = next((t for t in tasks if t.get("name") == name), None)

        if not task:
            logger.error(f"Scheduled task '{name}' not found")
            raise typer.Exit(1)

        logger.info(f"\n📋 Scheduled Task: {name}")
        logger.info(f"  Interval:  {task.get('interval', 'N/A')}")
        logger.info(f"  Enabled:   {task.get('enabled', True)}")
        logger.info(f"  Prompt:    {task.get('prompt', 'N/A')}")

        if task.get("metadata"):
            logger.info(f"  Metadata:")
            for key, value in task["metadata"].items():
                logger.info(f"    {key}: {value}")

    except Exception as e:
        logger.error(f"Error showing scheduled task: {e}")
        raise typer.Exit(1)


@schedule.command("run")
def run_scheduled_tasks(
    task_names: Optional[List[str]] = typer.Argument(
        None, help="Names of tasks to run (as defined in scheduled_tasks.yaml)"
    ),
    all_tasks: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Run all enabled tasks from scheduled_tasks.yaml",
    ),
):
    """Submit scheduled tasks to the agent queue for execution."""

    async def _run_schedule():
        # Load scheduled tasks from YAML
        scheduled_tasks = load_scheduled_tasks()

        if not scheduled_tasks:
            logger.error("No tasks found in scheduled_tasks.yaml")
            raise typer.Exit(1)

        # If no arguments, show available tasks
        if not task_names and not all_tasks:
            logger.info("Available scheduled tasks:")
            for task in scheduled_tasks:
                status = "✓ enabled" if task.enabled else "✗ disabled"
                logger.info(f"  - {task.name} ({status})")
            logger.info("\nUsage:")
            logger.info("  sparky agent schedule run <task-name> [<task-name> ...]")
            logger.info("  sparky agent schedule run --all")
            return 0

        # Determine which tasks to add
        tasks_to_add = []
        if all_tasks:
            # Add all enabled tasks
            tasks_to_add = [task for task in scheduled_tasks if task.enabled]
            if not tasks_to_add:
                logger.warning("No enabled tasks found in scheduled_tasks.yaml")
                return 0
        else:
            # Add specific tasks by name
            task_dict = {task.name: task for task in scheduled_tasks}
            for name in task_names:
                if name not in task_dict:
                    logger.error(f"Task '{name}' not found in scheduled_tasks.yaml")
                    logger.info(f"Available tasks: {', '.join(task_dict.keys())}")
                    raise typer.Exit(1)
                tasks_to_add.append(task_dict[name])

        # Create task queue
        task_queue = await create_task_queue()

        # Add each task to the queue
        added_count = 0
        for task in tasks_to_add:
            try:
                # Resolve the prompt (handles file() syntax)
                prompt = task.resolve_prompt(base_path=Path.cwd())

                # Add to task queue with metadata
                await task_queue.add_task(
                    instruction=prompt,
                    metadata={
                        "source": f"manual_{task.name}",
                        "scheduled_task_name": task.name,
                        **task.metadata,
                    },
                )
                logger.info(f"✓ Added task '{task.name}' to queue")
                added_count += 1
            except Exception as e:
                logger.error(f"✗ Failed to add task '{task.name}': {e}")

        return added_count

    try:
        count = run_async(_run_schedule())
        if count > 0:
            logger.info(f"\n✓ Successfully scheduled {count} task(s)")
    except Exception as e:
        logger.error(f"Error scheduling tasks: {e}")
        raise typer.Exit(1)


@schedule.command("add")
def add_scheduled_task_cmd(
    name: str = typer.Argument(..., help="Unique name for the scheduled task"),
    interval: str = typer.Argument(
        ...,
        help="Interval specification (e.g., 'every(1 hour)', 'cron(0 * * * *)', or cycles)",
    ),
    prompt: str = typer.Argument(
        ..., help="Prompt text or file reference (e.g., 'file(prompts/task.md)')"
    ),
    metadata_pairs: Optional[List[str]] = typer.Option(
        None,
        "--metadata",
        "-m",
        help="Metadata in key=value format (can be specified multiple times)",
    ),
    disabled: bool = typer.Option(
        False,
        "--disabled",
        help="Create the task in disabled state",
    ),
):
    """Add a new scheduled task to the configuration."""
    # Parse metadata if provided
    metadata = {}
    if metadata_pairs:
        for pair in metadata_pairs:
            if "=" not in pair:
                logger.error(f"Invalid metadata format: {pair}. Use key=value")
                raise typer.Exit(1)
            key, value = pair.split("=", 1)
            metadata[key.strip()] = value.strip()

    try:
        success = add_scheduled_task(
            name=name,
            interval=interval,
            prompt=prompt,
            metadata=metadata if metadata else None,
            enabled=not disabled,
        )

        if success:
            logger.info(f"✓ Added scheduled task '{name}'")
            logger.info(f"  Interval: {interval}")
            logger.info(f"  Status:   {'disabled' if disabled else 'enabled'}")
        else:
            logger.error(f"Failed to add scheduled task '{name}'")
            raise typer.Exit(1)

    except Exception as e:
        logger.error(f"Error adding scheduled task: {e}")
        raise typer.Exit(1)


@schedule.command("delete")
def delete_scheduled_task_cmd(
    name: str = typer.Argument(..., help="Name of the scheduled task to delete"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
):
    """Delete a scheduled task from the configuration."""
    try:
        # Check if task exists
        tasks = load_raw_config()
        task = next((t for t in tasks if t.get("name") == name), None)

        if not task:
            logger.error(f"Scheduled task '{name}' not found")
            raise typer.Exit(1)

        # Show task details
        logger.info(f"\nScheduled task to delete:")
        logger.info(f"  Name:     {name}")
        logger.info(f"  Interval: {task.get('interval', 'N/A')}")
        logger.info(f"  Prompt:   {task.get('prompt', 'N/A')[:50]}...")

        # Confirm deletion unless --force
        if not force:
            confirm = typer.confirm(
                "\nAre you sure you want to delete this scheduled task?"
            )
            if not confirm:
                logger.info("Cancelled.")
                return

        # Delete the task
        success = delete_scheduled_task(name)
        if success:
            logger.info(f"✓ Deleted scheduled task '{name}'")
        else:
            logger.error(f"Failed to delete scheduled task '{name}'")
            raise typer.Exit(1)

    except Exception as e:
        logger.error(f"Error deleting scheduled task: {e}")
        raise typer.Exit(1)


@schedule.command("enable")
def enable_scheduled_task_cmd(
    name: str = typer.Argument(..., help="Name of the scheduled task to enable"),
):
    """Enable a scheduled task."""
    try:
        success = update_scheduled_task(name, enabled=True)
        if success:
            logger.info(f"✓ Enabled scheduled task '{name}'")
        else:
            logger.error(f"Failed to enable scheduled task '{name}'")
            raise typer.Exit(1)
    except Exception as e:
        logger.error(f"Error enabling scheduled task: {e}")
        raise typer.Exit(1)


@schedule.command("disable")
def disable_scheduled_task_cmd(
    name: str = typer.Argument(..., help="Name of the scheduled task to disable"),
):
    """Disable a scheduled task."""
    try:
        success = update_scheduled_task(name, enabled=False)
        if success:
            logger.info(f"✓ Disabled scheduled task '{name}'")
        else:
            logger.error(f"Failed to disable scheduled task '{name}'")
            raise typer.Exit(1)
    except Exception as e:
        logger.error(f"Error disabling scheduled task: {e}")
        raise typer.Exit(1)


@agent.command("stats")
def agent_statistics():
    """Show detailed agent loop statistics including curiosity cycles."""

    try:

        async def _get_stats():
            task_queue = await create_task_queue()
            return await task_queue.get_task_stats()

        stats = run_async(_get_stats())

        logger.info("\n📊 Agent Statistics:")
        logger.info("\nTask Queue:")
        logger.info(f"  Pending:     {stats.get('pending', 0)}")
        logger.info(f"  In Progress: {stats.get('in_progress', 0)}")
        logger.info(f"  Completed:   {stats.get('completed', 0)}")
        logger.info(f"  Failed:      {stats.get('failed', 0)}")
        logger.info(f"  Total:       {stats.get('total', 0)}")

        if "loop_cycles" in stats:
            logger.info("\nAgent Loop:")
            logger.info(f"  Cycles:      {stats.get('loop_cycles', 0)}")
            logger.info(f"  Tasks Processed: {stats.get('tasks_processed', 0)}")
            logger.info(f"  Curiosity Enabled: {stats.get('curiosity_enabled', False)}")

    except Exception as e:
        logger.error(f"Error retrieving statistics: {e}")
        raise typer.Exit(1)


# Register the subcommand groups
agent.add_typer(tasks, name="tasks")
agent.add_typer(schedule, name="schedule")
