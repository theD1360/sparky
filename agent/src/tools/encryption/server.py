"""MCP Server: Encryption and Encoding Tools."""

import base64

from mcp.server.fastmcp import FastMCP

from models import MCPResponse

# Initialize the MCP server
mcp = FastMCP("encryption-tools")


@mcp.tool()
async def base64_encode(data: str, encoding: str = "utf-8") -> dict:
    """Encode a string to Base64."""
    try:
        input_bytes = data.encode(encoding)
        encoded_bytes = base64.b64encode(input_bytes)
        encoded_string = encoded_bytes.decode(encoding)
        result = {"encoded_string": encoded_string}
        return MCPResponse.success(result=result).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Encoding error: {e}").to_dict()


@mcp.tool()
async def base64_decode(data: str, encoding: str = "utf-8") -> dict:
    """Decode a Base64 string."""
    try:
        input_bytes = data.encode(encoding)
        decoded_bytes = base64.b64decode(input_bytes)
        decoded_string = decoded_bytes.decode(encoding)
        result = {"decoded_string": decoded_string}
        return MCPResponse.success(result=result).to_dict()
    except Exception as e:
        return MCPResponse.error(f"Decoding error: {e}").to_dict()


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
