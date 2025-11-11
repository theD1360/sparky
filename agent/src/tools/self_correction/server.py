import os

import google.generativeai as genai
import mcp.server.stdio
from dotenv import load_dotenv
from mcp.server import Server
from mcp.types import TextContent, Tool

# Load environment variables
load_dotenv()

# Initialize the MCP server
server = Server("self-correction-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for the MCP server."""
    return [
        Tool(
            name="self_correct",
            description="Review a plan or code against a checklist of questions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text_to_review": {
                        "type": "string",
                        "description": "The text to review.",
                    },
                    "checklist": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "A list of questions to answer about the text.",
                    },
                },
                "required": ["text_to_review", "checklist"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""

    # Configure API
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return [
            TextContent(
                type="text",
                text="Error: GOOGLE_API_KEY not found in environment variables",
            )
        ]

    genai.configure(api_key=api_key)

    if name == "self_correct":
        text_to_review = arguments.get("text_to_review")
        checklist = arguments.get("checklist")

        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"Please review the following text and answer the checklist questions below.\\n\\nText to review:\\n{text_to_review}\\n\\nChecklist:\\n"
            for question in checklist:
                prompt += f"- {question}\\n"

            response = model.generate_content(prompt)
            return [TextContent(type="text", text=response.text)]
        except Exception as e:
            return [
                TextContent(type="text", text=f"Error during self-correction: {str(e)}")
            ]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
