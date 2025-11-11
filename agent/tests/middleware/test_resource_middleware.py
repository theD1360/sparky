"""Test ResourceFetchingMiddleware functionality."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from sparky.middleware.base import MessageContext
from sparky.middleware.message_middlewares import ResourceFetchingMiddleware


@pytest.fixture
def mock_bot():
    """Create a mock bot instance with toolchain."""
    bot = MagicMock()
    bot.toolchain = MagicMock()
    return bot


class MockUri:
    """Mock URI object that simulates Pydantic's AnyUrl behavior."""
    
    def __init__(self, uri_string):
        self._uri = uri_string
    
    def __str__(self):
        return self._uri
    
    def __contains__(self, item):
        # Simulate the error that was occurring - AnyUrl is not iterable
        raise TypeError("argument of type 'AnyUrl' is not iterable")


@pytest.fixture
def mock_resource():
    """Create a mock resource with AnyUrl-like object."""
    resource = MagicMock()
    resource.uri = MockUri("knowledge://stats")
    resource.description = "Statistics about the knowledge graph"
    return resource


@pytest.fixture
def mock_client():
    """Create a mock client."""
    return MagicMock()


@pytest.mark.asyncio
async def test_resource_fetching_with_full_uri(mock_bot, mock_resource, mock_client):
    """Test fetching a resource using full URI."""
    # Setup
    middleware = ResourceFetchingMiddleware()
    message = "Show me the stats: @knowledge://stats"
    
    # Mock bot methods
    mock_bot.list_resources = AsyncMock(return_value=[(mock_client, mock_resource)])
    mock_bot.read_resource = AsyncMock(
        return_value=json.dumps({"total_nodes": 100, "total_edges": 50})
    )
    
    # Create context
    context = MessageContext(message=message, bot_instance=mock_bot)
    next_call = AsyncMock(return_value=context)
    
    # Execute
    result = await middleware(context, next_call)
    
    # Verify - original message should be preserved, resource appended at end
    assert result.modified_message is not None
    assert result.modified_message.startswith("Show me the stats: @knowledge://stats")
    assert "---" in result.modified_message
    assert "[Resource: knowledge://stats]" in result.modified_message
    assert "total_nodes" in result.modified_message
    assert "100" in result.modified_message
    mock_bot.read_resource.assert_called_once_with("knowledge://stats")


@pytest.mark.asyncio
async def test_resource_fetching_with_short_name(mock_bot, mock_resource, mock_client):
    """Test fetching a resource using short name."""
    # Setup
    middleware = ResourceFetchingMiddleware()
    message = "Show me @stats"
    
    # Mock bot methods
    mock_bot.list_resources = AsyncMock(return_value=[(mock_client, mock_resource)])
    mock_bot.read_resource = AsyncMock(
        return_value=json.dumps({"total_nodes": 100, "total_edges": 50})
    )
    
    # Create context
    context = MessageContext(message=message, bot_instance=mock_bot)
    next_call = AsyncMock(return_value=context)
    
    # Execute
    result = await middleware(context, next_call)
    
    # Verify - original message preserved, resource appended
    assert result.modified_message is not None
    assert result.modified_message.startswith("Show me @stats")
    assert "---" in result.modified_message
    assert "[Resource: knowledge://stats]" in result.modified_message
    assert "total_nodes" in result.modified_message
    mock_bot.read_resource.assert_called_once_with("knowledge://stats")


@pytest.mark.asyncio
async def test_resource_fetching_multiple_resources(mock_bot, mock_client):
    """Test fetching multiple resources in one message."""
    # Setup
    middleware = ResourceFetchingMiddleware()
    message = "Compare @stats and @memories"
    
    # Create mock resources
    stats_resource = MagicMock()
    stats_resource.uri = MockUri("knowledge://stats")
    stats_resource.description = "Stats"
    
    memories_resource = MagicMock()
    memories_resource.uri = MockUri("knowledge://memories")
    memories_resource.description = "Memories"
    
    # Mock bot methods
    mock_bot.list_resources = AsyncMock(
        return_value=[
            (mock_client, stats_resource),
            (mock_client, memories_resource),
        ]
    )
    
    async def mock_read_resource(uri):
        if uri == "knowledge://stats":
            return json.dumps({"total_nodes": 100})
        elif uri == "knowledge://memories":
            return json.dumps({"count": 10})
        raise ValueError(f"Unknown resource: {uri}")
    
    mock_bot.read_resource = AsyncMock(side_effect=mock_read_resource)
    
    # Create context
    context = MessageContext(message=message, bot_instance=mock_bot)
    next_call = AsyncMock(return_value=context)
    
    # Execute
    result = await middleware(context, next_call)
    
    # Verify - original message preserved with both @stats and @memories, resources appended
    assert result.modified_message is not None
    assert result.modified_message.startswith("Compare @stats and @memories")
    assert "---" in result.modified_message
    assert "[Resource: knowledge://stats]" in result.modified_message
    assert "[Resource: knowledge://memories]" in result.modified_message
    assert "total_nodes" in result.modified_message
    assert "count" in result.modified_message
    assert mock_bot.read_resource.call_count == 2


