"""Device link 2 on the phone (docs/DEVICE_LINK_V2.md): what a paired desktop sends this phone, and
what the user does with that desktop from the phone.

A loop reads each desktop's inbox every 20 seconds while the engine runs: actions waiting for an
approval, finished scheduled runs and turns, files, text and conversations sent to this phone, and
tasks the desktop asks this phone to do. Each is shown once (a notification) and remembered by its
id. The rest are the user's own requests from the Device connections pages: approve, stop, browse
and download files, send files and text, continue a conversation on the computer, wake it, sync
knowledge bases, decide on the desktop's requests.

Nothing the desktop sends runs here without the user: a request to do something on this phone waits
for the user's decision unless they chose to accept that desktop's requests by themselves, and even
then each step follows this phone's approval rules.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import re
import socket
import sqlite3
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from mobile_connections import MobileConnections, RemoteHTTPError, connection_database, unavailable_reason
from mobile_delivery import MobileOutbox, acknowledgements, refusal_reason, refused

MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_TEXT_BYTES = 64 * 1024
MAX_RELAY_MESSAGES = 200
MAX_RELAY_BYTES = 1024 * 1024
MAX_RELAY_FILES = 20
MAX_JOB_RESULT = 64 * 1024
RECEIVED_FOLDER = "来自电脑"
# Where pages stage files picked or shared for a computer (WebUiActivity, under the app's files).
STAGING_FOLDER = "to-computer"
_POLL_SECONDS = 20.0
_BACKOFF_SECONDS = (60.0, 60.0, 300.0)
_RUNTIME_SECONDS = 600.0
_KNOWLEDGE_SECONDS = 6 * 3600.0
_WAKE_SECONDS = 120.0
_ASK_SECONDS = 1800.0
_ASK_POLL_SECONDS = 5.0
_TRANSFER_ATTEMPTS = 5
_JOB_SETTINGS = ("ask", "auto", "off")
_TERMINAL = {"completed", "failed", "cancelled"}
_REVIEW_REFUSALS = {
    "unknown_path": "that file has no changes on the computer any more",
    "unknown_review": "that review is no longer on the computer",
    "unknown_comment": "that comment is no longer on the computer",
    "invalid_session": "the conversation no longer exists on the computer",
    "invalid_comment": "write a comment of at most 4,000 characters",
    "invalid_comment_anchor": "that line is not in this review's changes",
    "no_changes": "there are no uncommitted changes on the computer",
    "review_too_large": "the changes are too large to review on the phone; review them on the computer",
}
_MAC = re.compile(r"[0-9a-f]{2}([:-]?)(?:[0-9a-f]{2}\1){4}[0-9a-f]{2}")
_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_STAGED = re.compile(r"[A-Za-z0-9._-]{1,200}")

_current: MobileLink | None = None


def current() -> MobileLink | None:
    """The running link (tools reach it here: android_adapter.computer_tools)."""
    return _current


def _checked_id(value: object, what: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"invalid {what}")
    return value


def safe_filename(value: object) -> str:
    """A received or uploaded file's name without folders, control characters or a leading dot."""
    name = str(value or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ord(ch) >= 32 and ch not in '<>:"|?*').strip().lstrip(".")
    return name[:200] or "file"


def unique_path(folder: Path, name: str) -> Path:
    """``name`` in ``folder``, or "name (2).ext" and so on when it is taken."""
    target = folder / name
    stem, dot, suffix = name.rpartition(".")
    if not dot:
        stem, suffix = name, ""
    number = 2
    while target.exists():
        target = folder / (f"{stem} ({number}).{suffix}" if suffix else f"{stem} ({number})")
        number += 1
    return target


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _udp_socket() -> socket.socket:
    return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def magic_packet(mac: str) -> bytes:
    """Wake-on-LAN: six 0xFF bytes, then the MAC address sixteen times."""
    text = mac.strip().lower()
    if not _MAC.fullmatch(text):
        raise ValueError("invalid MAC address")
    raw = bytes.fromhex(re.sub(r"[:-]", "", text))
    return b"\xff" * 6 + raw * 16


def _message_text(event: Any) -> tuple[str, str] | None:
    data = event.data if isinstance(event.data, dict) else {}
    role, content = data.get("role"), data.get("content")
    if event.type != "message.created" or role not in {"user", "assistant"} or not isinstance(content, str):
        return None
    content = content.strip()
    return (role, content) if content else None


