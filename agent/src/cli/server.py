"""Server management commands for Sparky CLI."""

import os
import sys

import psutil
import typer
import uvicorn
from cli.common import logger
from daemon import DaemonContext
from daemon.pidfile import PIDLockFile
from servers.chat import ChatServer
from sparky.constants import SPARKY_CHAT_PID_FILE

server = typer.Typer(name="server", help="Server management commands")


def run_server(host, port, daemon):
    """Helper function to run the server."""
    try:
        uvicorn.run(
            ChatServer,
            host=host,
            port=port,
            log_level="error" if daemon else "info",
        )
    except ImportError:
        logger.error(
            "Error: 'uvicorn' and 'websockets' are required to run the chat server."
        )
        logger.warning("Please ensure dependencies are installed.")
        return sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start chat server: {e}")
        return sys.exit(1)


@server.command("start")
def start_server(
    host: str = typer.Option(
        "127.0.0.1", "--host", help="Host to bind the chat server to."
    ),
    port: int = typer.Option(8000, "--port", help="Port to bind the chat server to."),
    daemon: bool = typer.Option(
        False, "--daemon", help="Run the server in the background."
    ),
    pidfile: str = typer.Option(
        SPARKY_CHAT_PID_FILE, "--pidfile", help="Path to the PID file."
    ),
):
    """Launch the Sparky Chat Server."""
    if not daemon:
        try:
            # Non-daemon mode - server will handle its own PID file
            logger.info(f"Starting Sparky Chat Server on ws://{host}:{port}/ws/chat")
            logger.info("Press Ctrl+C to stop.")
            run_server(host, port, daemon=False)

        except KeyboardInterrupt:
            logger.info("\nServer stopped by user.")
        finally:
            logger.info("✓ Server stopped.")

    else:
        # Daemon mode - use DaemonContext for process management
        lock = PIDLockFile(pidfile)
        with DaemonContext(working_directory=os.getcwd(), pidfile=lock):
            # In daemon mode, run with quieter logging
            # The server app will create its own PID file, but DaemonContext manages the daemon process
            run_server(host, port, daemon=False)


@server.command("stop")
def kill_server(
    pidfile: str = typer.Option(
        SPARKY_CHAT_PID_FILE, "--pidfile", help="Path to the PID file."
    )
):
    """Stop the Sparky Chat Server."""
    if not os.path.exists(pidfile):
        logger.warning("Server is not running (PID file not found).")
        raise typer.Exit()

    try:
        with open(pidfile, "r") as f:
            pid = int(f.read().strip())
    except (IOError, ValueError):
        logger.error("Error reading PID file.")
        # As a cleanup, remove the invalid PID file
        os.remove(pidfile)
        raise typer.Exit(1)

    if not psutil.pid_exists(pid):
        logger.warning(
            f"Server not running, but a stale PID file for process {pid} was found. Cleaning up."
        )
        os.remove(pidfile)
        raise typer.Exit()

    try:
        proc = psutil.Process(pid)
        logger.info(f"Sending termination signal to server process {pid}...")
        proc.terminate()  # Sends SIGTERM

        # Wait for graceful termination
        try:
            proc.wait(timeout=10)
            logger.info(f"✓ Server process {pid} stopped gracefully.")
        except psutil.TimeoutExpired:
            logger.warning(
                f"Graceful shutdown timed out. Forcing termination of process {pid}..."
            )
            proc.kill()  # Sends SIGKILL
            proc.wait(timeout=5)  # Wait for the OS to kill it
            logger.info(f"✓ Server process {pid} forcefully terminated.")

    except psutil.NoSuchProcess:
        logger.warning(f"Server process {pid} was already gone.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise typer.Exit(1)
    finally:
        # Final cleanup of the PID file
        if os.path.exists(pidfile):
            os.remove(pidfile)


@server.command("restart")
def restart_server(
    host: str = typer.Option(
        "127.0.0.1", "--host", help="Host to bind the chat server to."
    ),
    port: int = typer.Option(8000, "--port", help="Port to bind the chat server to."),
    daemon: bool = typer.Option(
        False, "--daemon", help="Run the server in the background."
    ),
    pidfile: str = typer.Option(
        SPARKY_CHAT_PID_FILE, "--pidfile", help="Path to the PID file."
    ),
):
    """Restart the Sparky Chat Server."""
    try:
        logger.info("Stopping Sparky Chat Server...")
        kill_server(pidfile=pidfile)
    except Exception:
        pass
    finally:
        logger.info(f"Restarting Sparky Chat Server on ws://{host}:{port}/ws/chat")
        start_server(host=host, port=port, daemon=daemon, pidfile=pidfile)
