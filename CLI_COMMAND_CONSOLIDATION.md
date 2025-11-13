# CLI Command Consolidation

## Overview

Consolidated `sparky server` command to `sparky chat` to reflect the integrated architecture where the chat server and agent loop run in the same process.

## Command Changes

### Before (Old Commands)
```bash
# Server management
sparky server start
sparky server stop
sparky server restart

# Agent management (standalone)
sparky agent start
sparky agent stop
```

### After (New Commands)
```bash
# Chat server (includes agent loop if enabled)
sparky chat start
sparky chat stop
sparky chat restart

# Agent is now enabled via environment variable
SPARKY_ENABLE_AGENT_LOOP=true sparky chat start
```

## Migration Guide

### Simple Migration

**Old:**
```bash
# Terminal 1
sparky server start

# Terminal 2
sparky agent start
```

**New:**
```bash
# Single terminal
SPARKY_ENABLE_AGENT_LOOP=true sparky chat start
```

### With Options

**Old:**
```bash
sparky server start --host 0.0.0.0 --port 8080
```

**New:**
```bash
sparky chat start --host 0.0.0.0 --port 8080
```

### Daemon Mode

**Old:**
```bash
sparky server start --daemon
```

**New:**
```bash
sparky chat start --daemon
```

## Files Changed

### Code Changes
- **Created:** `agent/src/cli/chat.py` - New chat server CLI
- **Deleted:** `agent/src/cli/server.py` - Old server CLI
- **Updated:** `agent/src/cli/__init__.py` - Import chat instead of server

### Documentation Changes
- **Updated:** `agent/docs/core/cli.md` - Changed from "Server Commands" to "Chat Commands"
- **Updated:** `agent/README.md` - Updated quick start commands
- **Updated:** `README.md` - Updated Docker services list and development setup

## Command Reference

### Chat Server Commands

All commands now under `sparky chat`:

```bash
# Start chat server (optionally with agent loop)
sparky chat start [OPTIONS]

# Options:
#   --host TEXT      Host to bind (default: 127.0.0.1)
#   --port INTEGER   Port to bind (default: 8000)
#   --daemon         Run in background
#   --pidfile TEXT   Path to PID file (default: sparky-chat.pid)

# Stop chat server
sparky chat stop [OPTIONS]

# Restart chat server
sparky chat restart [OPTIONS]
```

### Environment Variables

```bash
# Enable agent loop for background task processing
export SPARKY_ENABLE_AGENT_LOOP=true

# Configure polling interval (seconds)
export SPARKY_AGENT_POLL_INTERVAL=10
```

### Task Management Commands

All task management commands remain unchanged under `sparky agent tasks`:

```bash
sparky agent tasks list
sparky agent tasks add "<instruction>"
sparky agent tasks get <task_id>
sparky agent tasks update <task_id> --status completed
sparky agent tasks delete <task_id>
sparky agent tasks clear --status completed
```

### Schedule Management Commands

All schedule commands remain unchanged under `sparky agent schedule`:

```bash
sparky agent schedule list
sparky agent schedule run <name>
sparky agent schedule add <name> <interval> <prompt>
sparky agent schedule enable <name>
sparky agent schedule disable <name>
```

## Rationale

### Why Consolidate?

1. **Simpler Mental Model**
   - One command to start everything: `sparky chat`
   - No confusion about which process does what
   - Clear separation: `chat` runs services, `agent` manages tasks

2. **Consistent with Usage**
   - You've been saying "sparky chat" in conversation
   - More intuitive: "start the chat server"
   - Agent is a feature, not a separate service

3. **Clearer Hierarchy**
   ```
   sparky
   ├── chat           # Server lifecycle (start/stop/restart)
   ├── client         # CLI client
   ├── agent          # Task/schedule management
   │   ├── tasks      # Task CRUD
   │   ├── schedule   # Schedule management
   │   └── status     # Statistics
   └── db             # Database operations
   ```

4. **Future-Proof**
   - Agent loop is now a feature toggle, not a process
   - Easy to add more features to chat server
   - Cleaner for potential API server additions later

## Docker Impact

### docker-compose.yml

No changes needed! The container name and command remain the same:

```yaml
services:
  sparky-server:
    container_name: sparky-server
    command: uvicorn servers.chat:app --host 0.0.0.0 --port 8000
    environment:
      - SPARKY_ENABLE_AGENT_LOOP=true  # Enable agent loop
```

### Dockerfile

No changes needed! The CLI is installed and works with new commands automatically.

## Testing

### Test New Commands

```bash
# Test chat start
sparky chat start
# Should show: "Starting Sparky Chat Server on ws://127.0.0.1:8000/ws/chat"

# Test with agent enabled
SPARKY_ENABLE_AGENT_LOOP=true sparky chat start
# Should show: "✅ Agent loop enabled - background tasks will be processed"

# Test chat stop (in another terminal)
sparky chat stop
# Should show: "✓ Server process <pid> stopped gracefully"
```

### Verify Old Commands Don't Work

```bash
# These should fail with helpful error
sparky server start
# Expected: "Error: No such command 'server'"

sparky agent start
# Expected: Shows status message directing to use chat server
```

## Backward Compatibility

### Breaking Changes
- ❌ `sparky server start/stop/restart` commands removed
- ❌ `sparky agent start/stop` commands removed

### Still Works
- ✅ All task management commands
- ✅ All schedule management commands
- ✅ All database commands
- ✅ Client commands
- ✅ Docker Compose setup
- ✅ Environment variables

### Aliases/Shortcuts

Users can add shell aliases for convenience:

```bash
# Add to ~/.bashrc or ~/.zshrc
alias sparky-start="SPARKY_ENABLE_AGENT_LOOP=true sparky chat start"
alias sparky-stop="sparky chat stop"
```

## Summary

**One command to rule them all:**
```bash
SPARKY_ENABLE_AGENT_LOOP=true sparky chat start
```

This single command:
- ✅ Starts the chat server
- ✅ Enables the agent loop
- ✅ Processes background tasks
- ✅ Handles scheduled tasks
- ✅ Provides WebSocket API
- ✅ Supports real-time updates

**Simpler. Cleaner. More intuitive.** 🎉

