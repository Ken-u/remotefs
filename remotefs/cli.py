"""Command-line interface for RemoteFS."""

import argparse
import sys
from pathlib import Path

from .config import Config
from .remote_client import RemoteClient
from .cache import MetadataCache
from .fuse_handler import RemoteFS


def cmd_mount(args):
    """Mount the remote filesystem."""
    config = Config.load(args.config)

    # Override with CLI args
    if args.server:
        config.server_url = args.server
    if args.token:
        config.token = args.token
    if args.mount_point:
        config.mount_point = Path(args.mount_point).expanduser()

    if not config.server_url:
        print("Error: No server URL provided", file=sys.stderr)
        print("Use --server or set REMOTEFS_SERVER env var", file=sys.stderr)
        sys.exit(1)

    # Create mount point
    config.mount_point.mkdir(parents=True, exist_ok=True)

    # Create client and cache
    client = RemoteClient(config.server_url, config.token)
    cache = MetadataCache(ttl=config.cache_ttl)

    # Mount
    print(f"Mounting RemoteFS at {config.mount_point}")
    fs = RemoteFS(client=client, cache=cache, root=str(config.mount_point))
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

    if not config.server_url:
        print("Not configured")
        sys.exit(1)

    client = RemoteClient(config.server_url, config.token)
    try:
        client.exists("/")
        print(f"Connected to {config.server_url}")
        print(f"Mount point: {config.mount_point}")
        print(f"Cache TTL: {config.cache_ttl}s")
    except Exception as e:
        print(f"Disconnected: {e}")
        sys.exit(1)


def cmd_config(args):
    """Show current configuration."""
    config = Config.load(args.config)

    print(f"Server URL: {config.server_url or '(not set)'}")
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
    mount_parser.add_argument("mount_point", nargs="?", help="Mount point path")
    mount_parser.set_defaults(func=cmd_mount)

    # unmount
    unmount_parser = subparsers.add_parser("unmount", help="Unmount remote filesystem")
    unmount_parser.add_argument("mount_point", help="Mount point path")
    unmount_parser.set_defaults(func=cmd_unmount)

    # status
    status_parser = subparsers.add_parser("status", help="Show connection status")
    status_parser.set_defaults(func=cmd_status)

    # config
    config_parser = subparsers.add_parser("config", help="Show configuration")
    config_parser.set_defaults(func=cmd_config)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
