"""Bounded workspace tree snapshots for session forks.

The copy is deliberately conservative: symlinks/reparse points are rejected,
``.git`` is skipped, total size is bounded, and the destination is created
atomically where possible.
"""

from __future__ import annotations

import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_MAX_ENTRIES = 200_000
_DEFAULT_MAX_BYTES = 2 * 1024 * 1024 * 1024
_SKIPPED_DIRECTORIES = frozenset({".git"})


class WorkspaceSnapshotError(OSError):
    pass


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshotReport:
    files: int
    directories: int
    bytes_copied: int


def snapshot_workspace_tree(
    source: str | Path,
    destination: str | Path,
    *,
    max_entries: int = _DEFAULT_MAX_ENTRIES,
    max_bytes: int = _DEFAULT_MAX_BYTES,
) -> WorkspaceSnapshotReport:
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    if not source_path.is_dir():
        raise WorkspaceSnapshotError(f"snapshot source is not a directory: {source_path}")
    if destination_path == source_path or source_path in destination_path.parents:
        raise WorkspaceSnapshotError("snapshot destination may not overlap the source")
    if max_entries < 1 or max_bytes < 1:
        raise ValueError("snapshot limits must be positive")

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.mkdir(exist_ok=True)
    files = 0
    directories = 0
    bytes_copied = 0
    entries = 0
    for root, directory_names, file_names in os.walk(source_path, topdown=True):
        directory_names[:] = sorted(
            name for name in directory_names if name not in _SKIPPED_DIRECTORIES
        )
        for name in sorted(file_names):
            entries += 1
            if entries > max_entries:
                raise WorkspaceSnapshotError("workspace snapshot entry limit exceeded")
            source_file = Path(root) / name
            metadata = source_file.lstat()
            if stat.S_ISLNK(metadata.st_mode) or (
                hasattr(metadata, "st_file_attributes") and metadata.st_file_attributes & 0x400
            ):
                raise WorkspaceSnapshotError(f"workspace snapshot rejected a link: {source_file}")
            if metadata.st_size > max_bytes - bytes_copied:
                raise WorkspaceSnapshotError("workspace snapshot byte limit exceeded")
            relative = source_file.relative_to(source_path)
            target = destination_path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target)
            files += 1
            bytes_copied += metadata.st_size
        directories += len(directory_names)
    return WorkspaceSnapshotReport(files, directories, bytes_copied)


__all__ = [
    "WorkspaceSnapshotError",
    "WorkspaceSnapshotReport",
    "snapshot_workspace_tree",
]
