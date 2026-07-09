"""Shared utilities and helpers for the Sparky CLI."""

import logging
from typing import List

from rich.console import Console
from sparky.initialization import create_langchain_toolchain

# Shared console and logger
console = Console(record=True)
logger = logging.getLogger(__name__)


async def initialize_agent_toolchain(tools: List[str] = None):
    """Initialize and return the LangChain toolchain for the agent.

    Uses the same initialization logic as the chat server to ensure
    consistency in tools and configuration.
    """
    toolchain, error = await create_langchain_toolchain(tools=tools, log_prefix="agent")
    if error:
        raise Exception(error)
    return toolchain
