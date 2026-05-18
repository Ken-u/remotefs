# RemoteFS 后端开发指南

> 类似于 AOSP HAL 的抽象层设计，让开发者可以轻松接入不同的远程存储后端。

## 概述

RemoteFS 使用**后端抽象层**（Backend Abstraction Layer）设计，类似于 AOSP 的 HAL（Hardware Abstraction Layer）。这种设计让核心文件系统逻辑与具体的传输协议解耦，开发者可以轻松实现自定义后端。

```
┌─────────────────────────────────────┐
│         FUSE Handler                │  ← 文件系统层
├─────────────────────────────────────┤
│         Metadata Cache              │  ← 缓存层
├─────────────────────────────────────┤
│      RemoteBackend (抽象接口)       │  ← 抽象层 (HAL)
├──────────────┬──────────────────────┤
│  HTTPBackend │  YourCustomBackend   │  ← 具体实现
└──────────────┴──────────────────────┘
```

## 核心接口

### RemoteBackend 抽象类

所有后端必须实现 `remotefs.backend.RemoteBackend` 抽象类：

```python
from remotefs import RemoteBackend, FileEntry, ExecResult, SearchResult

class MyCustomBackend(RemoteBackend):
    """我的自定义后端实现"""

    def __init__(self, **kwargs):
        # 初始化代码
        pass

    # === 文件操作 ===

    def read_file(self, path: str) -> bytes:
        """读取文件内容"""
        pass

    def write_file(self, path: str, content: bytes) -> bool:
        """写入文件内容"""
        pass

    def delete_file(self, path: str) -> bool:
        """删除文件"""
        pass

    def file_exists(self, path: str) -> bool:
        """检查文件是否存在"""
        pass

    # === 目录操作 ===

    def list_dir(self, path: str) -> List[FileEntry]:
        """列出目录内容"""
        pass

    def create_dir(self, path: str) -> bool:
        """创建目录"""
        pass

    def delete_dir(self, path: str) -> bool:
        """删除目录"""
        pass

    # === 命令执行 ===

    def exec_cmd(self, cmd: str, args: List[str], cwd: str = None) -> ExecResult:
        """执行命令"""
        pass

    # === 搜索 (可选) ===

    def search(self, pattern: str, path: str = "/") -> List[SearchResult]:
        """索引搜索（可选实现）"""
        raise NotImplementedError("Search not supported")
```

## 实现示例

### 示例 1: 本地文件系统后端

```python
"""Local filesystem backend for RemoteFS."""

import os
import subprocess
from pathlib import Path
from typing import List, Optional

from remotefs import RemoteBackend, FileEntry, ExecResult, SearchResult


class LocalBackend(RemoteBackend):
    """将本地目录暴露为 RemoteFS 后端。

    使用场景：
    - 测试 RemoteFS 功能
    - 将本地目录以 FUSE 方式挂载到其他位置
    """

    def __init__(self, root: str):
        self.root = Path(root).expanduser()

    def _resolve_path(self, path: str) -> Path:
        """将远程路径解析为本地路径"""
        return self.root / path.lstrip("/")

    def read_file(self, path: str) -> bytes:
        full_path = self._resolve_path(path)
        with open(full_path, "rb") as f:
            return f.read()

    def write_file(self, path: str, content: bytes) -> bool:
        full_path = self._resolve_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(content)
        return True

    def delete_file(self, path: str) -> bool:
        full_path = self._resolve_path(path)
        full_path.unlink()
        return True

    def file_exists(self, path: str) -> bool:
        full_path = self._resolve_path(path)
        return full_path.exists()

    def list_dir(self, path: str) -> List[FileEntry]:
        full_path = self._resolve_path(path)
        entries = []
        for item in full_path.iterdir():
            entries.append(FileEntry(
                name=item.name,
                type="dir" if item.is_dir() else "file",
                size=item.stat().st_size if item.is_file() else None,
                mtime=item.stat().st_mtime,
            ))
        return entries

    def create_dir(self, path: str) -> bool:
        full_path = self._resolve_path(path)
        full_path.mkdir(parents=True, exist_ok=True)
        return True

    def delete_dir(self, path: str) -> bool:
        full_path = self._resolve_path(path)
        os.rmdir(full_path)
        return True

    def exec_cmd(self, cmd: str, args: List[str], cwd: Optional[str] = None) -> ExecResult:
        result = subprocess.run(
            [cmd] + args,
            cwd=cwd or self.root,
            capture_output=True,
        )
        return ExecResult(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
        )
```

### 示例 2: S3 存储后端

