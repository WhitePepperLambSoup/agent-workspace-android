"""Detached archive/file signing for session exports and backups.

The signature is a small JSON document containing the payload SHA-256 and an
HMAC-SHA256 over that digest plus optional metadata. It never embeds the key.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

_SIGNATURE_VERSION = 1


class ArchiveSignatureError(ValueError):
    pass


def _hmac_hex(key: bytes, digest: str, metadata: dict[str, str]) -> str:
    payload = json.dumps(
        {"digest": digest, "metadata": metadata},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def sign_bytes(
    payload: bytes,
    key: bytes,
    *,
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not key:
        raise ArchiveSignatureError("signing key may not be empty")
    digest = hashlib.sha256(payload).hexdigest()
    meta = dict(metadata or {})
    signature = _hmac_hex(key, digest, meta)
    return {
        "version": _SIGNATURE_VERSION,
        "sha256": digest,
        "metadata": meta,
        "hmac_sha256": signature,
    }


def sign_file(
    path: str | Path,
    key: bytes,
    *,
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        payload = Path(path).read_bytes()
    except OSError as exc:
        raise ArchiveSignatureError(f"cannot read file for signing: {path}") from exc
    return sign_bytes(payload, key, metadata=metadata)


def verify_bytes(payload: bytes, key: bytes, signature: object) -> bool:
    if not isinstance(signature, dict):
        raise ArchiveSignatureError("signature document must be an object")
    if signature.get("version") != _SIGNATURE_VERSION:
        raise ArchiveSignatureError("signature version is unsupported")
    digest = signature.get("sha256")
    raw_metadata = signature.get("metadata", {})
    mac = signature.get("hmac_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ArchiveSignatureError("signature digest is invalid")
    if not isinstance(raw_metadata, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in raw_metadata.items()
    ):
        raise ArchiveSignatureError("signature metadata is invalid")
    if not isinstance(mac, str) or len(mac) != 64:
        raise ArchiveSignatureError("signature HMAC is invalid")
    actual_digest = hashlib.sha256(payload).hexdigest()
    if not hmac.compare_digest(actual_digest, digest):
        return False
    expected = _hmac_hex(key, digest, raw_metadata)
    return hmac.compare_digest(expected, mac)


def verify_file(path: str | Path, key: bytes, signature: object) -> bool:
    try:
        payload = Path(path).read_bytes()
    except OSError as exc:
        raise ArchiveSignatureError(f"cannot read file for verification: {path}") from exc
    return verify_bytes(payload, key, signature)


def write_signature(destination: str | Path, signature: dict[str, Any]) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(signature, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


__all__ = [
    "ArchiveSignatureError",
    "sign_bytes",
    "sign_file",
    "verify_bytes",
    "verify_file",
    "write_signature",
]
