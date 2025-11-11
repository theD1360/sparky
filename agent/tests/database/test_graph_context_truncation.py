"""Tests for get_graph_context content truncation feature."""

import pytest
from src.database.repository import KnowledgeRepository


@pytest.fixture
def repository(db_manager):
    """Create a repository instance with test database."""
    repo = KnowledgeRepository(db_manager)
    from src.database.embeddings import EmbeddingManager
    EmbeddingManager.get_instance()
    return repo


@pytest.fixture
def sample_nodes(repository):
    """Create sample nodes with varying content lengths."""
    # Create nodes with different content sizes
    node1 = repository.add_node(
        node_id="test:short",
        node_type="Concept",
        label="Short Content",
        content="This is short content.",
    )
    
    node2 = repository.add_node(
        node_id="test:long",
        node_type="Concept",
        label="Long Content",
        content="A" * 2000,  # 2000 character content
    )
    
    node3 = repository.add_node(
        node_id="test:medium",
        node_type="Concept",
        label="Medium Content",
        content="B" * 500,  # 500 character content
    )
    
    # Create connections
    repository.add_edge(
        source_id="test:short",
        target_id="test:long",
        edge_type="RELATES_TO",
    )
    
    repository.add_edge(
        source_id="test:short",
        target_id="test:medium",
        edge_type="RELATES_TO",
    )
    
    return node1, node2, node3


def test_default_truncation(repository, sample_nodes):
    """Test that default truncation limits content to 1000 characters."""
    node1, node2, node3 = sample_nodes
    
    # Get context with default parameters (should truncate at 1000)
    context = repository.get_graph_context("test:short", depth=1)
    
    assert context is not None
    assert "nodes" in context
    
    # Check that long content is truncated
    long_node = context["nodes"]["test:long"]
    assert len(long_node["content"]) == 1003  # 1000 + "..."
    assert long_node["content"].endswith("...")
    assert long_node["content_truncated"] is True
    assert long_node["content_full_length"] == 2000
    
    # Check that short content is not truncated
    short_node = context["nodes"]["test:short"]
    assert len(short_node["content"]) < 1000
    assert "content_truncated" not in short_node
    
    # Check that medium content is not truncated
    medium_node = context["nodes"]["test:medium"]
    assert len(medium_node["content"]) == 500
    assert "content_truncated" not in medium_node


def test_no_truncation(repository, sample_nodes):
    """Test that passing max_content_length=None disables truncation."""
    node1, node2, node3 = sample_nodes
    
    # Get context without truncation
    context = repository.get_graph_context(
        "test:short", depth=1, max_content_length=None
    )
    
    assert context is not None
    assert "nodes" in context
    
    # Check that long content is NOT truncated
    long_node = context["nodes"]["test:long"]
    assert len(long_node["content"]) == 2000
    assert not long_node["content"].endswith("...")
    assert "content_truncated" not in long_node


def test_custom_truncation_length(repository, sample_nodes):
    """Test that custom truncation length works."""
    node1, node2, node3 = sample_nodes
    
    # Get context with custom truncation at 300 chars
    context = repository.get_graph_context(
        "test:short", depth=1, max_content_length=300
    )
    
    assert context is not None
    assert "nodes" in context
    
    # Check that medium content is now truncated
    medium_node = context["nodes"]["test:medium"]
    assert len(medium_node["content"]) == 303  # 300 + "..."
    assert medium_node["content"].endswith("...")
    assert medium_node["content_truncated"] is True
    assert medium_node["content_full_length"] == 500


def test_exclude_content(repository, sample_nodes):
    """Test that include_content=False excludes all content."""
    node1, node2, node3 = sample_nodes
    
    # Get context without any content
    context = repository.get_graph_context(
        "test:short", depth=1, include_content=False
    )
    
    assert context is not None
    assert "nodes" in context
    
    # Check that all content is None
    for node_data in context["nodes"].values():
        assert node_data["content"] is None


def test_truncation_with_depth_2(repository, sample_nodes):
    """Test that truncation works correctly with depth=2."""
    node1, node2, node3 = sample_nodes
    
    # Add another layer
    node4 = repository.add_node(
        node_id="test:verylong",
        node_type="Concept",
        label="Very Long Content",
        content="C" * 5000,  # 5000 character content
    )
    repository.add_edge(
        source_id="test:long",
        target_id="test:verylong",
        edge_type="RELATES_TO",
    )
    
    # Get context with depth=2 and default truncation
    context = repository.get_graph_context("test:short", depth=2)
    
    assert context is not None
    assert "nodes" in context
    assert len(context["nodes"]) == 4  # All 4 nodes should be included
    
    # Check that very long content is truncated
    verylong_node = context["nodes"]["test:verylong"]
    assert len(verylong_node["content"]) == 1003  # 1000 + "..."
    assert verylong_node["content_truncated"] is True
    assert verylong_node["content_full_length"] == 5000


def test_truncation_preserves_metadata(repository, sample_nodes):
    """Test that truncation preserves all node metadata."""
    node1, node2, node3 = sample_nodes
    
    context = repository.get_graph_context("test:short", depth=1)
    
    # Check that all expected fields are present
    long_node = context["nodes"]["test:long"]
    assert long_node["id"] == "test:long"
    assert long_node["type"] == "Concept"
    assert long_node["label"] == "Long Content"
    assert "properties" in long_node
    assert "created_at" in long_node
    assert "updated_at" in long_node


