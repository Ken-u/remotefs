"""RemoteFS - FUSE-based remote filesystem for AI agents.

This package provides a FUSE-based filesystem that allows AI agents to
transparently access remote files and execute commands.

Basic usage:
    from remotefs import HTTPBackend, RemoteFS, MetadataCache

    backend = HTTPBackend("http://server:8080", token="xxx")
    cache = MetadataCache(ttl=5)
    fs = RemoteFS(backend=backend, cache=cache, root="/mnt/remote")

Custom backend:
    from remotefs import RemoteBackend, FileEntry, ExecResult

    class MyBackend(RemoteBackend):
        def read_file(self, path: str) -> bytes:
            # Your implementation
            pass

        # ... implement other abstract methods
"""

__version__ = "0.1.0"

# Core backend abstraction
from .backend import (
    RemoteBackend,
    FileEntry,
    ExecResult,
    SearchResult,
    BackendError,
    FileNotFoundError,
    PermissionDeniedError,
)

# Built-in HTTP backend
from .http_backend import HTTPBackend

# FUSE filesystem
from .fuse_handler import RemoteFS

# Supporting modules
from .cache import MetadataCache
from .config import Config

__all__ = [
    # Backend abstraction
    "RemoteBackend",
    "FileEntry",
    "ExecResult",
    "SearchResult",
    "BackendError",
    "FileNotFoundError",
    "PermissionDeniedError",
    # Built-in backends
    "HTTPBackend",
    # FUSE filesystem
    "RemoteFS",
    # Supporting
    "MetadataCache",
    "Config",
]