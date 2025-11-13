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

MCPServerType = Literal["stdio", "http", "sse"]


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""

    name: str
    command: Optional[str] = None
    args: Optional[List[str]] = None
    type: Optional[MCPServerType] = None
    url: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    description: Optional[str] = None
    bearerToken: Optional[str] = None

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
            # Project root
            Path.cwd() / "cp.json",
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
            command=config.get("command"),
            args=config.get("args"),
            url=config.get("url"),
            env=config.get("env"),
            bearerToken=config.get("bearerToken"),
            description=config.get("description"),
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

    @staticmethod
    def create_default_config(path: str):
        """Create a default MCP configuration file.

        Args:
            path: Path where to create the config file
        """
        default_config = {
            "mcpServers": {
                "calculator": {
                    "command": "python",
                    "args": ["src/tools/calculator/server.py"],
                    "description": "Calculator tools for mathematical operations",
                },
                "filesystem": {
                    "command": "python",
                    "args": ["src/tools/filesystem/server.py"],
                    "description": "Filesystem tools for file operations",
                },
            }
        }

        # Create directory if it doesn't exist
        os.makedirs(
            os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True
        )

        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)

        return path


def get_config(config_path: Optional[str] = None) -> MCPConfig:
    """Get MCP configuration.

    Args:
        config_path: Optional path to config file

    Returns:
        MCPConfig instance
    """
    return MCPConfig(config_path)
