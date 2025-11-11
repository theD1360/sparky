"""Tests for AgentOrchestrator."""

import unittest
from unittest.mock import AsyncMock, Mock, MagicMock, patch

from sparky import AgentOrchestrator
from sparky.providers import GeminiProvider, ProviderConfig


class TestAgentOrchestrator(unittest.TestCase):
    """Test the AgentOrchestrator class."""

    @patch("sparky.providers.gemini_provider.genai.configure")
    @patch("sparky.providers.gemini_provider.genai.GenerativeModel")
    def test_initialization_with_gemini_provider(self, mock_model_class, mock_configure):
        """Test that AgentOrchestrator initializes with GeminiProvider."""
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        
        config = ProviderConfig(model_name="gemini-1.5-pro", api_key="test_key")
        provider = GeminiProvider(config)
        orchestrator = AgentOrchestrator(provider=provider)
        
        # Verify provider is GeminiProvider
        self.assertIsInstance(orchestrator.provider, GeminiProvider)
        mock_configure.assert_called_once()

    @patch("sparky.providers.gemini_provider.genai.configure")
    @patch("sparky.providers.gemini_provider.genai.GenerativeModel")
    def test_initialization_with_custom_provider(self, mock_model_class, mock_configure):
        """Test that AgentOrchestrator can accept a custom provider."""
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        
        config = ProviderConfig(model_name="gemini-2.0-flash", api_key="test_key")
        custom_provider = GeminiProvider(config)
        
        orchestrator = AgentOrchestrator(provider=custom_provider)
        
        # Verify custom provider is used
        self.assertEqual(orchestrator.provider, custom_provider)
        self.assertIsNotNone(orchestrator.model)

    @patch("sparky.providers.gemini_provider.genai.configure")
    @patch("sparky.providers.gemini_provider.genai.GenerativeModel")
    def test_initialization_with_toolchain(self, mock_model_class, mock_configure):
        """Test AgentOrchestrator initialization with toolchain."""
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        
        mock_toolchain = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.inputSchema = {"type": "object", "properties": {}}
        mock_toolchain.available_tools = [(0, mock_tool)]
        
        config = ProviderConfig(model_name="gemini-1.5-pro", api_key="test_key")
        provider = GeminiProvider(config)
        orchestrator = AgentOrchestrator(
            provider=provider,
            toolchain=mock_toolchain,
        )
        
        # Verify toolchain is set
        self.assertEqual(orchestrator.toolchain, mock_toolchain)
        self.assertIsNotNone(orchestrator._safe_to_original)


class TestGeminiProvider(unittest.TestCase):
    """Test the GeminiProvider implementation."""

    @patch("sparky.providers.gemini_provider.genai.configure")
    def test_provider_configure(self, mock_configure):
        """Test provider configuration."""
        config = ProviderConfig(model_name="gemini-1.5-pro", api_key="test_key")
        provider = GeminiProvider(config)
        provider.configure()
        
        mock_configure.assert_called_once_with(api_key="test_key")

    @patch("sparky.providers.gemini_provider.genai.configure")
    @patch("sparky.providers.gemini_provider.genai.GenerativeModel")
    def test_provider_initialize_model_without_tools(self, mock_model_class, mock_configure):
        """Test model initialization without tools."""
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        
        config = ProviderConfig(model_name="gemini-1.5-pro", api_key="test_key")
        provider = GeminiProvider(config)
        provider.configure()
        
        model, safe_to_original = provider.initialize_model(toolchain=None)
        
        self.assertIsNotNone(model)
        self.assertIsNone(safe_to_original)
        mock_model_class.assert_called_once_with("gemini-1.5-pro")

    @patch("sparky.providers.gemini_provider.genai.configure")
    @patch("sparky.providers.gemini_provider.genai.GenerativeModel")
    def test_provider_prepare_tools(self, mock_model_class, mock_configure):
        """Test tool preparation for Gemini."""
        config = ProviderConfig(model_name="gemini-1.5-pro", api_key="test_key")
        provider = GeminiProvider(config)
        provider.configure()
        
        # Create mock toolchain
        mock_toolchain = MagicMock()
        mock_tool1 = MagicMock()
        mock_tool1.name = "tool1"
        mock_tool1.description = "Test tool 1"
        mock_tool1.inputSchema = {"type": "object", "properties": {}}
        
        mock_tool2 = MagicMock()
        mock_tool2.name = "tool-with-dash"  # Test name sanitization
        mock_tool2.description = "Test tool 2"
        mock_tool2.inputSchema = {"type": "object", "properties": {}}
        
        mock_toolchain.available_tools = [(0, mock_tool1), (1, mock_tool2)]
        
        tools, safe_to_original = provider.prepare_tools(mock_toolchain)
        
        # Verify tools were prepared
        self.assertEqual(len(tools), 2)
        self.assertEqual(tools[0]["name"], "tool1")
        self.assertEqual(tools[1]["name"], "tool_with_dash")  # Dash converted to underscore
        
        # Verify mapping
        self.assertEqual(safe_to_original["tool1"], "tool1")
        self.assertEqual(safe_to_original["tool_with_dash"], "tool-with-dash")

    def test_provider_extract_text(self):
        """Test text extraction from Gemini response."""
        config = ProviderConfig(model_name="gemini-1.5-pro", api_key="test_key")
        provider = GeminiProvider(config)
        
        # Create mock response
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_content = MagicMock()
        mock_part = MagicMock()
        mock_part.text = "Test response"
        
        mock_content.parts = [mock_part]
        mock_candidate.content = mock_content
        mock_response.candidates = [mock_candidate]
        
        text = provider.extract_text(mock_response)
        
        self.assertEqual(text, "Test response")

    def test_provider_get_function_calls(self):
        """Test function call extraction from Gemini response."""
        config = ProviderConfig(model_name="gemini-1.5-pro", api_key="test_key")
        provider = GeminiProvider(config)
        
        # Create mock response with function call
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_content = MagicMock()
        mock_part = MagicMock()
        mock_function_call = MagicMock()
        mock_function_call.name = "test_tool"
        mock_part.function_call = mock_function_call
        
        mock_content.parts = [mock_part]
        mock_candidate.content = mock_content
        mock_response.candidates = [mock_candidate]
        
        function_calls = provider.get_function_calls(mock_response)
        
        self.assertEqual(len(function_calls), 1)
        self.assertEqual(function_calls[0].name, "test_tool")


if __name__ == "__main__":
    unittest.main()
