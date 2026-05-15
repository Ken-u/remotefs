# RemoteFS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现基于 FUSE 的远程文件系统，让智能体能够无感知地操作远程文件

**Architecture:** Python + fusepy 实现 FUSE 文件系统，HTTP 客户端转发请求到远程执行插件

**Tech Stack:** Python 3.8+, fusepy, requests, pytest

---

## File Structure

```
remotefs/
├── remotefs/
│   ├── __init__.py          # 包入口
│   ├── fuse_handler.py      # FUSE 操作实现
│   ├── remote_client.py     # HTTP 客户端
│   ├── cache.py             # 元数据缓存
│   ├── config.py            # 配置管理
│   └── cli.py               # 命令行入口
├── tests/
│   ├── __init__.py
│   ├── test_cache.py
│   ├── test_remote_client.py
│   └── test_fuse_handler.py
├── pyproject.toml
└── README.md
```

---

## Task 1: 项目骨架 + 配置模块

**Files:**
- Create: `remotefs/__init__.py`
- Create: `remotefs/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`
- Create: `pyproject.toml`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "remotefs"
version = "0.1.0"
description = "FUSE-based remote filesystem for AI agents"
requires-python = ">=3.8"
dependencies = [
    "fusepy>=3.0.1",
    "requests>=2.28.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
]

[project.scripts]
remotefs = "remotefs.cli:main"
```

- [ ] **Step 2: 创建 remotefs/__init__.py**

```python
"""RemoteFS - FUSE-based remote filesystem for AI agents."""

__version__ = "0.1.0"
```

- [ ] **Step 3: 创建 remotefs/config.py**

```python
"""Configuration management for RemoteFS."""

import os
from pathlib import Path
from typing import Optional
import yaml


class Config:
    """RemoteFS configuration."""

    DEFAULT_TTL = 5  # seconds
    DEFAULT_MOUNT_POINT = "~/remotefs/workspace"

    def __init__(
        self,
        server_url: Optional[str] = None,
        token: Optional[str] = None,
        cache_ttl: int = DEFAULT_TTL,
        mount_point: Optional[str] = None,
    ):
        self.server_url = server_url or ""
        self.token = token or ""
        self.cache_ttl = cache_ttl
        self.mount_point = Path(mount_point or self.DEFAULT_MOUNT_POINT).expanduser()

    @classmethod
    def from_env(cls) -> "Config":
        """Load config from environment variables."""
        return cls(
            server_url=os.environ.get("REMOTEFS_SERVER"),
            token=os.environ.get("REMOTEFS_TOKEN"),
        )

    @classmethod
    def from_file(cls, path: Path) -> "Config":
        """Load config from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        server = data.get("server", {})
        cache = data.get("cache", {})
        mount = data.get("mount", {})
        return cls(
            server_url=server.get("url"),
            token=server.get("token"),
            cache_ttl=cache.get("ttl", cls.DEFAULT_TTL),
            mount_point=mount.get("path"),
        )

    @classmethod
    def load(
        cls,
        config_path: Optional[Path] = None,
    ) -> "Config":
        """Load config with priority: env > file > defaults."""
        # Check environment first
        if os.environ.get("REMOTEFS_SERVER"):
            return cls.from_env()

        # Then config file
        if config_path and config_path.exists():
            return cls.from_file(config_path)

        # Default config file location
        default_config = Path.home() / ".config" / "remotefs" / "config.yaml"
        if default_config.exists():
            return cls.from_file(default_config)

        # Empty config (will need CLI args)
        return cls()
```

- [ ] **Step 4: 创建 tests/test_config.py**

```python
"""Tests for RemoteFS configuration."""

import os
from pathlib import Path
from remotefs.config import Config


def test_default_config():
    """Test default configuration values."""
    config = Config()
    assert config.server_url == ""
    assert config.token == ""
    assert config.cache_ttl == 5
    assert config.mount_point == Path.home() / "remotefs" / "workspace"


def test_config_with_values():
    """Test configuration with explicit values."""
    config = Config(
        server_url="http://localhost:8080",
        token="test-token",
        cache_ttl=10,
        mount_point="/tmp/remotefs",
    )
    assert config.server_url == "http://localhost:8080"
    assert config.token == "test-token"
    assert config.cache_ttl == 10
    assert config.mount_point == Path("/tmp/remotefs")


def test_config_from_env(monkeypatch):
    """Test loading config from environment variables."""
    monkeypatch.setenv("REMOTEFS_SERVER", "http://env-server:9000")
    monkeypatch.setenv("REMOTEFS_TOKEN", "env-token")

    config = Config.from_env()
    assert config.server_url == "http://env-server:9000"
    assert config.token == "env-token"


def test_config_from_file(tmp_path):
    """Test loading config from YAML file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
