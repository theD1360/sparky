import json
import os
from contextlib import asynccontextmanager
from logging import getLogger
from typing import AsyncGenerator

import httpcore
import httpx
from mcp import ClientSession, ListToolsResult
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from rich.console import Console

from badmcp.config import MCPServerConfig

logger = getLogger(__name__)


class ToolClient:

    def __init__(self, mcp_config: MCPServerConfig):
        self._config = mcp_config
        self._session = None
        self._client = None
        self._available_tools = None
        self._available_prompts = None
        self._available_resources = None
        # Error tracking for better reporting upstream
        self.last_error: Exception | None = None
        self.last_error_tb: str | None = None

    @property
    def name(self):
        return self._config.name

    async def start(self):
        """Start the client and load tools, prompts, and resources concurrently."""
        import asyncio

        await asyncio.gather(
            self.load_tools(), self.load_prompts(), self.load_resources()
        )

    async def stop(self):
        """Stop the client and clean up resources."""
        # Sessions are managed by context managers and auto-close
        # Just clear our references
        self._session = None
        self._client = None
        self._available_tools = None
        self._available_prompts = None
        self._available_resources = None

    @property
    def available_tools(self) -> ListToolsResult:
        return self._available_tools

    @property
    def available_prompts(self):
        return self._available_prompts

    @property
    def available_resources(self):
        return self._available_resources

    async def restart(self):
        await self.stop()
        await self.start()

    def client(self):
        if self._config.is_stdio:
            return stdio_client(self._config.to_stdio_params())
        elif self._config.is_http:
            auth = None
            # HTTP/SSE server
            headers = {}
            if self._config.env:
                # Pass env vars as headers for SSE servers
                headers = self._config.env

            if self._config.bearerToken:
                headers = {
                    **headers,
                    "Authorization": f"Bearer {self._config.bearerToken}",
                }
            return sse_client(self._config.url, headers=headers, auth=auth)
        else:
            raise Exception("Unsupported MCP server type")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[ClientSession]:
        async with self.client() as (read, write):
            async with ClientSession(read, write) as session:
                self._session = session
                try:
                    await session.initialize()
                except Exception as e:
                    # Capture error so upstream can report better context
                    import traceback

                    self.last_error = e
                    self.last_error_tb = traceback.format_exc()
                    logger.warning(
                        "⚠ Could not connect to {}: {}".format(
                            self._config.name, str(e)
                        )
                    )
                yield session

    async def load_tools(self):
        """
        Load the tools available from the MCP server and store them in the _available_tools attribute.
        """
        async with self.session() as session:
            try:
                self._available_tools = await session.list_tools()
                # Clear previous error state on success
                self.last_error = None
                self.last_error_tb = None
                logger.info(
                    f"Successfully loaded {len(self.available_tools.tools)} tools from {self._config.name}"
                )
            except Exception as e:
                import traceback

                self.last_error = e
                self.last_error_tb = traceback.format_exc()
                logger.error(
                    "Error listing tools from {}: {}".format(self._config.name, str(e))
                )
                # Provide an empty tool list to avoid NoneType errors upstream
                try:
                    self._available_tools = ListToolsResult(tools=[])
                except Exception:
                    # Fallback if constructor signature differs
                    class _Empty:
                        tools = []

                    self._available_tools = _Empty()

    async def list_tools(self) -> ListToolsResult:
        """
        List the tools available from the MCP server.
        """
        async with self.session() as session:
            return await session.list_tools()

    async def load_prompts(self):
        """
        Load the prompts available from the MCP server and store them in the _available_prompts attribute.
        """
        async with self.session() as session:
            try:
                self._available_prompts = await session.list_prompts()
                # Clear previous error state on success
                self.last_error = None
                self.last_error_tb = None
                prompt_count = (
                    len(self._available_prompts.prompts)
                    if hasattr(self._available_prompts, "prompts")
                    else 0
                )
                logger.info(
                    f"Successfully loaded {prompt_count} prompts from {self._config.name}"
                )
            except Exception as e:
                import traceback

                self.last_error = e
                self.last_error_tb = traceback.format_exc()
                logger.error(
                    "Error listing prompts from {}: {}".format(
                        self._config.name, str(e)
                    )
                )
                # Provide an empty prompt list to avoid NoneType errors upstream
                try:
                    from mcp import ListPromptsResult

                    self._available_prompts = ListPromptsResult(prompts=[])
                except Exception:
                    # Fallback if constructor signature differs
                    class _Empty:
                        prompts = []

                    self._available_prompts = _Empty()

    async def list_prompts(self):
        """List available prompts from the MCP server."""
        async with self.session() as session:
            return await session.list_prompts()

    async def get_prompt(self, prompt_name: str, arguments: dict = None):
        """Get a prompt with arguments."""
        async with self.session() as session:
            return await session.get_prompt(prompt_name, arguments or {})

    async def load_resources(self):
        """
        Load the resources available from the MCP server and store them in the _available_resources attribute.
        """
        async with self.session() as session:
            try:
                self._available_resources = await session.list_resources()
                # Clear previous error state on success
                self.last_error = None
                self.last_error_tb = None
                resource_count = (
                    len(self._available_resources.resources)
                    if hasattr(self._available_resources, "resources")
                    else 0
                )
                logger.info(
                    f"Successfully loaded {resource_count} resources from {self._config.name}"
                )
            except Exception as e:
                import traceback

                self.last_error = e
                self.last_error_tb = traceback.format_exc()
                logger.error(
                    "Error listing resources from {}: {}".format(
                        self._config.name, str(e)
                    )
                )
                # Provide an empty resource list to avoid NoneType errors upstream
                try:
                    from mcp import ListResourcesResult

                    self._available_resources = ListResourcesResult(resources=[])
                except Exception:
                    # Fallback if constructor signature differs
                    class _Empty:
                        resources = []

                    self._available_resources = _Empty()

    async def list_resources(self):
        """List available resources from the MCP server."""
        async with self.session() as session:
            return await session.list_resources()

    async def read_resource(self, uri: str):
        """Read a resource by URI."""
        async with self.session() as session:
            result = await session.read_resource(uri)
            # Parse the resource content
            if result.contents:
                return "\n".join(
                    [
                        item.text if hasattr(item, "text") else str(item)
                        for item in result.contents
                    ]
                )
            return ""

    async def call(self, tool: str, args: dict):
        """Call an MCP tool and return the result."""
        attempts = 0
        last_exc = None
        while attempts < 3:
            attempts += 1
            try:
                async with self.session() as session:
                    result = await session.call_tool(tool, args)
                    if result.content:
                        # Join all text content
                        text_result = "\n".join(
                            [
                                item.text
                                for item in result.content
                                if hasattr(item, "text")
                            ]
                        )

                        # Try to parse as JSON if it looks like JSON (starts with { or [)
                        text_stripped = text_result.strip()
                        if text_stripped.startswith("{") or text_stripped.startswith(
                            "["
                        ):
                            try:
                                parsed = json.loads(text_result)
                                logger.debug(
                                    "Parsed JSON response from %s: %s",
                                    tool,
                                    type(parsed).__name__,
                                )
                                return parsed
                            except (json.JSONDecodeError, ValueError) as e:
                                logger.debug(
                                    "Failed to parse JSON from %s: %s",
                                    tool,
                                    str(e)[:100],
                                )
                                # Not valid JSON, return as string
                                pass

                        return text_result
                    else:
                        # Return empty string if no content (instead of None)
                        logger.warning(f"Tool {tool} returned empty content")
                        return ""
            except Exception as e:
                last_exc = e
                is_timeout = isinstance(e, httpx.ReadTimeout) or (
                    httpcore
                    and isinstance(e, getattr(httpcore, "ReadTimeout", tuple()))
                )
                if is_timeout and attempts < 3:
                    # brief backoff
                    import asyncio

                    await asyncio.sleep(0.5 * attempts)
                    continue
                break

        # If we exhausted all retries, return an error message
        if last_exc:
            logger.error(
                f"Tool {tool} call failed after {attempts} attempts: {last_exc}"
            )
            return json.dumps({"error": f"Tool call failed: {str(last_exc)}"})
        return ""


if __name__ == "__main__":
    import asyncio

    from rich.console import Console

    console = Console()

    async def core():
        tool = ToolClient(
            mcp_config=MCPServerConfig(
                name="test",
                type="sse",
                url="http://localhost:12008/metamcp/testing/sse",
                bearerToken=os.getenv("METAMCP_API_KEY"),
            )
        )
        tools_available = await tool.list_tools()
        console.print(tools_available)

        response = await tool.call(
            "Sequential-Thinking__sequentialthinking",
            {
                "thought": "something something something",
                "nextThoughtNeeded": True,
                "thoughtNumber": 1,
                "totalThoughts": 1,
            },
        )
        console.print(response)

    asyncio.run(core())
