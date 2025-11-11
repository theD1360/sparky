# Resource Appending Example

This document demonstrates the updated behavior of the `ResourceFetchingMiddleware` which now appends resource content at the end of messages instead of replacing `@resource` references inline.

## Before (Old Behavior)

**Input message:**
```
Review @knowledge://stats to understand the current state
```

**Output (replaced inline):**
```
Review 
[Resource: knowledge://stats]
```json
{
  "total_nodes": 1234,
  "total_edges": 5678
}
```
 to understand the current state
```

**Problem:** The original message flow is disrupted, making it hard to read and understand the instruction.

## After (New Behavior)

**Input message:**
```
Review @knowledge://stats to understand the current state
```

**Output (appended at end):**
```
Review @knowledge://stats to understand the current state

---
[Resource: knowledge://stats]
```json
{
  "total_nodes": 1234,
  "total_edges": 5678
}
```
```

**Benefit:** The original message remains intact and readable, while resource data is cleanly appended at the end.

## Multiple Resources Example

**Input message:**
```
Compare @knowledge://stats and @knowledge://memories to assess progress
```

**Output:**
```
Compare @knowledge://stats and @knowledge://memories to assess progress

---
[Resource: knowledge://stats]
```json
{
  "total_nodes": 1234,
  "total_edges": 5678
}
```

---
[Resource: knowledge://memories]
```json
{
  "memories": [
    {"key": "user_prefs", "preview": "..."}
  ],
  "count": 45
}
```
```

## Why This Matters

### For Prompts
The updated prompts in the `prompts/` directory can now use natural language that flows well:

- ✅ "Review @knowledge://stats to understand your graph size"
- ✅ "Check @knowledge://tool-usage/recent for recent activity"
- ✅ "Compare @stats and @memories"

Instead of awkward constructions that anticipate replacement:

- ❌ "Review the stats below"
- ❌ "Check recent activity"

### For the Agent
The agent receives:
1. Clear, readable instructions with resource references in context
2. Full resource data appended at the end for reference
3. Better understanding of what data corresponds to which reference

### For Debugging
When reviewing logs, you can see:
1. The original prompt structure
2. What resources were referenced
3. The actual data that was provided

## Implementation Details

The middleware now:
1. Keeps the original message unchanged
2. Collects all fetched resources
3. Appends them at the end with `---` separators
4. Formats JSON content with proper syntax highlighting
5. Handles errors by appending error messages instead of data

See `src/sparky/middleware/message_middlewares.py` for implementation.

