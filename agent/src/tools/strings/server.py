from __future__ import annotations
import json
import mcp.server.stdio
from mcp.server import Server
from mcp.types import TextContent, Tool

# Simple strings utility MCP server
server = Server("badmcp-strings-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="concatenate_strings",
            description="Join a list of strings into one string.",
            inputSchema={
                "type": "object",
                "properties": {
                    "strings": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of strings to concatenate in order",
                    },
                    "separator": {
                        "type": "string",
                        "description": "Optional separator to insert between items",
                        "default": "",
                    },
                },
                "required": ["strings"],
            },
        ),
        Tool(
            name="split_string",
            description="Split text by a delimiter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "delimiter": {"type": "string"},
                    "maxsplit": {
                        "type": "integer",
                        "description": "Max number of splits (-1 = unlimited)",
                        "default": -1,
                    },
                },
                "required": ["text", "delimiter"],
            },
        ),
        Tool(
            name="replace_string",
            description="Replace occurrences of a substring with another substring.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "old": {"type": "string"},
                    "new": {"type": "string"},
                    "count": {
                        "type": "integer",
                        "description": "Max number of replacements (-1 = all)",
                        "default": -1,
                    },
                },
                "required": ["text", "old", "new"],
            },
        ),
        Tool(
            name="substring",
            description="Extract a substring from start (inclusive) to end (exclusive).",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "start": {"type": "integer"},
                    "end": {
                        "type": "integer",
                        "description": "Exclusive end index (omit or null to go to end)",
                        "default": None,
                    },
                },
                "required": ["text", "start"],
            },
        ),
        Tool(
            name="to_lower",
            description="Convert text to lowercase.",
            inputSchema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        ),
        Tool(
            name="to_upper",
            description="Convert text to uppercase.",
            inputSchema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        ),
        Tool(
            name="strip_whitespace",
            description="Strip leading and trailing whitespace.",
            inputSchema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        ),
        Tool(
            name="json_parse",
            description="Parse a JSON string into a Python object (dict or list).",
            inputSchema={
                "type": "object",
                "properties": {
                    "json_string": {"type": "string"},
                },
                "required": ["json_string"],
            },
        ),
        Tool(
            name="json_stringify",
            description="Convert a Python object (dict/list) to a JSON string.",
            inputSchema={
                "type": "object",
                "properties": {
                    "data": {"type": "object"},
                },
                "required": ["data"],
            },
        ),
        Tool(
            name="get_list_item",
            description="Retrieve an item from a list by index.",
            inputSchema={
                "type": "object",
                "properties": {"list_obj": {}, "index": {"type": "integer"}},
                "required": ["list_obj", "index"],
            },
        ),
        Tool(
            name="set_list_item",
            description="Set a list item at a specific index.",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_obj": {},
                    "index": {"type": "integer"},
                    "value": {},
                },
                "required": ["list_obj", "index", "value"],
            },
        ),
        Tool(
            name="append_to_list",
            description="Append an item to a list.",
            inputSchema={
                "type": "object",
                "properties": {"list_obj": {}, "item": {}},
                "required": ["list_obj", "item"],
            },
        ),
        Tool(
            name="get_dict_value",
            description="Get a value from a dict by key.",
            inputSchema={
                "type": "object",
                "properties": {"dict_obj": {}, "key": {"type": "string"}},
                "required": ["dict_obj", "key"],
            },
        ),
        Tool(
            name="set_dict_value",
            description="Set or update a value in a dict by key.",
            inputSchema={
                "type": "object",
                "properties": {"dict_obj": {}, "key": {"type": "string"}, "value": {}},
                "required": ["dict_obj", "key", "value"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "concatenate_strings":
            strings = arguments.get("strings")
            if not isinstance(strings, list) or not all(
                isinstance(s, str) for s in strings
            ):
                return [
                    TextContent(
                        type="text", text="Error: 'strings' must be a list of strings"
                    )
                ]
            sep = arguments.get("separator", "")
            return [TextContent(type="text", text=sep.join(strings))]

        elif name == "split_string":
            text = arguments.get("text", "")
            delimiter = arguments.get("delimiter")
            if delimiter is None:
                return [TextContent(type="text", text="Error: 'delimiter' is required")]
            maxsplit = int(arguments.get("maxsplit", -1))
            parts = text.split(delimiter, maxsplit if maxsplit >= 0 else -1)
            # Return as a JSON-like string representation to keep TextContent
            return [TextContent(type="text", text=json.dumps(parts))]

        elif name == "replace_string":
            text = arguments.get("text", "")
            old = arguments.get("old")
            new = arguments.get("new", "")
            if old is None:
                return [TextContent(type="text", text="Error: 'old' is required")]
            count = int(arguments.get("count", -1))
            return [
                TextContent(
                    type="text",
                    text=text.replace(
                        old, new, count if count >= 0 else text.count(old)
                    ),
                )
            ]

        elif name == "substring":
            text = arguments.get("text", "")
            start = arguments.get("start")
            end = arguments.get("end", None)
            if start is None:
                return [TextContent(type="text", text="Error: 'start' is required")]
            try:
                s_idx = int(start)
                e_idx = None if end in (None, "") else int(end)
                return [TextContent(type="text", text=text[s_idx:e_idx])]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {e}")]

        elif name == "to_lower":
            return [
                TextContent(type="text", text=str(arguments.get("text", "").lower()))
            ]

        elif name == "to_upper":
            return [
                TextContent(type="text", text=str(arguments.get("text", "").upper()))
            ]

        elif name == "strip_whitespace":
            return [
                TextContent(type="text", text=str(arguments.get("text", "").strip()))
            ]

        elif name == "get_list_item":
            lst = arguments["list_obj"]
            idx = int(arguments["index"])
            return [TextContent(type="text", text=json.dumps(lst[idx]))]
        elif name == "set_list_item":
            lst = arguments["list_obj"]
            idx = int(arguments["index"])
            value = arguments["value"]
            lst[idx] = value
            return [TextContent(type="text", text=json.dumps(lst))]
        elif name == "append_to_list":
            lst = arguments["list_obj"]
            item = arguments["item"]
            lst.append(item)
            return [TextContent(type="text", text=json.dumps(lst))]
        elif name == "get_dict_value":
            d = arguments["dict_obj"]
            key = arguments["key"]
            return [TextContent(type="text", text=json.dumps(d.get(key)))]
        elif name == "set_dict_value":
            d = arguments["dict_obj"]
            key = arguments["key"]
            value = arguments["value"]
            d[key] = value
            return [TextContent(type="text", text=json.dumps(d))]
        elif name == "json_parse":
            json_string = arguments.get("json_string", "")
            try:
                parsed_data = json.loads(json_string)
                # To maintain the structure for other tools, we send it as a JSON string
                return [TextContent(type="text", text=json.dumps(parsed_data))]
            except json.JSONDecodeError as e:
                return [
                    TextContent(type="text", text=f"Error: Invalid JSON string: {e}")
                ]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        elif name == "json_stringify":
            data = arguments.get("data")
            if data is None:
                return [TextContent(type="text", text="Error: 'data' is required")]
            try:
                return [TextContent(type="text", text=json.dumps(data))]
            except TypeError as e:
                return [
                    TextContent(
                        type="text", text=f"Error: Object is not JSON serializable: {e}"
                    )
                ]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