@pytest.mark.asyncio
async def test_resource_not_found(mock_bot, mock_resource, mock_client):
    """Test handling of non-existent resource."""
    # Setup
    middleware = ResourceFetchingMiddleware()
    message = "Show me @nonexistent"
    
    # Mock bot methods
    mock_bot.list_resources = AsyncMock(return_value=[(mock_client, mock_resource)])
    
    # Create context
    context = MessageContext(message=message, bot_instance=mock_bot)
    next_call = AsyncMock(return_value=context)
    
    # Execute
    result = await middleware(context, next_call)
    
    # Verify - message should remain unmodified when resource not found
    assert result.modified_message is None
    # Should not attempt to read
    mock_bot.read_resource.assert_not_called()


@pytest.mark.asyncio
async def test_no_resource_pattern(mock_bot):
    """Test message without resource pattern."""
    # Setup
    middleware = ResourceFetchingMiddleware()
    message = "This is a regular message without resources"
    
    # Create context
    context = MessageContext(message=message, bot_instance=mock_bot)
    next_call = AsyncMock(return_value=context)
    
    # Execute
    result = await middleware(context, next_call)
    
    # Verify - should not modify message
    assert result.modified_message is None
    next_call.assert_called_once()


@pytest.mark.asyncio
async def test_no_toolchain_available(mock_bot):
    """Test handling when toolchain is not available."""
    # Setup
    middleware = ResourceFetchingMiddleware()
    message = "Show me @stats"
    
    # Remove toolchain
    mock_bot.toolchain = None
    
    # Create context
    context = MessageContext(message=message, bot_instance=mock_bot)
    next_call = AsyncMock(return_value=context)
    
    # Execute
    result = await middleware(context, next_call)
    
    # Verify - should continue without modification
    assert result.modified_message is None
    next_call.assert_called_once()


@pytest.mark.asyncio
async def test_resource_fetch_error(mock_bot, mock_resource, mock_client):
    """Test handling of resource fetch errors."""
    # Setup
    middleware = ResourceFetchingMiddleware()
    message = "Show me @stats"
    
    # Mock bot methods
    mock_bot.list_resources = AsyncMock(return_value=[(mock_client, mock_resource)])
    mock_bot.read_resource = AsyncMock(side_effect=Exception("Connection error"))
    
    # Create context
    context = MessageContext(message=message, bot_instance=mock_bot)
    next_call = AsyncMock(return_value=context)
    
    # Execute
    result = await middleware(context, next_call)
    
    # Verify - original message preserved, error appended at end
    assert result.modified_message is not None
    assert result.modified_message.startswith("Show me @stats")
    assert "---" in result.modified_message
    assert "Error fetching resource" in result.modified_message
    assert "Connection error" in result.modified_message


@pytest.mark.asyncio
async def test_non_json_resource_content(mock_bot, mock_resource, mock_client):
    """Test handling of non-JSON resource content."""
    # Setup
    middleware = ResourceFetchingMiddleware()
    message = "Show me @stats"
    
    # Mock bot methods
    mock_bot.list_resources = AsyncMock(return_value=[(mock_client, mock_resource)])
    mock_bot.read_resource = AsyncMock(return_value="Plain text content")
    
    # Create context
    context = MessageContext(message=message, bot_instance=mock_bot)
    next_call = AsyncMock(return_value=context)
    
    # Execute
    result = await middleware(context, next_call)
    
    # Verify - original message preserved, plain text content appended at end
    assert result.modified_message is not None
    assert result.modified_message.startswith("Show me @stats")
    assert "---" in result.modified_message
    assert "Plain text content" in result.modified_message
    assert "[Resource: knowledge://stats]" in result.modified_message


if __name__ == "__main__":
    # Run tests
    asyncio.run(pytest.main([__file__, "-v"]))

