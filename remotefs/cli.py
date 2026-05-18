"""Command-line interface for RemoteFS."""

import argparse
import importlib
import sys
from pathlib import Path
from typing import Optional

from .config import Config
from .http_backend import HTTPBackend
from .remote_run_backend import RemoteRunBackend
from .cache import MetadataCache


def create_backend(config: Config):
    """Create backend instance from config."""
    if config.backend_type == "remote-run":
        return RemoteRunBackend(
            base_url=config.server_url,
            token=config.token,
            rk_search_max_depth=config.rk_search_max_depth,
            rk_codesearch_project=config.rk_codesearch_project,
            rk_codesearch_type=config.rk_codesearch_type,
            rk_codesearch_search_field=config.rk_codesearch_search_field,
        )
    return HTTPBackend(base_url=config.server_url, token=config.token)


def get_fuse_install_hint(platform: str) -> str:
    """Return platform-specific installation guidance for FUSE."""
    if platform == "darwin":
        return "macOS detected. Install macFUSE with: brew install --cask macfuse"
    if platform.startswith("linux"):
        return "Linux detected. Install FUSE with: sudo apt install libfuse2 or sudo apt install fuse"
    if platform.startswith("win"):
        return "Windows detected. Install WinFsp from https://winfsp.dev/rel/"
    return "Install a FUSE runtime for your platform before mounting RemoteFS."


def probe_fuse() -> None:
    """Probe whether the FUSE runtime is available."""
    importlib.import_module(".fuse_handler", package="remotefs")


def warn_if_fuse_missing(platform: str, exc: Optional[Exception] = None) -> None:
    """Warn the user when the FUSE runtime is unavailable."""
    if exc is None:
        try:
            probe_fuse()
            return
        except (ImportError, OSError) as err:
            exc = err
    print(f"Warning: {exc}", file=sys.stderr)
    print(get_fuse_install_hint(platform), file=sys.stderr)


def ensure_fuse_available_or_exit(platform: str, exc: Optional[Exception] = None) -> None:
    """Require the FUSE runtime to be available or exit with guidance."""
    if exc is None:
        try:
            probe_fuse()
            return
        except (ImportError, OSError) as err:
            exc = err
    print(f"Error: {exc}", file=sys.stderr)
    print(get_fuse_install_hint(platform), file=sys.stderr)
    sys.exit(1)


def cmd_mount(args):
    """Mount the remote filesystem."""
    config = Config.load(args.config)

    # Override with CLI args
    if args.server:
        config.server_url = args.server
    if args.token:
        config.token = args.token
    if args.backend:
        config.backend_type = args.backend
    if args.mount_point:
        config.mount_point = Path(args.mount_point).expanduser()

    if not config.server_url:
        print("Error: No server URL provided", file=sys.stderr)
        print("Use --server or set REMOTEFS_SERVER env var", file=sys.stderr)
        sys.exit(1)

    # Create mount point
    config.mount_point.mkdir(parents=True, exist_ok=True)

    # Create backend and cache
    backend = create_backend(config)
    cache = MetadataCache(ttl=config.cache_ttl)

    # Mount
    print(f"Mounting RemoteFS at {config.mount_point}")
    from .fuse_handler import RemoteFS

    fs = RemoteFS(backend=backend, cache=cache, root=str(config.mount_point))
    fs.main()


def cmd_unmount(args):
    """Unmount the remote filesystem."""
    mount_point = Path(args.mount_point).expanduser()

    if not mount_point.exists():
        print(f"Error: {mount_point} does not exist", file=sys.stderr)
        sys.exit(1)

    # Unmount using fusermount
    import subprocess
    try:
        subprocess.run(["fusermount", "-u", str(mount_point)], check=True)
        print(f"Unmounted {mount_point}")
    except subprocess.CalledProcessError as e:
        print(f"Error unmounting: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args):
    """Show connection status."""
    config = Config.load(args.config)
    if args.backend:
        config.backend_type = args.backend

    if not config.server_url:
        print("Not configured")
        sys.exit(1)

    backend = create_backend(config)
    try:
        backend.file_exists("/")
        print(f"Connected to {config.server_url}")
        print(f"Backend: {config.backend_type}")
        print(f"Mount point: {config.mount_point}")
        print(f"Cache TTL: {config.cache_ttl}s")
    except Exception as e:
        print(f"Disconnected: {e}")
        sys.exit(1)


def cmd_config(args):
    """Show current configuration."""
    config = Config.load(args.config)

    print(f"Server URL: {config.server_url or '(not set)'}")
    print(f"Backend: {config.backend_type}")
    if config.backend_type == "remote-run":
        print(f"RK Search Max Depth: {config.rk_search_max_depth}")
        print(f"RK CodeSearch Project: {config.rk_codesearch_project or '(default)'}")
        print(f"RK CodeSearch Type: {config.rk_codesearch_type or '(default)'}")
        print(f"RK CodeSearch Field: {config.rk_codesearch_search_field}")
    print(f"Token: {'(set)' if config.token else '(not set)'}")
    print(f"Cache TTL: {config.cache_ttl}s")
    print(f"Mount point: {config.mount_point}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(prog="remotefs", description="RemoteFS - FUSE remote filesystem")
    parser.add_argument("--config", type=Path, help="Config file path")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # mount
    mount_parser = subparsers.add_parser("mount", help="Mount remote filesystem")
    mount_parser.add_argument("--server", help="Server URL")
    mount_parser.add_argument("--token", help="Auth token")
    mount_parser.add_argument(
        "--backend",
        choices=["http", "remote-run"],
        help="Backend type",
    )
    mount_parser.add_argument("mount_point", nargs="?", help="Mount point path")
    mount_parser.set_defaults(func=cmd_mount)

    # unmount
    unmount_parser = subparsers.add_parser("unmount", help="Unmount remote filesystem")
    unmount_parser.add_argument("mount_point", help="Mount point path")
    unmount_parser.set_defaults(func=cmd_unmount)

    # status
    status_parser = subparsers.add_parser("status", help="Show connection status")
    status_parser.add_argument(
        "--backend",
        choices=["http", "remote-run"],
        help="Backend type override",
    )
    status_parser.set_defaults(func=cmd_status)

    # config
    config_parser = subparsers.add_parser("config", help="Show configuration")
    config_parser.set_defaults(func=cmd_config)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "mount":
        ensure_fuse_available_or_exit(sys.platform)
    else:
        warn_if_fuse_missing(sys.platform)

    args.func(args)


if __name__ == "__main__":
    main()
