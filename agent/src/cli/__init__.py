"""Sparky CLI - Modular command-line interface."""

import typer
from dotenv import load_dotenv

from sparky.logging_config import setup_logging
from cli.agent import agent
from cli.chat import chat
from cli.client import client
from cli.db import db
from cli.generate import app as generate_app
from cli.models import app as models_app
from cli.utils import app as utils_app

# Load environment variables and setup logging
load_dotenv()
setup_logging()

# Create the main app
app = typer.Typer(
    name="sparky",
    help="🤖 Sparky - Build bots with Google GenAI and MCP",
    add_completion=False,
)

# Add command groups
app.add_typer(chat, name="chat")
app.add_typer(client, name="client")
app.add_typer(agent, name="agent")
app.add_typer(db, name="db")

# Add single commands as subcommands
app.command("generate", help="Generate a one-off response from a prompt")(
    generate_app.registered_commands[0].callback
)
app.command("list-models", help="List available Google AI models")(
    models_app.registered_commands[0].callback
)
app.command("test", help="Test your Sparky setup")(
    utils_app.registered_commands[0].callback
)
app.command("version", help="Show Sparky version")(
    utils_app.registered_commands[1].callback
)
app.command("mcp", help="Manage MCP server configuration")(
    utils_app.registered_commands[2].callback
)


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
