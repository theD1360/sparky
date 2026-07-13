"""MCP configuration file support."""

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from mcp import StdioServerParameters

logger = logging.getLogger(__name__)

MCPServerType = Literal["stdio", "http", "sse", "streamable_http"]


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""

    name: str
    command: Optional[str] = None
    args: Optional[List[str]] = None
    type: Optional[MCPServerType] = None
    transport: Optional[str] = None
    url: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    headers: Optional[Dict[str, str]] = None
    description: Optional[str] = None
    bearerToken: Optional[str] = None
    disabled: bool = False

    @property
    def is_stdio(self) -> bool:
        """Check if this is a stdio server."""
        return bool(self.command)

    @property
    def is_http(self) -> bool:
        """Check if this is an HTTP/SSE server."""
        return bool(self.url)

    @property
    def is_sse(self) -> bool:
        """Check if this is an SSE server."""
        return self.is_http and self.type == "sse"

    def to_stdio_params(self) -> StdioServerParameters:
        """Convert to MCP StdioServerParameters."""
        if not self.is_stdio:
            raise ValueError(f"Server {self.name} is not a stdio server")
        return StdioServerParameters(
            command=self.command, args=self.args or [], env=self.env
        )


class MCPConfig:
    """MCP configuration manager."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize MCP config.

        Args:
            config_path: Path to MCP config file. If None, searches for default locations.
        """
        self.config_path = config_path or self._find_config_file()
        self.servers: Dict[str, MCPServerConfig] = {}

        if self.config_path and os.path.exists(self.config_path):
            self.load_config()

    @staticmethod
    def _interpolate_env_vars(value: Any) -> Any:
        """Recursively interpolate environment variables in config values.

        Supports ${VAR_NAME} and ${VAR_NAME:-default} syntax.

        Args:
            value: Config value (can be string, dict, list, etc.)

        Returns:
            Value with environment variables replaced
        """
        if isinstance(value, str):
            # Replace ${VAR_NAME:-default} with environment variable or default
            def replace_var(match):
                full_expr = match.group(1)
                # Check if it has a default value (VAR:-default)
                if ":-" in full_expr:
                    var_name, default_value = full_expr.split(":-", 1)
                    return os.environ.get(var_name, default_value)
                else:
                    # Simple ${VAR_NAME} syntax
                    return os.environ.get(full_expr, "")

            return re.sub(r"\$\{([^}]+)\}", replace_var, value)
        elif isinstance(value, dict):
            return {k: MCPConfig._interpolate_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [MCPConfig._interpolate_env_vars(item) for item in value]
        else:
            return value

    @staticmethod
    def _find_config_file() -> Optional[str]:
        """Find MCP config file in standard locations."""
        search_paths = [
            # Current directory
            "mcp.json",
            ".mcp.json",
            "mcp_config.json",
            # Agent package / project layouts
            Path.cwd() / "mcp.json",
            Path.cwd() / "agent" / "mcp.json",
            Path(__file__).resolve().parents[2] / "mcp.json",
            Path.cwd() / ".mcp.json",
            # Home directory (like Claude Desktop)
            Path.home() / ".mcp" / "config.json",
            Path.home() / "Library" / "Application Support" / "Sparky" / "mcp.json",
        ]

        for path in search_paths:
            if Path(path).exists():
                return str(path)

        return None

    def load_config(self):
        """Load MCP servers from config file."""
        if not self.config_path:
            # If no config file exists, ensure required servers are present
            self._ensure_required_servers()
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # Support both formats:
            # 1. {"mcpServers": {...}} (Claude Desktop format)
            # 2. {"servers": {...}} (simplified format)
            servers_config = config.get("mcpServers") or config.get("servers", {})

            for name, server_def in servers_config.items():
                self.servers[name] = self._parse_server_config(name, server_def)

            # Ensure required servers are present after loading
            self._ensure_required_servers()

        except Exception as e:
            raise ValueError(
                "Failed to load MCP config from {}: {}".format(self.config_path, e)
            )

    def _ensure_required_servers(self):
        """Ensure required servers are present in the configuration.

        Currently ensures knowledge server is always present.
        """
        required_servers = {
            "knowledge": {
                "command": "python",
                "args": ["src/tools/knowledge/server.py"],
                "description": "Knowledge graph and memory management (required)",
                "env": {
                    "PYTHONPATH": "${PYTHONPATH:-/app/agent/src}",
                    "SPARKY_DB_URL": "${SPARKY_DB_URL}"
                }
            }
        }

        for name, server_def in required_servers.items():
            if name not in self.servers:
                logger.info(f"Auto-adding required server: {name}")
                self.servers[name] = self._parse_server_config(name, server_def)

    @staticmethod
    def _parse_server_config(name: str, config: Dict[str, Any]) -> MCPServerConfig:
        """Parse a server configuration.

        Supports both stdio servers (command/args) and HTTP/SSE servers (url).
        Interpolates environment variables in all config values.
        """
        # Interpolate environment variables in the entire config
        config = MCPConfig._interpolate_env_vars(config)

        return MCPServerConfig(
            name=name,
            type=config.get("type"),
            transport=config.get("transport"),
            command=config.get("command"),
            args=config.get("args"),
            url=config.get("url"),
            env=config.get("env"),
            headers=config.get("headers"),
            bearerToken=config.get("bearerToken"),
            description=config.get("description"),
            disabled=config.get("disabled", False) is True,
        )

    def get_server(self, name: str) -> Optional[MCPServerConfig]:
        """Get a server configuration by name.

        Args:
            name: Server name

        Returns:
            Server configuration or None if not found
        """
        return self.servers.get(name)

    def list_servers(self) -> List[str]:
        """Get list of configured server names."""
        return list(self.servers.keys())

    def get_all_servers(self) -> Dict[str, MCPServerConfig]:
        """Get all server configurations."""
        return self.servers.copy()

    def resolve_writable_path(self) -> str:
        """Return the path used for persisting MCP config."""
        if self.config_path:
            return self.config_path
        # Prefer agent/mcp.json next to this package's project root
        candidate = Path(__file__).resolve().parents[2] / "mcp.json"
        return str(candidate)

    def _read_raw_config(self) -> Dict[str, Any]:
        """Read raw JSON config from disk (preserves ${ENV} placeholders)."""
        path = self.resolve_writable_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("MCP config root must be a JSON object")
            return data
        return {"mcpServers": {}}

    def _write_raw_config(self, data: Dict[str, Any]) -> str:
        """Persist raw JSON config and reload in-memory servers."""
        path = self.resolve_writable_path()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if "mcpServers" not in data and "servers" not in data:
            data = {"mcpServers": data}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        self.config_path = path
        self.servers = {}
        self.load_config()
        return path

    def list_server_definitions(self, *, mask_secrets: bool = True) -> List[Dict[str, Any]]:
        """Return serializable server definitions from the raw config file."""
        raw = self._read_raw_config()
        servers = raw.get("mcpServers") or raw.get("servers") or {}
        out: List[Dict[str, Any]] = []
        for name, cfg in servers.items():
            if not isinstance(cfg, dict):
                continue
            entry = {"name": name, **cfg}
            if mask_secrets and entry.get("bearerToken"):
                token = str(entry["bearerToken"])
                if not token.startswith("${"):
                    entry["bearerToken"] = (
                        "***" + token[-4:] if len(token) > 4 else "****"
                    )
            out.append(entry)
        return out

    def upsert_server(self, name: str, definition: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a server definition and persist to mcp.json."""
        if not name or not isinstance(name, str):
            raise ValueError("Server name is required")
        if not isinstance(definition, dict):
            raise ValueError("Server definition must be an object")

        # Never persist the name field inside the definition blob
        clean = {k: v for k, v in definition.items() if k != "name" and v is not None}

        # If bearerToken is a masked placeholder, keep the existing value
        raw = self._read_raw_config()
        servers = raw.setdefault("mcpServers", raw.pop("servers", {}))
        if not isinstance(servers, dict):
            servers = {}
            raw["mcpServers"] = servers

        existing = servers.get(name, {}) if isinstance(servers.get(name), dict) else {}
        token = clean.get("bearerToken")
        if isinstance(token, str) and token.startswith("***"):
            if "bearerToken" in existing:
                clean["bearerToken"] = existing["bearerToken"]
            else:
                clean.pop("bearerToken", None)

        # Drop empty optional fields
        for key in list(clean.keys()):
            if clean[key] in ("", [], {}):
                clean.pop(key)

        servers[name] = clean
        self._write_raw_config(raw)
        return {"name": name, **clean}

    def delete_server(self, name: str) -> bool:
        """Delete a server definition from mcp.json."""
        raw = self._read_raw_config()
        servers = raw.get("mcpServers") or raw.get("servers") or {}
        if name not in servers:
            return False
        del servers[name]
        raw["mcpServers"] = servers
        self._write_raw_config(raw)
        return True

    def set_server_disabled(self, name: str, disabled: bool) -> Dict[str, Any]:
        """Enable or disable a server without removing it."""
        raw = self._read_raw_config()
        servers = raw.get("mcpServers") or raw.get("servers") or {}
        if name not in servers or not isinstance(servers[name], dict):
            raise KeyError(f"Server '{name}' not found")
        if disabled:
            servers[name]["disabled"] = True
        else:
            servers[name].pop("disabled", None)
        raw["mcpServers"] = servers
        self._write_raw_config(raw)
        return {"name": name, **servers[name]}

    @staticmethod
    def create_default_config(path: str):
        """Create a default MCP configuration file.

        Args:
            path: Path where to create the config file
        """
        default_config = {
            "mcpServers": {
                "knowledge": {
                    "command": "python",
                    "args": ["src/tools/knowledge/server.py"],
                    "description": "Knowledge graph and memory management",
                    "env": {
                        "PYTHONPATH": "${PYTHONPATH:-/app/agent/src}",
                        "SPARKY_DB_URL": "${SPARKY_DB_URL}",
                    },
                },
            }
        }

        # Create directory if it doesn't exist
        os.makedirs(
            os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True
        )

        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)
            f.write("\n")

        return path


def get_config(config_path: Optional[str] = None) -> MCPConfig:
    """Get MCP configuration.

    Args:
        config_path: Optional path to config file

    Returns:
        MCPConfig instance
    """
    return MCPConfig(config_path)
