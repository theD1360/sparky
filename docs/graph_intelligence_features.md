# Graph Intelligence Features

Four powerful new features to supercharge your knowledge graph operations.

## 1. find_similar_nodes 🔍

**Find semantically similar nodes using vector embeddings**

### Use Cases
- Discover related concepts automatically
- Find potential duplicate nodes
- Suggest connections between ideas
- Explore knowledge neighborhoods

### Example Usage

```python
# Find concepts similar to Python
find_similar_nodes(
    node_id="concept:python",
    similarity_threshold=0.8,
    limit=10
)
```

### Response
```json
{
    "success": true,
    "result": [
        {
            "id": "concept:programming_language",
            "type": "Concept",
            "label": "Programming Languages",
            "content": "...",
            "similarity": 0.92
        },
        {
            "id": "concept:javascript",
            "type": "Concept",
            "label": "JavaScript",
            "content": "...",
            "similarity": 0.85
        }
    ],
    "message": "Found 2 similar nodes to 'concept:python'"
}
```

### Tips
- Use `similarity_threshold=0.95` to find near-duplicates
- Use `similarity_threshold=0.7` for broader exploration
- Set `include_self=true` to include the reference node in results

---

## 2. validate_graph_integrity ✅

**Run comprehensive health checks on your graph**

### Use Cases
- Catch data quality issues early
- Regular graph maintenance
- Pre-deployment validation
- Audit graph structure

### Example Usage

```python
# Run all checks
validate_graph_integrity()

# Run specific checks
validate_graph_integrity(
    checks=["orphaned_nodes", "dangling_edges"]
)
```

### Available Checks

| Check | Description |
|-------|-------------|
| **orphaned_nodes** | Nodes with no edges (isolated) |
| **dangling_edges** | Edges pointing to non-existent nodes |
| **missing_embeddings** | Nodes without vector embeddings |
| **duplicate_edges** | Duplicate relationship records |
| **self_loops** | Edges from a node to itself |

### Response
```json
{
    "success": true,
    "result": {
        "checks_run": ["orphaned_nodes", "dangling_edges"],
        "issues_found": {
            "orphaned_nodes": [
                {"id": "concept:old", "type": "Concept", "label": "Old Concept"}
            ]
        },
        "total_issues": 1,
        "healthy": false
    },
    "message": "Graph integrity check complete: issues detected. Found 1 issues across 2 checks."
}
```

### Recommended Schedule
- Run **orphaned_nodes** and **dangling_edges** checks weekly
- Run **missing_embeddings** check monthly
- Run all checks before major releases

---

## 3. extract_subgraph 📦

**Extract and export portions of your graph**

### Use Cases
- Backup specific knowledge domains
- Share subgraphs with team members
- Import into visualization tools
- Migrate to other graph databases

### Example Usage

```python
# Extract a concept hierarchy as JSON
extract_subgraph(
    root_node_ids=["concept:programming"],
    depth=3,
    include_node_types=["Concept"],
    export_format="json"
)

# Export to Cypher for Neo4j
extract_subgraph(
    root_node_ids=["concept:python", "concept:java"],
    depth=2,
    export_format="cypher"
)

# Export to GraphML for visualization
extract_subgraph(
    root_node_ids=["concept:ai"],
    depth=2,
    export_format="graphml"
)
```

### Supported Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| **json** | Standard JSON with nodes/edges | General purpose, programmatic access |
| **cypher** | Neo4j CREATE statements | Import into Neo4j |
| **graphml** | GraphML XML format | Gephi, yEd, Cytoscape visualization |

### Response
```json
{
    "success": true,
    "result": {
        "nodes": [...],
        "edges": [...],
        "stats": {
            "node_count": 25,
            "edge_count": 40,
            "depth": 3
        },
        "export": "... formatted export string ..."
    },
    "message": "Extracted subgraph: 25 nodes, 40 edges (depth=3, format=json)"
}
```

### Tips
- Start with `depth=2` for manageable subgraphs
- Use `include_node_types` to filter specific domains
- JSON format includes full node content
- Cypher format is ready to paste into Neo4j Browser

