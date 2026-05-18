"""Tests for RemoteFS configuration."""

import os
from pathlib import Path
from remotefs.config import Config


def test_default_config():
    """Test default configuration values."""
    config = Config()
    assert config.server_url == ""
    assert config.token == ""
    assert config.backend_type == "http"
    assert config.rk_search_max_depth == 1
    assert config.rk_codesearch_project == ""
    assert config.rk_codesearch_type == ""
    assert config.rk_codesearch_search_field == "smart"
    assert config.cache_ttl == 5
    assert config.mount_point == Path.home() / "remotefs" / "workspace"


def test_config_with_values():
    """Test configuration with explicit values."""
    config = Config(
        server_url="http://localhost:8080",
        token="test-token",
        backend_type="remote-run",
        rk_search_max_depth=3,
        rk_codesearch_project="Android14",
        rk_codesearch_type="java",
        rk_codesearch_search_field="symbol",
        cache_ttl=10,
        mount_point="/tmp/remotefs",
    )
    assert config.server_url == "http://localhost:8080"
    assert config.token == "test-token"
    assert config.backend_type == "remote-run"
    assert config.rk_search_max_depth == 3
    assert config.rk_codesearch_project == "Android14"
    assert config.rk_codesearch_type == "java"
    assert config.rk_codesearch_search_field == "symbol"
    assert config.cache_ttl == 10
    assert config.mount_point == Path("/tmp/remotefs")


def test_config_from_env(monkeypatch):
    """Test loading config from environment variables."""
    monkeypatch.setenv("REMOTEFS_SERVER", "http://env-server:9000")
    monkeypatch.setenv("REMOTEFS_TOKEN", "env-token")
    monkeypatch.setenv("REMOTEFS_BACKEND", "remote-run")
    monkeypatch.setenv("REMOTEFS_RK_SEARCH_DEPTH", "4")
    monkeypatch.setenv("REMOTEFS_RK_CODESEARCH_PROJECT", "Android15")
    monkeypatch.setenv("REMOTEFS_RK_CODESEARCH_TYPE", "kotlin")
    monkeypatch.setenv("REMOTEFS_RK_CODESEARCH_FIELD", "def")

    config = Config.from_env()
    assert config.server_url == "http://env-server:9000"
    assert config.token == "env-token"
    assert config.backend_type == "remote-run"
    assert config.rk_search_max_depth == 4
    assert config.rk_codesearch_project == "Android15"
    assert config.rk_codesearch_type == "kotlin"
    assert config.rk_codesearch_search_field == "def"


def test_config_from_file(tmp_path):
    """Test loading config from YAML file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
server:
  url: http://file-server:9000
  token: file-token
  backend: remote-run
  rk_search_max_depth: 2
  rk_codesearch_project: Android14
  rk_codesearch_type: python
  rk_codesearch_search_field: full
cache:
  ttl: 15
mount:
  path: /mnt/remotefs
""")

    config = Config.from_file(config_file)
    assert config.server_url == "http://file-server:9000"
    assert config.token == "file-token"
    assert config.backend_type == "remote-run"
    assert config.rk_search_max_depth == 2
    assert config.rk_codesearch_project == "Android14"
    assert config.rk_codesearch_type == "python"
    assert config.rk_codesearch_search_field == "full"
    assert config.cache_ttl == 15
    assert config.mount_point == Path("/mnt/remotefs")


def test_config_load_priority(tmp_path, monkeypatch):
    """Test Config.load() priority: env > file > defaults."""
    # Test 1: Env vars take precedence over file
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
server:
  url: http://file-server:9000
  token: file-token
  backend: http
  rk_search_max_depth: 5
  rk_codesearch_project: Android16
  rk_codesearch_type: rust
  rk_codesearch_search_field: path
""")
    monkeypatch.setenv("REMOTEFS_SERVER", "http://env-server:8000")
    monkeypatch.setenv("REMOTEFS_TOKEN", "env-token")
    monkeypatch.setenv("REMOTEFS_BACKEND", "remote-run")
    monkeypatch.setenv("REMOTEFS_RK_SEARCH_DEPTH", "6")
    monkeypatch.setenv("REMOTEFS_RK_CODESEARCH_PROJECT", "Android17")
    monkeypatch.setenv("REMOTEFS_RK_CODESEARCH_TYPE", "cxx")
    monkeypatch.setenv("REMOTEFS_RK_CODESEARCH_FIELD", "symbol")

    config = Config.load(config_file)
    assert config.server_url == "http://env-server:8000"
    assert config.token == "env-token"
    assert config.backend_type == "remote-run"
    assert config.rk_search_max_depth == 6
    assert config.rk_codesearch_project == "Android17"
    assert config.rk_codesearch_type == "cxx"
    assert config.rk_codesearch_search_field == "symbol"

    # Test 2: File takes precedence over defaults when no env vars
    monkeypatch.delenv("REMOTEFS_SERVER", raising=False)
    monkeypatch.delenv("REMOTEFS_TOKEN", raising=False)
    monkeypatch.delenv("REMOTEFS_BACKEND", raising=False)
    monkeypatch.delenv("REMOTEFS_RK_SEARCH_DEPTH", raising=False)
    monkeypatch.delenv("REMOTEFS_RK_CODESEARCH_PROJECT", raising=False)
    monkeypatch.delenv("REMOTEFS_RK_CODESEARCH_TYPE", raising=False)
    monkeypatch.delenv("REMOTEFS_RK_CODESEARCH_FIELD", raising=False)

    config = Config.load(config_file)
    assert config.server_url == "http://file-server:9000"
    assert config.token == "file-token"
    assert config.backend_type == "http"
    assert config.rk_search_max_depth == 5
    assert config.rk_codesearch_project == "Android16"
    assert config.rk_codesearch_type == "rust"
    assert config.rk_codesearch_search_field == "path"

    # Test 3: Defaults when nothing configured
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("HOME", tmpdir)
        # Use non-existent config path
        fake_config = Path(tmpdir) / "nonexistent.yaml"
        config = Config.load(fake_config)
        assert config.server_url == ""
        assert config.token == ""
        assert config.backend_type == "http"
        assert config.rk_search_max_depth == 1
        assert config.rk_codesearch_project == ""
        assert config.rk_codesearch_type == ""
        assert config.rk_codesearch_search_field == "smart"
        assert config.cache_ttl == 5
