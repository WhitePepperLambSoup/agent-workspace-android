"""POSIX / Android 环境下的凭据安全存储实现。

替换原项目中依赖 Windows DPAPI (CryptProtectData) 的实现,
使用 AES-256-GCM 加密, 主密钥采用 POSIX 0600 (用户私有) 文件权限严格保护。
"""

from __future__ import annotations

import json
import os
import stat
from contextlib import suppress
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class PosixFileCredentialStore:
    """Linux / Android Termux 本地安全凭据库。"""

    def __init__(self, root_dir: Path | None = None) -> None:
        self._dir = root_dir or (Path.home() / ".agent-workspace" / "credentials")
        self._dir.mkdir(parents=True, exist_ok=True)
        # 强制目录为 0700 (只有当前用户有读写执行权限)
        with suppress(OSError):
            os.chmod(self._dir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

        self._key_file = self._dir / ".master_key"
        self._vault_file = self._dir / "vault.enc"
        self._master_key = self._get_or_create_master_key()

    def _get_or_create_master_key(self) -> bytes:
        if self._key_file.exists():
            return self._key_file.read_bytes()

        # 生成 256 位加密主密钥
        key = AESGCM.generate_key(bit_length=256)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        mode = stat.S_IRUSR | stat.S_IWUSR  # 0600
        fd = os.open(str(self._key_file), flags, mode)
        with os.fdopen(fd, "wb") as f:
            f.write(key)
        return key

    def _decrypt_vault(self) -> dict[str, str]:
        if not self._vault_file.exists():
            return {}

        data = self._vault_file.read_bytes()
        if len(data) < 12:
            return {}

        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(self._master_key)
        try:
            decrypted = aesgcm.decrypt(nonce, ciphertext, None)
            return json.loads(decrypted.decode("utf-8"))
        except Exception:
            return {}

    def _encrypt_vault(self, records: dict[str, str]) -> None:
        raw = json.dumps(records, ensure_ascii=False).encode("utf-8")
        nonce = os.urandom(12)
        aesgcm = AESGCM(self._master_key)
        ciphertext = aesgcm.encrypt(nonce, raw, None)

        tmp_file = self._vault_file.with_suffix(".tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        mode = stat.S_IRUSR | stat.S_IWUSR  # 0600
        fd = os.open(str(tmp_file), flags, mode)
        with os.fdopen(fd, "wb") as f:
            f.write(nonce + ciphertext)

        os.replace(tmp_file, self._vault_file)

    def get_credential(self, key: str) -> str | None:
        vault = self._decrypt_vault()
        return vault.get(key)

    def set_credential(self, key: str, value: str) -> None:
        vault = self._decrypt_vault()
        vault[key] = value
        self._encrypt_vault(vault)

    def delete_credential(self, key: str) -> bool:
        vault = self._decrypt_vault()
        if key in vault:
            del vault[key]
            self._encrypt_vault(vault)
            return True
        return False

    def list_credentials(self) -> list[str]:
        vault = self._decrypt_vault()
        return sorted(vault.keys())


# 全局单例
_DEFAULT_STORE = PosixFileCredentialStore()


def get_credential(key: str) -> str | None:
    return _DEFAULT_STORE.get_credential(key)


def set_credential(key: str, value: str) -> None:
    _DEFAULT_STORE.set_credential(key, value)


def delete_credential(key: str) -> bool:
    return _DEFAULT_STORE.delete_credential(key)


def list_credentials() -> list[str]:
    return _DEFAULT_STORE.list_credentials()
