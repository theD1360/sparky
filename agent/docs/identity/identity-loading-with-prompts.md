# Identity Loading with discover_concept Prompt

## Overview

The bot's identity loading now leverages the `discover_concept` prompt methodology for more thorough and structured identity discovery. This approach finds more relevant identity information and provides better coverage analysis.

## Comparison: Legacy vs Prompt-Guided

### Legacy Approach (still available)
```python
# Old method
identity = await knowledge.get_identity_memory(use_discover_concept_prompt=False)
```

**Process:**
1. Get `concept:self` node directly by ID
2. Get immediate neighbors (depth 1)
3. Combine all content

**Limitations:**
- Only finds nodes directly connected to `concept:self`
- Misses semantically related identity nodes
- No gap analysis or relationship mapping
- Limited to explicit graph connections

### Prompt-Guided Approach (default)
```python
# New method (default)
identity = await knowledge.get_identity_memory()
# or explicitly
identity = await knowledge.get_identity_memory(use_discover_concept_prompt=True)
```

**Process (follows `discover_concept` prompt):**
1. **Semantic Search**: Use `search_nodes` with natural language query
   - Searches for: "who am I, my purpose, my identity, my core being"
   - Finds nodes by meaning, not just explicit connections
   - Returns top 10 most relevant nodes

2. **Deep Context**: Use `get_graph_context` with depth 2
   - For each found node, get neighbors up to 2 hops away
   - Discovers related concepts even without direct connections
   - Builds comprehensive knowledge map

3. **Relationship Mapping**: Identify key connections
   - Maps relationships between identity nodes
   - Shows how concepts relate to each other
   - Provides structural understanding

4. **Coverage Analysis**: Summarize and identify gaps
   - Reports total nodes collected
   - Lists node types covered
   - Shows relationship count
   - Enables gap identification

**Benefits:**
- ✅ Finds more relevant identity information (semantic search)
- ✅ Discovers deeper connections (depth 2 context)
- ✅ Maps relationships between identity concepts
- ✅ Provides coverage metrics for gap analysis
- ✅ More robust to missing explicit connections

## Example Output Structure

### Legacy Output
```markdown
## CONCEPT

### Self
I am an AI assistant designed to help users...

### Purpose
My purpose is to assist with tasks...
```

### Prompt-Guided Output
```markdown
# IDENTITY KNOWLEDGE

## CONCEPT

### Self
I am an AI assistant designed to help users...

### Purpose
My purpose is to assist with tasks...

### Values
I value collaboration, learning, and growth...

## MEMORY

### Core Beliefs
I believe in continuous improvement...

## KEY RELATIONSHIPS

- Self --[ASPECT_OF]--> Values
- Purpose --[GUIDES]--> Behavior
- Core Beliefs --[INFORMS]--> Decision Making
- Values --[CONNECTED_TO]--> Purpose

## IDENTITY COVERAGE

- Total knowledge nodes: 15
- Node types: Concept, Memory, Guideline
- Relationships mapped: 23
```

## Usage

### In Bot Configuration

The new approach is **enabled by default**. No changes needed:

```python
bot = Bot(toolchain=toolchain, knowledge=knowledge)
await bot.start_chat()
# Identity loads automatically with prompt-guided approach
```

### Switching to Legacy

If you need the old behavior:

```python
# In knowledge.py or wherever identity is loaded
identity = await knowledge.get_identity_memory(use_discover_concept_prompt=False)
```

### Manual Identity Loading

```python
from sparky.knowledge import Knowledge

knowledge = Knowledge(session_id="test")

# Prompt-guided (recommended)
identity = await knowledge.get_identity_memory()

# Legacy
identity = await knowledge.get_identity_memory(use_discover_concept_prompt=False)
```

## Technical Details

### Semantic Search Query

The prompt approach uses this search query:
```python
"who am I, my purpose, my identity, my core being"
```

This query is designed to find:
- Core identity statements
- Purpose declarations
- Value systems
- Behavioral guidelines
- Self-descriptions

### Context Depth

Uses `depth=2` for graph context:
- **Depth 1**: Immediate neighbors
- **Depth 2**: Neighbors of neighbors

This discovers:
- Direct identity attributes
- Related concepts and memories
- Supporting information
- Historical context

### Node Collection Process

1. Search for core identity nodes (semantic)
2. For each found node:
   - Add to collection
   - Get graph context (depth 2)
   - Add all context nodes
