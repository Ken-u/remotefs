# RemoteFS 设计文档

## 概述

RemoteFS 是一个基于 FUSE 的远程文件系统，让本地运行的智能体能够无感知地操作远程服务器上的文件和执行命令。

## 目标

- 智能体完全无感知 — 像操作本地文件一样操作远程文件
- 无需学习 — 所有命令行为与远程环境一致
- 跨平台 — 支持 Linux、macOS、Windows

## 架构

```
智能体（本地）
    ↓ 无感操作（Read/Write/Bash）
FUSE 挂载点 ~/remotefs/workspace/
    ↓ Python fusepy
RemoteFS 客户端
    ↓ HTTP API 转发所有操作
远程执行插件（服务器端）
```

## 核心功能

### 文件操作

| 操作 | FUSE 方法 | 远程 API |
|------|----------|---------|
| 读取文件 | `read` | `GET /file?path=...` |
| 写入文件 | `write` | `POST /file?path=...` |
| 创建文件 | `create` | `POST /file?path=...` |
| 删除文件 | `unlink` | `DELETE /file?path=...` |
| 检查存在 | `getattr` | `HEAD /file?path=...` |

### 目录操作

| 操作 | FUSE 方法 | 远程 API |
|------|----------|---------|
| 列目录 | `readdir` | `GET /dir?path=...` |
| 创建目录 | `mkdir` | `POST /dir?path=...` |
| 删除目录 | `rmdir` | `DELETE /dir?path=...` |

### 搜索与命令执行

通过 `.local/bin/` 下的虚拟命令转发到远端执行：

| 本地命令 | 行为 |
|---------|------|
| `find . -name "*.py"` | 转发到远端执行，返回结果 |
| `grep -r "pattern" src/` | **索引优先**，无结果时降级实时搜索 |
| `make -j4` | 转发到远端执行，返回结果 |
| 任意命令 | 转发到远端执行，返回结果 |

### 索引搜索（极速代码定位）

针对 AOSP 等超大工程，提供基于索引的内容搜索：

**核心场景：全局定位**

智能体在超大工程中不知道代码在哪：
```
grep -r "class AudioManager" /     # 全局搜索，索引毫秒级返回
```

无索引时：
- 扫描几百万文件，超时或极慢
- 智能体被迫猜目录，猜错就浪费时间

有索引时：
- 毫秒级返回路径，直接定位
- 智能体无需猜测，效率大幅提升

**自动选择逻辑：**

```
智能体执行 grep -r "pattern"
    ↓
先查索引接口 → 有结果则返回（毫秒级）
    ↓
索引无结果或失败 → 降级到实时 grep
```

特点：
- 全局搜索体验从"不可用"变为"秒出"
- 索引可能不实时，与实际目录有差异
- 用于快速定位代码，智能体完全无感知

### 元数据缓存

- 缓存内容：文件属性（大小、修改时间）、目录列表
- 缓存策略：TTL 过期（默认 5 秒，可配置）
- 失效触发：写入操作时主动失效

## 虚拟文件系统布局

```
~/remotefs/workspace/
└── <远端目录结构>      # 按需发现，完全透明
```

- 无额外隐藏目录
- 智能体访问任何路径时，从远端按需获取
- `.local/bin/` 下的命令按需发现（首次访问或缓存）

## 按需探索机制

```
智能体访问 /src/main.py
    ↓
检查本地缓存 → 未命中
    ↓
请求远端 GET /file?path=/src/main.py
    ↓
返回文件内容 + 元数据
    ↓
缓存元数据，返回内容给智能体
```

## 命令执行机制

### 方案：FUSE exec 钩子

通过 FUSE 的 `ioctl` 或虚拟可执行文件实现：

1. 智能体执行 `make -j4`
2. FUSE 拦截执行请求
3. 转发到远端 `POST /exec` with `{"cmd": "make", "args": ["-j4"]}`
4. 返回 stdout/stderr/exit code

### 具体实现

在挂载点下创建 `.local/bin/` 虚拟目录：
- 首次访问时从远端获取可用命令列表
- 每个命令对应一个虚拟可执行文件
- 执行时触发远程调用

## 项目结构

```
remotefs/
├── remotefs/
│   ├── __init__.py
│   ├── fuse_handler.py    # FUSE 文件系统操作
│   ├── remote_client.py   # HTTP 客户端
│   ├── cache.py           # 元数据缓存
│   ├── config.py          # 配置管理
│   └── cli.py             # 命令行入口
├── tests/
├── pyproject.toml
└── README.md
```

## 配置方式

优先级：命令行 > 环境变量 > 配置文件

```yaml
# ~/.config/remotefs/config.yaml
server:
  url: "https://remote.example.com"
  token: "xxx"

cache:
  ttl: 5  # 秒

mount:
  path: "~/remotefs/workspace"
```

## 命令行工具

```bash
# 挂载
remotefs mount [--server URL] [--token TOKEN] [MOUNT_POINT]

# 卸载
remotefs unmount [MOUNT_POINT]

# 查看状态
remotefs status

# 查看配置
remotefs config
```

## 依赖

- Python 3.8+
- fusepy (跨平台 FUSE 绑定)
- requests (HTTP 客户端)

### 系统依赖

- Linux: libfuse
- macOS: macFUSE
- Windows: WinFsp + fusepy

## 远程 API 接口约定

RemoteFS 客户端需要对接现有的远程执行插件，预期接口：

### 文件操作
```
GET  /file?path=<path>           # 读取文件
POST /file?path=<path>           # 写入文件
DELETE /file?path=<path>         # 删除文件
GET  /dir?path=<path>            # 列目录
POST /dir?path=<path>            # 创建目录
DELETE /dir?path=<path>          # 删除目录
GET  /exists?path=<path>         # 检查存在
```

### 命令执行
```
POST /exec                       # 执行命令 {"cmd": "...", "args": [...]}
```

### 索引搜索（极速）
```
GET  /search?pattern=<pattern>&path=<path>   # 索引内容搜索
```
- 返回匹配结果列表，格式与 grep 一致
- 用于代码定位，毫秒级响应
- 可能不实时，与实际目录有差异

具体接口格式待用户提供现有插件文档后调整。

## 开发阶段

1. **Phase 1**: 基础 FUSE 框架 + 文件读写
2. **Phase 2**: 目录操作 + 元数据缓存
3. **Phase 3**: 命令执行支持
4. **Phase 4**: 跨平台测试 + 打包