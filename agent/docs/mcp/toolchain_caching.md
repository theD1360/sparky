# LangChain Toolchain Management

## Overview

The toolchain management system provides per-user LangChain toolchain instances with lazy loading. This ensures:

1. **Lazy Loading**: Tools are loaded only when the first web client connects for a user, not at server startup
2. **Real Progress**: The splash screen shows actual tool loading progress
3. **Per-User Isolation**: Each user gets their own toolchain instance for stateful sessions
4. **Automatic Cleanup**: Toolchains are cleaned up when users disconnect

## Architecture

### Components

- **`LangChainToolchain`**: Wrapper around `MultiServerMCPClient` for LangChain integration
- **`ConnectionManager`**: Manages per-user toolchain instances and WebSocket connections
- **`create_langchain_toolchain()`**: Factory function to create toolchain instances from MCP config

### Flow

```
1. First WebSocket Connection for a User
   ├─> ConnectionManager.initialize_tools_for_user()
   ├─> create_langchain_toolchain()
   │   ├─> Load MCP server configurations
   │   ├─> Create MultiServerMCPClient with all servers
   │   └─> Return LangChainToolchain instance
   ├─> Store in ConnectionManager.langchain_toolchains[user_id]
   └─> Send 'ready' message to client

2. Subsequent Connections (Same User)
   ├─> Check if toolchain exists for user_id
   ├─> If yes: Reuse existing toolchain
   └─> If no: Create new toolchain (user reconnected)

3. User Disconnection
   ├─> Cleanup toolchain via cleanup() method
   └─> Remove from ConnectionManager.langchain_toolchains
```

## Key Differences from Previous System

### Previous System (Deprecated)
- Global singleton cache with TTL-based invalidation
- Shared toolchain across all users
- Staggered cache expiration
- `ToolChainCache` and `ToolServerCache` classes

### Current System
- **Per-user toolchains**: Each user gets their own `LangChainToolchain` instance
- **No caching**: Toolchains are created fresh per user connection
- **Stateful sessions**: Each toolchain maintains its own MCP session state
- **Simpler architecture**: Direct creation, no TTL management

## Usage

### Creating a Toolchain

```python
from sparky.initialization import create_langchain_toolchain

# Create toolchain with all configured servers
toolchain, error = await create_langchain_toolchain()

# Create toolchain with specific servers
toolchain, error = await create_langchain_toolchain(
    tools=["filesystem", "github"],
    log_prefix="[user:123]"
)
```

### Using Toolchain in Agent

```python
from sparky.agent_orchestrator import AgentOrchestrator

# Toolchain is passed to AgentOrchestrator
bot = AgentOrchestrator(
    provider=provider,
    langchain_toolchain=toolchain,  # Per-user toolchain
    # ... other services
)
```

### Getting Tools

```python
# Get all LangChain tools from the toolchain
tools = await toolchain.get_langchain_tools()

# Get tools from a specific server
tools = await toolchain.get_langchain_tools(server_name="filesystem")
```

### Calling Tools Directly

```python
# Execute a tool by name
result = await toolchain.call_tool("git_branch", {})
```

### Listing Prompts and Resources

```python
# List all prompts (returns (server_name, prompt_name) tuples)
prompts = await toolchain.list_prompts()

# Get a prompt
prompt_text = await toolchain.get_prompt("server_name", "prompt_name", arguments={})

# List all resources (returns (server_name, resource_uri) tuples)
resources = await toolchain.list_resources()

# Read a resource
content = await toolchain.read_resource("resource://uri")
```

## Connection Manager Integration

The `ConnectionManager` in `chat_server.py` manages toolchains per user:

```python
class ConnectionManager:
    def __init__(self):
        # user_id -> LangChainToolchain instance
        self.langchain_toolchains: Dict[str, LangChainToolchain] = {}
        self.tools_initialized: Dict[str, bool] = {}
    
    async def initialize_tools_for_user(self, user_id: str, websocket: WebSocket):
        """Initialize tools for a user with progress updates."""
        # Check if already initialized
        if user_id in self.langchain_toolchains:
            return self.langchain_toolchains[user_id], None
        
        # Create new toolchain
        toolchain, error = await create_langchain_toolchain(
            log_prefix=f"[{user_id}]"
        )
        
        if toolchain:
            self.langchain_toolchains[user_id] = toolchain
            self.tools_initialized[user_id] = True
        
        return toolchain, error
```

## Benefits

### Performance
- **Fast startup**: Server starts immediately without waiting for tools
- **Lazy loading**: Tools loaded only when needed
- **Parallel loading**: Multiple users can load tools concurrently

### User Experience
- **True progress**: Splash screen shows actual loading status
- **Isolated sessions**: Each user's toolchain is independent
- **Stateful**: MCP sessions maintain state per user

### Reliability
- **Per-user isolation**: One user's toolchain issues don't affect others
- **Automatic cleanup**: Toolchains cleaned up on disconnect
- **Error handling**: Failed toolchain creation doesn't block server

## Configuration

### MCP Server Configuration

Toolchains are created from MCP configuration files. See MCP documentation for server setup.

### Environment Variables

No specific environment variables for toolchain management. Uses standard MCP configuration.

## Monitoring

### Log Messages

Key log messages to monitor:
```
INFO: [user:123] Creating LangChain toolchain...
INFO: [user:123] Creating toolchain with 3 server(s): filesystem, github, database
INFO: [user:123] LangChain toolchain created successfully
INFO: [user:123] Tools initialized successfully: 45 tool(s) from 3 server(s)
```

### Connection Manager Status

Check active toolchains via admin endpoints:
```bash
curl http://localhost:8000/api/admin/toolchain_status
```

## Troubleshooting

### Issue: Tools not loading
**Symptom**: Splash screen stuck on "Connecting to server..."

**Solution**:
1. Check server logs for errors (look for `[user:xxx]` prefix)
2. Verify MCP config files are valid
3. Check WebSocket connection status
4. Verify user_id is being passed correctly

### Issue: Toolchain not found for user
**Symptom**: Error "LangChainToolchain not initialized for user"

**Solution**:
1. Ensure `initialize_tools_for_user()` is called before creating AgentOrchestrator
2. Check that user_id matches between initialization and usage
3. Verify toolchain was created successfully (check logs)

### Issue: Tools not working
**Symptom**: Tool calls fail or return errors

**Solution**:
1. Check MCP server logs
2. Verify server configurations are correct
3. Check network connectivity for HTTP/SSE servers
4. Verify stdio server commands are correct

## Cleanup

Toolchains are automatically cleaned up when:
- User disconnects from WebSocket
- Server shuts down
- Explicit cleanup is called

```python
# Manual cleanup
await toolchain.cleanup()
```

## Migration Notes

If migrating from the old `ToolChainCache` system:

1. **No global cache**: Each user gets their own toolchain
2. **No TTL**: Toolchains exist for the lifetime of the user connection
3. **Different API**: Use `LangChainToolchain` methods instead of `ToolChain` methods
4. **LangChain integration**: Tools are LangChain `BaseTool` instances, not MCP tools directly

## Related Files

- `agent/src/sparky/langchain_toolchain.py` - LangChainToolchain implementation
- `agent/src/sparky/initialization.py` - Toolchain creation functions
- `agent/src/servers/chat/chat_server.py` - ConnectionManager integration
- `agent/src/sparky/agent_orchestrator.py` - Agent integration
