# tests/test_identity_service.py

import pytest
from unittest.mock import MagicMock, call
import re

from services.identity_service import IdentityService

@pytest.fixture
def mock_repository():
    """Create a mock KnowledgeRepository."""
    return MagicMock()

@pytest.fixture
def identity_service(mock_repository):
    """Create a IdentityService instance with the mock repository."""
    return IdentityService(repository=mock_repository)

@pytest.mark.asyncio
async def test_get_identity_memory_success(identity_service, mock_repository):
    """Test loading identity memory successfully."""
    await identity_service.get_identity_memory()

@pytest.mark.asyncio
async def test_get_identity_memory_failure(identity_service, mock_repository):
    """Test handling identity memory loading failure."""
    mock_repository.search_nodes.side_effect = Exception("Search failed")

    identity_memory = await identity_service.get_identity_memory()

    assert "Identity Loading Failed" in identity_memory
    mock_repository.search_nodes.assert_called_once()
