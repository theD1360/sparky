import psutil
from mcp.server.fastmcp import FastMCP

from models import MCPResponse

# Initialize the MCP server
mcp = FastMCP("introspection-tools")


@mcp.tool()
async def get_system_metrics() -> dict:
    """Get system metrics such as CPU usage, memory usage, and disk usage."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        disk_usage_percent = psutil.disk_usage("/").percent
        result = {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "disk_usage_percent": disk_usage_percent,
        }
        return MCPResponse.success(result=result).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Error getting system metrics: {str(e)}").to_dict()


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
