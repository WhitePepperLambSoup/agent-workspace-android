from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import zipfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from itertools import zip_longest
from pathlib import Path, PurePosixPath
from typing import Any, cast
from uuid import uuid4

from agent_workspace.core.events import (
    CURRENT_EVENT_SCHEMA_VERSION,
    Event,
    validate_event_payload,
)
from agent_workspace.core.models import Autonomy, BinaryArtifact, Mode
from agent_workspace.core.session import Session
from agent_workspace.storage.durable import durable_publish_new, durable_replace, fsync_directory
from agent_workspace.storage.lock import ProcessWriteLock
from agent_workspace.storage.sqlite import (
    CURRENT_SCHEMA_MIGRATIONS,
    CURRENT_SCHEMA_VERSION,
    SCHEMA_DEFINITIONS_BY_VERSION,
    SQLiteEventStore,
    normalize_schema_definition,
)

_BACKUP_FORMAT_VERSION = 1
_DEFAULT_BACKUP_MAX_AGE_DAYS = 30
_DEFAULT_BACKUP_MAX_TOTAL_BYTES = 10 * 1024 * 1024 * 1024
_EXPORT_FORMAT_VERSION = 3
_MAX_SESSION_ARCHIVE_BYTES = 128 * 1024 * 1024
_MAX_SESSION_ARCHIVE_ENTRIES = 2005
_MAX_SESSION_ARCHIVE_MANIFEST_BYTES = 1024 * 1024
_MAX_SESSION_ARCHIVE_EVENT_BYTES = 2 * 1024 * 1024
_MAX_SESSION_ARCHIVE_EVENTS = 100_000
_MAX_SESSION_ARCHIVE_JSON_BYTES = 16 * 1024 * 1024
_MAX_SESSION_ARTIFACT_BYTES = 128 * 1024
_MAX_SANDBOX_ARTIFACT_BYTES = 16 * 1024 * 1024
_MAX_IMPORTED_ACTIVE_BACKGROUND_JOBS = 4
_REDACTED = "<redacted>"
_SQLITE_SIDECAR_SUFFIXES = ("-journal", "-shm", "-wal")
_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "api_secret",
    "authorization",
    "aws_secret_access_key",
    "client_secret",
    "cookie",
    "credential",
    "credentials",
    "passphrase",
    "pass_phrase",
    "password",
    "passwd",
    "private_key",
    "secret",
    "secret_key",
    "set_cookie",
    "token",
}
_SENSITIVE_SUFFIXES = (
    "_api_key",
    "_api_secret",
    "_authorization",
    "_cookie",
    "_credential",
    "_credentials",
    "_passphrase",
    "_pass_phrase",
    "_password",
    "_private_key",
    "_secret",
    "_secret_access_key",
    "_secret_key",
    "_token",
)


class BackupValidationError(RuntimeError):
    pass


class SessionExportError(RuntimeError):
    """Raised when a session cannot be safely exported as a versioned archive."""


@dataclass(frozen=True, slots=True)
class DatabaseValidation:
    schema_version: int
    sessions: int
    events: int


@dataclass(frozen=True, slots=True)
class SessionArchiveValidation:
    format_version: int
    schema_version: int
    session_id: str
    event_count: int
    todo_count: int
    source_count: int
    citation_count: int
    artifact_count: int


@dataclass(frozen=True, slots=True)
class _VerifiedSessionArchive:
    validation: SessionArchiveValidation
    session: Session
    events: tuple[Event, ...]
    todos: tuple[dict[str, Any], ...]
    sources: tuple[dict[str, Any], ...]
    citations: tuple[dict[str, Any], ...]
    artifacts: dict[str, bytes]
    sandbox_artifacts: dict[str, bytes]


def session_checkpoint_report(database: str | Path, session_id: str) -> list[dict[str, str]]:
    """List active file-write checkpoints that block safe session export."""
    rows = SQLiteEventStore.list_file_checkpoints_read_only(database, session_id)
    return [{"attempt_id": attempt_id, "path": relative_path} for attempt_id, relative_path in rows]


def create_verified_backup(
    database: str | Path,
    backup_directory: str | Path,
    *,
    keep: int = 10,
    max_age_days: int = _DEFAULT_BACKUP_MAX_AGE_DAYS,
    max_total_bytes: int = _DEFAULT_BACKUP_MAX_TOTAL_BYTES,
    incremental: bool = False,
) -> Path:
    source_path = Path(database).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"database does not exist: {source_path}")
    if keep < 1:
        raise ValueError("backup retention count must be positive")
    if max_age_days < 1:
        raise ValueError("backup retention age must be positive")
    if max_total_bytes < 1:
        raise ValueError("backup retention size must be positive")
    directory = Path(backup_directory).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    source_identity = _file_identity(source_path)
    lineage = hashlib.sha256(os.path.normcase(str(source_path)).encode("utf-8")).hexdigest()[:16]
    lock = ProcessWriteLock(
        directory / ".backup.lock",
        busy_message="another backup operation is running",
    )
    with lock:
        return _create_verified_backup_locked(
            source_path,
            directory,
            source_identity=source_identity,
            lineage=lineage,
            keep=keep,
            max_age_days=max_age_days,
            max_total_bytes=max_total_bytes,
            incremental=incremental,
        )


def _create_verified_backup_locked(
    source_path: Path,
    directory: Path,
    *,
    source_identity: tuple[int, int],
    lineage: str,
    keep: int,
    max_age_days: int,
    max_total_bytes: int,
    incremental: bool,
) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".agent-backup-",
        suffix=".db.tmp",
        dir=directory,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = directory / f"agent-{lineage}-{timestamp}-{uuid4().hex[:8]}.db"
    manifest_path = _manifest_path(backup_path)
    try:
        _online_backup(source_path, temporary_path, source_identity=source_identity)
        validation = validate_database(temporary_path)
        digest = _sha256_file(temporary_path)
        parent_sha256 = _latest_backup_digest(directory, lineage) if incremental else None
        manifest = {
            "format_version": _BACKUP_FORMAT_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "database_file": backup_path.name,
            "lineage": lineage,
            "sha256": digest,
            "size": temporary_path.stat().st_size,
            "validation": asdict(validation),
            "backup_kind": "incremental" if incremental else "full",
            "parent_sha256": parent_sha256,
        }
        manifest_payload = _json_bytes(manifest)
        _publish_new_file(temporary_path, backup_path)
        _atomic_write(manifest_path, manifest_payload)
        _prune_backups(
            directory,
            lineage=lineage,
            keep=keep,
            max_age_days=max_age_days,
            max_total_bytes=max_total_bytes,
            protected=backup_path,
        )
        return backup_path
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        if backup_path.exists() and not manifest_path.exists():
            backup_path.unlink(missing_ok=True)
        raise


def verify_backup(backup: str | Path) -> DatabaseValidation:
    validation, _ = _verify_backup(backup)
    return validation


