# Using Prompts and Resources in Sparky

This guide shows how to use the newly implemented prompts and resources functionality in your bot.

## Overview

The bot now supports:
- **Prompts**: Reusable message templates for complex reasoning tasks
- **Resources**: Direct read-only access to common data

## Using Prompts

### Basic Usage

```python
# Get a prompt template with arguments
prompt_text = await bot.get_prompt("discover_concept", {
    "concept_name": "Python"
})

# The prompt_text now contains guidance for exploring the concept
print(prompt_text)
```

### Available Prompts

1. **discover_concept** - Explore knowledge about a concept
   ```python
   prompt = await bot.get_prompt("discover_concept", {
       "concept_name": "FastMCP"
   })
   ```

2. **solve_problem** - Structured problem-solving
   ```python
   prompt = await bot.get_prompt("solve_problem", {
       "problem_description": "Optimize database queries"
   })
   ```

3. **execute_workflow** - Run stored workflows
   ```python
   prompt = await bot.get_prompt("execute_workflow", {
       "workflow_name": "deploy_feature",
       "context": "staging environment"
   })
   ```

4. **organize_memories** - Memory organization
   ```python
   prompt = await bot.get_prompt("organize_memories", {
       "topic": "project_status"
   })
   ```

5. **analyze_knowledge_structure** - Graph analysis
   ```python
   prompt = await bot.get_prompt("analyze_knowledge_structure", {})
   ```

### Listing Available Prompts

```python
# List all prompts from all MCP servers
prompts = await bot.list_prompts()
for client, prompt in prompts:
    print(f"Prompt: {prompt.name} from {client.name}")
    print(f"Description: {prompt.description}")
```

## Using Resources

### Basic Usage

```python
# Read a resource by URI
stats = await bot.read_resource("knowledge://stats")

# Parse the JSON result
import json
stats_data = json.loads(stats)
print(f"Total nodes: {stats_data['total_nodes']}")
```

### Available Resources

1. **knowledge://stats** - Graph statistics
   ```python
   stats = await bot.read_resource("knowledge://stats")
   # Returns: {"total_nodes": 1234, "total_edges": 5678, ...}
   ```

2. **knowledge://memories** - All memories list
   ```python
   memories = await bot.read_resource("knowledge://memories")
   # Returns: {"memories": [...], "count": 45}
   ```

3. **knowledge://memory/{key}** - Specific memory
   ```python
   memory = await bot.read_resource("knowledge://memory/user_preferences")
   # Returns: {"key": "user_preferences", "content": "..."}
   ```

4. **knowledge://workflows** - Workflows list
   ```python
   workflows = await bot.read_resource("knowledge://workflows")
   # Returns: {"workflows": [...], "count": 12}
   ```

5. **knowledge://workflow/{name}** - Workflow definition
   ```python
   workflow = await bot.read_resource("knowledge://workflow/deploy_feature")
   # Returns: {"name": "...", "version": 3, "steps": [...]}
   ```

6. **knowledge://thinking-patterns** - Thinking patterns
   ```python
   patterns = await bot.read_resource("knowledge://thinking-patterns")
   # Returns: {"patterns": [...], "count": 8}
   ```

7. **knowledge://node/{id}/context** - Node context
   ```python
   context = await bot.read_resource("knowledge://node/concept:python/context")
   # Returns: {"central_node": {...}, "neighbors": [...], "edges": [...]}
   ```

8. **knowledge://tool-usage/recent** - Recent tool usage
   ```python
   usage = await bot.read_resource("knowledge://tool-usage/recent")
   # Returns: {"recent_calls": [...], "count": 20}
   ```

### Listing Available Resources

```python
# List all resources from all MCP servers
resources = await bot.list_resources()
for client, resource in resources:
    print(f"Resource: {resource.uri} from {client.name}")
    print(f"Description: {resource.description}")
```

## Complete Examples

### Example 1: Using a Prompt for Guidance

```python
async def explore_concept(bot, concept_name):
    """Use the discover_concept prompt to explore a topic."""
    
    # Get the prompt guidance
    prompt = await bot.get_prompt("discover_concept", {
        "concept_name": concept_name
    })
    
    print("Guidance for exploring concept:")
    print(prompt)
    
    # Now follow the prompt's instructions...
    # (This would be done by the AI or manually)
```

### Example 2: Quick Resource Check

```python
async def check_graph_health(bot):
    """Quick health check using resources."""
    
    # Get stats without calling any tools
    stats_json = await bot.read_resource("knowledge://stats")
    stats = json.loads(stats_json)
    
    print(f"Graph Health:")
    print(f"  Nodes: {stats['total_nodes']}")
    print(f"  Edges: {stats['total_edges']}")
    print(f"  Node Types: {stats['node_types']}")
    
    return stats
```

### Example 3: Combining Prompts and Resources