# ============================================================================
# PAGINATION TESTS
# ============================================================================


@pytest.fixture
def densely_connected_graph(repository):
    """Create a densely connected graph for pagination testing."""
    # Create a central node
    central = repository.add_node(
        node_id="test:central",
        node_type="Concept",
        label="Central Node",
        content="Central hub",
    )
    
    # Create 20 first-level nodes
    first_level_nodes = []
    for i in range(20):
        node = repository.add_node(
            node_id=f"test:level1_{i}",
            node_type="Concept",
            label=f"Level 1 Node {i}",
            content=f"First level node {i}",
        )
        first_level_nodes.append(node)
        repository.add_edge(
            source_id="test:central",
            target_id=f"test:level1_{i}",
            edge_type="CONNECTS_TO",
        )
    
    # Create 30 second-level nodes connected to first-level nodes
    for i in range(30):
        node = repository.add_node(
            node_id=f"test:level2_{i}",
            node_type="Concept",
            label=f"Level 2 Node {i}",
            content=f"Second level node {i}",
        )
        # Connect each level2 node to 2 level1 nodes
        repository.add_edge(
            source_id=f"test:level1_{i % 20}",
            target_id=f"test:level2_{i}",
            edge_type="CONNECTS_TO",
        )
        if i > 0:
            repository.add_edge(
                source_id=f"test:level1_{(i - 1) % 20}",
                target_id=f"test:level2_{i}",
                edge_type="CONNECTS_TO",
            )
    
    return central


def test_node_limit_enforcement(repository, densely_connected_graph):
    """Test that max_nodes limit is enforced."""
    # Request with a small node limit
    context = repository.get_graph_context(
        "test:central", depth=2, max_nodes=10, include_content=False
    )
    
    assert context is not None
    assert context["truncated"] is True
    assert context["nodes_returned"] == 10
    assert len(context["nodes"]) == 10


def test_edge_limit_enforcement(repository, densely_connected_graph):
    """Test that max_edges limit is enforced."""
    # Request with a small edge limit
    context = repository.get_graph_context(
        "test:central", depth=2, max_edges=15, include_content=False
    )
    
    assert context is not None
    assert context["truncated"] is True
    assert context["edges_returned"] == 15
    assert len(context["edges"]) == 15


def test_no_limits(repository, densely_connected_graph):
    """Test that setting limits to None returns all data."""
    context = repository.get_graph_context(
        "test:central", depth=1, max_nodes=None, max_edges=None, include_content=False
    )
    
    assert context is not None
    # Should have central + 20 level1 nodes = 21 nodes
    assert len(context["nodes"]) == 21
    # Should have 20 edges connecting central to level1
    assert len(context["edges"]) == 20
    # Should not be truncated if all nodes fit
    assert context["truncated"] is False


def test_truncation_metadata(repository, densely_connected_graph):
    """Test that truncation metadata is accurate."""
    context = repository.get_graph_context(
        "test:central", depth=2, max_nodes=15, max_edges=25, include_content=False
    )
    
    assert context is not None
    assert "truncated" in context
    assert "nodes_returned" in context
    assert "edges_returned" in context
    assert "max_depth_reached" in context
    
    # Check counts are accurate
    assert context["nodes_returned"] == len(context["nodes"])
    assert context["edges_returned"] == len(context["edges"])
    
    # Should be truncated due to node limit
    assert context["truncated"] is True


def test_depth_reached_with_limits(repository, densely_connected_graph):
    """Test that max_depth_reached is accurate when hitting limits."""
    # Very small limit should stop at depth 1
    context = repository.get_graph_context(
        "test:central", depth=2, max_nodes=5, include_content=False
    )
    
    assert context is not None
    assert context["max_depth_reached"] >= 1
    # Since we hit the node limit, we stopped early
    assert context["truncated"] is True


def test_pagination_with_depth_1(repository, densely_connected_graph):
    """Test pagination works correctly with depth=1."""
    context = repository.get_graph_context(
        "test:central", depth=1, max_nodes=10, include_content=False
    )
    
    assert context is not None
    # Should have at most 10 nodes (central + 9 neighbors)
    assert len(context["nodes"]) == 10
    assert context["truncated"] is True


def test_default_limits(repository, densely_connected_graph):
    """Test that default limits (50 nodes, 100 edges) are applied."""
    context = repository.get_graph_context(
        "test:central", depth=2, include_content=False
    )
    
    assert context is not None
    # Should respect default limit of 50 nodes
    assert len(context["nodes"]) <= 50
    # Should respect default limit of 100 edges
    assert len(context["edges"]) <= 100
    
    # Graph has 51 nodes total, so should be truncated
    assert context["truncated"] is True


def test_pagination_preserves_structure(repository, densely_connected_graph):
    """Test that pagination doesn't return edges to non-existent nodes."""
    context = repository.get_graph_context(
        "test:central", depth=2, max_nodes=15, include_content=False
    )
    
    assert context is not None
    node_ids = set(context["nodes"].keys())
    
    # All edges should connect nodes that are in the result set
    for edge in context["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids

