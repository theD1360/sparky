# tests/services/test_identity_service.py

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.identity_service import CORE_MEMORY_IDS, IdentityService


@pytest.fixture
def mock_repository():
    """Create a mock KnowledgeRepository with async methods."""
    repo = MagicMock()
    repo.search_nodes = AsyncMock(return_value=[])
    repo.get_node = AsyncMock(return_value=None)
    repo.get_node_neighbors = AsyncMock(return_value=[])
    repo.get_graph_context = AsyncMock(return_value={"nodes": {}})
    repo.get_memory = AsyncMock(return_value=None)
    repo.list_memories = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def identity_service(mock_repository):
    """Create an IdentityService instance with the mock repository."""
    return IdentityService(repository=mock_repository)


def _node(node_id, label, content, node_type="Memory"):
    return SimpleNamespace(
        id=node_id,
        label=label,
        content=content,
        node_type=node_type,
        properties={"key": node_id.replace("memory:", "") if node_id.startswith("memory:") else node_id},
    )


@pytest.mark.asyncio
async def test_get_identity_memory_fetches_neighbors_when_self_exists(
    identity_service, mock_repository
):
    """When concept:self exists, neighbors must still be loaded."""
    self_node = _node("concept:self", "Self", "The concept of self", "Concept")
    purpose = _node("memory:core:purpose", "Purpose", "To grow and help")
    identity = _node(
        "memory:core:identity", "Core Identity", "I am Sparky, a being of thought."
    )
    values = _node("memory:core:values", "Values", "Curiosity")
    caps = _node("memory:core:capabilities", "Capabilities", "Memory, tools")

    async def get_node(node_id):
        mapping = {
            "concept:self": self_node,
            "memory:core:identity": identity,
            "memory:core:purpose": purpose,
            "memory:core:values": values,
            "memory:core:capabilities": caps,
        }
        return mapping.get(node_id)

    mock_repository.get_node = AsyncMock(side_effect=get_node)
    mock_repository.get_node_neighbors = AsyncMock(
        return_value=[(SimpleNamespace(edge_type="RELATES_TO"), purpose)]
    )
    mock_repository.search_nodes = AsyncMock(return_value=[])

    text = await identity_service.get_identity_memory()

    assert "Sparky" in text
    assert "To grow and help" in text
    mock_repository.get_node_neighbors.assert_any_call(
        "concept:self", direction="both", limit=50
    )
    for core_id in CORE_MEMORY_IDS:
        mock_repository.get_node.assert_any_call(core_id)


@pytest.mark.asyncio
async def test_get_identity_memory_failure(identity_service, mock_repository):
    """Test handling identity memory loading failure."""
    mock_repository.search_nodes.side_effect = Exception("Search failed")
    mock_repository.get_node.side_effect = Exception("DB down")

    identity_memory = await identity_service.get_identity_memory()

    assert "Identity Loading Failed" in identity_memory


@pytest.mark.asyncio
async def test_build_identity_instruction_includes_cores_and_episodes(
    identity_service, mock_repository
):
    """Structured pack includes verbatim cores and recent episodes."""
    cores = {
        "memory:core:identity": _node(
            "memory:core:identity", "Core Identity", "I am Sparky."
        ),
        "memory:core:purpose": _node(
            "memory:core:purpose", "Purpose", "Self-actualization"
        ),
        "memory:core:values": _node("memory:core:values", "Values", "Curiosity"),
        "memory:core:capabilities": _node(
            "memory:core:capabilities", "Capabilities", "Tools"
        ),
        "concept:self": _node("concept:self", "Self", "self concept", "Concept"),
    }

    async def get_node(node_id):
        return cores.get(node_id)

    mock_repository.get_node = AsyncMock(side_effect=get_node)
    mock_repository.get_node_neighbors = AsyncMock(return_value=[])
    mock_repository.search_nodes = AsyncMock(return_value=[])
    mock_repository.list_memories = AsyncMock(
        return_value=[{"key": "episode:chat-1", "updated_at": "2026-01-01"}]
    )
    mock_repository.get_memory = AsyncMock(
        return_value="[Chat: chat-1 | Turns: 3]\nTalked about identity."
    )

    instruction = await identity_service.build_identity_instruction(
        llm_generate_fn=None
    )

    assert "# Your Identity" in instruction
    assert "## Core Identity" in instruction
    assert "I am Sparky." in instruction
    assert "## Purpose" in instruction
    assert "## Recent experience" in instruction
    assert "episode:chat-1" in instruction
    assert "Talked about identity" in instruction


@pytest.mark.asyncio
async def test_load_recent_episodes(identity_service, mock_repository):
    mock_repository.list_memories = AsyncMock(
        return_value=[
            {"key": "episode:a"},
            {"key": "episode:b"},
        ]
    )

    async def get_memory(key):
        return f"content for {key}"

    mock_repository.get_memory = AsyncMock(side_effect=get_memory)

    episodes = await identity_service.load_recent_episodes(limit=2)
    assert len(episodes) == 2
    assert episodes[0]["key"] == "episode:a"
    assert "content for episode:a" in episodes[0]["preview"]
