"""LangChain toolchain wrapper for MCP servers using langchain-mcp-adapters."""

import logging
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from badmcp.config import MCPServerConfig
from langchain_core.tools import BaseTool

from sparky.gemini_schema import tools_with_gemini_safe_arg_schemas
from sparky.mcp_toolkit import (
    clear_mcp_tool_cache,
    load_mcp_langchain_tools_async,
    mcp_config_to_connections,
)

logger = logging.getLogger(__name__)

# Lazy import - only import when actually needed
if TYPE_CHECKING:
    from langchain_mcp_adapters.client import MultiServerMCPClient


def _import_mcp_client():
    """Lazy import of MultiServerMCPClient with better error handling."""
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        return MultiServerMCPClient
    except ImportError as e:
        error_msg = str(e)
        if (
            "langchain_core.messages.content" in error_msg
            or "ModuleNotFoundError" in error_msg
        ):
            import sys

            print(
                "\n" + "=" * 80 + "\n"
                "ERROR: Version incompatibility detected!\n"
                "The langchain_mcp_adapters package requires a newer version of langchain_core.\n"
                "\n"
                "To fix this, please update your dependencies:\n"
                "  pip install --upgrade 'langchain-core>=0.3.20' 'langchain-mcp-adapters>=0.1.0'\n"
                "\n"
                "Or if using poetry:\n"
                "  poetry update langchain-core langchain-mcp-adapters\n"
                "\n"
                "Original error: " + error_msg + "\n" + "=" * 80 + "\n",
                file=sys.stderr,
            )
        raise


