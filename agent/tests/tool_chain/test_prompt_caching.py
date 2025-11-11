"""Tests for prompt caching in ToolChain."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from badmcp.tool_chain import ToolChain


class MockPrompt:
    """Mock prompt for testing."""

    def __init__(self, name, description="Test prompt"):
        self.name = name
        self.description = description


class MockPromptList:
    """Mock prompt list response."""

    def __init__(self, prompts):
        self.prompts = prompts


class MockToolClient:
    """Mock tool client for testing."""

    def __init__(self, name, prompts=None):
        self._config = MagicMock()
        self._config.name = name
        self.name = name
        self._prompts = prompts or []
        self.list_prompts_call_count = 0
        self.get_prompt_call_count = 0

    async def load_tools(self):
        """Mock load_tools."""
        pass

    async def list_prompts(self):
        """Mock list_prompts - tracks call count."""
        self.list_prompts_call_count += 1
        return MockPromptList(self._prompts)

    async def get_prompt(self, prompt_name, arguments=None):
        """Mock get_prompt - tracks call count."""
        self.get_prompt_call_count += 1
        
        # Return mock result with messages
        mock_content = MagicMock()
        mock_content.text = f"Rendered prompt: {prompt_name}"
        
        mock_message = MagicMock()
        mock_message.content = mock_content
        
        mock_result = MagicMock()
        mock_result.messages = [mock_message]
        
        return mock_result


class TestPromptCaching:
    """Tests for prompt caching functionality."""

    @pytest.mark.asyncio
    async def test_load_prompts_caches_results(self):
        """Test that load_prompts caches the results."""
        client1 = MockToolClient("client1", [
            MockPrompt("prompt1"),
            MockPrompt("prompt2"),
        ])
        client2 = MockToolClient("client2", [
            MockPrompt("prompt3"),
        ])

        toolchain = ToolChain([client1, client2])

        # First load
        prompts1 = await toolchain.load_prompts()
        assert len(prompts1) == 3
        assert client1.list_prompts_call_count == 1
        assert client2.list_prompts_call_count == 1

        # Second load - should use cache
        prompts2 = await toolchain.load_prompts()
        assert prompts1 is prompts2  # Same object
        assert client1.list_prompts_call_count == 1  # No additional calls
        assert client2.list_prompts_call_count == 1

    @pytest.mark.asyncio
    async def test_available_prompts_property(self):
        """Test available_prompts property."""
        client = MockToolClient("client", [MockPrompt("test")])
        toolchain = ToolChain([client])

        # Should raise if not loaded
        with pytest.raises(Exception, match="Prompts not loaded"):
            _ = toolchain.available_prompts

        # Load prompts
        await toolchain.load_prompts()

        # Now should work
        prompts = toolchain.available_prompts
        assert len(prompts) == 1

    @pytest.mark.asyncio
    async def test_list_all_prompts_uses_cache(self):
        """Test that list_all_prompts uses the cache."""
        client1 = MockToolClient("client1", [MockPrompt("prompt1")])
        client2 = MockToolClient("client2", [MockPrompt("prompt2")])

        toolchain = ToolChain([client1, client2])

        # First call - loads and caches
        prompts1 = await toolchain.list_all_prompts()
        assert len(prompts1) == 2
        assert client1.list_prompts_call_count == 1
        assert client2.list_prompts_call_count == 1

        # Second call - should use cache
        prompts2 = await toolchain.list_all_prompts()
        assert len(prompts2) == 2
        assert client1.list_prompts_call_count == 1  # No additional calls
        assert client2.list_prompts_call_count == 1

    @pytest.mark.asyncio
    async def test_find_prompt(self):
        """Test find_prompt method."""
        client1 = MockToolClient("client1", [MockPrompt("prompt1")])
        client2 = MockToolClient("client2", [MockPrompt("prompt2")])

        toolchain = ToolChain([client1, client2])

        # Should return None if prompts not loaded
        result = toolchain.find_prompt("prompt1")
        assert result is None

        # Load prompts
        await toolchain.load_prompts()

        # Now should find it
        result = toolchain.find_prompt("prompt1")
        assert result is client1

        result = toolchain.find_prompt("prompt2")
        assert result is client2

        # Should return None for non-existent prompt
        result = toolchain.find_prompt("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_prompt_uses_cache_for_lookup(self):
        """Test that get_prompt uses cache for finding client."""
        client = MockToolClient("client", [MockPrompt("test_prompt")])
        toolchain = ToolChain([client])

        # First call - loads cache and renders prompt
        result = await toolchain.get_prompt("test_prompt", {"arg": "value"})
        assert "Rendered prompt: test_prompt" in result
        assert client.list_prompts_call_count == 1
        assert client.get_prompt_call_count == 1

        # Second call - cache hit for lookup, still needs to render
        result = await toolchain.get_prompt("test_prompt", {"arg": "value2"})
        assert "Rendered prompt: test_prompt" in result
        assert client.list_prompts_call_count == 1  # No additional list call!
        assert client.get_prompt_call_count == 2  # Rendering still called

    @pytest.mark.asyncio
    async def test_get_prompt_not_found(self):
        """Test get_prompt with non-existent prompt."""
        client = MockToolClient("client", [MockPrompt("prompt1")])
        toolchain = ToolChain([client])

        with pytest.raises(Exception, match="Prompt 'nonexistent' not found"):
            await toolchain.get_prompt("nonexistent")

    @pytest.mark.asyncio
    async def test_prompts_format_conversion(self):
        """Test that list_all_prompts returns (client, prompt) tuples."""
        client1 = MockToolClient("client1", [MockPrompt("p1")])
        client2 = MockToolClient("client2", [MockPrompt("p2")])

        toolchain = ToolChain([client1, client2])
        prompts = await toolchain.list_all_prompts()

        # Should be list of (client, prompt) tuples
        assert len(prompts) == 2
        assert prompts[0][0] is client1
        assert prompts[0][1].name == "p1"
        assert prompts[1][0] is client2
        assert prompts[1][1].name == "p2"

    @pytest.mark.asyncio
    async def test_empty_prompts(self):
        """Test handling of clients with no prompts."""
        client1 = MockToolClient("client1", [])
        client2 = MockToolClient("client2", [MockPrompt("prompt1")])

        toolchain = ToolChain([client1, client2])
        prompts = await toolchain.list_all_prompts()

        # Should only have prompts from client2
        assert len(prompts) == 1
        assert prompts[0][1].name == "prompt1"

    @pytest.mark.asyncio
    async def test_prompt_caching_performance(self):
        """Test that caching improves performance."""
        # Create clients with prompts
        clients = [
            MockToolClient(f"client{i}", [MockPrompt(f"prompt{i}")])
            for i in range(10)
        ]

        toolchain = ToolChain(clients)

        # First call - loads all
        await toolchain.list_all_prompts()
        initial_calls = sum(c.list_prompts_call_count for c in clients)
        assert initial_calls == 10

        # Multiple subsequent calls - should not increase count
        for _ in range(5):
            await toolchain.list_all_prompts()

        final_calls = sum(c.list_prompts_call_count for c in clients)
        assert final_calls == 10  # No additional calls!


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



