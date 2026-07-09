"""Parse standard MCP client JSON (``mcpServers``) into langchain-mcp-adapters connections."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _normalize_transport(raw: str | None) -> str:
    t = (raw or "http").strip().lower()
    if t in ("streamable_http", "streamable-http"):
        return "streamable_http"
    if t == "sse":
        return "sse"
    if t in ("http", "https"):
        return "http"
    if t in ("websocket", "ws"):
        return "websocket"
    logger.warning("Unknown MCP transport %r; using http", raw)
    return "http"


def server_entry_to_connection(name: str, cfg: dict[str, Any]) -> dict[str, Any] | None:
    """Map one ``mcpServers`` entry to a langchain-mcp-adapters ``Connection`` dict."""
    if cfg.get("disabled") is True:
        logger.info("MCP server %r is disabled; skipping", name)
        return None

    cmd = (cfg.get("command") or "").strip() if isinstance(cfg.get("command"), str) else None
    if cmd:
        args = cfg.get("args")
        if args is None:
            arg_list: list[str] = []
        elif isinstance(args, list):
            arg_list = [str(x) for x in args]
        else:
            logger.warning("MCP server %r: args must be a list; skipping", name)
            return None
        env = cfg.get("env")
        if env is not None and not isinstance(env, dict):
            logger.warning("MCP server %r: env must be an object; ignoring", name)
            env = None
        out: dict[str, Any] = {
            "transport": "stdio",
            "command": cmd,
            "args": arg_list,
        }
        if env:
            out["env"] = {str(k): str(v) for k, v in env.items()}
        return out

    url = cfg.get("url")
    if isinstance(url, str) and url.strip():
        transport_raw = cfg.get("transport") if isinstance(cfg.get("transport"), str) else None
        server_type = cfg.get("type") if isinstance(cfg.get("type"), str) else None
        if transport_raw:
            transport = _normalize_transport(transport_raw)
        elif server_type == "sse":
            transport = "sse"
        elif server_type == "streamable_http":
            transport = "streamable_http"
        else:
            transport = _normalize_transport(server_type)

        conn: dict[str, Any] = {"transport": transport, "url": url.strip()}
        headers = cfg.get("headers")
        if isinstance(headers, dict) and headers:
            conn["headers"] = {str(k): str(v) for k, v in headers.items()}
        bearer = cfg.get("bearerToken")
        if bearer:
            if "headers" not in conn:
                conn["headers"] = {}
            conn["headers"]["Authorization"] = f"Bearer {bearer}"
        return conn

    logger.warning(
        'MCP server %r: need "command" (stdio) or "url" (remote); skipping',
        name,
    )
    return None


def parse_mcp_json_to_connections(data: dict[str, Any]) -> Dict[str, dict[str, Any]]:
    """Parse JSON object into server name -> Connection dict for ``MultiServerMCPClient``."""
    if "mcpServers" in data:
        servers = data["mcpServers"]
    else:
        servers = data

    if not isinstance(servers, dict):
        raise ValueError("MCP config must be an object with an mcpServers map (or a server map)")

    out: Dict[str, dict[str, Any]] = {}
    for name, cfg in servers.items():
        if not isinstance(name, str) or not isinstance(cfg, dict):
            continue
        conn = server_entry_to_connection(name, cfg)
        if conn is not None:
            out[name] = conn
    return out


def load_mcp_json_file(path: Path) -> Dict[str, dict[str, Any]]:
    """Read a JSON file and return connection map."""
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("MCP config file must contain a JSON object")
    return parse_mcp_json_to_connections(data)
