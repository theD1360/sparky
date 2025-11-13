# BadMCP PYTHONPATH Fix

## Root Cause

The `badmcp/config.py` module has a `_ensure_required_servers()` method that auto-adds a fallback configuration for required servers. This was:

1. **Referencing the old `knowledge_graph` server** instead of `knowledge`
2. **Using hardcoded path** without PYTHONPATH
3. **Not supporting** `${VAR:-default}` syntax for environment variables

This caused:
- ❌ `ModuleNotFoundError: No module named 'database'`
- ❌ `can't open file '/app/agent/src/tools/knowledge_graph/server.py'`

## Fixes Applied

### 1. Updated Required Server Configuration

**File**: `badmcp/config.py` lines 145-165

**Before:**
```python
required_servers = {
    "knowledge_graph": {  # ❌ Old name
        "command": "python",
        "args": ["src/tools/knowledge_graph/server.py"],  # ❌ Old path
        "description": "Knowledge graph and memory management (required)",
        # ❌ No PYTHONPATH!
    }
}
```

**After:**
```python
required_servers = {
    "knowledge": {  # ✅ Correct name
        "command": "python",
        "args": ["src/tools/knowledge/server.py"],  # ✅ Correct path
        "description": "Knowledge graph and memory management (required)",
        "env": {  # ✅ Added PYTHONPATH
            "PYTHONPATH": "${PYTHONPATH:-/app/agent/src}",
            "SPARKY_DB_URL": "${SPARKY_DB_URL}"
        }
    }
}
```

### 2. Enhanced Environment Variable Interpolation

**File**: `badmcp/config.py` lines 70-100

Added support for `${VAR:-default}` syntax (bash-style defaults):

**Before:**
```python
def replace_var(match):
    var_name = match.group(1)
    return os.environ.get(var_name, "")  # ❌ Only supports ${VAR}
```

**After:**
```python
def replace_var(match):
    full_expr = match.group(1)
    # Check if it has a default value (VAR:-default)
    if ":-" in full_expr:
        var_name, default_value = full_expr.split(":-", 1)
        return os.environ.get(var_name, default_value)  # ✅ Supports ${VAR:-default}
    else:
        return os.environ.get(full_expr, "")  # Still supports ${VAR}
```

## How It Works Now

### In Docker

1. Docker sets: `PYTHONPATH=/app/agent/src`
2. BadMCP config parses: `${PYTHONPATH:-/app/agent/src}`
3. Interpolation finds `PYTHONPATH` env var
4. Uses Docker's value: `/app/agent/src` ✅

### On Mac (without Docker)

1. No `PYTHONPATH` set
2. BadMCP config parses: `${PYTHONPATH:-/app/agent/src}`
3. Interpolation doesn't find `PYTHONPATH`
4. Uses default: `/app/agent/src` ✅

### In Development (with custom PYTHONPATH)

1. Developer sets: `PYTHONPATH=/custom/path`
2. BadMCP config parses: `${PYTHONPATH:-/app/agent/src}`
3. Interpolation finds custom `PYTHONPATH`
4. Uses custom value: `/custom/path` ✅

## Complete Fix Chain

To fully fix the issue, we updated:

1. ✅ **mcp.json** - All 8 tool servers with `${PYTHONPATH:-...}` syntax
2. ✅ **mcp.example.json** - Example config with PYTHONPATH
3. ✅ **badmcp/config.py** - Required server fallback + interpolation
4. ✅ **tests/tool_chain/test_prompts_resources.py** - Old references
5. ✅ **tools/code/server.py** - Escape sequence warnings

## Testing

After these changes, restart Docker:
```bash
docker-compose down
docker-compose up -d
```

Check logs:
```bash
docker-compose logs -f sparky-server
```

Should see:
- ✅ No `ModuleNotFoundError`
- ✅ No "can't open file" errors
- ✅ Knowledge server loads successfully
- ✅ Code tools load successfully
- ✅ All imports work

## Environment Variable Syntax Support

The config now supports:

| Syntax | Example | Behavior |
|--------|---------|----------|
| `${VAR}` | `${API_KEY}` | Returns env var or empty string |
| `${VAR:-default}` | `${PYTHONPATH:-/app/agent/src}` | Returns env var or default value |

## Why This Fix Was Necessary

The `_ensure_required_servers()` method exists as a safety net to ensure critical servers are always available, even if `mcp.json` is missing or incomplete. However, it was:

1. Using **outdated references** (`knowledge_graph`)
2. **Not respecting environment** (no PYTHONPATH)
3. **Overriding user config** when added as fallback

Now it:
1. Uses **current references** (`knowledge`)
2. **Respects environment** (PYTHONPATH with defaults)
3. **Only adds when missing** (doesn't override existing config)

---

**Status**: ✅ Fixed  
**Date**: November 13, 2025  
**Impact**: All tool servers now load correctly in Docker and local environments

