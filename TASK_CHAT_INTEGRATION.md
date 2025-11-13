# Task-Chat Integration

## Overview

Tasks can now be executed within existing chat contexts, allowing task results to appear directly in user chats with proper attribution and context awareness.

## Key Features

### 1. Chat-Specific Task Execution

Tasks can optionally specify a `chat_id` to execute in:
- **With chat_id:** Task executes in that chat, using the chat's user_id
- **Without chat_id:** Task creates its own chat (original behavior)

### 2. User Context Inheritance

When a task specifies a chat_id:
- Task looks up the chat's `user_id` from the knowledge graph
- Bot instance is created with that user_id
- All messages and tool calls attributed to the chat's user
- Task appears as part of the natural conversation flow

### 3. Task Message Attribution

All task-related messages include `task_id` in their payload:
```json
{
  "type": "message",
  "data": {
    "text": "Task result...",
    "task_id": "abc123..."
  },
  "session_id": "...",
  "user_id": "...",
  "chat_id": "..."
}
```

The UI can use this to display task messages with special indicators (e.g., 🤖 badge).

### 4. WebSocket Routing

Messages are routed to anyone viewing the specified chat:
- Task messages go to the chat_id's active WebSocket connections
- Multiple users can watch the same chat
- No restriction on who receives updates

## Usage

### Creating Tasks in Specific Chats

**CLI:**
```bash
# Add task to a specific chat
sparky agent tasks add "Summarize our conversation" --chat <chat_id>

# Add task with metadata and chat
sparky agent tasks add "Research topic X" \
  --chat <chat_id> \
  --metadata priority=high
```

**Programmatically:**
```python
from sparky.task_queue import create_task_queue

task_queue = create_task_queue()
task = await task_queue.add_task(
    instruction="Your task here",
    chat_id="chat-uuid-here",
    metadata={"source": "user_request"}
)
```

### Creating Tasks Without Chat (Original Behavior)

```bash
# Task creates its own chat
sparky agent tasks add "Background research"

# This is useful for:
# - Scheduled maintenance tasks
# - Agent-initiated tasks
# - Tasks that don't belong to user conversations
```

## Architecture

### Task Flow with chat_id

```
1. Task created with chat_id
   ↓
2. Task queue stores chat_id in metadata
   ↓
3. Agent loop picks up task
   ↓
4. Look up chat to get user_id
   ↓
5. Create new bot instance with user's identity
   ↓
6. Execute in chat context
   ↓
7. WebSocket messages → chat's active connections
   ↓
8. UI displays with task indicator (🤖)
```

### Task Flow without chat_id

```
1. Task created without chat_id
   ↓
2. Agent loop picks up task
   ↓
3. TaskService creates new chat (or reuses for scheduled tasks)
   ↓
4. Bot created with user_id="agent"
   ↓
5. Execute in agent's chat
   ↓
6. WebSocket messages → agent user's connections
```

## Implementation Details

### 1. Task Queue Changes

**`add_task()` signature:**
```python
async def add_task(
    self,
    instruction: str,
    metadata: Optional[Dict[str, Any]] = None,
    depends_on: Optional[List[str]] = None,
    allow_duplicates: bool = False,
    chat_id: Optional[str] = None,  # NEW
) -> Dict[str, Any]:
```

**Storage:**
- `chat_id` stored in `metadata["chat_id"]`
- Persists in knowledge graph Task node properties

### 2. Message Payload Updates

All message payloads now include optional `task_id`:

- `ChatMessagePayload.task_id`
- `StatusPayload.task_id`
- `ErrorPayload.task_id`
- `ToolUsePayload.task_id`
- `ToolResultPayload.task_id`
- `ThoughtPayload.task_id`

### 3. WebSocketForwarder Updates

**Constructor:**
```python
def __init__(
    self,
    websocket: Any,
    session_id: str,
    user_id: str,
    chat_id: str,
    task_id: Optional[str] = None,  # NEW
):
```

All forward methods now include task_id in payloads.

### 4. Task Execution Logic

