# RemoteFS

FUSE-based remote filesystem for AI agents.

## Features

- **Transparent access** - Agents operate remote files as if local
- **Full command support** - All commands forwarded to remote environment
- **Fast code search** - Index-based search for large codebases (AOSP-scale)
- **Cross-platform** - Linux, macOS, Windows (via WinFsp)

## Installation

```bash
pip install -e .
```

### System Dependencies

- **Linux**: `sudo apt install libfuse2` or `sudo apt install fuse`
- **macOS**: `brew install --cask macfuse`
- **Windows**: Install [WinFsp](https://winfsp.dev/rel/)

## Configuration

Create `~/.config/remotefs/config.yaml`:

```yaml
server:
  url: "http://your-server:8080"
  token: "your-token"
cache:
  ttl: 5
mount:
  path: "~/remotefs/workspace"
```

Or use environment variables:

```bash
export REMOTEFS_SERVER=http://your-server:8080
export REMOTEFS_TOKEN=your-token
```

## Usage

### Mount

```bash
remotefs mount
# or
remotefs mount --server http://server:8080 --token TOKEN /path/to/mount
```

### Unmount

```bash
remotefs unmount ~/remotefs/workspace
```

### Status

```bash
remotefs status
```

### Configuration

```bash
remotefs config
```

## Remote API

Your remote server must implement these endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/file?path=<path>` | Read file |
| POST | `/file?path=<path>` | Write file |
| DELETE | `/file?path=<path>` | Delete file |
| HEAD | `/file?path=<path>` | Check existence |
| GET | `/dir?path=<path>` | List directory |
| POST | `/dir?path=<path>` | Create directory |
| DELETE | `/dir?path=<path>` | Delete directory |
| POST | `/exec` | Execute command |
| GET | `/search?pattern=<pattern>&path=<path>` | Index search |

### `/exec` Request

```json
{
  "cmd": "make",
  "args": ["-j4"],
  "cwd": "/path/to/working/dir"
}
```

### `/exec` Response

```json
{
  "stdout": "...",
  "stderr": "...",
  "exit_code": 0
}
```

### `/search` Response

```json
[
  {"path": "/src/foo.py", "line": 10, "match": "def foo()"}
]
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/
```

## License

MIT