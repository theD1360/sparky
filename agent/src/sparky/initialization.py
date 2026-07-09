"""Shared initialization logic for Sparky components.

This module provides common initialization routines used by both the chat server
and the agent to ensure consistent toolchain and knowledge setup.
"""

import asyncio
import os
import traceback
from logging import getLogger
from typing import List, Optional, Tuple

from badmcp.config import MCPConfig
from database.database import get_database_manager
from database.repository import KnowledgeRepository
from services import KnowledgeService
from sparky.langchain_toolchain import LangChainToolchain
from sparky.mcp_toolkit import log_mcp_startup_diagnostics

logger = getLogger(__name__)


async def create_langchain_toolchain(
    tools: List[str] = None,
    log_prefix: str = "startup",
) -> Tuple[Optional[LangChainToolchain], Optional[str]]:
    """Create a LangChain toolchain with all configured MCP servers.

    Args:
        tools: List of server names to include. If None, all servers will be included.
        log_prefix: Prefix for log messages (e.g., "startup", "agent")

    Returns:
        Tuple of (toolchain, error_message)
        - toolchain: LangChainToolchain instance or None on failure
        - error_message: Error message if initialization failed, None on success
    """
    try:
        logger.info(f"[{log_prefix}] Creating LangChain toolchain...")
        mcp_config = MCPConfig()
        all_servers = mcp_config.get_all_servers()

        # Filter servers if tools list is provided
        if tools is not None:
            servers = {
                name: config for name, config in all_servers.items() if name in tools
            }
        else:
            servers = all_servers

        if not servers:
            error_msg = "No MCP servers configured"
            logger.error(f"[{log_prefix}] {error_msg}")
            return None, error_msg

        logger.info(
            f"[{log_prefix}] Creating toolchain with {len(servers)} server(s): {', '.join(servers.keys())}"
        )

        toolchain = LangChainToolchain.from_mcp_config(servers)
        await log_mcp_startup_diagnostics()
        logger.info(f"[{log_prefix}] LangChain toolchain created successfully")

        return toolchain, None

    except Exception as e:
        error_msg = f"Error creating LangChain toolchain: {type(e).__name__}: {e}"
        logger.error(f"[{log_prefix}] {error_msg}")
        logger.error(f"[{log_prefix}] Traceback: {traceback.format_exc()}")
        return None, error_msg


async def initialize_toolchain_with_knowledge(
    session_id: str = "server",
    log_prefix: str = "startup",
):
    """Initialize toolchain and Knowledge module.

    This is the full initialization used by the chat server, which includes
    the Knowledge module setup.

    Args:
        session_id: Session identifier for the Knowledge module
        log_prefix: Prefix for log messages

    Returns:
        Tuple of (toolchain, knowledge, error_message)
    """
    # Create toolchain
    toolchain, error = await create_langchain_toolchain(log_prefix=log_prefix)
    if error:
        return None, None, error

    try:
        # Initialize Knowledge module
        logger.info(f"[{log_prefix}] Initializing shared Knowledge module...")

        # Create repository first
        db_url = os.getenv("SPARKY_DB_URL")
        if not db_url:
            logger.warning(
                f"[{log_prefix}] SPARKY_DB_URL not set, KnowledgeService will not be initialized"
            )
            knowledge = None
        else:
            db_manager = get_database_manager(db_url=db_url)
            db_manager.connect()
            repository = KnowledgeRepository(db_manager)

            knowledge = KnowledgeService(
                repository=repository,
                session_id=session_id,
                model=None,  # Will be set per-connection for chat server
                auto_memory=True,
            )
            logger.info(f"[{log_prefix}] Initialized KnowledgeService with repository")

        return toolchain, knowledge, None

    except Exception as e:
        error_msg = f"Error initializing knowledge: {type(e).__name__}: {e}"
        logger.error(f"[{log_prefix}] {error_msg}")
        logger.error(f"[{log_prefix}] Traceback: {traceback.format_exc()}")
        return toolchain, None, error_msg
