# Agent Guide: Using FastMCP Prompts and Resources

## Overview

The knowledge server now exposes **Prompts** (reusable message templates) and **Resources** (direct read-only data access) through FastMCP. These features help you work more efficiently with the knowledge graph.

### Key Benefits

1. **Prompts** provide proven templates for complex reasoning tasks
2. **Resources** give instant access to common data without tool calls
3. Both reduce cognitive load and improve consistency
4. They encode best practices for knowledge graph usage

## Part 1: Understanding Prompts

### What Are Prompts?

Prompts are reusable message templates that guide you through complex tasks. They're like having a mentor who reminds you of the best approach for common scenarios.

### Available Prompts

#### 1. `discover_concept` - Exploring Knowledge

**When to Use:**
- You need to understand what the knowledge graph knows about a topic
- Starting research on an unfamiliar concept
- Building a comprehensive understanding of a subject

**Arguments:**
- `concept_name` (str): The concept to explore

**Example Usage:**
```python
prompt = get_prompt("discover_concept", {"concept_name": "FastMCP"})
# Follow the instructions in the returned prompt
```

**What It Guides You To Do:**
1. Use search_nodes with natural language queries
2. Get full context with get_graph_context (depth 2)
3. Identify relationships and connected concepts
4. Summarize knowledge and identify gaps

#### 2. `solve_problem` - Structured Problem Solving

**When to Use:**
- Facing a complex problem that requires systematic thinking
- Want to apply learned patterns from past solutions
- Need to document your approach for future reference

**Arguments:**
- `problem_description` (str): Description of the problem to solve

**Example Usage:**
```python
prompt = get_prompt("solve_problem", {
    "problem_description": "Optimize database query performance"
})
```

**What It Guides You To Do:**
1. Use apply_sequential_thinking to get relevant patterns
2. Break problem into sub-problems
3. Search for similar past solutions
4. Execute solution step by step
5. Save approach with save_problem_solution

#### 3. `execute_workflow` - Running Stored Workflows

**When to Use:**
- Need to execute a predefined sequence of operations
- Want consistency in multi-step processes
- Running routine tasks with defined steps

**Arguments:**
- `workflow_name` (str): Name of the workflow to execute
- `context` (str, optional): Additional context for this execution

**Example Usage:**
```python
prompt = get_prompt("execute_workflow", {
    "workflow_name": "deploy_feature",
    "context": "staging environment"
})
```

**What It Guides You To Do:**
1. Retrieve workflow definition with get_workflow
2. Review each step and arguments
3. Execute steps in sequence
4. Track execution status
5. Report results and failures

#### 4. `organize_memories` - Memory Management

**When to Use:**
- Memories are getting cluttered or disorganized
- Need to consolidate related information
- Want to improve future retrieval efficiency

**Arguments:**
- `topic` (str): Topic area to organize memories around

**Example Usage:**
```python
prompt = get_prompt("organize_memories", {
    "topic": "user_preferences"
})
```

**What It Guides You To Do:**
1. Search for related memories
2. Check for duplicates or outdated info
3. Consolidate related memories
4. Create hierarchical memory keys
5. Link memories to concept nodes

#### 5. `analyze_knowledge_structure` - Graph Health Check

**When to Use:**
- Want to understand overall knowledge graph structure
- Looking for disconnected or under-connected knowledge
- Planning knowledge graph improvements

**Arguments:** None

**Example Usage:**
```python
prompt = get_prompt("analyze_knowledge_structure", {})
```

**What It Guides You To Do:**
1. Get summary statistics with analyze_graph('summary')
2. Find central concepts with analyze_graph('centrality')
3. Find isolated clusters with analyze_graph('components')
4. Identify gaps and disconnected nodes
5. Suggest improvements

## Part 2: Understanding Resources

### What Are Resources?

Resources are read-only endpoints that provide instant access to commonly-needed data. Unlike tools, they don't require a function call - you just read them like files.

### Why Use Resources Instead of Tools?

**Use Resources When:**
- You need quick access to common data
- The data is read-only (no modifications needed)
- You want to reduce tool call overhead
- Checking status or getting overviews

