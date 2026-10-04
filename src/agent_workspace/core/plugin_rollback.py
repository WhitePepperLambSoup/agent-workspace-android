"""Plugin rollback store.

Keeps the manifest, archive digest, and install time of every installed
plugin version and can roll the active version back to an earlier release.
Rollbacks are data-only decisions: callers install/activate the returned
manifest themselves.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_workspace.core.plugins import PluginManifest


class PluginRollbackError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PluginVersionRecord:
    version: int
    archive_sha256: str
    manifest: PluginManifest
    installed_at: float

    def to_document(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "archive_sha256": self.archive_sha256,
            "manifest": self.manifest.to_document(),
            "installed_at": self.installed_at,
        }


@dataclass(frozen=True, slots=True)
class PluginRollback:
    plugin_id: str
    from_version: int
    to_version: int
    manifest: PluginManifest
    archive_sha256: str

    def to_document(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "manifest": self.manifest.to_document(),
            "archive_sha256": self.archive_sha256,
        }


class PluginRollbackStore:
    """JSON-persisted install history with one active version per plugin."""

    def __init__(self, path: str | Path, *, clock: Any = time.time) -> None:
        self.path = Path(path)
        self._clock = clock
        self._plugins: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PluginRollbackError(f"cannot read plugin rollback store: {exc}") from exc
        raw_plugins = document.get("plugins") if isinstance(document, dict) else None
        if not isinstance(raw_plugins, dict):
            raise PluginRollbackError("plugin rollback store must declare a plugins object")
        for plugin_id, raw in raw_plugins.items():
            self._plugins[str(plugin_id)] = self._parse_plugin(str(plugin_id), raw)

    def _parse_plugin(self, plugin_id: str, raw: object) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise PluginRollbackError(f"plugin {plugin_id!r} history is invalid")
        current_version = raw.get("current_version")
        raw_history = raw.get("history")
        if not isinstance(current_version, int) or not isinstance(raw_history, list):
            raise PluginRollbackError(f"plugin {plugin_id!r} history is invalid")
        history: list[PluginVersionRecord] = []
        seen_versions: set[int] = set()
        for entry in raw_history:
            record = self._parse_record(plugin_id, entry)
            if record.version in seen_versions:
                raise PluginRollbackError(
                    f"plugin {plugin_id!r} history has duplicate version {record.version}"
                )
            seen_versions.add(record.version)
            history.append(record)
        history.sort(key=lambda record: record.version, reverse=True)
        versions = {record.version for record in history}
        if current_version not in versions:
            raise PluginRollbackError(
                f"plugin {plugin_id!r} current version {current_version} is not in history"
            )
        return {"current_version": current_version, "history": history}

    def _parse_record(self, plugin_id: str, raw: object) -> PluginVersionRecord:
        if not isinstance(raw, dict):
            raise PluginRollbackError(f"plugin {plugin_id!r} history record is invalid")
        try:
            manifest = PluginManifest.from_document(raw.get("manifest"))
            version = int(raw["version"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PluginRollbackError(f"plugin {plugin_id!r} history record is invalid") from exc
        if manifest.id != plugin_id:
            raise PluginRollbackError(
                f"plugin {plugin_id!r} history contains manifest for {manifest.id!r}"
            )
        if manifest.version != version:
            raise PluginRollbackError(
                f"plugin {plugin_id!r} history version {version} does not match its manifest"
            )
        try:
            archive_sha256 = str(raw["archive_sha256"])
            installed_at = float(raw["installed_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PluginRollbackError(f"plugin {plugin_id!r} history record is invalid") from exc
        return PluginVersionRecord(version, archive_sha256, manifest, installed_at)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        document: dict[str, Any] = {
            "plugins": {
                plugin_id: {
                    "current_version": state["current_version"],
                    "history": [record.to_document() for record in state["history"]],
                }
                for plugin_id, state in self._plugins.items()
            }
        }
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(document, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, self.path)

    def record_install(
        self,
        manifest: PluginManifest,
        archive_sha256: str,
        *,
        installed_at: float | None = None,
    ) -> PluginVersionRecord:
        if (
            not archive_sha256
            or any(character not in "0123456789abcdef" for character in archive_sha256.casefold())
            or len(archive_sha256) != 64
        ):
            raise PluginRollbackError("plugin archive sha256 must be a 64-character hex digest")
        state = self._plugins.get(manifest.id, {"current_version": 0, "history": []})
        versions = {record.version for record in state["history"]}
        if manifest.version in versions:
            raise PluginRollbackError(
                f"plugin {manifest.id!r} version {manifest.version} is already recorded"
            )
        record = PluginVersionRecord(
            manifest.version,
            archive_sha256.casefold(),
            manifest,
            float(installed_at) if installed_at is not None else float(self._clock()),
        )
        state["history"] = [record, *state["history"]]
        state["history"] = sorted(state["history"], key=lambda item: item.version, reverse=True)
        state["current_version"] = max(record.version, int(state["current_version"]))
        self._plugins[manifest.id] = state
        self.save()
        return record

    def current(self, plugin_id: str) -> PluginVersionRecord | None:
        state = self._plugins.get(plugin_id)
        if state is None:
            return None
        current_version = int(state["current_version"])
        return next(
            (record for record in state["history"] if record.version == current_version),
            None,
        )

    def history(self, plugin_id: str) -> tuple[PluginVersionRecord, ...]:
        state = self._plugins.get(plugin_id)
        if state is None:
            return ()
        return tuple(state["history"])

    def rollback(
        self,
        plugin_id: str,
        *,
        target_version: int | None = None,
    ) -> PluginRollback:
        state = self._plugins.get(plugin_id)
        if state is None:
            raise PluginRollbackError(f"plugin {plugin_id!r} has no recorded history")
        history: list[PluginVersionRecord] = list(state["history"])
        current_version = int(state["current_version"])
        current_record = next(
            (record for record in history if record.version == current_version), None
        )
        if current_record is None:
            raise PluginRollbackError(f"plugin {plugin_id!r} current version is missing")
        if target_version is None:
            older = [record for record in history if record.version < current_version]
            if not older:
                raise PluginRollbackError(f"plugin {plugin_id!r} has no earlier version")
            target = older[0]  # history is sorted newest first, so this is the newest older one
        else:
            candidate = next(
                (record for record in history if record.version == target_version), None
            )
            if candidate is None:
                raise PluginRollbackError(
                    f"plugin {plugin_id!r} version {target_version} is not in history"
                )
            target = candidate
            if target.version >= current_version:
                raise PluginRollbackError("plugin rollback target must be earlier than current")
        state["current_version"] = target.version
        self.save()
        return PluginRollback(
            plugin_id=plugin_id,
            from_version=current_version,
            to_version=target.version,
            manifest=target.manifest,
            archive_sha256=target.archive_sha256,
        )


__all__ = [
    "PluginRollback",
    "PluginRollbackError",
    "PluginRollbackStore",
    "PluginVersionRecord",
]
