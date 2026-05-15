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