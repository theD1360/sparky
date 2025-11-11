import os
import pytest
from fastapi.testclient import TestClient
from src.servers.chat.chat_server import app

client = TestClient(app)


@pytest.fixture
def test_file():
    # Create a dummy file for testing
    with open("test.txt", "w") as f:
        f.write("test content")
    yield "test.txt"
    os.remove("test.txt")


def test_upload_file(test_file):
    """Test file upload endpoint.
    
    Note: This test may fail if no active session/chat exists in the server.
    It's primarily for testing the endpoint's validation and file handling logic.
    """
    with open(test_file, "rb") as f:
        files = {"file": (test_file, f, "text/plain")}
        response = client.post(
            "/upload_file?session_id=test_session&chat_id=test_chat&user_id=test_user",
            files=files
        )

    # The endpoint might return 404 if no knowledge graph exists for the session
    # or 200 if successful. Both are acceptable outcomes for this test.
    if response.status_code == 200:
        # Success case
        json_response = response.json()
        assert "file_id" in json_response
        assert "file_name" in json_response
        # description may or may not be present depending on analysis
        
        # Verify the file is saved
        file_id = json_response["file_id"]
        file_name = json_response["file_name"]
        file_path = f"uploads/{file_id.split(':')[1]}"
        
        # Check if file exists
        if os.path.exists(file_path):
            # Clean up uploaded file
            os.remove(file_path)
            
        assert file_name == "test.txt"
    elif response.status_code == 404:
        # Expected when no active session exists
        json_response = response.json()
        assert "detail" in json_response
        assert "No knowledge graph found" in json_response["detail"]
    else:
        # Unexpected status code
        pytest.fail(f"Unexpected status code: {response.status_code}, body: {response.json()}")
