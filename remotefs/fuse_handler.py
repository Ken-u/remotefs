"""FUSE handler for RemoteFS."""

import os
import stat
from typing import Dict, Any, List, Optional, Tuple
from fuse import FUSE  # type: ignore

from .backend import RemoteBackend, BackendError, FileNotFoundError as BackendFileNotFoundError
from .cache import MetadataCache
from .http_backend import HTTPBackend


class RemoteFS:
    """FUSE filesystem for remote execution.

    This class implements a FUSE filesystem that forwards all operations
    to a backend implementation.

    Args:
        backend: RemoteBackend instance (or HTTPBackend for backward compatibility)
        cache: MetadataCache instance for caching
        *args, **kwargs: Passed to FUSE constructor
    """

    def __init__(
        self,
        backend: Optional[RemoteBackend] = None,
        cache: Optional[MetadataCache] = None,
        client=None,  # Deprecated: use backend instead
        root: str = "/",
    ):
        # Backward compatibility: accept 'client' parameter
        if backend is None and client is not None:
            # Wrap old RemoteClient in HTTPBackend adapter
            self._client = client
            self.backend = None
        else:
            self.backend = backend
            self._client = None

        self.root = root
        self.cache = cache or MetadataCache()
        self._file_handles: Dict[int, Tuple[str, str]] = {}  # fd -> (path, mode)
        self._next_fd = 100

    def main(self, *args, **kwargs):
        """Mount this filesystem via fusepy."""
        return FUSE(self, self.root, *args, **kwargs)

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

        # Query remote - try to list as directory first, then check as file
        try:
            if self.backend:
                entries = self.backend.list_dir(path)
            else:
                # Backward compatibility with old client
                entries = self._client.list_dir(path)
            # If list_dir succeeds, it's a directory
            attr = self._make_dir_attr()
        except (BackendError, Exception):
            # Not a directory, try as file
            try:
                if self.backend:
                    exists = self.backend.file_exists(path)
                else:
                    exists = self._client.exists(path)
                if exists:
                    attr = {"type": "file", "size": 0, "mode": 0o644}
                else:
                    raise FileNotFoundError(path)
            except (BackendError, Exception):
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
            if self.backend:
                remote_entries = self.backend.list_dir(path)
                for entry in remote_entries:
                    entries.append(entry.name)
            else:
                # Backward compatibility
                remote_entries = self._client.list_dir(path)
                for entry in remote_entries:
                    entries.append(entry["name"])
        except (BackendError, Exception):
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

        try:
            if self.backend:
                content = self.backend.read_file(path)
            else:
                content = self._client.read_file(path)
            self.cache.set(f"content:{path}", content, ttl=1)  # Short TTL for content
            return content[offset : offset + size]
        except (BackendError, Exception) as e:
            raise OSError(f"Failed to read file: {e}")

    def write(self, path: str, data: bytes, offset: int, fd: int) -> int:
        """Write to a file.

        Note: This implementation ignores the offset parameter and writes the entire file.
        This is a simplification for the initial version - in production, you'd buffer
        and write at the specified offset.
        """
        try:
            if self.backend:
                self.backend.write_file(path, data)
            else:
                self._client.write_file(path, data)
        except (BackendError, Exception) as e:
            raise OSError(f"Failed to write file: {e}")

        # Invalidate cache
        self.cache.delete(f"content:{path}")
        self.cache.delete(f"attr:{path}")
        self.cache.delete_prefix(f"readdir:{os.path.dirname(path)}")

        return len(data)

    def create(self, path: str, mode: int) -> int:
        """Create a new file."""
        try:
            if self.backend:
                self.backend.write_file(path, b"")
            else:
                self._client.write_file(path, b"")
        except (BackendError, Exception) as e:
            raise OSError(f"Failed to create file: {e}")

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
        try:
            if self.backend:
                self.backend.create_dir(path)
            else:
                self._client.create_dir(path)
        except (BackendError, Exception) as e:
            raise OSError(f"Failed to create directory: {e}")

        self.cache.delete(f"attr:{path}")
        self.cache.delete_prefix(f"readdir:{os.path.dirname(path)}")

    def rmdir(self, path: str) -> None:
        """Remove a directory."""
        try:
            if self.backend:
                self.backend.delete_dir(path)
            else:
                self._client.delete_dir(path)
        except (BackendError, Exception) as e:
            raise OSError(f"Failed to remove directory: {e}")

        self.cache.delete(f"attr:{path}")
        self.cache.delete_prefix(f"readdir:{os.path.dirname(path)}")

    def unlink(self, path: str) -> None:
        """Delete a file."""
        try:
            if self.backend:
                self.backend.delete_file(path)
            else:
                self._client.delete_file(path)
        except (BackendError, Exception) as e:
            raise OSError(f"Failed to delete file: {e}")

        self.cache.delete(f"content:{path}")
        self.cache.delete(f"attr:{path}")
        self.cache.delete_prefix(f"readdir:{os.path.dirname(path)}")
