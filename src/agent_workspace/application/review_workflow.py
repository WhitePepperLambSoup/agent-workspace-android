"""Durable immutable review snapshots, inline comments, and delivery state."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast
from urllib.parse import urlparse
from uuid import uuid4

from agent_workspace.core.models import (
    DeliveryCheck,
    DeliveryState,
    ReviewComment,
    ReviewCommentState,
    ReviewDelivery,
    ReviewSnapshot,
)
from agent_workspace.storage.sqlite import SQLiteEventStore

_MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024
_MAX_FILES_BYTES = 700 * 1024
_MAX_FILES = 500
_CHECK_STATES = frozenset(
    {
        "queued",
        "in_progress",
        "success",
        "failure",
        "neutral",
        "skipped",
        "cancelled",
        "timed_out",
        "action_required",
        "unknown",
    }
)


class ReviewWorkflowError(ValueError):
    """Stable review workflow validation error."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _text(value: str, name: str, *, limit: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ReviewWorkflowError(f"invalid_{name}")
    normalized = value.strip()
    if (not allow_empty and not normalized) or len(normalized) > limit:
        raise ReviewWorkflowError(f"invalid_{name}")
    return normalized


def _sha(value: str, name: str) -> str:
    normalized = _text(value, name, limit=40).lower()
    if len(normalized) != 40 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ReviewWorkflowError(f"invalid_{name}")
    return normalized


