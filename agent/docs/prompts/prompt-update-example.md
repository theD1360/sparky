# Prompt Update Example: Before & After

This document shows a concrete example of how the prompts have been improved with the new `/<prompt>` and `@<resource>` features.

## Example: Curiosity Prompt

### Before

```markdown
Conduct a centrality analysis of your knowledge graph to identify nodes with low 
connectivity—these represent gaps or weak spots in your understanding. Focus your 
efforts on these nodes: formulate targeted questions and actively seek answers from 
external sources to enrich your knowledge. For each node, aim to meaningfully increase 
its connections and integrate new information found. If you are unable to reliably 
enrich a node's connectivity after inquiry, mark it for deletion to maintain a healthy, 
robust knowledge graph.
```

**Problems with the old prompt:**
1. ❌ No guidance on HOW to conduct centrality analysis
2. ❌ No awareness of current system state
3. ❌ Vague instructions ("formulate targeted questions")
4. ❌ Agent must figure out which tools to use
5. ❌ More exploration and trial-and-error needed
6. ❌ Higher API costs from repeated attempts

### After

```markdown
# Curiosity & Knowledge Exploration

Your purpose is to explore knowledge gaps and actively strengthen your understanding.

## Step 1: Analyze Your Knowledge Structure

First, check your current knowledge state:
- Review @knowledge://stats to understand your graph size and composition
- Check @knowledge://tool-usage/recent to see what areas you've been exploring

Then use `/analyze_knowledge_structure` to get comprehensive guidance on:
- Identifying central concepts vs isolated nodes
- Finding disconnected clusters
- Spotting weakly connected areas

## Step 2: Identify Exploration Targets

Focus on nodes with low connectivity—these represent gaps in understanding:
1. Use centrality analysis to find nodes with few connections
2. Look for isolated clusters that should be connected
3. Identify concepts mentioned in @knowledge://memories that lack depth

## Step 3: Explore and Enrich

For each gap you've identified:
1. Use `/discover_concept <concept_name>` to get structured exploration guidance
2. Formulate targeted questions based on the prompt's recommendations
3. Search external sources and existing knowledge
4. Create meaningful connections using the knowledge graph tools

## Step 4: Integrate Findings

- Add new nodes and relationships discovered
- Link findings to the session context for traceability
- Check @knowledge://thinking-patterns for relevant learning patterns to apply

## Step 5: Clean Up

If a node cannot be meaningfully enriched after exploration:
- Mark it for potential deletion
- Document why it couldn't be enriched
- Maintain a healthy, well-connected knowledge graph

**Remember:** The goal is not just to add information, but to build a coherent, 
interconnected web of understanding. Use resources first for quick checks, then 
dive deeper with prompts and tools.
```

**Improvements in the new prompt:**
1. ✅ Clear step-by-step structure
2. ✅ Immediate context via `@knowledge://stats` and `@knowledge://tool-usage/recent`
3. ✅ Structured guidance via `/analyze_knowledge_structure` and `/discover_concept`
4. ✅ Specific tool and approach recommendations
5. ✅ Reduced ambiguity and exploration time
6. ✅ Lower API costs through focused execution

## Execution Comparison

### Before: Agent Behavior
```
1. Read vague prompt
2. Think: "How do I conduct centrality analysis?"
3. Try calling analyze_graph tool
4. Think: "What parameters do I need?"
5. Call with wrong parameters (fails)
6. Think: "Let me check the knowledge graph state first"
7. Call search_nodes tool (exploring)
8. Call get_node tool (more exploring)
9. Think: "Maybe I should check graph statistics"
10. Call analyze_graph('summary')
11. Now understands state, tries centrality analysis again
12. Finally succeeds
... continues with similar trial-and-error ...
```

**Cost:** ~12-15 tool calls, multiple failed attempts, lots of model thinking tokens

### After: Agent Behavior
```
1. Read structured prompt
2. See @knowledge://stats embedded → knows graph size immediately (1234 nodes, 5678 edges)
3. See @knowledge://tool-usage/recent → knows recent focus areas
4. Instruction says: "Use /analyze_knowledge_structure"
5. Call /analyze_knowledge_structure → get detailed guidance
6. Follow step-by-step approach from prompt
7. When finds gap, use `/discover_concept <concept>` as instructed
8. Execute efficiently with clear direction
```

**Cost:** ~4-6 tool calls, focused execution, minimal thinking tokens

**Estimated Cost Reduction:** 50-70% fewer tool calls, faster execution, clearer results

## Resource Usage Comparison

### Before
```python
# Agent must call tools to get basic information
await bot.toolchain.call("analyze_graph", {"analysis_type": "summary"})
# ^ This costs API time, might fail, adds latency

# Then must call again for centrality
await bot.toolchain.call("analyze_graph", {"analysis_type": "centrality"})
# ^ Another API call, more latency

# And the agent might not know these tools exist without exploration
```

### After
```markdown
# Resources are pre-loaded into the prompt automatically
@knowledge://stats
# ^ Injected before the message is sent, zero tool call overhead
# Agent sees:
# {
#   "total_nodes": 1234,
#   "total_edges": 5678,
#   "node_types": { "Concept": 450, "Memory": 320 }
# }

@knowledge://tool-usage/recent  
# ^ Also injected, showing recent activity patterns
# Agent immediately knows what it's been doing

# Then gets structured guidance
/analyze_knowledge_structure
# ^ This renders to a comprehensive prompt template
# Agent gets step-by-step instructions on HOW to proceed
```

**Benefits:**
- Resources load instantly (no tool calls)
- Prompts provide proven approaches (no guessing)
- Agent starts with full context (no exploration phase)

## Cost Analysis

### Scenario: Agent runs curiosity task 100 times per month

**Before (per task):**
- Tool calls: ~12
- Model input tokens: ~2000
- Model output tokens: ~800
- Approximate cost: $0.04/task

**Monthly cost (100 tasks):** ~$4.00

**After (per task):**
- Tool calls: ~5
- Model input tokens: ~2500 (slightly higher due to richer prompt)
- Model output tokens: ~600 (more focused)
- Approximate cost: $0.02/task

**Monthly cost (100 tasks):** ~$2.00

**Estimated savings:** ~50% ($2.00/month for this single task)

**Across all scheduled tasks (reflection, curiosity, curation, etc.):**
- Estimated total monthly savings: $10-15
- Additional benefits:
  - Faster task completion
  - Higher quality results
  - More consistent execution
  - Reduced failure rates

## Key Takeaways

1. **Pre-loading context via `@resources`** eliminates exploration phase
2. **Structured guidance via `/<prompts>`** reduces trial-and-error
3. **Step-by-step instructions** make execution more predictable
4. **Clear tool recommendations** prevent wasted API calls
5. **Result:** Lower costs, faster execution, better outcomes

## Next Steps

1. Monitor actual tool call metrics after deployment
2. Gather feedback from task execution logs
3. Refine prompts based on real-world usage patterns
4. Consider adding more resources and prompts as needed

