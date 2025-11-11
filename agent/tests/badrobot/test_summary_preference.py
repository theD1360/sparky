"""Tests for summary preference in chat history loading."""

from unittest.mock import MagicMock, Mock

import pytest

from sparky.agent_orchestrator import AgentOrchestrator
from sparky.providers import GeminiProvider, ProviderConfig
from database.models import Node


class TestSummaryPreference:
    """Test that summaries are preferred over full chat history."""

    def test_get_recent_messages_prefers_summary(self):
        """Test that _get_recent_messages includes only messages after the most recent summary."""
        # Setup
        config = ProviderConfig(model_name="gemini-1.5-pro")
        provider = GeminiProvider(config)
        orchestrator = AgentOrchestrator(provider=provider)

        # Mock knowledge and repository
        orchestrator.knowledge = Mock()
        orchestrator.knowledge.repository = Mock()
        orchestrator._chat_id = "test-chat-id"

        # Create mock nodes representing a chat history with a summary
        nodes = [
            # Old messages (should be excluded)
            Mock(
                id="msg1",
                node_type="ChatMessage",
                content="Old message 1",
                properties={"role": "user", "message_type": "message"},
            ),
            Mock(
                id="msg2",
                node_type="ChatMessage",
                content="Old message 2",
                properties={"role": "model", "message_type": "message"},
            ),
            # Summary (should be included)
            Mock(
                id="summary1",
                node_type="ChatMessage",
                content="Summary of previous conversation",
                properties={"role": "user", "message_type": "summary"},
            ),
            # Recent messages (should be included)
            Mock(
                id="msg3",
                node_type="ChatMessage",
                content="New message 1",
                properties={"role": "user", "message_type": "message"},
            ),
            Mock(
                id="msg4",
                node_type="ChatMessage",
                content="New message 2",
                properties={"role": "model", "message_type": "message"},
            ),
        ]

        orchestrator.knowledge.repository.get_chat_messages.return_value = nodes

        # Execute
        messages = orchestrator._get_recent_messages()

        # Verify
        # Should return 3 messages: summary + 2 recent messages
        assert len(messages) == 3, f"Expected 3 messages, got {len(messages)}"

        # Verify the messages are the summary and the ones after it
        assert messages[0]["parts"][0] == "Summary of previous conversation"
        assert messages[1]["parts"][0] == "New message 1"
        assert messages[2]["parts"][0] == "New message 2"

    def test_get_recent_messages_without_summary(self):
        """Test that without a summary, only the last N messages are included."""
        # Setup
        config = ProviderConfig(model_name="gemini-1.5-pro")
        provider = GeminiProvider(config)
        orchestrator = AgentOrchestrator(provider=provider)
        orchestrator.max_history_turns = 2  # Limit to 2 turns = 4 messages

        # Mock knowledge and repository
        orchestrator.knowledge = Mock()
        orchestrator.knowledge.repository = Mock()
        orchestrator._chat_id = "test-chat-id"

        # Create mock nodes with many messages but no summary
        nodes = [
            Mock(
                id=f"msg{i}",
                node_type="ChatMessage",
                content=f"Message {i}",
                properties={
                    "role": "user" if i % 2 == 0 else "model",
                    "message_type": "message",
                },
            )
            for i in range(10)
        ]

        orchestrator.knowledge.repository.get_chat_messages.return_value = nodes

        # Execute
        messages = orchestrator._get_recent_messages()

        # Verify - should only get last 4 messages (2 turns * 2 messages)
        assert len(messages) == 4, f"Expected 4 messages, got {len(messages)}"
        assert messages[0]["parts"][0] == "Message 6"
        assert messages[-1]["parts"][0] == "Message 9"

    def test_format_history_for_summary_excludes_old_summaries(self):
        """Test that _format_history_for_summary only includes messages since last summary."""
        # Setup
        config = ProviderConfig(model_name="gemini-1.5-pro")
        provider = GeminiProvider(config)
        orchestrator = AgentOrchestrator(provider=provider)

        # Mock knowledge and repository
        orchestrator.knowledge = Mock()
        orchestrator.knowledge.repository = Mock()
        orchestrator._chat_id = "test-chat-id"

        # Create mock nodes
        nodes = [
            Mock(
                id="old_msg",
                node_type="ChatMessage",
                content="Old message",
                properties={"role": "user", "message_type": "message"},
            ),
            Mock(
                id="summary1",
                node_type="ChatMessage",
                content="Previous summary",
                properties={"role": "user", "message_type": "summary"},
            ),
            Mock(
                id="new_msg1",
                node_type="ChatMessage",
                content="New message 1",
                properties={"role": "user", "message_type": "message"},
            ),
            Mock(
                id="new_msg2",
                node_type="ChatMessage",
                content="New message 2",
                properties={"role": "model", "message_type": "message"},
            ),
        ]

        orchestrator.knowledge.repository.get_chat_messages.return_value = nodes

        # Execute
        formatted = orchestrator._format_history_for_summary()

        # Verify - should only include messages after the summary
        assert "Old message" not in formatted
        assert "Previous summary" not in formatted
        assert "New message 1" in formatted
        assert "New message 2" in formatted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

