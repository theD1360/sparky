"""Admin API endpoints for system management."""

import os
import sys
from datetime import datetime
from logging import getLogger
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available, system metrics will be limited")

logger = getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class EnvVarInfo(BaseModel):
    """Environment variable information."""

    key: str
    value: str
    description: Optional[str] = None


class EnvVarUpdate(BaseModel):
    """Environment variable update request."""

    value: str


class SystemInfoResponse(BaseModel):
    """System information response."""

    python_version: str
    platform: str
    uptime_seconds: float
    memory_used_mb: float
    memory_total_mb: float
    memory_percent: float
    disk_used_gb: float
    disk_total_gb: float
    disk_percent: float
    active_sessions: int
    total_connections: int


class CacheStatusResponse(BaseModel):
    """Tool cache status response."""

    success: bool
    cache_initialized: bool
    servers: Dict
    total_servers: int


class ServerReloadResponse(BaseModel):
    """Server reload response."""

    success: bool
    message: str
    server_name: str


# Environment variable descriptions
ENV_VAR_DESCRIPTIONS = {
    "AGENT_MODEL": "LLM model to use for agent (e.g., gemini-2.0-flash)",
    "SPARKY_ENABLE_AGENT_LOOP": "Enable background agent loop for scheduled tasks",
    "SPARKY_AGENT_POLL_INTERVAL": "Agent loop polling interval in seconds",
    "SPARKY_TOOL_CACHE_TTL": "Tool cache TTL in minutes",
    "GEMINI_API_KEY": "Google Gemini API key (hidden for security)",
    "DATABASE_URL": "Database connection URL (hidden for security)",
    "LOG_LEVEL": "Logging level (DEBUG, INFO, WARNING, ERROR)",
}

# Sensitive keys that should be masked
SENSITIVE_KEYS = {
    "GEMINI_API_KEY",
    "DATABASE_URL",
    "API_KEY",
    "SECRET",
    "PASSWORD",
    "TOKEN",
}


@router.get("/tool_cache_status", response_model=CacheStatusResponse)
async def get_tool_cache_status():
    """Get status of toolchains (per-websocket).

    Returns:
        Dictionary with toolchain status
    """
    try:
        from servers.chat.chat_server import _connection_manager

        if _connection_manager and _connection_manager.langchain_toolchains:
            # Return info about active toolchains
            toolchains_info = {}
            for user_id, toolchain in _connection_manager.langchain_toolchains.items():
                toolchains_info[user_id] = {
                    "active": True,
                    "server_count": len(toolchain.client.connections),
                }
            return {
                "success": True,
                "cache_initialized": True,
                "servers": toolchains_info,
                "total_servers": sum(
                    len(tc.client.connections)
                    for tc in _connection_manager.langchain_toolchains.values()
                ),
            }
        else:
            return {
                "success": True,
                "cache_initialized": False,
                "servers": {},
                "total_servers": 0,
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "cache_initialized": False,
            "servers": {},
            "total_servers": 0,
        }


