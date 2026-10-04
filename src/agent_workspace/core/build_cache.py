"""Content-addressed cache for build artifacts.

Artifacts are stored under ``<cache_root>/<sha256>`` and can be pruned by a
byte budget. The cache is intentionally boring and dependency-free so build
scripts can use it before any Python packages are installed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_READ_CHUNK = 1024 * 1024


@dataclass(frozen=True, slots=True)
class ArtifactCacheEntry:
    digest: str
    path: Path
    size: int
    modified: float
    metadata: dict[str, Any]

    def to_document(self) -> dict[str, Any]:
        return {
            "digest": self.digest,
            "path": str(self.path),
            "size": self.size,
            "modified": self.modified,
            "metadata": self.metadata,
        }


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(_READ_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_path(cache_root: Path, digest: str) -> Path:
    if not _DIGEST_PATTERN.fullmatch(digest):
        raise ValueError("artifact digest must be a 64-character sha256 hex digest")
    return cache_root / digest


def build_artifact_put(
    cache_root: str | Path,
    source: str | Path,
    *,
    metadata: dict[str, Any] | None = None,
) -> ArtifactCacheEntry:
    root = Path(cache_root).expanduser().resolve()
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file():
        raise ValueError("source artifact is not a file")
    digest = sha256_file(source_path)
    root.mkdir(parents=True, exist_ok=True)
    destination = _artifact_path(root, digest)
    if not destination.exists():
        temporary = destination.with_suffix(".tmp")
        temporary.unlink(missing_ok=True)
        shutil.copyfile(source_path, temporary)
        os.replace(temporary, destination)
    meta = dict(metadata or {})
    sidecar = destination.with_suffix(".json")
    sidecar.write_text(
        json.dumps(meta, sort_keys=True),
        encoding="utf-8",
    )
    stat = destination.stat()
    return ArtifactCacheEntry(
        digest=digest,
        path=destination,
        size=stat.st_size,
        modified=stat.st_mtime,
        metadata=meta,
    )


def build_artifact_get(
    cache_root: str | Path,
    digest: str,
    *,
    verify: bool = False,
) -> ArtifactCacheEntry | None:
    root = Path(cache_root).expanduser().resolve()
    destination = _artifact_path(root, digest)
    if not destination.is_file():
        return None
    if verify and sha256_file(destination) != digest:
        return None
    sidecar = destination.with_suffix(".json")
    metadata: dict[str, Any] = {}
    if sidecar.is_file():
        try:
            loaded = json.loads(sidecar.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                metadata = loaded
        except (json.JSONDecodeError, OSError):
            metadata = {}
    stat = destination.stat()
    return ArtifactCacheEntry(
        digest=digest,
        path=destination,
        size=stat.st_size,
        modified=stat.st_mtime,
        metadata=metadata,
    )


def build_artifact_stats(cache_root: str | Path) -> dict[str, Any]:
    root = Path(cache_root).expanduser().resolve()
    if not root.is_dir():
        return {"cache_root": str(root), "files": 0, "bytes": 0, "artifacts": []}
    artifacts: list[dict[str, Any]] = []
    total = 0
    for path in root.iterdir():
        if not path.is_file() or not _DIGEST_PATTERN.fullmatch(path.name):
            continue
        stat = path.stat()
        total += stat.st_size
        artifacts.append(
            {
                "digest": path.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            }
        )
    artifacts.sort(key=lambda item: item["modified"], reverse=True)
    return {
        "cache_root": str(root),
        "files": len(artifacts),
        "bytes": total,
        "artifacts": artifacts,
    }


def build_artifact_prune(
    cache_root: str | Path,
    *,
    max_bytes: int,
    dry_run: bool = False,
) -> list[str]:
    if max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")
    root = Path(cache_root).expanduser().resolve()
    if not root.is_dir():
        return []
    entries: list[tuple[float, int, str, Path]] = []
    total = 0
    for path in root.iterdir():
        if not path.is_file() or not _DIGEST_PATTERN.fullmatch(path.name):
            continue
        stat = path.stat()
        total += stat.st_size
        entries.append((stat.st_mtime, stat.st_size, path.name, path))
    if total <= max_bytes:
        return []
    entries.sort(key=lambda item: (item[0], item[2]))
    pruned: list[str] = []
    for _, size, digest, path in entries:
        if total <= max_bytes:
            break
        pruned.append(digest)
        total -= size
        if not dry_run:
            path.unlink(missing_ok=True)
            path.with_suffix(".json").unlink(missing_ok=True)
    return pruned


def build_artifact_touch(
    cache_root: str | Path,
    digest: str,
) -> bool:
    """Refresh an artifact's mtime so LRU pruning keeps recently used entries."""
    root = Path(cache_root).expanduser().resolve()
    destination = _artifact_path(root, digest)
    if not destination.is_file():
        return False
    now = time.time()
    os.utime(destination, (now, now))
    return True


__all__ = [
    "ArtifactCacheEntry",
    "build_artifact_get",
    "build_artifact_prune",
    "build_artifact_put",
    "build_artifact_stats",
    "build_artifact_touch",
    "sha256_file",
]
