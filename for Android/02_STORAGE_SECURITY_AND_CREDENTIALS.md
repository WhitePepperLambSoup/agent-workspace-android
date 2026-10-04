> 历史方案说明：本页保留早期 Termux/原生宿主设计供参考。当前默认 APK 使用 Chaquopy Python 3.12、CPU JNI 推理和可选 PRoot 工具链；旧页的全功能/后台保活/默认工具可用性描述不是当前验收结论。安装与构建请以 [README](README.md)、[当前架构](00_PORTING_OVERVIEW_AND_ARCHITECTURE.md) 和 [构建指南](10_APK_BUILD_AND_RELEASE_GUIDE.md) 为准。

# Android (Termux) 存储、安全与凭据管理改造方案

> 文档编号：AW-AND-02  
> 涉及模块：`src/agent_workspace/credentials.py`、`storage/sqlite.py`、`storage/lock.py`、`storage/recovery.py`  

---

## 1. 凭据系统 (Credentials) 跨平台重构

### 1.1 现状与问题分析
* **Windows 当前实现**：
  [`src/agent_workspace/credentials.py`](file:///d:/opencode%20program/Agent/src/agent_workspace/credentials.py) 目前依赖 Windows 原生数据保护 API（DPAPI）：
  ```python
  # ctypes.windll.crypt32.CryptProtectData
  # ctypes.windll.crypt32.CryptUnprotectData
  ```
  在 Android / Termux 环境下，`windll` 直接抛出 `AttributeError: module 'ctypes' has no attribute 'windll'`。
* **目标契约**：
  必须为凭据管理抽象出通用的 `CredentialStore` 接口，根据操作系统动态挂载适配器。

### 1.2 跨平台抽象设计

```python
# 抽象协议与工厂
class CredentialStore(Protocol):
    def get_secret(self, key: str) -> str | None: ...
    def set_secret(self, key: str, value: str) -> None: ...
    def delete_secret(self, key: str) -> bool: ...
    def list_keys(self) -> list[str]: ...
```

### 1.3 Termux 环境下的安全方案实现：`PosixFileCredentialStore`

由于 Termux 处于 Linux 沙盒中，最实用且安全的设计是基于 **AES-256-GCM + 0600 POSIX 权限受保护的本地密钥库**：

```python
import os
import stat
import json
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class PosixFileCredentialStore:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self._dir = storage_dir or (Path.home() / ".agent-workspace" / "credentials")
        self._dir.mkdir(parents=True, exist_ok=True)
        # 强制设置目录权限为仅当前用户可读写执行 (0700)
        os.chmod(self._dir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

        self._key_file = self._dir / ".master_key"
        self._data_file = self._dir / "vault.enc"
        self._master_key = self._load_or_create_master_key()

    def _load_or_create_master_key(self) -> bytes:
        if self._key_file.exists():
            # 严格校验权限
            mode = os.stat(self._key_file).st_mode
            if mode & (stat.S_IRWXG | stat.S_IRWXO):
                raise PermissionError("Master key file permissions are insecure (must be 0600)")
            return self._key_file.read_bytes()

        # 随机生成 256 位密钥
        key = AESGCM.generate_key(bit_length=256)
        # 0600 创建文件
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(str(self._key_file), flags, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "wb") as f:
            f.write(key)
        return key

    def set_secret(self, key: str, value: str) -> None:
        records = self._decrypt_all()
        records[key] = value
        self._encrypt_all(records)

    def get_secret(self, key: str) -> str | None:
        records = self._decrypt_all()
        return records.get(key)
```

> **安全优势**：
> 1. 完全符合 Android Linux 的 UID 隔离原则，其他任何应用都无法读取该文件；
> 2. 规避了外部第三方 Keyring 守护进程的复杂依赖。

---

## 2. 存储与 SQLite WAL 在 Termux 的运行优化

### 2.1 SQLite3 兼容性
* **底层库验证**：
  Termux 的 Python 3.12 动态链接了系统的 `libsqlite3.so`。经核查，系统预装的 SQLite 均为 3.40+ 版本，**默认编译了 FTS5 全文搜索、JSON1、RTREE 与 WAL 模块**。
* **数据库路径配置**：
  * 数据库路径统一映射为 `$HOME/.agent-workspace/sessions.db`；
  * **严禁软链接至外部共享存储**。

### 2.2 跨平台互斥文件锁：`ProcessWriteLock`
* **现有基础**：在提交 `072db5b` 中，项目已经为 Linux/POSIX 引入了 `fcntl.flock`。
* **在 Android 上的注意事项**：
  ```python
  import fcntl
  import os


  class ProcessWriteLock:
      def acquire(self) -> None:
          # 在 Termux 的 ext4 文件系统上完全兼容
          fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
  ```
  在 Termux 内部存储上，`flock` 的并发互斥性 100% 成立，能有效保证单写者模型（桌面/CLI 不冲突）。

---

## 3. 文件检查点与恢复机制 (Recovery)

* **CAS（Compare-And-Swap）校验**：
  [`storage/recovery.py`](file:///d:/opencode%20program/Agent/src/agent_workspace/storage/recovery.py) 中原先使用 DPAPI 对暂存检查点内容进行加密校验。
* **改造对齐**：
  将检查点的哈希签名与加密直接对接到上述 `PosixFileCredentialStore` 中的同款 AES-GCM 引擎，确保灾难恢复、代码回滚（Rollback）逻辑在 Linux 平台无差别运行。
