# RemoteFS 后端开发指南

RemoteFS 使用**后端抽象层**设计，让开发者可以轻松接入不同的远程存储后端。

## 架构

```
┌─────────────────────────────────────┐
│         FUSE Handler                │  ← 文件系统层
├─────────────────────────────────────┤
│         Metadata Cache              │  ← 缓存层
├─────────────────────────────────────┤
│      RemoteBackend (抽象接口)       │  ← 抽象层
├──────────────┬──────────────────────┤
│  HTTPBackend │  YourCustomBackend   │  ← 具体实现
└──────────────┴──────────────────────┘
```

## 核心接口

实现 `remotefs.backend.RemoteBackend` 抽象类：

```python
from remotefs import RemoteBackend, FileEntry, ExecResult

class MyBackend(RemoteBackend):
    """自定义后端实现"""

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
        """索引搜索（可选）"""
        raise NotImplementedError("Search not supported")
```

## 接入示例

### 示例 1: 本地文件系统

```python
"""本地文件系统后端"""

import os
import subprocess
from pathlib import Path
from typing import List, Optional

from remotefs import RemoteBackend, FileEntry, ExecResult


class LocalBackend(RemoteBackend):
    """本地文件系统后端"""

    def __init__(self, root: str):
        self.root = Path(root).expanduser()

    def _resolve(self, path: str) -> Path:
        return self.root / path.lstrip("/")

    def read_file(self, path: str) -> bytes:
        with open(self._resolve(path), "rb") as f:
            return f.read()

    def write_file(self, path: str, content: bytes) -> bool:
        full_path = self._resolve(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(content)
        return True

    def delete_file(self, path: str) -> bool:
        self._resolve(path).unlink()
        return True

    def file_exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def list_dir(self, path: str) -> List[FileEntry]:
        entries = []
        for item in self._resolve(path).iterdir():
            entries.append(FileEntry(
                name=item.name,
                type="dir" if item.is_dir() else "file",
                size=item.stat().st_size if item.is_file() else None,
                mtime=item.stat().st_mtime,
            ))
        return entries

    def create_dir(self, path: str) -> bool:
        self._resolve(path).mkdir(parents=True, exist_ok=True)
        return True

    def delete_dir(self, path: str) -> bool:
        os.rmdir(self._resolve(path))
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

### 示例 2: S3 存储

```python
"""Amazon S3 后端"""

import boto3
from typing import List, Optional
from remotefs import RemoteBackend, FileEntry, ExecResult


class S3Backend(RemoteBackend):
    """S3 存储桶后端"""

    def __init__(self, bucket: str, region: str = "us-east-1"):
        self.bucket = bucket
        self.s3 = boto3.client("s3", region_name=region)

    def _key(self, path: str) -> str:
        return path.lstrip("/")

    def read_file(self, path: str) -> bytes:
        response = self.s3.get_object(Bucket=self.bucket, Key=self._key(path))
        return response["Body"].read()

    def write_file(self, path: str, content: bytes) -> bool:
        self.s3.put_object(Bucket=self.bucket, Key=self._key(path), Body=content)
        return True

    def delete_file(self, path: str) -> bool:
        self.s3.delete_object(Bucket=self.bucket, Key=self._key(path))
        return True

    def file_exists(self, path: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=self._key(path))
            return True
        except self.s3.exceptions.ClientError:
            return False

    def list_dir(self, path: str) -> List[FileEntry]:
        prefix = self._key(path)
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        response = self.s3.list_objects_v2(
            Bucket=self.bucket,
            Prefix=prefix,
            Delimiter="/",
        )

        entries = []
        for p in response.get("CommonPrefixes", []):
            entries.append(FileEntry(
                name=p["Prefix"].rstrip("/").split("/")[-1],
                type="dir",
            ))
        for obj in response.get("Contents", []):
            name = obj["Key"].split("/")[-1]
            if name:
                entries.append(FileEntry(
                    name=name,
                    type="file",
                    size=obj["Size"],
                    mtime=obj["LastModified"].timestamp(),
                ))
        return entries

    def create_dir(self, path: str) -> bool:
        key = self._key(path).rstrip("/") + "/"
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=b"")
        return True

    def delete_dir(self, path: str) -> bool:
        prefix = self._key(path).rstrip("/") + "/"
        paginator = self.s3.get_paginator("list_objects_v2")
        objects = [{"Key": obj["Key"]} for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix) for obj in page.get("Contents", [])]
        if objects:
            self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": objects})
        return True

    def exec_cmd(self, cmd: str, args: List[str], cwd: Optional[str] = None) -> ExecResult:
        raise NotImplementedError("S3 不支持命令执行")
