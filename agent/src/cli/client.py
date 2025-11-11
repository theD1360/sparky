"""Client commands for Sparky CLI."""

from typing import Optional

import typer

from utils.async_util import run_async
from client import run_textual_client

client = typer.Typer(name="client", help="Chat client commands")


@client.command("start")
def start_client(
    host: str = typer.Option(
        "127.0.0.1", "--host", help="Host to bind the chat server to."
    ),
    port: int = typer.Option(8000, "--port", help="Port to bind the chat server to."),
    personality: Optional[str] = typer.Option(
        None, "--personality", help="Optional bot personality to set on connect."
    ),
    session_id: Optional[str] = typer.Option(
        None,
        "--session-id",
        help="Optional session ID to reconnect to existing session.",
    ),
):
    """Start the chat client. By default uses the Textual TUI."""
    run_async(run_textual_client(host, port, personality, session_id))
