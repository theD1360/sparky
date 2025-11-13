# Bulk Operations and Update Node Usage Guide

The knowledge graph server now supports bulk operations for efficiently adding multiple nodes and edges in a single transaction, as well as a dedicated update command for modifying existing nodes, and a convenient append_graph function for merging complete subgraphs.

## Append Graph (Recommended for Complete Subgraphs)

Use `append_graph` when you have both nodes and edges to add together. This is the most convenient way to merge a complete subgraph into your knowledge graph:

```python
append_graph(
    nodes=[
        {
            "node_id": "concept:animals",
            "node_type": "Concept",
            "label": "Animals",
            "content": "Living organisms that can move..."
        },
        {
            "node_id": "concept:mammals",
            "node_type": "Concept",
            "label": "Mammals",
            "content": "Warm-blooded vertebrates..."
        },
        {
            "node_id": "concept:dogs",
            "node_type": "Concept",
            "label": "Dogs",
            "content": "Domesticated mammals..."
        }
    ],
    edges=[
        {
            "source_id": "concept:mammals",
            "target_id": "concept:animals",
            "edge_type": "SUBCLASS_OF"
        },
        {
            "source_id": "concept:dogs",
            "target_id": "concept:mammals",
            "edge_type": "SUBCLASS_OF"
        }
    ]
)
```

### Response Format

```json
{
    "success": true,
    "result": {
        "nodes_added": ["concept:animals", "concept:mammals", "concept:dogs"],
        "nodes_updated": [],
        "nodes_failed": [],
        "edges_added": [
            "concept:mammals -> concept:animals (SUBCLASS_OF)",
            "concept:dogs -> concept:mammals (SUBCLASS_OF)"
        ],
        "edges_updated": [],
        "edges_failed": [],
        "total_nodes": 3,
        "total_edges": 2
    },
    "message": "Graph appended: 3 nodes added, 0 nodes updated, 2 edges added, 0 edges updated"
}
```

## Bulk Add Nodes

Use `bulk_add_nodes` to add or update multiple nodes at once:

```python
bulk_add_nodes([
    {
        "node_id": "concept:python",
        "node_type": "Concept",
        "label": "Python Programming",
        "content": "Python is a high-level programming language...",
        "properties": {"importance": "high", "category": "programming"}
    },
    {
        "node_id": "concept:java",
        "node_type": "Concept",
        "label": "Java Programming",
        "content": "Java is an object-oriented language...",
        "properties": {"importance": "high", "category": "programming"}
    },
    {
        "node_id": "concept:javascript",
        "node_type": "Concept",
        "label": "JavaScript Programming",
        "content": "JavaScript is a dynamic scripting language..."
    }
])
```

### Response Format

```json
{
    "success": true,
    "result": {
        "added": ["concept:python", "concept:java", "concept:javascript"],
        "updated": [],
        "failed": [],
        "total": 3
    },
    "message": "Bulk operation completed: 3 added, 0 updated, 0 failed"
}
```

## Bulk Add Edges

Use `bulk_add_edges` to add or update multiple edges at once:

```python
# Note: All referenced nodes must exist before creating edges
bulk_add_edges([
    {
        "source_id": "concept:python",
        "target_id": "concept:programming",
        "edge_type": "INSTANCE_OF",
        "properties": {"confidence": 1.0}
    },
    {
        "source_id": "concept:java",
        "target_id": "concept:programming",
        "edge_type": "INSTANCE_OF",
        "properties": {"confidence": 1.0}
    },
    {
        "source_id": "concept:javascript",
        "target_id": "concept:programming",
        "edge_type": "INSTANCE_OF"
    }
])
```

### Response Format

```json
{
    "success": true,
    "result": {
        "added": [
            "concept:python -> concept:programming (INSTANCE_OF)",
            "concept:java -> concept:programming (INSTANCE_OF)",
            "concept:javascript -> concept:programming (INSTANCE_OF)"
        ],
        "updated": [],
        "failed": [],
        "total": 3
    },
    "message": "Bulk operation completed: 3 added, 0 updated, 0 failed"
}
```

