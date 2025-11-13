"""Agent management commands for Sparky CLI."""

import atexit
import os
import signal
from pathlib import Path
from typing import List, Optional

import psutil
import typer
from daemon import DaemonContext
from daemon.pidfile import PIDLockFile
from rich.table import Table

from sparky.scheduled_tasks import load_scheduled_tasks
from sparky.task_queue import create_task_queue
from sparky.constants import SPARKY_AGENT_PID_FILE
from cli.common import console, initialize_agent_toolchain, logger
from servers.task import TaskServer
from utils.async_util import run_async

agent = typer.Typer(name="agent", help="Manage the proactive agent background tasks")


@agent.command("start")
def start_agent(
    daemon: bool = typer.Option(
        False, "--daemon", "-d", help="Run the agent in the background as a daemon."
    ),
    poll_interval: int = typer.Option(
        10, "--interval", "-i", help="Seconds to wait between polling for tasks."
    ),
):
    """Start the proactive agent loop to process background tasks."""
    os.makedirs("logs", exist_ok=True)
    pidfile = PIDLockFile(SPARKY_AGENT_PID_FILE)

    # Check for stale PID file
    if pidfile.is_locked():
        # Verify the process is actually running
        try:
            with open(SPARKY_AGENT_PID_FILE, "r") as f:
                pid = int(f.read().strip())

            if not psutil.pid_exists(pid):
                logger.warning(
                    f"Found stale PID file with non-existent process {pid}. Cleaning up."
                )
                pidfile.break_lock()
            else:
                logger.warning("Agent is already running (PID file locked).")
                logger.info("To stop the agent, run: sparky agent stop")
                raise typer.Exit(1)
        except (IOError, ValueError) as e:
            logger.warning(f"Invalid PID file. Cleaning up. Error: {e}")
            pidfile.break_lock()

    async def run_agent():
        """Async function to run the agent loop."""
        toolchain = await initialize_agent_toolchain()
        server = TaskServer(toolchain, poll_interval=poll_interval)
        await server.run()

    if not daemon:
        # Foreground mode with signal handling
        shutdown_requested = False

        def cleanup_pidfile():
            """Ensure PID file is cleaned up."""
            if pidfile.is_locked():
                try:
                    pidfile.release()
                    logger.info("PID file cleaned up")
                except Exception as e:
                    logger.warning(f"Error releasing PID file: {e}")

        def signal_handler(signum, frame):
            """Handle shutdown signals."""
            nonlocal shutdown_requested
            sig_name = signal.Signals(signum).name
            logger.info(f"\nReceived {sig_name}, shutting down gracefully...")
            shutdown_requested = True
            cleanup_pidfile()
            raise SystemExit(0)

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        # Register cleanup to run on exit
        atexit.register(cleanup_pidfile)

        try:
            logger.info("Starting agent in foreground. Press Ctrl+C to stop.")
            pidfile.acquire()
            run_async(run_agent())
        except (KeyboardInterrupt, SystemExit):
            if not shutdown_requested:
                logger.info("\nAgent stopped by user.")
        except Exception as e:
            logger.error(f"Agent error: {e}", exc_info=True)
        finally:
            cleanup_pidfile()
            logger.info("✓ Agent stopped.")
    else:
        # Daemon mode
        logger.info(f"Starting agent as a daemon. PID file: {SPARKY_AGENT_PID_FILE}")
        log_file = os.path.join("logs", "agent.log")

        with DaemonContext(
            working_directory=os.getcwd(),
            pidfile=pidfile,
            stdout=open(log_file, "a+"),
            stderr=open(log_file, "a+"),
        ):
            run_async(run_agent())


