"""Backup and restore of the phone's conversations, workspace and settings.

A backup is one zip: the engine's data folder (SQLite databases copied with SQLite's backup API, so
an open database is captured consistently), the app-private default workspace, and the app and
interface settings the clients hand over. API keys are never included. Bulky or rebuildable data
(on-device models, the developer toolchain, logs) stays out.

Restoring cannot replace databases the engine has open, so it is staged: the archive is checked
and unpacked next to the live data, and the next engine start swaps it in before opening anything.
The data it replaces is kept once as *.before-restore.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import threading
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

FORMAT = "agent-workspace-backup"
VERSION = 1
MANIFEST = "manifest.json"
EXCLUDED_DATA_DIRS = {"logs", "local-models", "toolchain", "backups", "cache", "tmp"}
EXCLUDED_SUFFIXES = (".tmp", ".part", "-wal", "-shm", "-journal", ".lock")
STAGING = "restore-staging"
READY_MARKER = "READY"
MAX_ARCHIVE_ENTRIES = 200_000
MAX_SETTINGS_BYTES = 4 * 1024 * 1024
FREE_SPACE_MARGIN = 64 * 1024 * 1024


class BackupError(ValueError):
    """A backup or restore the user has to fix (shown as a 400)."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _is_sqlite(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def _data_files(data: Path):
    for path in sorted(data.rglob("*")):
        relative = path.relative_to(data)
        if relative.parts and relative.parts[0] in EXCLUDED_DATA_DIRS:
            continue
        if path.is_symlink() or not path.is_file() or path.name.endswith(EXCLUDED_SUFFIXES):
            continue
        yield path, relative


