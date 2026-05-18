# RemoteFS

基于 FUSE 的远程文件系统，专为 AI 智能体设计。

## 功能特性

- **透明访问** - 智能体像操作本地文件一样操作远程文件
- **完整命令支持** - 所有命令转发到远程环境执行
- **极速代码搜索** - 基于索引的搜索，支持超大代码库（AOSP 级别）
- **跨平台** - 支持 Linux、macOS、Windows（通过 WinFsp）

## 安装

推荐使用 `uv` + 本地虚拟环境：

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

如果只需要运行时依赖：

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

如果你仍然使用普通 `pip`，可以退回到：

```bash
pip install -e .
```

### 系统依赖

- **Linux**: `sudo apt install libfuse2` 或 `sudo apt install fuse`
- **macOS**: `brew install --cask macfuse`
- **Windows**: 安装 [WinFsp](https://winfsp.dev/rel/)

## 配置

创建配置文件 `~/.config/remotefs/config.yaml`：

```yaml
server:
  backend: "http"  # 或 "remote-run"
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

或使用环境变量：

```bash
export REMOTEFS_SERVER=http://your-server:8080
export REMOTEFS_TOKEN=your-token
export REMOTEFS_BACKEND=http
export REMOTEFS_RK_SEARCH_DEPTH=1
export REMOTEFS_RK_CODESEARCH_PROJECT=
export REMOTEFS_RK_CODESEARCH_TYPE=
export REMOTEFS_RK_CODESEARCH_FIELD=smart
```

## 使用方法

### 挂载

```bash
remotefs mount
# 或
remotefs mount --server http://server:8080 --token TOKEN /path/to/mount
# 或使用 Remote Run 后端
remotefs mount --backend remote-run --server http://server:8522 --token TOKEN /path/to/mount
```

### 卸载

```bash
remotefs unmount ~/remotefs/workspace
```

### 查看状态

```bash
remotefs status
```

### 查看配置

```bash
remotefs config
```

## 内置后端

- `http`: 直接调用 REST 文件 API（`/file`、`/dir`、`/exec`、`/search`）
- `remote-run`: 通过 Remote Run Agent API 和 allowlisted 命令工作，例如 `Read`、`Write`、`list_dir`、`path_exists`、`make_dir`、`delete_path`

`remote-run` 更适合代码工作区。读取通过 `download_path` 是二进制安全的；写入当前依赖 Remote Run 的 `Write` 命令，因此只保证 UTF-8 文本写入。

对 `remote-run`，`search()` 采用混合策略：
- 路径深度 `<= rk_search_max_depth`：先走 `rk_codesearch`，无结果再回退 `Grep`
- 更深路径：先走 `Grep`，无结果再补 `rk_codesearch`

如果你要在代码里强制只走索引模糊搜索，可以直接调用 `RemoteRunBackend.search_index(pattern, path="/")`。

可选的 `rk_codesearch` 调优项：
- `rk_codesearch_project`: 限定索引搜索的项目范围
- `rk_codesearch_type`: 限定文件类型，例如 `java`、`python`、`rust`
- `rk_codesearch_search_field`: 选择索引搜索模式，例如 `smart`、`full`、`path`、`def`、`symbol`

## 远程 API

远程服务器需要实现以下接口：

| 方法 | 接口 | 描述 |
|------|------|------|
| GET | `/file?path=<path>` | 读取文件 |
| POST | `/file?path=<path>` | 写入文件 |
| DELETE | `/file?path=<path>` | 删除文件 |
| HEAD | `/file?path=<path>` | 检查文件存在 |
| GET | `/dir?path=<path>` | 列目录 |
| POST | `/dir?path=<path>` | 创建目录 |
| DELETE | `/dir?path=<path>` | 删除目录 |
| POST | `/exec` | 执行命令 |
| GET | `/search?pattern=<pattern>&path=<path>` | 索引内容搜索 |

### `/exec` 请求格式

```json
{
  "cmd": "make",
  "args": ["-j4"],
  "cwd": "/path/to/working/dir"
}
```

### `/exec` 响应格式

```json
{
  "stdout": "...",
  "stderr": "...",
  "exit_code": 0
}
```

### `/search` 响应格式

```json
[
  {"path": "/src/foo.py", "line": 10, "match": "def foo()"}
]
```

## 开发

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
pytest tests/
```

## 许可证

MIT