**Use Tools When:**
- You need to modify data (add, update, delete)
- You need advanced filtering or querying
- You need to perform complex operations
- Resources don't provide what you need

### Available Resources

#### 1. `knowledge://stats` - Graph Statistics

**Purpose:** Get overview statistics about the knowledge graph

**Returns:**
```json
{
  "total_nodes": 1234,
  "total_edges": 5678,
  "node_types": {
    "Concept": 450,
    "Memory": 320,
    "Session": 100
  },
  "edge_types": {
    "RELATES_TO": 2000,
    "INSTANCE_OF": 500
  }
}
```

**When to Use:**
- Quick health check of the knowledge graph
- Understanding graph size and composition
- Before starting major operations

#### 2. `knowledge://memories` - All Memories List

**Purpose:** Get list of all stored memories with previews

**Returns:**
```json
{
  "memories": [
    {
      "key": "user_preferences",
      "preview": "User prefers Python 3.11, dark mode, verbose logging...",
      "updated_at": "2024-01-15T10:30:00"
    }
  ],
  "count": 45
}
```

**When to Use:**
- Getting overview of stored memories
- Finding what's already saved before creating new memory
- Checking for memory naming patterns

#### 3. `knowledge://memory/{memory_key}` - Specific Memory

**Purpose:** Get content of a specific memory

**URI Template:** Replace `{memory_key}` with actual key

**Example:**
```
knowledge://memory/user_preferences
knowledge://memory/project/status
```

**Returns:**
```json
{
  "key": "user_preferences",
  "content": "Full memory content here..."
}
```

**When to Use:**
- Quick memory lookup without tool call
- Checking memory content before update
- Referencing memory in prompts or reasoning

#### 4. `knowledge://workflows` - Workflows List

**Purpose:** Get list of available workflows

**Returns:**
```json
{
  "workflows": [
    {
      "name": "deploy_feature",
      "version": 3,
      "description": "Deploys a feature to production",
      "steps_count": 8
    }
  ],
  "count": 12
}
```

**When to Use:**
- Discovering available workflows
- Checking if a workflow exists before execution
- Understanding workflow inventory

#### 5. `knowledge://workflow/{workflow_name}` - Workflow Definition

**Purpose:** Get complete workflow definition with all steps

**URI Template:** Replace `{workflow_name}` with actual workflow name

**Example:**
```
knowledge://workflow/deploy_feature
knowledge://workflow/analyze_codebase
```

**Returns:**
```json
{
  "name": "deploy_feature",
  "version": 3,
  "description": "Deploys a feature to production",
  "steps": [
    {"tool_name": "run_tests", "args": {"suite": "all"}},
    {"tool_name": "build_artifact", "args": {}}
  ]
}
```

**When to Use:**
- Before executing a workflow (review steps)
- Understanding what a workflow does
- Planning workflow modifications

#### 6. `knowledge://thinking-patterns` - Available Thinking Patterns

**Purpose:** Get list of stored thinking patterns for problem-solving

**Returns:**
```json
{
  "patterns": [
    {
      "name": "debugging_approach",
      "description": "Systematic approach to debugging",
      "applicable_to": ["bugs", "errors", "failures"],
      "usage_count": 45
    }
  ],
  "count": 8
}
```

**When to Use:**
- Finding relevant problem-solving approaches
- Before starting complex reasoning tasks
- Learning from past successful patterns

#### 7. `knowledge://node/{node_id}/context` - Node Context

**Purpose:** Get a node and its immediate neighbors (depth 1)

**URI Template:** Replace `{node_id}` with actual node ID

**Example:**
```
knowledge://node/concept:python/context
knowledge://node/memory:user_prefs/context
```

**Returns:**
```json
{
  "central_node": {...},
  "neighbors": [...],
  "edges": [...]
}
```

**When to Use:**
- Quick context around a specific node
- Understanding immediate relationships
- Before deeper graph traversal

#### 8. `knowledge://tool-usage/recent` - Recent Tool Usage

**Purpose:** Get statistics on recent tool calls and failures

