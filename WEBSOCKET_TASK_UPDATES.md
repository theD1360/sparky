# WebSocket Task Agent Updates

This document explains how to use the real-time WebSocket updates feature for the task agent.

## Overview

The task agent can now send real-time updates via WebSocket when you're logged in as the agent user. This allows you to see:
- Tool calls as they happen
- Agent thoughts and reasoning
- Task status updates
- Errors and completions
- All agent messages

## Setup

### Method 1: Run Agent Loop Within Chat Server (Recommended)

This is the simplest method - both services run in the same process and share the ConnectionManager.

1. **Set environment variables:**
   ```bash
   export SPARKY_ENABLE_AGENT_LOOP=true
   export SPARKY_AGENT_POLL_INTERVAL=10  # Optional, defaults to 10 seconds
   ```

2. **Start the chat server:**
   ```bash
   sparky chat
   ```

   The agent loop will automatically start in the background when the chat server starts.

3. **In the UI:**
   - Get the agent's session ID (check the logs when the agent loop starts, or use localStorage)
   - Log in as user_id: `agent`
   - You should see a "Task Monitor" or similar chat

4. **Add a task via CLI (in a separate terminal):**
   ```bash
   sparky agent tasks add "What is the current date and time?"
   ```

5. **Watch the UI:**
   - You should see real-time updates as the task executes
   - Tool calls, thoughts, and responses will appear in real-time

### Method 2: Run Servers Separately (Advanced)

If you need to run the agent loop separately (e.g., as a daemon), you can still use this feature:

1. **Start the chat server:**
   ```bash
   sparky chat
   ```

2. **Start the agent loop separately:**
   ```bash
   # Note: This won't have WebSocket support unless you implement IPC
   sparky agent start
   ```

   **Note:** With separate processes, WebSocket updates won't work by default. You would need to implement inter-process communication (e.g., Redis pub/sub) to bridge the two processes.

## How It Works

### Architecture

1. **ConnectionManager Extension:**
   - Added `session_to_user` mapping to track which user_id is associated with each WebSocket session
   - Added `get_active_connection_by_user(user_id)` method to find active connections by user

2. **WebSocketForwarder:**
   - New utility class that wraps WebSocket message sending
   - Converts bot events to WebSocket messages
   - Handles all message types: tool_use, tool_result, thought, message, status, error

3. **AgentLoop Integration:**
   - Accepts optional `connection_manager` parameter
   - Before executing each task, checks if the agent user has an active WebSocket connection
   - If found, subscribes to bot events and forwards them to WebSocket
   - Events forwarded: TOOL_USE, TOOL_RESULT, THOUGHT, MESSAGE_SENT, MESSAGE_RECEIVED

4. **Event Flow:**
   ```
   Task Execution
   └─> Bot Event (e.g., TOOL_USE)
       └─> Event Handler
           └─> WebSocketForwarder
               └─> WebSocket Message
                   └─> UI Update
   ```

## Testing

### Basic Test

1. Start the chat server with agent loop enabled:
   ```bash
   export SPARKY_ENABLE_AGENT_LOOP=true
   sparky chat
   ```

2. Open the UI and log in as user `agent`

3. Add a simple task:
   ```bash
   sparky agent tasks add "List all files in the current directory"
   ```

4. Watch the UI - you should see:
   - Status: "Task starting..."
   - Tool calls (e.g., list_directory)
   - Tool results
   - Agent responses
   - Status: "Task completed"

### Advanced Test

Test with a more complex task that uses multiple tools:

```bash
sparky agent tasks add "Research the latest news about AI and create a summary document"
```

You should see:
- Multiple tool calls (search, file creation, etc.)
- Agent thinking/reasoning
- Progress updates
- Final completion status

## Troubleshooting

### No updates appearing in UI

1. **Check environment variables:**
   ```bash
   echo $SPARKY_ENABLE_AGENT_LOOP
   ```
   Should be "true"

2. **Check chat server logs:**
   Look for: "Agent loop started in background"
   Look for: "WebSocket forwarder created for task..."

3. **Check user_id:**
   Make sure you're logged in as user_id: `agent` (not "Agent" or any other variation)

4. **Check WebSocket connection:**
   Open browser console and look for WebSocket connection logs
   Should see: "WebSocket connected"

### Updates delayed or missing

1. **Check poll interval:**
   - Default is 10 seconds between task checks
   - Adjust with `SPARKY_AGENT_POLL_INTERVAL` environment variable

2. **Check task queue:**
   ```bash
   sparky agent tasks list
   ```
   Make sure tasks are in "pending" or "in_progress" state

### Errors in logs

1. **"No active connection for user agent":**
   - Make sure you're logged into the UI as user `agent`
   - Check that WebSocket is connected (browser console)

2. **"Error sending WebSocket message":**
   - WebSocket connection may have dropped
   - Try refreshing the browser
   - Check network connectivity

## Configuration

### Environment Variables

- `SPARKY_ENABLE_AGENT_LOOP`: Set to "true" to enable agent loop in chat server (default: false)
- `SPARKY_AGENT_POLL_INTERVAL`: Seconds between task queue polls (default: 10)
- `AGENT_MODEL`: LLM model to use for task execution (default: "gemini-2.0-flash")

### Files Modified

- `agent/src/servers/chat/chat_server.py`: Extended ConnectionManager, added agent loop startup
- `agent/src/servers/task/task_server.py`: Added WebSocket forwarding support
- `agent/src/utils/websocket_forwarder.py`: New - WebSocket message forwarding utility

## Future Enhancements

Potential improvements:
1. Add inter-process communication for separate server support
2. Add filtering options (e.g., hide tool calls, show only errors)
3. Add task progress indicators
4. Support multiple simultaneous agent users
5. Add WebSocket reconnection with event replay

