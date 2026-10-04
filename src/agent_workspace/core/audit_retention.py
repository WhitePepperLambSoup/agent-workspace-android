"""Retention policy for exported audit logs.

Audit exports are append-only SIEM files. Retention only removes complete
files matching ``audit-*.jsonl`` so a running exporter can write new files
without a partially written file ever being considered for deletion.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULT_MAX_FILES = 180
_DEFAULT_MAX_TOTAL_BYTES = 10 * 1024 * 1024 * 1024
_DEFAULT_MAX_AGE_DAYS = 365


@dataclass(frozen=True, slots=True)
class AuditRetentionPolicy:
    max_age_days: int | None = _DEFAULT_MAX_AGE_DAYS
    max_files: int = _DEFAULT_MAX_FILES
    max_total_bytes: int = _DEFAULT_MAX_TOTAL_BYTES
    glob: str = "audit-*.jsonl"

    def validate(self) -> None:
        if self.max_age_days is not None and self.max_age_days <= 0:
            raise ValueError("max_age_days must be positive or None")
        if self.max_files <= 0:
            raise ValueError("max_files must be positive")
        if self.max_total_bytes <= 0:
            raise ValueError("max_total_bytes must be positive")
        if not self.glob or ".." in self.glob:
            raise ValueError("glob must be a non-empty single directory pattern")

    def to_document(self) -> dict[str, Any]:
        return {
            "max_age_days": self.max_age_days,
            "max_files": self.max_files,
            "max_total_bytes": self.max_total_bytes,
            "glob": self.glob,
        }


@dataclass(frozen=True, slots=True)
class AuditRetentionReport:
    directory: Path
    policy: AuditRetentionPolicy
    scanned: int
    deleted: tuple[str, ...]
    kept: tuple[str, ...]
    released_bytes: int
    dry_run: bool

    def to_document(self) -> dict[str, Any]:
        return {
            "directory": str(self.directory),
            "policy": self.policy.to_document(),
            "scanned": self.scanned,
            "deleted": list(self.deleted),
            "kept": list(self.kept),
            "released_bytes": self.released_bytes,
            "dry_run": self.dry_run,
        }


@dataclass(slots=True)
class _Candidate:
    name: str
    path: Path
    size: int
    modified: float


def _candidates(root: Path, policy: AuditRetentionPolicy) -> list[_Candidate]:
    found: list[_Candidate] = []
    for path in root.glob(policy.glob):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        found.append(
            _Candidate(
                name=path.name,
                path=path,
                size=stat.st_size,
                modified=stat.st_mtime,
            )
        )
    found.sort(key=lambda item: (item.modified, item.name))
    return found


def apply_audit_retention(
    directory: str | Path,
    policy: AuditRetentionPolicy,
    *,
    now: float | None = None,
    dry_run: bool = False,
) -> AuditRetentionReport:
    policy.validate()
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        return AuditRetentionReport(root, policy, 0, (), (), 0, dry_run)
    reference = time.time() if now is None else now
    candidates = _candidates(root, policy)
    deletion_flags = [False] * len(candidates)

    for index, item in enumerate(candidates):
        if policy.max_age_days is not None and (
            reference - item.modified >= policy.max_age_days * 86_400
        ):
            deletion_flags[index] = True

    kept_count = sum(1 for flagged in deletion_flags if not flagged)
    kept_bytes = sum(
        item.size for item, flagged in zip(candidates, deletion_flags, strict=True) if not flagged
    )
    if kept_count > policy.max_files or kept_bytes > policy.max_total_bytes:
        for index, item in enumerate(candidates):
            if deletion_flags[index]:
                continue
            if kept_count <= policy.max_files and kept_bytes <= policy.max_total_bytes:
                break
            deletion_flags[index] = True
            kept_count -= 1
            kept_bytes -= item.size

    deleted: list[str] = []
    released = 0
    for item, flagged in zip(candidates, deletion_flags, strict=True):
        if not flagged:
            continue
        deleted.append(item.name)
        released += item.size
        if not dry_run:
            try:
                item.path.unlink()
            except OSError:
                released -= item.size
                deleted.pop()
    kept = sorted(set(item.name for item in candidates) - set(deleted))
    return AuditRetentionReport(
        directory=root,
        policy=policy,
        scanned=len(candidates),
        deleted=tuple(deleted),
        kept=tuple(kept),
        released_bytes=released,
        dry_run=dry_run,
    )


def build_audit_retention_policy(**overrides: Any) -> AuditRetentionPolicy:
    values: dict[str, Any] = {
        "max_age_days": _DEFAULT_MAX_AGE_DAYS,
        "max_files": _DEFAULT_MAX_FILES,
        "max_total_bytes": _DEFAULT_MAX_TOTAL_BYTES,
        "glob": "audit-*.jsonl",
    }
    for key, value in overrides.items():
        if key not in values:
            raise TypeError(f"unknown audit retention policy option: {key}")
        values[key] = value
    return AuditRetentionPolicy(**values)


def default_audit_retention_policy() -> AuditRetentionPolicy:
    return AuditRetentionPolicy()


__all__ = [
    "AuditRetentionPolicy",
    "AuditRetentionReport",
    "apply_audit_retention",
    "build_audit_retention_policy",
    "default_audit_retention_policy",
]
