from __future__ import annotations

import base64
import ctypes
import hashlib
import ipaddress
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from agent_workspace.config import default_data_dir, provider_origin

CREDENTIAL_NAMESPACE = "AgentWorkspace/provider-credential/v1"

_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2
_ERROR_NOT_FOUND = 1168
_CRYPTPROTECT_UI_FORBIDDEN = 0x1
_PROVIDER_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")

# Credential blobs are DPAPI-protected under the current Windows user so that
# machine-persisted Credential Manager entries cannot be decrypted by other
# local accounts. The marker distinguishes protected blobs from legacy
# plaintext entries written by earlier 0.1 alpha builds.
_PROTECTED_CREDENTIAL_PREFIX = "awdp1:"
_CREDENTIAL_ENTROPY_PREFIX = "agent-workspace/credential/v2/"


class CredentialStore(Protocol):
    def get(self, target: str) -> str | None: ...

    def set(self, target: str, secret: str) -> None: ...

    def delete(self, target: str) -> None: ...


@dataclass(slots=True)
class MemoryCredentialStore:
    """In-memory credential store intended for tests and ephemeral runtimes."""

    _credentials: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def get(self, target: str) -> str | None:
        return self._credentials.get(target)

    def set(self, target: str, secret: str) -> None:
        self._credentials[target] = secret

    def delete(self, target: str) -> None:
        self._credentials.pop(target, None)


def credential_target(provider_id: str, base_url: str) -> str:
    """Build a stable credential target scoped to a provider and endpoint origin."""

    if not isinstance(provider_id, str) or _PROVIDER_ID_PATTERN.fullmatch(provider_id) is None:
        raise ValueError("provider id must be lowercase ASCII letters, digits, '.', '_' or '-'")
    if not isinstance(base_url, str):
        raise ValueError("provider base URL must be a string")

    scheme, hostname, port = provider_origin(base_url)
    hostname = _normalize_hostname(hostname)
    origin_hostname = f"[{hostname}]" if ":" in hostname else hostname
    origin = f"{scheme}://{origin_hostname}:{port}"
    origin_hash = hashlib.sha256(origin.encode("utf-8")).hexdigest()
    return f"{CREDENTIAL_NAMESPACE}/{provider_id}/{origin_hash}"


def _normalize_hostname(hostname: str) -> str:
    try:
        return ipaddress.ip_address(hostname).compressed.lower()
    except ValueError:
        try:
            normalized = hostname.rstrip(".").encode("idna").decode("ascii").lower()
        except UnicodeError:
            raise ValueError("provider base URL contains an invalid hostname") from None
        if not normalized:
            raise ValueError("provider base URL contains an invalid hostname") from None
        return normalized


class _FILETIME(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]


class _CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", ctypes.c_uint32),
        ("Type", ctypes.c_uint32),
        ("TargetName", ctypes.c_wchar_p),
        ("Comment", ctypes.c_wchar_p),
        ("LastWritten", _FILETIME),
        ("CredentialBlobSize", ctypes.c_uint32),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", ctypes.c_uint32),
        ("AttributeCount", ctypes.c_uint32),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", ctypes.c_wchar_p),
        ("UserName", ctypes.c_wchar_p),
    ]


_PCREDENTIALW = ctypes.POINTER(_CREDENTIALW)


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("size", ctypes.c_uint32),
        ("data", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class WindowsCredentialStore:
    """Windows Credential Manager store whose blobs are DPAPI-protected for the current user.

    Entries persist across logon sessions (CRED_PERSIST_LOCAL_MACHINE), but the secret
    blob is encrypted with the current user's DPAPI key before it is written, so other
    local accounts on the same machine cannot decrypt the stored API key.
    """

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("Windows Credential Manager is only available on Windows")

        library: Any = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        library.CredReadW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.POINTER(_PCREDENTIALW),
        ]
        library.CredReadW.restype = ctypes.c_int
        library.CredWriteW.argtypes = [ctypes.POINTER(_CREDENTIALW), ctypes.c_uint32]
        library.CredWriteW.restype = ctypes.c_int
        library.CredDeleteW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32]
        library.CredDeleteW.restype = ctypes.c_int
        library.CredFree.argtypes = [ctypes.c_void_p]
        library.CredFree.restype = None
        self._library: Any = library

    def get(self, target: str) -> str | None:
        credential_pointer = _PCREDENTIALW()
        succeeded = self._library.CredReadW(
            target,
            _CRED_TYPE_GENERIC,
            0,
            ctypes.byref(credential_pointer),
        )
        if not succeeded:
            error_code = ctypes.get_last_error()
            if error_code == _ERROR_NOT_FOUND:
                return None
            raise _credential_error("CredReadW", error_code)
        if not credential_pointer:
            raise OSError("CredReadW returned an invalid credential buffer")

        try:
            credential = credential_pointer.contents
            blob = ctypes.string_at(
                credential.CredentialBlob,
                credential.CredentialBlobSize,
            )
            try:
                decoded = blob.decode("utf-8")
            except UnicodeDecodeError:
                raise OSError("credential contains an invalid UTF-8 blob") from None
            return _unprotect_credential_blob(target, decoded)
        finally:
            self._library.CredFree(ctypes.cast(credential_pointer, ctypes.c_void_p))

    def set(self, target: str, secret: str) -> None:
        try:
            protected_blob = _protect_credential_blob(target, secret)
        except UnicodeEncodeError:
            raise ValueError("credential secret must be valid UTF-8") from None

        encoded_blob = protected_blob.encode("utf-8")
        blob = ctypes.create_string_buffer(encoded_blob, max(1, len(encoded_blob)))
        credential = _CREDENTIALW()
        credential.Type = _CRED_TYPE_GENERIC
        credential.TargetName = target
        credential.CredentialBlobSize = len(encoded_blob)
        credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = _CRED_PERSIST_LOCAL_MACHINE

        if not self._library.CredWriteW(ctypes.byref(credential), 0):
            raise _credential_error("CredWriteW", ctypes.get_last_error())

    def delete(self, target: str) -> None:
        if self._library.CredDeleteW(target, _CRED_TYPE_GENERIC, 0):
            return
        error_code = ctypes.get_last_error()
        if error_code != _ERROR_NOT_FOUND:
            raise _credential_error("CredDeleteW", error_code)


