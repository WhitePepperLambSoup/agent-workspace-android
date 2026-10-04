"""Workspace file version history projected from ``file.version.recorded``.

The projection tracks successful write_file executions without duplicating
file content; callers can use the recorded SHA-256 to read the matching file
or checkpoint when needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_workspace.application.ports import EventStore
from agent_workspace.core.events import Event


@dataclass(frozen=True, slots=True)
class FileVersion:
    path: str
    sha256: str
    bytes: int
    attempt_id: str
    recorded_at: str
    sequence: int | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "attempt_id": self.attempt_id,
            "recorded_at": self.recorded_at,
            "sequence": self.sequence,
        }


class FileHistoryManager:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def versions(self, session_id: str, path: str | None = None) -> list[FileVersion]:
        versions: list[FileVersion] = []
        for event in self._store.list_events(session_id):
            if event.type != "file.version.recorded":
                continue
            version = _version_from_event(event)
            if version is None:
                continue
            if path is not None and version.path != path:
                continue
            versions.append(version)
        versions.sort(key=lambda item: (item.recorded_at, item.sequence or 0))
        return versions

    def latest(self, session_id: str, path: str) -> FileVersion | None:
        versions = self.versions(session_id, path)
        return versions[-1] if versions else None


def _version_from_event(event: Event) -> FileVersion | None:
    data = event.data
    path = data.get("path")
    digest = data.get("sha256")
    size = data.get("bytes")
    attempt_id = data.get("attempt_id")
    if (
        not isinstance(path, str)
        or not path
        or not isinstance(digest, str)
        or len(digest) != 64
        or type(size) is not int
        or size < 0
        or not isinstance(attempt_id, str)
    ):
        return None
    return FileVersion(path, digest, size, attempt_id, event.created_at, event.sequence)


__all__ = ["FileHistoryManager", "FileVersion"]
