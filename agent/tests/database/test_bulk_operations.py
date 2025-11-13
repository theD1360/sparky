"""Tests for bulk add operations."""

import pytest
from src.database.repository import KnowledgeRepository


@pytest.fixture
def repository(db_manager):
    """Create a repository instance with test database."""
    repo = KnowledgeRepository(db_manager)
    from src.database.embeddings import EmbeddingManager
    EmbeddingManager.get_instance()
    return repo


def test_bulk_add_nodes_success(repository):
    """Test successful bulk addition of nodes."""
    nodes = [
        {
            "node_id": "test:bulk_node1",
            "node_type": "Test",
            "label": "Bulk Test Node 1",
            "content": "This is test node 1",
            "properties": {"test": "bulk1"}
        },
        {
            "node_id": "test:bulk_node2",
            "node_type": "Test",
            "label": "Bulk Test Node 2",
            "content": "This is test node 2",
            "properties": {"test": "bulk2"}
        },
        {
            "node_id": "test:bulk_node3",
            "node_type": "Test",
            "label": "Bulk Test Node 3",
            "content": "This is test node 3",
            "properties": {"test": "bulk3"}
        }
    ]
    
    result = repository.bulk_add_nodes(nodes)
    
    assert result["total"] == 3
    assert len(result["added"]) == 3
    assert len(result["updated"]) == 0
    assert len(result["failed"]) == 0
    
    # Verify nodes were actually created
    for node_data in nodes:
        node = repository.get_node(node_data["node_id"])
        assert node is not None
        assert node.label == node_data["label"]
        assert node.content == node_data["content"]


def test_bulk_add_nodes_update(repository):
    """Test that bulk_add_nodes updates existing nodes."""
    # Create initial nodes
    initial_nodes = [
        {
            "node_id": "test:update1",
            "node_type": "Test",
            "label": "Initial Label 1",
            "content": "Initial content 1"
        },
        {
            "node_id": "test:update2",
            "node_type": "Test",
            "label": "Initial Label 2",
            "content": "Initial content 2"
        }
    ]
    
    repository.bulk_add_nodes(initial_nodes)
    
    # Update the same nodes
    updated_nodes = [
        {
            "node_id": "test:update1",
            "node_type": "Test",
            "label": "Updated Label 1",
            "content": "Updated content 1"
        },
        {
            "node_id": "test:update2",
            "node_type": "Test",
            "label": "Updated Label 2",
            "content": "Updated content 2"
        }
    ]
    
    result = repository.bulk_add_nodes(updated_nodes)
    
    assert result["total"] == 2
    assert len(result["added"]) == 0
    assert len(result["updated"]) == 2
    assert len(result["failed"]) == 0
    
    # Verify nodes were updated
    node1 = repository.get_node("test:update1")
    assert node1.label == "Updated Label 1"
    assert node1.content == "Updated content 1"


def test_bulk_add_nodes_missing_fields(repository):
    """Test that bulk_add_nodes handles missing required fields."""
    nodes = [
        {
            "node_id": "test:valid",
            "node_type": "Test",
            "label": "Valid Node"
        },
        {
            "node_id": "test:missing_type",
            # Missing node_type
            "label": "Missing Type"
        },
        {
            "node_id": "test:missing_label",
            "node_type": "Test"
            # Missing label
        }
    ]
    
    result = repository.bulk_add_nodes(nodes)
    
    assert result["total"] == 3
    assert len(result["added"]) == 1
    assert len(result["updated"]) == 0
    assert len(result["failed"]) == 2
    
    # Verify valid node was created
    valid_node = repository.get_node("test:valid")
    assert valid_node is not None


def test_bulk_add_edges_success(repository):
    """Test successful bulk addition of edges."""
    # First create nodes
    nodes = [
        {
            "node_id": "test:edge_node1",
            "node_type": "Test",
            "label": "Node 1"
        },
        {
            "node_id": "test:edge_node2",
            "node_type": "Test",
            "label": "Node 2"
        },
        {
            "node_id": "test:edge_node3",
            "node_type": "Test",
            "label": "Node 3"
        }
    ]
    repository.bulk_add_nodes(nodes)
    
    # Add edges
    edges = [
        {
            "source_id": "test:edge_node1",
            "target_id": "test:edge_node2",
            "edge_type": "RELATES_TO",
            "properties": {"strength": 0.8}
        },
        {
            "source_id": "test:edge_node2",
            "target_id": "test:edge_node3",
            "edge_type": "RELATES_TO",
            "properties": {"strength": 0.9}
        },
        {
            "source_id": "test:edge_node1",
            "target_id": "test:edge_node3",
            "edge_type": "DEPENDS_ON"
        }
    ]
    
    result = repository.bulk_add_edges(edges)
    
    assert result["total"] == 3
    assert len(result["added"]) == 3
    assert len(result["updated"]) == 0
    assert len(result["failed"]) == 0


