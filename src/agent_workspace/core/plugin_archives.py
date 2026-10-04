"""Plugin signed archive validation.

A plugin archive envelope binds a plugin manifest to the archive bytes with
an Ed25519 signature over the archive digest plus the canonical manifest.
Validation verifies both the signature and the content digest, then checks
that the manifest inside the envelope is structurally valid.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from agent_workspace.core.plugins import PluginError, PluginManifest

_ARCHIVE_VERSION = 1


class PluginArchiveError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PluginArchiveValidation:
    valid: bool
    plugin: PluginManifest | None
    reason: str
    digest_matches: bool = False
    signature_valid: bool = False

    def to_document(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "plugin": self.plugin.to_document() if self.plugin is not None else None,
            "reason": self.reason,
            "digest_matches": self.digest_matches,
            "signature_valid": self.signature_valid,
        }


def load_private_key(pem: bytes) -> Ed25519PrivateKey:
    try:
        key = serialization.load_pem_private_key(pem, password=None)
    except (ValueError, TypeError) as exc:
        raise PluginArchiveError(f"cannot load ed25519 private key: {exc}") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise PluginArchiveError("plugin archive signing requires an Ed25519 private key")
    return key


def load_public_key(pem: bytes) -> Ed25519PublicKey:
    try:
        key = serialization.load_pem_public_key(pem)
    except (ValueError, TypeError) as exc:
        raise PluginArchiveError(f"cannot load ed25519 public key: {exc}") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise PluginArchiveError("plugin archive validation requires an Ed25519 public key")
    return key


def _canonical_manifest(manifest: PluginManifest) -> bytes:
    return json.dumps(manifest.to_document(), sort_keys=True, separators=(",", ":")).encode("utf-8")


def _signature_message(payload: bytes, manifest: PluginManifest) -> bytes:
    return hashlib.sha256(payload).digest() + _canonical_manifest(manifest)


def sign_plugin_archive(
    payload: bytes,
    manifest: PluginManifest,
    private_key_pem: bytes,
    *,
    key_id: str = "",
) -> dict[str, Any]:
    """Return a detached envelope for one plugin archive payload."""
    if not payload:
        raise PluginArchiveError("plugin archive payload may not be empty")
    key = load_private_key(private_key_pem)
    signature = key.sign(_signature_message(payload, manifest))
    return {
        "version": _ARCHIVE_VERSION,
        "key_id": key_id,
        "plugin": manifest.to_document(),
        "archive_sha256": hashlib.sha256(payload).hexdigest(),
        "signature_hex": signature.hex(),
    }


def validate_plugin_archive(
    payload: bytes,
    envelope: object,
    public_key_pem: bytes,
) -> PluginArchiveValidation:
    if not isinstance(envelope, dict):
        return PluginArchiveValidation(False, None, "plugin archive envelope must be an object")
    if envelope.get("version") != _ARCHIVE_VERSION:
        return PluginArchiveValidation(
            False, None, "plugin archive envelope version is unsupported"
        )
    raw_sha256 = envelope.get("archive_sha256")
    raw_signature = envelope.get("signature_hex")
    if not isinstance(raw_sha256, str) or len(raw_sha256) != 64:
        return PluginArchiveValidation(False, None, "plugin archive sha256 is invalid")
    if not isinstance(raw_signature, str) or len(raw_signature) != 128:
        return PluginArchiveValidation(False, None, "plugin archive signature is invalid")
    try:
        plugin = PluginManifest.from_document(envelope.get("plugin"))
    except PluginError as exc:
        return PluginArchiveValidation(False, None, f"plugin manifest is invalid: {exc}")
    digest_matches = hashlib.sha256(payload).hexdigest() == raw_sha256
    try:
        key = load_public_key(public_key_pem)
        key.verify(bytes.fromhex(raw_signature), _signature_message(payload, plugin))
    except PluginArchiveError as exc:
        return PluginArchiveValidation(False, None, str(exc))
    except (InvalidSignature, ValueError) as exc:
        return PluginArchiveValidation(
            False,
            None,
            f"plugin archive signature verification failed: {exc}",
            digest_matches=digest_matches,
        )
    if not digest_matches:
        return PluginArchiveValidation(
            False,
            plugin,
            "plugin archive content hash does not match the envelope",
            digest_matches=False,
            signature_valid=True,
        )
    return PluginArchiveValidation(
        True,
        plugin,
        "plugin archive signature and content digest are valid",
        digest_matches=True,
        signature_valid=True,
    )


def validate_plugin_archive_files(
    archive_path: str | Path,
    envelope_path: str | Path,
    public_key_pem: bytes,
) -> PluginArchiveValidation:
    try:
        payload = Path(archive_path).read_bytes()
    except OSError as exc:
        raise PluginArchiveError(f"cannot read plugin archive: {archive_path}") from exc
    try:
        raw = json.loads(Path(envelope_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PluginArchiveError(f"cannot read plugin archive envelope: {envelope_path}") from exc
    return validate_plugin_archive(payload, raw, public_key_pem)


__all__ = [
    "PluginArchiveError",
    "PluginArchiveValidation",
    "load_private_key",
    "load_public_key",
    "sign_plugin_archive",
    "validate_plugin_archive",
    "validate_plugin_archive_files",
]
