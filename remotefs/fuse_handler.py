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