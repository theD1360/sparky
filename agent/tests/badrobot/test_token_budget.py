"""Tests for token budget configuration and functionality."""

import os
from unittest.mock import Mock, patch

import pytest

from sparky.providers import GeminiProvider, ProviderConfig
from sparky.agent_orchestrator import AgentOrchestrator


class TestProviderConfig:
    """Tests for ProviderConfig token budget features."""

    def test_default_token_budget_percent(self):
        """Test that default token budget percentage is 0.8."""
        config = ProviderConfig(model_name="test-model")
        assert config.token_budget_percent == 0.8

    def test_custom_token_budget_percent(self):
        """Test setting custom token budget percentage."""
        config = ProviderConfig(model_name="test-model", token_budget_percent=0.5)
        assert config.token_budget_percent == 0.5

    def test_get_effective_token_budget_with_context_window(self):
        """Test calculating effective token budget with context window set."""
        config = ProviderConfig(
            model_name="test-model",
            context_window=1000000,
            token_budget_percent=0.8
        )
        effective_budget = config.get_effective_token_budget()
        assert effective_budget == 800000

    def test_get_effective_token_budget_without_context_window(self):
        """Test that get_effective_token_budget returns None when context_window is not set."""
        config = ProviderConfig(model_name="test-model")
        effective_budget = config.get_effective_token_budget()
        assert effective_budget is None

    def test_get_effective_token_budget_with_different_percentages(self):
        """Test effective token budget calculation with various percentages."""
        test_cases = [
            (0.1, 100000),
            (0.5, 500000),
            (0.8, 800000),
            (1.0, 1000000),
        ]
        
        for percent, expected in test_cases:
            config = ProviderConfig(
                model_name="test-model",
                context_window=1000000,
                token_budget_percent=percent
            )
            assert config.get_effective_token_budget() == expected


class TestGeminiProviderContextWindow:
    """Tests for GeminiProvider context window detection."""

    def test_gemini_2_0_flash_context_window(self):
        """Test context window for Gemini 2.0 Flash."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        provider = GeminiProvider(config)
        assert provider.get_model_context_window() == 1048576

    def test_gemini_1_5_pro_context_window(self):
        """Test context window for Gemini 1.5 Pro."""
        config = ProviderConfig(model_name="gemini-1.5-pro")
        provider = GeminiProvider(config)
        assert provider.get_model_context_window() == 2097152

    def test_gemini_pro_context_window(self):
        """Test context window for legacy Gemini Pro."""
        config = ProviderConfig(model_name="gemini-pro")
        provider = GeminiProvider(config)
        assert provider.get_model_context_window() == 32768

    def test_explicit_context_window_overrides_model_default(self):
        """Test that explicit context_window in config overrides model defaults."""
        config = ProviderConfig(
            model_name="gemini-2.0-flash",
            context_window=500000
        )
        provider = GeminiProvider(config)
        assert provider.get_model_context_window() == 500000

    def test_unknown_model_defaults_to_1m(self):
        """Test that unknown Gemini models default to 1M tokens."""
        config = ProviderConfig(model_name="gemini-unknown-model")
        provider = GeminiProvider(config)
        assert provider.get_model_context_window() == 1048576


class TestAgentOrchestratorTokenBudget:
    """Tests for AgentOrchestrator token budget functionality."""

    @patch.dict(os.environ, {}, clear=True)
    def test_default_token_budget_no_env(self):
        """Test that default token budget is used when env var not set."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        # Mock the provider methods to avoid actual API calls
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Should use default 0.8
                assert orchestrator.provider.config.token_budget_percent == 0.8

    @patch.dict(os.environ, {"SPARKY_TOKEN_BUDGET_PERCENT": "0.6"})
    def test_token_budget_from_env(self):
        """Test that token budget is read from environment variable."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Should use env value
                assert orchestrator.provider.config.token_budget_percent == 0.6

    @patch.dict(os.environ, {"SPARKY_TOKEN_BUDGET_PERCENT": "1.5"})
    def test_token_budget_clamped_to_max(self):
        """Test that token budget percentage is clamped to 1.0."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Should be clamped to 1.0
                assert orchestrator.provider.config.token_budget_percent == 1.0

    @patch.dict(os.environ, {"SPARKY_TOKEN_BUDGET_PERCENT": "0.05"})
    def test_token_budget_clamped_to_min(self):
        """Test that token budget percentage is clamped to 0.1."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Should be clamped to 0.1
                assert orchestrator.provider.config.token_budget_percent == 0.1

    @patch.dict(os.environ, {"SPARKY_TOKEN_BUDGET_PERCENT": "invalid"})
    def test_invalid_token_budget_uses_default(self):
        """Test that invalid env value falls back to default."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Should use default 0.8
                assert orchestrator.provider.config.token_budget_percent == 0.8

    @patch.dict(os.environ, {}, clear=True)
    def test_get_effective_token_budget(self):
        """Test get_effective_token_budget method."""
        config = ProviderConfig(
            model_name="gemini-2.0-flash",
            token_budget_percent=0.8
        )
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Gemini 2.0 Flash has 1M tokens, 80% = 838,860 tokens
                effective_budget = orchestrator.get_effective_token_budget()
                assert effective_budget == int(1048576 * 0.8)
                assert effective_budget == 838860


class TestTokenBudgetIntegration:
    """Integration tests for token budget with message loading."""

    @patch.dict(os.environ, {"SPARKY_TOKEN_BUDGET_PERCENT": "0.7"})
    def test_message_loading_uses_token_budget(self):
        """Test that message loading respects token budget."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Create mock message service
                mock_message_service = Mock()
                orchestrator.message_service = mock_message_service
                orchestrator._chat_id = "test-chat-id"
                
                # Call _get_recent_messages with token limit enabled
                orchestrator._get_recent_messages(use_token_limit=True)
                
                # Verify that get_messages_within_token_limit was called
                mock_message_service.get_messages_within_token_limit.assert_called_once()
                
                # Check that the token budget was calculated correctly
                call_args = mock_message_service.get_messages_within_token_limit.call_args
                expected_budget = int(1048576 * 0.7)  # 733,603 tokens
                assert call_args[1]['max_tokens'] == expected_budget
                assert call_args[1]['prefer_summaries'] is True

    @patch.dict(os.environ, {}, clear=True)
    def test_message_loading_without_token_limit(self):
        """Test that message loading can still use count-based limits."""
        config = ProviderConfig(model_name="gemini-2.0-flash")
        
        with patch.object(GeminiProvider, 'configure'):
            with patch.object(GeminiProvider, 'initialize_model', return_value=(Mock(), {})):
                provider = GeminiProvider(config)
                orchestrator = AgentOrchestrator(provider=provider)
                
                # Create mock message service
                mock_message_service = Mock()
                orchestrator.message_service = mock_message_service
                orchestrator._chat_id = "test-chat-id"
                
                # Call _get_recent_messages with token limit disabled
                orchestrator._get_recent_messages(use_token_limit=False)
                
                # Verify that get_recent_messages was called instead
                mock_message_service.get_recent_messages.assert_called_once()
                assert not mock_message_service.get_messages_within_token_limit.called


