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
from badmcp.tool_chain import ToolChain
from badmcp.tool_client import ToolClient
from database.database import get_database_manager
from database.repository import KnowledgeRepository
from services import KnowledgeService

logger = getLogger(__name__)


async def initialize_toolchain(
    tools: List[str] = None,
    log_prefix: str = "startup",
) -> Tuple[Optional[ToolChain], Optional[str]]:
    """Initialize the MCP toolchain with all configured servers.

    Args:
        tools: List of tool names to load, if None, all tools will be loaded
        log_prefix: Prefix for log messages (e.g., "startup", "agent")

    Returns:
        Tuple of (toolchain, error_message)
        - toolchain: Initialized ToolChain instance or None on failure
        - error_message: Error message if initialization failed, None on success
    """
    try:
        logger.info(f"[{log_prefix}] Loading MCP toolchain...")
        mcp_config = MCPConfig()
        servers = mcp_config.get_all_servers()
        if tools is None:
            tools = [ToolClient(s) for s in servers.values()]
        else:
            tools = [ToolClient(s) for s in servers.values() if s.name in tools]

        # Asynchronously start all clients in parallel using gather
        results = await asyncio.gather(
            *[tc.start() for tc in tools], return_exceptions=True
        )

        loaded_tools = []
        for tc, result in zip(tools, results):
            if isinstance(result, Exception):
                logger.error(
                    f"[{log_prefix}] Failed to load server '{tc.name}': {type(result).__name__}: {result}"
                )
                tb = traceback.format_exception(
                    type(result), result, result.__traceback__
                )
                logger.error(f"[{log_prefix}] Traceback: {''.join(tb)}")
            else:
                loaded_tools.append(tc)
                logger.info(f"[{log_prefix}] Successfully loaded tools from: {tc.name}")

        if not loaded_tools:
            error_msg = "No MCP servers loaded successfully"
            logger.error(f"[{log_prefix}] {error_msg}")
            return None, error_msg

        toolchain = ToolChain(loaded_tools)
        print(
            f"[{log_prefix}] Initializing toolchain (loading tools, prompts, and resources)..."
        )
        await toolchain.initialize()
        print(f"[{log_prefix}] Toolchain initialized")
        logger.info(
            f"[{log_prefix}] MCP toolchain initialized with {len(loaded_tools)}/{len(tools)} servers"
        )

        return toolchain, None

    except Exception as e:
        error_msg = f"Error initializing toolchain: {type(e).__name__}: {e}"
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
    # Initialize toolchain
    toolchain, error = await initialize_toolchain(log_prefix=log_prefix)
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
