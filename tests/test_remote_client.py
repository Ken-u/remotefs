"""Tests for RemoteFS remote client."""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
from remotefs.remote_client import RemoteClient, RemoteError


@pytest.fixture
def client():
    """Create test client."""
    return RemoteClient("http://test-server:8080", "test-token")


def test_read_file(client):
    """Test reading a file."""
    with patch.object(client.session, "request") as mock_request:
        mock_request.return_value.status_code = 200
        mock_request.return_value.content = b"file content"

        content = client.read_file("/test/file.txt")
        assert content == b"file content"


def test_write_file(client):
    """Test writing a file."""
    with patch.object(client.session, "request") as mock_request:
        mock_request.return_value.status_code = 200

        result = client.write_file("/test/file.txt", b"new content")
        assert result is True


def test_list_dir(client):
    """Test listing a directory."""
    with patch.object(client.session, "request") as mock_request:
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = [
            {"name": "file1.txt", "type": "file", "size": 100},
            {"name": "subdir", "type": "dir"},
        ]

        contents = client.list_dir("/test")
        assert len(contents) == 2
        assert contents[0]["name"] == "file1.txt"


def test_exec_cmd(client):
    """Test executing a command."""
    with patch.object(client.session, "request") as mock_request:
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = {
            "stdout": "output",
            "stderr": "",
            "exit_code": 0,
        }

        result = client.exec_cmd("make", ["-j4"])
        assert result["stdout"] == "output"
        assert result["exit_code"] == 0


def test_search(client):
    """Test index search."""
    with patch.object(client.session, "request") as mock_request:
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = [
            {"path": "/src/foo.py", "line": 10, "match": "def foo()"},
        ]

        results = client.search("def foo", "/src")
        assert len(results) == 1
        assert results[0]["path"] == "/src/foo.py"


def test_remote_error(client):
    """Test error handling."""
    with patch.object(client.session, "request") as mock_request:
        # Create a mock response that will raise HTTPError
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            "404 Client Error: Not Found", response=mock_response
        )
        mock_request.return_value = mock_response

        with pytest.raises(RemoteError) as exc_info:
            client.read_file("/nonexistent")
        assert exc_info.value.status_code == 404