def _canonical_path(value: object) -> str:
    if not isinstance(value, str) or value != value.strip() or not value or len(value) > 1_000:
        raise ReviewWorkflowError("invalid_snapshot_path")
    if "\\" in value or ":" in value:
        raise ReviewWorkflowError("invalid_snapshot_path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ReviewWorkflowError("invalid_snapshot_path")
    return value


def _canonical_files(files: Sequence[Mapping[str, Any]]) -> tuple[str, tuple[dict[str, Any], ...]]:
    if not isinstance(files, Sequence) or isinstance(files, (str, bytes)):
        raise ReviewWorkflowError("invalid_snapshot_files")
    if not 0 < len(files) <= _MAX_FILES:
        raise ReviewWorkflowError("invalid_snapshot_files")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_file in files:
        if not isinstance(raw_file, Mapping):
            raise ReviewWorkflowError("invalid_snapshot_files")
        document = dict(raw_file)
        path = _canonical_path(document.get("filePath"))
        if path in seen:
            raise ReviewWorkflowError("duplicate_snapshot_path")
        seen.add(path)
        document["filePath"] = path
        hunks = document.get("hunks", [])
        if not isinstance(hunks, list):
            raise ReviewWorkflowError("invalid_snapshot_files")
        for hunk in hunks:
            if not isinstance(hunk, dict) or not isinstance(hunk.get("lines", []), list):
                raise ReviewWorkflowError("invalid_snapshot_files")
            for line in hunk.get("lines", []):
                if not isinstance(line, dict) or line.get("kind") not in {
                    "add",
                    "delete",
                    "context",
                    "marker",
                }:
                    raise ReviewWorkflowError("invalid_snapshot_files")
                for key in ("oldLineno", "newLineno"):
                    number = line.get(key)
                    if number is not None and (type(number) is not int or number <= 0):
                        raise ReviewWorkflowError("invalid_snapshot_files")
        normalized.append(document)
    try:
        encoded = json.dumps(
            normalized,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ReviewWorkflowError("invalid_snapshot_files") from error
    if len(encoded.encode("utf-8")) > _MAX_FILES_BYTES:
        raise ReviewWorkflowError("snapshot_too_large")
    return encoded, tuple(normalized)


class ReviewWorkflowService:
    def __init__(self, database: str | Path) -> None:
        self.database = Path(database).expanduser().resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with SQLiteEventStore(self.database):
            pass

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.database), timeout=5, isolation_level="DEFERRED", check_same_thread=False
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create_snapshot(
        self,
        *,
        workspace: str | Path,
        checkout_path: str | Path,
        session_id: str,
        base_sha: str,
        head_sha: str,
        files: Sequence[Mapping[str, Any]],
        diff_text: str,
        working_tree_dirty: bool,
        run_id: str | None = None,
        snapshot_id: str | None = None,
    ) -> ReviewSnapshot:
        root = str(Path(workspace).expanduser().resolve())
        checkout = str(Path(checkout_path).expanduser().resolve())
        canonical_files, _ = _canonical_files(files)
        if not isinstance(diff_text, str) or len(diff_text.encode("utf-8")) > _MAX_SNAPSHOT_BYTES:
            raise ReviewWorkflowError("snapshot_too_large")
        if type(working_tree_dirty) is not bool:
            raise ReviewWorkflowError("invalid_working_tree_state")
        identifier = snapshot_id or str(uuid4())
        created_at = _now()
        with self._connection() as connection:
            session = connection.execute(
                "SELECT workspace FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if session is None or str(Path(cast(str, session["workspace"])).resolve()) != checkout:
                raise ReviewWorkflowError("invalid_session")
            if run_id is not None:
                run = connection.execute(
                    "SELECT workspace, session_id FROM agent_runs WHERE id = ?", (run_id,)
                ).fetchone()
                if run is None or cast(str, run["workspace"]) != root:
                    raise ReviewWorkflowError("invalid_run")
                if cast(str, run["session_id"]) != session_id:
                    raise ReviewWorkflowError("invalid_run_session")
            connection.execute(
                """
                INSERT INTO review_snapshots (
                    id, workspace, checkout_path, session_id, run_id, base_sha, head_sha,
                    diff_sha256, diff_text, files_json, working_tree_dirty, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    root,
                    checkout,
                    session_id,
                    run_id,
                    _sha(base_sha, "base_sha"),
                    _sha(head_sha, "head_sha"),
                    hashlib.sha256(diff_text.encode("utf-8")).hexdigest(),
                    diff_text,
                    canonical_files,
                    int(working_tree_dirty),
                    created_at,
                ),
            )
        snapshot = self.get_snapshot(identifier)
        assert snapshot is not None
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> ReviewSnapshot | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM review_snapshots WHERE id = ?", (snapshot_id,)
            ).fetchone()
        return self._snapshot_from_row(row) if row is not None else None

    def list_snapshots(self, workspace: str | Path, *, limit: int = 100) -> list[ReviewSnapshot]:
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ReviewWorkflowError("invalid_limit")
        root = str(Path(workspace).expanduser().resolve())
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM review_snapshots WHERE workspace = ?
                ORDER BY created_at DESC, id LIMIT ?
                """,
                (root, limit),
            ).fetchall()
        return [self._snapshot_from_row(row) for row in rows]

    def create_comment(
        self,
        snapshot_id: str,
        *,
        path: str,
        side: str,
        line: int,
        body: str,
        author: str = "user",
    ) -> ReviewComment:
        canonical_path = _canonical_path(path)
        if side not in {"old", "new"} or type(line) is not int or line <= 0:
            raise ReviewWorkflowError("invalid_comment_anchor")
        snapshot = self.get_snapshot(snapshot_id)
        if snapshot is None:
            raise ReviewWorkflowError("unknown_snapshot")
        line_key = "oldLineno" if side == "old" else "newLineno"
        anchored = any(
            file.get("filePath") == canonical_path
            and any(
                isinstance(hunk, dict)
                and any(
                    isinstance(item, dict) and item.get(line_key) == line
                    for item in hunk.get("lines", [])
                )
                for hunk in file.get("hunks", [])
            )
            for file in snapshot.files
        )
        if not anchored:
            raise ReviewWorkflowError("invalid_comment_anchor")
        identifier = str(uuid4())
        timestamp = _now()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO review_comments (
                    id, snapshot_id, path, side, line, body, state, author,
                    followup_run_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'open', ?, NULL, ?, ?)
                """,
                (
                    identifier,
                    snapshot_id,
                    canonical_path,
                    side,
                    line,
                    _text(body, "comment", limit=20_000),
                    _text(author, "author", limit=200),
                    timestamp,
                    timestamp,
                ),
            )
        comment = self.get_comment(identifier)
        assert comment is not None
        return comment

    def get_comment(self, comment_id: str) -> ReviewComment | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM review_comments WHERE id = ?", (comment_id,)
            ).fetchone()
        return self._comment_from_row(row) if row is not None else None

    def list_comments(
        self, snapshot_id: str, *, state: ReviewCommentState | None = None
    ) -> list[ReviewComment]:
        arguments: list[object] = [snapshot_id]
        condition = ""
        if state is not None:
            condition = " AND state = ?"
            arguments.append(state.value)
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM review_comments WHERE snapshot_id = ?"
                + condition
                + " ORDER BY path, line, created_at, id",
                arguments,
            ).fetchall()
        return [self._comment_from_row(row) for row in rows]

    def resolve_comment(self, comment_id: str) -> ReviewComment:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE review_comments SET state = 'resolved', updated_at = ?
                WHERE id = ? AND state = 'open'
                """,
                (_now(), comment_id),
            )
            if cursor.rowcount != 1:
                raise ReviewWorkflowError("unknown_or_resolved_comment")
        comment = self.get_comment(comment_id)
        assert comment is not None
        return comment

    def link_comment_followup(self, comment_id: str, run_id: str) -> ReviewComment:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT s.workspace AS snapshot_workspace, r.workspace AS run_workspace,
                    c.followup_run_id
                FROM review_comments c
                JOIN review_snapshots s ON s.id = c.snapshot_id
                LEFT JOIN agent_runs r ON r.id = ?
                WHERE c.id = ?
                """,
                (run_id, comment_id),
            ).fetchone()
            if row is None:
                raise ReviewWorkflowError("unknown_comment")
            if row["run_workspace"] is None or row["run_workspace"] != row["snapshot_workspace"]:
                raise ReviewWorkflowError("invalid_followup_run")
            if row["followup_run_id"] is not None:
                raise ReviewWorkflowError("followup_already_exists")
            connection.execute(
                "UPDATE review_comments SET followup_run_id = ?, updated_at = ? WHERE id = ?",
                (run_id, _now(), comment_id),
            )
        comment = self.get_comment(comment_id)
        assert comment is not None
        return comment

    def upsert_delivery(
        self,
        snapshot_id: str,
        *,
        pr_url: str | None,
        pr_number: int | None,
        state: DeliveryState,
        is_draft: bool,
        head_branch: str | None,
        base_branch: str | None,
        commit_sha: str | None = None,
        last_error: str | None = None,
    ) -> ReviewDelivery:
        if pr_url is not None:
            parsed = urlparse(pr_url)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ReviewWorkflowError("invalid_pull_request_url")
        if pr_number is not None and (type(pr_number) is not int or pr_number <= 0):
            raise ReviewWorkflowError("invalid_pull_request_number")
        if commit_sha is not None and (
            len(commit_sha) != 40
            or any(character not in "0123456789abcdef" for character in commit_sha.lower())
        ):
            raise ReviewWorkflowError("invalid_delivery_commit")
        timestamp = _now()
        with self._connection() as connection:
            if (
                connection.execute(
                    "SELECT 1 FROM review_snapshots WHERE id = ?", (snapshot_id,)
                ).fetchone()
                is None
            ):
                raise ReviewWorkflowError("unknown_snapshot")
            connection.execute(
                """
                INSERT INTO review_deliveries (
                    snapshot_id, provider, pr_url, pr_number, state, is_draft,
                    head_branch, base_branch, commit_sha, last_error, created_at, updated_at
                ) VALUES (?, 'github', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_id) DO UPDATE SET
                    pr_url = COALESCE(excluded.pr_url, review_deliveries.pr_url),
                    pr_number = COALESCE(excluded.pr_number, review_deliveries.pr_number),
                    state = excluded.state,
                    is_draft = excluded.is_draft,
                    head_branch = COALESCE(excluded.head_branch, review_deliveries.head_branch),
                    base_branch = COALESCE(excluded.base_branch, review_deliveries.base_branch),
                    commit_sha = COALESCE(excluded.commit_sha, review_deliveries.commit_sha),
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
                """,
                (
                    snapshot_id,
                    pr_url,
                    pr_number,
                    state.value,
                    int(is_draft),
                    head_branch,
                    base_branch,
                    commit_sha.lower() if commit_sha is not None else None,
                    last_error,
                    timestamp,
                    timestamp,
                ),
            )
        delivery = self.get_delivery(snapshot_id)
        assert delivery is not None
        return delivery

    def get_delivery(self, snapshot_id: str) -> ReviewDelivery | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM review_deliveries WHERE snapshot_id = ?", (snapshot_id,)
            ).fetchone()
        return self._delivery_from_row(row) if row is not None else None

    def replace_delivery_checks(
        self, snapshot_id: str, checks: Sequence[Mapping[str, Any]]
    ) -> list[DeliveryCheck]:
        if len(checks) > 500:
            raise ReviewWorkflowError("too_many_delivery_checks")
        timestamp = _now()
        normalized: list[tuple[str, str, str | None, str]] = []
        names: set[str] = set()
        for check in checks:
            name = _text(cast(str, check.get("name")), "check_name", limit=500)
            state = cast(str, check.get("state", "unknown"))
            if state not in _CHECK_STATES or name in names:
                raise ReviewWorkflowError("invalid_delivery_check")
            names.add(name)
            raw_url = check.get("url")
            url = raw_url if isinstance(raw_url, str) and raw_url else None
            if url is not None:
                parsed = urlparse(url)
                if parsed.scheme != "https" or not parsed.netloc:
                    raise ReviewWorkflowError("invalid_delivery_check")
            detail = _text(
                cast(str, check.get("detail", "")),
                "check_detail",
                limit=10_000,
                allow_empty=True,
            )
            normalized.append((name, state, url, detail))
        with self._connection() as connection:
            if (
                connection.execute(
                    "SELECT 1 FROM review_deliveries WHERE snapshot_id = ?", (snapshot_id,)
                ).fetchone()
                is None
            ):
                raise ReviewWorkflowError("unknown_delivery")
            connection.execute("DELETE FROM delivery_checks WHERE snapshot_id = ?", (snapshot_id,))
            connection.executemany(
                """
                INSERT INTO delivery_checks (snapshot_id, name, state, url, detail, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (snapshot_id, name, state, url, detail, timestamp)
                    for name, state, url, detail in normalized
                ],
            )
        return self.list_delivery_checks(snapshot_id)

    def list_delivery_checks(self, snapshot_id: str) -> list[DeliveryCheck]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM delivery_checks WHERE snapshot_id = ? ORDER BY name",
                (snapshot_id,),
            ).fetchall()
        return [self._check_from_row(row) for row in rows]

    @staticmethod
    def _snapshot_from_row(row: sqlite3.Row) -> ReviewSnapshot:
        files = cast(list[dict[str, Any]], json.loads(cast(str, row["files_json"])))
        return ReviewSnapshot(
            id=cast(str, row["id"]),
            workspace=cast(str, row["workspace"]),
            checkout_path=cast(str, row["checkout_path"]),
            session_id=cast(str, row["session_id"]),
            run_id=cast(str | None, row["run_id"]),
            base_sha=cast(str, row["base_sha"]),
            head_sha=cast(str, row["head_sha"]),
            diff_sha256=cast(str, row["diff_sha256"]),
            diff_text=cast(str, row["diff_text"]),
            files=tuple(files),
            working_tree_dirty=bool(row["working_tree_dirty"]),
            created_at=cast(str, row["created_at"]),
        )

    @staticmethod
    def _comment_from_row(row: sqlite3.Row) -> ReviewComment:
        return ReviewComment(
            id=cast(str, row["id"]),
            snapshot_id=cast(str, row["snapshot_id"]),
            path=cast(str, row["path"]),
            side=cast(str, row["side"]),
            line=cast(int, row["line"]),
            body=cast(str, row["body"]),
            state=ReviewCommentState(cast(str, row["state"])),
            author=cast(str, row["author"]),
            followup_run_id=cast(str | None, row["followup_run_id"]),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
        )

    @staticmethod
    def _delivery_from_row(row: sqlite3.Row) -> ReviewDelivery:
        return ReviewDelivery(
            snapshot_id=cast(str, row["snapshot_id"]),
            provider=cast(str, row["provider"]),
            pr_url=cast(str | None, row["pr_url"]),
            pr_number=cast(int | None, row["pr_number"]),
            state=DeliveryState(cast(str, row["state"])),
            is_draft=bool(row["is_draft"]),
            head_branch=cast(str | None, row["head_branch"]),
            base_branch=cast(str | None, row["base_branch"]),
            commit_sha=cast(str | None, row["commit_sha"]),
            last_error=cast(str | None, row["last_error"]),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
        )

    @staticmethod
    def _check_from_row(row: sqlite3.Row) -> DeliveryCheck:
        return DeliveryCheck(
            snapshot_id=cast(str, row["snapshot_id"]),
            name=cast(str, row["name"]),
            state=cast(str, row["state"]),
            url=cast(str | None, row["url"]),
            detail=cast(str, row["detail"]),
            updated_at=cast(str, row["updated_at"]),
        )


__all__ = ["ReviewWorkflowError", "ReviewWorkflowService"]
