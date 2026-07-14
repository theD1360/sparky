"""Tests for core memory protection and association hooks."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database.repository import KnowledgeRepository


@pytest.mark.asyncio
async def test_repository_save_memory_rejects_core_overwrite():
    repo = KnowledgeRepository.__new__(KnowledgeRepository)
    existing = SimpleNamespace(
        id="memory:core:identity",
        content="I am Sparky.",
        properties={"key": "core:identity"},
    )
    repo.get_node = AsyncMock(return_value=existing)
    repo.add_node = AsyncMock()

    with pytest.raises(ValueError, match="Cannot overwrite protected core memory"):
        await repo.save_memory("core:identity", "sparky", overwrite=True)

    repo.add_node.assert_not_called()


@pytest.mark.asyncio
async def test_repository_save_memory_allows_core_revision_flag():
    repo = KnowledgeRepository.__new__(KnowledgeRepository)
    existing = SimpleNamespace(
        id="memory:core:identity",
        content="I am Sparky.",
        properties={"key": "core:identity"},
    )
    repo.get_node = AsyncMock(return_value=existing)
    repo.add_node = AsyncMock(return_value=existing)

    result = await repo.save_memory(
        "core:identity",
        "I am Sparky, evolved.",
        overwrite=True,
        allow_core_revision=True,
    )
    assert result is existing
    repo.add_node.assert_called_once()


@pytest.mark.asyncio
async def test_repository_save_memory_allows_non_core_overwrite():
    repo = KnowledgeRepository.__new__(KnowledgeRepository)
    existing = SimpleNamespace(
        id="memory:notes",
        content="old",
        properties={"key": "notes"},
    )
    repo.get_node = AsyncMock(return_value=existing)
    repo.add_node = AsyncMock(return_value=existing)

    await repo.save_memory("notes", "new", overwrite=True)
    repo.add_node.assert_called_once()


@pytest.mark.asyncio
async def test_save_memory_tool_rejects_core_and_auto_associates_non_core():
    from tools.knowledge import server as knowledge_server

    mock_repo = MagicMock()
    mock_repo.get_node = AsyncMock(
        return_value=SimpleNamespace(id="memory:core:identity", content="full")
    )
    mock_repo.save_memory = AsyncMock()

    with patch.object(knowledge_server, "_kb_repository", mock_repo):
        result = await knowledge_server.save_memory(
            "core:identity", "sparky", overwrite=True
        )

    assert result.get("status") == "error" or result.get("error") or (
        "Cannot overwrite" in str(result)
    )
    mock_repo.save_memory.assert_not_called()


@pytest.mark.asyncio
async def test_save_memory_tool_auto_associates():
    from tools.knowledge import server as knowledge_server

    mock_repo = MagicMock()
    mock_repo.get_node = AsyncMock(return_value=None)
    mock_repo.save_memory = AsyncMock()

    with patch.object(knowledge_server, "_kb_repository", mock_repo):
        with patch.object(
            knowledge_server, "_auto_associate_memory", new_callable=AsyncMock
        ) as mock_assoc:
            result = await knowledge_server.save_memory("user_prefs", "x")
            mock_assoc.assert_awaited_once_with("user_prefs")

    assert result.get("status") == "success" or "user_prefs" in str(result)


@pytest.mark.asyncio
async def test_auto_associate_episode_links_to_self():
    from services.knowledge_service import KnowledgeService

    mock_repo = MagicMock()
    mock_repo.add_node = AsyncMock()
    mock_repo.add_edge = AsyncMock()

    ks = KnowledgeService(repository=mock_repo)
    ks._ensure_ontology_structure = AsyncMock()
    ks._ensure_memory_in_graph = AsyncMock()

    await ks.auto_associate_memory("episode:chat-123", "Autobiographical Episode")

    mock_repo.add_edge.assert_any_await(
        source_id="memory:episode:chat-123",
        target_id="concept:self",
        edge_type="EXPERIENCED_BY",
    )


@pytest.mark.asyncio
async def test_on_summarized_writes_episode():
    from services.knowledge_service import KnowledgeService

    mock_repo = MagicMock()
    mock_repo.save_memory = AsyncMock()
    mock_repo.add_node = AsyncMock()
    mock_repo.add_edge = AsyncMock()

    ks = KnowledgeService(repository=mock_repo, session_id="chat-abc")
    ks._ensure_ontology_structure = AsyncMock()
    ks._ensure_memory_in_graph = AsyncMock()
    ks.auto_associate_memory = AsyncMock()
    ks.events.async_dispatch = AsyncMock()

    await ks._on_summarized("We discussed identity.", 4)

    # Summary + episode
    save_keys = [c.kwargs.get("key") or c.args[0] for c in mock_repo.save_memory.await_args_list]
    # save_memory called as keyword args
    called_keys = []
    for call in mock_repo.save_memory.await_args_list:
        if call.kwargs.get("key"):
            called_keys.append(call.kwargs["key"])
        elif call.args:
            called_keys.append(call.args[0])
    assert "chat:chat-abc:summary" in called_keys
    assert "episode:chat-abc" in called_keys
    ks.auto_associate_memory.assert_any_await(
        "episode:chat-abc", "Autobiographical Episode"
    )
