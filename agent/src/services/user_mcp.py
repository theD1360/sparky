"""Helpers for per-user MCP extra server preferences."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from badmcp.config import MCPConfig


def system_server_names() -> set[str]:
    """Names of servers defined in the shared mcp.json catalog."""
    config = MCPConfig()
    return {s["name"] for s in config.list_server_definitions(mask_secrets=False)}


def list_system_servers_readonly() -> List[Dict[str, Any]]:
    """System servers for UI display (no secrets; not user-editable)."""
    config = MCPConfig()
    out: List[Dict[str, Any]] = []
    for entry in config.list_server_definitions(mask_secrets=True):
        out.append(
            {
                "name": entry.get("name"),
                "description": entry.get("description") or "",
                "disabled": bool(entry.get("disabled", False)),
                "transport": "stdio" if entry.get("command") else "remote",
                "url": entry.get("url"),
                "readonly": True,
            }
        )
    return out


def mask_extra_servers(extras: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return a copy of extras with bearer tokens masked."""
    masked: List[Dict[str, Any]] = []
    for entry in extras:
        if not isinstance(entry, dict):
            continue
        item = copy.deepcopy(entry)
        token = item.get("bearerToken")
        if isinstance(token, str) and token and not token.startswith("${"):
            item["bearerToken"] = "***" + token[-4:] if len(token) > 4 else "****"
        masked.append(item)
    return masked


def normalize_remote_definition(
    definition: Dict[str, Any], *, existing: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Validate and clean a user remote MCP definition."""
    clean = {
        k: v
        for k, v in definition.items()
        if k != "name" and v is not None and v not in ("", [], {})
    }
    if clean.get("command") or clean.get("args"):
        raise ValueError("User MCP servers cannot use stdio (command/args)")
    if not clean.get("url"):
        raise ValueError("User MCP servers require a url")

    token = clean.get("bearerToken")
    if isinstance(token, str) and token.startswith("***") and existing:
        if existing.get("bearerToken"):
            clean["bearerToken"] = existing["bearerToken"]
        else:
            clean.pop("bearerToken", None)

    # Drop stdio-only fields if present
    clean.pop("command", None)
    clean.pop("args", None)
    clean.pop("env", None)
    return clean


def extras_list_to_map(extras: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Convert preference list to name → definition map."""
    out: Dict[str, Dict[str, Any]] = {}
    for entry in extras or []:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        out[name] = {k: v for k, v in entry.items() if k != "name"}
    return out


def map_to_extras_list(servers: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert name → definition map back to preference list."""
    return [{"name": name, **cfg} for name, cfg in servers.items()]