---

## 4. merge_duplicate_nodes 🔀

**Consolidate duplicate or redundant nodes**

### Use Cases
- Clean up duplicate entries
- Merge data from multiple sources
- Consolidate knowledge about same concept
- Fix data import issues

### Example Usage

```python
# Merge duplicate Python concepts
merge_duplicate_nodes(
    node_ids=["concept:python", "concept:python_lang", "concept:python3"],
    keep_node_id="concept:python",
    merge_strategy="union"
)

# Merge keeping only specific node's properties
merge_duplicate_nodes(
    node_ids=["user:john_doe", "user:john"],
    keep_node_id="user:john_doe",
    merge_strategy="keep"
)
```

### Merge Strategies

| Strategy | Description | When to Use |
|----------|-------------|-------------|
| **union** | Combine all properties | Merge complementary data |
| **keep** | Keep only kept node's properties | Trust one source only |
| **prefer_newer** | Use most recent properties | Latest data is best |

### What Happens
1. All properties are merged according to strategy
2. All edges are redirected to the kept node
3. Duplicate edges are automatically removed
4. Merged nodes are deleted
5. Kept node is updated with merged data

### Response
```json
{
    "success": true,
    "result": {
        "kept_node_id": "concept:python",
        "merged_node_ids": ["concept:python_lang", "concept:python3"],
        "edges_redirected": 15,
        "merged_properties": {
            "importance": "high",
            "category": "programming",
            "version": "3.12"
        },
        "node": {...}
    },
    "message": "Merged 2 nodes into 'concept:python', redirected 15 edges"
}
```

### Best Practices
1. **Find duplicates first** using `find_similar_nodes` with high threshold (0.95+)
2. **Review before merging** - merging is not easily reversible
3. **Use union strategy** when nodes have complementary data
4. **Backup first** for important nodes using `extract_subgraph`

---

## Workflow Examples

### Finding and Merging Duplicates

```python
# Step 1: Find potential duplicates
similar = find_similar_nodes(
    node_id="concept:python",
    similarity_threshold=0.95,
    limit=5
)

# Step 2: Review the results manually
# Look at similar nodes with very high similarity

# Step 3: Merge confirmed duplicates
merge_duplicate_nodes(
    node_ids=["concept:python", "concept:python_lang"],
    keep_node_id="concept:python",
    merge_strategy="union"
)
```

### Regular Graph Maintenance

```python
# Step 1: Check graph health
health = validate_graph_integrity()

# Step 2: Fix orphaned nodes
# Review orphaned nodes and either:
# - Connect them to the graph with add_edge
# - Delete them if no longer needed

# Step 3: Fix dangling edges  
# Delete edges pointing to non-existent nodes

# Step 4: Verify
health = validate_graph_integrity()
assert health["result"]["healthy"] == true
```

### Exporting a Knowledge Domain

```python
# Step 1: Identify root concepts
root_concepts = ["concept:machine_learning", "concept:deep_learning"]

# Step 2: Extract subgraph
subgraph = extract_subgraph(
    root_node_ids=root_concepts,
    depth=3,
    include_node_types=["Concept"],
    export_format="json"
)

# Step 3: Save or share the export
export_data = subgraph["result"]["export"]
# Write to file or send to teammate
```

---

## Performance Tips

1. **find_similar_nodes**: Results are cached by embedding system
2. **validate_graph_integrity**: Can be slow on very large graphs (>100K nodes)
3. **extract_subgraph**: Keep depth ≤ 3 for large graphs
4. **merge_duplicate_nodes**: Fast operation, but backup first

## Safety Notes

⚠️ **merge_duplicate_nodes is destructive** - merged nodes are permanently deleted
⚠️ **extract_subgraph** with large depths can return huge amounts of data
⚠️ Always run **validate_graph_integrity** after bulk operations

## Next Steps

These four features work great together:
1. Use `validate_graph_integrity` to find issues
2. Use `find_similar_nodes` to discover duplicates
3. Use `merge_duplicate_nodes` to consolidate
4. Use `extract_subgraph` to backup important domains

Happy graphing! 🚀

