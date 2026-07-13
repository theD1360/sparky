"""Load and cache LangChain tools from MCP servers via langchain-mcp-adapters."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from badmcp.config import MCPConfig
from badmcp.mcp_json import load_mcp_json_file, parse_mcp_json_to_connections
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

_MAX_TOOL_NAMES_LOG = 80
_MCP_LOAD_RETRY_TTL_SECONDS = float(
    os.getenv("SPARKY_MCP_LOAD_RETRY_TTL_SECONDS", "300")
)

_mcp_tools_cache: Optional[List[BaseTool]] = None
_mcp_external_load_failed: bool = False
_mcp_external_load_failed_at: float | None = None


def format_tool_names_for_log(
    tools: Iterable[Any], *, max_names: int = _MAX_TOOL_NAMES_LOG
) -> str:
    """Sorted tool names for startup diagnostics (truncated if very long)."""
    names: list[str] = []
    for tool in tools:
        name = getattr(tool, "name", None)
        names.append(str(name) if name else type(tool).__name__)
    names.sort()
    if len(names) > max_names:
        return ", ".join(names[:max_names]) + f", … (+{len(names) - max_names} more)"
    return ", ".join(names) if names else "(none)"


def mcp_tool_name_prefix() -> Optional[str]:
    raw = (os.getenv("SPARKY_MCP_TOOL_NAME_PREFIX") or "").strip()
    return raw or None


def mcp_tool_allowlist() -> Optional[set[str]]:
    raw = (os.getenv("SPARKY_MCP_TOOL_ALLOWLIST") or "").strip()
    if not raw:
        return None
    allow = {item.strip() for item in raw.split(",") if item.strip()}
    return allow or None


def mcp_preload_at_startup() -> bool:
    return os.getenv("SPARKY_MCP_PRELOAD_AT_STARTUP", "false").lower() in (
        "1",
        "true",
        "yes",
    )


def resolved_mcp_config_path(config_path: Optional[str] = None) -> Path | None:
    """Resolve MCP JSON path from explicit path or MCPConfig search."""
    if config_path:
        path = Path(config_path).expanduser()
        return path if path.is_file() else None
    mcp_config = MCPConfig()
    if mcp_config.config_path and Path(mcp_config.config_path).is_file():
        return Path(mcp_config.config_path)
    return None


def mcp_config_to_connections(
    config_path: Optional[str] = None,
    *,
    server_names: Optional[List[str]] = None,
) -> Dict[str, dict[str, Any]]:
    """Build langchain-mcp-adapters connection map from Sparky MCP config."""
    path = resolved_mcp_config_path(config_path)
    if path is not None:
        connections = load_mcp_json_file(path)
    else:
        mcp_config = MCPConfig(config_path)
        raw_servers: dict[str, Any] = {}
        for name, server in mcp_config.get_all_servers().items():
            if server.disabled:
                continue
            entry: dict[str, Any] = {}
            if server.command:
                entry["command"] = server.command
                if server.args:
                    entry["args"] = server.args
                if server.env:
                    entry["env"] = server.env
            elif server.url:
                entry["url"] = server.url
                if server.transport:
                    entry["transport"] = server.transport
                elif server.type:
                    entry["type"] = server.type
                if server.headers:
                    entry["headers"] = server.headers
                if server.bearerToken:
                    entry["bearerToken"] = server.bearerToken
            raw_servers[name] = entry
        connections = parse_mcp_json_to_connections({"mcpServers": raw_servers})

    if server_names is not None:
        connections = {
            name: conn for name, conn in connections.items() if name in server_names
        }
    return connections


def _apply_allowlist(tools: List[BaseTool]) -> List[BaseTool]:
    allow = mcp_tool_allowlist()
    if not allow:
        return tools
    filtered = [tool for tool in tools if tool.name in allow]
    if len(filtered) < len(tools):
        logger.info(
            "MCP tool allowlist applied: %d -> %d tools",
            len(tools),
            len(filtered),
        )
    return filtered


def _mcp_load_failure_is_stale() -> bool:
    if not _mcp_external_load_failed or _mcp_external_load_failed_at is None:
        return False
    return (time.monotonic() - _mcp_external_load_failed_at) >= _MCP_LOAD_RETRY_TTL_SECONDS


async def load_mcp_langchain_tools_async(
    *,
    config_path: Optional[str] = None,
    server_names: Optional[List[str]] = None,
    tool_interceptors: Optional[list] = None,
) -> List[BaseTool]:
    """Load LangChain tools from configured MCP servers.

    Uses per-server discovery with timeouts (via ``LangChainToolchain``) so one
    bad/slow server cannot hang the whole load the way a single ``get_tools()``
    ``asyncio.gather`` does.
    """
    from sparky.langchain_toolchain import LangChainToolchain

    connections = mcp_config_to_connections(config_path, server_names=server_names)
    if not connections:
        raise ValueError("No usable MCP servers configured")

    logger.info(
        "MCP: loading tools from %d server(s): %s",
        len(connections),
        ", ".join(sorted(connections.keys())),
    )

    toolchain = LangChainToolchain.from_connections(
        connections,
        tool_interceptors=tool_interceptors,
    )
    tools = await toolchain.get_langchain_tools(gemini_safe=False)
    n_before = len(tools)
    tools = _apply_allowlist(tools)
    logger.info(
        "MCP: %d tool(s) for LLM (%d before allowlist) | %s",
        len(tools),
        n_before,
        format_tool_names_for_log(tools),
    )
    return list(tools)


async def ensure_mcp_tool_cache_async(
    *,
    config_path: Optional[str] = None,
    server_names: Optional[List[str]] = None,
    force: bool = False,
) -> List[BaseTool]:
    """Load MCP tools into the process cache if not yet loaded."""
    global _mcp_tools_cache, _mcp_external_load_failed, _mcp_external_load_failed_at

    if _mcp_tools_cache is not None and not force:
        return list(_mcp_tools_cache)

    if _mcp_external_load_failed and not force:
        if _mcp_load_failure_is_stale():
            logger.info("MCP toolkit: retrying external load after TTL")
            _mcp_external_load_failed = False
            _mcp_external_load_failed_at = None
        else:
            logger.debug("MCP toolkit: skipping external load (recent failure)")
            return list(_mcp_tools_cache or [])

    try:
        tools = await load_mcp_langchain_tools_async(
            config_path=config_path,
            server_names=server_names,
        )
        _mcp_tools_cache = tools
        return list(tools)
    except Exception as exc:
        _mcp_external_load_failed = True
        _mcp_external_load_failed_at = time.monotonic()
        _mcp_tools_cache = []
        logger.warning(
            "MCP toolkit: external server load failed (%s). "
            "Agent will continue without MCP tools until retry TTL expires.",
            exc,
        )
        return []


def clear_mcp_tool_cache() -> None:
    """Clear cached MCP tools (e.g. after admin reload)."""
    global _mcp_tools_cache, _mcp_external_load_failed, _mcp_external_load_failed_at
    _mcp_tools_cache = None
    _mcp_external_load_failed = False
    _mcp_external_load_failed_at = None


async def log_mcp_startup_diagnostics(config_path: Optional[str] = None) -> None:
    """Log MCP config resolution; optionally preload tools at startup."""
    path = resolved_mcp_config_path(config_path)
    logger.info(
        "MCP startup: resolved_path=%s, cwd=%s",
        path,
        Path.cwd(),
    )
    if path is None:
        return
    if not mcp_preload_at_startup():
        logger.info(
            "MCP startup: preload disabled (SPARKY_MCP_PRELOAD_AT_STARTUP=false); "
            "tools will load on first agent invocation"
        )
        return
    try:
        await ensure_mcp_tool_cache_async(config_path=config_path, force=True)
    except Exception:
        logger.exception(
            "MCP startup: tool preload failed; will retry on first agent use"
        )