def test_bulk_add_edges_update(repository):
    """Test that bulk_add_edges updates existing edges."""
    # Create nodes
    nodes = [
        {"node_id": "test:edge_update1", "node_type": "Test", "label": "Node 1"},
        {"node_id": "test:edge_update2", "node_type": "Test", "label": "Node 2"}
    ]
    repository.bulk_add_nodes(nodes)
    
    # Create initial edge
    initial_edges = [
        {
            "source_id": "test:edge_update1",
            "target_id": "test:edge_update2",
            "edge_type": "RELATES_TO",
            "properties": {"value": 1}
        }
    ]
    repository.bulk_add_edges(initial_edges)
    
    # Update the same edge
    updated_edges = [
        {
            "source_id": "test:edge_update1",
            "target_id": "test:edge_update2",
            "edge_type": "RELATES_TO",
            "properties": {"value": 2}
        }
    ]
    
    result = repository.bulk_add_edges(updated_edges)
    
    assert result["total"] == 1
    assert len(result["added"]) == 0
    assert len(result["updated"]) == 1
    assert len(result["failed"]) == 0


def test_bulk_add_edges_missing_nodes(repository):
    """Test that bulk_add_edges handles missing nodes."""
    # Create only one node
    repository.add_node("test:exists", "Test", "Existing Node")
    
    edges = [
        {
            "source_id": "test:exists",
            "target_id": "test:nonexistent",
            "edge_type": "RELATES_TO"
        },
        {
            "source_id": "test:nonexistent1",
            "target_id": "test:nonexistent2",
            "edge_type": "RELATES_TO"
        }
    ]
    
    result = repository.bulk_add_edges(edges)
    
    assert result["total"] == 2
    assert len(result["added"]) == 0
    assert len(result["updated"]) == 0
    assert len(result["failed"]) == 2
    
    # Verify error messages mention missing nodes
    for failure in result["failed"]:
        assert "not found" in failure["error"]


def test_bulk_add_edges_missing_fields(repository):
    """Test that bulk_add_edges handles missing required fields."""
    # Create nodes
    repository.add_node("test:field_test1", "Test", "Node 1")
    repository.add_node("test:field_test2", "Test", "Node 2")
    
    edges = [
        {
            "source_id": "test:field_test1",
            "target_id": "test:field_test2",
            "edge_type": "RELATES_TO"
        },
        {
            "source_id": "test:field_test1",
            # Missing target_id
            "edge_type": "RELATES_TO"
        },
        {
            "source_id": "test:field_test1",
            "target_id": "test:field_test2"
            # Missing edge_type
        }
    ]
    
    result = repository.bulk_add_edges(edges)
    
    assert result["total"] == 3
    assert len(result["added"]) == 1
    assert len(result["updated"]) == 0
    assert len(result["failed"]) == 2


def test_bulk_add_mixed_success_and_failure(repository):
    """Test bulk operations with mix of successes and failures."""
    nodes = [
        {
            "node_id": "test:mixed1",
            "node_type": "Test",
            "label": "Valid Node 1"
        },
        {
            "node_id": "test:mixed2",
            # Missing node_type (will fail)
            "label": "Invalid Node"
        },
        {
            "node_id": "test:mixed3",
            "node_type": "Test",
            "label": "Valid Node 3"
        }
    ]
    
    result = repository.bulk_add_nodes(nodes)
    
    assert result["total"] == 3
    assert len(result["added"]) == 2
    assert len(result["failed"]) == 1
    
    # Verify valid nodes were created
    assert repository.get_node("test:mixed1") is not None
    assert repository.get_node("test:mixed3") is not None
    assert repository.get_node("test:mixed2") is None


def test_bulk_operations_empty_list(repository):
    """Test bulk operations with empty lists."""
    result = repository.bulk_add_nodes([])
    assert result["total"] == 0
    assert len(result["added"]) == 0
    assert len(result["failed"]) == 0
    
    result = repository.bulk_add_edges([])
    assert result["total"] == 0
    assert len(result["added"]) == 0
    assert len(result["failed"]) == 0


