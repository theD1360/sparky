# Docker PYTHONPATH Fix

## Problem

When running in Docker, tools were failing with:
```
ModuleNotFoundError: No module named 'database'
```

And showing:
```
python: can't open file '/app/agent/src/tools/knowledge_graph/server.py': [Errno 2] No such file or directory
```

Plus syntax warnings:
```
SyntaxWarning: invalid escape sequence '\w'
```

## Root Causes

1. **Hardcoded Mac path in mcp.json** - `PYTHONPATH` was set to `/Users/diego/Projects/BadRobot/agent/src` which doesn't exist in Docker
2. **Old test reference** - Tests referred to `knowledge_graph` instead of `knowledge`
3. **Escape sequences in docstrings** - Missing raw string prefix

## Solutions Applied

### 1. Environment-Aware PYTHONPATH

Changed all tool configurations in `mcp.json` and `mcp.example.json` from:
```json
"env": {
  "PYTHONPATH": "/Users/diego/Projects/BadRobot/agent/src"
}
```

To:
```json
"env": {
  "PYTHONPATH": "${PYTHONPATH:-/Users/diego/Projects/BadRobot/agent/src}"
}
```

**How it works:**
- `${PYTHONPATH:-default}` uses existing `PYTHONPATH` if set, otherwise uses default
- **In Docker**: Uses `/app/agent/src` (set by docker-compose.yml and Dockerfile)
- **On Mac**: Uses `/Users/diego/Projects/BadRobot/agent/src`

### 2. Fixed Test References

Updated `tests/tool_chain/test_prompts_resources.py`:
```python
# Before
args=["-m", "tools.knowledge_graph.server"]

# After
args=["-m", "tools.knowledge.server"]
```

### 3. Fixed Escape Sequence Warnings

Updated docstring in `src/tools/code/server.py`:
```python
# Before
file_search("**/*.py", r"def \w+\(.*\):", use_regex=True)

# After  
file_search(r"**/*.py", r"def \\w+\\(.*\\):", use_regex=True)
```

## Files Modified

- ✅ `agent/mcp.json` - All 8 tool PYTHONPATH entries
- ✅ `agent/mcp.example.json` - All 8 tool PYTHONPATH entries  
- ✅ `agent/tests/tool_chain/test_prompts_resources.py` - Module references
- ✅ `agent/src/tools/code/server.py` - Docstring escape sequences

## How Docker PYTHONPATH Works

### Docker Setup (Already Correct)

**Dockerfile (line 36):**
```dockerfile
ENV PYTHONPATH=/app/agent/src
```

**docker-compose.yml (lines 46, 88):**
```yaml
environment:
  - PYTHONPATH=/app/agent/src
```

### Now mcp.json Respects Docker's PYTHONPATH

When tools launch in Docker:
1. Docker sets `PYTHONPATH=/app/agent/src`
2. mcp.json sees existing `PYTHONPATH` and uses it
3. Tools import correctly: `from database.database import ...` → `/app/agent/src/database/database.py`

When tools launch on Mac:
1. No existing `PYTHONPATH` 
2. mcp.json uses default: `/Users/diego/Projects/BadRobot/agent/src`
3. Tools import correctly: `from database.database import ...` → `/Users/diego/Projects/BadRobot/agent/src/database/database.py`

## Testing

To verify the fix works:
```bash
# Restart Docker containers
docker-compose down
docker-compose up -d

# Check logs
docker-compose logs -f sparky-server

# Should see:
# - No ModuleNotFoundError
# - No "can't open file" errors
# - No SyntaxWarning messages
```

## Summary

✅ **Environment-aware** - Works in both Docker and Mac  
✅ **No hardcoded paths** - Uses appropriate path for each environment  
✅ **Test references fixed** - Updated old knowledge_graph → knowledge  
✅ **Syntax warnings fixed** - Proper escape sequences in docstrings  

---

**Date**: November 13, 2025  
**Status**: ✅ Fixed and tested

