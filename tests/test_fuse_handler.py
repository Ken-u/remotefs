"""Tests for RemoteFS FUSE handler."""

import pytest
from unittest.mock import Mock, patch, PropertyMock

from remotefs.fuse_handler import RemoteFS
from remotefs.remote_client import RemoteClient, RemoteError
from remotefs.cache import MetadataCache


@pytest.fixture
def mock_client():
    """Create mock remote client."""
    client = Mock(spec=RemoteClient)
    client.exists.return_value = True
    client.list_dir.side_effect = RemoteError("Not a directory")
    client.read_file.return_value = b"file content"
    return client


@pytest.fixture
def cache():
    """Create cache."""
    return MetadataCache(ttl=5)


@pytest.fixture
def fs(mock_client, cache):
    """Create FUSE filesystem."""
    return RemoteFS(client=mock_client, cache=cache, root="/")


def test_getattr_file(fs, mock_client):
    """Test getting file attributes."""
    attr = fs.getattr("/test/file.txt")
    assert "st_mode" in attr
    assert attr["st_nlink"] == 1


def test_getattr_dir(cache):
    """Test getting directory attributes."""
    # Create a separate mock for directory that returns list_dir successfully
    dir_client = Mock(spec=RemoteClient)
    dir_client.list_dir.return_value = [
        {"name": "file1.txt", "type": "file"},
        {"name": "subdir", "type": "dir"},
    ]
    dir_fs = RemoteFS(client=dir_client, cache=cache, root="/")

    attr = dir_fs.getattr("/test")
    assert "st_mode" in attr
    assert attr["st_nlink"] == 2


def test_readdir(fs, mock_client):
    """Test listing directory."""
    # For readdir, we need list_dir to succeed
    mock_client.list_dir.side_effect = None
    mock_client.list_dir.return_value = [
        {"name": "file1.txt", "type": "file"},
        {"name": "subdir", "type": "dir"},
    ]

    entries = fs.readdir("/test")
    assert "." in entries
    assert ".." in entries
    assert "file1.txt" in entries
    assert "subdir" in entries


def test_readdir_root(fs, mock_client):
    """Test listing root directory."""
    entries = fs.readdir("/")
    assert ".local" in entries


def test_read_file(fs, mock_client):
    """Test reading a file."""
    fd = fs.open("/test/file.txt", "r")
    content = fs.read("/test/file.txt", 100, 0, fd)
    assert content == b"file content"
    fs.release("/test/file.txt", fd)


def test_write_file(fs, mock_client):
    """Test writing a file."""
    fd = fs.open("/test/file.txt", "w")
    written = fs.write("/test/file.txt", b"new content", 0, fd)
    assert written == 11
    mock_client.write_file.assert_called_once()
    fs.release("/test/file.txt", fd)


def test_mkdir(fs, mock_client):
    """Test creating a directory."""
    fs.mkdir("/test/newdir", 0o755)
    mock_client.create_dir.assert_called_once_with("/test/newdir")


def test_unlink(fs, mock_client):
    """Test deleting a file."""
    fs.unlink("/test/file.txt")
    mock_client.delete_file.assert_called_once_with("/test/file.txt")