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