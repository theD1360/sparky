# tests/test_file_service.py

import pytest
from unittest.mock import MagicMock, patch
import aiofiles
import os
from pathlib import Path

from services.file_service import FileService

@pytest.fixture
def mock_repository():
    """Create a mock KnowledgeRepository."""
    return MagicMock()

@pytest.fixture
def file_service(mock_repository, tmpdir):
    """Create a FileService instance with the mock repository."""
    service = FileService(repository=mock_repository, upload_directory=tmpdir)
    return service

@pytest.mark.asyncio
async def test_upload_file_success(file_service, mock_repository, tmpdir):
    """Test uploading a file successfully."""
    file_content = b"test file content"
    filename = "test.txt"
    mime_type = "text/plain"
    file_size = len(file_content)
    user_id = "test_user"
    session_id = "test_session"

    file_node_id = await file_service.upload_file(
        file_content=file_content,
        filename=filename,
        mime_type=mime_type,
        file_size=file_size,
        user_id=user_id,
        session_id=session_id,
    )

    assert file_node_id is not None
    mock_repository.add_node.assert_called_once()
    mock_repository.add_edge.assert_called()

    # Assert that add_node was called with the correct arguments
    args, kwargs = mock_repository.add_node.call_args
    assert kwargs["node_type"] == "File"
    assert kwargs["label"] == filename
    assert kwargs["content"].startswith("File uploaded to")
    assert kwargs["properties"]["filename"] == filename
    assert kwargs["properties"]["mime_type"] == mime_type
    assert kwargs["properties"]["file_size"] == file_size

    # Assert that add_edge was called to link the file to the user and session
    mock_repository.add_edge.assert_any_call(
        source_id=f"user:{user_id}", target_id=file_node_id, edge_type="UPLOADED"
    )
    mock_repository.add_edge.assert_any_call(
        source_id=session_id, target_id=file_node_id, edge_type="CONTAINS"
    )

@pytest.mark.asyncio
async def test_upload_file_failure(file_service, mock_repository, tmpdir):
    """Test handling file upload failure."""
    with patch("os.path.exists") as mock_exists, \
         patch("os.makedirs") as mock_makedirs, \
         patch("os.path.join") as mock_join, \
         patch("builtins.open") as mock_open:

        mock_exists.return_value = False
        mock_makedirs.side_effect = OSError("Failed to create directory")
        mock_join.return_value = "fake_path"
        mock_open.side_effect = OSError("Failed to open file")
        
        file_node_id = await file_service.upload_file(
            file_content=b"test", filename="test.txt", mime_type="text/plain", file_size=4
        )
        assert file_node_id is None
        mock_repository.add_node.assert_not_called()
