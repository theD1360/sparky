# Smart Maintenance Task Selection

Your role is to assess the current state of your knowledge system and intelligently select the most urgent maintenance task to perform.

## Step 1: Assess System Health

**Gather key metrics:**
- Check @knowledge://stats for:
  - Total nodes and edges
  - Node-to-edge ratio (healthy ratio is ~2-4 edges per node)
  - Recent growth patterns
  - Node type distributions

- Use `validate_graph_integrity()` to identify:
  - Orphaned nodes (nodes with no connections)
  - Dangling edges (edges pointing to non-existent nodes)
  - Missing embeddings
  - Duplicate edges and self-loops
  - Overall structural health and issue counts

## Step 2: Identify Urgent Needs

Based on your analysis, determine which maintenance category needs the most attention:

**Gardening (gardener_prompt.md)** - Choose if:
- High number of isolated nodes (degree < 2)
- Many disconnected clusters
- Fragmented knowledge areas
- Low connectivity ratio (< 2 edges per node)

**Curiosity (curiosity_prompt.md)** - Choose if:
- Shallow nodes lacking depth
- Knowledge gaps in core areas
- Recent additions need enrichment
- Stale or unexplored concepts

**Curation (curation_prompt.md)** - Choose if:
- Duplicate or redundant nodes
- Low-quality or outdated information
- Inconsistent node types
- Graph bloat or noise

**Reflection (reflection_prompt.md)** - Choose if:
- Need to consolidate recent learnings
- Pattern recognition across sessions
- Strategic thinking about knowledge organization
- Long-term goal alignment

## Step 3: Select and Execute

**Make a clear decision:**
1. State which maintenance task is most urgent and why
2. Load the selected prompt from `prompts/` directory
3. Execute that prompt's full workflow
4. Do not deviate from the selected prompt's steps

**Priority guidance:**
- **Critical**: > 20% isolated nodes → Gardening
- **High**: Shallow knowledge on core concepts → Curiosity  
- **Medium**: Redundancy or quality issues → Curation
- **Low**: General consolidation → Reflection

## Step 4: Document Your Choice

**Record your decision:**
- Which task you selected
- Key metrics that informed your decision
- Expected impact on knowledge graph health
- Link this maintenance session to current context

**Remember:** You're performing triage on your knowledge system. Choose the maintenance task that addresses the most pressing structural issue, then execute it thoroughly using the selected prompt's guidance.
