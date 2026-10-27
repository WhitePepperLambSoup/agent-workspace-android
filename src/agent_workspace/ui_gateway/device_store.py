"""What device link 2 keeps between requests: transfers, phone jobs, messages, finished turns
and activity.

All of it lives in one SQLite file next to the paired phones. A phone's request ids and transfer
ids make its uploads, messages and hand-offs idempotent: the same id sent again returns what the
first request did. Files the desktop sends a phone are copied into an outbox when they are sent,
so a later change to the original does not change what the phone receives; a transfer the phone
has not collected expires after 7 days.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import threading
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

TRANSFER_DAYS = 7
JOB_WAIT_MINUTES = 10
CANCELLED_JOB_HOURS = 1
MESSAGES_KEPT = 20
ACTIVITY_KEPT = 100
TURNS_KEPT = 50
JOB_STATES = (
    "waiting",
    "accepted",
    "running",
    "succeeded",
    "failed",
    "rejected",
    "expired",
    "cancelled",
)
FINISHED_JOB_STATES = frozenset({"succeeded", "failed", "rejected", "expired", "cancelled"})
# What a phone may report from each state (POST /mobile/phone-jobs/{id}).
JOB_TRANSITIONS: dict[str, frozenset[str]] = {
    "waiting": frozenset({"accepted", "rejected"}),
    "accepted": frozenset({"running", "failed"}),
    "running": frozenset({"succeeded", "failed"}),
}
ACTIVITY_ACTIONS = frozenset(
    {
        "paired",
        "task_sent",
        "task_finished",
        "approval_decided",
        "turn_stopped",
        "file_received",
        "file_sent",
        "text_received",
        "text_sent",
        "conversation_received",
        "conversation_sent",
        "job_sent",
        "job_finished",
        "knowledge_synced",
    }
)


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds")


class DeviceStoreError(Exception):
    """A request the store refuses: a stable code and its HTTP status."""

    def __init__(self, code: str, status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass(frozen=True, slots=True)
class Transfer:
    transfer_id: str
    device_id: str
    kind: str  # file, conversation, text, link
    created_at: str
    expires_at: str
    name: str | None = None
    size: int | None = None
    sha256: str | None = None
    text: str | None = None
    title: str | None = None
    message_count: int | None = None
    source: str | None = None  # the conversation it came from, when there is one

    def inbox_item(self) -> dict[str, object]:
        item: dict[str, object] = {
            "transfer_id": self.transfer_id,
            "kind": self.kind,
            "created_at": self.created_at,
        }
        if self.kind == "file":
            item.update(name=self.name, size=self.size, sha256=self.sha256, **{"from": self.source})
        elif self.kind == "conversation":
            item.update(title=self.title, message_count=self.message_count)
        else:
            item["text"] = self.text
        return item


@dataclass(frozen=True, slots=True)
class PhoneJob:
    job_id: str
    device_id: str
    session_id: str
    title: str
    prompt: str
    operate_phone: bool
    state: str
    created_at: str
    expires_at: str
    updated_at: str
    result: str | None = None
    error: str | None = None

    def document(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "device_id": self.device_id,
            "session_id": self.session_id,
            "title": self.title,
            "prompt": self.prompt,
            "operate_phone": self.operate_phone,
            "state": self.state,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "result": self.result,
            "error": self.error,
        }


class DeviceStore:
    def __init__(self, directory: Path, *, clock: Callable[[], datetime] | None = None) -> None:
        self.directory = directory
        self.outbox = directory / "outbox"
        self.path = directory / "link.db"
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        directory.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS transfers (
                    transfer_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    name TEXT, size INTEGER, sha256 TEXT, text TEXT,
                    title TEXT, message_count INTEGER, source TEXT, content TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS received (
                    device_id TEXT NOT NULL,
                    transfer_id TEXT NOT NULL,
                    document TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (device_id, transfer_id)
                );
                CREATE TABLE IF NOT EXISTS phone_jobs (
                    job_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    operate_phone INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    result TEXT, error TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (device_id, request_id)
                );
                CREATE TABLE IF NOT EXISTS handoffs (
                    device_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    document TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (device_id, request_id)
                );
                CREATE TABLE IF NOT EXISTS activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS activity_device ON activity (device_id, id);
                CREATE TABLE IF NOT EXISTS turns (
                    turn_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    state TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    device_id TEXT,
                    finished_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        return connection

    def now(self) -> datetime:
        return self._clock()

    # ---- transfers: what this desktop sends a phone ------------------------------------------

    @staticmethod
    def _transfer(row: sqlite3.Row) -> Transfer:
        return Transfer(
            transfer_id=row["transfer_id"],
            device_id=row["device_id"],
            kind=row["kind"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            name=row["name"],
            size=row["size"],
            sha256=row["sha256"],
            text=row["text"],
            title=row["title"],
            message_count=row["message_count"],
            source=row["source"],
        )

    def add_transfer(
        self,
        device_id: str,
        kind: str,
        *,
        file: Path | None = None,
        name: str | None = None,
        sha256: str | None = None,
        text: str | None = None,
        title: str | None = None,
        conversation: dict[str, Any] | None = None,
        source: str | None = None,
    ) -> Transfer:
        transfer_id = uuid4().hex
        now = self.now()
        size: int | None = None
        if kind == "file":
            assert file is not None
            self.outbox.mkdir(parents=True, exist_ok=True)
            target = self.outbox / transfer_id
            shutil.copyfile(file, target)
            size = target.stat().st_size
        content = json.dumps(conversation, ensure_ascii=False) if conversation is not None else None
        message_count = len(conversation.get("messages", [])) if conversation is not None else None
        with self._lock, closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO transfers (transfer_id, device_id, kind, name, size, sha256, text, "
                "title, message_count, source, content, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    transfer_id, device_id, kind, name, size, sha256, text, title, message_count,
                    source, content, _iso(now), _iso(now + timedelta(days=TRANSFER_DAYS)),
                ),
            )  # fmt: skip
            row = db.execute(
                "SELECT * FROM transfers WHERE transfer_id = ?", (transfer_id,)
            ).fetchone()
        return self._transfer(row)

    def transfers(self, device_id: str, limit: int = 50) -> list[Transfer]:
        self._expire_transfers()
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM transfers WHERE device_id = ? ORDER BY created_at DESC LIMIT ?",
                (device_id, limit),
            ).fetchall()
        return [self._transfer(row) for row in rows]

    def transfer_content(self, device_id: str, transfer_id: str) -> tuple[Transfer, Any]:
        """A file transfer's outbox path, or a conversation transfer's document."""
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM transfers WHERE transfer_id = ? AND device_id = ?",
                (transfer_id, device_id),
            ).fetchone()
        if row is None:
            raise DeviceStoreError("unknown_transfer", 404)
        transfer = self._transfer(row)
        if transfer.kind == "file":
            path = self.outbox / transfer.transfer_id
            if not path.is_file():
                raise DeviceStoreError("unknown_transfer", 404)
            return transfer, path
        if transfer.kind == "conversation":
            return transfer, json.loads(row["content"] or "{}")
        return transfer, {"text": transfer.text}

    def finish_transfer(self, device_id: str, transfer_id: str) -> bool:
        with self._lock, closing(self._connect()) as db, db:
            deleted = db.execute(
                "DELETE FROM transfers WHERE transfer_id = ? AND device_id = ?",
                (transfer_id, device_id),
            ).rowcount
        (self.outbox / transfer_id).unlink(missing_ok=True)
        return deleted > 0

    def _expire_transfers(self) -> None:
        now = _iso(self.now())
        with self._lock, closing(self._connect()) as db, db:
            expired = [
                row["transfer_id"]
                for row in db.execute(
                    "SELECT transfer_id FROM transfers WHERE expires_at <= ?", (now,)
                )
            ]
            db.execute("DELETE FROM transfers WHERE expires_at <= ?", (now,))
        for transfer_id in expired:
            (self.outbox / transfer_id).unlink(missing_ok=True)

    # ---- idempotent requests from a phone ------------------------------------------------------

    def received(self, device_id: str, transfer_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT document FROM received WHERE device_id = ? AND transfer_id = ?",
                (device_id, transfer_id),
            ).fetchone()
        return json.loads(row["document"]) if row is not None else None

    def remember_received(self, device_id: str, transfer_id: str, document: dict[str, Any]) -> None:
        with self._lock, closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO received (device_id, transfer_id, document, created_at) "
                "VALUES (?, ?, ?, ?)",
                (device_id, transfer_id, json.dumps(document), _iso(self.now())),
            )

    def handoff(self, device_id: str, request_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT document FROM handoffs WHERE device_id = ? AND request_id = ?",
                (device_id, request_id),
            ).fetchone()
        return json.loads(row["document"]) if row is not None else None

    def remember_handoff(self, device_id: str, request_id: str, document: dict[str, Any]) -> None:
        with self._lock, closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO handoffs (device_id, request_id, document, created_at) "
                "VALUES (?, ?, ?, ?)",
                (device_id, request_id, json.dumps(document), _iso(self.now())),
            )

    # ---- text and links a phone sends -----------------------------------------------------------

    def add_message(self, device_id: str, request_id: str, kind: str, text: str) -> bool:
        """Keep a phone's text or link; False when this request id was received before."""
        with self._lock, closing(self._connect()) as db, db:
            if db.execute(
                "SELECT 1 FROM messages WHERE device_id = ? AND request_id = ?",
                (device_id, request_id),
            ).fetchone():
                return False
            db.execute(
                "INSERT INTO messages (id, device_id, request_id, kind, text, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (uuid4().hex, device_id, request_id, kind, text, _iso(self.now())),
            )
            db.execute(
                "DELETE FROM messages WHERE id NOT IN "
                "(SELECT id FROM messages ORDER BY created_at DESC LIMIT ?)",
                (MESSAGES_KEPT,),
            )
        return True

    def messages(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT id, device_id, kind, text, created_at FROM messages "
                "ORDER BY created_at DESC LIMIT ?",
                (MESSAGES_KEPT,),
            ).fetchall()
        return [dict(row) for row in rows]

    # ---- jobs this desktop asks a phone to do ---------------------------------------------------

    @staticmethod
    def _job(row: sqlite3.Row) -> PhoneJob:
        return PhoneJob(
            job_id=row["job_id"],
            device_id=row["device_id"],
            session_id=row["session_id"],
            title=row["title"],
            prompt=row["prompt"],
            operate_phone=bool(row["operate_phone"]),
            state=row["state"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            updated_at=row["updated_at"],
            result=row["result"],
            error=row["error"],
        )

    def add_job(
        self, device_id: str, session_id: str, title: str, prompt: str, operate_phone: bool
    ) -> PhoneJob:
        job_id = uuid4().hex
        now = self.now()
        with self._lock, closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO phone_jobs (job_id, device_id, session_id, title, prompt, "
                "operate_phone, state, created_at, expires_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'waiting', ?, ?, ?)",
                (
                    job_id, device_id, session_id, title, prompt, int(operate_phone), _iso(now),
                    _iso(now + timedelta(minutes=JOB_WAIT_MINUTES)), _iso(now),
                ),
            )  # fmt: skip
        job = self.job(job_id)
        assert job is not None
        return job

    def job(self, job_id: str) -> PhoneJob | None:
        self._expire_jobs()
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM phone_jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._job(row) if row is not None else None

    def _expire_jobs(self) -> None:
        now = _iso(self.now())
        with self._lock, closing(self._connect()) as db, db:
            db.execute(
                "UPDATE phone_jobs SET state = 'expired', updated_at = ? "
                "WHERE state = 'waiting' AND expires_at <= ?",
                (now, now),
            )

    def report_job(
        self,
        device_id: str,
        job_id: str,
        state: str,
        *,
        result: str | None = None,
        error: str | None = None,
    ) -> PhoneJob:
        """A phone's report on a job, checked against the allowed transitions."""
        job = self.job(job_id)
        if job is None or job.device_id != device_id:
            raise DeviceStoreError("unknown_job", 404)
        if job.state == "expired":
            raise DeviceStoreError("job_expired", 410)
        if state == job.state:
            return job  # the same report again
        if state not in JOB_TRANSITIONS.get(job.state, frozenset()):
            raise DeviceStoreError("invalid_transition", 409)
        with self._lock, closing(self._connect()) as db, db:
            db.execute(
                "UPDATE phone_jobs SET state = ?, result = ?, error = ?, updated_at = ? "
                "WHERE job_id = ?",
                (
                    state,
                    result if state == "succeeded" else job.result,
                    error if state == "failed" else job.error,
                    _iso(self.now()),
                    job_id,
                ),
            )
        refreshed = self.job(job_id)
        assert refreshed is not None
        return refreshed

    def cancel_job(self, job_id: str) -> PhoneJob | None:
        job = self.job(job_id)
        if job is None or job.state in FINISHED_JOB_STATES:
            return job
        with self._lock, closing(self._connect()) as db, db:
            db.execute(
                "UPDATE phone_jobs SET state = 'cancelled', updated_at = ? WHERE job_id = ?",
                (_iso(self.now()), job_id),
            )
        return self.job(job_id)

    def open_jobs(self, device_id: str, limit: int = 20) -> list[PhoneJob]:
        """A phone's jobs to act on: waiting, accepted or running, and those cancelled within
        the last hour (so the phone stops them)."""
        self._expire_jobs()
        cutoff = _iso(self.now() - timedelta(hours=CANCELLED_JOB_HOURS))
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM phone_jobs WHERE device_id = ? AND (state IN "
                "('waiting', 'accepted', 'running') OR (state = 'cancelled' AND updated_at >= ?)) "
                "ORDER BY created_at DESC LIMIT ?",
                (device_id, cutoff, limit),
            ).fetchall()
        return [self._job(row) for row in rows]

    # ---- turns that finished on this desktop ---------------------------------------------------

    def add_turn(
        self,
        turn_id: str,
        session_id: str,
        title: str,
        state: str,
        summary: str,
        device_id: str | None = None,
    ) -> None:
        """A finished turn, for phones to be told about; ``device_id`` is the phone that handed
        the task over, if one did (that phone is not told again)."""
        with self._lock, closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO turns (turn_id, session_id, title, state, summary, "
                "device_id, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    turn_id, session_id, title[:200], state, summary[:300], device_id,
                    _iso(self.now()),
                ),
            )  # fmt: skip
            db.execute(
                "DELETE FROM turns WHERE turn_id NOT IN "
                "(SELECT turn_id FROM turns ORDER BY finished_at DESC, rowid DESC LIMIT ?)",
                (TURNS_KEPT,),
            )

    def turns(self, device_id: str, limit: int = 20) -> list[dict[str, object]]:
        """The latest finished turns, leaving out the tasks this phone handed over."""
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM turns WHERE device_id IS NULL OR device_id != ? "
                "ORDER BY finished_at DESC, rowid DESC LIMIT ?",
                (device_id, limit),
            ).fetchall()
        return [
            {
                "turn_id": row["turn_id"],
                "session_id": row["session_id"],
                "title": row["title"],
                "state": row["state"],
                "finished_at": row["finished_at"],
                "summary": row["summary"],
            }
            for row in rows
        ]

    # ---- activity --------------------------------------------------------------------------------

    def log(self, device_id: str, action: str, detail: str) -> None:
        if action not in ACTIVITY_ACTIONS:
            raise ValueError(f"unknown activity: {action}")
        with self._lock, closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO activity (device_id, at, action, detail) VALUES (?, ?, ?, ?)",
                (device_id, _iso(self.now()), action, " ".join(detail.split())[:200]),
            )
            db.execute(
                "DELETE FROM activity WHERE device_id = ? AND id NOT IN (SELECT id FROM activity "
                "WHERE device_id = ? ORDER BY id DESC LIMIT ?)",
                (device_id, device_id, ACTIVITY_KEPT),
            )

    def activity(self, device_id: str) -> list[dict[str, str]]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT at, action, detail FROM activity WHERE device_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (device_id, ACTIVITY_KEPT),
            ).fetchall()
        return [{"at": row["at"], "action": row["action"], "detail": row["detail"]} for row in rows]

    def forget_device(self, device_id: str) -> None:
        """Everything kept for a phone that was removed."""
        with self._lock, closing(self._connect()) as db, db:
            files = [
                row["transfer_id"]
                for row in db.execute(
                    "SELECT transfer_id FROM transfers WHERE device_id = ?", (device_id,)
                )
            ]
            for table in ("transfers", "received", "handoffs", "activity"):
                db.execute(f"DELETE FROM {table} WHERE device_id = ?", (device_id,))
            db.execute(
                "UPDATE phone_jobs SET state = 'cancelled' WHERE device_id = ? AND state IN "
                "('waiting', 'accepted', 'running')",
                (device_id,),
            )
        for transfer_id in files:
            (self.outbox / transfer_id).unlink(missing_ok=True)


__all__ = [
    "ACTIVITY_ACTIONS",
    "FINISHED_JOB_STATES",
    "JOB_STATES",
    "DeviceStore",
    "DeviceStoreError",
    "PhoneJob",
    "Transfer",
]
