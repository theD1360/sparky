# Testing FastMCP Prompts and Resources

This document provides testing instructions for the newly added prompts and resources in the knowledge server.

## Prerequisites

1. Ensure the knowledge server is running with database initialized
2. Have an MCP client connected to the knowledge server

## Testing Prompts

### 1. Test `discover_concept` Prompt

**Test Command (via MCP client):**
```python
prompt_result = await client.get_prompt("discover_concept", {
    "concept_name": "Python"
})
```

**Expected Result:**
- Should return a formatted string with instructions for exploring the concept
- Should include steps for using search_nodes and get_graph_context

### 2. Test `solve_problem` Prompt

**Test Command:**
```python
prompt_result = await client.get_prompt("solve_problem", {
    "problem_description": "How to optimize database queries"
})
```

**Expected Result:**
- Should return structured problem-solving steps
- Should reference apply_sequential_thinking and save_problem_solution

### 3. Test `execute_workflow` Prompt

**Test Command:**
```python
prompt_result = await client.get_prompt("execute_workflow", {
    "workflow_name": "deploy_feature",
    "context": "production environment"
})
```

**Expected Result:**
- Should return workflow execution instructions
- Should include steps for retrieving and executing workflow

### 4. Test `organize_memories` Prompt

**Test Command:**
```python
prompt_result = await client.get_prompt("organize_memories", {
    "topic": "project_status"
})
```

**Expected Result:**
- Should return memory organization instructions
- Should include search_memory and consolidation steps

### 5. Test `analyze_knowledge_structure` Prompt

**Test Command:**
```python
prompt_result = await client.get_prompt("analyze_knowledge_structure", {})
```

**Expected Result:**
- Should return graph analysis instructions
- Should reference various analyze_graph operations

## Testing Resources

### 1. Test Graph Statistics Resource

**Test Command:**
```python
stats = await client.read_resource("knowledge://stats")
```

**Expected Result:**
- JSON with total_nodes, total_edges, node_types, edge_types
- Should handle database not initialized error gracefully

### 2. Test Memories List Resource

**Test Command:**
```python
memories = await client.read_resource("knowledge://memories")
```

**Expected Result:**
- JSON array of memories with key, preview, updated_at
- Should include count field

### 3. Test Memory Content Resource (Template)

**Test Command:**
```python
memory = await client.read_resource("knowledge://memory/user_preferences")
```

**Expected Result:**
- JSON with key and content fields
- Should return error if memory not found

### 4. Test Workflows List Resource

**Test Command:**
```python
workflows = await client.read_resource("knowledge://workflows")
```

**Expected Result:**
- JSON array of workflows with name, version, description, steps_count
- Should include count field

### 5. Test Workflow Definition Resource (Template)

**Test Command:**
```python
workflow = await client.read_resource("knowledge://workflow/deploy_feature")
```

**Expected Result:**
- JSON with complete workflow definition including steps
- Should return error if workflow not found

### 6. Test Thinking Patterns Resource

**Test Command:**
```python
patterns = await client.read_resource("knowledge://thinking-patterns")
```

**Expected Result:**
- JSON array of thinking patterns with usage statistics
- Should include pattern names and applicable_to lists

### 7. Test Node Context Resource (Template)

**Test Command:**
```python
context = await client.read_resource("knowledge://node/concept:python/context")
```

**Expected Result:**
- JSON with node and its immediate neighbors (depth 1)
- Should return error if node not found

### 8. Test Recent Tool Usage Resource

**Test Command:**
```python
usage = await client.read_resource("knowledge://tool-usage/recent")
```

**Expected Result:**
- JSON with recent_calls array (up to 20 most recent)
- Should include tool_name, status, timestamp for each call

## Error Handling Tests

### Test Database Not Initialized

1. Stop the database
2. Try accessing any resource
3. **Expected:** Should return `{"error": "Database not initialized"}`

### Test Invalid Parameters

1. Try accessing non-existent memory: `knowledge://memory/nonexistent`
2. Try accessing non-existent workflow: `knowledge://workflow/nonexistent`
3. Try accessing non-existent node: `knowledge://node/invalid:id/context`
4. **Expected:** Should return appropriate error messages

## Integration Tests

### Test Prompt -> Tool Execution Flow

1. Get the `discover_concept` prompt for "databases"
2. Follow the instructions in the prompt
3. Use search_nodes, get_graph_context as instructed
4. Verify the workflow produces useful results

### Test Resource -> Tool Comparison

1. Read `knowledge://stats` resource
2. Call `analyze_graph('summary')` tool
3. Compare the results - should be consistent

### Test Resource Template Parameter Parsing

1. Read `knowledge://memory/test_key`
2. Verify the `memory_key` parameter is correctly extracted from URI
3. Repeat for workflow and node context templates

## Performance Tests

1. Load test resources with large result sets
2. Verify response times are acceptable (< 1 second)
3. Check memory usage doesn't spike

## Checklist

- [ ] All 5 prompts return properly formatted instructions
- [ ] All 8 resources return valid JSON
- [ ] Error handling works for database not initialized
- [ ] Error handling works for not found items
- [ ] Resource templates correctly parse URI parameters
- [ ] Resources provide instant access without tool call overhead
- [ ] Prompts guide effective knowledge graph usage

## Notes

- Prompts are meant to guide the agent, not replace tools
- Resources provide read-only access for common queries
- Both features should reduce redundant tool calls
- Monitor agent usage patterns to identify needs for additional prompts/resources




