# ResourceFetchingMiddleware

A message middleware that automatically fetches and inserts MCP resource content into user messages using the `@<resource>` syntax.

## Overview

The `ResourceFetchingMiddleware` intercepts messages before they reach the AI model and replaces `@<resource>` patterns with actual content from MCP resources. This allows users to easily reference and include resource data in their messages without manually fetching it.

## Features

- **Flexible Resource References**: Supports both full URIs (e.g., `@knowledge://stats`) and short names (e.g., `@stats`)
- **Multiple Resources**: Can fetch and insert multiple resources in a single message
- **Smart Formatting**: Automatically formats JSON resources with syntax highlighting
- **Error Handling**: Gracefully handles missing resources and provides helpful suggestions
- **Non-blocking**: Continues with the original message if resource fetching fails

## Usage

### Basic Setup

```python
from sparky import Bot, ResourceFetchingMiddleware

bot = Bot(
    middlewares=[ResourceFetchingMiddleware()],
    toolchain=toolchain,
    model_name="gemini-2.0-flash",
)
```

### Example Messages

#### Using Full URI
```
User: "Show me the current stats @knowledge://stats"
```

#### Using Short Name
```
User: "What memories do we have? @memories"
```

#### Multiple Resources
```
User: "Compare @stats with @workflows and summarize the differences"
```

## How It Works

1. **Pattern Matching**: Scans the message for `@<resource>` patterns
2. **Resource Lookup**: Queries available resources from the toolchain
3. **Content Fetching**: Retrieves the content using `read_resource(uri)`
4. **Formatting**: Formats the content (pretty-prints JSON if applicable)
5. **Replacement**: Replaces `@<resource>` with the formatted content
6. **Continuation**: Passes the modified message to the next middleware

## Resource Name Matching

The middleware uses a smart matching system:

- **Full URI**: `@knowledge://stats` → matches `knowledge://stats`
- **Path without scheme**: `@stats` → matches the last part of `knowledge://stats`
- **Partial path**: `@tool-usage/recent` → matches `knowledge://tool-usage/recent`

## Content Formatting

### JSON Resources
```
[Resource: knowledge://stats]
```json
{
  "total_nodes": 100,
  "total_edges": 50
}
```
```

### Plain Text Resources
```
[Resource: knowledge://readme]
This is the content of the resource...
```

## Error Handling

When a resource is not found:
```
[Resource 'nonexistent' not found. Available resources: stats, memories, workflows, ...]
```

When fetching fails:
```
[Error fetching resource 'knowledge://stats': Connection timeout]
```

## Integration

The middleware is automatically registered in:
- **Chat Server** (`src/servers/chat/chat_server.py`)
- **Task Server** (`src/servers/task/task_server.py`)

Order of middlewares:
1. `SelfModificationGuard()` - Prevents unauthorized modifications
2. `ResourceFetchingMiddleware()` - Fetches resource content
3. `CommandPromptMiddleware()` - Processes commands

## Testing

Run the test suite:
```bash
poetry run pytest tests/test_resource_middleware.py -v
```

See the example:
```bash
poetry run python examples/resource_middleware_example.py
```

## Implementation Details

- **File**: `src/sparky/middleware/message_middlewares.py`
- **Class**: `ResourceFetchingMiddleware`
- **Type**: `MiddlewareType.MESSAGE`
- **Pattern**: `r"@([\w:/\-\.]+)"`

## Best Practices

1. **Use Descriptive Names**: Choose resource URIs that are easy to remember
2. **Combine with Commands**: Use resources with `/` commands for powerful queries
3. **Monitor Performance**: Large resources may increase message processing time
4. **Handle Errors**: Design prompts to handle cases where resources might not exist

## See Also

- [Middleware System](../README.md#middleware)
- [MCP Resources](https://modelcontextprotocol.io/docs/resources)
- [CommandPromptMiddleware](./command-prompt-middleware.md)

