# Tool Chain Caching System

## Overview

The tool chain caching system provides intelligent, lazy-loaded MCP tool servers with per-server cache invalidation. This ensures:

1. **Lazy Loading**: Tools are loaded only when the first web client connects, not at server startup
2. **Real Progress**: The splash screen shows actual tool loading progress
3. **Caching**: Tool servers are cached and shared across sessions for performance
4. **Staggered Invalidation**: Each tool server has a unique TTL to prevent all servers from reloading simultaneously

## Architecture

### Components

- **`ToolChainCache`**: Main caching class that manages tool server lifecycle
- **`ToolServerCache`**: Individual cache entry for each tool server with TTL
- **Global Singleton**: `get_toolchain_cache()` provides shared cache instance

### Flow

```
1. First WebSocket Connection
   ├─> ConnectionManager.initialize_tools_for_session()
   ├─> ToolChainCache.get_or_load_toolchain()
   │   ├─> Load each MCP server (with progress callbacks)
   │   ├─> Cache with staggered TTL
   │   └─> Build ToolChain
   └─> Send 'ready' message to client

2. Subsequent Connections
   ├─> Check if tools already initialized for session
   ├─> If yes: Use existing toolchain reference
   └─> If no: Use cached toolchain (no reload needed)

3. Cache Expiration
   ├─> Each server checked independently
   ├─> Expired servers reloaded on next connection
   └─> Other servers remain cached
```

## Cache TTL Strategy

### Base TTL
- Default: 60 minutes per server

### Staggering Mechanism
1. **Hash-based variance**: Each server gets ±20% variance based on name hash (48-72 min)
2. **Load-count offset**: Additional 0-30 min offset based on how many times loaded
3. **Result**: Servers reload at different times, spreading the load

### Example
```
Server A: 52 minutes (base=60, variance=-8, offset=0)
Server B: 67 minutes (base=60, variance=+2, offset=5)
Server C: 75 minutes (base=60, variance=+5, offset=10)
```

## Usage

### Getting Cache Status

HTTP endpoint for monitoring:
```bash
curl http://localhost:8000/api/admin/tool_cache_status
```

Response:
```json
{
  "success": true,
  "cache_initialized": true,
  "total_servers": 3,
  "servers": {
    "filesystem": {
      "loaded_at": "2025-11-13T10:30:00",
      "age_minutes": 15.3,
      "ttl_minutes": 65,
      "expired": false,
      "load_count": 1
    },
    "github": {
      "loaded_at": "2025-11-13T10:30:01",
      "age_minutes": 15.3,
      "ttl_minutes": 58,
      "expired": false,
      "load_count": 1
    }
  }
}
```

### Force Reload a Server

Programmatically (future feature):
```python
from sparky.toolchain_cache import get_toolchain_cache

cache = get_toolchain_cache()
success = await cache.force_reload_server("filesystem")
```

## Benefits

### Performance
- **Fast startup**: Server starts immediately without waiting for tools
- **Shared cache**: Multiple sessions benefit from cached tools
- **Selective reload**: Only expired servers reload, not all

### User Experience
- **True progress**: Splash screen shows actual loading status
- **Faster connections**: Subsequent connections use cached tools
- **No waiting**: No artificial delays in progress updates

### Reliability
- **Staggered invalidation**: Prevents thundering herd problem
- **Per-server control**: Each tool server managed independently
- **Automatic cleanup**: Old clients properly stopped and cleaned up

## Configuration

### Environment Variables

Future enhancement - configurable TTL:
```bash
# Base TTL in minutes (default: 60)
SPARKY_TOOL_CACHE_TTL=60

# TTL variance percentage (default: 20)
SPARKY_TOOL_CACHE_VARIANCE=20
```

### Code Configuration

Modify `ToolChainCache.BASE_TTL_MINUTES`:
```python
class ToolChainCache:
    # Base TTL for tool servers (in minutes)
    BASE_TTL_MINUTES = 60  # Change this value
```

## Monitoring

### Log Messages

Key log messages to monitor:
```
INFO: Server ready - toolchain will be initialized on first client connection
INFO: Loading 3 server(s) out of 3 total
INFO: Successfully loaded server 'filesystem' (TTL: 65 min)
INFO: Server 'github' cache expired (age: 61.2 min, ttl: 60 min), will reload
```

### Metrics

Track these metrics:
- Cache hit rate (sessions using cached vs loading)
- Tool loading duration per server
- Cache age distribution
- Reload frequency per server

## Troubleshooting

### Issue: Tools not loading
**Symptom**: Splash screen stuck on "Connecting to server..."

**Solution**:
1. Check server logs for errors
2. Verify MCP config files are valid
3. Check `/api/admin/tool_cache_status` for errors

### Issue: Frequent reloads
**Symptom**: Tools reload on every connection

**Solution**:
1. Check if TTL is too short
2. Verify cache is not being cleared
3. Check for exceptions during tool initialization

### Issue: All servers reload at once
**Symptom**: Performance degradation when cache expires

**Solution**:
1. This should NOT happen with staggering
2. If it does, check hash function
3. Increase TTL variance percentage

## Future Enhancements

1. **Configurable TTL**: Per-server TTL configuration
2. **Manual control**: API endpoints to reload/clear cache
3. **Health checks**: Periodic server health validation
4. **Metrics**: Prometheus/Grafana integration
5. **Warm cache**: Pre-load popular tools on startup (optional)

## Related Files

- `agent/src/sparky/toolchain_cache.py` - Main implementation
- `agent/src/servers/chat/chat_server.py` - Integration
- `agent/src/badmcp/tool_chain.py` - Tool chain core
- `web_ui/src/SplashScreen.js` - Progress display