def read_backup_manifest(backup: str | Path) -> dict[str, object]:
    """Return a verified backup manifest without exposing database contents."""
    backup_path = Path(backup).expanduser().resolve()
    _verify_backup(backup_path)
    try:
        raw = json.loads(_manifest_path(backup_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise BackupValidationError("backup manifest is missing or invalid") from None
    if not isinstance(raw, dict):
        raise BackupValidationError("backup manifest is invalid")
    return cast(dict[str, object], raw)


def _verify_backup(backup: str | Path) -> tuple[DatabaseValidation, str]:
    backup_path = Path(backup).expanduser().resolve()
    _reject_sqlite_sidecars(backup_path, label="backup")
    manifest_path = _manifest_path(backup_path)
    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise BackupValidationError("backup manifest is missing or invalid") from None
    if not isinstance(raw_manifest, dict):
        raise BackupValidationError("backup manifest is invalid")
    manifest = cast(dict[str, object], raw_manifest)
    format_version = manifest.get("format_version")
    if type(format_version) is not int or format_version != _BACKUP_FORMAT_VERSION:
        raise BackupValidationError("backup format version is unsupported")
    if not _is_timezone_aware_timestamp(manifest.get("created_at")):
        raise BackupValidationError("backup creation timestamp is invalid")
    if manifest.get("database_file") != backup_path.name:
        raise BackupValidationError("backup manifest does not match the database file")
    lineage = manifest.get("lineage")
    if (
        not isinstance(lineage, str)
        or len(lineage) != 16
        or any(character not in "0123456789abcdef" for character in lineage)
        or not backup_path.name.startswith(f"agent-{lineage}-")
    ):
        raise BackupValidationError("backup lineage metadata is invalid")
    expected_size = manifest.get("size")
    expected_digest = manifest.get("sha256")
    if (
        not isinstance(expected_size, int)
        or isinstance(expected_size, bool)
        or expected_size < 0
        or not isinstance(expected_digest, str)
        or len(expected_digest) != 64
        or any(character not in "0123456789abcdef" for character in expected_digest)
    ):
        raise BackupValidationError("backup manifest metadata is invalid")
    backup_kind = manifest.get("backup_kind")
    parent_sha256 = manifest.get("parent_sha256")
    if backup_kind not in {"full", "incremental"}:
        raise BackupValidationError("backup kind metadata is invalid")
    if parent_sha256 is not None and not _is_sha256(parent_sha256):
        raise BackupValidationError("backup parent digest metadata is invalid")
    if backup_kind == "full" and parent_sha256 is not None:
        raise BackupValidationError("full backup cannot reference a parent")
    try:
        actual_size = backup_path.stat().st_size
        actual_digest = _sha256_file(backup_path)
    except OSError:
        raise BackupValidationError("backup database is missing or unreadable") from None
    if actual_size != expected_size or actual_digest != expected_digest:
        raise BackupValidationError("backup hash or size does not match its manifest")
    validation = validate_database(backup_path)
    raw_validation = manifest.get("validation")
    if not _validation_matches(raw_validation, validation):
        raise BackupValidationError("backup validation summary does not match its manifest")
    _reject_sqlite_sidecars(backup_path, label="backup")
    return validation, expected_digest


def restore_dry_run(backup: str | Path, destination: str | Path) -> dict[str, object]:
    """Verify a backup and report whether restoring it would be safe."""
    backup_path = Path(backup).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    validation, _digest = _verify_backup(backup_path)
    destination_exists = destination_path.exists()
    if not destination_exists:
        destination_kind = "missing"
    elif destination_path.is_dir():
        destination_kind = "directory"
    elif destination_path.is_file():
        destination_kind = "file"
    else:
        destination_kind = "other"
    destination_empty = (
        destination_exists and destination_path.is_dir() and not any(destination_path.iterdir())
    )
    manifest = read_backup_manifest(backup_path)
    return {
        "backup": str(backup_path),
        "destination": str(destination_path),
        "destination_exists": destination_exists,
        "destination_empty": destination_empty,
        "destination_kind": destination_kind,
        "safe_to_restore": not destination_exists,
        "reason": "destination_missing"
        if not destination_exists
        else "destination_namespace_exists",
        "manifest": manifest,
        "validation": asdict(validation),
    }


def restore_verified_backup(backup: str | Path, destination: str | Path) -> Path:
    backup_path = Path(backup).expanduser().resolve()
    _, expected_digest = _verify_backup(backup_path)
    destination_path = Path(destination).expanduser().resolve()
    _ensure_destination_namespace_available(destination_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination_path.name}.",
        suffix=".restore.tmp",
        dir=destination_path.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        with backup_path.open("rb") as source, temporary_path.open("wb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)
            target.flush()
            os.fsync(target.fileno())
        if _sha256_file(temporary_path) != expected_digest:
            raise BackupValidationError("backup changed while it was being restored")
        _reject_sqlite_sidecars(temporary_path, label="restore snapshot")
        validation = validate_database(temporary_path)
        if validation.schema_version < CURRENT_SCHEMA_VERSION:
            with SQLiteEventStore(temporary_path, create_migration_backup=False):
                pass
            _normalize_database(temporary_path)
            validation = validate_database(temporary_path)
            if validation.schema_version != CURRENT_SCHEMA_VERSION:
                raise BackupValidationError("restored database migration failed")
        _ensure_destination_namespace_available(destination_path)
        _publish_new_file(temporary_path, destination_path)
        return destination_path
    finally:
        temporary_path.unlink(missing_ok=True)


def _normalize_legacy_event_payload(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Fill optional fields that older builds did not record.

    The store is append-only, so historical rows keep their original JSON;
    read-side validation only tolerates the missing fields instead of
    rewriting events.
    """
    if event_type == "turn.started":
        if "model" in data or "mode" in data:
            data.setdefault("provider", "legacy")
            data.setdefault("continuation", False)
    elif event_type == "turn.completed":
        data.setdefault("provider_attempts", 0)
    elif event_type == "context.compacted":
        data.setdefault("summarized", False)
    return data


def validate_database(database: str | Path) -> DatabaseValidation:
    database_path = Path(database).expanduser().resolve()
    uri = f"{database_path.as_uri()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, timeout=5, uri=True)
    except sqlite3.Error:
        raise BackupValidationError("database cannot be opened") from None
    connection.row_factory = sqlite3.Row
    try:
        # All integrity and replay queries must observe the same WAL snapshot.
        connection.execute("BEGIN")
        quick_check = connection.execute("PRAGMA quick_check").fetchall()
        if [row[0] for row in quick_check] != ["ok"]:
            raise BackupValidationError("database quick_check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise BackupValidationError("database foreign key check failed")
        raw_schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
        if type(raw_schema_version) is not int:
            raise BackupValidationError("database schema version is invalid")
        schema_version = raw_schema_version
        expected_definitions = SCHEMA_DEFINITIONS_BY_VERSION.get(schema_version)
        if expected_definitions is None:
            raise BackupValidationError("database schema version is unsupported")
        # Validate the migration ledger before comparing object definitions so
        # a forged version/name is reported as provenance damage rather than a
        # less actionable schema mismatch.
        raw_migrations = [
            (row[0], row[1])
            for row in connection.execute(
                "SELECT version, name FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]
        if any(
            type(version) is not int or not isinstance(name, str)
            for version, name in raw_migrations
        ):
            raise BackupValidationError("database migration history is invalid")
        migrations = cast(list[tuple[int, str]], raw_migrations)
        if tuple(migrations) != CURRENT_SCHEMA_MIGRATIONS[:schema_version]:
            raise BackupValidationError("database migration history is incomplete")
        actual_definitions = {
            normalize_schema_definition(cast(str, row[0]))
            for row in connection.execute(
                "SELECT sql FROM sqlite_schema WHERE sql IS NOT NULL"
            ).fetchall()
        }
        # Older snapshots can contain additive objects created by a newer
        # process before an interrupted downgrade. Their recorded migration
        # ledger remains authoritative; require all historical definitions but
        # tolerate those additive objects. Current databases stay exact.
        if schema_version == CURRENT_SCHEMA_VERSION:
            definitions_match = actual_definitions == expected_definitions
        else:
            historical_actual = set(actual_definitions)
            # A newer process may have applied the additive memory expiry
            # column before a crash left the migration ledger at an older
            # version. Treat that column like other additive objects while the
            # historical ledger remains authoritative.
            for definition in actual_definitions:
                if (
                    definition.startswith("CREATE TABLE memories (")
                    and "expires_at TEXT" in definition
                ):
                    historical_actual.add(
                        definition.replace(
                            (
                                " expires_at TEXT CHECK (expires_at IS NULL OR "
                                "length(expires_at) <= 64),"
                            ),
                            "",
                        )
                    )
            definitions_match = expected_definitions.issubset(historical_actual)
        if not definitions_match:
            raise BackupValidationError("database schema definition is inconsistent")
        rows = connection.execute(
            """
            SELECT s.id, s.next_sequence, COUNT(e.id) AS event_count,
                   MIN(e.sequence) AS minimum_sequence, MAX(e.sequence) AS maximum_sequence
            FROM sessions AS s
            LEFT JOIN events AS e ON e.session_id = s.id
            GROUP BY s.id, s.next_sequence
            """
        ).fetchall()
        event_count = 0
        for row in rows:
            count = cast(int, row["event_count"])
            event_count += count
            if cast(int, row["next_sequence"]) != count + 1:
                raise BackupValidationError("session event sequence counter is inconsistent")
            if count and (row["minimum_sequence"] != 1 or row["maximum_sequence"] != count):
                raise BackupValidationError("session event sequence is not continuous")
        for row in connection.execute("SELECT id, mode, autonomy FROM sessions"):
            try:
                Mode(cast(str, row["mode"]))
                Autonomy(cast(str, row["autonomy"]))
            except ValueError:
                raise BackupValidationError(
                    f"session {row['id']} contains an unsupported mode or autonomy"
                ) from None
        for row in connection.execute("SELECT id, type, data_json, schema_version FROM events"):
            if row["schema_version"] != CURRENT_EVENT_SCHEMA_VERSION:
                raise BackupValidationError(f"event {row['id']} uses an unsupported schema version")
            try:
                data = json.loads(cast(str, row["data_json"]))
            except (TypeError, UnicodeError, json.JSONDecodeError):
                raise BackupValidationError(f"event {row['id']} contains invalid JSON") from None
            if not isinstance(data, dict):
                raise BackupValidationError(f"event {row['id']} data is not a JSON object")
            try:
                validate_event_payload(
                    cast(str, row["type"]),
                    _normalize_legacy_event_payload(cast(str, row["type"]), data),
                )
            except ValueError as exc:
                raise BackupValidationError(f"event {row['id']} is invalid: {exc}") from None
        try:
            replay_error = SQLiteEventStore.projection_replay_error(connection, schema_version)
        except (sqlite3.Error, ValueError) as exc:
            raise BackupValidationError(f"event projection replay failed: {exc}") from None
        if replay_error is not None:
            raise BackupValidationError(replay_error)
        if schema_version >= 6:
            checkpoint_mismatch = connection.execute(
                """
                SELECT c.attempt_id
                FROM file_checkpoints AS c
                JOIN tool_attempts AS t ON t.id = c.attempt_id
                JOIN sessions AS s ON s.id = c.session_id
                JOIN events AS e ON e.id = c.started_event_id
                WHERE t.session_id != c.session_id
                   OR t.started_event_id != c.started_event_id
                   OR (t.state != 'started' AND NOT (? >= 23 AND t.state = 'unknown'))
                   OR s.workspace != c.workspace
                   OR e.session_id != c.session_id
                   OR e.type != 'tool.started'
                LIMIT 1
                """,
                (schema_version,),
            ).fetchone()
            if checkpoint_mismatch is not None:
                raise BackupValidationError("workspace file checkpoint is inconsistent")
            mode_columns = (
                "preimage_executable, postimage_executable"
                if schema_version >= 12
                else "CASE WHEN preimage_sha256 IS NULL THEN NULL "
                "ELSE COALESCE(preimage_executable, 0) END AS preimage_executable, "
                "COALESCE(postimage_executable, 0) AS postimage_executable"
                if schema_version >= 10
                else "CASE WHEN preimage_sha256 IS NULL THEN NULL ELSE 0 END AS "
                "preimage_executable, 0 AS postimage_executable"
            )
            state_columns = (
                "preimage_kind, postimage_kind"
                if schema_version >= 12
                else "CASE WHEN preimage_sha256 IS NULL THEN 'missing' ELSE 'file' END AS "
                "preimage_kind, 'file' AS postimage_kind"
            )
            for row in connection.execute(
                f"""
                SELECT attempt_id, relative_path, preimage_sha256,
                        protected_preimage, session_id, workspace,
                        postimage_sha256, created_at, {mode_columns}, {state_columns}
                FROM file_checkpoints
                """
            ):
                protected_preimage = row["protected_preimage"]
                preimage_digest = row["preimage_sha256"]
                relative_path = row["relative_path"]
                # Decryption is deliberately not attempted during validation: a
                # checkpoint that the current Windows user cannot decrypt (for
                # example after a cross-user restore) must not brick database
                # opening or backup verification. Recovery treats it as an
                # unknown-outcome attempt instead.
                preimage_kind = row["preimage_kind"]
                postimage_kind = row["postimage_kind"]
                preimage_mode = row["preimage_executable"]
                postimage_mode = row["postimage_executable"]
                if (
                    not isinstance(relative_path, str)
                    or "\\" in relative_path
                    or relative_path.startswith("/")
                    or any(part in {"", ".", ".."} for part in relative_path.split("/"))
                    or not _is_timezone_aware_timestamp(row["created_at"])
                    or preimage_kind not in {"missing", "file", "directory"}
                    or postimage_kind not in {"missing", "file", "directory"}
                    or preimage_mode not in {None, 0, 1}
                    or postimage_mode not in {None, 0, 1}
                    or (
                        preimage_kind == "file"
                        and (
                            protected_preimage is None
                            or not _is_sha256(preimage_digest)
                            or preimage_mode is None
                        )
                    )
                    or (
                        preimage_kind != "file"
                        and (
                            protected_preimage is not None
                            or preimage_digest is not None
                            or preimage_mode is not None
                        )
                    )
                    or (
                        postimage_kind == "file"
                        and (not _is_sha256(row["postimage_sha256"]) or postimage_mode is None)
                    )
                    or (
                        postimage_kind != "file"
                        and (row["postimage_sha256"] is not None or postimage_mode is not None)
                    )
                    or (
                        protected_preimage is not None and not isinstance(protected_preimage, bytes)
                    )
                    or (preimage_digest is not None and not _is_sha256(preimage_digest))
                ):
                    raise BackupValidationError(
                        f"workspace file checkpoint {row['attempt_id']} is invalid"
                    )
        if schema_version >= 5:
            search_index_mismatch = connection.execute(
                """
                WITH missing AS (
                    SELECT rowid FROM search_documents
                    EXCEPT
                    SELECT id FROM session_search_docsize
                ),
                unexpected AS (
                    SELECT id FROM session_search_docsize
                    EXCEPT
                    SELECT rowid FROM search_documents
                )
                SELECT 1 FROM missing
                UNION ALL
                SELECT 1 FROM unexpected
                UNION ALL
                SELECT 1
                FROM search_documents AS d
                LEFT JOIN session_search_vocab AS v
                  ON v.doc = d.rowid
                 AND v.col = 'integrity_token'
                 AND v.term = d.integrity_token
                WHERE v.doc IS NULL
                UNION ALL
                SELECT 1
                FROM session_search_vocab AS v
                LEFT JOIN search_documents AS d
                  ON d.rowid = v.doc
                 AND d.integrity_token = v.term
                WHERE v.col = 'integrity_token' AND d.rowid IS NULL
                LIMIT 1
                """
            ).fetchone()
            if search_index_mismatch is not None:
                raise BackupValidationError("session search index is inconsistent")
            for row in connection.execute("SELECT id, text, integrity_token FROM search_documents"):
                payload = f"{row['id']}\0{row['text']}".encode()
                expected_token = f"z{hashlib.sha256(payload).hexdigest()}"
                if row["integrity_token"] != expected_token:
                    raise BackupValidationError(
                        f"session search document {row['id']} has an invalid integrity token"
                    )
            _validate_search_terms(connection)
        if schema_version >= 11:
            for artifact in connection.execute(
                "SELECT sha256, content, byte_count FROM binary_artifacts"
            ):
                content = artifact["content"]
                if (
                    not isinstance(content, bytes)
                    or not _is_sha256(artifact["sha256"])
                    or len(content) != artifact["byte_count"]
                    or len(content) > 16 * 1024 * 1024
                    or hashlib.sha256(content).hexdigest() != artifact["sha256"]
                ):
                    raise BackupValidationError("sandbox binary artifact is invalid")
            orphan = connection.execute(
                """
                SELECT a.sha256
                FROM binary_artifacts AS a
                LEFT JOIN sandbox_change_artifacts AS r
                  ON r.artifact_sha256 = a.sha256
                WHERE r.artifact_sha256 IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM events AS e
                      WHERE e.type = 'image.attached'
                        AND json_extract(e.data_json, '$.sha256') = a.sha256
                  )
                LIMIT 1
                """
            ).fetchone()
            if orphan is not None:
                raise BackupValidationError("binary artifact is unreferenced")
            for missing_query in (
                """
                SELECT 1 FROM events AS e
                WHERE e.type = 'image.attached'
                  AND json_type(e.data_json, '$.sha256') = 'text'
                  AND NOT EXISTS (
                      SELECT 1 FROM binary_artifacts AS b
                      WHERE b.sha256 = json_extract(e.data_json, '$.sha256')
                  )
                LIMIT 1
                """,
                """
                SELECT 1 FROM events AS e
                WHERE e.type = 'sandbox.changeset.created'
                  AND json_extract(e.data_json, '$.format_version') = 2
                  AND EXISTS (
                      SELECT 1
                      FROM json_each(
                          CASE WHEN json_type(e.data_json, '$.changes') = 'array'
                               THEN json_extract(e.data_json, '$.changes') END
                      ) AS change
                      WHERE json_type(change.value, '$.artifact_sha256') = 'text'
                        AND NOT EXISTS (
                            SELECT 1 FROM binary_artifacts AS b
                            WHERE b.sha256 = json_extract(change.value, '$.artifact_sha256')
                        )
                  )
                LIMIT 1
                """,
            ):
                missing = connection.execute(missing_query).fetchone()
                if missing is not None:
                    raise BackupValidationError("event references a missing binary artifact")
        return DatabaseValidation(schema_version, len(rows), event_count)
    except sqlite3.Error:
        raise BackupValidationError("database validation query failed") from None
    finally:
        connection.close()


def _referenced_binary_artifact_ids(events: Iterable[Event]) -> set[str]:
    """Collect binary artifact sha256 identifiers referenced by events.

    Covers both ``sandbox.changeset.created`` (format_version 2) change entries and
    ``image.attached`` events so exports, archive verification, and garbage
    collection all share one definition of "referenced".
    """
    identifiers: set[str] = set()
    for event in events:
        if event.type == "sandbox.changeset.created" and event.data.get("format_version") == 2:
            for change in cast(list[dict[str, Any]], event.data.get("changes", [])):
                if isinstance(change, dict) and isinstance(change.get("artifact_sha256"), str):
                    identifiers.add(change["artifact_sha256"])
        elif event.type == "image.attached":
            sha256 = event.data.get("sha256")
            if isinstance(sha256, str):
                identifiers.add(sha256)
    return identifiers


def export_session(
    database: str | Path,
    session_id: str,
    destination: str | Path,
) -> Path:
    database_path = Path(database).expanduser().resolve()
    if not database_path.is_file():
        raise KeyError(f"unknown session: {session_id}")
    source_identity = _file_identity(database_path)
    destination_path = Path(destination).expanduser().resolve()
    if destination_path.exists():
        raise FileExistsError(f"export destination already exists: {destination_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination_path.name}.",
        suffix=".zip.tmp",
        dir=destination_path.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    snapshot_descriptor, snapshot_name = tempfile.mkstemp(
        prefix=f".{destination_path.name}.",
        suffix=".snapshot.tmp",
        dir=destination_path.parent,
    )
    os.close(snapshot_descriptor)
    snapshot_path = Path(snapshot_name)
    try:
        _online_backup(database_path, snapshot_path, source_identity=source_identity)
        validation = validate_database(snapshot_path)
        session = SQLiteEventStore.get_session_read_only(snapshot_path, session_id)
        if session is None:
            raise KeyError(f"unknown session: {session_id}")
        events = SQLiteEventStore.list_events_read_only(snapshot_path, session_id)
        _validate_event_sequence(events)
        active_checkpoints = SQLiteEventStore.list_file_checkpoints_read_only(
            snapshot_path,
            session_id,
        )
        if active_checkpoints:
            detail = ", ".join(path for _, path in active_checkpoints)
            raise SessionExportError(
                "session has interrupted file-write checkpoints; resume the session to settle "
                f"them before exporting ({detail})"
            )
        todos = SQLiteEventStore.list_todos_read_only(snapshot_path, session_id)
        sources = SQLiteEventStore.list_research_sources_read_only(snapshot_path, session_id)
        citations = SQLiteEventStore.list_citations_read_only(snapshot_path, session_id)
        _validate_event_sequence(events)
        memory_tool_call_ids = {
            cast(str, event.data["tool_call_id"])
            for event in events
            if event.type == "tool.proposed"
            and event.data.get("name") in {"memory_search", "memory_write"}
            and isinstance(event.data.get("tool_call_id"), str)
        }
        event_payloads: list[bytes] = []
        for event in events:
            archive_type, archive_data = _archive_event(event, memory_tool_call_ids)
            event_payloads.append(
                _json_bytes(
                    {
                        "id": event.id,
                        "session_id": event.session_id,
                        "type": archive_type,
                        "data": archive_data,
                        "schema_version": event.schema_version,
                        "sequence": event.sequence,
                        "causation_id": event.causation_id,
                        "correlation_id": event.correlation_id,
                        "created_at": event.created_at,
                    },
                    newline=True,
                )
            )
        event_lines = b"".join(event_payloads)
        payloads = {
            "session.json": _json_bytes(asdict(session)),
            "events.jsonl": event_lines,
            "todos.json": _json_bytes(
                [
                    {
                        "id": todo.id,
                        "content": todo.content,
                        "status": todo.status.value,
                        "position": todo.position,
                        "created_at": todo.created_at,
                        "updated_at": todo.updated_at,
                    }
                    for todo in todos
                ]
            ),
            "sources.json": _json_bytes(
                [
                    {
                        "id": source.id,
                        "url": source.url,
                        "title": source.title,
                        "artifact_sha256": source.artifact_sha256,
                        "artifact_bytes": source.artifact_bytes,
                        "response_sha256": source.response_sha256,
                        "response_bytes": source.response_bytes,
                        "media_type": source.media_type,
                        "fetched_at": source.fetched_at,
                        "truncated": source.truncated,
                        "summary": source.summary,
                        "created_at": source.created_at,
                        "updated_at": source.updated_at,
                    }
                    for source in sources
                ]
            ),
            "citations.json": _json_bytes(
                [
                    {
                        "id": citation.id,
                        "source_id": citation.source_id,
                        "claim": citation.claim,
                        "locator": citation.locator,
                        "quote": citation.quote,
                        "created_at": citation.created_at,
                    }
                    for citation in citations
                ]
            ),
        }
        for artifact_sha256 in sorted({source.artifact_sha256 for source in sources}):
            artifact = SQLiteEventStore.get_text_artifact_read_only(
                snapshot_path,
                artifact_sha256,
            )
            if artifact is None or hashlib.sha256(artifact.content).hexdigest() != artifact_sha256:
                raise BackupValidationError("research artifact is unavailable or corrupt")
            payloads[f"artifacts/{artifact_sha256}.txt"] = artifact.content
        sandbox_artifact_ids = _referenced_binary_artifact_ids(events)
        for artifact_sha256 in sorted(sandbox_artifact_ids):
            sandbox_artifact = SQLiteEventStore.get_binary_artifact_read_only(
                snapshot_path,
                artifact_sha256,
            )
            if (
                sandbox_artifact is None
                or hashlib.sha256(sandbox_artifact.content).hexdigest() != artifact_sha256
            ):
                raise BackupValidationError("sandbox artifact is unavailable or corrupt")
            payloads[f"sandbox-artifacts/{artifact_sha256}.bin"] = sandbox_artifact.content
        manifest = {
            "format_version": _EXPORT_FORMAT_VERSION,
            "schema_version": validation.schema_version,
            "created_at": datetime.now(UTC).isoformat(),
            "session_id": session.id,
            "event_count": len(events),
            "todo_count": len(todos),
            "source_count": len(sources),
            "citation_count": len(citations),
            "artifact_count": len({source.artifact_sha256 for source in sources}),
            "sandbox_artifact_count": len(sandbox_artifact_ids),
            "contains_conversation_and_tool_output": True,
            "contains_research_evidence": bool(sources or citations),
            "contains_sandbox_artifacts": bool(sandbox_artifact_ids),
            "files": {
                name: {"sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}
                for name, payload in payloads.items()
            },
        }
        manifest_payload = _json_bytes(manifest)
        archive_payloads = {"manifest.json": manifest_payload, **payloads}
        if len(archive_payloads) > _MAX_SESSION_ARCHIVE_ENTRIES:
            raise BackupValidationError("session archive entry count exceeds the safety limit")
        expanded_size = 0
        for name, payload in archive_payloads.items():
            if len(payload) > _archive_member_limit(name):
                raise BackupValidationError("session archive member exceeds the safety limit")
            expanded_size += len(payload)
        if expanded_size > _MAX_SESSION_ARCHIVE_BYTES:
            raise BackupValidationError("session archive expanded size exceeds the safety limit")
        with zipfile.ZipFile(
            temporary_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            archive.writestr("manifest.json", manifest_payload)
            for name, payload in payloads.items():
                archive.writestr(name, payload)
        _fsync_file(temporary_path)
        _verify_session_archive(temporary_path)
        _publish_new_file(temporary_path, destination_path)
        return destination_path
    finally:
        temporary_path.unlink(missing_ok=True)
        snapshot_path.unlink(missing_ok=True)


def verify_session_archive(archive: str | Path) -> SessionArchiveValidation:
    return _verify_session_archive(archive).validation


def import_session_archive(
    store: SQLiteEventStore,
    archive: str | Path,
    workspace: str | Path,
) -> Session:
    verified = _verify_session_archive(archive)
    workspace_path = Path(workspace).expanduser().resolve(strict=True)
    if not workspace_path.is_dir():
        raise ValueError(f"workspace is not a directory: {workspace_path}")
    imported_session_id = str(uuid4())
    event_ids = {event.id: str(uuid4()) for event in verified.events}
    attempt_ids: dict[str, str] = {}
    tool_call_ids: dict[str, str] = {}
    todo_ids: dict[str, str] = {}
    citation_ids: dict[str, str] = {}
    idempotency_keys: dict[str, str] = {}
    for event in verified.events:
        _collect_import_id(event.data.get("attempt_id"), attempt_ids)
        _collect_import_id(event.data.get("tool_call_id"), tool_call_ids)
        _collect_import_id(event.data.get("todo_id"), todo_ids)
        _collect_import_id(event.data.get("citation_id"), citation_ids)
        _collect_import_id(event.data.get("idempotency_key"), idempotency_keys)
        raw_calls = event.data.get("tool_calls")
        if isinstance(raw_calls, list):
            for raw_call in raw_calls:
                if isinstance(raw_call, dict):
                    _collect_import_id(raw_call.get("id"), tool_call_ids)
    correlation_ids: dict[str, str] = {}
    external_causation_ids: dict[str, str] = {}
    replacements = {
        **attempt_ids,
        **tool_call_ids,
        **todo_ids,
        **citation_ids,
        **idempotency_keys,
    }
    imported_events: list[Event] = []
    for event in verified.events:
        data = _remap_import_event_data(
            event,
            imported_session_id,
            str(workspace_path),
            attempt_ids=attempt_ids,
            tool_call_ids=tool_call_ids,
            todo_ids=todo_ids,
            citation_ids=citation_ids,
            idempotency_keys=idempotency_keys,
            replacements=replacements,
        )
        causation_id = _remap_event_link(
            event.causation_id,
            event_ids,
            external_causation_ids,
        )
        correlation_id = _remap_event_link(
            event.correlation_id,
            event_ids,
            correlation_ids,
        )
        imported_events.append(
            Event(
                id=event_ids[event.id],
                session_id=imported_session_id,
                type=(
                    "sandbox.change.applied.imported"
                    if event.type == "sandbox.change.applied"
                    else "autonomy.changed.imported"
                    if event.type == "autonomy.changed"
                    else event.type
                ),
                data=data,
                schema_version=event.schema_version,
                causation_id=causation_id,
                correlation_id=correlation_id,
                created_at=event.created_at,
            )
        )
    now = datetime.now(UTC).isoformat()
    for anchor in _active_background_job_anchors(imported_events).values():
        imported_events.append(
            Event(
                session_id=imported_session_id,
                type="background.job.interrupted",
                data={
                    "job_id": anchor.data["job_id"],
                    "reason": "session archive imported without a durable process identity",
                },
                causation_id=anchor.id,
                correlation_id=anchor.correlation_id,
                created_at=now,
            )
        )
    imported_events.append(
        Event(
            session_id=imported_session_id,
            type="session.imported",
            data={
                "archive_session_id": verified.session.id,
                "archive_format_version": verified.validation.format_version,
                "archive_sha256": _sha256_file(Path(archive).expanduser().resolve()),
            },
            created_at=now,
        )
    )
    imported = Session(
        workspace=str(workspace_path),
        mode=_archive_initial_mode(verified.session, list(verified.events)),
        autonomy=Autonomy.ASK,
        id=imported_session_id,
        title=f"Imported: {verified.session.title}"[:500],
        created_at=now,
        updated_at=now,
    )
    store.import_session(
        imported,
        tuple(imported_events),
        tuple(
            BinaryArtifact(sha256, content)
            for sha256, content in verified.sandbox_artifacts.items()
        ),
    )
    projected = store.get_session(imported_session_id)
    if projected is None:
        raise RuntimeError("imported session projection is unavailable")
    return projected


def _verify_session_archive(archive: str | Path) -> _VerifiedSessionArchive:
    archive_path = Path(archive).expanduser().resolve()
    try:
        archive_size = archive_path.stat().st_size
    except OSError:
        raise BackupValidationError("session archive is missing or unreadable") from None
    if not 0 < archive_size <= _MAX_SESSION_ARCHIVE_BYTES:
        raise BackupValidationError("session archive size exceeds the safety limit")
    try:
        with zipfile.ZipFile(archive_path) as document:
            payloads = _verified_archive_payloads(document)
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile):
        raise BackupValidationError("session archive is not a valid ZIP file") from None

    manifest = _json_object(payloads.pop("manifest.json"), "session archive manifest")
    format_version = manifest.get("format_version")
    manifest_fields = {
        "format_version",
        "schema_version",
        "created_at",
        "session_id",
        "event_count",
        "todo_count",
        "source_count",
        "citation_count",
        "artifact_count",
        "contains_conversation_and_tool_output",
        "contains_research_evidence",
        "files",
    }
    if format_version == 3:
        manifest_fields.update({"sandbox_artifact_count", "contains_sandbox_artifacts"})
    if set(manifest) != manifest_fields:
        raise BackupValidationError("session archive manifest fields are invalid")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != set(payloads):
        raise BackupValidationError("session archive manifest file set is inconsistent")
    for name, payload in payloads.items():
        metadata = files.get(name)
        if (
            not isinstance(metadata, dict)
            or set(metadata) != {"sha256", "size"}
            or type(metadata.get("size")) is not int
            or metadata["size"] != len(payload)
            or not _is_sha256(metadata.get("sha256"))
            or metadata["sha256"] != hashlib.sha256(payload).hexdigest()
        ):
            raise BackupValidationError(f"session archive member failed verification: {name}")

    required_files = {
        "session.json",
        "events.jsonl",
        "todos.json",
        "sources.json",
        "citations.json",
    }
    if not required_files.issubset(payloads):
        raise BackupValidationError("session archive is missing required members")
    schema_version = manifest.get("schema_version")
    session_id = manifest.get("session_id")
    if type(format_version) is not int or format_version not in {2, 3}:
        raise BackupValidationError("session archive format version is unsupported")
    supported_schemas = (
        {7, 8, 9, 10} if format_version == 2 else set(range(7, CURRENT_SCHEMA_VERSION + 1))
    )
    if type(schema_version) is not int or schema_version not in supported_schemas:
        raise BackupValidationError("session archive schema version is unsupported")
    if not isinstance(session_id, str) or not session_id:
        raise BackupValidationError("session archive has an invalid session id")
    if not _is_timezone_aware_timestamp(manifest.get("created_at")):
        raise BackupValidationError("session archive creation timestamp is invalid")

    session = _archive_session(payloads["session.json"], session_id)
    events = _archive_events(payloads["events.jsonl"], session_id)
    if len(_active_background_job_anchors(events)) > _MAX_IMPORTED_ACTIVE_BACKGROUND_JOBS:
        raise BackupValidationError("session archive exceeds the active background-job limit")
    required_schema = 7
    if any(event.type.startswith("memory.") for event in events):
        required_schema = max(required_schema, 8)
    if any(event.type.startswith("sandbox.") for event in events):
        required_schema = max(required_schema, 9)
    if any(
        event.type == "sandbox.changeset.created" and event.data.get("format_version") == 2
        for event in events
    ):
        required_schema = max(required_schema, 11)
    if any(event.type.startswith("background.job.") for event in events):
        required_schema = max(required_schema, 13)
    if schema_version < required_schema:
        raise BackupValidationError("session archive schema version contradicts its event features")
    todos = _archive_object_list(payloads["todos.json"], "Todo projection")
    sources = _archive_object_list(payloads["sources.json"], "source projection")
    citations = _archive_object_list(payloads["citations.json"], "citation projection")
    artifacts = {
        name.removeprefix("artifacts/").removesuffix(".txt"): payload
        for name, payload in payloads.items()
        if name.startswith("artifacts/")
    }
    sandbox_artifacts = {
        name.removeprefix("sandbox-artifacts/").removesuffix(".bin"): payload
        for name, payload in payloads.items()
        if name.startswith("sandbox-artifacts/")
    }
    _validate_archive_counts(
        manifest,
        events,
        todos,
        sources,
        citations,
        artifacts,
        sandbox_artifacts,
    )
    expected_artifact_names = {
        f"artifacts/{source.get('artifact_sha256')}.txt" for source in sources
    }
    actual_artifact_names = {name for name in payloads if name.startswith("artifacts/")}
    if expected_artifact_names != actual_artifact_names:
        raise BackupValidationError("session archive artifact references are inconsistent")
    for digest, content in artifacts.items():
        if (
            not _is_sha256(digest)
            or len(content) > _MAX_SESSION_ARTIFACT_BYTES
            or hashlib.sha256(content).hexdigest() != digest
        ):
            raise BackupValidationError("session archive contains an invalid research artifact")
    expected_sandbox_names = {
        f"sandbox-artifacts/{sha256}.bin" for sha256 in _referenced_binary_artifact_ids(events)
    }
    actual_sandbox_names = {name for name in payloads if name.startswith("sandbox-artifacts/")}
    if expected_sandbox_names != actual_sandbox_names:
        raise BackupValidationError("session archive sandbox artifact references are inconsistent")
    for digest, content in sandbox_artifacts.items():
        if (
            not _is_sha256(digest)
            or len(content) > _MAX_SANDBOX_ARTIFACT_BYTES
            or hashlib.sha256(content).hexdigest() != digest
        ):
            raise BackupValidationError("session archive contains an invalid sandbox artifact")

    _verify_archive_projections(
        session,
        events,
        todos,
        sources,
        citations,
        artifacts,
        sandbox_artifacts,
    )
    validation = SessionArchiveValidation(
        format_version=format_version,
        schema_version=schema_version,
        session_id=session_id,
        event_count=len(events),
        todo_count=len(todos),
        source_count=len(sources),
        citation_count=len(citations),
        artifact_count=len(artifacts),
    )
    return _VerifiedSessionArchive(
        validation,
        session,
        tuple(events),
        tuple(todos),
        tuple(sources),
        tuple(citations),
        artifacts,
        sandbox_artifacts,
    )


def _verified_archive_payloads(document: zipfile.ZipFile) -> dict[str, bytes]:
    entries = document.infolist()
    if not entries or len(entries) > _MAX_SESSION_ARCHIVE_ENTRIES:
        raise BackupValidationError("session archive entry count exceeds the safety limit")
    names = [entry.filename for entry in entries]
    if len(names) != len(set(names)):
        raise BackupValidationError("session archive contains duplicate member names")
    total_size = 0
    for entry in entries:
        path = PurePosixPath(entry.filename)
        if (
            entry.is_dir()
            or not entry.filename
            or "\\" in entry.filename
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or entry.flag_bits & 0x1
            or stat.S_ISLNK(entry.external_attr >> 16)
            or entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
        ):
            raise BackupValidationError("session archive contains an unsafe member")
        maximum = _archive_member_limit(entry.filename)
        if entry.file_size < 0 or entry.file_size > maximum:
            raise BackupValidationError("session archive member exceeds the safety limit")
        if entry.file_size > 1024 * 1024 and (
            entry.compress_size <= 0 or entry.file_size > entry.compress_size * 1000
        ):
            raise BackupValidationError("session archive compression ratio is unsafe")
        total_size += entry.file_size
        if total_size > _MAX_SESSION_ARCHIVE_BYTES:
            raise BackupValidationError("session archive expanded size exceeds the safety limit")
    if "manifest.json" not in names:
        raise BackupValidationError("session archive manifest is missing")
    payloads: dict[str, bytes] = {}
    for entry in entries:
        with document.open(entry, "r") as stream:
            payload = stream.read(entry.file_size + 1)
        if len(payload) != entry.file_size:
            raise BackupValidationError("session archive member size changed while reading")
        payloads[entry.filename] = payload
    return payloads


def _archive_member_limit(name: str) -> int:
    if name == "manifest.json":
        return _MAX_SESSION_ARCHIVE_MANIFEST_BYTES
    if name == "events.jsonl":
        return 64 * 1024 * 1024
    if name in {"session.json", "todos.json", "sources.json", "citations.json"}:
        return _MAX_SESSION_ARCHIVE_JSON_BYTES
    if re.fullmatch(r"artifacts/[0-9a-f]{64}\.txt", name):
        return _MAX_SESSION_ARTIFACT_BYTES
    if re.fullmatch(r"sandbox-artifacts/[0-9a-f]{64}\.bin", name):
        return _MAX_SANDBOX_ARTIFACT_BYTES
    raise BackupValidationError(f"session archive contains an unexpected member: {name}")


def _json_object(payload: bytes, label: str) -> dict[str, Any]:
    value = _strict_json(payload, label)
    if not isinstance(value, dict):
        raise BackupValidationError(f"{label} is not a JSON object")
    return cast(dict[str, Any], value)


def _strict_json(payload: bytes, label: str) -> object:
    try:
        text = payload.decode("utf-8")

        def object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON key")
                result[key] = value
            return result

        return json.loads(
            text,
            object_pairs_hook=object_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("invalid number")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise BackupValidationError(f"{label} contains invalid JSON") from None


def _archive_session(payload: bytes, expected_id: str) -> Session:
    data = _json_object(payload, "session archive session")
    required = {
        "workspace",
        "mode",
        "autonomy",
        "id",
        "title",
        "messages",
        "created_at",
        "updated_at",
    }
    if set(data) != required or data.get("id") != expected_id or data.get("messages") != []:
        raise BackupValidationError("session archive session metadata is inconsistent")
    if (
        not isinstance(data.get("workspace"), str)
        or not data["workspace"]
        or not isinstance(data.get("title"), str)
        or not data["title"]
        or not _is_timezone_aware_timestamp(data.get("created_at"))
        or not _is_timezone_aware_timestamp(data.get("updated_at"))
    ):
        raise BackupValidationError("session archive session metadata is invalid")
    try:
        mode = Mode(cast(str, data.get("mode")))
        autonomy = Autonomy(cast(str, data.get("autonomy")))
    except (TypeError, ValueError):
        raise BackupValidationError("session archive session mode is invalid") from None
    return Session(
        workspace=cast(str, data["workspace"]),
        mode=mode,
        autonomy=autonomy,
        id=expected_id,
        title=cast(str, data["title"]),
        created_at=cast(str, data["created_at"]),
        updated_at=cast(str, data["updated_at"]),
    )


def _archive_events(payload: bytes, session_id: str) -> list[Event]:
    if not payload:
        return []
    lines = payload.splitlines()
    if len(lines) > _MAX_SESSION_ARCHIVE_EVENTS or any(
        not line or len(line) > _MAX_SESSION_ARCHIVE_EVENT_BYTES for line in lines
    ):
        raise BackupValidationError("session archive event stream exceeds the safety limit")
    events: list[Event] = []
    ids: set[str] = set()
    for expected_sequence, line in enumerate(lines, start=1):
        data = _json_object(line, "session archive event")
        if set(data) != {
            "id",
            "session_id",
            "type",
            "data",
            "schema_version",
            "sequence",
            "causation_id",
            "correlation_id",
            "created_at",
        }:
            raise BackupValidationError("session archive event fields are invalid")
        event_id = data.get("id")
        event_data = data.get("data")
        if (
            not isinstance(event_id, str)
            or not event_id
            or event_id in ids
            or data.get("session_id") != session_id
            or not isinstance(data.get("type"), str)
            or not data["type"]
            or not isinstance(event_data, dict)
            or type(data.get("schema_version")) is not int
            or data.get("schema_version") != CURRENT_EVENT_SCHEMA_VERSION
            or type(data.get("sequence")) is not int
            or data.get("sequence") != expected_sequence
            or (
                data.get("causation_id") is not None
                and not isinstance(data.get("causation_id"), str)
            )
            or (
                data.get("correlation_id") is not None
                and not isinstance(data.get("correlation_id"), str)
            )
            or not _is_timezone_aware_timestamp(data.get("created_at"))
        ):
            raise BackupValidationError("session archive event metadata is invalid")
        ids.add(event_id)
        event_type = cast(str, data["type"])
        if event_type in {"memory.upserted", "memory.deleted"}:
            raise BackupValidationError("session archive contains an active memory event")
        if event_type == "memory.audit" and not _is_memory_audit_event(event_data):
            raise BackupValidationError("session archive memory audit event is invalid")
        try:
            validate_event_payload(event_type, cast(dict[str, Any], event_data))
        except ValueError as exc:
            raise BackupValidationError(f"session archive event is invalid: {exc}") from None
        events.append(
            Event(
                id=event_id,
                session_id=session_id,
                type=event_type,
                data=cast(dict[str, Any], event_data),
                schema_version=CURRENT_EVENT_SCHEMA_VERSION,
                sequence=expected_sequence,
                causation_id=cast(str | None, data.get("causation_id")),
                correlation_id=cast(str | None, data.get("correlation_id")),
                created_at=cast(str, data["created_at"]),
            )
        )
    return events


def _archive_object_list(payload: bytes, label: str) -> list[dict[str, Any]]:
    value = _strict_json(payload, f"session archive {label}")
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise BackupValidationError(f"session archive {label} is invalid")
    return cast(list[dict[str, Any]], value)


def _validate_archive_counts(
    manifest: dict[str, Any],
    events: list[Event],
    todos: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    artifacts: dict[str, bytes],
    sandbox_artifacts: dict[str, bytes],
) -> None:
    expected = {
        "event_count": len(events),
        "todo_count": len(todos),
        "source_count": len(sources),
        "citation_count": len(citations),
        "artifact_count": len(artifacts),
    }
    if any(
        type(manifest.get(key)) is not int or manifest.get(key) != value
        for key, value in expected.items()
    ):
        raise BackupValidationError("session archive manifest counts are inconsistent")
    if (
        manifest.get("contains_conversation_and_tool_output") is not True
        or type(manifest.get("contains_research_evidence")) is not bool
    ):
        raise BackupValidationError("session archive privacy metadata is invalid")
    if manifest["contains_research_evidence"] != bool(sources or citations):
        raise BackupValidationError("session archive research metadata is inconsistent")
    if manifest.get("format_version") == 3 and (
        type(manifest.get("sandbox_artifact_count")) is not int
        or manifest["sandbox_artifact_count"] != len(sandbox_artifacts)
        or type(manifest.get("contains_sandbox_artifacts")) is not bool
        or manifest["contains_sandbox_artifacts"] != bool(sandbox_artifacts)
    ):
        raise BackupValidationError("session archive sandbox artifact metadata is inconsistent")


def _verify_archive_projections(
    session: Session,
    events: list[Event],
    todos: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    artifacts: dict[str, bytes],
    sandbox_artifacts: dict[str, bytes],
) -> None:
    initial_mode = _archive_initial_mode(session, events)
    initial_autonomy = _archive_initial_autonomy(session, events)
    with tempfile.TemporaryDirectory(prefix="agent-workspace-archive-verify-") as temporary:
        database = Path(temporary) / "archive.db"
        replay_session = Session(
            workspace=session.workspace,
            mode=initial_mode,
            autonomy=initial_autonomy,
            id=session.id,
            title=session.title,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        with SQLiteEventStore(database, create_migration_backup=False) as store:
            try:
                store.import_session(
                    replay_session,
                    tuple(events),
                    tuple(
                        BinaryArtifact(sha256, content)
                        for sha256, content in sandbox_artifacts.items()
                    ),
                )
            except (sqlite3.Error, ValueError):
                raise BackupValidationError("session archive projection replay failed") from None
            replayed = store.get_session(session.id)
            replayed_todos = [
                {
                    "id": todo.id,
                    "content": todo.content,
                    "status": todo.status.value,
                    "position": todo.position,
                    "created_at": todo.created_at,
                    "updated_at": todo.updated_at,
                }
                for todo in store.list_todos(session.id)
            ]
            replayed_sources = [
                {
                    "id": source.id,
                    "url": source.url,
                    "title": source.title,
                    "artifact_sha256": source.artifact_sha256,
                    "artifact_bytes": source.artifact_bytes,
                    "response_sha256": source.response_sha256,
                    "response_bytes": source.response_bytes,
                    "media_type": source.media_type,
                    "fetched_at": source.fetched_at,
                    "truncated": source.truncated,
                    "summary": source.summary,
                    "created_at": source.created_at,
                    "updated_at": source.updated_at,
                }
                for source in store.list_research_sources(session.id)
            ]
            replayed_citations = [
                {
                    "id": citation.id,
                    "source_id": citation.source_id,
                    "claim": citation.claim,
                    "locator": citation.locator,
                    "quote": citation.quote,
                    "created_at": citation.created_at,
                }
                for citation in store.list_citations(session.id)
            ]
            replayed_artifacts = {
                digest: artifact.content
                for digest in artifacts
                if (artifact := store.get_text_artifact(digest)) is not None
            }
        if (
            replayed is None
            or replayed.mode is not session.mode
            or replayed.autonomy is not session.autonomy
            or replayed.title != session.title
            or replayed_todos != todos
            or replayed_sources != sources
            or replayed_citations != citations
            or replayed_artifacts != artifacts
        ):
            raise BackupValidationError("session archive projections are inconsistent")
        validate_database(database)


def _active_background_job_anchors(events: list[Event]) -> dict[str, Event]:
    active: dict[str, Event] = {}
    for event in events:
        job_id = event.data.get("job_id")
        if not isinstance(job_id, str) or not event.type.startswith("background.job."):
            continue
        if event.type == "background.job.created" or (
            event.type == "background.job.started" and job_id in active
        ):
            active[job_id] = event
        elif event.type in {
            "background.job.succeeded",
            "background.job.failed",
            "background.job.stopped",
            "background.job.interrupted",
        }:
            active.pop(job_id, None)
    return active


def _archive_initial_mode(session: Session, events: list[Event]) -> Mode:
    first_change = next((event for event in events if event.type == "mode.changed"), None)
    if first_change is None:
        return session.mode
    try:
        return Mode(cast(str, first_change.data.get("from_mode")))
    except (TypeError, ValueError):
        raise BackupValidationError("session archive initial mode is invalid") from None


def _archive_initial_autonomy(session: Session, events: list[Event]) -> Autonomy:
    first_change = next((event for event in events if event.type == "autonomy.changed"), None)
    if first_change is None:
        return session.autonomy
    try:
        return Autonomy(cast(str, first_change.data.get("from_autonomy")))
    except (TypeError, ValueError):
        raise BackupValidationError("session archive initial autonomy is invalid") from None


def _collect_import_id(value: object, mapping: dict[str, str]) -> None:
    if isinstance(value, str) and value:
        mapping.setdefault(value, str(uuid4()))


def _remap_event_link(
    value: str | None,
    event_ids: dict[str, str],
    external_ids: dict[str, str],
) -> str | None:
    if value is None:
        return None
    if value in event_ids:
        return event_ids[value]
    return external_ids.setdefault(value, str(uuid4()))


def _remap_import_event_data(
    event: Event,
    session_id: str,
    workspace: str,
    *,
    attempt_ids: dict[str, str],
    tool_call_ids: dict[str, str],
    todo_ids: dict[str, str],
    citation_ids: dict[str, str],
    idempotency_keys: dict[str, str],
    replacements: dict[str, str],
) -> dict[str, Any]:
    data = copy.deepcopy(event.data)
    mappings = {
        "attempt_id": attempt_ids,
        "tool_call_id": tool_call_ids,
        "todo_id": todo_ids,
        "citation_id": citation_ids,
        "idempotency_key": idempotency_keys,
    }
    for key, mapping in mappings.items():
        value = data.get(key)
        if isinstance(value, str) and value in mapping:
            data[key] = mapping[value]
    if data.get("session_id") == event.session_id:
        data["session_id"] = session_id
    if event.type == "sandbox.changeset.created":
        data["workspace"] = workspace
    if event.type == "message.created":
        data["trust"] = "untrusted_data"
        data["reasoning"] = ""
        data["provider_metadata"] = {}
    raw_calls = data.get("tool_calls")
    if isinstance(raw_calls, list):
        for raw_call in raw_calls:
            if not isinstance(raw_call, dict):
                continue
            call_id = raw_call.get("id")
            if isinstance(call_id, str) and call_id in tool_call_ids:
                raw_call["id"] = tool_call_ids[call_id]
            raw_call["provider_metadata"] = {}
            arguments = raw_call.get("arguments")
            if isinstance(arguments, dict):
                raw_call["arguments"] = _replace_import_ids(arguments, replacements)
    if event.type == "tool.proposed" and isinstance(data.get("arguments"), dict):
        data["arguments"] = _replace_import_ids(data["arguments"], replacements)
    return data


def _replace_import_ids(value: object, replacements: dict[str, str]) -> object:
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, list):
        return [_replace_import_ids(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _replace_import_ids(item, replacements) for key, item in value.items()}
    return value


def _validate_event_sequence(events: list[Event]) -> None:
    for expected, event in enumerate(events, start=1):
        if event.sequence != expected:
            raise BackupValidationError("session event sequence is not continuous")


def _manifest_path(backup_path: Path) -> Path:
    return backup_path.with_name(f"{backup_path.name}.manifest.json")


def _latest_backup_digest(directory: Path, lineage: str) -> str | None:
    candidates: list[tuple[str, str]] = []
    for manifest_path in directory.glob(f"agent-{lineage}-*.db.manifest.json"):
        try:
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        digest = document.get("sha256")
        created_at = document.get("created_at")
        if isinstance(digest, str) and len(digest) == 64 and isinstance(created_at, str):
            candidates.append((created_at, digest))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _online_backup(
    source_path: Path,
    destination_path: Path,
    *,
    source_identity: tuple[int, int],
) -> None:
    source: sqlite3.Connection | None = None
    destination: sqlite3.Connection | None = None
    completed = False
    try:
        if _file_identity(source_path) != source_identity:
            raise BackupValidationError("database source changed before backup")
        source = sqlite3.connect(
            f"{source_path.as_uri()}?mode=ro",
            timeout=5,
            uri=True,
        )
        if _file_identity(source_path) != source_identity:
            raise BackupValidationError("database source changed while opening backup")
        destination = sqlite3.connect(str(destination_path))
        source.backup(destination)
        if _file_identity(source_path) != source_identity:
            raise BackupValidationError("database source changed during backup")
        completed = True
    except sqlite3.Error:
        raise BackupValidationError("database backup failed") from None
    finally:
        if destination is not None:
            destination.close()
        if source is not None:
            source.close()
        if not completed:
            _remove_sqlite_sidecars(destination_path)
    if completed:
        _normalize_database(destination_path)


def _normalize_database(database_path: Path) -> None:
    connection: sqlite3.Connection | None = None
    mode: str | None = None
    try:
        connection = sqlite3.connect(str(database_path), timeout=5)
        connection.execute("PRAGMA synchronous = FULL")
        row = connection.execute("PRAGMA journal_mode = DELETE").fetchone()
        mode = cast(str, row[0]) if row is not None else None
    except sqlite3.Error:
        raise BackupValidationError("database snapshot normalization failed") from None
    finally:
        if connection is not None:
            connection.close()
        _remove_sqlite_sidecars(database_path)
    if mode is None or mode.casefold() != "delete":
        raise BackupValidationError("database snapshot normalization failed")
    _reject_sqlite_sidecars(database_path, label="database snapshot")


def _publish_new_file(source_path: Path, destination_path: Path) -> None:
    durable_publish_new(source_path, destination_path)


def _file_identity(path: Path) -> tuple[int, int]:
    try:
        metadata = path.stat()
    except OSError:
        raise BackupValidationError(f"database file is unavailable: {path}") from None
    return metadata.st_dev, metadata.st_ino


def _existing_sqlite_sidecars(database_path: Path) -> list[Path]:
    return [
        database_path.with_name(f"{database_path.name}{suffix}")
        for suffix in _SQLITE_SIDECAR_SUFFIXES
        if database_path.with_name(f"{database_path.name}{suffix}").exists()
    ]


def _remove_sqlite_sidecars(database_path: Path) -> None:
    for suffix in _SQLITE_SIDECAR_SUFFIXES:
        database_path.with_name(f"{database_path.name}{suffix}").unlink(missing_ok=True)


def _reject_sqlite_sidecars(database_path: Path, *, label: str) -> None:
    sidecars = _existing_sqlite_sidecars(database_path)
    if sidecars:
        raise BackupValidationError(f"{label} has an unexpected SQLite sidecar: {sidecars[0]}")


def _ensure_destination_namespace_available(database_path: Path) -> None:
    if database_path.exists():
        raise FileExistsError(f"restore destination already exists: {database_path}")
    sidecars = _existing_sqlite_sidecars(database_path)
    if sidecars:
        raise FileExistsError(f"restore destination sidecar already exists: {sidecars[0]}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_file(path: Path) -> None:
    with path.open("r+b") as stream:
        os.fsync(stream.fileno())


def _json_bytes(value: object, *, newline: bool = False) -> bytes:
    suffix = "\n" if newline else ""
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + suffix
    ).encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        durable_replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def _prune_backups(
    directory: Path,
    *,
    lineage: str,
    keep: int,
    max_age_days: int,
    max_total_bytes: int,
    protected: Path,
) -> None:
    database_pattern = f"agent-{lineage}-*.db"
    changed = False
    for backup in directory.glob(database_pattern):
        if not _manifest_path(backup).exists():
            backup.unlink(missing_ok=True)
            _remove_sqlite_sidecars(backup)
            changed = True
    protected_manifest = _manifest_path(protected)
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    candidates: list[tuple[datetime, Path, Path, int]] = []
    for manifest in sorted(
        (
            manifest
            for manifest in directory.glob(f"agent-{lineage}-*.db.manifest.json")
            if manifest != protected_manifest
        ),
        reverse=True,
    ):
        backup_name = manifest.name.removesuffix(".manifest.json")
        backup = directory / backup_name
        if not backup.exists():
            manifest.unlink(missing_ok=True)
            changed = True
            continue
        try:
            _verify_backup(backup)
            raw_manifest = json.loads(manifest.read_text(encoding="utf-8"))
            created_at = datetime.fromisoformat(cast(str, raw_manifest["created_at"]))
            pair_size = backup.stat().st_size + manifest.stat().st_size
        except BackupValidationError:
            try:
                backup.unlink(missing_ok=True)
                _remove_sqlite_sidecars(backup)
                manifest.unlink(missing_ok=True)
            except OSError:
                continue
            changed = True
            continue
        except (KeyError, OSError, TypeError, ValueError):
            continue
        candidates.append((created_at, manifest, backup, pair_size))
    candidates.sort(key=lambda item: (item[0], item[1].name), reverse=True)
    protected_size = protected.stat().st_size + protected_manifest.stat().st_size
    retained_bytes = protected_size
    retained_count = 1
    for created_at, manifest, backup, pair_size in candidates:
        retain = (
            retained_count < keep
            and created_at >= cutoff
            and retained_bytes + pair_size <= max_total_bytes
        )
        if retain:
            retained_count += 1
            retained_bytes += pair_size
            continue
        try:
            backup.unlink(missing_ok=True)
            _remove_sqlite_sidecars(backup)
        except OSError:
            continue
        manifest.unlink(missing_ok=True)
        changed = True
    if changed:
        fsync_directory(directory)


def _redact_sensitive(value: object) -> object:
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for key, item in value.items():
            normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", str(key))
            normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", normalized)
            normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()
            sensitive = normalized in _SENSITIVE_KEYS or normalized.endswith(_SENSITIVE_SUFFIXES)
            result[str(key)] = _REDACTED if sensitive else _redact_sensitive(item)
        return result
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    return value


def _archive_event(event: Event, memory_tool_call_ids: set[str]) -> tuple[str, dict[str, Any]]:
    data = cast(dict[str, Any], _redact_sensitive(event.data))
    if event.type in {"memory.upserted", "memory.deleted"}:
        audit: dict[str, Any] = {
            "operation": "upsert" if event.type == "memory.upserted" else "delete",
            "content_omitted": True,
        }
        attempt_id = data.get("attempt_id")
        if isinstance(attempt_id, str) and attempt_id:
            audit["attempt_id"] = attempt_id
        return "memory.audit", audit
    if event.type == "tool.proposed" and data.get("name") in {
        "memory_search",
        "memory_write",
    }:
        data["arguments"] = _omitted_memory_arguments(data.get("name"), data.get("arguments"))
    if event.type == "tool.settled" and data.get("name") in {
        "memory_search",
        "memory_write",
    }:
        data["result"] = "<memory tool result omitted from archive>"
    if event.type == "message.created":
        raw_calls = data.get("tool_calls")
        if isinstance(raw_calls, list):
            for raw_call in raw_calls:
                if not isinstance(raw_call, dict) or raw_call.get("name") not in {
                    "memory_search",
                    "memory_write",
                }:
                    continue
                raw_call["arguments"] = _omitted_memory_arguments(
                    raw_call.get("name"),
                    raw_call.get("arguments"),
                )
        if data.get("role") == "tool" and data.get("tool_call_id") in memory_tool_call_ids:
            data["content"] = "<memory tool result omitted from archive>"
            data["reasoning"] = ""
    return event.type, data


def _omitted_memory_arguments(tool_name: object, arguments: object) -> dict[str, object]:
    omitted: dict[str, object] = {"memory_content_omitted": True}
    if tool_name == "memory_write" and isinstance(arguments, dict):
        action = arguments.get("action")
        if action in {"upsert", "delete"}:
            omitted["action"] = action
    return omitted


def _is_memory_audit_event(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    if set(data) not in (
        {"operation", "content_omitted"},
        {"operation", "content_omitted", "attempt_id"},
    ):
        return False
    return (
        data.get("operation") in {"upsert", "delete"}
        and data.get("content_omitted") is True
        and (
            "attempt_id" not in data
            or (isinstance(data.get("attempt_id"), str) and bool(data.get("attempt_id")))
        )
    )


def _validation_matches(raw: object, validation: DatabaseValidation) -> bool:
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "sessions", "events"}:
        return False
    if any(type(raw[key]) is not int for key in raw):
        return False
    return raw == asdict(validation)


def _validate_search_terms(connection: sqlite3.Connection) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".agent-search-validation-",
        suffix=".db",
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    expected = sqlite3.connect(temporary_path)
    try:
        expected.execute("PRAGMA journal_mode = OFF")
        expected.execute("PRAGMA synchronous = OFF")
        expected.execute("PRAGMA temp_store = FILE")
        expected.execute(
            """
            CREATE VIRTUAL TABLE expected_search USING fts5(
                text,
                integrity_token,
                tokenize='unicode61 remove_diacritics 2'
            )
            """
        )
        expected.execute(
            "CREATE VIRTUAL TABLE expected_vocab USING fts5vocab(expected_search, 'instance')"
        )
        expected.executemany(
            "INSERT INTO expected_search(rowid, text, integrity_token) VALUES (?, ?, ?)",
            connection.execute(
                "SELECT rowid, text, integrity_token FROM search_documents ORDER BY rowid"
            ),
        )
        actual_terms = connection.execute(
            """
            SELECT term, doc, col, offset
            FROM session_search_vocab
            ORDER BY term, doc, col, offset
            """
        )
        expected_terms = expected.execute(
            """
            SELECT term, doc, col, offset
            FROM expected_vocab
            ORDER BY term, doc, col, offset
            """
        )
        try:
            for actual, rebuilt in zip_longest(actual_terms, expected_terms):
                if actual is None or rebuilt is None or tuple(actual) != tuple(rebuilt):
                    raise BackupValidationError("session search index terms are inconsistent")
        finally:
            actual_terms.close()
            expected_terms.close()
    finally:
        expected.close()
        temporary_path.unlink(missing_ok=True)


def _is_timezone_aware_timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