server:
  url: http://file-server:9000
  token: file-token
cache:
  ttl: 15
mount:
  path: /mnt/remotefs
""")

    config = Config.from_file(config_file)
    assert config.server_url == "http://file-server:9000"
    assert config.token == "file-token"
    assert config.cache_ttl == 15
    assert config.mount_point == Path("/mnt/remotefs")
```

- [ ] **Step 5: Run tests to verify they fail (no implementation yet)**

```bash
cd /home/linaro/remotefs && python -m pytest tests/test_config.py -v
```
Expected: Tests fail with import errors or assertion failures

- [ ] **Step 6: Implement Config class (already done in Step 3)**

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd /home/linaro/remotefs && python -m pytest tests/test_config.py -v
```
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
cd /home/linaro/remotefs
git add -A
git commit -m "feat: add configuration module with tests"
```

---

## Task 2: 远程 HTTP 客户端

**Files:**
- Create: `remotefs/remote_client.py`
- Create: `tests/test_remote_client.py`

- [ ] **Step 1: 创建 remotefs/remote_client.py**

```python
"""HTTP client for remote execution plugin."""

from typing import List, Dict, Any, Optional
import requests


class RemoteError(Exception):
    """Error from remote server."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class RemoteClient:
    """Client for remote execution plugin API."""

    def __init__(self, base_url: str, token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make HTTP request with error handling."""
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response
        except requests.HTTPError as e:
            raise RemoteError(str(e), status_code=e.response.status_code)
        except requests.RequestException as e:
            raise RemoteError(f"Connection error: {e}")

    def read_file(self, path: str) -> bytes:
        """Read file content from remote."""
        response = self._request("GET", "/file", params={"path": path})
        return response.content

    def write_file(self, path: str, content: bytes) -> bool:
        """Write file content to remote."""
        response = self._request("POST", "/file", params={"path": path}, data=content)
        return response.status_code == 200

    def delete_file(self, path: str) -> bool:
        """Delete file on remote."""
        response = self._request("DELETE", "/file", params={"path": path})
        return response.status_code == 200

    def list_dir(self, path: str) -> List[Dict[str, Any]]:
        """List directory contents on remote."""
        response = self._request("GET", "/dir", params={"path": path})
        return response.json()

    def create_dir(self, path: str) -> bool:
        """Create directory on remote."""
        response = self._request("POST", "/dir", params={"path": path})
        return response.status_code == 200

    def delete_dir(self, path: str) -> bool:
        """Delete directory on remote."""
        response = self._request("DELETE", "/dir", params={"path": path})
        return response.status_code == 200

    def exists(self, path: str) -> bool:
        """Check if path exists on remote."""
        response = self._request("HEAD", "/file", params={"path": path})
        return response.status_code == 200

    def exec_cmd(self, cmd: str, args: List[str], cwd: str = "") -> Dict[str, Any]:
        """Execute command on remote."""
        payload = {"cmd": cmd, "args": args}
        if cwd:
            payload["cwd"] = cwd
        response = self._request("POST", "/exec", json=payload)
        return response.json()

    def search(self, pattern: str, path: str = "/") -> List[Dict[str, Any]]:
        """Search files by content using index."""
        response = self._request("GET", "/search", params={"pattern": pattern, "path": path})
        return response.json()
```

- [ ] **Step 2: 创建 tests/test_remote_client.py**

```python
"""Tests for RemoteFS remote client."""

import pytest
from unittest.mock import Mock, patch
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
        mock_request.return_value.raise_for_status.side_effect = Exception("HTTP 404")
        mock_request.return_value.status_code = 404

        with pytest.raises(RemoteError) as exc_info:
            client.read_file("/nonexistent")
        assert exc_info.value.status_code == 404
```

- [ ] **Step 3: Run tests**

```bash
cd /home/linaro/remotefs && python -m pytest tests/test_remote_client.py -v
```

- [ ] **Step 4: Fix any failing tests**

- [ ] **Step 5: Commit**

```bash
cd /home/linaro/remotefs
git add -A
git commit -m "feat: add remote HTTP client with tests"
```

---

## Task 3: 元数据缓存模块

**Files:**
- Create: `remotefs/cache.py`
- Create: `tests/test_cache.py`

- [ ] **Step 1: 创建 remotefs/cache.py**

```python
"""Metadata cache for RemoteFS."""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """A cached metadata entry."""

    value: Any
    expires_at: float

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        return time.time() > self.expires_at


class MetadataCache:
    """TTL-based metadata cache."""

    def __init__(self, ttl: int = 5):
        self._cache: Dict[str, CacheEntry] = {}
        self.ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, or None if missing/expired."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.is_expired():
            del self._cache[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        expires_at = time.time() + (ttl or self.ttl)
        self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    def delete(self, key: str) -> None:
        """Delete key from cache."""
        self._cache.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        """Delete all keys with given prefix."""
        to_delete = [k for k in self._cache if k.startswith(prefix)]
        for key in to_delete:
            del self._cache[key]

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        return self.get(key) is not None
```

- [ ] **Step 2: 创建 tests/test_cache.py**

```python
"""Tests for RemoteFS metadata cache."""

import time
from remotefs.cache import MetadataCache, CacheEntry


def test_cache_set_get():
    """Test basic set and get."""
    cache = MetadataCache(ttl=5)
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"


def test_cache_missing_key():
    """Test getting missing key returns None."""
    cache = MetadataCache()
    assert cache.get("nonexistent") is None


def test_cache_expiration():
    """Test cache entry expires after TTL."""
    cache = MetadataCache(ttl=1)
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"
    time.sleep(1.1)
    assert cache.get("key1") is None


def test_cache_delete():
    """Test deleting a key."""
    cache = MetadataCache()
    cache.set("key1", "value1")
    cache.delete("key1")
    assert cache.get("key1") is None


def test_cache_delete_prefix():
    """Test deleting keys by prefix."""
    cache = MetadataCache()
    cache.set("/src/file1.py", "content1")
    cache.set("/src/file2.py", "content2")
    cache.set("/tests/test.py", "content3")

    cache.delete_prefix("/src/")

    assert cache.get("/src/file1.py") is None
    assert cache.get("/src/file2.py") is None
    assert cache.get("/tests/test.py") == "content3"


def test_cache_clear():
    """Test clearing all cache entries."""
    cache = MetadataCache()
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.clear()
    assert cache.get("key1") is None
    assert cache.get("key2") is None


def test_cache_exists():
    """Test checking if key exists."""
    cache = MetadataCache(ttl=1)
    cache.set("key1", "value1")
    assert cache.exists("key1") is True
    time.sleep(1.1)
    assert cache.exists("key1") is False
```

- [ ] **Step 3: Run tests**

```bash
cd /home/linaro/remotefs && python -m pytest tests/test_cache.py -v
```

- [ ] **Step 4: Commit**

```bash
cd /home/linaro/remotefs
git add -A
git commit -m "feat: add metadata cache with TTL support"
```

---

## Task 4: FUSE 处理器

**Files:**
- Create: `remotefs/fuse_handler.py`
- Create: `tests/test_fuse_handler.py`

- [ ] **Step 1: 创建 remotefs/fuse_handler.py**

```python
"""FUSE handler for RemoteFS."""

import os
import stat
from typing import Dict, Any, List, Optional, Tuple
from fusepy import FUSE  # type: ignore

from .remote_client import RemoteClient, RemoteError
from .cache import MetadataCache


class RemoteFS(FUSE):
    """FUSE filesystem for remote execution."""

    def __init__(self, client: RemoteClient, cache: MetadataCache, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = client
        self.cache = cache
        self._file_handles: Dict[int, Tuple[str, str]] = {}  # fd -> (path, mode)
        self._next_fd = 100

    def _get_attr(self, path: str) -> Dict[str, Any]:
        """Get file/directory attributes."""
        # Check cache first
        cached = self.cache.get(f"attr:{path}")
        if cached:
            return cached

        # Check if it's a virtual path
        if path == "/.local":
            return self._make_dir_attr()
        if path.startswith("/.local/bin"):
            return self._make_cmd_attr(path)

        # Query remote
        try:
            if self.client.exists(path):
                # It's a file
                attr = {"type": "file", "size": 0, "mode": 0o644}
            else:
                # Try as directory
                self.client.list_dir(path)
                attr = self._make_dir_attr()
        except RemoteError:
            raise FileNotFoundError(path)

        self.cache.set(f"attr:{path}", attr)
        return attr

    def _make_dir_attr(self, mode: int = 0o755) -> Dict[str, Any]:
        """Create directory attributes."""
        return {"type": "dir", "mode": mode}

    def _make_cmd_attr(self, path: str) -> Dict[str, Any]:
        """Create executable file attributes for virtual commands."""
        return {"type": "file", "mode": 0o755}

    def getattr(self, path: str) -> Dict[str, Any]:
        """Get file/directory attributes."""
        attr = self._get_attr(path)

        if attr["type"] == "dir":
            return {
                "st_mode": stat.S_IFDIR | attr.get("mode", 0o755),
                "st_nlink": 2,
            }
        else:
            return {
                "st_mode": stat.S_IFREG | attr.get("mode", 0o644),
                "st_nlink": 1,
                "st_size": attr.get("size", 0),
            }

    def readdir(self, path: str) -> List[str]:
        """List directory contents."""
        # Check cache first
        cached = self.cache.get(f"readdir:{path}")
        if cached:
            return cached

        entries = [".", ".."]

        # Add .local for root
        if path == "/":
            entries.append(".local")

        # Query remote for real directories
        try:
            remote_entries = self.client.list_dir(path)
            for entry in remote_entries:
                entries.append(entry["name"])
        except RemoteError:
            pass

        self.cache.set(f"readdir:{path}", entries)
        return entries

    def open(self, path: str, mode: str) -> int:
        """Open a file."""
        fd = self._next_fd
        self._next_fd += 1
        self._file_handles[fd] = (path, mode)
        return fd

    def read(self, path: str, size: int, offset: int, fd: int) -> bytes:
        """Read from a file."""
        # Check cache first
        cached = self.cache.get(f"content:{path}")
        if cached:
            return cached[offset : offset + size]

        content = self.client.read_file(path)
        self.cache.set(f"content:{path}", content, ttl=1)  # Short TTL for content
        return content[offset : offset + size]

    def write(self, path: str, data: bytes, offset: int, fd: int) -> int:
        """Write to a file."""
        # For simplicity, write the whole file
        # In production, you'd buffer and write at offset
        self.client.write_file(path, data)

        # Invalidate cache
        self.cache.delete(f"content:{path}")
        self.cache.delete(f"attr:{path}")
        self.cache.delete_prefix(f"readdir:{os.path.dirname(path)}")

        return len(data)

    def create(self, path: str, mode: int) -> int:
        """Create a new file."""
        self.client.write_file(path, b"")
        self.cache.delete(f"attr:{path}")
        self.cache.delete_prefix(f"readdir:{os.path.dirname(path)}")

        fd = self._next_fd
        self._next_fd += 1
        self._file_handles[fd] = (path, "w")
        return fd

    def release(self, path: str, fd: int) -> None:
        """Release a file handle."""
        self._file_handles.pop(fd, None)

    def mkdir(self, path: str, mode: int) -> None:
        """Create a directory."""
        self.client.create_dir(path)
        self.cache.delete(f"attr:{path}")
        self.cache.delete_prefix(f"readdir:{os.path.dirname(path)}")

    def rmdir(self, path: str) -> None:
        """Remove a directory."""
        self.client.delete_dir(path)
        self.cache.delete(f"attr:{path}")
        self.cache.delete_prefix(f"readdir:{os.path.dirname(path)}")

    def unlink(self, path: str) -> None:
        """Delete a file."""
        self.client.delete_file(path)
        self.cache.delete(f"content:{path}")
        self.cache.delete(f"attr:{path}")
        self.cache.delete_prefix(f"readdir:{os.path.dirname(path)}")
```

- [ ] **Step 2: 创建 tests/test_fuse_handler.py**

```python
"""Tests for RemoteFS FUSE handler."""

import pytest
from unittest.mock import Mock, patch
from remotefs.fuse_handler import RemoteFS
from remotefs.remote_client import RemoteClient
from remotefs.cache import MetadataCache


@pytest.fixture
def mock_client():
    """Create mock remote client."""
    client = Mock(spec=RemoteClient)
    client.exists.return_value = True
    client.list_dir.return_value = [
        {"name": "file1.txt", "type": "file"},
        {"name": "subdir", "type": "dir"},
    ]
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


def test_getattr_dir(fs, mock_client):
    """Test getting directory attributes."""
    mock_client.exists.return_value = False
    attr = fs.getattr("/test")
    assert "st_mode" in attr
    assert attr["st_nlink"] == 2


def test_readdir(fs, mock_client):
    """Test listing directory."""
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
```

- [ ] **Step 3: Run tests**

```bash
cd /home/linaro/remotefs && python -m pytest tests/test_fuse_handler.py -v
```

- [ ] **Step 4: Commit**

```bash
cd /home/linaro/remotefs
git add -A
git commit -m "feat: add FUSE handler implementation"
```

---

## Task 5: 命令行工具

**Files:**
- Create: `remotefs/cli.py`

- [ ] **Step 1: 创建 remotefs/cli.py**

```python
"""Command-line interface for RemoteFS."""

import argparse
import sys
from pathlib import Path

from .config import Config
from .remote_client import RemoteClient
from .cache import MetadataCache
from .fuse_handler import RemoteFS


def cmd_mount(args):
    """Mount the remote filesystem."""
    config = Config.load(args.config)

    # Override with CLI args
    if args.server:
        config.server_url = args.server
    if args.token:
        config.token = args.token
    if args.mount_point:
        config.mount_point = Path(args.mount_point).expanduser()

    if not config.server_url:
        print("Error: No server URL provided", file=sys.stderr)
        print("Use --server or set REMOTEFS_SERVER env var", file=sys.stderr)
        sys.exit(1)

    # Create mount point
    config.mount_point.mkdir(parents=True, exist_ok=True)

    # Create client and cache
    client = RemoteClient(config.server_url, config.token)
    cache = MetadataCache(ttl=config.cache_ttl)

    # Mount
    print(f"Mounting RemoteFS at {config.mount_point}")
    fs = RemoteFS(client=client, cache=cache, root=str(config.mount_point))
    fs.main()


def cmd_unmount(args):
    """Unmount the remote filesystem."""
    mount_point = Path(args.mount_point).expanduser()

    if not mount_point.exists():
        print(f"Error: {mount_point} does not exist", file=sys.stderr)
        sys.exit(1)

    # Unmount using fusermount
    import subprocess
    try:
        subprocess.run(["fusermount", "-u", str(mount_point)], check=True)
        print(f"Unmounted {mount_point}")
    except subprocess.CalledProcessError as e:
        print(f"Error unmounting: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args):
    """Show connection status."""
    config = Config.load(args.config)

    if not config.server_url:
        print("Not configured")
        sys.exit(1)

    client = RemoteClient(config.server_url, config.token)
    try:
        client.exists("/")
        print(f"Connected to {config.server_url}")
        print(f"Mount point: {config.mount_point}")
        print(f"Cache TTL: {config.cache_ttl}s")
    except Exception as e:
        print(f"Disconnected: {e}")
        sys.exit(1)


def cmd_config(args):
    """Show current configuration."""
    config = Config.load(args.config)

    print(f"Server URL: {config.server_url or '(not set)'}")
    print(f"Token: {'(set)' if config.token else '(not set)'}")
    print(f"Cache TTL: {config.cache_ttl}s")
    print(f"Mount point: {config.mount_point}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(prog="remotefs", description="RemoteFS - FUSE remote filesystem")
    parser.add_argument("--config", type=Path, help="Config file path")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # mount
    mount_parser = subparsers.add_parser("mount", help="Mount remote filesystem")
    mount_parser.add_argument("--server", help="Server URL")
    mount_parser.add_argument("--token", help="Auth token")
    mount_parser.add_argument("mount_point", nargs="?", help="Mount point path")
    mount_parser.set_defaults(func=cmd_mount)

    # unmount
    unmount_parser = subparsers.add_parser("unmount", help="Unmount remote filesystem")
    unmount_parser.add_argument("mount_point", help="Mount point path")
    unmount_parser.set_defaults(func=cmd_unmount)

    # status
    status_parser = subparsers.add_parser("status", help="Show connection status")
    status_parser.set_defaults(func=cmd_status)

    # config
    config_parser = subparsers.add_parser("config", help="Show configuration")
    config_parser.set_defaults(func=cmd_config)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 测试命令行工具**

```bash
cd /home/linaro/remotefs && python -m remotefs.cli --help
cd /home/linaro/remotefs && python -m remotefs.cli config
```

- [ ] **Step 3: Commit**

```bash
cd /home/linaro/remotefs
git add -A
git commit -m "feat: add command-line interface"
```

---

## Task 6: README 文档

**Files:**
- Create: `README.md`

- [ ] **Step 1: 创建 README.md**

```markdown
# RemoteFS

FUSE-based remote filesystem for AI agents.

## Features

- **Transparent access** - Agents operate remote files as if local
- **Full command support** - All commands forwarded to remote environment
- **Fast code search** - Index-based search for large codebases (AOSP-scale)
- **Cross-platform** - Linux, macOS, Windows (via WinFsp)

## Installation

```bash
pip install -e .
```

### System Dependencies

- **Linux**: `sudo apt install libfuse2` or `sudo apt install fuse`
- **macOS**: `brew install --cask macfuse`
- **Windows**: Install [WinFsp](https://winfsp.dev/rel/)

## Configuration

Create `~/.config/remotefs/config.yaml`:

```yaml
server:
  url: "http://your-server:8080"
  token: "your-token"
cache:
  ttl: 5
mount:
  path: "~/remotefs/workspace"
```

Or use environment variables:

```bash
export REMOTEFS_SERVER=http://your-server:8080
export REMOTEFS_TOKEN=your-token
```

## Usage

### Mount

```bash
remotefs mount
# or
remotefs mount --server http://server:8080 --token TOKEN /path/to/mount
```

### Unmount

```bash
remotefs unmount ~/remotefs/workspace
```

### Status

```bash
remotefs status
```

### Configuration

```bash
remotefs config
```

## Remote API

Your remote server must implement these endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/file?path=<path>` | Read file |
| POST | `/file?path=<path>` | Write file |
| DELETE | `/file?path=<path>` | Delete file |
| HEAD | `/file?path=<path>` | Check existence |
| GET | `/dir?path=<path>` | List directory |
| POST | `/dir?path=<path>` | Create directory |
| DELETE | `/dir?path=<path>` | Delete directory |
| POST | `/exec` | Execute command |
| GET | `/search?pattern=<pattern>&path=<path>` | Index search |

### `/exec` Request

```json
{
  "cmd": "make",
  "args": ["-j4"],
  "cwd": "/path/to/working/dir"
}
```

### `/exec` Response

```json
{
  "stdout": "...",
  "stderr": "...",
  "exit_code": 0
}
```

### `/search` Response

```json
[
  {"path": "/src/foo.py", "line": 10, "match": "def foo()"}
]
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/
```

## License

MIT
```

- [ ] **Step 2: Commit**

```bash
cd /home/linaro/remotefs
git add -A
git commit -m "docs: add README"
```

---

## Task 7: 集成测试 + 端到端验证

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 创建集成测试**

```python
"""Integration tests for RemoteFS."""

import pytest
import subprocess
from pathlib import Path
from remotefs.config import Config
from remotefs.remote_client import RemoteClient
from remotefs.cache import MetadataCache
from remotefs.fuse_handler import RemoteFS


@pytest.fixture
def mock_server():
    """Start mock server for integration tests."""
    # This would start a test server
    # For now, skip if no real server
    pytest.skip("Requires mock server")


def test_full_workflow(mock_server, tmp_path):
    """Test complete workflow."""
    mount_point = tmp_path / "mount"
    mount_point.mkdir()

    config = Config(
        server_url="http://localhost:8080",
        token="test",
        mount_point=str(mount_point),
    )

    client = RemoteClient(config.server_url, config.token)
    cache = MetadataCache(ttl=config.cache_ttl)

    # Create FUSE filesystem (in background)
    fs = RemoteFS(client=client, cache=cache, root=str(mount_point))

    # Test operations would go here
    # This requires running FUSE in background thread
    pass
```

- [ ] **Step 2: 手动端到端测试**

```bash
# 1. 安装依赖
pip install -e .

# 2. 查看帮助
remotefs --help

# 3. 查看配置
remotefs config

# 4. 挂载 (需要真实服务器)
# remotefs mount --server http://your-server --token TOKEN

# 5. 验证智能体工具
# Read /home/linaro/remotefs/workspace/some-file.py
# Bash: ls ~/remotefs/workspace/
# Bash: grep -r "pattern" ~/remotefs/workspace/
```

- [ ] **Step 3: Commit**

```bash
cd /home/linaro/remotefs
git add -A
git commit -m "test: add integration test skeleton"
```

---

## 完成标准

- [ ] 所有单元测试通过
- [ ] 命令行工具可用
- [ ] README 文档完整
- [ ] 能够挂载并验证基本文件操作

---

## 注意事项

1. **API 适配** - 实际接口需要根据你现有的远程执行插件调整
2. **FUSE 权限** - 某些系统需要额外配置才能允许非 root 用户挂载
3. **错误处理** - 生产环境需要更完善的错误处理和日志
4. **性能优化** - 大文件读取、并发请求等可能需要优化