```

### 示例 3: SSH/SFTP

```python
"""SSH/SFTP 后端"""

import paramiko
from typing import List, Optional
from remotefs import RemoteBackend, FileEntry, ExecResult


class SSHBackend(RemoteBackend):
    """SSH/SFTP 远程后端"""

    def __init__(self, host: str, port: int = 22, username: str = "",
                 password: str = "", key_path: Optional[str] = None):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {"hostname": host, "port": port, "username": username}
        if key_path:
            connect_kwargs["key_filename"] = key_path
        if password:
            connect_kwargs["password"] = password

        self.client.connect(**connect_kwargs)
        self.sftp = self.client.open_sftp()

    def close(self):
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
        for attr in self.sftp.listdir_attr(path):
            entries.append(FileEntry(
                name=attr.filename,
                type="dir" if attr.st_mode & 0o40000 else "file",
                size=attr.st_size,
                mtime=attr.st_mtime,
                mode=attr.st_mode & 0o777,
            ))
        return entries

    def create_dir(self, path: str) -> bool:
        self.sftp.mkdir(path)
        return True

    def delete_dir(self, path: str) -> bool:
        self.sftp.rmdir(path)
        return True

    def exec_cmd(self, cmd: str, args: List[str], cwd: Optional[str] = None) -> ExecResult:
        full_cmd = f"cd {cwd} && {cmd} {' '.join(args)}" if cwd else f"{cmd} {' '.join(args)}"
        stdin, stdout, stderr = self.client.exec_command(full_cmd)
        return ExecResult(
            stdout=stdout.read(),
            stderr=stderr.read(),
            exit_code=stdout.channel.recv_exit_status(),
        )
```

## 使用自定义后端

```python
from remotefs import RemoteFS, MetadataCache
from my_backend import LocalBackend  # 你的后端

# 创建后端
backend = LocalBackend(root="/data/storage")

# 创建缓存
cache = MetadataCache(ttl=5)

# 挂载文件系统
fs = RemoteFS(backend=backend, cache=cache, root="/mnt/myfs")
fs.main()
```

## API 参考

### 数据类

```python
@dataclass
class FileEntry:
    name: str              # 文件名
    type: str              # "file" 或 "dir"
    size: Optional[int]    # 文件大小
    mode: Optional[int]    # 权限模式
    mtime: Optional[float] # 修改时间

@dataclass
class ExecResult:
    stdout: bytes    # 标准输出
    stderr: bytes    # 标准错误
    exit_code: int   # 退出码

@dataclass
class SearchResult:
    path: str              # 文件路径
    line: int              # 行号
    match: str             # 匹配内容
    context: Optional[str] # 上下文
```

### 异常

```python
BackendError              # 基类
├── FileNotFoundError     # 文件不存在
└── PermissionDeniedError # 权限拒绝
```

### 使用异常

```python
from remotefs import BackendError, FileNotFoundError, PermissionDeniedError

def read_file(self, path: str) -> bytes:
    if not self._exists(path):
        raise FileNotFoundError(f"文件不存在: {path}")
    if not self._readable(path):
        raise PermissionDeniedError(f"权限拒绝: {path}")
    # ...
```

## 测试

```python
import pytest
from my_backend import MyBackend

@pytest.fixture
def backend():
    return MyBackend(...)

class TestMyBackend:
    def test_read_write(self, backend):
        backend.write_file("/test.txt", b"hello")
        assert backend.read_file("/test.txt") == b"hello"

    def test_exists(self, backend):
        assert not backend.file_exists("/nope")
        backend.write_file("/exists.txt", b"")
        assert backend.file_exists("/exists.txt")

    def test_list_dir(self, backend):
        backend.write_file("/dir/file.txt", b"")
        entries = backend.list_dir("/dir")
        assert len(entries) == 1
        assert entries[0].name == "file.txt"
```