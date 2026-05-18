"""HTTP backend implementation for RemoteFS.

This module provides an HTTP-based backend that communicates with a remote
server via REST API.
"""

from typing import List, Dict, Any, Optional
import requests

from .backend import (
    RemoteBackend,
    FileEntry,
    ExecResult,
    SearchResult,
    BackendError,
    FileNotFoundError,
    PermissionDeniedError,
)


class HTTPBackend(RemoteBackend):
    """HTTP-based backend for RemoteFS.

    Communicates with a remote server via REST API.

    Example:
        backend = HTTPBackend(
            base_url="http://remote-server:8080",
            token="your-auth-token"
        )
        content = backend.read_file("/src/main.py")
    """

    def __init__(self, base_url: str, token: str = "", timeout: int = 30):
        """Initialize HTTP backend.

        Args:
            base_url: Base URL of the remote server (e.g., "http://localhost:8080")
            token: Authentication token (optional)
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[bytes] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Make HTTP request with error handling."""
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(
                method,
                url,
                params=params,
                data=data,
                json=json,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response
        except requests.HTTPError as e:
            status_code = e.response.status_code
            if status_code == 404:
                raise FileNotFoundError(f"Not found: {path}", code="NOT_FOUND")
            elif status_code == 403:
                raise PermissionDeniedError(f"Access denied: {path}", code="FORBIDDEN")
            else:
                raise BackendError(
                    f"HTTP error {status_code}: {e}",
                    code=f"HTTP_{status_code}"
                )
        except requests.RequestException as e:
            raise BackendError(f"Connection error: {e}", code="CONNECTION_ERROR")

    # === File Operations ===

    def read_file(self, path: str) -> bytes:
        """Read file content from remote server."""
        response = self._request("GET", "/file", params={"path": path})
        return response.content

    def write_file(self, path: str, content: bytes) -> bool:
        """Write file content to remote server."""
        response = self._request("POST", "/file", params={"path": path}, data=content)
        return response.status_code == 200

    def delete_file(self, path: str) -> bool:
        """Delete file on remote server."""
        response = self._request("DELETE", "/file", params={"path": path})
        return response.status_code == 200

    def file_exists(self, path: str) -> bool:
        """Check if file exists on remote server."""
        try:
            response = self._request("HEAD", "/file", params={"path": path})
            return response.status_code == 200
        except FileNotFoundError:
            return False

    # === Directory Operations ===

    def list_dir(self, path: str) -> List[FileEntry]:
        """List directory contents on remote server."""
        response = self._request("GET", "/dir", params={"path": path})
        entries = []
        for item in response.json():
            entries.append(FileEntry(
                name=item.get("name", ""),
                type=item.get("type", "file"),
                size=item.get("size"),
                mode=item.get("mode"),
                mtime=item.get("mtime"),
            ))
        return entries

    def create_dir(self, path: str) -> bool:
        """Create directory on remote server."""
        response = self._request("POST", "/dir", params={"path": path})
        return response.status_code == 200

    def delete_dir(self, path: str) -> bool:
        """Delete directory on remote server."""
        response = self._request("DELETE", "/dir", params={"path": path})
        return response.status_code == 200

    # === Command Execution ===

    def exec_cmd(self, cmd: str, args: List[str], cwd: Optional[str] = None) -> ExecResult:
        """Execute command on remote server."""
        payload = {"cmd": cmd, "args": args}
        if cwd:
            payload["cwd"] = cwd
        response = self._request("POST", "/exec", json=payload)
        result = response.json()
        return ExecResult(
            stdout=result.get("stdout", "").encode() if isinstance(result.get("stdout"), str) else result.get("stdout", b""),
            stderr=result.get("stderr", "").encode() if isinstance(result.get("stderr"), str) else result.get("stderr", b""),
            exit_code=result.get("exit_code", -1),
        )

    # === Search ===

    def search(self, pattern: str, path: str = "/") -> List[SearchResult]:
        """Search files by content using index."""
        response = self._request("GET", "/search", params={"pattern": pattern, "path": path})
        results = []
        for item in response.json():
            results.append(SearchResult(
                path=item.get("path", ""),
                line=item.get("line", 0),
                match=item.get("match", ""),
                context=item.get("context"),
            ))
        return results

    # === Lifecycle ===

    def disconnect(self) -> None:
        """Close HTTP session."""
        self.session.close()