**Returns:**
```json
{
  "recent_calls": [
    {
      "tool_name": "search_nodes",
      "status": "success",
      "timestamp": "2024-01-15T10:30:00"
    },
    {
      "tool_name": "add_node",
      "status": "error",
      "timestamp": "2024-01-15T10:29:00"
    }
  ],
  "count": 20
}
```

**When to Use:**
- Debugging recent failures
- Understanding tool usage patterns
- Identifying frequently used tools

## Part 3: Best Practices

### When to Use Prompts

1. **Starting Complex Tasks:** Use prompts as checklists for multi-step operations
2. **Learning Best Practices:** Prompts encode proven approaches - follow them
3. **Maintaining Consistency:** Use the same prompt for similar tasks
4. **Avoiding Mistakes:** Prompts remind you of easy-to-forget steps

### When to Use Resources

1. **Quick Lookups:** Get common data without tool call overhead
2. **Status Checks:** Check graph state before major operations
3. **Discovery:** Browse available memories, workflows, patterns
4. **Context Building:** Gather background info for reasoning

### Combining Prompts and Resources

**Example Workflow:**
1. Read `knowledge://stats` to understand graph state
2. Use `discover_concept` prompt to explore a topic
3. Read `knowledge://thinking-patterns` for relevant approaches
4. Execute using guided approach from prompt
5. Save results to build knowledge

### Common Patterns

#### Pattern 1: Research and Learn
```
1. Read knowledge://stats (understand current state)
2. Get discover_concept prompt for topic
3. Follow prompt's search and exploration steps
4. Read knowledge://node/{found_node}/context for depth
5. Summarize and save findings
```

#### Pattern 2: Solve New Problem
```
1. Get solve_problem prompt with problem description
2. Read knowledge://thinking-patterns for relevant approaches
3. Search for similar past solutions
4. Apply pattern-guided reasoning
5. Save solution with save_problem_solution
```

#### Pattern 3: Execute Routine Task
```
1. Read knowledge://workflows to find relevant workflow
2. Read knowledge://workflow/{name} to review steps
3. Get execute_workflow prompt
4. Follow prompt to execute each step
5. Track and report results
```

#### Pattern 4: Maintain Knowledge Graph
```
1. Read knowledge://stats for overview
2. Get analyze_knowledge_structure prompt
3. Follow prompt's analysis steps
4. Identify improvement opportunities
5. Create new connections and consolidate
```

## Part 4: Error Handling

### Resource Errors

If a resource returns an error, it will be in this format:
```json
{"error": "Description of the error"}
```

**Common Errors:**
- `"Database not initialized"` - Wait for database to initialize
- `"Memory 'key' not found"` - Check memory key spelling or create memory
- `"Node 'id' not found"` - Verify node ID is correct
- `"Workflow 'name' not found"` - Check workflow name or create workflow

### Prompt Errors

Prompts themselves don't error - they always return guidance. However, following the prompt's instructions might lead to tool errors. Handle these gracefully:

1. Read the error message carefully
2. Check if a resource can help (e.g., knowledge://stats to verify database state)
3. Adjust approach based on error
4. Document the issue if it's a pattern

## Part 5: Quick Reference

### All Prompts
- `discover_concept(concept_name)` - Explore knowledge about a concept
- `solve_problem(problem_description)` - Apply structured problem-solving
- `execute_workflow(workflow_name, context?)` - Run stored workflows
- `organize_memories(topic)` - Organize and consolidate memories
- `analyze_knowledge_structure()` - Analyze graph structure and health

### All Resources
- `knowledge://stats` - Graph statistics overview
- `knowledge://memories` - List all memories with previews
- `knowledge://memory/{key}` - Get specific memory content
- `knowledge://workflows` - List available workflows
- `knowledge://workflow/{name}` - Get workflow definition
- `knowledge://thinking-patterns` - List thinking patterns
- `knowledge://node/{id}/context` - Get node with neighbors
- `knowledge://tool-usage/recent` - Recent tool usage stats

## Remember

- **Prompts guide, Resources provide data**
- **Use prompts for complex tasks, resources for quick data**
- **Always check resources before heavy tool operations**
- **Follow prompt guidance - they encode best practices**
- **Combine them for powerful workflows**

The goal is to make you more effective and efficient. Use these features actively!




