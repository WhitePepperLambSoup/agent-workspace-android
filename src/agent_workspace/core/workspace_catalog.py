"""Workspace catalog persisted as a small JSON document."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


class WorkspaceCatalogError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WorkspaceEntry:
    path: str
    name: str
    last_used: float = 0.0

    def to_document(self) -> dict[str, object]:
        return {"path": self.path, "name": self.name, "last_used": self.last_used}


class WorkspaceCatalog:
    """Named workspace list with recent-use ordering."""

    def __init__(
        self,
        path: str | Path,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = Path(path)
        self._clock = clock
        self._entries: dict[str, WorkspaceEntry] = {}
        if self.path.is_file():
            self._load()

    def _load(self) -> None:
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkspaceCatalogError(f"cannot read workspace catalog: {exc}") from exc
        if not isinstance(document, dict) or not isinstance(document.get("workspaces"), list):
            raise WorkspaceCatalogError("workspace catalog is invalid")
        for raw in document["workspaces"]:
            if not isinstance(raw, dict):
                raise WorkspaceCatalogError("workspace catalog entry is invalid")
            path = raw.get("path")
            name = raw.get("name")
            last_used = raw.get("last_used", 0.0)
            if not isinstance(path, str) or not path or not isinstance(name, str) or not name:
                raise WorkspaceCatalogError("workspace catalog entry is invalid")
            self._entries[path] = WorkspaceEntry(path, name, float(last_used))

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(
                {"workspaces": [entry.to_document() for entry in self.entries()]},
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return self.path

    def add(self, path: str | Path, name: str | None = None) -> WorkspaceEntry:
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_dir():
            raise WorkspaceCatalogError(f"workspace is not a directory: {resolved}")
        entry = WorkspaceEntry(
            str(resolved),
            name.strip() if name else resolved.name,
            self._clock(),
        )
        self._entries[entry.path] = entry
        self.save()
        return entry

    def remove(self, path: str | Path) -> None:
        resolved = str(Path(path).expanduser().resolve())
        if resolved not in self._entries:
            raise KeyError(f"unknown workspace: {resolved}")
        del self._entries[resolved]
        self.save()

    def touch(self, path: str | Path) -> WorkspaceEntry:
        resolved = str(Path(path).expanduser().resolve())
        entry = self._entries.get(resolved)
        if entry is None:
            return self.add(resolved)
        updated = WorkspaceEntry(entry.path, entry.name, self._clock())
        self._entries[resolved] = updated
        self.save()
        return updated

    def entries(self) -> tuple[WorkspaceEntry, ...]:
        return tuple(
            sorted(self._entries.values(), key=lambda entry: (-entry.last_used, entry.name))
        )


__all__ = ["WorkspaceCatalog", "WorkspaceCatalogError", "WorkspaceEntry"]
