# RemoteFS

基于 FUSE 的远程文件系统，专为 AI 智能体设计。

## 功能特性

- **透明访问** - 智能体像操作本地文件一样操作远程文件
- **完整命令支持** - 所有命令转发到远程环境执行
- **极速代码搜索** - 基于索引的搜索，支持超大代码库（AOSP 级别）
- **跨平台** - 支持 Linux、macOS、Windows（通过 WinFsp）

## 安装

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
  url: "http://your-server:8080"
  token: "your-token"
cache:
  ttl: 5
mount:
  path: "~/remotefs/workspace"
```

或使用环境变量：

```bash
export REMOTEFS_SERVER=http://your-server:8080
export REMOTEFS_TOKEN=your-token
```

## 使用方法

### 挂载

```bash
remotefs mount
# 或
remotefs mount --server http://server:8080 --token TOKEN /path/to/mount
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
pip install -e ".[dev]"
pytest tests/
```

## 许可证

MIT
