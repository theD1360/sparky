# Standalone Task Server Removal

## Overview

The standalone task server has been retired in favor of the integrated approach where the agent loop runs within the chat server process. This provides better resource utilization, simpler deployment, and enables features like real-time WebSocket updates.

## Changes Made

### 1. CLI Commands Removed

**Removed from `agent/src/cli/agent.py`:**
- ❌ `sparky agent start` - No longer needed
- ❌ `sparky agent stop` - No longer needed

**Updated:**
- ✅ `sparky agent status` - Now shows task queue stats and indicates agent runs in chat server

### 2. Imports Cleaned Up

**Files modified:**
- `agent/src/cli/agent.py`:
  - Removed imports: `atexit`, `signal`, `psutil`, `DaemonContext`, `PIDLockFile`
  - Removed imports: `initialize_agent_toolchain`, `TaskServer`
  - Removed unused `os` import

- `agent/src/cli/common.py`:
  - Removed import: `SPARKY_AGENT_PID_FILE`
  - Removed constant: `AGENT_PID_FILE`

- `agent/src/sparky/constants.py`:
  - Removed constant: `SPARKY_AGENT_PID_FILE`

### 3. Documentation Updated

**`agent/docs/core/cli.md`:**
- Removed documentation for `sparky agent start` and `sparky agent stop`
- Added section explaining integrated approach with environment variables
- Updated lifecycle section to show how to enable agent loop

**`agent/docs/tasks/task_server.md`:**
- Added section on running the agent loop
- Clarified that agent loop runs within chat server
- Added environment variable documentation

## New Approach

### How to Run the Agent Loop

Instead of running a separate process, enable the agent loop when starting the chat server:

```bash
export SPARKY_ENABLE_AGENT_LOOP=true
export SPARKY_AGENT_POLL_INTERVAL=10  # Optional, defaults to 10
sparky chat
```

### Benefits

1. **Simpler Deployment**
   - One process instead of two
   - No need to manage separate PID files
   - Shared connection manager for WebSocket updates

2. **Better Resource Utilization**
   - Single toolchain instance shared between chat and agent
   - Single database connection pool
   - Reduced memory footprint

3. **Real-Time WebSocket Updates**
   - Agent can send updates to connected users
   - Automatic reconnection detection
   - Seamless integration with UI

4. **Easier Development**
   - Single process to debug
   - Consistent logging
   - Shared configuration

## Migration Guide

### For Users Currently Running Standalone

**Old way:**
```bash
# Terminal 1: Start chat server
sparky chat

# Terminal 2: Start agent
sparky agent start
```

**New way:**
```bash
# Single terminal
export SPARKY_ENABLE_AGENT_LOOP=true
sparky chat
```

### For Docker Deployments

**Old `docker-compose.yml`:**
```yaml
services:
  sparky-server:
    command: sparky chat
  
  sparky-agent:  # Remove this service
    command: sparky agent start --daemon
```

**New `docker-compose.yml`:**
```yaml
services:
  sparky-server:
    command: sparky chat
    environment:
      - SPARKY_ENABLE_AGENT_LOOP=true
      - SPARKY_AGENT_POLL_INTERVAL=10
```

### CLI Commands Still Available

All task management commands remain unchanged:

```bash
# Task management
sparky agent tasks list
sparky agent tasks add "<instruction>"
sparky agent tasks get <task_id>
sparky agent tasks update <task_id> --status completed
sparky agent tasks delete <task_id>
sparky agent tasks clear --status completed

# Schedule management
sparky agent schedule list
sparky agent schedule show <name>
sparky agent schedule run <name>
sparky agent schedule add <name> <interval> <prompt>
sparky agent schedule enable <name>
sparky agent schedule disable <name>

# Statistics
sparky agent status
sparky agent stats
```

## Environment Variables

### Agent Loop Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SPARKY_ENABLE_AGENT_LOOP` | Enable agent loop in chat server | `false` |
| `SPARKY_AGENT_POLL_INTERVAL` | Seconds between task queue polls | `10` |

### WebSocket Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENT_MODEL` | LLM model for task execution | `gemini-2.0-flash` |

## Cleanup Checklist

- [x] Removed `sparky agent start` command
- [x] Removed `sparky agent stop` command  
- [x] Updated `sparky agent status` command
- [x] Cleaned up imports (atexit, signal, psutil, DaemonContext, PIDLockFile)
- [x] Removed `SPARKY_AGENT_PID_FILE` constant
- [x] Updated CLI documentation
- [x] Updated task server documentation
- [x] Removed Docker container for standalone agent

## Files Modified

### Code Changes
- `agent/src/cli/agent.py` - Removed start/stop commands, cleaned imports
- `agent/src/cli/common.py` - Removed unused imports
- `agent/src/sparky/constants.py` - Removed unused constant

### Documentation Changes
- `agent/docs/core/cli.md` - Updated lifecycle section
- `agent/docs/tasks/task_server.md` - Added running instructions

## Backward Compatibility

**Breaking Changes:**
- ❌ `sparky agent start` no longer exists
- ❌ `sparky agent stop` no longer exists
- ❌ Standalone agent Docker container no longer works

**Still Works:**
- ✅ All task management commands
- ✅ All schedule management commands
- ✅ Task queue functionality
- ✅ Scheduled tasks
- ✅ Agent statistics

## Testing

To verify the changes work:

```bash
# 1. Enable agent loop
export SPARKY_ENABLE_AGENT_LOOP=true

# 2. Start chat server
sparky chat

# 3. In another terminal, add a task
sparky agent tasks add "Test task"

# 4. Check status
sparky agent status

# 5. View task queue
sparky agent tasks list
```

Expected: Task should be executed by the integrated agent loop.

## Future Considerations

With the standalone server removed, future enhancements can focus on:
1. Enhanced WebSocket features (already implemented)
2. Better resource sharing between chat and agent
3. Unified logging and monitoring
4. Simplified deployment configurations

## References

- WebSocket Task Updates: `WEBSOCKET_TASK_UPDATES.md`
- WebSocket Reconnection: `WEBSOCKET_RECONNECTION.md`
- WebSocket Fixes: `WEBSOCKET_FIXES.md`