# ============================================================================
# UPDATE_NODE TESTS
# ============================================================================


def test_update_node_success(repository):
    """Test successful node update."""
    # Create a node
    repository.add_node(
        "test:update_test",
        "Test",
        "Original Label",
        "Original content",
        {"key": "value"}
    )
    
    # Update the node
    updated = repository.update_node(
        "test:update_test",
        label="Updated Label",
        content="Updated content"
    )
    
    assert updated.id == "test:update_test"
    assert updated.label == "Updated Label"
    assert updated.content == "Updated content"
    assert updated.properties == {"key": "value"}  # Properties unchanged


def test_update_node_partial_update(repository):
    """Test that update_node only changes provided fields."""
    # Create a node
    repository.add_node(
        "test:partial_update",
        "Test",
        "Original Label",
        "Original content",
        {"original": "data"}
    )
    
    # Update only content
    updated = repository.update_node(
        "test:partial_update",
        content="New content only"
    )
    
    assert updated.label == "Original Label"  # Unchanged
    assert updated.content == "New content only"  # Changed
    assert updated.properties == {"original": "data"}  # Unchanged


def test_update_node_all_fields(repository):
    """Test updating all fields at once."""
    # Create a node
    repository.add_node(
        "test:update_all",
        "Test",
        "Original",
        "Original content"
    )
    
    # Update all fields
    updated = repository.update_node(
        "test:update_all",
        node_type="UpdatedType",
        label="Updated Label",
        content="Updated content",
        properties={"new": "properties"}
    )
    
    assert updated.node_type == "UpdatedType"
    assert updated.label == "Updated Label"
    assert updated.content == "Updated content"
    assert updated.properties == {"new": "properties"}


def test_update_node_nonexistent(repository):
    """Test that update_node raises error for nonexistent node."""
    with pytest.raises(ValueError, match="not found"):
        repository.update_node("test:nonexistent", label="Should fail")


def test_update_node_properties_replacement(repository):
    """Test that properties are replaced, not merged."""
    # Create node with properties
    repository.add_node(
        "test:props_replace",
        "Test",
        "Label",
        properties={"key1": "value1", "key2": "value2"}
    )
    
    # Update with new properties
    updated = repository.update_node(
        "test:props_replace",
        properties={"key3": "value3"}
    )
    
    # Old properties should be replaced, not merged
    assert updated.properties == {"key3": "value3"}
    assert "key1" not in updated.properties
    assert "key2" not in updated.properties


def test_update_node_preserves_timestamps(repository):
    """Test that update_node updates the updated_at timestamp."""
    import time
    
    # Create node
    node = repository.add_node(
        "test:timestamps",
        "Test",
        "Original"
    )
    original_created = node.created_at
    original_updated = node.updated_at
    
    # Wait a bit to ensure timestamp difference
    time.sleep(0.1)
    
    # Update node
    updated = repository.update_node(
        "test:timestamps",
        label="Updated"
    )
    
    # created_at should be unchanged, updated_at should be newer
    assert updated.created_at == original_created
    assert updated.updated_at > original_updated


# ============================================================================
# APPEND_GRAPH TESTS
# ============================================================================


