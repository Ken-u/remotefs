"""Tests for CLI import behavior."""

import importlib
import sys
import pytest


def test_cli_module_import_does_not_require_fuse(monkeypatch):
    """Importing the CLI module should not import fuse_handler eagerly."""
    sys.modules.pop("remotefs", None)
    sys.modules.pop("remotefs.cli", None)
    sys.modules.pop("remotefs.fuse_handler", None)

    module = importlib.import_module("remotefs.cli")

    assert hasattr(module, "main")
    assert "remotefs.fuse_handler" not in sys.modules


def test_package_import_does_not_require_fuse(monkeypatch):
    """Importing remotefs should not eagerly load fuse_handler."""
    sys.modules.pop("remotefs", None)
    sys.modules.pop("remotefs.cli", None)
    sys.modules.pop("remotefs.fuse_handler", None)

    module = importlib.import_module("remotefs")

    assert hasattr(module, "HTTPBackend")
    assert hasattr(module, "RemoteRunBackend")
    assert "remotefs.fuse_handler" not in sys.modules


@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("darwin", "brew install --cask macfuse"),
        ("linux", "sudo apt install libfuse2"),
        ("win32", "WinFsp"),
    ],
)
def test_fuse_install_hint_by_platform(platform, expected):
    """Platform-specific FUSE install hints should be actionable."""
    sys.modules.pop("remotefs", None)
    sys.modules.pop("remotefs.cli", None)
    module = importlib.import_module("remotefs.cli")

    hint = module.get_fuse_install_hint(platform)

    assert expected in hint


def test_warn_if_fuse_missing_continues_for_non_mount(capsys):
    """Non-mount commands should warn when FUSE is missing but continue."""
    sys.modules.pop("remotefs", None)
    sys.modules.pop("remotefs.cli", None)
    module = importlib.import_module("remotefs.cli")

    module.warn_if_fuse_missing("linux", exc=OSError("Unable to find libfuse"))

    captured = capsys.readouterr()
    assert "Warning:" in captured.err
    assert "libfuse2" in captured.err


def test_ensure_fuse_for_mount_exits_with_install_hint(capsys):
    """Mount should stop early when FUSE runtime is unavailable."""
    sys.modules.pop("remotefs", None)
    sys.modules.pop("remotefs.cli", None)
    module = importlib.import_module("remotefs.cli")

    with pytest.raises(SystemExit) as exc:
        module.ensure_fuse_available_or_exit("darwin", exc=OSError("Unable to find libfuse"))

    captured = capsys.readouterr()
    assert exc.value.code == 1
    assert "Unable to find libfuse" in captured.err
    assert "brew install --cask macfuse" in captured.err
