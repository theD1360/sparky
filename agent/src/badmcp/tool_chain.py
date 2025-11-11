from asyncio import gather
from logging import getLogger

from mcp import Tool

from badmcp.tool_client import ToolClient

logger = getLogger(__name__)


class ToolChain:
    def __init__(self, tool_clients: list[ToolClient]):
        self.tool_clients = tool_clients
        self._available_tools = None
        self._available_prompts = None
        self._available_resources = None

    async def load_tools(self):
        """Aggregate tools from tool clients' caches."""
        if self._available_tools is not None:
            return self._available_tools

        # Aggregate tools from clients' existing caches (already loaded by client.start())
        tools: list[tuple[int, Tool]] = []
        for idx, tool_client in enumerate(self.tool_clients):
            try:
                at = tool_client.available_tools
                tool_list = getattr(at, "tools", None) if at is not None else None
                logger.debug(
                    f"[ToolChain] Checking {tool_client._config.name}: at={at}, tool_list={tool_list}, "
                    f"has {len(tool_list) if tool_list else 0} tools"
                )
                if tool_list is None:
                    # Provide clearer error context
                    err = getattr(tool_client, "last_error", None)
                    if err is not None:
                        tb = getattr(tool_client, "last_error_tb", None)
                        logger.info(
                            f"Error loading tools from {tool_client._config.name}: {type(err).__name__}: {err}"
                        )
                        if tb:
                            # Print only the last traceback line for brevity
                            last_line = tb.strip().splitlines()[-1] if tb else ""
                            logger.info(f"{last_line}")
                    else:
                        logger.warning(
                            f"No tools available from {tool_client._config.name} (uninitialized or empty)"
                        )
                    continue
                if len(tool_list) == 0:
                    logger.warning(
                        f"Tool list for {tool_client._config.name} is empty (loaded but no tools)"
                    )
                for tool in tool_list:
                    tools.append((idx, tool))
            except Exception as e:
                logger.error(
                    f"Error loading tools from {tool_client._config.name}: {str(e)}"
                )
        self._available_tools = tools

        logger.info(
            f"[ToolChain] Total tools available: {len(tools)} from {len(self.tool_clients)} clients"
        )

        return self._available_tools

    async def load_prompts(self):
        """Aggregate prompts from tool clients' caches."""
        if self._available_prompts is not None:
            return self._available_prompts

        # Aggregate prompts from clients' existing caches (already loaded by client.start())
        prompts: list[tuple[int, any]] = []
        for idx, tool_client in enumerate(self.tool_clients):
            try:
                ap = tool_client.available_prompts
                prompt_list = getattr(ap, "prompts", None) if ap is not None else None
                logger.debug(
                    f"[ToolChain] Checking {tool_client._config.name}: ap={ap}, prompt_list={prompt_list}, "
                    f"has {len(prompt_list) if prompt_list else 0} prompts"
                )
                if prompt_list is None:
                    # Provide clearer error context
                    err = getattr(tool_client, "last_error", None)
                    if err is not None:
                        tb = getattr(tool_client, "last_error_tb", None)
                        logger.info(
                            f"Error loading prompts from {tool_client._config.name}: {type(err).__name__}: {err}"
                        )
                        if tb:
                            # Print only the last traceback line for brevity
                            last_line = tb.strip().splitlines()[-1] if tb else ""
                            logger.info(f"{last_line}")
                    else:
                        logger.warning(
                            f"No prompts available from {tool_client._config.name} (uninitialized or empty)"
                        )
                    continue
                if len(prompt_list) == 0:
                    logger.debug(
                        f"Prompt list for {tool_client._config.name} is empty (loaded but no prompts)"
                    )
                for prompt in prompt_list:
                    prompts.append((idx, prompt))
            except Exception as e:
                logger.error(
                    f"Error loading prompts from {tool_client._config.name}: {str(e)}"
                )
        self._available_prompts = prompts

        logger.info(
            f"[ToolChain] Total prompts available: {len(prompts)} from {len(self.tool_clients)} clients"
        )

        return self._available_prompts

    async def load_resources(self):
        """Aggregate resources from tool clients' caches."""
        if self._available_resources is not None:
            return self._available_resources

        # Aggregate resources from clients' existing caches (already loaded by client.start())
        resources: list[tuple[int, any]] = []
        for idx, tool_client in enumerate(self.tool_clients):
            try:
                ar = tool_client.available_resources
                resource_list = (
                    getattr(ar, "resources", None) if ar is not None else None
                )
                logger.debug(
                    f"[ToolChain] Checking {tool_client._config.name}: ar={ar}, resource_list={resource_list}, "
                    f"has {len(resource_list) if resource_list else 0} resources"
                )
                if resource_list is None:
                    # Provide clearer error context
                    err = getattr(tool_client, "last_error", None)
                    if err is not None:
                        tb = getattr(tool_client, "last_error_tb", None)
                        logger.info(
                            f"Error loading resources from {tool_client._config.name}: {type(err).__name__}: {err}"
                        )
                        if tb:
                            # Print only the last traceback line for brevity
                            last_line = tb.strip().splitlines()[-1] if tb else ""
                            logger.info(f"{last_line}")
                    else:
                        logger.warning(
                            f"No resources available from {tool_client._config.name} (uninitialized or empty)"
                        )
                    continue
                if len(resource_list) == 0:
                    logger.debug(
                        f"Resource list for {tool_client._config.name} is empty (loaded but no resources)"
                    )
                for resource in resource_list:
                    resources.append((idx, resource))
            except Exception as e:
                logger.error(
                    f"Error loading resources from {tool_client._config.name}: {str(e)}"
                )
        self._available_resources = resources

        logger.info(
            f"[ToolChain] Total resources available: {len(resources)} from {len(self.tool_clients)} clients"
        )

        return self._available_resources

    async def initialize(self):
        """Initialize the tool chain by loading tools, prompts, and resources concurrently."""
        logger.info(
            "[ToolChain] Initializing: loading tools, prompts, and resources..."
        )
        tools, prompts, resources = await gather(
            self.load_tools(), self.load_prompts(), self.load_resources()
        )
        logger.info("[ToolChain] Initialization complete")
        return tools, prompts, resources

    @property
    def available_tools(self) -> list[tuple[int, Tool]]:
        if self._available_tools is not None:
            return self._available_tools

        raise Exception("Tools not loaded")

    @property
    def available_prompts(self) -> list[tuple[int, any]]:
        if self._available_prompts is not None:
            return self._available_prompts

        raise Exception("Prompts not loaded")

    @property
    def available_resources(self) -> list[tuple[int, any]]:
        if self._available_resources is not None:
            return self._available_resources

        raise Exception("Resources not loaded")

    def find(self, tool_name: str):
        for client_idx, tool in self.available_tools:
            if tool_name == tool.name:
                return self.tool_clients[client_idx]
        return None

    async def call(self, tool_name: str, arguments: dict):
        tool = self.find(tool_name)
        if tool:
            return await tool.call(tool_name, arguments)
        raise Exception("Tool not found")

    async def list_all_prompts(self):
        """List prompts from all tool clients."""
        # Use cached data if available
        if self._available_prompts is not None:
            # Convert from (idx, prompt) to (tool_client, prompt) format
            return [
                (self.tool_clients[idx], prompt)
                for idx, prompt in self._available_prompts
            ]

        # Fall back to on-demand loading if not cached
        all_prompts = []
        for tool_client in self.tool_clients:
            try:
                prompts = await tool_client.list_prompts()
                if prompts and hasattr(prompts, "prompts"):
                    for prompt in prompts.prompts:
                        all_prompts.append((tool_client, prompt))
            except Exception as e:
                logger.debug(f"Error listing prompts from {tool_client.name}: {e}")
        return all_prompts

    async def get_prompt(self, prompt_name: str, arguments: dict = None):
        """Get a prompt from any client that has it."""
        # Use cached prompts if available for faster lookup
        if self._available_prompts is not None:
            last_error = None
            for client_idx, prompt in self._available_prompts:
                if prompt.name == prompt_name:
                    tool_client = self.tool_clients[client_idx]
                    logger.info(
                        f"Getting prompt {prompt_name} from {tool_client.name} with args: {arguments}"
                    )
                    try:
                        # Ensure arguments is a dict (not None)
                        prompt_args = arguments if arguments is not None else {}
                        logger.debug(f"Calling get_prompt with args: {prompt_args}")
                        result = await tool_client.get_prompt(prompt_name, prompt_args)
                        logger.debug(f"Got result type: {type(result)}")
                        # Extract the prompt text from the result
                        if hasattr(result, "messages"):
                            # Return the first message content
                            if result.messages:
                                msg = result.messages[0]
                                if hasattr(msg, "content"):
                                    if hasattr(msg.content, "text"):
                                        prompt_text = msg.content.text
                                        logger.info(
                                            f"Successfully extracted prompt text: {prompt_text[:100]}..."
                                        )
                                        return prompt_text
                                    prompt_text = str(msg.content)
                                    logger.info(
                                        f"Extracted prompt as string: {prompt_text[:100]}..."
                                    )
                                    return prompt_text
                        prompt_text = str(result)
                        logger.info(
                            f"Converted result to string: {prompt_text[:100]}..."
                        )
                        return prompt_text
                    except Exception as e:
                        last_error = e
                        logger.error(
                            f"Error getting prompt {prompt_name} from {tool_client.name}: {e}"
                        )
                        continue
            # If we found the prompt but all attempts failed, raise the last error
            if last_error:
                raise Exception(
                    f"Prompt '{prompt_name}' found but failed to retrieve: {str(last_error)}"
                )
            raise Exception(f"Prompt '{prompt_name}' not found")

        # Fall back to on-demand loading if not cached
        for tool_client in self.tool_clients:
            try:
                prompts = await tool_client.list_prompts()
                if prompts and hasattr(prompts, "prompts"):
                    for prompt in prompts.prompts:
                        if prompt.name == prompt_name:
                            logger.info(
                                f"Getting prompt {prompt_name} from {tool_client.name}"
                            )
                            result = await tool_client.get_prompt(
                                prompt_name, arguments
                            )
                            logger.debug(f"Got result type: {type(result)}")
                            # Extract the prompt text from the result
                            if hasattr(result, "messages"):
                                # Return the first message content
                                if result.messages:
                                    msg = result.messages[0]
                                    if hasattr(msg, "content"):
                                        if hasattr(msg.content, "text"):
                                            prompt_text = msg.content.text
                                            logger.info(
                                                f"Successfully extracted prompt text: {prompt_text[:100]}..."
                                            )
                                            return prompt_text
                                        prompt_text = str(msg.content)
                                        logger.info(
                                            f"Extracted prompt as string: {prompt_text[:100]}..."
                                        )
                                        return prompt_text
                            prompt_text = str(result)
                            logger.info(
                                f"Converted result to string: {prompt_text[:100]}..."
                            )
                            return prompt_text
            except Exception as e:
                logger.debug(f"Prompt {prompt_name} not in {tool_client.name}: {e}")
        raise Exception(f"Prompt '{prompt_name}' not found")

    async def list_all_resources(self):
        """List resources from all tool clients."""
        # Use cached data if available
        if self._available_resources is not None:
            # Convert from (idx, resource) to (tool_client, resource) format
            return [
                (self.tool_clients[idx], resource)
                for idx, resource in self._available_resources
            ]

        # Fall back to on-demand loading if not cached
        all_resources = []
        for tool_client in self.tool_clients:
            try:
                resources = await tool_client.list_resources()
                if resources and hasattr(resources, "resources"):
                    for resource in resources.resources:
                        all_resources.append((tool_client, resource))
            except Exception as e:
                logger.debug(f"Error listing resources from {tool_client.name}: {e}")
        return all_resources

    async def read_resource(self, uri: str):
        """Read a resource by URI from any client."""
        # Use cached resources if available for faster lookup
        if self._available_resources is not None:
            # Find the resource in cache to identify which client has it
            for client_idx, resource in self._available_resources:
                if hasattr(resource, "uri"):
                    # Convert resource.uri to string for comparison (it may be an AnyUrl object)
                    resource_uri = str(resource.uri)
                    if resource_uri == uri:
                        tool_client = self.tool_clients[client_idx]
                        try:
                            logger.info(
                                f"Reading resource {uri} from {tool_client.name} (cached lookup)"
                            )
                            result = await tool_client.read_resource(uri)
                            logger.info(f"Result: {result[:100]}")
                            if result:
                                return result
                        except Exception as e:
                            logger.debug(f"Error reading resource {uri}: {e}")
                            # Continue to fallback below
                            break

        # Fall back to trying all clients if not cached or not found in cache
        logger.debug(f"Resource {uri} not in cache or cache miss, trying all clients")
        last_error = None
        for tool_client in self.tool_clients:
            try:
                logger.info(
                    f"Reading resource {uri} from {tool_client.name} (fallback)"
                )
                result = await tool_client.read_resource(uri)
                logger.info(f"Result: {result[:100]}")
                if result:
                    return result
            except Exception as e:
                last_error = e
                logger.debug(f"Resource {uri} not in {tool_client.name}: {e}")

        # If no client had the resource, raise the last error
        if last_error:
            raise last_error
        raise Exception(f"Resource '{uri}' not found")


if __name__ == "__main__":
    import asyncio
    import os

    from badmcp.config import MCPServerConfig

    async def core():
        tool = ToolClient(
            mcp_config=MCPServerConfig(
                name="test",
                type="sse",
                url="http://localhost:12008/metamcp/testing/sse",
                bearerToken=os.getenv("METAMCP_API_KEY"),
            )
        )

        tool_chain = ToolChain([tool])
        await tool_chain.initialize()
        logger.info(tool_chain.available_tools)

        tool = tool_chain.find("Sequential-Thinking__sequentialthinking")
        logger.info(tool)
        response = await tool_chain.call(
            "Sequential-Thinking__sequentialthinking",
            {
                "thought": "something something something",
                "nextThoughtNeeded": True,
                "thoughtNumber": 1,
                "totalThoughts": 1,
            },
        )
        logger.info(response)

    asyncio.run(core())
