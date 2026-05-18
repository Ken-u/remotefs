# RemoteFS

FUSE-based remote filesystem for AI agents.

## Features

- **Transparent access** - Agents operate remote files as if local
- **Full command support** - All commands forwarded to remote environment
- **Fast code search** - Index-based search for large codebases (AOSP-scale)
- **Cross-platform** - Linux, macOS, Windows (via WinFsp)

## Installation

Recommended: use `uv` with a local virtual environment.

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

If you only need runtime dependencies:

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

Fallback for plain `pip` users:

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
  backend: "http"  # or "remote-run"
  url: "http://your-server:8080"
  token: "your-token"
  rk_search_max_depth: 1
  rk_codesearch_project: ""
  rk_codesearch_type: ""
  rk_codesearch_search_field: "smart"
cache:
  ttl: 5
mount:
  path: "~/remotefs/workspace"
```

Or use environment variables:

```bash
export REMOTEFS_SERVER=http://your-server:8080
export REMOTEFS_TOKEN=your-token
export REMOTEFS_BACKEND=http
export REMOTEFS_RK_SEARCH_DEPTH=1
export REMOTEFS_RK_CODESEARCH_PROJECT=
export REMOTEFS_RK_CODESEARCH_TYPE=
export REMOTEFS_RK_CODESEARCH_FIELD=smart
```

## Usage

### Mount

```bash
remotefs mount
# or
remotefs mount --server http://server:8080 --token TOKEN /path/to/mount
# or use Remote Run backend
remotefs mount --backend remote-run --server http://server:8522 --token TOKEN /path/to/mount
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

## Built-in Backends

- `http`: direct REST file API (`/file`, `/dir`, `/exec`, `/search`)
- `remote-run`: Remote Run Agent API using allowlisted commands such as `Read`, `Write`, `list_dir`, `path_exists`, `make_dir`, and `delete_path`

`remote-run` is oriented toward source workspaces. Reads are binary-safe through `download_path`, but writes currently depend on the Remote Run `Write` command and therefore support UTF-8 text payloads only.

For `remote-run`, `search()` uses a hybrid strategy:
- path depth `<= rk_search_max_depth`: try `rk_codesearch` first, then fall back to `Grep`
- deeper paths: try `Grep` first, then fall back to `rk_codesearch`

If you need to force index-based fuzzy search from code, use `RemoteRunBackend.search_index(pattern, path="/")`.

Optional `rk_codesearch` tuning:
- `rk_codesearch_project`: restrict search to a specific indexed project
- `rk_codesearch_type`: restrict indexed results to a file type such as `java`, `python`, or `rust`
- `rk_codesearch_search_field`: choose the index mode, for example `smart`, `full`, `path`, `def`, or `symbol`

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
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
pytest tests/
```

## License

MIT
