import asyncio
from logging import getLogger

from badmcp.tool_client import ToolClient

logger = getLogger(__name__)


class Control:
    def __init__(self, tool_clients: list[ToolClient]):
        self.tool_clients = tool_clients

    async def restart_all(self):
        logger.warning("Restarting all tool servers...")
        for tool_client in self.tool_clients:
            await tool_client.restart()
        logger.info("All tool servers restarted.")

    async def restart_by_name(self, name: str):
        tool_client = self.find_by_name(name)
        if tool_client:
            logger.warning(f"Restarting {name} tool server...")
            await tool_client.restart()
            logger.info(f"{name} tool server restarted.")
        else:
            logger.error(f"Tool server {name} not found.")

    async def start_all(self):
        logger.warning("Starting all tool servers...")
        await asyncio.gather(
            *[tool_client.start() for tool_client in self.tool_clients]
        )
        logger.info("All tool servers started.")

    async def start_by_name(self, name: str):
        tool_client = self.find_by_name(name)
        if tool_client:
            logger.warning(f"Starting {name} tool server...")
            await tool_client.start()
            logger.info(f"{name} tool server started.")
        else:
            logger.error(f"Tool server {name} not found.")

    async def stop_all(self):
        logger.warning("Stopping all tool servers...")
        for tool_client in self.tool_clients:
            await tool_client.stop()
        logger.info("All tool servers stopped.")

    async def stop_by_name(self, name: str):
        tool_client = self.find_by_name(name)
        if tool_client:
            logger.warning(f"Stopping {name} tool server...")
            await tool_client.stop()
            logger.info(f"{name} tool server stopped.")
        else:
            logger.error(f"Tool server {name} not found.")

    async def close(self):
        """Close all tool server connections and clean up."""
        await self.stop_all()

    def find_by_name(self, name: str) -> ToolClient | None:
        for tool_client in self.tool_clients:
            if tool_client.name == name:
                return tool_client
        return None
