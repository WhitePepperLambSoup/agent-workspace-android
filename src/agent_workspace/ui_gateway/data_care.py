"""The app's data on this computer: how much there is, its backups, and putting one back.

A restore cannot replace the database while the app has it open, and on Windows an open file
cannot even be moved. So a restore is checked now and carried out at the next start, before the
database is opened; the database it replaces is kept beside it until the next restore.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from agent_workspace.storage.recovery import (
    BackupValidationError,
    create_verified_backup,
    restore_verified_backup,
    verify_backup,
)
from agent_workspace.ui_gateway.backups import KEEP_BACKUPS, backup_directory

_LOGGER = logging.getLogger(__name__)

_PENDING = "restore-pending.json"
_RESULT = "restore-result.json"
_ASIDE_PREFIX = ".before-restore-"
_SIDECARS = ("-wal", "-shm")
# Listing a data folder should not take long whatever is in it.
_MAX_WALKED_FILES = 200_000


class DataCareError(RuntimeError):
    """Something a person can act on; the message is the gateway's error code."""


def database_health(database: Path) -> str:
    """'missing' before the first conversation, 'damaged' when SQLite cannot read it, else 'ok'."""
    if not database.exists():
        return "missing"
    try:
        connection = sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True, timeout=2)
    except (sqlite3.Error, ValueError, OSError):
        return "damaged"
    try:
        row = connection.execute("PRAGMA quick_check(1)").fetchone()
        return "ok" if row and row[0] == "ok" else "damaged"
    except sqlite3.OperationalError as error:
        # Another connection holding the file is not damage.
        return "ok" if "locked" in str(error).lower() or "busy" in str(error).lower() else "damaged"
    except sqlite3.Error:
        return "damaged"
    finally:
        connection.close()


def list_backups(database: Path) -> list[dict[str, object]]:
    """This data folder's backups, newest first, from their manifests (nothing is verified here)."""
    backups: list[dict[str, object]] = []
    for manifest in backup_directory(database).glob("agent-*.db.manifest.json"):
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
            created = datetime.fromisoformat(document["created_at"])
            name = document["database_file"]
            size = document["size"]
        except (OSError, UnicodeError, ValueError, KeyError, TypeError):
            continue
        if (
            not isinstance(name, str)
            or not isinstance(size, int)
            or created.tzinfo is None
            or not manifest.with_name(name).is_file()
        ):
            continue
        backups.append({"name": name, "createdAt": created.isoformat(), "bytes": size})
    backups.sort(key=lambda item: str(item["createdAt"]), reverse=True)
    return backups


def storage_usage(database: Path) -> dict[str, int]:
    """Bytes in the data folder by what they are for."""
    root = database.parent
    backups = backup_directory(database)
    usage = {"conversations": 0, "backups": 0, "other": 0}
    walked = 0
    for folder, _subfolders, names in os.walk(root):
        path = Path(folder)
        in_backups = path == backups or backups in path.parents
        for name in names:
            walked += 1
            if walked > _MAX_WALKED_FILES:
                return usage
            try:
                size = (path / name).stat().st_size
            except OSError:
                continue
            if in_backups:
                usage["backups"] += size
            elif path == root and name.startswith(database.name):
                usage["conversations"] += size
            else:
                usage["other"] += size
    return usage


def create_backup_now(database: Path) -> dict[str, object]:
    """A backup asked for by hand, kept under the daily backup's retention."""
    if not database.is_file():
        raise DataCareError("database_missing")
    try:
        path = create_verified_backup(
            database, backup_directory(database), keep=KEEP_BACKUPS, quick_prune=True
        )
    except (OSError, sqlite3.Error, BackupValidationError, RuntimeError, ValueError) as error:
        _LOGGER.warning("backup failed: %s", error)
        raise DataCareError("backup_failed") from None
    for item in list_backups(database):
        if item["name"] == path.name:
            return item
    raise DataCareError("backup_failed")


def _backup_named(database: Path, name: object) -> Path:
    if not isinstance(name, str) or Path(name).name != name or not name.endswith(".db"):
        raise DataCareError("invalid_backup")
    path = backup_directory(database) / name
    if not path.is_file():
        raise DataCareError("invalid_backup")
    return path


def request_restore(database: Path, name: object) -> None:
    """Check a backup now and leave a note for the next start to put it back."""
    path = _backup_named(database, name)
    try:
        verify_backup(path)
    except (BackupValidationError, OSError, sqlite3.Error, ValueError) as error:
        _LOGGER.warning("backup does not verify: %s", error)
        raise DataCareError("backup_damaged") from None
    _write_note(database.with_name(_PENDING), {"backup": path.name})


def request_fresh_start(database: Path) -> None:
    """A damaged database with no backup: the next start moves it aside and begins an empty one."""
    _write_note(database.with_name(_PENDING), {"backup": None})


def _write_note(path: Path, document: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(document), encoding="utf-8")
        temporary.replace(path)
    except OSError as error:
        _LOGGER.warning("note could not be written: %s", error)
        raise DataCareError("data_folder_unavailable") from None


def _move_database(source: Path, destination: Path) -> None:
    for suffix in ("", *_SIDECARS):
        origin = source.with_name(source.name + suffix)
        if origin.exists():
            origin.replace(destination.with_name(destination.name + suffix))


def apply_pending_restore(
    database: Path, *, now: datetime | None = None
) -> dict[str, object] | None:
    """At start, before the database is opened: carry out a restore that was asked for."""
    pending = database.with_name(_PENDING)
    try:
        document = json.loads(pending.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, ValueError):
        pending.unlink(missing_ok=True)
        return None
    name = document.get("backup") if isinstance(document, dict) else None
    moment = now or datetime.now(UTC)
    aside = database.with_name(f"{database.name}{_ASIDE_PREFIX}{moment:%Y%m%d-%H%M%S}")
    result: dict[str, object] = {"ok": False, "backup": name, "at": moment.isoformat()}
    try:
        backup = None if name is None else _backup_named(database, name)
        if database.exists():
            _move_database(database, aside)
        if backup is not None:
            restore_verified_backup(backup, database)
        database.with_name(f"{database.name}.validated").unlink(missing_ok=True)
        result["ok"] = True
        _forget_older_asides(database, keep=aside.name)
    except (OSError, sqlite3.Error, DataCareError, BackupValidationError, RuntimeError) as error:
        _LOGGER.error("restore failed: %s", error)
        # The database that was there goes back: nothing is lost by a restore that failed.
        if aside.exists():
            database.unlink(missing_ok=True)
            _move_database(aside, database)
    finally:
        pending.unlink(missing_ok=True)
    _write_note(database.with_name(_RESULT), result)
    return result


def _forget_older_asides(database: Path, *, keep: str) -> None:
    for path in database.parent.glob(f"{database.name}{_ASIDE_PREFIX}*"):
        if not path.name.startswith(keep):
            path.unlink(missing_ok=True)


def last_restore(database: Path) -> dict[str, object] | None:
    """How the last restore went, once: the window says it, and it is not said again."""
    path = database.with_name(_RESULT)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    path.unlink(missing_ok=True)
    return document if isinstance(document, dict) else None