```python
"""Amazon S3 backend for RemoteFS."""

import boto3
from typing import List, Optional
from remotefs import RemoteBackend, FileEntry, ExecResult, SearchResult


class S3Backend(RemoteBackend):
    """将 S3 存储桶暴露为 RemoteFS 后端。

    注意：S3 是对象存储，某些文件系统语义（如目录）需要模拟实现。
    """

    def __init__(self, bucket: str, region: str = "us-east-1"):
        self.bucket = bucket
        self.s3 = boto3.client("s3", region_name=region)

    def _resolve_key(self, path: str) -> str:
        """将路径转换为 S3 key"""
        return path.lstrip("/")

    def read_file(self, path: str) -> bytes:
        key = self._resolve_key(path)
        response = self.s3.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def write_file(self, path: str, content: bytes) -> bool:
        key = self._resolve_key(path)
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=content)
        return True

    def delete_file(self, path: str) -> bool:
        key = self._resolve_key(path)
        self.s3.delete_object(Bucket=self.bucket, Key=key)
        return True

    def file_exists(self, path: str) -> bool:
        key = self._resolve_key(path)
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except self.s3.exceptions.ClientError:
            return False

    def list_dir(self, path: str) -> List[FileEntry]:
        key = self._resolve_key(path)
        if not key.endswith("/"):
            key += "/"

        response = self.s3.list_objects_v2(
            Bucket=self.bucket,
            Prefix=key,
            Delimiter="/",
        )

        entries = []
        # 添加"目录"（公共前缀）
        for prefix in response.get("CommonPrefixes", []):
            name = prefix["Prefix"].rstrip("/").split("/")[-1]
            entries.append(FileEntry(name=name, type="dir"))

        # 添加文件
        for obj in response.get("Contents", []):
            name = obj["Key"].split("/")[-1]
            entries.append(FileEntry(
                name=name,
                type="file",
                size=obj["Size"],
                mtime=obj["LastModified"].timestamp(),
            ))

        return entries

    def create_dir(self, path: str) -> bool:
        # S3 不需要显式创建目录，但我们可以创建一个占位符
        key = self._resolve_key(path).rstrip("/") + "/"
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=b"")
        return True

    def delete_dir(self, path: str) -> bool:
        # 删除目录下所有对象
        key = self._resolve_key(path).rstrip("/") + "/"
        paginator = self.s3.get_paginator("list_objects_v2")
        objects_to_delete = []

        for page in paginator.paginate(Bucket=self.bucket, Prefix=key):
            for obj in page.get("Contents", []):
                objects_to_delete.append({"Key": obj["Key"]})

        if objects_to_delete:
            self.s3.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": objects_to_delete}
            )
        return True

    def exec_cmd(self, cmd: str, args: List[str], cwd: Optional[str] = None) -> ExecResult:
        # S3 不支持命令执行
        raise NotImplementedError("Command execution not supported on S3")
```

### 示例 3: SSH/SFTP 后端

```python
"""SSH/SFTP backend for RemoteFS."""

import paramiko
from typing import List, Optional
from remotefs import RemoteBackend, FileEntry, ExecResult, SearchResult


class SSHBackend(RemoteBackend):
    """通过 SSH/SFTP 访问远程服务器。

    使用场景：
    - 安全地访问远程开发环境
    - 通过 SSH 隧道访问内部网络资源
    """

    def __init__(self, host: str, port: int = 22, username: str = "",
                 password: str = "", key_path: Optional[str] = None):
        self.host = host
        self.port = port
        self.username = username

        # 建立 SSH 连接
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if key_path:
            self.client.connect(
                host, port, username,
                key_filename=key_path,
                password=password
            )
        else:
            self.client.connect(host, port, username, password=password)

        self.sftp = self.client.open_sftp()

    def close(self):
        """关闭连接"""
        self.sftp.close()
        self.client.close()

    def read_file(self, path: str) -> bytes:
        with self.sftp.open(path, "rb") as f:
            return f.read()

    def write_file(self, path: str, content: bytes) -> bool:
        with self.sftp.open(path, "wb") as f:
            f.write(content)
        return True

    def delete_file(self, path: str) -> bool:
        self.sftp.remove(path)
        return True

    def file_exists(self, path: str) -> bool:
        try:
            self.sftp.stat(path)
            return True
        except FileNotFoundError:
            return False

    def list_dir(self, path: str) -> List[FileEntry]:
        entries = []
        for entry in self.sftp.listdir_attr(path):
            entries.append(FileEntry(
                name=entry.filename,
                type="dir" if entry.st_mode & 0o40000 else "file",
                size=entry.st_size,
                mtime=entry.st_mtime,
                mode=entry.st_mode & 0o777,
            ))
        return entries

    def create_dir(self, path: str) -> bool:
        self.sftp.mkdir(path)
        return True

    def delete_dir(self, path: str) -> bool:
        self.sftp.rmdir(path)
        return True

    def exec_cmd(self, cmd: str, args: List[str], cwd: Optional[str] = None) -> ExecResult:
        full_cmd = cmd + " " + " ".join(args)
        if cwd:
            full_cmd = f"cd {cwd} && {full_cmd}"

        stdin, stdout, stderr = self.client.exec_command(full_cmd)
        return ExecResult(
            stdout=stdout.read(),
            stderr=stderr.read(),
            exit_code=stdout.channel.recv_exit_status(),
        )
```

