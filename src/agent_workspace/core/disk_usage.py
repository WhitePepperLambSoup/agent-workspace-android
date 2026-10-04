"""Workspace disk usage reporting."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_SKIPPED_DIRECTORIES = frozenset({".git", ".venv", "node_modules", "__pycache__"})


@dataclass(frozen=True, slots=True)
class DiskUsageReport:
    files: int
    directories: int
    bytes: int
    largest_files: tuple[tuple[str, int], ...]

    def to_document(self) -> dict[str, object]:
        return {
            "files": self.files,
            "directories": self.directories,
            "bytes": self.bytes,
            "largest_files": [{"path": path, "bytes": size} for path, size in self.largest_files],
        }


def workspace_disk_usage(
    workspace: str | Path,
    *,
    top_n: int = 10,
) -> DiskUsageReport:
    if top_n < 0:
        raise ValueError("top_n must be non-negative")
    root = Path(workspace).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("workspace is not a directory")
    files = 0
    directories = 0
    total = 0
    sizes: list[tuple[str, int]] = []
    for directory, directory_names, file_names in os.walk(root, topdown=True):
        directory_names[:] = sorted(
            name for name in directory_names if name not in _SKIPPED_DIRECTORIES
        )
        directories += len(directory_names)
        for name in file_names:
            path = Path(directory) / name
            try:
                size = path.stat().st_size
            except OSError:
                continue
            files += 1
            total += size
            sizes.append((path.relative_to(root).as_posix(), size))
    sizes.sort(key=lambda item: (-item[1], item[0]))
    return DiskUsageReport(files, directories, total, tuple(sizes[:top_n]))


__all__ = ["DiskUsageReport", "workspace_disk_usage"]
