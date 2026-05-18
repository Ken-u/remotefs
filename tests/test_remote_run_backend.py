"""Tests for RemoteFS Remote Run backend."""

import pytest
from unittest.mock import Mock

from remotefs.backend import (
    BackendError,
    ExecResult,
    FileEntry,
    FileNotFoundError,
    SearchResult,
)
from remotefs.remote_run_backend import RemoteRunBackend


@pytest.fixture
def mock_api():
    """Create mock Remote Run API client."""
    return Mock()


@pytest.fixture
def backend(mock_api):
    """Create backend with injected API client."""
    return RemoteRunBackend(
        base_url="http://remote-run.test",
        token="test-token",
        rk_search_max_depth=1,
        rk_codesearch_project="Android14",
        rk_codesearch_type="python",
        rk_codesearch_search_field="def",
        api_client=mock_api,
    )


def test_list_dir_parses_entries(backend, mock_api):
    """list_dir should map Remote Run JSON to FileEntry objects."""
    mock_api.execute.return_value = {
        "status": "COMPLETED",
        "exit_code": 0,
        "stdout_truncated": """
        {
          "entries": [
            {"name": "main.py", "path": "src/main.py", "size_bytes": 12, "type": "file"},
            {"name": "pkg", "path": "src/pkg", "size_bytes": null, "type": "directory"}
          ]
        }
        """,
    }

    entries = backend.list_dir("/src")

    assert entries == [
        FileEntry(name="main.py", type="file", size=12),
        FileEntry(name="pkg", type="dir", size=None),
    ]
    mock_api.execute.assert_called_once_with("list_dir", {"path": "src"})


def test_file_exists_returns_false_for_missing_path(backend, mock_api):
    """file_exists should return False for missing paths."""
    mock_api.execute.return_value = {
        "status": "COMPLETED",
        "exit_code": 0,
        "stdout_truncated": """
        {
          "exists": false,
          "is_dir": false,
          "is_file": false,
          "path": "missing.txt",
          "type": "missing"
        }
        """,
    }

    assert backend.file_exists("/missing.txt") is False


def test_read_file_downloads_binary_content(backend, mock_api):
    """read_file should use download_path and download the resulting file bytes."""
    mock_api.execute.return_value = {
        "status": "COMPLETED",
        "exit_code": 0,
        "job_id": "job_123",
        "output_files": [{"path": "docs/spec.pdf"}],
    }
    mock_api.download_files.return_value = {"docs/spec.pdf": b"%PDF-1.7 binary data"}

    content = backend.read_file("/docs/spec.pdf")

    assert content == b"%PDF-1.7 binary data"
    mock_api.execute.assert_called_once_with("download_path", {"path": "docs/spec.pdf"})
    mock_api.download_files.assert_called_once_with(
        "job_123",
        ["docs/spec.pdf"],
    )


def test_write_file_rejects_non_utf8_binary_payload(backend):
    """write_file should reject non-text payloads until a binary-safe upload command exists."""
    with pytest.raises(BackendError, match="UTF-8"):
        backend.write_file("/blob.bin", b"\xff\xfe\x00\x01")


def test_read_file_raises_not_found(backend, mock_api):
    """read_file should map a missing path error to FileNotFoundError."""
    mock_api.execute.return_value = {
        "status": "FAILED",
        "exit_code": 1,
        "stdout_truncated": "Error: file does not exist: docs/missing.txt",
        "stderr_truncated": "",
    }

    with pytest.raises(FileNotFoundError):
        backend.read_file("/docs/missing.txt")


def test_exec_cmd_passes_allowlisted_command_id_and_parameters(backend, mock_api):
    """exec_cmd should treat cmd as a Remote Run command_id and parse key=value args."""
    mock_api.execute.return_value = {
        "status": "COMPLETED",
        "exit_code": 0,
        "stdout_truncated": '{"ok": true}',
        "stderr_truncated": "",
    }

    result = backend.exec_cmd("list_dir", ["path=src", "max_entries=10"])

    assert result == ExecResult(stdout=b'{"ok": true}', stderr=b"", exit_code=0)
    mock_api.execute.assert_called_once_with(
        "list_dir",
        {"path": "src", "max_entries": 10},
    )