## 使用自定义后端

### 方式 1: 编程方式

```python
from remotefs import RemoteFS, MetadataCache
from my_backend import LocalBackend  # 你的自定义后端

# 创建后端实例
backend = LocalBackend(root="/data/remote-storage")

# 创建缓存
cache = MetadataCache(ttl=5)

# 挂载 FUSE 文件系统
fs = RemoteFS(backend=backend, cache=cache, root="/mnt/myfs")
fs.main()
```

### 方式 2: CLI 扩展

修改 `cli.py` 添加自定义后端支持：

```python
def cmd_mount(args):
    config = Config.load(args.config)

    # 根据配置选择后端
    backend_type = config.backend_type  # "http", "local", "s3", etc.

    if backend_type == "http":
        backend = HTTPBackend(config.server_url, config.token)
    elif backend_type == "local":
        backend = LocalBackend(config.local_root)
    elif backend_type == "s3":
        backend = S3Backend(config.s3_bucket, config.s3_region)
    # ... 其他后端

    cache = MetadataCache(ttl=config.cache_ttl)
    fs = RemoteFS(backend=backend, cache=cache, root=str(config.mount_point))
    fs.main()
```

## 错误处理

后端应该抛出合适的异常：

```python
from remotefs import BackendError, FileNotFoundError, PermissionDeniedError

def read_file(self, path: str) -> bytes:
    try:
        # 你的实现
        pass
    except IOError as e:
        if e.errno == errno.ENOENT:
            raise FileNotFoundError(f"File not found: {path}", code="NOT_FOUND")
        elif e.errno == errno.EACCES:
            raise PermissionDeniedError(f"Access denied: {path}", code="FORBIDDEN")
        else:
            raise BackendError(f"IO error: {e}", code="IO_ERROR")
```

## 测试后端

```python
import pytest
from remotefs import RemoteBackend

def backend_fixture() -> RemoteBackend:
    """创建后端实例用于测试"""
    return YourBackend(...)

class TestYourBackend:
    """测试后端实现"""

    def test_read_write_file(self, backend):
        content = b"Hello, World!"
        backend.write_file("/test.txt", content)
        assert backend.read_file("/test.txt") == content

    def test_file_exists(self, backend):
        assert not backend.file_exists("/nonexistent")
        backend.write_file("/exists.txt", b"")
        assert backend.file_exists("/exists.txt")

    def test_list_dir(self, backend):
        entries = backend.list_dir("/")
        assert isinstance(entries, list)

    def test_exec_cmd(self, backend):
        result = backend.exec_cmd("echo", ["hello"])
        assert result.exit_code == 0
        assert b"hello" in result.stdout
```

## API 参考

### 数据结构

```python
@dataclass
class FileEntry:
    """文件或目录条目"""
    name: str           # 文件名
    type: str           # "file" 或 "dir"
    size: Optional[int] = None   # 文件大小（字节）
    mode: Optional[int] = None   # 权限模式
    mtime: Optional[float] = None  # 修改时间

@dataclass
class ExecResult:
    """命令执行结果"""
    stdout: bytes       # 标准输出
    stderr: bytes       # 标准错误
    exit_code: int      # 退出码

@dataclass
class SearchResult:
    """搜索结果"""
    path: str           # 文件路径
    line: int           # 行号
    match: str          # 匹配内容
    context: Optional[str] = None  # 上下文
```

### 异常层次

```
BackendError (基类)
├── FileNotFoundError (404)
├── PermissionDeniedError (403)
└── ... (自定义异常)
```

## 最佳实践

1. **实现所有必需方法** - 确保实现 `RemoteBackend` 的所有抽象方法
2. **正确的异常处理** - 抛出合适的异常类型，便于上层处理
3. **资源管理** - 实现 `close()` 或 `disconnect()` 方法清理资源
4. **连接池** - 对于网络后端，使用连接池提高性能
5. **重试机制** - 网络操作应该包含重试逻辑
6. **日志记录** - 记录关键操作和错误，便于调试
7. **单元测试** - 为后端实现编写完整的测试

## 迁移指南

### 从旧版 RemoteClient 迁移

旧代码：
```python
from remotefs.remote_client import RemoteClient

client = RemoteClient("http://server:8080", "token")
content = client.read_file("/test.txt")
```

新代码：
```python
from remotefs import HTTPBackend

backend = HTTPBackend("http://server:8080", "token")
content = backend.read_file("/test.txt")
```

FUSE Handler 仍然支持旧的 `client` 参数以保证向后兼容。