**In `AgentLoop._on_task_available()`:**

```python
# 1. Check if task has chat_id
task_chat_id = metadata.get("chat_id")

# 2. If yes, look up chat to get user_id
if task_chat_id:
    chat_node = repository.get_chat(task_chat_id)
    task_user_id = chat_node.properties.get("user_id")
    
# 3. Create bot with correct user_id
await bot.start_chat(
    session_id=self.session_id,
    user_id=task_user_id,  # Uses chat's user or defaults to "agent"
    chat_id=chat_id,
    ...
)

# 4. Create forwarder with task_id
websocket_forwarder = await create_websocket_forwarder(
    connection_manager, task_user_id, chat_id, task_id
)
```

## User Experience

### Scenario 1: User Requests Task in Their Chat

**User in chat 123:**
```
User: Can you research this topic for me?
Bot: I'll create a task for that.
```

**Backend:**
```python
# Bot creates task with chat_id
await task_queue.add_task(
    instruction="Research topic X",
    chat_id="chat-123"
)
```

**User sees in same chat:**
```
[Few moments later]
🤖 Task abc: Starting execution...
🤖 [Tool Use] search(query="topic X")
🤖 [Tool Result] Found 10 results...
🤖 [Thought] I'll summarize the key findings...
🤖 Task response: Here's what I found...
✅ Task abc completed successfully
```

### Scenario 2: Agent Self-Initiated Task

**Backend:**
```python
# Scheduled maintenance task
await task_queue.add_task(
    instruction="Validate knowledge graph integrity",
    # No chat_id specified
)
```

**Result:**
- Task creates its own chat
- Runs as user="agent"
- Only visible to agent user in UI
- Original behavior preserved

### Scenario 3: Multiple Users Watching Same Chat

**Setup:**
- User A creates chat
- User A adds task to that chat
- User B opens same chat (if permissions allow)

**Result:**
- Both users see task updates in real-time
- WebSocket messages sent to anyone viewing chat_id
- No restriction on viewers

## UI Integration

### Frontend Changes Needed

The frontend should display task messages with indicators:

```javascript
// In message rendering
if (message.data.task_id) {
  // This is a task message
  return <TaskMessage 
    taskId={message.data.task_id}
    content={message.data.text || message.data.message}
    type={message.type}  // tool_use, thought, message, etc.
  />
} else {
  // Regular message
  return <ChatMessage content={message.data.text} />
}
```

### Suggested UI Indicators

- **Status messages:** `🤖 Task abc: Starting...`
- **Tool calls:** `🔧 Using tool: search(...)`
- **Thoughts:** `💭 Thinking...`
- **Messages:** `🤖 Task response: ...`
- **Completion:** `✅ Task completed`
- **Errors:** `❌ Task failed: ...`

## Benefits

### For Users
- ✅ Task results appear in relevant chat context
- ✅ No need to switch between chats
- ✅ Task execution visible in real-time
- ✅ Clear attribution (task vs user messages)

### For Agents
- ✅ Can execute tasks in user conversations
- ✅ Maintain context and continuity
- ✅ User identity preserved
- ✅ Natural conversation flow

### For System
- ✅ Flexible task routing
- ✅ Backward compatible (chat_id is optional)
- ✅ Isolated execution (always new bot instance)
- ✅ Clean separation (task_id in all messages)

## Concurrent Execution

### Behavior

Tasks can execute while users are actively chatting:
- **User sends message** → Normal bot processes it
- **Task executes** → Separate bot instance processes it
- **Messages interleave** in chat history

### Example Timeline

```
Time  User Action           Task Action
────────────────────────────────────────────────────
0:00  "Hello"               
0:01  Bot: "Hi!"            
0:02  "What about topic X?" 
0:03  Bot: "I'll research"  
0:04                        [Task starts]
0:05  "Thanks!"             
0:06  Bot: "You're welcome" 
0:07                        🤖 Task: Using search...
0:08  "Anything else?"      
0:09  Bot: "What do you     
      need?"                
0:10                        🤖 Task result: Found...
0:11                        ✅ Task completed
```