## Error Handling

Bulk operations are fault-tolerant. If some items fail, others will still be processed:

```python
bulk_add_nodes([
    {
        "node_id": "valid:node",
        "node_type": "Test",
        "label": "Valid Node"
    },
    {
        "node_id": "invalid:node",
        # Missing required field: node_type
        "label": "Invalid Node"
    }
])
```

Response:
```json
{
    "success": true,
    "result": {
        "added": ["valid:node"],
        "updated": [],
        "failed": [
            {
                "node_id": "invalid:node",
                "error": "Missing required fields: node_id, node_type, or label"
            }
        ],
        "total": 2
    },
    "message": "Bulk operation completed: 1 added, 0 updated, 1 failed"
}
```

## Benefits

1. **Performance**: All operations are executed in a single database transaction, significantly faster than individual calls
2. **Atomic**: All changes are committed together
3. **Fault-tolerant**: Individual failures don't prevent other items from being processed
4. **Efficient**: Reduces network overhead when adding many items

## Update Node

Use `update_node` to modify an existing node. Unlike `add_node` which creates or updates (upsert), `update_node` only works on existing nodes and returns an error if the node doesn't exist:

```python
# Update specific fields of an existing node
update_node(
    node_id="concept:python",
    content="Updated description of Python programming language...",
    properties={"importance": "critical", "version": "3.12"}
)
```

### Partial Updates

You only need to provide the fields you want to change - all other fields remain unchanged:

```python
# Update only the label
update_node(
    node_id="concept:python",
    label="Python 3.x Programming"
)

# Update only properties
update_node(
    node_id="concept:python",
    properties={"last_reviewed": "2024-11-13"}
)
```

### Response Format

Success:
```json
{
    "success": true,
    "result": {
        "id": "concept:python",
        "type": "Concept",
        "label": "Python 3.x Programming",
        "content": "Updated description...",
        "properties": {"last_reviewed": "2024-11-13"},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-11-13T10:30:00Z"
    },
    "message": "Successfully updated node 'concept:python'"
}
```

Error (node not found):
```json
{
    "success": false,
    "error": "Node concept:nonexistent not found"
}
```

### When to Use update_node vs add_node

- **Use `update_node`** when:
  - You want to ensure the node already exists
  - You're modifying an existing node and want an error if it doesn't exist
  - You want to do partial updates (only change specific fields)

- **Use `add_node`** when:
  - You want to create a new node or update if it exists (upsert behavior)
  - You're creating nodes and don't care if they already exist
  - You want to replace all fields of a node

## Choosing the Right Function

- **Use `append_graph`** when:
  - You have both nodes and edges to add together
  - You're importing a complete subgraph structure
  - You want the convenience of a single operation for everything

- **Use `bulk_add_nodes`** when:
  - You only need to add nodes without edges
  - You're doing a separate node creation phase

- **Use `bulk_add_edges`** when:
  - You only need to add edges between existing nodes
  - You're connecting previously created nodes

- **Use `update_node`** when:
  - You want to ensure the node already exists
  - You're modifying specific fields of an existing node
  - You want partial updates

- **Use `add_node`** when:
  - You're adding individual nodes
  - You want upsert behavior (create or update)

## Best Practices

1. **Prefer append_graph for subgraphs**: When adding related nodes and edges together, use `append_graph` for convenience and clarity
2. **Create nodes before edges**: When using separate bulk operations, always add nodes before edges
3. **Batch size**: For very large datasets, consider batching into groups of 100-1000 items
4. **Error checking**: Review the `failed` arrays in responses to handle any errors
5. **Update operations**: Bulk functions support upsert - existing items will be updated automatically
6. **Use update_node for safety**: When modifying existing nodes, prefer `update_node` to catch accidental typos in node IDs
7. **Structure validation**: Ensure your graph structure is valid before appending (no dangling edges, proper node references)

