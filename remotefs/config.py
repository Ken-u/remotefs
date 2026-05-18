"""Configuration management for RemoteFS."""

import os
from pathlib import Path
from typing import Optional
import yaml


class Config:
    """RemoteFS configuration."""

    DEFAULT_TTL = 5  # seconds
    DEFAULT_MOUNT_POINT = "~/remotefs/workspace"
    DEFAULT_RK_SEARCH_MAX_DEPTH = 1

    def __init__(
        self,
        server_url: Optional[str] = None,
        token: Optional[str] = None,
        backend_type: str = "http",
        rk_search_max_depth: int = DEFAULT_RK_SEARCH_MAX_DEPTH,
        rk_codesearch_project: Optional[str] = None,
        rk_codesearch_type: Optional[str] = None,
        rk_codesearch_search_field: str = "smart",
        cache_ttl: int = DEFAULT_TTL,
        mount_point: Optional[str] = None,
    ):
        self.server_url = server_url or ""
        self.token = token or ""
        self.backend_type = backend_type
        self.rk_search_max_depth = rk_search_max_depth
        self.rk_codesearch_project = rk_codesearch_project or ""
        self.rk_codesearch_type = rk_codesearch_type or ""
        self.rk_codesearch_search_field = rk_codesearch_search_field
        self.cache_ttl = cache_ttl
        self.mount_point = Path(mount_point or self.DEFAULT_MOUNT_POINT).expanduser()

    @classmethod
    def from_env(cls) -> "Config":
        """Load config from environment variables."""
        return cls(
            server_url=os.environ.get("REMOTEFS_SERVER"),
            token=os.environ.get("REMOTEFS_TOKEN"),
            backend_type=os.environ.get("REMOTEFS_BACKEND", "http"),
            rk_search_max_depth=int(
                os.environ.get("REMOTEFS_RK_SEARCH_DEPTH", cls.DEFAULT_RK_SEARCH_MAX_DEPTH)
            ),
            rk_codesearch_project=os.environ.get("REMOTEFS_RK_CODESEARCH_PROJECT"),
            rk_codesearch_type=os.environ.get("REMOTEFS_RK_CODESEARCH_TYPE"),
            rk_codesearch_search_field=os.environ.get("REMOTEFS_RK_CODESEARCH_FIELD", "smart"),
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
            backend_type=server.get("backend", "http"),
            rk_search_max_depth=server.get("rk_search_max_depth", cls.DEFAULT_RK_SEARCH_MAX_DEPTH),
            rk_codesearch_project=server.get("rk_codesearch_project"),
            rk_codesearch_type=server.get("rk_codesearch_type"),
            rk_codesearch_search_field=server.get("rk_codesearch_search_field", "smart"),
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