class MobileLink:
    def __init__(
        self,
        path: Path,
        connections: MobileConnections,
        outbox: MobileOutbox,
        *,
        workspace: Path,
        data: Path,
        runtime: Any = None,
        controller: Any = None,
        notify: Callable[[dict[str, Any]], None] | None = None,
        knowledge: Callable[[], Any] | None = None,
        discover: Callable[[float], list[dict[str, Any]]] | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self.path = path
        self.connections = connections
        self.outbox = outbox
        self.workspace = Path(workspace)
        self.data = Path(data)
        self.runtime = runtime
        self.controller = controller
        self.notify = notify or (lambda _notice: None)
        self.knowledge = knowledge
        self.discover = discover
        self.clock = clock
        self._next: dict[str, float] = {}
        self._failures: dict[str, int] = {}
        self._transfer_attempts: dict[tuple[str, str], int] = {}
        self._waiters: dict[str, asyncio.Task] = {}
        self._waking: dict[str, float] = {}
        self._told_jobs: set[str] = set()
        self._operations: dict[str, dict[str, Any]] = {}
        self._tasks: set[asyncio.Task] = set()
        # One per computer: a read of one never waits for another's.
        self._locks: dict[str, asyncio.Lock] = {}
        with connection_database(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS link_seen (host_id TEXT NOT NULL, kind TEXT NOT NULL, "
                "item_id TEXT NOT NULL, at REAL NOT NULL, PRIMARY KEY (host_id, kind, item_id))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS link_activity (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "host_id TEXT NOT NULL, at REAL NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS link_settings (host_id TEXT PRIMARY KEY, "
                "jobs TEXT NOT NULL DEFAULT 'ask', kb_pairs TEXT NOT NULL DEFAULT '[]', kb_synced_at REAL, "
                "kb_result TEXT, primed INTEGER NOT NULL DEFAULT 0, job_session TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS link_state (host_id TEXT PRIMARY KEY, inbox TEXT, "
                "polled_at REAL, error TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS link_received (host_id TEXT NOT NULL, transfer_id TEXT NOT NULL, "
                "kind TEXT NOT NULL, name TEXT, path TEXT, text TEXT, session_id TEXT, state TEXT NOT NULL, "
                "error TEXT, at REAL NOT NULL, sha256 TEXT, PRIMARY KEY (host_id, transfer_id))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS link_jobs (host_id TEXT NOT NULL, job_id TEXT NOT NULL, "
                "title TEXT NOT NULL, prompt TEXT NOT NULL, operate_phone INTEGER NOT NULL, state TEXT NOT NULL, "
                "task_id TEXT, session_id TEXT, result TEXT, error TEXT, reported TEXT, "
                "created_at REAL NOT NULL, updated_at REAL NOT NULL, PRIMARY KEY (host_id, job_id))"
            )

    # ---- small records ---------------------------------------------------------------------------

    def _db(self) -> sqlite3.Connection:
        return connection_database(self.path)

    def activity(self, host_id: str, action: str, detail: str) -> None:
        with self._db() as db:
            db.execute(
                "INSERT INTO link_activity (host_id, at, action, detail) VALUES (?,?,?,?)",
                (host_id, self.clock(), action, " ".join(str(detail).split())[:200]),
            )
            db.execute(
                "DELETE FROM link_activity WHERE host_id=? AND id NOT IN "
                "(SELECT id FROM link_activity WHERE host_id=? ORDER BY id DESC LIMIT 300)",
                (host_id, host_id),
            )

    def _seen(self, host_id: str, kind: str) -> set[str]:
        with self._db() as db:
            rows = db.execute(
                "SELECT item_id FROM link_seen WHERE host_id=? AND kind=?", (host_id, kind)
            ).fetchall()
        return {row["item_id"] for row in rows}

    def _mark(self, host_id: str, kind: str, item_ids: list[str]) -> None:
        if not item_ids:
            return
        with self._db() as db:
            db.executemany(
                "INSERT OR IGNORE INTO link_seen (host_id, kind, item_id, at) VALUES (?,?,?,?)",
                [(host_id, kind, item_id, self.clock()) for item_id in item_ids],
            )
            # Ids are kept for a while after they leave the desktop's lists, then dropped.
            db.execute(
                "DELETE FROM link_seen WHERE host_id=? AND kind=? AND item_id NOT IN "
                "(SELECT item_id FROM link_seen WHERE host_id=? AND kind=? ORDER BY at DESC LIMIT 500)",
                (host_id, kind, host_id, kind),
            )

    def _unmark(self, host_id: str, kind: str, item_ids: list[str]) -> None:
        with self._db() as db:
            db.executemany(
                "DELETE FROM link_seen WHERE host_id=? AND kind=? AND item_id=?",
                [(host_id, kind, item_id) for item_id in item_ids],
            )

    def settings(self, host_id: str) -> dict[str, Any]:
        with self._db() as db:
            row = db.execute("SELECT * FROM link_settings WHERE host_id=?", (host_id,)).fetchone()
        if row is None:
            return {"jobs": "ask", "kb_pairs": [], "kb_synced_at": None, "kb_result": None, "primed": False,
                    "job_session": None}
        try:
            pairs = json.loads(row["kb_pairs"] or "[]")
        except ValueError:
            pairs = []
        try:
            result = json.loads(row["kb_result"]) if row["kb_result"] else None
        except ValueError:
            result = None
        return {
            "jobs": row["jobs"] if row["jobs"] in _JOB_SETTINGS else "ask",
            "kb_pairs": pairs if isinstance(pairs, list) else [],
            "kb_synced_at": row["kb_synced_at"],
            "kb_result": result,
            "primed": bool(row["primed"]),
            "job_session": row["job_session"],
        }

    def _set(self, host_id: str, **values: Any) -> None:
        with self._db() as db:
            db.execute("INSERT OR IGNORE INTO link_settings (host_id) VALUES (?)", (host_id,))
            for key, value in values.items():
                db.execute(f"UPDATE link_settings SET {key}=? WHERE host_id=?", (value, host_id))

    def forget(self, host_id: str) -> None:
        """A removed computer: what was kept about it goes too (received files stay in the workspace),
        and so do its notifications that wait for an answer or open its page."""
        tags = [f"approval:{item_id}" for item_id in self._seen(host_id, "approval")]
        tags += [f"job:{job['job_id']}" for job in self.jobs(host_id) if job["state"] == "waiting"]
        tags += [f"{action}:{host_id}" for action in ("turn", "run", "online", "moved")]
        for tag in tags:
            with contextlib.suppress(Exception):
                self.notify({"action": "cancel", "tag": tag})
        with self._db() as db:
            for table in ("link_seen", "link_activity", "link_settings", "link_state", "link_received", "link_jobs"):
                db.execute(f"DELETE FROM {table} WHERE host_id=?", (host_id,))
        self._next.pop(host_id, None)
        self._failures.pop(host_id, None)

    def _host(self, host_id: object) -> dict[str, Any]:
        host = self.connections.get(_checked_id(host_id, "computer"))
        if host["api"] != "mobile":
            raise ValueError("this device does not support the phone connection")
        return host

    @staticmethod
    def _needs(host: dict[str, Any], feature: str) -> None:
        if feature not in host["features"]:
            raise ValueError("the computer's app is older and cannot do this yet; update it there")

    # ---- the loop ---------------------------------------------------------------------------------

    async def run(self) -> None:
        """Reads each computer on its own: one that is away (trying its addresses can take half a
        minute) must not hold up the others, nor a newly paired one."""
        global _current
        _current = self
        polling: dict[str, asyncio.Task] = {}
        while True:
            try:
                hosts = [host for host in self.connections.list() if host["api"] == "mobile"]
            except sqlite3.Error:
                hosts = []
            for host in hosts:
                host_id = host["host_id"]
                running = polling.get(host_id)
                if (running is not None and not running.done()) or self.clock() < self._next.get(host_id, 0.0):
                    continue
                polling[host_id] = asyncio.get_running_loop().create_task(self._guarded_poll(host_id),
                                                                          name=f"link-poll-{host_id}")
            for host_id in [key for key, task in polling.items() if task.done()]:
                polling.pop(host_id, None)
            await asyncio.sleep(2)

    async def _guarded_poll(self, host_id: str) -> None:
        """One read that cannot stop the loop: an unexpected error or a hung request waits and is tried again."""
        try:
            await asyncio.wait_for(self.poll(host_id), timeout=180)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            reason = f"{type(error).__name__}: {error}"[:300]
            with contextlib.suppress(sqlite3.Error), self._db() as db:
                db.execute(
                    "INSERT INTO link_state (host_id, error) VALUES (?,?) "
                    "ON CONFLICT(host_id) DO UPDATE SET error=excluded.error",
                    (host_id, reason),
                )
            self._schedule(host_id, False)

    def _schedule(self, host_id: str, ok: bool) -> None:
        if ok:
            self._failures[host_id] = 0
            self._next[host_id] = self.clock() + _POLL_SECONDS
            return
        count = self._failures.get(host_id, 0)
        self._failures[host_id] = count + 1
        self._next[host_id] = self.clock() + _BACKOFF_SECONDS[min(count, len(_BACKOFF_SECONDS) - 1)]

    async def poll(self, host_id: str) -> dict[str, Any]:
        """Read one desktop's inbox and act on what is new. Never raises for a desktop that is away."""
        async with self._locks.setdefault(host_id, asyncio.Lock()):
            try:
                host = self._host(host_id)
                if host.get("runtime_at") is None or self.clock() - float(host["runtime_at"] or 0) > _RUNTIME_SECONDS:
                    host = await self.connections.refresh_runtime(host_id)
                    if "device" in host["features"] and host_id not in self._told_jobs:
                        # The desktop offers its phone_task tool only for phones that take requests.
                        choice = self.settings(host_id)["jobs"]
                        await self.connections.request(host_id, "POST", "/mobile/device", {"accepts_jobs": choice != "off"})
                        self._told_jobs.add(host_id)
                inbox: dict[str, Any] = {}
                if "inbox" in host["features"]:
                    _, inbox = await self.connections.request(host_id, "GET", "/mobile/inbox")
                await self._handle(host, inbox)
                await self._drive_jobs(host)
                await self._knowledge_due(host)
            except (httpx.HTTPError, ValueError, KeyError, sqlite3.Error) as error:
                if isinstance(error, KeyError):
                    return {"ok": False}
                # A computer that removed this phone answers 401 (RemoteHTTPError says so).
                reason = unavailable_reason(error) if isinstance(error, httpx.HTTPError) else str(error)
                with self._db() as db:
                    db.execute(
                        "INSERT INTO link_state (host_id, error) VALUES (?,?) "
                        "ON CONFLICT(host_id) DO UPDATE SET error=excluded.error",
                        (host_id, reason[:300]),
                    )
                self._schedule(host_id, False)
                if isinstance(error, httpx.HTTPError):
                    await self._refind(host_id)
                return {"ok": False, "error": reason}
            with self._db() as db:
                db.execute(
                    "INSERT INTO link_state (host_id, inbox, polled_at, error) VALUES (?,?,?,NULL) "
                    "ON CONFLICT(host_id) DO UPDATE SET inbox=excluded.inbox, polled_at=excluded.polled_at, "
                    "error=NULL",
                    (host_id, json.dumps(inbox, ensure_ascii=False)[:2_000_000], self.clock()),
                )
            self._schedule(host_id, True)
            return {"ok": True}

    async def _handle(self, host: dict[str, Any], inbox: dict[str, Any]) -> None:
        host_id, name = host["host_id"], host["name"]
        primed = self.settings(host_id)["primed"]

        approvals = [item for item in inbox.get("approvals") or [] if isinstance(item, dict)
                     and isinstance(item.get("request_id"), str)]
        current = {item["request_id"] for item in approvals}
        seen = self._seen(host_id, "approval")
        for item in approvals:
            if item["request_id"] not in seen:
                self.notify({"action": "approval", "id": item["request_id"], "host": name, "host_id": host_id,
                             "tool": str(item.get("tool") or "")[:80], "text": str(item.get("summary") or "")[:300]})
        self._mark(host_id, "approval", sorted(current - seen))
        gone = sorted(seen - current)
        for request_id in gone:
            self.notify({"action": "cancel", "tag": f"approval:{request_id}"})
        self._unmark(host_id, "approval", gone)

        for kind, key, entries in (("run", "run_id", inbox.get("runs")), ("turn", "turn_id", inbox.get("turns"))):
            items = [item for item in entries or [] if isinstance(item, dict) and isinstance(item.get(key), str)]
            seen = self._seen(host_id, kind)
            fresh = [item for item in items if item[key] not in seen]
            # One notification per computer replaces the last: in the order they ended, so the one left
            # showing is the latest (the computer's list follows when they started).
            ended = sorted(fresh, key=lambda item: str(item.get("finished_at") or item.get("updated_at") or ""))
            for item in ended if primed else []:
                finished = item.get("state") == "succeeded"
                text = item.get("result") if kind == "run" else item.get("summary")
                if not finished:
                    text = item.get("error") or item.get("summary") or text
                self.notify({"action": kind, "id": item[key], "host": name, "host_id": host_id,
                             "title": str(item.get("title") or "")[:120], "finished": finished,
                             "text": str(text or "")[:300], "state": str(item.get("state") or "")})
            self._mark(host_id, kind, [item[key] for item in fresh])

        for item in inbox.get("transfers") or []:
            if isinstance(item, dict) and isinstance(item.get("transfer_id"), str):
                await self._receive(host, item)

        await self._jobs(host, [item for item in inbox.get("phone_jobs") or [] if isinstance(item, dict)])
        if not primed:
            # Results already there when the computer was paired are not news.
            self._set(host_id, primed=1)

    # ---- received transfers ----------------------------------------------------------------------

    def _received(self, host_id: str, transfer_id: str) -> sqlite3.Row | None:
        with self._db() as db:
            return db.execute(
                "SELECT * FROM link_received WHERE host_id=? AND transfer_id=?", (host_id, transfer_id)
            ).fetchone()

    def _record(self, host_id: str, transfer_id: str, kind: str, **values: Any) -> None:
        with self._db() as db:
            db.execute(
                "INSERT INTO link_received (host_id, transfer_id, kind, name, path, text, session_id, state, error, at, "
                "sha256) VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(host_id, transfer_id) DO UPDATE SET "
                "name=excluded.name, path=excluded.path, text=excluded.text, session_id=excluded.session_id, "
                "state=excluded.state, error=excluded.error, at=excluded.at, sha256=excluded.sha256",
                (host_id, transfer_id, kind, values.get("name"), values.get("path"), values.get("text"),
                 values.get("session_id"), values.get("state", "received"), values.get("error"), self.clock(),
                 values.get("sha256")),
            )

    async def _receive(self, host: dict[str, Any], item: dict[str, Any]) -> None:
        host_id, name = host["host_id"], host["name"]
        transfer_id = item["transfer_id"]
        if not _ID.fullmatch(transfer_id):
            return
        if self._received(host_id, transfer_id) is not None:
            # Kept already: tell the desktop again in case the first "done" was lost.
            with contextlib.suppress(httpx.HTTPError, ValueError):
                await self.connections.request(host_id, "POST", f"/mobile/transfers/{quote(transfer_id, safe='')}/done", {})
            return
        kind = item.get("kind")
        key = (host_id, transfer_id)
        try:
            if kind == "file":
                received, sha256 = await self._receive_file(host_id, transfer_id, item)
                self._record(host_id, transfer_id, kind, name=received.name,
                             path=received.relative_to(self.workspace).as_posix(), sha256=sha256)
                self.activity(host_id, "file_received", received.name)
                self.notify({"action": "file", "id": transfer_id, "host": name, "host_id": host_id,
                             "name": received.name, "path": received.relative_to(self.workspace).as_posix()})
            elif kind in {"text", "link"}:
                text = item.get("text")
                if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > MAX_TEXT_BYTES:
                    raise ValueError("the text from the computer is empty or too long")
                self._record(host_id, transfer_id, kind, text=text)
                self.activity(host_id, "text_received", text[:80])
                self.notify({"action": "text", "id": transfer_id, "host": name, "host_id": host_id,
                             "text": text[:2000], "link": kind == "link"})
            elif kind == "conversation":
                _, document = await self.connections.request(
                    host_id, "GET", f"/mobile/transfers/{quote(transfer_id, safe='')}/content",
                    max_bytes=MAX_RELAY_BYTES * 2,
                )
                session_id, title = self.import_conversation(name, document)
                self._record(host_id, transfer_id, kind, name=title, session_id=session_id)
                self.activity(host_id, "conversation_received", title)
                self.notify({"action": "conversation", "id": transfer_id, "host": name, "host_id": host_id,
                             "title": title, "session_id": session_id})
            else:
                self._record(host_id, transfer_id, str(kind or "unknown")[:20], state="failed",
                             error="this app version does not know this kind of transfer")
        except (httpx.HTTPError, ValueError, OSError) as error:
            attempts = self._transfer_attempts.get(key, 0) + 1
            self._transfer_attempts[key] = attempts
            if attempts < _TRANSFER_ATTEMPTS:
                return  # tried again at the next poll
            reason = unavailable_reason(error) if isinstance(error, httpx.HTTPError) else str(error)
            self._record(host_id, transfer_id, str(kind or "file")[:20], name=str(item.get("name") or "")[:200],
                         state="failed", error=reason[:300])
            return
        self._transfer_attempts.pop(key, None)
        with contextlib.suppress(httpx.HTTPError, ValueError):
            await self.connections.request(host_id, "POST", f"/mobile/transfers/{quote(transfer_id, safe='')}/done", {})

    async def _receive_file(self, host_id: str, transfer_id: str, item: dict[str, Any]) -> tuple[Path, str]:
        size = item.get("size")
        if isinstance(size, int) and size > MAX_FILE_BYTES:
            raise ValueError("the file is larger than 100 MiB")
        folder = self.workspace / RECEIVED_FOLDER
        folder.mkdir(parents=True, exist_ok=True)
        target = unique_path(folder, safe_filename(item.get("name")))
        received = await self.connections.download(
            host_id, f"/mobile/transfers/{quote(transfer_id, safe='')}/content", target, max_bytes=MAX_FILE_BYTES
        )
        expected = item.get("sha256")
        if isinstance(expected, str) and expected and expected.lower() != received["sha256"]:
            target.unlink(missing_ok=True)
            raise ValueError("the file arrived damaged; it will be fetched again")
        return target, received["sha256"]

    def retry_transfer(self, host_id: str, transfer_id: str) -> dict[str, Any]:
        """A transfer that failed five times: forget it, so the next poll fetches it again."""
        with self._db() as db:
            db.execute(
                "DELETE FROM link_received WHERE host_id=? AND transfer_id=? AND state='failed'",
                (_checked_id(host_id, "computer"), _checked_id(transfer_id, "transfer")),
            )
        self._transfer_attempts.pop((host_id, transfer_id), None)
        self._next[host_id] = 0.0
        return {"ok": True}

    # ---- local conversations ---------------------------------------------------------------------

    def _new_session(self, title: str) -> str:
        from agent_workspace.core.models import Autonomy

        service = self.runtime.service
        workspace = getattr(service, "_execution_workspace", None) or self.workspace
        autonomy = getattr(service, "_execution_autonomy", None) or Autonomy.WORKSPACE
        return service.create_session(workspace, autonomy=autonomy, title=title[:120]).id

    def _session_exists(self, session_id: str | None) -> bool:
        if not session_id:
            return False
        try:
            self.runtime.service.get_session(session_id)
        except (KeyError, ValueError):
            return False
        return True

    def import_conversation(self, host_name: str, document: dict[str, Any]) -> tuple[str, str]:
        """A conversation the computer sent ("continue on the phone"): a new conversation here with its
        messages as earlier history."""
        from agent_workspace.core.events import Event

        messages = document.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError("the conversation from the computer has no messages")
        title = " ".join(str(document.get("title") or "").split())[:100] or f"{host_name}"
        kept: list[tuple[str, str]] = []
        total = 0
        for item in messages[-MAX_RELAY_MESSAGES:]:
            if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
                continue
            content = item.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            total += len(content.encode("utf-8"))
            if total > MAX_RELAY_BYTES:
                break
            kept.append((item["role"], content))
        if not kept:
            raise ValueError("the conversation from the computer has no messages")
        session_id = self._new_session(title)
        for role, content in kept:
            self.runtime.store.append(Event(
                session_id=session_id,
                type="message.created",
                data={"role": role, "content": content, "reasoning": "", "tool_calls": [], "trust": "trusted",
                      "sensitivity": "normal", "provider_metadata": {}, "relayed_from": "computer"},
            ))
        return session_id, title

    def _conversation_messages(self, session_id: str) -> tuple[str, list[dict[str, str]], list[dict[str, str]]]:
        """A conversation's title, its text messages (the latest that fit) and its pictures."""
        session = self.runtime.service.get_session(session_id)
        events = self.runtime.store.list_events(session_id)
        messages: list[dict[str, str]] = []
        for event in events:
            found = _message_text(event)
            if found:
                messages.append({"role": found[0], "content": found[1]})
        messages = messages[-MAX_RELAY_MESSAGES:]
        while messages and len(json.dumps(messages, ensure_ascii=False).encode("utf-8")) > MAX_RELAY_BYTES - 4096:
            messages.pop(0)
        images: list[dict[str, str]] = []
        for event in events:
            if event.type != "mobile.task.created":
                continue
            for ref in event.data.get("image_refs") or []:
                if isinstance(ref, dict) and isinstance(ref.get("path"), str) and ref not in images:
                    images.append({"path": ref["path"], "sha256": str(ref.get("sha256") or "")})
        return str(getattr(session, "title", "") or ""), messages, images[:MAX_RELAY_FILES]

    # ---- jobs the desktop asks this phone to do --------------------------------------------------

    def jobs(self, host_id: str) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute(
                "SELECT * FROM link_jobs WHERE host_id=? ORDER BY created_at DESC LIMIT 30", (host_id,)
            ).fetchall()
        return [{**dict(row), "operate_phone": bool(row["operate_phone"])} for row in rows]

    def _job(self, host_id: str, job_id: str) -> sqlite3.Row | None:
        with self._db() as db:
            return db.execute("SELECT * FROM link_jobs WHERE host_id=? AND job_id=?", (host_id, job_id)).fetchone()

    def _job_state(self, host_id: str, job_id: str, state: str, **values: Any) -> None:
        assignments = ", ".join(f"{key}=?" for key in values)
        with self._db() as db:
            db.execute(
                f"UPDATE link_jobs SET state=?, updated_at=?{', ' + assignments if assignments else ''} "
                "WHERE host_id=? AND job_id=?",
                (state, self.clock(), *values.values(), host_id, job_id),
            )

    async def _report(self, host_id: str, job_id: str, state: str, **extra: Any) -> bool:
        """Tell the desktop where its request stands; False when it says the request is gone."""
        try:
            await self.connections.request(
                host_id, "POST", f"/mobile/phone-jobs/{quote(job_id, safe='')}", {"state": state, **extra}
            )
        except RemoteHTTPError as error:
            if error.status_code in {404, 409, 410}:
                return False
            raise
        with self._db() as db:
            db.execute("UPDATE link_jobs SET reported=? WHERE host_id=? AND job_id=?", (state, host_id, job_id))
        return True

    async def _jobs(self, host: dict[str, Any], items: list[dict[str, Any]]) -> None:
        host_id, name = host["host_id"], host["name"]
        listed: set[str] = set()
        for item in items:
            job_id, state = item.get("job_id"), item.get("state")
            if not isinstance(job_id, str) or not _ID.fullmatch(job_id):
                continue
            listed.add(job_id)
            local = self._job(host_id, job_id)
            if state == "waiting" and local is None:
                prompt = item.get("prompt")
                if not isinstance(prompt, str) or not prompt.strip():
                    continue
                now = self.clock()
                with self._db() as db:
                    db.execute(
                        "INSERT INTO link_jobs (host_id, job_id, title, prompt, operate_phone, state, created_at, "
                        "updated_at) VALUES (?,?,?,?,?,'waiting',?,?)",
                        (host_id, job_id, " ".join(str(item.get("title") or "").split())[:120], prompt[:20000],
                         int(item.get("operate_phone") is True), now, now),
                    )
                self.activity(host_id, "job_received", prompt[:80])
                choice = self.settings(host_id)["jobs"]
                if choice == "off":
                    await self.decide_job(host_id, job_id, "reject")
                elif choice == "auto":
                    await self.decide_job(host_id, job_id, "accept")
                else:
                    self.notify({"action": "job", "id": job_id, "host": name, "host_id": host_id,
                                 "title": str(item.get("title") or "")[:120], "text": prompt[:300],
                                 "operate_phone": item.get("operate_phone") is True})
            elif state == "cancelled" and local is not None and local["state"] in {"waiting", "accepted", "running"}:
                if local["task_id"] and self.controller is not None:
                    with contextlib.suppress(Exception):
                        await self.controller.cancel(local["task_id"])
                self._job_state(host_id, job_id, "cancelled")
                self.notify({"action": "cancel", "tag": f"job:{job_id}"})
                self.activity(host_id, "job_cancelled", local["prompt"][:80])
        # Requests that left the list while still waiting for the user: expired on the desktop.
        for job in self.jobs(host_id):
            if job["state"] == "waiting" and job["job_id"] not in listed:
                self._job_state(host_id, job["job_id"], "expired")
                self.notify({"action": "cancel", "tag": f"job:{job['job_id']}"})

    async def decide_job(self, host_id: str, job_id: str, decision: str, *, approve_all: bool = False) -> dict[str, Any]:
        """The user's answer to a desktop's request: reject, or accept and run it here."""
        host = self._host(host_id)
        job = self._job(host_id, _checked_id(job_id, "request"))
        if job is None:
            raise KeyError("unknown request")
        if job["state"] != "waiting":
            raise ValueError("this request was already answered")
        self.notify({"action": "cancel", "tag": f"job:{job_id}"})
        if decision == "reject":
            await self._report(host_id, job_id, "rejected")
            self._job_state(host_id, job_id, "rejected")
            self.activity(host_id, "job_rejected", job["prompt"][:80])
            return self._job_document(host_id, job_id)
        if decision != "accept":
            raise ValueError("decision must be accept or reject")
        if not await self._report(host_id, job_id, "accepted"):
            self._job_state(host_id, job_id, "expired")
            raise ValueError("the computer no longer waits for this request")
        self._job_state(host_id, job_id, "accepted")
        self.activity(host_id, "job_accepted", job["prompt"][:80])
        try:
            task_id, session_id = await self._start_job(host, job, approve_all=approve_all)
        except Exception as error:
            reason = " ".join(str(error).split())[:300] or type(error).__name__
            self._job_state(host_id, job_id, "failed", error=reason)
            with contextlib.suppress(httpx.HTTPError, ValueError):
                await self._report(host_id, job_id, "failed", error=reason)
            raise ValueError(f"the request could not start here: {reason}") from None
        self._job_state(host_id, job_id, "running", task_id=task_id, session_id=session_id)
        with contextlib.suppress(httpx.HTTPError, ValueError):
            await self._report(host_id, job_id, "running")
        self._watch_job(host_id, job_id, task_id)
        return self._job_document(host_id, job_id)

    def _job_document(self, host_id: str, job_id: str) -> dict[str, Any]:
        job = self._job(host_id, job_id)
        return {**dict(job), "operate_phone": bool(job["operate_phone"])} if job is not None else {}

    async def _start_job(self, host: dict[str, Any], job: sqlite3.Row, *, approve_all: bool) -> tuple[str, str]:
        from mobile_protocol import parse_mobile_task_request

        if self.controller is None or self.runtime is None:
            raise ValueError("the engine is not ready")
        settings = self.settings(host["host_id"])
        session_id = settings["job_session"]
        if not self._session_exists(session_id):
            session_id = self._new_session(f"{host['name']} 交来的任务")
            self._set(host["host_id"], job_session=session_id)
        title = f"「{job['title']}」" if job["title"] else ""
        # The conversation and its notifications show the request itself; where it came from is a note.
        note = (
            f"[This message is a request from the AI on the paired computer {host['name']}"
            f"{' (conversation ' + title + ')' if title else ''}. The user read it and agreed to let this phone do it.]"
        )
        operate = bool(job["operate_phone"])
        request = parse_mobile_task_request({
            "session_id": session_id,
            "prompt": job["prompt"],
            "source_note": note,
            **({"phone_control": True, "auto_approve": True} if operate and approve_all else {}),
            **({"phone_control": True} if operate and not approve_all else {}),
        })
        task = await self.controller.submit(
            request, request_id=f"phone-job:{host['host_id']}:{job['job_id']}"[:128],
            preauthorized=approve_all and not operate,
        )
        return task.task_id, session_id

    def _watch_job(self, host_id: str, job_id: str, task_id: str) -> None:
        if self.controller is None or job_id in self._waiters:
            return

        async def wait() -> None:
            try:
                await self.controller.wait(task_id)
                await self._finish_job(host_id, job_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass  # the next poll reports it (_drive_jobs)
            finally:
                self._waiters.pop(job_id, None)

        with contextlib.suppress(RuntimeError):
            self._waiters[job_id] = asyncio.get_running_loop().create_task(wait(), name=f"phone-job-{job_id}")

    async def _finish_job(self, host_id: str, job_id: str) -> None:
        job = self._job(host_id, job_id)
        if job is None or job["state"] != "running" or not job["task_id"] or self.controller is None:
            return
        task = self.controller.get(job["task_id"])
        state = getattr(task.state, "value", str(task.state))
        if state not in {"succeeded", "failed", "cancelled", "interrupted"}:
            return
        if state == "succeeded":
            result = self._last_reply(job["session_id"])[:MAX_JOB_RESULT] or "Done."
            if await self._report(host_id, job_id, "succeeded", result=result):
                self._job_state(host_id, job_id, "succeeded", result=result)
            else:
                self._job_state(host_id, job_id, "succeeded", result=result, error="the computer stopped waiting")
            self.activity(host_id, "job_finished", job["prompt"][:80])
        else:
            reason = (getattr(task, "reason", None) or state)[:2000]
            with contextlib.suppress(RemoteHTTPError):
                await self._report(host_id, job_id, "failed", error=reason)
            self._job_state(host_id, job_id, "failed", error=reason[:300])
            self.activity(host_id, "job_failed", job["prompt"][:80])

    async def _drive_jobs(self, host: dict[str, Any]) -> None:
        """Requests running here when the engine restarted: report those that ended."""
        for job in self.jobs(host["host_id"]):
            if job["state"] == "running" and job["job_id"] not in self._waiters:
                with contextlib.suppress(KeyError):
                    await self._finish_job(host["host_id"], job["job_id"])

    def _last_reply(self, session_id: str | None) -> str:
        if not session_id or self.runtime is None:
            return ""
        for event in reversed(self.runtime.store.list_events(session_id)):
            found = _message_text(event)
            if found and found[0] == "assistant":
                return found[1]
        return ""

    async def set_jobs(self, host_id: str, choice: str) -> dict[str, Any]:
        host = self._host(host_id)
        if choice not in _JOB_SETTINGS:
            raise ValueError("choose ask, auto or off")
        self._set(host_id, jobs=choice)
        if "device" in host["features"]:
            self._told_jobs.discard(host_id)
            with contextlib.suppress(httpx.HTTPError, ValueError):
                await self.connections.request(host_id, "POST", "/mobile/device", {"accepts_jobs": choice != "off"})
                self._told_jobs.add(host_id)
        return self.settings(host_id)

    # ---- the user's requests ---------------------------------------------------------------------

    def start(self, host_id: object, kind: str, work: Callable[[], Any]) -> dict[str, Any]:
        """Run a long request (sending or fetching files, syncing) in the background; the page asks
        for its state with ``operation``."""
        self._host(host_id)
        operation_id = uuid.uuid4().hex
        record: dict[str, Any] = {"operation_id": operation_id, "host_id": host_id, "kind": kind,
                                  "state": "running", "started_at": self.clock(), "result": None, "error": None}
        self._operations[operation_id] = record
        for stale in list(self._operations)[:-50]:
            if self._operations[stale]["state"] != "running":
                self._operations.pop(stale, None)

        async def run() -> None:
            try:
                record["result"] = await work()
                record["state"] = "done"
            except asyncio.CancelledError:
                record.update(state="failed", error="stopped")
                raise
            except Exception as error:
                if isinstance(error, RemoteHTTPError) and refused(error):
                    reason = refusal_reason(error)
                elif isinstance(error, httpx.HTTPError):
                    reason = unavailable_reason(error)
                else:
                    reason = " ".join(str(error).split())[:500] or type(error).__name__
                record.update(state="failed", error=reason)
            finally:
                record["finished_at"] = self.clock()
                self._tasks.discard(task)

        task = asyncio.get_running_loop().create_task(run(), name=f"link-{kind}")
        self._tasks.add(task)
        return dict(record)

    def operation(self, operation_id: object) -> dict[str, Any]:
        record = self._operations.get(str(operation_id or ""))
        if record is None:
            raise KeyError("unknown operation")
        return dict(record)

    def poll_soon(self, host_id: str) -> None:
        self._next[host_id] = 0.0

    def summary(self) -> dict[str, dict[str, Any]]:
        """Per computer, for the Device connections list: reachable or why not, and what waits."""
        with self._db() as db:
            states = db.execute("SELECT * FROM link_state").fetchall()
            waiting = {
                row["host_id"]: row["n"]
                for row in db.execute(
                    "SELECT host_id, COUNT(*) AS n FROM link_jobs WHERE state='waiting' GROUP BY host_id"
                )
            }
        result: dict[str, dict[str, Any]] = {}
        for row in states:
            approvals = 0
            if row["inbox"]:
                with contextlib.suppress(ValueError, TypeError):
                    approvals = len(json.loads(row["inbox"]).get("approvals") or [])
            result[row["host_id"]] = {
                "online": row["error"] is None and row["polled_at"] is not None,
                "error": row["error"],
                "polled_at": row["polled_at"],
                "approvals": approvals,
                "jobs_waiting": waiting.get(row["host_id"], 0),
                "waking": self._waking.get(row["host_id"], 0.0) > self.clock(),
            }
        return result

    def computer(self, host_id: str) -> dict[str, Any]:
        """What the computer page shows: the host, its last inbox, what was received, requests, records."""
        host = self._host(host_id)
        with self._db() as db:
            state = db.execute("SELECT * FROM link_state WHERE host_id=?", (host_id,)).fetchone()
            received = db.execute(
                "SELECT * FROM link_received WHERE host_id=? ORDER BY at DESC LIMIT 50", (host_id,)
            ).fetchall()
            activity = db.execute(
                "SELECT at, action, detail FROM link_activity WHERE host_id=? ORDER BY id DESC LIMIT 100", (host_id,)
            ).fetchall()
        inbox: dict[str, Any] = {}
        if state is not None and state["inbox"]:
            with contextlib.suppress(ValueError):
                inbox = json.loads(state["inbox"])
        settings = self.settings(host_id)
        return {
            "host": host,
            "online": state is not None and state["error"] is None and state["polled_at"] is not None,
            "polled_at": state["polled_at"] if state is not None else None,
            "error": state["error"] if state is not None else None,
            "waking": self._waking.get(host_id, 0.0) > self.clock(),
            "approvals": inbox.get("approvals") or [],
            "runs": inbox.get("runs") or [],
            "turns": inbox.get("turns") or [],
            "received": [dict(row) for row in received],
            "jobs": self.jobs(host_id),
            "settings": {key: settings[key] for key in ("jobs", "kb_pairs", "kb_synced_at", "kb_result")},
            "activity": [dict(row) for row in activity],
        }

    def refresh(self, host_id: str) -> dict[str, Any]:
        """Read the computer again soon (the loop does it within seconds), its runtime included."""
        self._host(host_id)
        with self._db() as db:
            db.execute("UPDATE mobile_hosts SET runtime_at=NULL WHERE host_id=?", (host_id,))
        self.poll_soon(host_id)
        return self.computer(host_id)

    async def approve(self, host_id: str, request_id: object, decision: object) -> dict[str, Any]:
        host = self._host(host_id)
        self._needs(host, "approvals")
        request_id = _checked_id(request_id, "approval")
        if decision not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject")
        try:
            await self.connections.request(
                host_id, "POST", f"/mobile/approvals/{quote(request_id, safe='')}", {"decision": decision}
            )
        except RemoteHTTPError as error:
            if error.code == "approval_already_resolved":
                raise ValueError("this was already answered on the computer or another phone") from None
            if error.code == "scope_denied":
                raise ValueError(refusal_reason(error)) from None
            raise
        self.notify({"action": "cancel", "tag": f"approval:{request_id}"})
        waiting = next((item for item in self.computer(host_id)["approvals"]
                        if isinstance(item, dict) and item.get("request_id") == request_id), {})
        what = str(waiting.get("summary") or waiting.get("tool") or request_id)
        self.activity(host_id, "approval_decided", f"{'allowed' if decision == 'approve' else 'refused'}: {what}")
        # Shown as answered right away; the next read of the inbox confirms it.
        with self._db() as db:
            row = db.execute("SELECT inbox FROM link_state WHERE host_id=?", (host_id,)).fetchone()
            if row is not None and row["inbox"]:
                with contextlib.suppress(ValueError, AttributeError):
                    inbox = json.loads(row["inbox"])
                    inbox["approvals"] = [item for item in inbox.get("approvals") or []
                                          if not isinstance(item, dict) or item.get("request_id") != request_id]
                    db.execute("UPDATE link_state SET inbox=? WHERE host_id=?", (json.dumps(inbox), host_id))
        self.poll_soon(host_id)
        return self.computer(host_id)

    async def stop(self, host_id: str, session_id: object) -> dict[str, Any]:
        host = self._host(host_id)
        self._needs(host, "stop")
        session_id = _checked_id(session_id, "conversation")
        try:
            await self.connections.request(host_id, "POST", f"/mobile/sessions/{quote(session_id, safe='')}/stop", {})
        except RemoteHTTPError as error:
            if error.code == "not_running":
                raise ValueError("that conversation is not running on the computer") from None
            raise
        self.activity(host_id, "turn_stopped", session_id)
        return {"stopped": True}

    async def browse(self, host_id: str, path: object = "") -> dict[str, Any]:
        host = self._host(host_id)
        self._needs(host, "files")
        relative = str(path or "").strip().strip("/")
        if len(relative) > 1000 or ".." in relative.split("/"):
            raise ValueError("invalid folder")
        try:
            _, listing = await self.connections.request(
                host_id, "GET", "/mobile/files" + (f"?{urlencode({'path': relative})}" if relative else "")
            )
        except RemoteHTTPError as error:
            if error.code in {"unknown_path", "invalid_path"}:
                raise ValueError("that folder is not on the computer") from None
            if error.code == "no_workspace":
                raise ValueError(refusal_reason(error)) from None
            raise
        return listing

    async def download(self, host_id: str, path: object) -> dict[str, Any]:
        host = self._host(host_id)
        self._needs(host, "files")
        relative = str(path or "").strip().strip("/")
        if not relative or len(relative) > 1000 or ".." in relative.split("/"):
            raise ValueError("invalid file")
        folder = self.workspace / RECEIVED_FOLDER
        target = unique_path(folder, safe_filename(relative))
        try:
            received = await self.connections.download(
                host_id, f"/mobile/files/content?{urlencode({'path': relative})}", target, max_bytes=MAX_FILE_BYTES
            )
        except RemoteHTTPError as error:
            if error.code in {"unknown_path", "invalid_path"}:
                raise ValueError("that file is not on the computer") from None
            if error.code == "payload_too_large":
                raise ValueError("the file is larger than 100 MiB") from None
            raise
        self.activity(host_id, "file_received", target.name)
        return {"path": target.relative_to(self.workspace).as_posix(), "name": target.name, "sha256": received["sha256"]}

    # ---- code review (feature "code_review", the desktop's docs/DEVICE_LINK_API.md) ---------------

    async def _review_call(self, host_id: str, method: str, route: str, payload: Any = None) -> dict[str, Any]:
        """The changes of the folder open on the computer, through the window's own Changes page."""
        self._needs(self._host(host_id), "code_review")
        try:
            _, answer = await self.connections.request(host_id, method, route, payload, timeout=30)
        except RemoteHTTPError as error:
            if error.code in _REVIEW_REFUSALS:
                raise ValueError(_REVIEW_REFUSALS[error.code]) from None
            if error.code in {"scope_denied", "no_workspace"}:
                raise ValueError(refusal_reason(error)) from None
            raise
        return answer

    async def changes(self, host_id: str) -> dict[str, Any]:
        return await self._review_call(host_id, "GET", "/mobile/changes")

    async def change_diff(self, host_id: str, path: object) -> dict[str, Any]:
        if not isinstance(path, str) or not path or len(path) > 1000:
            raise ValueError("invalid file")
        return await self._review_call(host_id, "GET", f"/mobile/changes/diff?{urlencode({'path': path})}")

    async def reviews(self, host_id: str) -> dict[str, Any]:
        return await self._review_call(host_id, "GET", "/mobile/reviews")

    async def review(self, host_id: str, review_id: object) -> dict[str, Any]:
        review_id = _checked_id(review_id, "review")
        return await self._review_call(host_id, "GET", f"/mobile/reviews/{quote(review_id, safe='')}")

    async def freeze_review(self, host_id: str) -> dict[str, Any]:
        """The changes frozen into a review, under the conversation open in the computer's window."""
        return await self._review_call(host_id, "POST", "/mobile/reviews", {})

    async def review_comment(
        self, host_id: str, review_id: object, path: object, side: object, line: object, body: object
    ) -> dict[str, Any]:
        review_id = _checked_id(review_id, "review")
        text = body.strip() if isinstance(body, str) else ""
        if not text or len(text) > 4000:
            raise ValueError("write a comment of at most 4,000 characters")
        if not isinstance(path, str) or not path or side not in {"old", "new"} or type(line) is not int or line < 1:
            raise ValueError("that line is not in this review's changes")
        answer = await self._review_call(
            host_id, "POST", f"/mobile/reviews/{quote(review_id, safe='')}/comments",
            {"path": path, "side": side, "line": line, "body": text},
        )
        self.activity(host_id, "review_comment", f"{path}:{line}")
        return answer

    async def review_followup(self, host_id: str, comment_id: object) -> dict[str, Any]:
        """A comment handed to the computer's AI, which works on it in a copy of the folder of its own."""
        comment_id = _checked_id(comment_id, "comment")
        try:
            answer = await self._review_call(
                host_id, "POST", f"/mobile/reviews/comments/{quote(comment_id, safe='')}/followup", {}
            )
        except RemoteHTTPError as error:
            # Handed over already (here, from the window, or a request whose answer was lost).
            if error.code == "followup_already_exists":
                return {"already": True}
            raise
        self.activity(host_id, "review_followup", str(answer.get("run_id") or comment_id))
        return answer

    def _staged(self, entry: object) -> tuple[Path, bool]:
        """A file to send: one staged by the app for this purpose (deleted once sent), or a file in the
        phone's workspace."""
        staging = (self.data.parent / STAGING_FOLDER).resolve()
        if isinstance(entry, dict) and isinstance(entry.get("staged"), str):
            name = entry["staged"]
            if not _STAGED.fullmatch(name):
                raise ValueError("invalid file")
            path = (staging / name).resolve()
            if path.parent != staging or not path.is_file():
                raise ValueError("the picked file is gone; pick it again")
            return path, True
        if isinstance(entry, dict) and isinstance(entry.get("workspace"), str):
            path = (self.workspace / entry["workspace"]).resolve()
            if self.workspace.resolve() not in path.parents or not path.is_file():
                raise ValueError("invalid file")
            return path, False
        raise ValueError("invalid file")

    async def send_files(
        self,
        host_id: str,
        files: object,
        *,
        knowledge: object = None,
        instruction: object = None,
        session_id: object = None,
    ) -> dict[str, Any]:
        """Files to the computer's open folder (from-phone folder); with an instruction, a task too."""
        host = self._host(host_id)
        self._needs(host, "files")
        if not isinstance(files, list) or not files or len(files) > 50:
            raise ValueError("choose 1 to 50 files")
        base = None
        if knowledge not in (None, ""):
            base = " ".join(str(knowledge).split())[:100]
        task_text = " ".join(str(instruction or "").split()).strip()[:20000]
        sources = [self._staged(entry) for entry in files]
        sent: list[dict[str, Any]] = []
        failed: list[dict[str, str]] = []
        for (path, staged), entry in zip(sources, files, strict=True):
            # A staged copy has a random name (ComputerSend); the page passes the original one.
            given = entry.get("name") if isinstance(entry, dict) else None
            name = safe_filename(given if isinstance(given, str) and given.strip() else path.name)
            staged_name = entry.get("staged") if isinstance(entry, dict) else None
            try:
                answer, transfer_id = await self._upload_one(host_id, path, name, base)
            except (httpx.HTTPError, ValueError, OSError) as error:
                failed.append({"name": name, "staged": staged_name, "error": self._reason(error)})
                continue
            sent.append({"name": name, "path": str(answer.get("path") or name), "transfer_id": transfer_id,
                         "staged": staged_name})
            self.activity(host_id, "file_sent", name)
            if staged:
                path.unlink(missing_ok=True)
        if not sent:
            raise ValueError(failed[0]["error"] if failed else "nothing was sent")
        # Files that went are gone from the phone's staging folder: from here on the answer says what
        # happened to each instead of failing as a whole (the page keeps only what is still to send).
        task = task_error = None
        if task_text:
            listing = "\n".join(f"- {item['path']}" for item in sent)
            prompt = f"{task_text}\n\nFiles sent from my phone, in the open folder:\n{listing}"
            try:
                task = await self._hand_over(host, prompt, session_id=session_id, title=task_text[:40],
                                             files=[item["transfer_id"] for item in sent])
            except (httpx.HTTPError, ValueError) as error:
                task_error = self._reason(error)
        return {"sent": sent, "failed": failed, "task": task, "task_error": task_error}

    @staticmethod
    def _reason(error: BaseException) -> str:
        if isinstance(error, RemoteHTTPError):
            return {
                "checksum_mismatch": "the file was damaged on the way; send it again",
                "payload_too_large": "the file is larger than 100 MiB",
            }.get(error.code or "", refusal_reason(error))
        if isinstance(error, httpx.HTTPError):
            return unavailable_reason(error)
        return " ".join(str(error).split())[:300] or type(error).__name__

    async def _upload_one(self, host_id: str, path: Path, name: str, base: str | None) -> tuple[dict[str, Any], str]:
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValueError("the file is larger than 100 MiB")
        sha256 = file_sha256(path)
        transfer_id = "t" + hashlib.sha256(f"{host_id}:{sha256}:{name}:{uuid.uuid4()}".encode()).hexdigest()[:32]
        query = {"name": name, "size": str(size), "sha256": sha256, **({"knowledge": base} if base else {})}
        answer = await self.connections.upload(host_id, f"/mobile/files/{transfer_id}?{urlencode(query)}", path, sha256=sha256)
        return answer, transfer_id

    async def send_text(self, host_id: str, text: object, kind: object = "text") -> dict[str, Any]:
        host = self._host(host_id)
        self._needs(host, "messages")
        if kind not in {"text", "link"}:
            raise ValueError("kind must be text or link")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("write something to send")
        if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValueError("the text is longer than 64 KiB")
        await self.connections.request(
            host_id, "POST", "/mobile/messages", {"request_id": str(uuid.uuid4()), "kind": kind, "text": text}
        )
        self.activity(host_id, "text_sent", text[:80])
        return {"ok": True}

    async def _upload_images(self, host_id: str, images: list[dict[str, str]]) -> list[str]:
        """A conversation's pictures sent first, so the computer's copy has them (2.9)."""
        transfers: list[str] = []
        for image in images:
            path = (self.workspace / image["path"]).resolve()
            if self.workspace.resolve() not in path.parents or not path.is_file():
                continue
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                continue
            sha256 = file_sha256(path)
            transfer_id = "t" + hashlib.sha256(f"{host_id}:{sha256}:relay".encode()).hexdigest()[:32]
            query = {"name": safe_filename(path.name), "size": str(size), "sha256": sha256}
            await self.connections.upload(host_id, f"/mobile/files/{transfer_id}?{urlencode(query)}", path, sha256=sha256)
            transfers.append(transfer_id)
        return transfers

    async def _hand_over(
        self,
        host: dict[str, Any],
        prompt: str,
        *,
        session_id: object = None,
        title: str,
        files: list[str] | None = None,
        messages: list[dict[str, str]] | None = None,
        request_id: str | None = None,
        confirmed: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """A task in an existing computer conversation (through the outbox), or in a new one.
        ``confirmed``: what the user accepted on the phone (accept_autonomy, private content)."""
        host_id = host["host_id"]
        request_id = request_id or str(uuid.uuid4())
        confirmed = acknowledgements(confirmed or {})
        if session_id:
            delivery = self.outbox.enqueue({"host_id": host_id, "session_id": _checked_id(session_id, "conversation"),
                                            "prompt": prompt, "request_id": request_id, **confirmed})
            delivery = await self.outbox.send(delivery["delivery_id"])
            self.activity(host_id, "task_sent", prompt[:80])
            return delivery
        self._needs(host, "conversations")
        try:
            _, created = await self.connections.request(
                host_id,
                "POST",
                "/mobile/conversations",
                {"request_id": request_id, "title": title or "From phone", "messages": messages or [],
                 **({"files": files} if files else {}), **({"prompt": prompt, **confirmed} if prompt else {})},
                timeout=60,
            )
        except RemoteHTTPError as error:
            if refused(error):
                raise ValueError(refusal_reason(error)) from None
            raise
        task = created.get("task") if isinstance(created.get("task"), dict) else None
        remote_session = created.get("session_id")
        delivery = None
        if task and isinstance(task.get("task_id"), str) and isinstance(remote_session, str):
            delivery = self.outbox.record_submitted(
                host_id, request_id, {"session_id": remote_session, "prompt": prompt, **confirmed}, task["task_id"]
            )
            self.activity(host_id, "task_sent", prompt[:80])
        return {"session_id": remote_session, "title": created.get("title"), "delivery": delivery}

    async def new_task(self, host_id: str, prompt: object, confirmed: dict[str, Any] | None = None) -> dict[str, Any]:
        """A task in a new conversation on the computer (the handoff panel's "New conversation")."""
        host = self._host(host_id)
        self._needs(host, "tasks")
        text = str(prompt or "").strip()
        if not text or len(text) > 65536:
            raise ValueError("write what the computer should do")
        return await self._hand_over(host, text, title=" ".join(text.split())[:40], confirmed=confirmed)

    async def relay(self, host_id: str, session_id: object, prompt: object = None) -> dict[str, Any]:
        """Continue a phone conversation on the computer: its messages, pictures and an optional prompt."""
        host = self._host(host_id)
        self._needs(host, "conversations")
        if self.runtime is None:
            raise ValueError("the engine is not ready")
        title, messages, images = self._conversation_messages(_checked_id(session_id, "conversation"))
        if not messages:
            raise ValueError("this conversation has no messages to continue")
        files = await self._upload_images(host_id, images) if images and "files" in host["features"] else []
        text = " ".join(str(prompt or "").split())[:20000]
        created = await self._hand_over(host, text, title=title or "From phone", files=files, messages=messages)
        self.activity(host_id, "conversation_sent", title or str(session_id))
        return created

    def wake_targets(self, host_id: str) -> list[dict[str, str]]:
        targets = []
        for item in self.connections.runtime(host_id).get("wake") or []:
            if not isinstance(item, dict) or not isinstance(item.get("mac"), str):
                continue
            with contextlib.suppress(ValueError):
                magic_packet(item["mac"])
                broadcast = item.get("broadcast") if isinstance(item.get("broadcast"), str) else "255.255.255.255"
                targets.append({"mac": item["mac"], "broadcast": broadcast})
        return targets[:8]

    async def wake(self, host_id: str) -> dict[str, Any]:
        """Wake-on-LAN packets to the computer's network cards, then wait (in the background) until it
        answers again."""
        host = self._host(host_id)
        targets = self.wake_targets(host_id)
        if not targets:
            raise ValueError("the computer has not allowed waking it from the phone")
        sent = 0
        for target in targets:
            packet = magic_packet(target["mac"])
            for address in {target["broadcast"], "255.255.255.255"}:
                for port in (9, 7):
                    with contextlib.suppress(OSError), _udp_socket() as sender:
                        sender.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                        sender.sendto(packet, (address, port))
                        sent += 1
        if not sent:
            raise ValueError("could not send on this network; is the phone on the computer's Wi-Fi?")
        self._waking[host_id] = self.clock() + _WAKE_SECONDS
        self.activity(host_id, "wake_sent", host["name"])

        async def wait_online() -> None:
            deadline = self.clock() + _WAKE_SECONDS
            while self.clock() < deadline:
                await asyncio.sleep(5)
                with contextlib.suppress(httpx.HTTPError, ValueError):
                    await self.connections.request(host_id, "GET", "/health", timeout=4)
                    self._waking.pop(host_id, None)
                    self._next[host_id] = 0.0
                    self.notify({"action": "online", "id": host_id, "host": host["name"], "host_id": host_id})
                    return
            self._waking.pop(host_id, None)

        with contextlib.suppress(RuntimeError):
            waiting = asyncio.get_running_loop().create_task(wait_online(), name=f"wake-{host_id}")
            self._tasks.add(waiting)
            waiting.add_done_callback(self._tasks.discard)
        return {"sent": sent}

    async def read_runs(self, host_id: str, run_ids: object) -> dict[str, Any]:
        host = self._host(host_id)
        if not isinstance(run_ids, list) or not run_ids or len(run_ids) > 50:
            raise ValueError("invalid results")
        ids = [_checked_id(item, "result") for item in run_ids]
        if "inbox_read" in host["features"]:
            await self.connections.request(host_id, "POST", "/mobile/inbox/read", {"run_ids": ids})
        return {"ok": True}

    async def remote_device(self, host_id: str) -> dict[str, Any]:
        host = self._host(host_id)
        self._needs(host, "device")
        _, document = await self.connections.request(host_id, "GET", "/mobile/device")
        return document

    async def _refind(self, host_id: str) -> None:
        """All addresses failed: look for the same desktop (its desktop_id) on this network. An HTTPS
        one is moved to its new address when its pinned certificate answers there; an HTTP one is
        offered to the user (nothing proves it is the same computer)."""
        if self.discover is None:
            return
        host = self.connections.get(host_id)
        if not host.get("desktop_id") or self._failures.get(host_id, 0) != 2:
            return  # once, after the second failure in a row
        try:
            found = await asyncio.to_thread(self.discover, 4.0)
        except Exception:
            return
        for service in found:
            if service.get("id") != host["desktop_id"] or not isinstance(service.get("url"), str):
                continue
            if host.get("fingerprint") and service["url"].startswith("https://"):
                with contextlib.suppress(Exception):
                    self.connections.use_address(host_id, service["url"])
                    await self.connections.request(host_id, "GET", "/health", timeout=5)
                    self.activity(host_id, "address_changed", service["url"])
                    self._next[host_id] = 0.0
                return
            if not host.get("fingerprint") and service["url"].startswith("http://"):
                self.notify({"action": "moved", "id": host_id, "host": host["name"], "host_id": host_id,
                             "url": service["url"]})
                with self._db() as db:
                    db.execute("UPDATE link_state SET error=? WHERE host_id=?",
                               (f"found at {service['url']}", host_id))
                return

    # ---- knowledge bases -------------------------------------------------------------------------

    async def knowledge_bases(self, host_id: str) -> dict[str, Any]:
        host = self._host(host_id)
        self._needs(host, "knowledge")
        _, listing = await self.connections.request(host_id, "GET", "/mobile/knowledge", max_bytes=8 * 1024 * 1024)
        bases = []
        for base in listing.get("bases") or []:
            if isinstance(base, dict) and isinstance(base.get("id"), str):
                documents = base.get("documents") if isinstance(base.get("documents"), list) else []
                bases.append({"id": base["id"], "name": str(base.get("name") or ""), "documents": len(documents)})
        phone = []
        if self.knowledge is not None:
            store = self.knowledge()
            phone = [{"id": item["id"], "label": item["label"], "documents": item["ready"]} for item in store.collections()]
        return {"computer": bases, "phone": phone}

    def set_pairs(self, host_id: str, pairs: object) -> dict[str, Any]:
        self._host(host_id)
        if not isinstance(pairs, list) or len(pairs) > 20:
            raise ValueError("invalid knowledge base pairs")
        kept = []
        for pair in pairs:
            if not isinstance(pair, dict):
                raise ValueError("invalid knowledge base pairs")
            kept.append({"computer": _checked_id(pair.get("computer"), "knowledge base"),
                         "phone": _checked_id(pair.get("phone"), "knowledge base")})
        self._set(host_id, kb_pairs=json.dumps(kept))
        return self.settings(host_id)

    async def _knowledge_due(self, host: dict[str, Any]) -> None:
        settings = self.settings(host["host_id"])
        if not settings["kb_pairs"] or "knowledge" not in host["features"]:
            return
        if settings["kb_synced_at"] and self.clock() - float(settings["kb_synced_at"]) < _KNOWLEDGE_SECONDS:
            return
        with contextlib.suppress(httpx.HTTPError, ValueError):
            await self.sync_knowledge(host["host_id"])

    async def sync_knowledge(self, host_id: str) -> dict[str, Any]:
        """Each pair of knowledge bases gets the documents the other side has and it lacks (by the
        original file's SHA-256). Removals are not copied."""
        host = self._host(host_id)
        self._needs(host, "knowledge")
        if self.knowledge is None:
            raise ValueError("the knowledge base is not available")
        store = self.knowledge()
        pairs = self.settings(host_id)["kb_pairs"]
        if not pairs:
            raise ValueError("add a pair of knowledge bases first")
        _, listing = await self.connections.request(host_id, "GET", "/mobile/knowledge", max_bytes=8 * 1024 * 1024)
        bases = {base["id"]: base for base in listing.get("bases") or [] if isinstance(base, dict)
                 and isinstance(base.get("id"), str)}
        collections = {item["id"]: item for item in store.collections()}
        phone_docs = store.documents(ready_only=True)
        phone_hashes = {document["sha256"] for document in store.documents() if document["state"] != "failed"}
        computer_hashes = {
            document.get("sha256")
            for base in bases.values()
            for document in base.get("documents") or []
            if isinstance(document, dict)
        }
        to_phone = to_computer = 0
        errors: list[str] = []
        for pair in pairs:
            base = bases.get(pair["computer"])
            if base is None or pair["phone"] not in collections:
                errors.append("a paired knowledge base no longer exists")
                continue
            for document in base.get("documents") or []:
                if not isinstance(document, dict) or document.get("sha256") in phone_hashes:
                    continue
                if not isinstance(document.get("id"), str) or not _ID.fullmatch(document["id"]):
                    continue
                try:
                    _, extracted = await self.connections.request(
                        host_id, "GET", f"/mobile/knowledge/documents/{quote(document['id'], safe='')}",
                        max_bytes=32 * 1024 * 1024, timeout=120,
                    )
                    added = await asyncio.to_thread(store.add_extracted, extracted, collection_id=pair["phone"],
                                                    origin="computer")
                except (httpx.HTTPError, ValueError) as error:
                    errors.append(f"{str(document.get('title') or '')[:60]}: {str(error)[:120]}")
                    continue
                phone_hashes.add(added.get("sha256"))
                to_phone += 0 if added.get("duplicate") else 1
            for document in phone_docs:
                if document["collection_id"] != pair["phone"] or document["sha256"] in computer_hashes:
                    continue
                try:
                    extracted = await asyncio.to_thread(store.extracted, document["id"])
                    await self.connections.request(
                        host_id, "POST", "/mobile/knowledge/documents",
                        {"base": str(base.get("name") or ""), **extracted}, timeout=120,
                    )
                except (httpx.HTTPError, ValueError) as error:
                    errors.append(f"{document['title'][:60]}: {str(error)[:120]}")
                    continue
                computer_hashes.add(document["sha256"])
                to_computer += 1
        result = {"to_phone": to_phone, "to_computer": to_computer, "errors": errors[:10]}
        self._set(host_id, kb_synced_at=self.clock(), kb_result=json.dumps(result, ensure_ascii=False))
        if to_phone or to_computer:
            self.activity(host_id, "knowledge_synced", f"to phone {to_phone}, to computer {to_computer}")
        return result

    # ---- the phone's AI asking the computer ------------------------------------------------------

    def _reachable(self, host_id: str) -> bool:
        """Read without an error within the last two minutes."""
        with self._db() as db:
            row = db.execute("SELECT polled_at, error FROM link_state WHERE host_id=?", (host_id,)).fetchone()
        return row is not None and row["error"] is None and self.clock() - float(row["polled_at"] or 0) < 120

    def computers_for_tasks(self) -> list[dict[str, Any]]:
        return [
            host for host in self.connections.list()
            if host["api"] == "mobile" and (not host["scopes"] or "tasks" in host["scopes"])
        ]

    async def ask_computer(
        self, task: str, *, computer: str | None = None, conversation: str | None = None, request_id: str,
        timeout: float = _ASK_SECONDS,
    ) -> dict[str, Any]:
        """Hand one part of a task to a paired computer and wait for its answer (ask_computer)."""
        hosts = self.computers_for_tasks()
        if not hosts:
            raise ValueError("no computer is paired with this phone")
        if computer:
            wanted = computer.strip().lower()
            matches = [host for host in hosts if host["name"].lower() == wanted] or [
                host for host in hosts if wanted in host["name"].lower() or wanted in host["url"].lower()
            ]
        else:
            matches = hosts
        # Several with that name (an old pairing left behind, say): the one that answers now.
        if len(matches) > 1:
            matches = [host for host in matches if self._reachable(host["host_id"])] or matches
        if len(matches) != 1:
            names = ", ".join(f"{host['name']} ({host['url']})" for host in hosts)
            raise ValueError(f"name one of the paired computers: {names}")
        host = matches[0]
        session_id = None
        if conversation:
            _, listing = await self.connections.request(host["host_id"], "GET", "/sessions")
            wanted = conversation.strip().lower()
            sessions = [item for item in listing.get("sessions") or [] if isinstance(item, dict)]
            matches = [item for item in sessions if str(item.get("title") or "").lower() == wanted] or [
                item for item in sessions if wanted in str(item.get("title") or "").lower()
            ]
            if len(matches) != 1:
                raise ValueError("no single conversation on the computer has that title")
            session_id = matches[0].get("id")
        elif "conversations" not in host["features"]:
            raise ValueError("the computer's app is older: name one of its conversations (conversation=...)")
        handed = await self._hand_over(host, task, session_id=session_id, title=task[:40], request_id=request_id)
        delivery = handed if session_id else handed.get("delivery")
        if not delivery:
            raise ValueError("the computer did not start the task")
        deadline = self.clock() + timeout
        while True:
            current = self.outbox.get(delivery["delivery_id"])
            if current["state"] in _TERMINAL:
                break
            if self.clock() > deadline:
                raise ValueError("the computer has not finished after 30 minutes; it keeps working and the "
                                 "result will show under Outbox & handoff")
            await asyncio.sleep(_ASK_POLL_SECONDS)
            with contextlib.suppress(httpx.HTTPError, ValueError, KeyError):
                current = await self.outbox.reconcile(delivery["delivery_id"])
                if current["state"] in _TERMINAL:
                    break
        return {"computer": host["name"], "state": current["state"], "result": current.get("result"),
                "error": current.get("error")}


def staging_folder(data: Path | None = None) -> Path:
    root = Path(data or os.getenv("AGENT_WORKSPACE_DATA_DIR") or ".")
    return root.parent / STAGING_FOLDER
