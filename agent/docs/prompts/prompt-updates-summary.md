# Prompt Updates: Leveraging `/<prompt>` and `@<resource>` Features

## Overview

All scheduled task prompts have been updated to leverage the new `/<prompt>` and `@<resource>` middleware features. This should significantly improve task execution by:

1. **Providing immediate context** via `@<resource>` references (reducing tool call overhead)
2. **Guiding structured exploration** via `/<prompt>` command suggestions
3. **Reducing cognitive load** with clear step-by-step instructions
4. **Lowering costs** by frontloading context and reducing trial-and-error

## What Changed

### Updated Prompts

All major scheduled task prompts have been restructured:

1. **`curiosity_prompt.md`** - Knowledge exploration and gap filling
2. **`reflection_prompt.md`** - Self-improvement and task generation
3. **`curation_prompt.md`** - Memory organization and knowledge integration
4. **`gardener_prompt.md`** - Knowledge graph cultivation
5. **`alignment_prompt.md`** - Values and purpose alignment
6. **`metacognition_prompt.md`** - Cognitive pattern analysis
7. **`workflow_discovery_prompt.md`** - Workflow abstraction
8. **`integrated_reflection_prompt.md`** - Comprehensive holistic reflection

### Key Improvements

#### Before
```markdown
Conduct a centrality analysis of your knowledge graph to identify nodes 
with low connectivity...
```

**Issues:**
- No specific guidance on HOW to conduct analysis
- No context about current state
- Agent must figure out which tools to use
- More trial and error = higher costs

#### After
```markdown
## Step 1: Analyze Your Knowledge Structure

First, check your current knowledge state:
- Review @knowledge://stats to understand your graph size and composition
- Check @knowledge://tool-usage/recent to see what areas you've been exploring

Then use `/analyze_knowledge_structure` to get comprehensive guidance on:
- Identifying central concepts vs isolated nodes
- Finding disconnected clusters
- Spotting weakly connected areas
```

**Benefits:**
- Immediate context via resources (no tool calls needed)
- Specific prompt commands for structured guidance
- Clear step-by-step process
- Reduced ambiguity = lower costs

## How the Features Work

### `@<resource>` - Instant Data Access

When the agent encounters `@<resource>` in a prompt:
1. The `ResourceFetchingMiddleware` intercepts it
2. Fetches the resource content from MCP servers
3. Injects the content directly into the message
4. No tool call overhead - it's pre-loaded context

**Examples:**
- `@knowledge://stats` → Current graph statistics
- `@knowledge://memories` → List of all memories
- `@knowledge://tool-usage/recent` → Recent tool usage patterns
- `@knowledge://thinking-patterns` → Available problem-solving patterns
- `@knowledge://workflows` → Available workflows

**Benefits:**
- Zero tool call latency
- Immediate context for decision-making
- Reduced need to "explore" the state

### `/<prompt>` - Structured Guidance

When the agent encounters `/<prompt>` in a prompt:
1. The `CommandPromptMiddleware` intercepts it
2. Fetches the MCP prompt template
3. Renders it with appropriate arguments
4. Replaces the command with the full prompt text

**Examples:**
- `/analyze_knowledge_structure` → Comprehensive graph analysis guidance
- `/discover_concept Python` → Structured concept exploration for Python
- `/solve_problem <description>` → Problem-solving framework
- `/organize_memories project` → Memory organization guidance
- `/execute_workflow deploy_feature` → Workflow execution instructions

**Benefits:**
- Consistent, proven approaches
- Reduced cognitive load
- Best practices encoded in prompts
- More focused, efficient execution

## Cost Reduction Strategy

### Old Approach
1. Read vague prompt
2. Try to figure out what to do
3. Call tools to explore state
4. Realize wrong approach
5. Try different tools
6. Eventually find right path
7. Execute task

**Cost:** Many exploratory tool calls + trial/error + model thinking time

