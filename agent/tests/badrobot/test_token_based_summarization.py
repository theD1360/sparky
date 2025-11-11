"""Tests for token-based conversation summarization."""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

from sparky.providers import GeminiProvider, ProviderConfig
from sparky.agent_orchestrator import AgentOrchestrator


class TestTokenBasedSummarizationConfig:
    """Tests for token-based summarization configuration."""

    @patch.dict(os.environ, {}, clear=True)
    def test_default_summary_token_threshold(self):
        """Test that default summary token threshold is 0.85."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                assert orchestrator.summary_token_threshold == 0.85

    @patch.dict(os.environ, {"SPARKY_SUMMARY_TOKEN_THRESHOLD": "0.75"})
    def test_custom_summary_token_threshold(self):
        """Test setting custom summary token threshold via env var."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                assert orchestrator.summary_token_threshold == 0.75

    @patch.dict(os.environ, {"SPARKY_SUMMARY_TOKEN_THRESHOLD": "0.3"})
    def test_summary_threshold_clamped_to_min(self):
        """Test that summary threshold is clamped to minimum 0.5."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                assert orchestrator.summary_token_threshold == 0.5

    @patch.dict(os.environ, {"SPARKY_SUMMARY_TOKEN_THRESHOLD": "1.2"})
    def test_summary_threshold_clamped_to_max(self):
        """Test that summary threshold is clamped to maximum 0.95."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                assert orchestrator.summary_token_threshold == 0.95

    @patch.dict(os.environ, {"SPARKY_SUMMARY_TOKEN_THRESHOLD": "invalid"})
    def test_invalid_summary_threshold_uses_default(self):
        """Test that invalid env value falls back to default."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                assert orchestrator.summary_token_threshold == 0.85


class TestShouldSummarize:
    """Tests for _should_summarize() method."""

    @patch.dict(os.environ, {}, clear=True)
    def test_should_summarize_no_message_service(self):
        """Test that _should_summarize returns False when message_service is None."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # No message service set
                assert orchestrator._should_summarize() is False

    @patch.dict(os.environ, {}, clear=True)
    def test_should_summarize_no_chat_id(self):
        """Test that _should_summarize returns False when chat_id is None."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Set message service but no chat_id
                orchestrator.message_service = Mock()
                assert orchestrator._should_summarize() is False

    @patch.dict(os.environ, {"SPARKY_SUMMARY_TOKEN_THRESHOLD": "0.85"})
    def test_should_summarize_below_threshold(self):
        """Test that _should_summarize returns False when below threshold."""
        config = ProviderConfig(model_name="gemini-2.0-flash", token_budget_percent=0.8)
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Mock dependencies
                mock_node = Mock()
                mock_node.properties = {"message_type": "message"}
                
                orchestrator._chat_id = "test-chat"
                orchestrator.message_service = Mock()
                orchestrator.knowledge = Mock()
                orchestrator.knowledge.repository.get_chat_messages.return_value = [mock_node]
                orchestrator.message_service._convert_nodes_to_llm_format.return_value = [
                    {"role": "user", "parts": ["test"]}
                ]
                # Low token count (100 tokens)
                orchestrator.message_service.estimate_tokens.return_value = 100
                
                # Should not summarize (100 < 85% of 838,860)
                assert orchestrator._should_summarize() is False

    @patch.dict(os.environ, {"SPARKY_SUMMARY_TOKEN_THRESHOLD": "0.85"})
    def test_should_summarize_above_threshold(self):
        """Test that _should_summarize returns True when above threshold."""
        config = ProviderConfig(model_name="gemini-2.0-flash", token_budget_percent=0.8)
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Mock dependencies
                mock_node = Mock()
                mock_node.properties = {"message_type": "message"}
                
                orchestrator._chat_id = "test-chat"
                orchestrator.message_service = Mock()
                orchestrator.knowledge = Mock()
                orchestrator.knowledge.repository.get_chat_messages.return_value = [mock_node]
                orchestrator.message_service._convert_nodes_to_llm_format.return_value = [
                    {"role": "user", "parts": ["test"] * 1000}
                ]
                # High token count (750,000 tokens)
                orchestrator.message_service.estimate_tokens.return_value = 750000
                
                # Should summarize (750,000 >= 85% of 838,860)
                assert orchestrator._should_summarize() is True

    @patch.dict(os.environ, {"SPARKY_SUMMARY_TOKEN_THRESHOLD": "0.85"})
    def test_should_summarize_only_checks_since_last_summary(self):
        """Test that _should_summarize only considers messages since last summary."""
        config = ProviderConfig(model_name="gemini-2.0-flash", token_budget_percent=0.8)
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Mock nodes: old messages, then summary, then new messages
                old_msg = Mock()
                old_msg.properties = {"message_type": "message"}
                
                summary = Mock()
                summary.properties = {"message_type": "summary"}
                
                new_msg = Mock()
                new_msg.properties = {"message_type": "message"}
                
                orchestrator._chat_id = "test-chat"
                orchestrator.message_service = Mock()
                orchestrator.knowledge = Mock()
                orchestrator.knowledge.repository.get_chat_messages.return_value = [
                    old_msg, old_msg, old_msg, summary, new_msg, new_msg
                ]
                orchestrator.message_service._convert_nodes_to_llm_format.return_value = [
                    {"role": "user", "parts": ["test"]},
                    {"role": "model", "parts": ["response"]}
                ]
                orchestrator.message_service.estimate_tokens.return_value = 100
                
                # Should only check new messages after summary
                orchestrator._should_summarize()
                
                # Verify only messages after summary were converted
                call_args = orchestrator.message_service._convert_nodes_to_llm_format.call_args[0][0]
                assert len(call_args) == 2  # Only 2 new messages after summary
                assert call_args[0] == new_msg
                assert call_args[1] == new_msg


class TestSummarizeConversation:
    """Tests for _summarize_conversation() method."""

    @patch.dict(os.environ, {}, clear=True)
    @pytest.mark.asyncio
    async def test_summarize_conversation_generates_summary(self):
        """Test that _summarize_conversation generates and saves a summary."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Mock dependencies
                orchestrator._chat_id = "test-chat"
                orchestrator.message_service = Mock()
                orchestrator.message_service.format_for_summary.return_value = "Test conversation"
                
                # Mock generate to return a summary
                orchestrator.generate = AsyncMock(return_value="This is a summary")
                
                # Mock events
                orchestrator.events.async_dispatch = AsyncMock()
                
                # Call summarize
                await orchestrator._summarize_conversation()
                
                # Verify generate was called
                orchestrator.generate.assert_called_once()
                assert "Summarize the key points" in orchestrator.generate.call_args[0][0]
                
                # Verify SUMMARIZED event was dispatched
                orchestrator.events.async_dispatch.assert_called_once()
                assert orchestrator.events.async_dispatch.call_args[0][1] == "This is a summary"

    @patch.dict(os.environ, {}, clear=True)
    @pytest.mark.asyncio
    async def test_summarize_conversation_handles_empty_summary(self):
        """Test that _summarize_conversation handles empty summaries gracefully."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Mock dependencies
                orchestrator._chat_id = "test-chat"
                orchestrator.message_service = Mock()
                orchestrator.message_service.format_for_summary.return_value = "Test conversation"
                
                # Mock generate to return empty string
                orchestrator.generate = AsyncMock(return_value="")
                
                # Mock events
                orchestrator.events.async_dispatch = AsyncMock()
                
                # Call summarize
                await orchestrator._summarize_conversation()
                
                # Verify fallback text was used
                orchestrator.events.async_dispatch.assert_called_once()
                assert "No conversation content to summarize yet." in orchestrator.events.async_dispatch.call_args[0][1]


class TestIntegrationWithStartChat:
    """Integration tests for summarization in start_chat."""

    @patch.dict(os.environ, {"SPARKY_SUMMARY_TOKEN_THRESHOLD": "0.85"})
    @pytest.mark.asyncio
    async def test_start_chat_triggers_summarization_when_needed(self):
        """Test that start_chat triggers summarization when threshold is exceeded."""
        config = ProviderConfig(model_name="gemini-2.0-flash", token_budget_percent=0.8)
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Mock _should_summarize to return True
                orchestrator._should_summarize = Mock(return_value=True)
                
                # Mock _summarize_conversation
                orchestrator._summarize_conversation = AsyncMock()
                
                # Mock other dependencies
                orchestrator.identity_service = Mock()
                orchestrator.identity_service.get_identity_memory = AsyncMock(return_value="Identity")
                orchestrator.identity_service.summarize_identity = AsyncMock(return_value="Identity summary")
                orchestrator.identity_service.format_identity_instruction = Mock(return_value="Identity instruction")
                orchestrator.identity_service.get_session_context = AsyncMock(return_value="Session context")
                
                orchestrator._get_recent_messages = Mock(return_value=[])
                orchestrator.provider.start_chat = AsyncMock(return_value=Mock())
                orchestrator.events.async_dispatch = AsyncMock()
                
                # Call start_chat
                await orchestrator.start_chat(session_id="test-session")
                
                # Verify summarization was called
                orchestrator._summarize_conversation.assert_called_once()

    @patch.dict(os.environ, {"SPARKY_SUMMARY_TOKEN_THRESHOLD": "0.85"})
    @pytest.mark.asyncio
    async def test_start_chat_skips_summarization_when_not_needed(self):
        """Test that start_chat skips summarization when below threshold."""
        config = ProviderConfig(model_name="gemini-2.0-flash", token_budget_percent=0.8)
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Mock _should_summarize to return False
                orchestrator._should_summarize = Mock(return_value=False)
                
                # Mock _summarize_conversation
                orchestrator._summarize_conversation = AsyncMock()
                
                # Mock other dependencies
                orchestrator.identity_service = Mock()
                orchestrator.identity_service.get_identity_memory = AsyncMock(return_value="Identity")
                orchestrator.identity_service.summarize_identity = AsyncMock(return_value="Identity summary")
                orchestrator.identity_service.format_identity_instruction = Mock(return_value="Identity instruction")
                orchestrator.identity_service.get_session_context = AsyncMock(return_value="Session context")
                
                orchestrator._get_recent_messages = Mock(return_value=[])
                orchestrator.provider.start_chat = AsyncMock(return_value=Mock())
                orchestrator.events.async_dispatch = AsyncMock()
                
                # Call start_chat
                await orchestrator.start_chat(session_id="test-session")
                
                # Verify summarization was NOT called
                orchestrator._summarize_conversation.assert_not_called()


