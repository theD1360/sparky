"""Shared utilities and helpers for the Sparky CLI."""

import logging
from typing import List

from rich.console import Console
from sparky.constants import SPARKY_AGENT_PID_FILE
from sparky.initialization import initialize_toolchain

# Shared console and logger
console = Console(record=True)
logger = logging.getLogger(__name__)

AGENT_PID_FILE = SPARKY_AGENT_PID_FILE


async def initialize_agent_toolchain(tools: List[str] = None):
    """Initialize and return the MCP toolchain for the agent.

    Uses the same initialization logic as the chat server to ensure
    consistency in tools and configuration.
    """
    toolchain, error = await initialize_toolchain(tools=tools, log_prefix="agent")
    if error:
        raise Exception(error)
    return toolchain