### New Approach
1. Read detailed prompt with embedded resources
2. See current state immediately (via `@resources`)
3. Get structured guidance (via `/<prompts>`)
4. Follow clear steps
5. Execute task efficiently

**Cost:** Minimal tool calls + focused execution + reduced model confusion

## Updated Prompt Structure

All prompts now follow this pattern:

```markdown
# [Task Name & Purpose]

Clear statement of the task's goal.

## Step 1: Gather Context
- @resource references for immediate state awareness
- Clear questions to consider

## Step 2: [Specific Action]
- Specific steps to take
- /<prompt> commands for structured guidance
- @resource references for data access
- Questions to guide thinking

## Step 3: [Next Action]
...continuing the pattern...

## Remember
Key takeaway or principle for the task
```

## Usage Examples

### Example 1: Curiosity Task

**Old behavior:**
```
Agent reads: "Conduct centrality analysis..."
Agent thinks: "How do I do that? What's my current state?"
Agent calls: analyze_graph tool
Agent calls: search_nodes tool (exploring)
Agent calls: get_node tool (more exploring)
...eventually figures it out...
```

**New behavior:**
```
Agent reads prompt with:
- @knowledge://stats (sees: 1234 nodes, 5678 edges)
- @knowledge://tool-usage/recent (sees recent activity)
- Instruction: "Use /analyze_knowledge_structure"
Agent immediately knows:
- Current graph size
- Recent focus areas
- How to get structured analysis
Agent executes efficiently with clear direction
```

### Example 2: Reflection Task

**Old behavior:**
```
Agent reads: "Review past actions..."
Agent thinks: "What have I been doing? Where do I look?"
Agent searches through conversation history
Agent tries various tools to understand state
...lots of exploration...
```

**New behavior:**
```
Agent reads prompt with:
- @knowledge://tool-usage/recent (sees last 20 tool calls)
- @knowledge://stats (sees knowledge growth)
- @knowledge://memories (sees any flagged issues)
Agent immediately sees:
- What it's been doing
- Whether there are problems
- What has changed
Agent proceeds to reflection with full context
```

## Testing the Updates

### Manual Test

Run a curiosity task and observe:
1. Does it reference @resources correctly?
2. Does it use /<prompt> commands appropriately?
3. Does it execute more efficiently than before?
4. Are there fewer exploratory tool calls?

### Metrics to Track

**Before updates:**
- Tool calls per task: ?
- Average task completion time: ?
- Failed/repeated attempts: ?

**After updates:**
- Tool calls per task: ? (should be lower)
- Average task completion time: ? (should be faster)
- Failed/repeated attempts: ? (should be fewer)

## Future Enhancements

### Potential Additions

1. **More Resources:**
   - `@knowledge://recent-sessions` - Recent conversation sessions
   - `@knowledge://failed-tasks` - Tasks that failed recently
   - `@knowledge://knowledge-gaps` - Identified gaps in knowledge

2. **More Prompts:**
   - `/debug_issue <description>` - Systematic debugging guidance
   - `/integrate_concept <concept>` - Concept integration workflow
   - `/plan_project <project>` - Project planning framework

3. **Prompt Caching:**
   - Cache frequently used prompts to reduce latency
   - Pre-load common resources at task start

4. **Adaptive Prompts:**
   - Prompts that adjust based on current state
   - Conditional sections based on @resource content

## Rollout Plan

1. ✅ Update all prompt files
2. ⬜ Test with scheduled tasks
3. ⬜ Monitor tool call metrics
4. ⬜ Gather feedback from task execution logs
5. ⬜ Refine prompts based on actual usage
6. ⬜ Document any issues or edge cases

## Notes

- The `concept_workflow.md` file was left unchanged as it's reference documentation, not an executable prompt
- All prompts are backward compatible - they work fine even if middleware is disabled
- Resources and prompts gracefully degrade if MCP servers are unavailable

## Questions?

- Are there specific resources that should be added?
- Are there common patterns that should become prompts?
- Should we add more examples or clarification to any prompts?

