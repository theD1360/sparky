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


def test_save_message_verifies_chat_node_exists(message_service, mock_repository):
    """Test that save_message verifies chat node exists before linking."""
    session_id = "test_session"
    content = "Hello, world!"
    role = "user"
    chat_id = "test_chat"
    
    # Mock chat node exists
    mock_chat_node = MagicMock()
    mock_repository.get_node.return_value = mock_chat_node
    mock_repository.get_chat_messages.return_value = []

    message_service.save_message(
        content=content, role=role, session_id=session_id, chat_id=chat_id
    )

    # Verify that get_node was called to check chat existence
    mock_repository.get_node.assert_called_with(f"chat:{chat_id}")


def test_save_message_warns_when_chat_node_missing(message_service, mock_repository):
    """Test that save_message logs warning when chat node doesn't exist."""
    session_id = "test_session"
    content = "Hello, world!"
    role = "user"
    chat_id = "test_chat"
    
    # Mock chat node does NOT exist
    mock_repository.get_node.return_value = None
    mock_repository.get_chat_messages.return_value = []

    # Should still succeed (message linked to session)
    result = message_service.save_message(
        content=content, role=role, session_id=session_id, chat_id=chat_id
    )

    # Message should still be created
    assert result is not None
    mock_repository.add_node.assert_called_once()
    
    # Should have created edge to session but not to chat
    session_edge_created = any(
        call_args[1].get("source_id") == session_id 
        for call_args in mock_repository.add_edge.call_args_list
    )
    assert session_edge_created


def test_get_recent_messages_uses_fallback(message_service, mock_repository):
    """Test that get_recent_messages uses session fallback."""
    chat_id = "test_chat"
    
    # Mock empty chat messages (will trigger fallback)
    mock_repository.get_chat_messages.return_value = []

    messages = message_service.get_recent_messages(chat_id=chat_id)

    # Verify fallback parameter was passed
    mock_repository.get_chat_messages.assert_called_once()
    call_kwargs = mock_repository.get_chat_messages.call_args[1]
    assert call_kwargs.get("use_session_fallback") == True


def test_format_for_summary_uses_fallback(message_service, mock_repository):
    """Test that format_for_summary uses session fallback."""
    chat_id = "test_chat"
    
    # Mock empty messages
    mock_repository.get_chat_messages.return_value = []

    result = message_service.format_for_summary(chat_id=chat_id)

    # Verify fallback parameter was passed
    mock_repository.get_chat_messages.assert_called_once()
    call_kwargs = mock_repository.get_chat_messages.call_args[1]
    assert call_kwargs.get("use_session_fallback") == True


def test_get_messages_within_token_limit_includes_all_messages(message_service, mock_repository):
    """Test that token limit method includes all messages via fallback."""
    from datetime import datetime, timezone
    from database.models import Node
    
    chat_id = "test_chat"
    
    # Create mock message nodes
    mock_messages = [
        Node(
            id=f"chat:session:1",
            node_type="ChatMessage",
            label="Message 1",
            content="Hello",
            properties={"role": "user", "message_type": "message"},
            created_at=datetime.now(timezone.utc)
        ),
        Node(
            id=f"chat:session:2",
            node_type="ChatMessage",
            label="Message 2",
            content="Hi there",
            properties={"role": "model", "message_type": "message"},
            created_at=datetime.now(timezone.utc)
        ),
    ]
    
    mock_repository.get_chat_messages.return_value = mock_messages

    messages = message_service.get_messages_within_token_limit(
        chat_id=chat_id, max_tokens=10000
    )

    # Verify messages were retrieved with fallback
    assert len(messages) == 2
    mock_repository.get_chat_messages.assert_called()
    call_kwargs = mock_repository.get_chat_messages.call_args[1]
    assert call_kwargs.get("use_session_fallback") == True