def test_search_uses_rk_codesearch_first_for_shallow_paths(backend, mock_api):
    """search should prefer rk_codesearch for root and shallow directories."""
    mock_api.execute.side_effect = [
        {
            "status": "COMPLETED",
            "exit_code": 0,
            "stdout_truncated": """
            [reference] src/main.py
              project: remotefs
              12: class RemoteFS:
            time_ms: 17
            result_count: 1
            returned_files: 1
            project_scope: remotefs
            """,
            "stderr_truncated": "",
        }
    ]

    results = backend.search("RemoteFS", "/")

    assert results == [
        SearchResult(
            path="src/main.py",
            line=12,
            match="class RemoteFS:",
            context="source=rk_codesearch project=remotefs kind=reference",
        )
    ]
    mock_api.execute.assert_called_once_with(
        "rk_codesearch",
        {
            "action": "search",
            "keywords": "RemoteFS",
            "keyword_mode": "and",
            "search_field": "def",
            "project": "Android14",
            "type": "python",
            "limit": 20,
        },
    )


def test_search_falls_back_to_grep_when_rk_codesearch_has_no_results(backend, mock_api):
    """search should fall back to Grep when rk_codesearch returns no matches."""
    mock_api.execute.side_effect = [
        {
            "status": "COMPLETED",
            "exit_code": 0,
            "stdout_truncated": "time_ms: 10\nresult_count: 0\nreturned_files: 0\nproject_scope: remotefs\n\nNo results",
            "stderr_truncated": "",
        },
        {
            "status": "COMPLETED",
            "exit_code": 0,
            "stdout_truncated": "src/main.py:12:class RemoteFS:",
            "stderr_truncated": "",
        },
    ]

    results = backend.search("RemoteFS", "/")

    assert results == [
        SearchResult(
            path="src/main.py",
            line=12,
            match="class RemoteFS:",
            context="source=grep",
        )
    ]
    assert mock_api.execute.call_args_list[1].args == (
        "Grep",
        {
            "pattern": "RemoteFS",
            "path": ".",
            "output_mode": "content",
            "head_limit": 20,
            "-n": True,
        },
    )


def test_search_prefers_grep_first_for_deep_paths(backend, mock_api):
    """search should prefer Grep first for deep paths where path filtering matters more."""
    mock_api.execute.side_effect = [
        {
            "status": "COMPLETED",
            "exit_code": 0,
            "stdout_truncated": "src/core/engine.py:33:def RemoteFSEngine():",
            "stderr_truncated": "",
        }
    ]

    results = backend.search("RemoteFS", "/src/core")

    assert results == [
        SearchResult(
            path="src/core/engine.py",
            line=33,
            match="def RemoteFSEngine():",
            context="source=grep",
        )
    ]
    mock_api.execute.assert_called_once_with(
        "Grep",
        {
            "pattern": "RemoteFS",
            "path": "src/core",
            "output_mode": "content",
            "head_limit": 20,
            "-n": True,
        },
    )


def test_search_uses_configured_depth_threshold(backend, mock_api):
    """search should respect rk_search_max_depth when choosing the first strategy."""
    backend.rk_search_max_depth = 2
    mock_api.execute.side_effect = [
        {
            "status": "COMPLETED",
            "exit_code": 0,
            "stdout_truncated": """
            [text] src/core/engine.py
              project: remotefs
              33: def RemoteFSEngine():
            """,
            "stderr_truncated": "",
        }
    ]

    results = backend.search("RemoteFS", "/src/core")

    assert results == [
        SearchResult(
            path="src/core/engine.py",
            line=33,
            match="def RemoteFSEngine():",
            context="source=rk_codesearch project=remotefs kind=text",
        )
    ]
    mock_api.execute.assert_called_once_with(
        "rk_codesearch",
        {
            "action": "search",
            "keywords": "RemoteFS",
            "keyword_mode": "and",
            "search_field": "def",
            "project": "Android14",
            "type": "python",
            "limit": 20,
        },
    )


def test_search_index_forces_rk_codesearch(backend, mock_api):
    """search_index should always use rk_codesearch regardless of path depth."""
    mock_api.execute.side_effect = [
        {
            "status": "COMPLETED",
            "exit_code": 0,
            "stdout_truncated": """
            [reference] src/core/engine.py
              project: remotefs
              33: def RemoteFSEngine():
            """,
            "stderr_truncated": "",
        }
    ]

    results = backend.search_index("RemoteFS", "/frameworks/base/core")

    assert results == [
        SearchResult(
            path="src/core/engine.py",
            line=33,
            match="def RemoteFSEngine():",
            context="source=rk_codesearch project=remotefs kind=reference",
        )
    ]
    mock_api.execute.assert_called_once_with(
        "rk_codesearch",
        {
            "action": "search",
            "keywords": "RemoteFS",
            "keyword_mode": "and",
            "search_field": "def",
            "project": "Android14",
            "type": "python",
            "limit": 20,
        },
    )
