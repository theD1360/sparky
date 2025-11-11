"""Shared utilities and helpers for the Sparky CLI."""

import logging
from typing import List

from rich.console import Console

from sparky.initialization import initialize_toolchain

# Shared console and logger
console = Console(record=True)
logger = logging.getLogger(__name__)


# Constants
# Use /tmp for PID file in containers to avoid persistence issues
# Check if running in Docker by looking for /.dockerenv or checking cgroup
def _get_pid_file_path():
    """Determine appropriate PID file location."""
    import os

    # If in Docker, use /tmp which doesn't persist across restarts
    if os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv"):
        return "/tmp/sparky-agent.pid"
    # Otherwise use current directory
    return "agent.pid"


AGENT_PID_FILE = _get_pid_file_path()


async def initialize_agent_toolchain(tools: List[str] = None):
    """Initialize and return the MCP toolchain for the agent.

    Uses the same initialization logic as the chat server to ensure
    consistency in tools and configuration.
    """
    toolchain, error = await initialize_toolchain(tools=tools, log_prefix="agent")
    if error:
        raise Exception(error)
    return toolchain