@agent.command("stop")
def stop_agent():
    """Stop the background agent loop."""
    if not os.path.exists(SPARKY_AGENT_PID_FILE):
        logger.warning("Agent is not running (PID file not found).")
        raise typer.Exit()

    try:
        with open(SPARKY_AGENT_PID_FILE, "r") as f:
            pid = int(f.read().strip())
    except (IOError, ValueError):
        logger.error("Error reading PID file. Cleaning up.")
        os.remove(SPARKY_AGENT_PID_FILE)
        raise typer.Exit(1)

    if not psutil.pid_exists(pid):
        logger.warning(f"Agent process {pid} not found. Cleaning up stale PID file.")
        os.remove(SPARKY_AGENT_PID_FILE)
        raise typer.Exit()

    try:
        proc = psutil.Process(pid)
        logger.info(f"Sending termination signal to agent process {pid}...")
        proc.terminate()

        try:
            proc.wait(timeout=10)
            logger.info(f"✓ Agent process {pid} stopped gracefully.")
        except psutil.TimeoutExpired:
            logger.warning("Graceful shutdown timed out. Forcing termination...")
            proc.kill()
            proc.wait(timeout=5)
            logger.info(f"✓ Agent process {pid} forcefully terminated.")

    except psutil.NoSuchProcess:
        logger.warning(f"Agent process {pid} was already gone.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise typer.Exit(1)
    finally:
        if os.path.exists(SPARKY_AGENT_PID_FILE):
            os.remove(SPARKY_AGENT_PID_FILE)


@agent.command("status")
def agent_status():
    """Check if the agent is running and show task statistics."""
    # Check if agent is running
    if os.path.exists(SPARKY_AGENT_PID_FILE):
        try:
            with open(SPARKY_AGENT_PID_FILE, "r") as f:
                pid = int(f.read().strip())
            if psutil.pid_exists(pid):
                logger.info(f"✓ Agent is running (PID: {pid})")
            else:
                logger.warning(f"✗ Agent PID file exists but process {pid} not found")
        except Exception as e:
            logger.error(f"Error checking agent status: {e}")
    else:
        logger.info("✗ Agent is not running")

    # Show task statistics
    try:

        async def _get_stats():
            task_queue = create_task_queue()
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


@agent.command("list-tasks")
def list_agent_tasks(
    status_filter: Optional[str] = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (pending, in_progress, completed, failed)",
    ),
):
    """List all tasks in the agent's queue."""

    try:

        async def _get_tasks():
            task_queue = create_task_queue()
            return await task_queue.get_all_tasks()

        tasks = run_async(_get_tasks())

        if status_filter:
            tasks = [t for t in tasks if t.get("status") == status_filter]

        if not tasks:
            logger.info("No tasks found.")
            return

        table = Table(title="Agent Task Queue")
        table.add_column("ID", style="cyan", no_wrap=True, max_width=36)
        table.add_column("Tool", style="magenta")
        table.add_column("Status", style="yellow")
        table.add_column("Created", style="green")
        table.add_column("Updated", style="blue")

        for task in tasks:
            table.add_row(
                task.get("id", "")[:36],
                task.get("tool_name", ""),
                task.get("status", ""),
                task.get("created_at", "")[:19] if task.get("created_at") else "",
                task.get("updated_at", "")[:19] if task.get("updated_at") else "",
            )

        console.print(table)

    except Exception as e:
        logger.error(f"Error retrieving tasks: {e}")
        raise typer.Exit(1)


@agent.command("add-task")
def add_agent_task(
    instructions: str = typer.Argument(
        ..., help="A prompt that describes the task to be performed"
    ),
):
    """Add a new task to the agent's queue."""

    async def _add_task():
        task_queue = create_task_queue()
        return await task_queue.add_task(instruction=instructions)

    try:
        task = run_async(_add_task())
    except Exception as e:
        logger.error(f"Error adding task: {e}")
        raise typer.Exit(1)
    logger.info(f"✓ Added task {task['id']}")
    logger.info(f"  Status: {task['status']}")


@agent.command("clear-completed")
def clear_agent_completed(
    keep_failed: bool = typer.Option(
        True, "--keep-failed", help="Keep failed tasks for debugging"
    ),
):
    """Clear completed tasks from the queue."""

    try:

        async def _clear_tasks():
            task_queue = create_task_queue()
            return await task_queue.clear_completed_tasks(keep_failed=keep_failed)

        count = run_async(_clear_tasks())
        logger.info(f"✓ Cleared {count} completed task(s)")
    except Exception as e:
        logger.error(f"Error clearing tasks: {e}")
        raise typer.Exit(1)


@agent.command("schedule")
def schedule_tasks(
    task_names: Optional[List[str]] = typer.Argument(
        None, help="Names of tasks to schedule (as defined in scheduled_tasks.yaml)"
    ),
    all_tasks: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Schedule all enabled tasks from scheduled_tasks.yaml",
    ),
):
    """Schedule tasks from scheduled_tasks.yaml to run in the agent queue."""

    async def run_schedule():
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
            logger.info("  sparky agent schedule <task-name> [<task-name> ...]")
            logger.info("  sparky agent schedule --all")
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
        task_queue = create_task_queue()

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
        count = run_async(run_schedule())
        if count > 0:
            logger.info(f"\n✓ Successfully scheduled {count} task(s)")
    except Exception as e:
        logger.error(f"Error scheduling tasks: {e}")
        raise typer.Exit(1)


@agent.command("stats")
def agent_statistics():
    """Show detailed agent loop statistics including curiosity cycles."""

    try:

        async def _get_stats():
            task_queue = create_task_queue()
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
