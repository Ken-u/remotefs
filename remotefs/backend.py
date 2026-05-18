"""Backend abstraction layer for RemoteFS.

This module defines the abstract interface (similar to AOSP HAL) that backend
implementations must follow to integrate with RemoteFS.

Example usage:
    # Create a custom backend
    class MyBackend(RemoteBackend):
        def read_file(self, path: str) -> bytes:
            # Your implementation here
            pass

    # Use with RemoteFS
    backend = MyBackend()
    fs = RemoteFS(backend=backend, ...)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class FileEntry:
    """Represents a file or directory entry."""
    name: str
    type: str  # "file" or "dir"
    size: Optional[int] = None
    mode: Optional[int] = None
    mtime: Optional[float] = None


@dataclass
class ExecResult:
    """Result of command execution."""
    stdout: bytes
    stderr: bytes
    exit_code: int


@dataclass
class SearchResult:
    """Result of index search."""
    path: str
    line: int
    match: str
    context: Optional[str] = None


class BackendError(Exception):
    """Base exception for backend errors."""

    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.code = code


class FileNotFoundError(BackendError):
    """Raised when a file or directory does not exist."""
    pass


class PermissionDeniedError(BackendError):
    """Raised when access is denied."""
    pass


class RemoteBackend(ABC):
    """Abstract base class for RemoteFS backends.

    Implement this class to create a custom backend for RemoteFS.

    Example:
        class HTTPBackend(RemoteBackend):
            def __init__(self, base_url: str, token: str = ""):
                self.base_url = base_url
                self.token = token

            def read_file(self, path: str) -> bytes:
                # Your implementation
                pass

            # ... implement other methods
    """

    # === File Operations ===

    @abstractmethod
    def read_file(self, path: str) -> bytes:
        """Read file content.

        Args:
            path: File path (absolute, starting with /)

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file does not exist
            PermissionDeniedError: If access is denied
            BackendError: For other errors
        """
        pass

    @abstractmethod
    def write_file(self, path: str, content: bytes) -> bool:
        """Write file content.

        Args:
            path: File path (absolute, starting with /)
            content: File content as bytes

        Returns:
            True if successful

        Raises:
            PermissionDeniedError: If access is denied
            BackendError: For other errors
        """
        pass

    @abstractmethod
    def delete_file(self, path: str) -> bool:
        """Delete a file.

        Args:
            path: File path (absolute, starting with /)

        Returns:
            True if successful

        Raises:
            FileNotFoundError: If file does not exist
            PermissionDeniedError: If access is denied
            BackendError: For other errors
        """
        pass

    @abstractmethod
    def file_exists(self, path: str) -> bool:
        """Check if a file exists.

        Args:
            path: File path (absolute, starting with /)

        Returns:
            True if file exists

        Raises:
            BackendError: For errors other than "not found"
        """
        pass

    # === Directory Operations ===

    @abstractmethod
    def list_dir(self, path: str) -> List[FileEntry]:
        """List directory contents.

        Args:
            path: Directory path (absolute, starting with /)

        Returns:
            List of file/directory entries

        Raises:
            FileNotFoundError: If directory does not exist
            PermissionDeniedError: If access is denied
            BackendError: For other errors
        """
        pass

    @abstractmethod
    def create_dir(self, path: str) -> bool:
        """Create a directory.

        Args:
            path: Directory path (absolute, starting with /)

        Returns:
            True if successful

        Raises:
            PermissionDeniedError: If access is denied
            BackendError: For other errors
        """
        pass

    @abstractmethod
    def delete_dir(self, path: str) -> bool:
        """Delete a directory.

        Args:
            path: Directory path (absolute, starting with /)

        Returns:
            True if successful

        Raises:
            FileNotFoundError: If directory does not exist
            PermissionDeniedError: If access is denied
            BackendError: For other errors
        """
        pass

    # === Command Execution ===

    @abstractmethod
    def exec_cmd(self, cmd: str, args: List[str], cwd: Optional[str] = None) -> ExecResult:
        """Execute a command.

        Args:
            cmd: Command name
            args: Command arguments
            cwd: Working directory (optional)

        Returns:
            ExecResult with stdout, stderr, and exit_code

        Raises:
            FileNotFoundError: If command not found
            PermissionDeniedError: If execution is denied
            BackendError: For other errors
        """
        pass

    # === Search (Optional) ===

    def search(self, pattern: str, path: str = "/") -> List[SearchResult]:
        """Search files by content using index.

        This is an optional method. Backends without index search can leave
        this unimplemented or raise NotImplementedError.

        Args:
            pattern: Search pattern (e.g., grep pattern)
            path: Search root path

        Returns:
            List of search results

        Raises:
            NotImplementedError: If search is not supported
            BackendError: For other errors
        """
        raise NotImplementedError("Search not supported by this backend")

    # === Lifecycle (Optional) ===

    def connect(self) -> None:
        """Initialize backend connection.

        Optional method for backends that need explicit connection setup.
        """
        pass

    def disconnect(self) -> None:
        """Close backend connection.

        Optional method for backends that need explicit cleanup.
        """
        pass

    def is_connected(self) -> bool:
        """Check if backend is connected.

        Returns:
            True if connected

        Optional method for backends with connection state.
        """
        return True
