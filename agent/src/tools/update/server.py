"""MCP Server for triggering self-updates."""

import asyncio
import os
import signal

from mcp.server.fastmcp import FastMCP
from models import MCPResponse
from sparky.constants import SPARKY_CHAT_PID_FILE

# Initialize the MCP server
mcp = FastMCP("self-update-tools")


@mcp.tool()
async def trigger_self_update() -> dict:
    """Triggers the bot to update its source code from the main git branch and restart itself to apply the changes."""
    try:
        # Execute the update script in the background.
        # We don't wait for it to finish because this process will be killed.
        asyncio.create_task(
            asyncio.create_subprocess_shell("./scripts/update_and_restart.sh")
        )

        # Return a message indicating the process has started.
        # The bot will likely shut down before this message is fully processed.
        return MCPResponse.success(
            message="Self-update process initiated. The bot will restart shortly."
        ).to_dict()

    except Exception as e:
        return MCPResponse.error(f"Error initiating self-update: {str(e)}").to_dict()


@mcp.tool()
async def restart_chat_server() -> dict:
    """Restarts the chat server by sending a SIGTERM signal to the current process, allowing the process manager to restart it."""
    try:
        # Send SIGTERM to current process to trigger graceful shutdown
        # The process manager (like systemd, docker, or the update script) will restart it
        with open(SPARKY_CHAT_PID_FILE, "r") as f:
            pid = int(f.read())
        os.kill(pid, signal.SIGTERM)

        return MCPResponse.success(
            message="Server restart initiated. The process will shut down gracefully and be restarted by the process manager."
        ).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error restarting server: {str(e)}").to_dict()


@mcp.tool()
async def stop_server() -> dict:
    """Stops the chat server by sending a SIGTERM signal to the current process."""
    try:
        # Send SIGTERM to current process to trigger graceful shutdown
        with open(SPARKY_CHAT_PID_FILE, "r") as f:
            pid = int(f.read())
        os.kill(pid, signal.SIGTERM)

        return MCPResponse.success(
            message="Server stop initiated. The process will shut down gracefully."
        ).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error stopping server: {str(e)}").to_dict()


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
