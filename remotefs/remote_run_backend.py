"""Remote Run backend implementation for RemoteFS."""

from __future__ import annotations

import json
import re
import uuid
import zipfile
from io import BytesIO
from typing import Any, Dict, List, Optional

import requests

from .backend import (
    BackendError,
    ExecResult,
    FileEntry,
    FileNotFoundError,
    PermissionDeniedError,
    RemoteBackend,
    SearchResult,
)


class RemoteRunAPI:
    """Low-level client for the Remote Run agent HTTP API."""

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: int = 30,
        session_id: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.session_id = session_id
        self.session = requests.Session()

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.HTTPError as exc:
            raise BackendError(
                f"Remote Run HTTP error {exc.response.status_code}: {exc}",
                code=f"HTTP_{exc.response.status_code}",
            ) from exc
        except requests.RequestException as exc:
            raise BackendError(
                f"Remote Run connection error: {exc}",
                code="CONNECTION_ERROR",
            ) from exc

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self._request("POST", path, json=payload)
        return response.json()

    def _ensure_session(self) -> str:
        if self.session_id:
            ping = self._post_json(
                "/agent/session/ping",
                {"sessionid": self.session_id, "token": self.token},
            )
            if ping.get("status") not in ("CLOSED", "ERROR"):
                return self.session_id
            self.session_id = None

        opened = self._post_json("/agent/session/open", {"token": self.token})
        session_id = opened.get("sessionid")
        if not session_id:
            raise BackendError("Remote Run did not return a sessionid")
        self.session_id = session_id
        return session_id

    def execute(self, command_id: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        session_id = self._ensure_session()
        return self._post_json(
            "/agent/command/execute",
            {
                "sessionid": session_id,
                "token": self.token,
                "command_id": command_id,
                "parameters": parameters or {},
                "nonce": str(uuid.uuid4()),
            },
        )

    def download_files(self, job_id: str, file_paths: List[str]) -> Dict[str, bytes]:
        session_id = self._ensure_session()
        response = self._request(
            "POST",
            "/agent/files/download",
            json={
                "token": self.token,
                "session_id": session_id,
                "job_id": job_id,
                "file_paths": file_paths,
            },
        )

        files: Dict[str, bytes] = {}
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            for name in archive.namelist():
                files[name] = archive.read(name)
        return files

    def close(self) -> None:
        if not self.session_id:
            return
        try:
            self._post_json(
                "/agent/session/close",
                {"sessionid": self.session_id, "token": self.token},
            )
        finally:
            self.session_id = None
            self.session.close()


class RemoteRunBackend(RemoteBackend):
    """RemoteBackend implementation backed by Remote Run command execution."""

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: int = 30,
        rk_search_max_depth: int = 1,
        rk_codesearch_project: str = "",
        rk_codesearch_type: str = "",
        rk_codesearch_search_field: str = "smart",
        api_client: Optional[RemoteRunAPI] = None,
    ):
        self.rk_search_max_depth = rk_search_max_depth
        self.rk_codesearch_project = rk_codesearch_project
        self.rk_codesearch_type = rk_codesearch_type
        self.rk_codesearch_search_field = rk_codesearch_search_field
        self.api = api_client or RemoteRunAPI(base_url=base_url, token=token, timeout=timeout)

    def _project_path(self, path: str) -> str:
        normalized = path.strip()
        if not normalized or normalized == "/":
            return "."
        return normalized.lstrip("/")

    def _command_output(self, result: Dict[str, Any]) -> str:
        for key in ("stdout", "stdout_truncated", "detail"):
            value = result.get(key)
            if value:
                return str(value)
        for key in ("stderr", "stderr_truncated"):
            value = result.get(key)
            if value:
                return str(value)
        return ""

    def _raise_for_failure(self, result: Dict[str, Any], path: Optional[str] = None) -> None:
        if result.get("status") == "COMPLETED" and result.get("exit_code", 1) == 0:
            return

        message = self._command_output(result) or "Remote Run command failed"
        lowered = message.lower()
        if "does not exist" in lowered or "not found" in lowered:
            raise FileNotFoundError(path or message, code="NOT_FOUND")
        if "permission" in lowered or "denied" in lowered or "forbidden" in lowered:
            raise PermissionDeniedError(message, code="FORBIDDEN")
        raise BackendError(message)

    def _execute(self, command_id: str, parameters: Dict[str, Any], path: Optional[str] = None) -> Dict[str, Any]:
        result = self.api.execute(command_id, parameters)
        self._raise_for_failure(result, path=path)
        return result

    def _execute_json(self, command_id: str, parameters: Dict[str, Any], path: Optional[str] = None) -> Dict[str, Any]:
        result = self._execute(command_id, parameters, path=path)
        output = self._command_output(result)
        if not output:
            return {}
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise BackendError(f"{command_id} returned non-JSON output: {output}") from exc

    def _parse_exec_parameters(self, args: List[str]) -> Dict[str, Any]:
        parameters: Dict[str, Any] = {}
        for arg in args:
            if "=" not in arg:
                raise BackendError(
                    "RemoteRunBackend.exec_cmd expects allowlisted command parameters as key=value pairs"
                )
            key, raw_value = arg.split("=", 1)
            try:
                parameters[key] = json.loads(raw_value)
            except json.JSONDecodeError:
                parameters[key] = raw_value
        return parameters

    def _path_depth(self, path: str) -> int:
        project_path = self._project_path(path)
        if project_path == ".":
            return 0
        return len([part for part in project_path.split("/") if part])

    def _grep_parameters(self, pattern: str, path: str) -> Dict[str, Any]:
        return {
            "pattern": pattern,
            "path": self._project_path(path),
            "output_mode": "content",
            "head_limit": 20,
            "-n": True,
        }

    def _rk_keywords(self, pattern: str) -> str:
        tokens = [token for token in re.split(r"\s+", pattern.strip()) if token]
        return ",".join(tokens) if tokens else pattern

    def _parse_rk_codesearch_output(self, output: str) -> List[SearchResult]:
        results: List[SearchResult] = []
        current_path: Optional[str] = None
        current_kind: Optional[str] = None
        current_project: Optional[str] = None

        for raw_line in output.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("[") and "] " in stripped:
                match = re.match(r"\[(?P<kind>[^\]]+)\]\s+(?P<path>.+)", stripped)
                if match:
                    current_kind = match.group("kind")
                    current_path = match.group("path")
                    current_project = None
                continue
            if stripped.startswith("project:"):
                current_project = stripped.split(":", 1)[1].strip()
                continue
            if stripped.startswith(("time_ms:", "result_count:", "returned_files:", "project_scope:", "RRUN_DONE_", "No results")):
                continue
            match = re.match(r"(?P<line>\d+):\s?(?P<content>.+)", stripped)
            if match and current_path:
                context_parts = ["source=rk_codesearch"]
                if current_project:
                    context_parts.append(f"project={current_project}")
                if current_kind:
                    context_parts.append(f"kind={current_kind}")
                results.append(
                    SearchResult(
                        path=current_path,
                        line=int(match.group("line")),
                        match=match.group("content"),
                        context=" ".join(context_parts),
                    )
                )
        return results

    def _parse_grep_output(self, output: str) -> List[SearchResult]:
        results: List[SearchResult] = []
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = re.match(r"(?P<path>.+?):(?P<line>\d+):(?P<content>.*)", line)
            if not match:
                continue
            results.append(
                SearchResult(
                    path=match.group("path"),
                    line=int(match.group("line")),
                    match=match.group("content"),
                    context="source=grep",
                )
            )
        return results

    def _search_with_rk_codesearch(self, pattern: str) -> List[SearchResult]:
        params = {
            "action": "search",
            "keywords": self._rk_keywords(pattern),
            "keyword_mode": "and",
            "search_field": self.rk_codesearch_search_field,
            "limit": 20,
        }
        if self.rk_codesearch_project:
            params["project"] = self.rk_codesearch_project
        if self.rk_codesearch_type:
            params["type"] = self.rk_codesearch_type
        result = self._execute("rk_codesearch", params)
        return self._parse_rk_codesearch_output(self._command_output(result))

    def _search_with_grep(self, pattern: str, path: str) -> List[SearchResult]:
        result = self._execute("Grep", self._grep_parameters(pattern, path), path=path)
        return self._parse_grep_output(self._command_output(result))

    def read_file(self, path: str) -> bytes:
        project_path = self._project_path(path)
        result = self._execute("download_path", {"path": project_path}, path=path)
        job_id = result.get("job_id")
        output_files = result.get("output_files", [])
        file_paths = [entry["path"] for entry in output_files if "path" in entry]
        if not job_id or not file_paths:
            raise BackendError(f"download_path did not return downloadable files for {path}")

        files = self.api.download_files(job_id, file_paths)
        if project_path in files:
            return files[project_path]
        if len(files) == 1:
            return next(iter(files.values()))
        raise BackendError(f"Unable to resolve downloaded file for {path}")

    def write_file(self, path: str, content: bytes) -> bool:
        project_path = self._project_path(path)
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BackendError(
                "Remote Run Write only supports UTF-8 text payloads; binary writes are unsupported",
                code="UNSUPPORTED_BINARY_WRITE",
            ) from exc

        self._execute("Write", {"file_path": project_path, "content": text}, path=path)
        return True

    def delete_file(self, path: str) -> bool:
        project_path = self._project_path(path)
        self._execute("delete_path", {"path": project_path}, path=path)
        return True

    def file_exists(self, path: str) -> bool:
        project_path = self._project_path(path)
        result = self._execute_json("path_exists", {"path": project_path}, path=path)
        return bool(result.get("exists"))

    def list_dir(self, path: str) -> List[FileEntry]:
        project_path = self._project_path(path)
        result = self._execute_json("list_dir", {"path": project_path}, path=path)
        entries = []
        for item in result.get("entries", []):
            entry_type = "dir" if item.get("type") == "directory" else "file"
            entries.append(
                FileEntry(
                    name=item.get("name", ""),
                    type=entry_type,
                    size=item.get("size_bytes"),
                )
            )
        return entries

    def create_dir(self, path: str) -> bool:
        project_path = self._project_path(path)
        self._execute("make_dir", {"path": project_path}, path=path)
        return True

    def delete_dir(self, path: str) -> bool:
        project_path = self._project_path(path)
        self._execute("delete_path", {"path": project_path}, path=path)
        return True

    def exec_cmd(self, cmd: str, args: List[str], cwd: Optional[str] = None) -> ExecResult:
        if cwd:
            raise BackendError("Remote Run commands are project-scoped and do not support cwd overrides")
        parameters = self._parse_exec_parameters(args)
        result = self._execute(cmd, parameters)
        stdout = self._command_output(result).encode()
        stderr = str(result.get("stderr", result.get("stderr_truncated", ""))).encode()
        return ExecResult(stdout=stdout, stderr=stderr, exit_code=result.get("exit_code", -1))

    def search(self, pattern: str, path: str = "/") -> List[SearchResult]:
        depth = self._path_depth(path)

        if depth <= self.rk_search_max_depth:
            results = self._search_with_rk_codesearch(pattern)
            if results:
                return results
            return self._search_with_grep(pattern, path)

        results = self._search_with_grep(pattern, path)
        if results:
            return results
        return self._search_with_rk_codesearch(pattern)

    def search_index(self, pattern: str, path: str = "/") -> List[SearchResult]:
        """Force index-based search via rk_codesearch."""
        _ = path
        return self._search_with_rk_codesearch(pattern)

    def disconnect(self) -> None:
        self.api.close()
