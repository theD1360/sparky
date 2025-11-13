# WebSocket Task Agent - Bug Fixes

## Issues Fixed

### Issue 1: Duplicate Event Subscriptions ✅
**Problem:** Event handlers were being subscribed multiple times for reused bot instances (scheduled tasks), causing duplicate WebSocket messages.

**Root Cause:** Event subscription code was outside the `if not is_reused:` block, so it ran on every task execution.

**Solution:**
- Added `_chat_websocket_forwarders` dict to track forwarders by chat_id
- Event subscription only happens once when bot is created (inside `if not is_reused:` block)
- Event handlers use dynamic lookup to always reference the current forwarder
- When a task runs again, we update the forwarder in the dict, and existing handlers find it

**Files Changed:**
- `agent/src/servers/task/task_server.py`

### Issue 2: Incorrect Tool Result Handler Signature ✅
**Problem:** The `on_tool_result` event handler had the wrong function signature, causing errors during tool execution.

**Root Cause:** The handler expected one parameter `(result)` but the `TOOL_RESULT` event is dispatched with two: `(tool_name, result)`.

**Solution:**
- Fixed handler signature from `on_tool_result(result: Any)` to `on_tool_result(tool_name: str, result: str)`
- This matches the actual event dispatch: `events.async_dispatch(BotEvents.TOOL_RESULT, tool_name, result_str)`

**Files Changed:**
- `agent/src/servers/task/task_server.py`

**Impact:** This was likely causing the agent to struggle with tool execution, especially in smart_maintenance tasks that rely heavily on tools.

### Issue 3: Improved Logging for Message Routing 📊
**Problem:** Messages appearing in wrong chats - difficult to diagnose without proper logging.

**Solution:**
- Added detailed logging in WebSocketForwarder showing user_id, session_id, and chat_id for every message
- Added logging when forwarder is created vs when connection is not available
- Added emoji indicators for easier log scanning: ✅ 📤 ℹ️

**Files Changed:**
- `agent/src/utils/websocket_forwarder.py`
- `agent/src/servers/task/task_server.py`

## Message Routing Architecture

### How It Works:
1. **Backend:** WebSocketForwarder includes `chat_id` in every message
2. **Frontend:** Filters messages based on `currentChatId` (see `App.js` lines 656-663)
3. **Filtering Logic:**
   ```javascript
   // Frontend filters messages unless:
   // - It's a global message (session_info, ready, etc.), OR
   // - The message's chat_id matches the current chat
   if (messageChatId && currentChatId && messageChatId !== currentChatId && !isGlobalMessage) {
     console.warn(`Ignoring message for chat ${messageChatId}, current chat is ${currentChatId}`);
     return;
   }
   ```

### Debugging Message Routing:

To diagnose routing issues, check the logs:

1. **Backend logs:** Look for:
   ```
   ✅ WebSocket forwarder created: task=<id>, chat=<chat_id>, user=agent
   📤 Sent <message_type> message to user=agent, session=<session>, chat=<chat_id>
   ```

2. **Browser console:** Look for:
   ```
   Ignoring message for chat <chat_id>, current chat is <other_chat_id>
   ```

3. **Verify:** The `chat_id` in backend logs should match the chat you're viewing in the UI

### Common Scenarios:

- **User viewing different chat:** Messages filtered by frontend (expected behavior)
- **User on home page:** `currentChatId` is null, messages NOT filtered (might see them)
- **User viewing task's chat:** Messages appear in real-time (expected behavior)

## Testing the Fixes

### Test 1: No Duplicate Messages
```bash
# Start server with agent loop
export SPARKY_ENABLE_AGENT_LOOP=true
sparky chat

# Add scheduled task multiple times
sparky agent tasks add "Test task 1"
# Wait for completion
sparky agent tasks add "Test task 2"

# Expected: Each tool call appears only ONCE per execution
```

### Test 2: Tool Execution Works
```bash
# Add a task that uses tools
sparky agent tasks add "Check knowledge graph stats and validate integrity"

# Expected: Tools execute successfully without errors
# Check logs for successful tool use and results
```

### Test 3: Message Routing
```bash
# In UI: Log in as user "agent"
# Open chat A (not the task's chat)
# Add a task that will execute in chat B

# Expected: 
# - Backend logs show messages sent with chat_id=B
# - Frontend console shows "Ignoring message for chat B, current chat is A"
# - Messages don't appear in chat A

# Switch to chat B in UI
# Expected:
# - Messages for chat B now appear
```

## Files Modified

- `agent/src/servers/task/task_server.py` - Fixed event subscription and handler signatures
- `agent/src/utils/websocket_forwarder.py` - Added detailed logging

## Migration Notes

No breaking changes. Existing deployments can update without changes to:
- Database
- Configuration
- Environment variables
- API contracts

The fixes are backward compatible and improve reliability without changing behavior.

