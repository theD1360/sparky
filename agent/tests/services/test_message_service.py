# tests/test_message_service.py

import pytest
from unittest.mock import MagicMock, call

from services.message_service import MessageService

@pytest.fixture
def mock_repository():
    """Create a mock KnowledgeRepository."""
    return MagicMock()

@pytest.fixture
def message_service(mock_repository):
    """Create a MessageService instance with the mock repository."""
    return MessageService(repository=mock_repository)

def test_save_message_success(message_service, mock_repository):
    """Test saving a message successfully."""
    session_id = "test_session"
    content = "Hello, world!"
    role = "user"
    chat_id = "test_chat"

    message_service.save_message(
        content=content, role=role, session_id=session_id, chat_id=chat_id
    )

    mock_repository.add_node.assert_called_once()
    mock_repository.add_edge.assert_called()

    # Assert that add_node was called with the correct arguments
    args, kwargs = mock_repository.add_node.call_args
    assert kwargs["node_type"] == "ChatMessage"
    assert kwargs["label"].startswith("Chat Message")
    assert kwargs["content"] == content
    assert kwargs["properties"]["role"] == role
    assert kwargs["properties"]["internal"] == False

    # Assert that add_edge was called to link the message to the session and chat
    expected_calls = [
        call(source_id=session_id, target_id=kwargs["node_id"], edge_type="CONTAINS"),
        call(source_id=f"chat:{chat_id}", target_id=kwargs["node_id"], edge_type="CONTAINS")
    ]
    mock_repository.add_edge.assert_has_calls(expected_calls, any_order=True)



def test_save_message_no_session_id(message_service, mock_repository):
    """Test that save_message returns None when session_id is missing."""
    content = "Hello, world!"
    role = "user"

    result = message_service.save_message(content=content, role=role, session_id=None)

    assert result is None
    mock_repository.add_node.assert_not_called()
    mock_repository.add_edge.assert_not_called()