def _credential_entropy(target: str) -> bytes:
    return hashlib.sha256(f"{_CREDENTIAL_ENTROPY_PREFIX}{target}".encode()).digest()


def _protect_credential_blob(target: str, secret: str) -> str:
    encoded_secret = secret.encode("utf-8")
    protected = protect_current_user_data(encoded_secret, entropy=_credential_entropy(target))
    return _PROTECTED_CREDENTIAL_PREFIX + base64.b64encode(protected).decode("ascii")


def _unprotect_credential_blob(target: str, blob: str) -> str:
    if not blob.startswith(_PROTECTED_CREDENTIAL_PREFIX):
        return blob
    payload = blob[len(_PROTECTED_CREDENTIAL_PREFIX) :]
    try:
        protected = base64.b64decode(payload, validate=True)
    except ValueError:
        raise OSError("credential blob is not valid protected data") from None
    try:
        unprotected = unprotect_current_user_data(
            protected,
            entropy=_credential_entropy(target),
        )
    except OSError:
        raise OSError(
            "credential is protected for a different Windows user; re-enter the API key"
        ) from None
    try:
        return unprotected.decode("utf-8")
    except UnicodeDecodeError:
        raise OSError("unprotected credential contains an invalid UTF-8 blob") from None


class FileCredentialStore:
    """POSIX fallback: a user-only (0600) JSON credential file under the data directory."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def _read(self) -> dict[str, str]:
        try:
            raw = self._path.read_bytes()
        except FileNotFoundError:
            return {}
        except OSError as exc:
            raise OSError(f"cannot read credential file: {self._path}") from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            raise OSError(f"credential file is corrupt: {self._path}") from None
        if not isinstance(payload, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in payload.items()
        ):
            raise OSError(f"credential file is corrupt: {self._path}")
        return payload

    def _write(self, payload: dict[str, str]) -> None:
        import os as _os
        import tempfile as _tempfile

        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = _tempfile.mkstemp(
            prefix=f".{self._path.name}.",
            suffix=".tmp",
            dir=self._path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with _os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
                stream.flush()
                _os.fsync(stream.fileno())
            _os.chmod(temporary, 0o600)
            _os.replace(temporary, self._path)
        except OSError:
            temporary.unlink(missing_ok=True)
            raise

    def get(self, target: str) -> str | None:
        return self._read().get(target)

    def set(self, target: str, secret: str) -> None:
        payload = self._read()
        payload[target] = secret
        self._write(payload)

    def delete(self, target: str) -> None:
        payload = self._read()
        payload.pop(target, None)
        self._write(payload)


def default_credential_store() -> CredentialStore:
    if sys.platform == "win32":
        return WindowsCredentialStore()
    return FileCredentialStore(default_data_dir() / "credentials.json")


def _credential_error(operation: str, error_code: int) -> OSError:
    return OSError(error_code, f"{operation} failed with Windows error {error_code}")


def protect_current_user_data(data: bytes, *, entropy: bytes) -> bytes:
    return _crypt_data(data, entropy=entropy, protect=True)


def unprotect_current_user_data(data: bytes, *, entropy: bytes) -> bytes:
    return _crypt_data(data, entropy=entropy, protect=False)


def _crypt_data(data: bytes, *, entropy: bytes, protect: bool) -> bytes:
    if sys.platform != "win32":
        raise OSError("Windows DPAPI is only available on Windows")
    if not entropy:
        raise ValueError("DPAPI entropy may not be empty")
    crypt32: Any = ctypes.WinDLL("Crypt32.dll", use_last_error=True)
    kernel32: Any = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
    operation = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    operation.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_wchar_p if protect else ctypes.POINTER(ctypes.c_wchar_p),
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(_DATA_BLOB),
    ]
    operation.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    input_blob, input_buffer = _data_blob(data)
    entropy_blob, entropy_buffer = _data_blob(entropy)
    output_blob = _DATA_BLOB()
    description = ctypes.c_wchar_p()
    try:
        description_argument: object = None if protect else ctypes.byref(description)
        if not operation(
            ctypes.byref(input_blob),
            "Agent Workspace file checkpoint" if protect else description_argument,
            ctypes.byref(entropy_blob),
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(output_blob),
        ):
            name = "CryptProtectData" if protect else "CryptUnprotectData"
            raise _credential_error(name, ctypes.get_last_error())
        result = ctypes.string_at(output_blob.data, output_blob.size)
        if output_blob.data and output_blob.size:
            ctypes.memset(output_blob.data, 0, output_blob.size)
        return result
    finally:
        ctypes.memset(input_buffer, 0, max(1, len(data)))
        ctypes.memset(entropy_buffer, 0, max(1, len(entropy)))
        if output_blob.data:
            kernel32.LocalFree(ctypes.cast(output_blob.data, ctypes.c_void_p))
        if description:
            kernel32.LocalFree(ctypes.cast(description, ctypes.c_void_p))


def _data_blob(data: bytes) -> tuple[_DATA_BLOB, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(data, max(1, len(data)))
    blob = _DATA_BLOB(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buffer