def _workspace_files(workspace: Path):
    if not workspace.is_dir():
        return
    for path in sorted(workspace.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        yield path, path.relative_to(workspace)


def create_backup(
    files_dir: Path,
    output: Path,
    *,
    app_settings: dict[str, Any] | None = None,
    web_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write a backup zip to ``output``; returns what it contains."""
    files_dir = Path(files_dir)
    data = files_dir / "agent-data"
    workspace = files_dir / "workspace"
    counts = {"data_files": 0, "workspace_files": 0, "bytes": 0}
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    with (
        tempfile.TemporaryDirectory(dir=output.parent) as scratch,
        zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive,
    ):
        for path, relative in _data_files(data):
            name = PurePosixPath("agent-data", *relative.parts).as_posix()
            if _is_sqlite(path):
                # A live database is copied through SQLite itself, never as raw bytes.
                copy = Path(scratch) / f"{uuid.uuid4().hex}.db"
                source = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
                target = sqlite3.connect(copy)
                try:
                    source.backup(target)
                finally:
                    target.close()
                    source.close()
                archive.write(copy, name)
                counts["bytes"] += copy.stat().st_size
                copy.unlink()
            else:
                archive.write(path, name)
                counts["bytes"] += path.stat().st_size
            counts["data_files"] += 1
        for path, relative in _workspace_files(workspace):
            archive.write(path, PurePosixPath("workspace", *relative.parts).as_posix())
            counts["workspace_files"] += 1
            counts["bytes"] += path.stat().st_size
        for name, value in (
            ("settings/app.json", app_settings),
            ("settings/web.json", web_settings),
        ):
            if value:
                archive.writestr(name, json.dumps(value, ensure_ascii=False))
        manifest = {
            "format": FORMAT,
            "version": VERSION,
            "created_at": _now(),
            "app_version": (app_settings or {}).get("app_version"),
            **counts,
            "excluded": [*sorted(EXCLUDED_DATA_DIRS), "api keys"],
        }
        archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=1))
    os.replace(partial, output)
    return {**manifest, "path": str(output), "size": output.stat().st_size}


def _safe_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        name.startswith(("/", "\\"))
        or "\\" in name
        or ":" in name
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.parts[0] not in {"agent-data", "workspace", "settings", MANIFEST}
    ):
        raise BackupError(f"the backup contains an unexpected entry: {name[:120]}")
    return path


def stage_restore(files_dir: Path, archive_path: Path) -> dict[str, Any]:
    """Check a backup and unpack it next to the live data; the next engine start swaps it in."""
    files_dir = Path(files_dir)
    staging = files_dir / STAGING
    try:
        archive = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile):
        raise BackupError("this file is not an Agent Workspace backup") from None
    with archive:
        try:
            manifest = json.loads(archive.read(MANIFEST))
        except (KeyError, ValueError):
            raise BackupError("this file is not an Agent Workspace backup") from None
        if manifest.get("format") != FORMAT:
            raise BackupError("this file is not an Agent Workspace backup")
        if not isinstance(manifest.get("version"), int) or manifest["version"] > VERSION:
            raise BackupError("this backup was made by a newer version of the app; update first")
        members = archive.infolist()
        if len(members) > MAX_ARCHIVE_ENTRIES:
            raise BackupError("the backup has too many files")
        total = 0
        for member in members:
            _safe_member(member.filename)
            total += member.file_size
        free = shutil.disk_usage(files_dir).free
        if total + FREE_SPACE_MARGIN > free:
            raise BackupError("not enough free space on the phone to restore this backup")
        settings: dict[str, Any] = {}
        for key, name in (("app", "settings/app.json"), ("web", "settings/web.json")):
            try:
                info = archive.getinfo(name)
            except KeyError:
                continue
            if info.file_size > MAX_SETTINGS_BYTES:
                raise BackupError("the backup settings are too large")
            value = json.loads(archive.read(name))
            if isinstance(value, dict):
                settings[key] = value
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        for member in members:
            target = staging.joinpath(*_safe_member(member.filename).parts)
            if not target.resolve().is_relative_to(staging.resolve()):
                raise BackupError("the backup contains an unexpected entry")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink, 1024 * 1024)
        (staging / READY_MARKER).write_text(_now(), encoding="utf-8")
    return {"manifest": manifest, "settings": settings}


def apply_staged_restore(files_dir: Path) -> bool:
    """Run at engine start, before any database opens: swap a staged restore into place."""
    files_dir = Path(files_dir)
    staging = files_dir / STAGING
    if not (staging / READY_MARKER).is_file():
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)  # an interrupted restore never started
        return False
    for name in ("agent-data", "workspace"):
        live = files_dir / name
        restored = staging / name
        if not restored.exists():
            continue
        if live.exists():
            kept = files_dir / f"{name}.before-restore"
            if kept.exists():
                shutil.rmtree(kept)
            live.rename(kept)
            if name == "agent-data":
                # Models, the toolchain and logs are not in backups; keep the phone's copies.
                for directory in EXCLUDED_DATA_DIRS:
                    if (kept / directory).exists() and not (restored / directory).exists():
                        (kept / directory).rename(restored / directory)
        restored.rename(live)
    shutil.rmtree(staging, ignore_errors=True)
    return True


class BackupJobs:
    """One backup at a time, in a thread, so a large workspace never blocks a request."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def start(self, files_dir: Path, output: Path, **settings: Any) -> dict[str, Any]:
        with self._lock:
            if any(job["state"] == "running" for job in self._jobs.values()):
                raise BackupError("a backup is already being created")
            job_id = uuid.uuid4().hex
            self._jobs = {job_id: {"job_id": job_id, "state": "running", "started_at": _now()}}

        def run() -> None:
            try:
                result = create_backup(files_dir, output, **settings)
                update = {"state": "done", **result}
            except Exception as exc:
                output.with_suffix(output.suffix + ".partial").unlink(missing_ok=True)
                update = {"state": "failed", "error": str(exc)[:500]}
            with self._lock:
                self._jobs[job_id].update(update)

        threading.Thread(target=run, name="agent-backup", daemon=True).start()
        return self.status(job_id)

    def status(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            return dict(job)


backup_jobs = BackupJobs()
