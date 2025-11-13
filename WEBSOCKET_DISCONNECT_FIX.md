# WebSocket Disconnect Error Fix

## Issue
When users refresh the page or disconnect mid-task, the server threw errors:

```
RuntimeError: Unexpected ASGI message 'websocket.send', after sending 'websocket.close' or response already completed.
```

## Root Cause

**Sequence of events:**
1. User viewing task with WebSocket connected
2. Task agent is executing and sending updates via WebSocket
3. User refreshes page → WebSocket disconnects
4. ConnectionManager removes WebSocket from `active_connections`
5. Task agent still has reference to old `WebSocketForwarder` with closed connection
6. Task tries to send message → RuntimeError

**Why it happened:**
- Tasks can run longer than WebSocket connections
- WebSocketForwarder held a direct reference to the WebSocket
- No error handling for closed connections

## Solution

### 1. Graceful Error Handling in WebSocketForwarder

Added specific handling for closed WebSocket connections:

```python
try:
    await self.websocket.send_text(message_text)
    # ... success logging
except RuntimeError as e:
    # WebSocket was closed (user refreshed, disconnected, etc.)
    if "websocket.close" in str(e).lower() or "already completed" in str(e).lower():
        logger.debug(f"🔌 WebSocket closed - skipping message")
        return False
    # Other RuntimeError
    logger.error(f"RuntimeError: {e}")
    return False
```

**Benefits:**
- No more error spam in logs
- Task continues executing even if user disconnects
- Debug-level logging instead of errors (expected behavior)

### 2. Improved Disconnect Logging

Added user_id to disconnect logs for easier debugging:

```python
logger.info(
    f"[{session_id}] WebSocket disconnected (session preserved), user={user_id}"
)
```

## Behavior After Fix

### When User Refreshes During Task:

**Before:**
- ❌ RuntimeError exceptions in logs
- ❌ Stack traces cluttering logs
- ✅ Task continues (but with errors)

**After:**
- ✅ Clean debug log: "🔌 WebSocket closed - skipping message"
- ✅ Task continues silently
- ✅ No error spam
- ✅ When user reconnects, new forwarder created

### When User Reconnects:

1. User opens page again
2. WebSocket reconnects with same `user_id`
3. ConnectionManager maps new WebSocket to user
4. Next task run creates new forwarder with new WebSocket
5. Updates resume appearing in UI

## Edge Cases Handled

### Case 1: User refreshes multiple times during task
- Each refresh creates new WebSocket
- Old forwarders gracefully fail silently
- New forwarder created on next task execution
- No duplicate messages

### Case 2: Task completes after disconnect
- Task completion message fails silently
- Task status updated in database (not affected)
- User sees completion when they check later

### Case 3: Long-running scheduled task
- Task runs for 30+ minutes
- User may connect/disconnect multiple times
- Each WebSocket lifecycle is independent
- No interference between connections

## Files Modified

- `agent/src/utils/websocket_forwarder.py` - Added RuntimeError handling
- `agent/src/servers/chat/chat_server.py` - Improved disconnect logging

## Testing

### Test 1: Refresh During Task
```bash
# Start task
sparky agent tasks add "Complex task that takes 2+ minutes"

# In browser:
1. Watch updates appear
2. Refresh page mid-task
3. Check logs for debug message (not error)
4. Reconnect - task should complete normally
```

**Expected:** Debug log only, no errors

### Test 2: Multiple Refreshes
```bash
# Long running task
sparky agent tasks add "Run smart maintenance"

# In browser:
1. Refresh 3-4 times during execution
2. Check logs
3. No RuntimeError exceptions
```

**Expected:** Multiple "🔌 WebSocket closed" debug logs, no errors

### Test 3: Task Completion After Disconnect
```bash
# Start task, immediately close browser
sparky agent tasks add "Quick task"
# Close browser within 1 second

# Check task status
sparky agent tasks list --status completed
```

**Expected:** Task completes successfully despite no WebSocket

## Migration

No breaking changes. Safe to deploy immediately:
- ✅ No database changes
- ✅ No config changes  
- ✅ No API changes
- ✅ Backward compatible

Existing deployments benefit immediately without any updates required.

