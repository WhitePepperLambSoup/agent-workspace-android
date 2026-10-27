"""Folders whose documents join a knowledge base by themselves.

The desktop scans each watched folder when it starts and every half hour. Supported files that
are new or changed since the last scan are added to that folder's knowledge base; the store skips
content it already holds. A file changed within the last minute may still be downloading, so it
waits for the next scan. Folders offered for watching: where WeChat and QQ keep received files,
when they exist on this computer.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_workspace.knowledge.store import (
    MAX_FILE_BYTES,
    SUPPORTED_SUFFIXES,
    KnowledgeError,
    KnowledgeStore,
)

SCAN_INTERVAL_SECONDS = 30 * 60
SETTLE_SECONDS = 60
MAX_FOLDERS = 20
# One scan adds at most this many documents; the rest follow in later scans.
MAX_ADDED_PER_SCAN = 100
_MAX_DEPTH = 6
_MAX_ENTRIES = 50_000


@dataclass(slots=True)
class WatchedFolder:
    path: str
    collection_id: str
    added_at: str
    last_scan: str | None = None
    added: int = 0  # documents this folder has added so far
    error: str | None = None
    seen: dict[str, list[int]] = field(default_factory=dict)  # file -> [size, mtime_ns]

    def document(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "collectionId": self.collection_id,
            "addedAt": self.added_at,
            "lastScan": self.last_scan,
            "added": self.added,
            "error": self.error,
            "files": len(self.seen),
        }


@dataclass(frozen=True, slots=True)
class ScanReport:
    added: int
    waiting: int  # changed too recently, or past this scan's limit
    failed: int


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def suggested_folders(home: Path | None = None) -> list[dict[str, str]]:
    """Where WeChat and QQ keep received files, for the folders that exist."""
    documents = (home or Path.home()) / "Documents"
    patterns = (
        ("WeChat", "WeChat Files/*/FileStorage/File"),
        ("WeChat", "xwechat_files/*/msg/file"),
        ("QQ", "Tencent Files/*/FileRecv"),
        ("QQ", "Tencent Files/*/nt_qq/nt_data/File"),
    )
    found: list[dict[str, str]] = []
    for label, pattern in patterns:
        try:
            matches = sorted(documents.glob(pattern))
        except OSError:
            continue
        found.extend({"label": label, "path": str(path)} for path in matches if path.is_dir())
    return found


class FolderWatch:
    """The watched folders of one knowledge store and what each scan has seen."""

    def __init__(
        self,
        root: Path,
        store: KnowledgeStore,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = root / "watched-folders.json"
        self.store = store
        self._clock = clock
        self._lock = threading.Lock()
        self._scanned_at = float("-inf")

    def _load(self) -> list[WatchedFolder]:
        try:
            raw = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            return []
        folders: list[WatchedFolder] = []
        for item in raw.get("folders", []) if isinstance(raw, dict) else []:
            try:
                folders.append(WatchedFolder(**item))
            except TypeError:
                continue
        return folders

    def _save(self, folders: list[WatchedFolder]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".watch-", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump({"folders": [asdict(folder) for folder in folders]}, stream)
            os.replace(temporary, self.path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def folders(self) -> list[WatchedFolder]:
        with self._lock:
            return self._load()

    def add(self, path: object, collection_id: object = None) -> WatchedFolder:
        if not isinstance(path, str) or not path.strip():
            raise KnowledgeError("choose a folder to watch")
        folder = Path(path).expanduser()
        if not folder.is_dir():
            raise KnowledgeError("the folder does not exist")
        target = str(collection_id or "default")
        if target not in {item["id"] for item in self.store.collections()}:
            raise KnowledgeError("there is no such knowledge base")
        store_root = _key(str(self.path.parent))
        if _key(str(folder)).startswith(store_root) or store_root.startswith(_key(str(folder))):
            raise KnowledgeError("the knowledge base's own folder cannot be watched")
        with self._lock:
            folders = self._load()
            if any(_key(item.path) == _key(str(folder)) for item in folders):
                raise KnowledgeError("this folder is already watched")
            if len(folders) >= MAX_FOLDERS:
                raise KnowledgeError(f"at most {MAX_FOLDERS} folders can be watched")
            watched = WatchedFolder(str(folder.resolve()), target, _now())
            folders.append(watched)
            self._save(folders)
            return watched

    def remove(self, path: object) -> bool:
        if not isinstance(path, str):
            return False
        with self._lock:
            folders = self._load()
            kept = [item for item in folders if _key(item.path) != _key(path)]
            if len(kept) == len(folders):
                return False
            self._save(kept)
            return True

    def due(self) -> bool:
        return self._clock() - self._scanned_at >= SCAN_INTERVAL_SECONDS

    def scan(self) -> ScanReport:
        """Add what is new in every watched folder."""
        with self._lock:
            self._scanned_at = self._clock()
            folders = self._load()
            added = waiting = failed = 0
            budget = MAX_ADDED_PER_SCAN
            for folder in folders:
                report = self._scan_folder(folder, budget)
                added += report.added
                waiting += report.waiting
                failed += report.failed
                budget -= report.added
            self._save(folders)
            return ScanReport(added, waiting, failed)

    def _files(self, root: Path) -> list[tuple[Path, os.stat_result]]:
        found: list[tuple[Path, os.stat_result]] = []
        pending = [(root, 0)]
        visited = 0
        while pending:
            current, depth = pending.pop()
            try:
                entries = list(os.scandir(current))
            except OSError:
                continue
            for entry in entries:
                visited += 1
                if visited > _MAX_ENTRIES:
                    return found
                if entry.name.startswith((".", "~$")):
                    continue
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir():
                        if depth < _MAX_DEPTH:
                            pending.append((Path(entry.path), depth + 1))
                        continue
                    if Path(entry.name).suffix.casefold() not in SUPPORTED_SUFFIXES:
                        continue
                    found.append((Path(entry.path), entry.stat()))
                except OSError:
                    continue
        return found

    def _scan_folder(self, folder: WatchedFolder, budget: int) -> ScanReport:
        root = Path(folder.path)
        if not root.is_dir():
            folder.error = "missing"
            return ScanReport(0, 0, 0)
        folder.error = None
        added = waiting = failed = 0
        settled_before = self._clock() - SETTLE_SECONDS
        present: set[str] = set()
        for path, metadata in sorted(self._files(root), key=lambda item: item[1].st_mtime):
            name = str(path)
            present.add(name)
            identity = [metadata.st_size, metadata.st_mtime_ns]
            if folder.seen.get(name) == identity:
                continue
            if metadata.st_size == 0 or metadata.st_size > MAX_FILE_BYTES:
                folder.seen[name] = identity  # never addable; don't look again until it changes
                continue
            if metadata.st_mtime > settled_before or added >= budget:
                waiting += 1
                continue
            try:
                result = self.store.add_file(
                    path,
                    path.name,
                    origin="watch",
                    origin_path=name,
                    collection_id=folder.collection_id,
                )
            except KnowledgeError as error:
                if "full" in str(error):
                    folder.error = "full"
                    waiting += 1
                    break
                failed += 1
                folder.seen[name] = identity
                continue
            except OSError:
                failed += 1  # locked or vanished; try again next scan
                continue
            folder.seen[name] = identity
            if not result.get("duplicate"):
                added += 1
        folder.seen = {name: value for name, value in folder.seen.items() if name in present}
        folder.added += added
        folder.last_scan = _now()
        return ScanReport(added, waiting, failed)


__all__ = [
    "FolderWatch",
    "ScanReport",
    "WatchedFolder",
    "suggested_folders",
]