@router.post("/servers/{server_name}/reload")
async def reload_server(server_name: str) -> ServerReloadResponse:
    """Force reload a specific MCP server.

    Note: With per-websocket toolchains, this will reload for all active connections.

    Args:
        server_name: Name of the server to reload

    Returns:
        Reload status and message
    """
    try:
        from servers.chat.chat_server import _connection_manager

        if not _connection_manager or not _connection_manager.langchain_toolchains:
            return ServerReloadResponse(
                success=False,
                message="No active toolchains to reload",
                server_name=server_name,
            )

        # Reload toolchains for all active connections
        # This requires recreating the toolchain
        reloaded_count = 0
        for user_id in list(_connection_manager.langchain_toolchains.keys()):
            try:
                # Recreate toolchain for this user
                from sparky.initialization import create_langchain_toolchain
                from sparky.mcp_toolkit import clear_mcp_tool_cache

                clear_mcp_tool_cache()

                new_toolchain, error = await create_langchain_toolchain(
                    log_prefix=f"[reload:{user_id}]"
                )
                if new_toolchain and not error:
                    _connection_manager.langchain_toolchains[user_id] = new_toolchain
                    reloaded_count += 1
            except Exception as e:
                logger.error(f"Error reloading toolchain for {user_id}: {e}")

        if reloaded_count > 0:
            return ServerReloadResponse(
                success=True,
                message=f"Server '{server_name}' reloaded for {reloaded_count} connection(s)",
                server_name=server_name,
            )
        else:
            return ServerReloadResponse(
                success=False,
                message=f"Failed to reload server '{server_name}'",
                server_name=server_name,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reloading server: {str(e)}")


@router.get("/env", response_model=List[EnvVarInfo])
async def list_env_vars():
    """List environment variables (filtered for relevant ones).

    Returns:
        List of environment variables with descriptions
    """
    try:
        logger.info("Fetching environment variables...")
        env_vars = []

        # Get relevant environment variables
        for key, description in ENV_VAR_DESCRIPTIONS.items():
            value = os.getenv(key, "")

            # Mask sensitive values
            if any(sensitive in key.upper() for sensitive in SENSITIVE_KEYS):
                if value:
                    value = "***" + value[-4:] if len(value) > 4 else "****"

            env_vars.append(
                EnvVarInfo(
                    key=key,
                    value=value if value else "(not set)",
                    description=description,
                )
            )

        logger.info(f"Fetched {len(env_vars)} environment variables")
        return env_vars
    except Exception as e:
        logger.error(f"Error fetching env vars: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error fetching env vars: {str(e)}"
        )


@router.put("/env/{key}")
async def update_env_var(key: str, update: EnvVarUpdate):
    """Update an environment variable (runtime only, not persistent).

    Args:
        key: Environment variable key
        update: New value

    Returns:
        Success status
    """
    try:
        # Security: Only allow updating known safe variables
        if any(sensitive in key.upper() for sensitive in SENSITIVE_KEYS):
            raise HTTPException(
                status_code=403,
                detail="Cannot update sensitive environment variables through API",
            )

        # Update runtime environment
        os.environ[key] = update.value

        return {
            "success": True,
            "message": f"Environment variable '{key}' updated to '{update.value}' (runtime only)",
            "key": key,
            "value": update.value,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating env var: {str(e)}")


@router.get("/system", response_model=SystemInfoResponse)
async def get_system_info():
    """Get system information and metrics.

    Returns:
        System information including memory, disk, and process stats
    """
    try:
        logger.info("Fetching system information...")

        if not PSUTIL_AVAILABLE:
            logger.error("psutil not available")
            raise HTTPException(
                status_code=503,
                detail="psutil library not available - cannot get system metrics",
            )

        # Get process info
        process = psutil.Process()
        logger.debug(f"Got process: PID {process.pid}")

        # Get system memory info
        mem = psutil.virtual_memory()
        memory_used_mb = mem.used / (1024 * 1024)
        memory_total_mb = mem.total / (1024 * 1024)
        memory_percent = mem.percent
        logger.debug(
            f"Memory: {memory_percent}% ({memory_used_mb:.0f} / {memory_total_mb:.0f} MB)"
        )

        # Get disk info
        disk = psutil.disk_usage("/")
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_total_gb = disk.total / (1024 * 1024 * 1024)
        disk_percent = disk.percent
        logger.debug(
            f"Disk: {disk_percent}% ({disk_used_gb:.1f} / {disk_total_gb:.1f} GB)"
        )

        # Get process uptime
        create_time = datetime.fromtimestamp(process.create_time())
        uptime = (datetime.now() - create_time).total_seconds()
        logger.debug(f"Uptime: {uptime:.0f} seconds")

        # Get connection manager stats
        active_sessions = 0
        total_connections = 0
        try:
            from servers.chat.chat_server import _connection_manager

            if _connection_manager:
                session_info = _connection_manager.get_session_info()
                active_sessions = session_info.get("total_sessions", 0)
                total_connections = session_info.get("active_connections", 0)
                logger.debug(
                    f"Sessions: {active_sessions}, Connections: {total_connections}"
                )
        except Exception as e:
            logger.warning(f"Could not get connection manager stats: {e}")

        result = SystemInfoResponse(
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            platform=sys.platform,
            uptime_seconds=uptime,
            memory_used_mb=memory_used_mb,
            memory_total_mb=memory_total_mb,
            memory_percent=memory_percent,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
            disk_percent=disk_percent,
            active_sessions=active_sessions,
            total_connections=total_connections,
        )
        logger.info("System information fetched successfully")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching system info: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error fetching system info: {str(e)}"
        )