3. Ensure `concept:self` is included
4. Get context for `concept:self` (depth 2)
5. Deduplicate using `seen_ids` set

### Relationship Tracking

For each identity node:
- Get all neighbors (both directions)
- Record edge types
- Filter to relationships within identity set
- Display top 10 most relevant

## Benefits for the Agent

### 1. More Complete Identity
The semantic search finds identity nodes that might not be explicitly connected to `concept:self` but are semantically related.

**Example:**
- Legacy: Finds only nodes with `ASPECT_OF` edge to `concept:self`
- Prompt-guided: Finds any node discussing identity, purpose, or self

### 2. Better Context Understanding
The depth-2 traversal provides richer context about how identity concepts relate.

**Example:**
- Legacy: Knows "I value collaboration"
- Prompt-guided: Knows "I value collaboration, which informs my communication style, which affects how I respond to users"

### 3. Gap Identification
The coverage summary helps identify missing identity information.

**Example:**
```
## IDENTITY COVERAGE
- Total knowledge nodes: 8
- Node types: Concept, Memory
- Relationships mapped: 5
```

This shows: No Guideline nodes - might need to add behavioral guidelines.

### 4. Relationship Awareness
The relationship mapping shows how identity concepts interconnect.

**Example:**
```
- Purpose --[GUIDES]--> Behavior
- Values --[INFORMS]--> Purpose
```

This helps the agent understand the structure of its identity.

## Performance Considerations

### Speed
- **Legacy**: Faster (direct node lookup)
- **Prompt-guided**: Slightly slower (semantic search + graph traversal)

**Recommendation**: The improved quality outweighs the small performance cost for identity loading (happens once per session).

### Memory
- **Legacy**: Loads fewer nodes
- **Prompt-guided**: Loads more nodes (better coverage)

**Impact**: Minimal - identity is loaded once and cached.

### Database Load
- **Legacy**: 1 direct lookup + 1 neighbor query
- **Prompt-guided**: 1 semantic search + multiple context queries

**Mitigation**: Optimized with node deduplication and limits.

## Migration Guide

### No Action Required
The new approach is backward compatible and enabled by default. Existing deployments will automatically benefit.

### To Revert to Legacy
If you experience issues:

1. **Temporarily**: Pass `use_discover_concept_prompt=False`
   ```python
   identity = await knowledge.get_identity_memory(use_discover_concept_prompt=False)
   ```

2. **Permanently**: Modify `knowledge.py`
   ```python
   async def get_identity_memory(self, use_discover_concept_prompt: bool = False):
   ```

### To Customize
You can modify the search query in `_load_identity_with_prompt()`:

```python
core_results = self.repository.search_nodes(
    query="YOUR CUSTOM QUERY HERE",  # Customize this
    node_type=None,
    limit=10,
    order_by="relevance",
)
```

## Troubleshooting

### "No identity nodes with content found"
**Cause**: Database has no identity information
**Solution**: Initialize identity nodes in the knowledge graph

### Identity loading is slow
**Cause**: Large graph with many related nodes
**Solution**: 
- Reduce context depth (change `depth=2` to `depth=1`)
- Reduce search limit (change `limit=10` to `limit=5`)

### Identity is missing expected information
**Cause**: Semantic search query doesn't match your identity content
**Solution**: Customize the search query to match your identity structure

### Too much information in identity
**Cause**: Semantic search is too broad
**Solution**:
- Make search query more specific
- Filter by node_type
- Reduce search limit

## Future Enhancements

### Potential Improvements

1. **Configurable Search Query**
   - Allow passing custom search terms
   - Support multiple search queries
   - Combine results from different queries

2. **Adaptive Depth**
   - Use depth 1 for large graphs
   - Use depth 2 for small graphs
   - Balance performance vs coverage

3. **Caching**
   - Cache identity between sessions
   - Invalidate on identity node changes
   - Reduce repeated searches

4. **Gap Filling**
   - Automatically detect missing identity aspects
   - Suggest questions to fill gaps
   - Guide identity development

## Conclusion

The prompt-guided identity loading provides:
- ✅ More thorough identity discovery
- ✅ Better relationship understanding
- ✅ Coverage analysis for gap identification
- ✅ Follows best practices from `discover_concept` prompt
- ✅ Backward compatible with legacy approach

This enhancement makes your agent more self-aware and better equipped to understand its own identity and purpose.




