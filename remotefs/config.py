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