def test_append_graph_success(repository):
    """Test successful appending of a complete subgraph."""
    nodes = [
        {
            "node_id": "concept:animals",
            "node_type": "Concept",
            "label": "Animals",
            "content": "Living organisms"
        },
        {
            "node_id": "concept:mammals",
            "node_type": "Concept",
            "label": "Mammals",
            "content": "Warm-blooded animals"
        },
        {
            "node_id": "concept:dogs",
            "node_type": "Concept",
            "label": "Dogs",
            "content": "Domesticated mammals"
        }
    ]
    
    edges = [
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
    
    result = repository.append_graph(nodes, edges)
    
    # Check nodes were added
    assert result["total_nodes"] == 3
    assert len(result["nodes_added"]) == 3
    assert len(result["nodes_updated"]) == 0
    assert len(result["nodes_failed"]) == 0
    
    # Check edges were added
    assert result["total_edges"] == 2
    assert len(result["edges_added"]) == 2
    assert len(result["edges_updated"]) == 0
    assert len(result["edges_failed"]) == 0
    
    # Verify the graph structure
    animals = repository.get_node("concept:animals")
    mammals = repository.get_node("concept:mammals")
    dogs = repository.get_node("concept:dogs")
    
    assert animals is not None
    assert mammals is not None
    assert dogs is not None


def test_append_graph_with_existing_nodes(repository):
    """Test appending a graph when some nodes already exist."""
    # Create one node first
    repository.add_node(
        "concept:existing",
        "Concept",
        "Existing Concept",
        "Already in graph"
    )
    
    nodes = [
        {
            "node_id": "concept:existing",
            "node_type": "Concept",
            "label": "Updated Existing Concept",
            "content": "Updated content"
        },
        {
            "node_id": "concept:new",
            "node_type": "Concept",
            "label": "New Concept"
        }
    ]
    
    edges = [
        {
            "source_id": "concept:new",
            "target_id": "concept:existing",
            "edge_type": "RELATES_TO"
        }
    ]
    
    result = repository.append_graph(nodes, edges)
    
    # One node should be updated, one added
    assert len(result["nodes_added"]) == 1
    assert len(result["nodes_updated"]) == 1
    assert len(result["edges_added"]) == 1
    
    # Verify the existing node was updated
    existing = repository.get_node("concept:existing")
    assert existing.label == "Updated Existing Concept"


def test_append_graph_empty(repository):
    """Test appending an empty graph."""
    result = repository.append_graph([], [])
    
    assert result["total_nodes"] == 0
    assert result["total_edges"] == 0
    assert len(result["nodes_added"]) == 0
    assert len(result["edges_added"]) == 0


def test_append_graph_nodes_only(repository):
    """Test appending nodes without edges."""
    nodes = [
        {
            "node_id": "test:node1",
            "node_type": "Test",
            "label": "Node 1"
        },
        {
            "node_id": "test:node2",
            "node_type": "Test",
            "label": "Node 2"
        }
    ]
    
    result = repository.append_graph(nodes, [])
    
    assert result["total_nodes"] == 2
    assert result["total_edges"] == 0
    assert len(result["nodes_added"]) == 2
    assert len(result["edges_added"]) == 0


def test_append_graph_with_failures(repository):
    """Test appending a graph with some invalid data."""
    # Create valid nodes to connect to
    repository.add_node("concept:valid", "Concept", "Valid Node")
    
    nodes = [
        {
            "node_id": "test:valid_new",
            "node_type": "Test",
            "label": "Valid"
        },
        {
            "node_id": "test:invalid",
            # Missing required fields
            "content": "Invalid node"
        }
    ]
    
    edges = [
        {
            "source_id": "test:valid_new",
            "target_id": "concept:valid",
            "edge_type": "RELATES_TO"
        },
        {
            "source_id": "test:nonexistent",
            "target_id": "concept:valid",
            "edge_type": "RELATES_TO"
        }
    ]
    
    result = repository.append_graph(nodes, edges)
    
    # One node should succeed, one should fail
    assert len(result["nodes_added"]) == 1
    assert len(result["nodes_failed"]) == 1
    
    # One edge should succeed, one should fail
    assert len(result["edges_added"]) == 1
    assert len(result["edges_failed"]) == 1


def test_append_graph_complex_structure(repository):
    """Test appending a more complex graph structure."""
    # Create a small taxonomy
    nodes = [
        {"node_id": "tax:root", "node_type": "Taxonomy", "label": "Root"},
        {"node_id": "tax:level1_a", "node_type": "Taxonomy", "label": "Level 1-A"},
        {"node_id": "tax:level1_b", "node_type": "Taxonomy", "label": "Level 1-B"},
        {"node_id": "tax:level2_a1", "node_type": "Taxonomy", "label": "Level 2-A1"},
        {"node_id": "tax:level2_a2", "node_type": "Taxonomy", "label": "Level 2-A2"},
    ]
    
    edges = [
        {"source_id": "tax:level1_a", "target_id": "tax:root", "edge_type": "CHILD_OF"},
        {"source_id": "tax:level1_b", "target_id": "tax:root", "edge_type": "CHILD_OF"},
        {"source_id": "tax:level2_a1", "target_id": "tax:level1_a", "edge_type": "CHILD_OF"},
        {"source_id": "tax:level2_a2", "target_id": "tax:level1_a", "edge_type": "CHILD_OF"},
    ]
    
    result = repository.append_graph(nodes, edges)
    
    assert result["total_nodes"] == 5
    assert result["total_edges"] == 4
    assert len(result["nodes_added"]) == 5
    assert len(result["edges_added"]) == 4
    assert len(result["nodes_failed"]) == 0
    assert len(result["edges_failed"]) == 0
    
    # Verify structure by checking one path
    level2_a1 = repository.get_node("tax:level2_a1")
    assert level2_a1 is not None