class LangChainToolchain:
    """Wrapper around MultiServerMCPClient for LangChain integration.

    Provides a unified interface for tools, prompts, and resources from MCP servers.
    One instance per websocket connection for stateful sessions.
    """

    def __init__(self, mcp_client: Any):
        """Initialize the LangChain toolchain.

        Args:
            mcp_client: MultiServerMCPClient instance with configured MCP servers
        """
        self.client = mcp_client
        self._cached_tools: Optional[List[BaseTool]] = None

    @classmethod
    def from_mcp_config(
        cls,
        servers: Dict[str, MCPServerConfig],
        *,
        tool_interceptors: Optional[list] = None,
    ) -> "LangChainToolchain":
        """Create a LangChainToolchain from MCP server configurations.

        Args:
            servers: Dictionary mapping server names to MCPServerConfig instances
            tool_interceptors: Optional langchain-mcp-adapters tool interceptors

        Returns:
            LangChainToolchain instance
        """
        raw_servers: Dict[str, Dict[str, Any]] = {}
        for name, config in servers.items():
            if config.disabled:
                logger.info("Skipping disabled MCP server: %s", name)
                continue
            if config.is_stdio:
                entry: Dict[str, Any] = {
                    "command": config.command,
                    "args": config.args or [],
                }
                if config.env:
                    entry["env"] = config.env
                raw_servers[name] = entry
            elif config.is_http:
                entry = {"url": config.url}
                if config.transport:
                    entry["transport"] = config.transport
                elif config.type:
                    entry["type"] = config.type
                if config.headers:
                    entry["headers"] = config.headers
                if config.bearerToken:
                    entry["bearerToken"] = config.bearerToken
                if config.env and not config.headers:
                    entry["headers"] = config.env
                raw_servers[name] = entry
            else:
                logger.warning(
                    "Skipping server %s: unknown server type (not stdio or http)",
                    name,
                )

        from badmcp.mcp_json import parse_mcp_json_to_connections

        connections = parse_mcp_json_to_connections({"mcpServers": raw_servers})
        if not connections:
            raise ValueError("No usable MCP server connections configured")

        MultiServerMCPClient = _import_mcp_client()
        client_kwargs: Dict[str, Any] = {}
        prefix = (os.getenv("SPARKY_MCP_TOOL_NAME_PREFIX") or "").strip()
        if prefix:
            client_kwargs["tool_name_prefix"] = prefix
        if tool_interceptors:
            client_kwargs["tool_interceptors"] = tool_interceptors

        client = MultiServerMCPClient(connections=connections, **client_kwargs)
        return cls(client)

    @classmethod
    def from_connections(
        cls,
        connections: Dict[str, Dict[str, Any]],
        *,
        tool_interceptors: Optional[list] = None,
    ) -> "LangChainToolchain":
        """Create a toolchain directly from langchain-mcp-adapters connection dicts."""
        MultiServerMCPClient = _import_mcp_client()
        client_kwargs: Dict[str, Any] = {}
        prefix = (os.getenv("SPARKY_MCP_TOOL_NAME_PREFIX") or "").strip()
        if prefix:
            client_kwargs["tool_name_prefix"] = prefix
        if tool_interceptors:
            client_kwargs["tool_interceptors"] = tool_interceptors
        client = MultiServerMCPClient(connections=connections, **client_kwargs)
        return cls(client)

    async def get_langchain_tools(
        self,
        server_name: Optional[str] = None,
        *,
        gemini_safe: bool = True,
    ) -> List[BaseTool]:
        """Get all LangChain tools from MCP servers.

        Loads servers individually so one failing server (e.g. MetaMCP 404)
        does not abort tool discovery for the rest.

        Args:
            server_name: Optional server name to get tools from. If None, gets tools from all servers.
            gemini_safe: When True, strip JSON Schema noise for Gemini compatibility.

        Returns:
            List of LangChain BaseTool instances
        """
        if server_name is None and self._cached_tools is not None:
            return self._cached_tools

        if server_name is not None:
            tools = await self.client.get_tools(server_name=server_name)
        else:
            tools = []
            failed: List[str] = []
            for name in list(self.client.connections.keys()):
                try:
                    server_tools = await self.client.get_tools(server_name=name)
                    tools.extend(server_tools)
                    logger.info(
                        "Loaded %d tool(s) from MCP server %s",
                        len(server_tools),
                        name,
                    )
                except Exception as e:
                    failed.append(name)
                    logger.warning(
                        "Skipping MCP server %s during tool load: %s: %s",
                        name,
                        type(e).__name__,
                        e,
                    )
            if failed:
                logger.warning(
                    "MCP tool load completed with %d/%d server(s) skipped: %s",
                    len(failed),
                    len(self.client.connections),
                    ", ".join(failed),
                )

        if gemini_safe:
            tools = tools_with_gemini_safe_arg_schemas(tools) or tools
        if server_name is None:
            self._cached_tools = tools
        return tools

    async def call_tool(self, tool_name: str, args: dict) -> Any:
        """Execute a tool by name.

        Note: This is primarily for middleware compatibility. LangChain tools
        are typically executed directly by the LLM provider.

        Args:
            tool_name: Name of the tool to call
            args: Arguments for the tool

        Returns:
            Tool execution result
        """
        tools = await self.get_langchain_tools()
        for tool in tools:
            if tool.name == tool_name:
                try:
                    result = await tool.ainvoke(args)
                    return result
                except Exception as e:
                    logger.error("Error executing tool %s: %s", tool_name, e)
                    raise
        raise ValueError(f"Tool {tool_name} not found")

    async def get_prompt(
        self, server_name: str, prompt_name: str, arguments: Optional[dict] = None
    ) -> str:
        """Get a prompt from an MCP server."""
        if arguments:
            async with self.client.session(server_name) as session:
                result = await session.get_prompt(prompt_name, arguments or {})
                if hasattr(result, "messages"):
                    return "\n".join(
                        msg.content if hasattr(msg, "content") else str(msg)
                        for msg in result.messages
                    )
                return str(result)
        return await self.client.get_prompt(server_name, prompt_name)

    async def get_resources(
        self, server_name: Optional[str] = None, uris: Optional[List[str]] = None
    ) -> List[Any]:
        """Get resources from MCP servers."""
        return await self.client.get_resources(server_name=server_name, uris=uris)

    async def list_prompts(self) -> List[tuple]:
        """List all available prompts from all MCP servers."""
        prompts = []
        for server_name in self.client.connections.keys():
            try:
                async with self.client.session(server_name) as session:
                    result = await session.list_prompts()
                    if hasattr(result, "prompts"):
                        for prompt in result.prompts:
                            prompts.append((server_name, prompt.name))
            except Exception as e:
                logger.warning(
                    "Failed to list prompts from %s: %s",
                    server_name,
                    e,
                    exc_info=True,
                )
        return prompts

    async def list_resources(self) -> List[tuple]:
        """List all available resources from all MCP servers."""
        resources = []
        for server_name in self.client.connections.keys():
            try:
                async with self.client.session(server_name) as session:
                    result = await session.list_resources()
                    if hasattr(result, "resources"):
                        for resource in result.resources:
                            resources.append((server_name, resource.uri))
            except Exception as e:
                logger.warning(
                    "Failed to list resources from %s: %s",
                    server_name,
                    e,
                    exc_info=True,
                )
        return resources

    async def read_resource(self, uri: str) -> str:
        """Read a resource by URI."""
        resources = await self.get_resources()
        for blob in resources:
            if hasattr(blob, "metadata") and blob.metadata.get("uri") == uri:
                if hasattr(blob, "as_string"):
                    return blob.as_string()
                return str(blob)

        for server_name in self.client.connections.keys():
            try:
                async with self.client.session(server_name) as session:
                    result = await session.read_resource(uri)
                    if result.contents:
                        return "\n".join(
                            item.text if hasattr(item, "text") else str(item)
                            for item in result.contents
                        )
            except Exception:
                continue

        raise ValueError(f"Resource {uri} not found")

    async def cleanup(self):
        """Clean up the MCP client and close all sessions."""
        self._cached_tools = None


__all__ = [
    "LangChainToolchain",
    "clear_mcp_tool_cache",
    "load_mcp_langchain_tools_async",
    "mcp_config_to_connections",
]