```python
async def solve_with_context(bot, problem):
    """Solve a problem using both prompts and resources."""
    
    # First, check what thinking patterns are available
    patterns_json = await bot.read_resource("knowledge://thinking-patterns")
    patterns = json.loads(patterns_json)
    
    print(f"Found {patterns['count']} thinking patterns")
    
    # Get the problem-solving prompt
    prompt = await bot.get_prompt("solve_problem", {
        "problem_description": problem
    })
    
    print("Problem-solving guidance:")
    print(prompt)
    
    # The AI can now follow the prompt using available patterns
```

### Example 4: Memory Organization

```python
async def organize_project_memories(bot):
    """Organize memories related to a project."""
    
    # Get all current memories
    memories_json = await bot.read_resource("knowledge://memories")
    memories = json.loads(memories_json)
    
    print(f"Current memories: {memories['count']}")
    
    # Get organization guidance
    prompt = await bot.get_prompt("organize_memories", {
        "topic": "project"
    })
    
    print("Organization guidance:")
    print(prompt)
    
    # Follow the prompt to organize memories
```

## Integration with ToolChain

If you're working directly with the ToolChain (not through Bot), you can use:

```python
# Access prompts
prompt = await toolchain.get_prompt("discover_concept", {"concept_name": "AI"})

# Access resources
stats = await toolchain.read_resource("knowledge://stats")

# List all prompts
prompts = await toolchain.list_all_prompts()

# List all resources
resources = await toolchain.list_all_resources()
```

## Integration with ToolClient

For direct server access:

```python
# With a specific tool client
client = ToolClient(mcp_config)

# List prompts from this server
prompts = await client.list_prompts()

# Get a specific prompt
prompt = await client.get_prompt("discover_concept", {"concept_name": "AI"})

# List resources from this server
resources = await client.list_resources()

# Read a resource
stats = await client.read_resource("knowledge://stats")
```

## Error Handling

### Prompt Not Found

```python
try:
    prompt = await bot.get_prompt("nonexistent_prompt", {})
except Exception as e:
    print(f"Prompt not found: {e}")
```

### Resource Not Found

```python
try:
    data = await bot.read_resource("knowledge://nonexistent")
except Exception as e:
    print(f"Resource not found: {e}")
```

### Resource Returns Error

```python
stats_json = await bot.read_resource("knowledge://stats")
stats = json.loads(stats_json)

if "error" in stats:
    print(f"Resource error: {stats['error']}")
else:
    # Process normal data
    print(f"Nodes: {stats['total_nodes']}")
```

## Performance Considerations

### When to Use Resources vs Tools

**Use Resources:**
- Quick status checks (e.g., graph stats)
- Frequent reads of the same data
- When you need instant access
- Read-only operations

**Use Tools:**
- When you need to modify data
- Complex queries with filters
- Operations that require computation
- When resources don't provide what you need

### Example: Efficient Workflow

```python
async def efficient_check(bot):
    # Fast: Use resource for quick check
    stats = json.loads(await bot.read_resource("knowledge://stats"))
    
    if stats["total_nodes"] > 1000:
        # Only call tool if needed for detailed analysis
        result = await bot.toolchain.call("analyze_graph", {
            "analysis_type": "summary"
        })
```

## Best Practices

1. **Cache prompt text** if you'll use it multiple times
   ```python
   # Cache the prompt
   self._cached_prompt = await bot.get_prompt("discover_concept", args)
   ```

2. **Parse resource JSON once**
   ```python
   # Parse once, use many times
   stats = json.loads(await bot.read_resource("knowledge://stats"))
   node_count = stats["total_nodes"]
   edge_count = stats["total_edges"]
   ```

3. **Handle errors gracefully**
   ```python
   try:
       data = await bot.read_resource(uri)
       parsed = json.loads(data)
       if "error" in parsed:
           # Handle server-side error
           return None
   except Exception as e:
       # Handle client-side error
       logger.error(f"Failed to read resource: {e}")
       return None
   ```

4. **Use prompts as templates**
   - Don't just read prompts - follow their guidance
   - Prompts encode best practices from successful patterns
   - Use them to structure your approach to complex tasks

## Testing Your Implementation

See `/docs/prompts-resources-testing.md` for comprehensive testing procedures.

## Troubleshooting

### "Toolchain not initialized"
```python
# Make sure bot is started with toolchain
bot = Bot(toolchain=my_toolchain)
await bot.start_chat()
```

### Prompt not rendering arguments
```python
# Make sure arguments match the prompt signature
prompt = await bot.get_prompt("discover_concept", {
    "concept_name": "Python"  # Must match parameter name
})
```

### Resource URI not found
```python
# Check the exact URI format
# Correct: "knowledge://stats"
# Wrong: "knowledge:/stats" (missing slash)
```

## Summary

- **Prompts** provide structured guidance for complex tasks
- **Resources** give instant access to common data
- Both integrate seamlessly with the existing bot API
- Use them to reduce tool call overhead and improve consistency




