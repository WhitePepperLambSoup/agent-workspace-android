"""Declarative plugin manifests and a validated plugin registry.

Plugins declare metadata and optional tool/module entry points. This module
validates and versions manifests; execution of plugin code remains the
caller's responsibility so installation never runs untrusted Python.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_PLUGIN_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
_SCHEMA_VERSION = 1


class PluginError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PluginManifest:
    id: str
    name: str
    version: int
    schema_version: int = _SCHEMA_VERSION
    entry_point: str = ""
    tools: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    sha256: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if _PLUGIN_ID.fullmatch(self.id) is None:
            raise PluginError("plugin id must be lowercase ASCII letters, digits, '.', '_' or '-'")
        if not self.name.strip():
            raise PluginError("plugin name may not be empty")
        if self.version < 1:
            raise PluginError("plugin version must be positive")
        if self.schema_version != _SCHEMA_VERSION:
            raise PluginError(f"plugin schema {self.schema_version} is unsupported")
        if self.entry_point and not Path(self.entry_point).suffix == ".py":
            raise PluginError("plugin entry_point must be a .py module when set")
        if self.sha256 and (
            len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256)
        ):
            raise PluginError("plugin sha256 must be a 64-character hex digest")

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "schema_version": self.schema_version,
            "entry_point": self.entry_point,
            "tools": list(self.tools),
            "requires": list(self.requires),
            "conflicts": list(self.conflicts),
            "sha256": self.sha256,
            "description": self.description,
        }

    @classmethod
    def from_document(cls, value: object) -> PluginManifest:
        if not isinstance(value, dict):
            raise PluginError("plugin manifest must be an object")
        try:
            return cls(
                id=str(value["id"]),
                name=str(value["name"]),
                version=int(value["version"]),
                schema_version=int(value.get("schema_version", _SCHEMA_VERSION)),
                entry_point=str(value.get("entry_point", "")),
                tools=tuple(str(item) for item in value.get("tools", ())),
                requires=tuple(str(item) for item in value.get("requires", ())),
                conflicts=tuple(str(item) for item in value.get("conflicts", ())),
                sha256=str(value.get("sha256", "")),
                description=str(value.get("description", "")),
            )
        except PluginError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise PluginError("plugin manifest is invalid") from exc


@dataclass(slots=True)
class PluginRegistry:
    manifests: dict[str, PluginManifest] = field(default_factory=dict)

    def validate_manifest(self, manifest: PluginManifest) -> None:
        existing = self.manifests.get(manifest.id)
        if existing is not None and existing.version > manifest.version:
            raise PluginError(
                f"plugin {manifest.id!r} would downgrade version "
                f"{existing.version} to {manifest.version}"
            )
        missing = [plugin_id for plugin_id in manifest.requires if plugin_id not in self.manifests]
        if missing:
            raise PluginError(
                f"plugin {manifest.id!r} requires missing plugins: {', '.join(missing)}"
            )
        conflicts = [plugin_id for plugin_id in manifest.conflicts if plugin_id in self.manifests]
        if conflicts:
            raise PluginError(f"plugin {manifest.id!r} conflicts with: {', '.join(conflicts)}")

    def register(self, manifest: PluginManifest) -> None:
        self.validate_manifest(manifest)
        self.manifests[manifest.id] = manifest

    def _atomic_install_bytes(
        self,
        destination_dir: Path,
        target_path: Path,
        data: bytes,
        manifest: PluginManifest,
    ) -> None:
        def _write(stream: Any) -> None:
            stream.write(data)

        self._atomic_install_op(destination_dir, target_path, _write, manifest)

    def _atomic_install_op(
        self,
        destination_dir: Path,
        target_path: Path,
        write_callback: Any,
        manifest: PluginManifest,
    ) -> None:
        temporary: Path | None = None
        backup: Path | None = None
        existed = target_path.exists()
        old_manifest = self.manifests.get(manifest.id)

        try:
            with tempfile.NamedTemporaryFile(
                dir=destination_dir,
                prefix=f".{target_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp_file:
                temporary = Path(tmp_file.name)
                write_callback(tmp_file)
                tmp_file.flush()

            if existed:
                with tempfile.NamedTemporaryFile(
                    dir=destination_dir,
                    prefix=f".{target_path.name}.bak.",
                    suffix=".tmp",
                    delete=False,
                ) as backup_file:
                    backup = Path(backup_file.name)
                shutil.copy2(target_path, backup)

            temporary.replace(target_path)
            temporary = None

            self.manifests[manifest.id] = manifest

            if backup and backup.exists():
                with suppress(OSError):
                    backup.unlink()

        except Exception:
            if temporary and temporary.exists():
                with suppress(OSError):
                    temporary.unlink()
            if existed and backup and backup.exists():
                with suppress(OSError):
                    backup.replace(target_path)
            elif not existed and target_path.exists():
                with suppress(OSError):
                    target_path.unlink()
            if old_manifest is not None:
                self.manifests[manifest.id] = old_manifest
            else:
                self.manifests.pop(manifest.id, None)
            raise

    def install_manifest(self, source: str | Path, destination: str | Path) -> PluginManifest:
        source_path = Path(source)
        destination_path = Path(destination).expanduser().resolve()
        raw = json.loads(source_path.read_text(encoding="utf-8"))
        manifest = PluginManifest.from_document(raw)
        self.validate_manifest(manifest)
        destination_path.mkdir(parents=True, exist_ok=True)
        target = destination_path / f"{manifest.id}.json"
        payload = (json.dumps(manifest.to_document(), indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        self._atomic_install_bytes(destination_path, target, payload, manifest)
        return manifest

    @staticmethod
    def hash_file(path: str | Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    def verify_file(self, manifest: PluginManifest, path: str | Path) -> bool:
        if not manifest.sha256:
            return True
        return self.hash_file(path) == manifest.sha256

    def install_file(
        self,
        source: str | Path,
        destination: str | Path,
        manifest: PluginManifest,
    ) -> Path:
        source_path = Path(source)
        if not self.verify_file(manifest, source_path):
            raise PluginError(f"plugin {manifest.id!r} content hash does not match its manifest")
        self.validate_manifest(manifest)
        destination_path = Path(destination).expanduser().resolve()
        destination_path.mkdir(parents=True, exist_ok=True)
        target = destination_path / source_path.name

        def _copy(stream: Any) -> None:
            with source_path.open("rb") as incoming:
                shutil.copyfileobj(incoming, stream, length=1024 * 1024)

        self._atomic_install_op(destination_path, target, _copy, manifest)
        return target

    def install_archive(
        self,
        payload: bytes,
        envelope: object,
        destination: str | Path,
        *,
        public_key_pem: bytes,
    ) -> Path:
        """Verify a signed archive before atomically activating its payload.

        Signature verification happens before any destination directory is
        created or existing plugin file is replaced.  The manifest's entry
        point is used as the filename, while path traversal is rejected.
        """
        from agent_workspace.core.plugin_archives import validate_plugin_archive

        validation = validate_plugin_archive(payload, envelope, public_key_pem)
        if not validation.valid or validation.plugin is None:
            raise PluginError(f"plugin archive verification failed: {validation.reason}")
        manifest = validation.plugin
        self.validate_manifest(manifest)
        destination_path = Path(destination).expanduser().resolve()
        entry_point = (
            Path(manifest.entry_point) if manifest.entry_point else Path(f"{manifest.id}.archive")
        )
        if entry_point.is_absolute() or ".." in entry_point.parts:
            raise PluginError("plugin archive entry point escapes its destination")
        target = destination_path / entry_point
        target.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_install_bytes(target.parent, target, payload, manifest)
        return target


__all__ = [
    "PluginError",
    "PluginManifest",
    "PluginRegistry",
]