### Safety

- ✅ Separate bot instances (no state corruption)
- ✅ Different message attribution (task vs user)
- ✅ Transaction isolation in knowledge graph
- ⚠️  Messages may interleave (could be confusing)

### Future Enhancements

Potential improvements for concurrent execution:
1. **Task Queueing:** Wait for active chat to be idle
2. **Visual Grouping:** Collapse task messages into expandable section
3. **Notifications:** Alert user when task completes
4. **Locking:** Prevent user messages during task execution

For now, messages interleave. Users can still use the chat normally while tasks execute.

## Testing

### Test 1: Task in User Chat

```bash
# 1. Start server with agent loop
SPARKY_ENABLE_AGENT_LOOP=true sparky chat start

# 2. In UI: Create a regular chat, get the chat_id from URL
# URL: http://localhost:3000/chat/<chat_id>

# 3. Add task to that chat
sparky agent tasks add "What is 2+2?" --chat <chat_id>

# 4. In UI: Watch task execute in that chat
# Should see: 🤖 indicators on task messages
```

### Test 2: Task Without Chat (Original Behavior)

```bash
# Add task without chat_id
sparky agent tasks add "Background research"

# Log in as user "agent" in UI
# Should see task in agent's own chat (original behavior)
```

### Test 3: Scheduled Task

```bash
# Scheduled tasks don't specify chat_id
# They execute in their own persistent chats
# Original behavior preserved
```

## Migration

### Backward Compatibility

- ✅ **No breaking changes**
- ✅ Existing tasks work as before
- ✅ chat_id is optional
- ✅ Default behavior unchanged

### For Existing Code

```python
# Old way (still works)
await task_queue.add_task(instruction="Task here")

# New way (with chat)
await task_queue.add_task(
    instruction="Task here",
    chat_id="chat-uuid"
)
```

### For CLI Users

```bash
# Old way (still works)
sparky agent tasks add "Task here"

# New way (with chat)
sparky agent tasks add "Task here" --chat <chat_id>
```

## Files Modified

### Core Implementation
1. `agent/src/sparky/task_queue.py`
   - Added `chat_id` parameter to `add_task()`
   - Stores chat_id in metadata

2. `agent/src/servers/task/task_server.py`
   - Looks up chat to get user_id
   - Creates bot with chat's user_id
   - Routes WebSocket to chat's connections

3. `agent/src/utils/websocket_forwarder.py`
   - Added `task_id` parameter
   - Includes task_id in all message payloads

### Message Models
4. `agent/src/models/websocket.py`
   - Added optional `task_id` to all message payloads
   - Updated `to_dict()` to include task_id

### CLI
5. `agent/src/cli/agent.py`
   - Added `--chat` option to `tasks add` command
   - Shows chat_id in output when specified

## Configuration

No configuration needed! Feature is automatic:
- CLI: Use `--chat` option when adding tasks
- Programmatic: Pass `chat_id` parameter
- UI: Task messages include `task_id` for styling

## Security Considerations

### Permissions

Currently no permission checks:
- Any task can execute in any chat
- Task inherits chat's user_id

### Future Enhancements

Consider adding:
1. **Permission checks:** Verify task creator can access chat
2. **User validation:** Ensure chat owner approves task execution
3. **Rate limiting:** Prevent task spam in user chats
4. **Audit logging:** Track which tasks executed in which chats

For now, tasks are trusted system operations.

## Summary

**What changed:**
- ✅ Tasks can specify chat_id
- ✅ Tasks inherit chat's user_id
- ✅ Task messages include task_id
- ✅ UI can display task indicators

**What stayed the same:**
- ✅ Tasks without chat_id work as before
- ✅ Scheduled tasks unchanged
- ✅ Task queue API compatible
- ✅ WebSocket protocol extended (not changed)

**Ready to use:**
```bash
sparky agent tasks add "Your task" --chat <chat_id>
```

Task will execute in that chat with real-time updates! 🎉

