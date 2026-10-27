"""Persist handoffs before sending and never replay an ambiguous legacy run."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import httpx
from mobile_connections import MobileConnections, RemoteHTTPError, connection_database
from mobile_protocol import parse_mobile_task_request


_BROAD_AUTONOMY = frozenset({"yolo", "full_access"})


def acknowledgements(payload: dict) -> dict:
    """What the user confirmed on the phone before handing a task to a desktop (docs/DEVICE_LINK_V2.md):
    running in a conversation that approves everything by itself (2.1), and sending numbers that
    usually stay with the on-device model (2.2)."""
    found: dict = {}
    autonomy = payload.get("accept_autonomy")
    if autonomy is not None:
        if autonomy not in _BROAD_AUTONOMY:
            raise ValueError("accept_autonomy must be yolo or full_access")
        found["accept_autonomy"] = autonomy
    if payload.get("private_accepted") is not None or payload.get("on_device") is not None:
        if payload.get("private_accepted") is not True or payload.get("on_device") is not True:
            raise ValueError("private content goes to a computer only with on_device and private_accepted")
        found.update(on_device=True, private_accepted=True)
    return found


_REFUSALS = {
    "desktop_autonomy_too_broad": (
        "this conversation on the computer approves everything by itself; confirm on the phone to hand tasks to it"
    ),
    "autonomy_changed": (
        "the conversation's settings on the computer changed; check them and confirm again before handing it over"
    ),
    "scope_denied": (
        "the computer has not allowed this phone to do this; allow it for this phone under Phone connection on the computer"
    ),
    "unsupported_task": "the computer does not take this kind of task",
    "unknown_session": "the conversation no longer exists on the computer",
    "no_workspace": "no folder is open on the computer; open one there first",
}


def refused(error: RemoteHTTPError) -> bool:
    """A definite no from the desktop (not a busy or lost request)."""
    return 400 <= error.status_code < 500 and error.status_code not in {408, 429} or error.code == "no_workspace"


def refusal_reason(error: RemoteHTTPError) -> str:
    return _REFUSALS.get(error.code or "", str(error))


class MobileOutbox:
    def __init__(self, path: Path, connections: MobileConnections, *, on_finished=None):
        self.path = path
        self.connections = connections
        # Told about a handed-over task that finished on the other device (a notification).
        self.on_finished = on_finished
        self._lock = asyncio.Lock()
        with connection_database(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS mobile_outbox "
                "(delivery_id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, "
                "digest TEXT NOT NULL, host_id TEXT NOT NULL, payload TEXT NOT NULL, "
                "state TEXT NOT NULL, remote_task_id TEXT, result TEXT, error TEXT, "
                "created_at REAL NOT NULL, updated_at REAL NOT NULL, dispatch_api TEXT)"
            )
            columns = {row["name"] for row in db.execute("PRAGMA table_info(mobile_outbox)")}
            if "dispatch_api" not in columns:
                db.execute("ALTER TABLE mobile_outbox ADD COLUMN dispatch_api TEXT")
            # What the desktop says its running task is doing now (device link 2).
            if "activity" not in columns:
                db.execute("ALTER TABLE mobile_outbox ADD COLUMN activity TEXT")
            db.execute(
                "UPDATE mobile_outbox SET state='uncertain', "
                "error='interrupted during dispatch' WHERE state='sending'"
            )
            # Earlier mobile timeouts were recorded as pending after dispatch.
            db.execute(
                "UPDATE mobile_outbox SET state='uncertain', "
                "dispatch_api=COALESCE(dispatch_api,'mobile') WHERE state='pending' "
                "AND error='retry uses the same request id'"
            )

    def list(self):
        with connection_database(self.path) as db:
            rows = db.execute(
                "SELECT * FROM mobile_outbox "
                "WHERE state IN ('pending','sending','submitted','uncertain') "
                "OR delivery_id IN (SELECT delivery_id FROM mobile_outbox "
                "WHERE state IN ('completed','failed','cancelled') "
                "ORDER BY created_at DESC LIMIT 200) "
                "ORDER BY created_at DESC"
            ).fetchall()
        return [self._public(row) for row in rows]

    def _active(self):
        with connection_database(self.path) as db:
            rows = db.execute(
                "SELECT * FROM mobile_outbox "
                "WHERE state IN ('pending','sending','submitted','uncertain') "
                "ORDER BY created_at, delivery_id"
            ).fetchall()
        return [self._public(row) for row in rows]

    @staticmethod
    def _public(row):
        value = dict(row)
        value["payload"] = json.loads(value["payload"])
        value.pop("digest", None)
        return value

    def get(self, delivery_id):
        with connection_database(self.path) as db:
            row = db.execute(
                "SELECT * FROM mobile_outbox WHERE delivery_id=?", (delivery_id,)
            ).fetchone()
        if row is None:
            raise KeyError("unknown outgoing request")
        return self._public(row)

    def enqueue(self, payload):
        host = self.connections.get(payload.get("host_id"))
        request = parse_mobile_task_request(payload)
        request_id = payload.get("request_id") or str(uuid4())
        if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
            raise ValueError("invalid outgoing request id")
        document = {
            "session_id": request.session_id,
            "prompt": request.prompt,
            "model": request.model,
            "reasoning_effort": request.reasoning_effort,
            **acknowledgements(payload),
        }
        serialized = json.dumps(document, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256((host["host_id"] + serialized).encode()).hexdigest()
        now, delivery_id = time.time(), str(uuid4())
        with connection_database(self.path) as db:
            existing = db.execute(
                "SELECT * FROM mobile_outbox WHERE request_id=?", (request_id,)
            ).fetchone()
            if existing:
                if existing["digest"] != digest:
                    raise ValueError("request id already belongs to different content")
                return self._public(existing)
            db.execute(
                "INSERT INTO mobile_outbox "
                "(delivery_id,request_id,digest,host_id,payload,state,created_at,updated_at) "
                "VALUES (?,?,?,?,?,'pending',?,?)",
                (delivery_id, request_id, digest, host["host_id"], serialized, now, now),
            )
        return self.get(delivery_id)

    def record_submitted(self, host_id, request_id, payload, remote_task_id):
        """A task the desktop already accepted another way (a new conversation with its first
        prompt): kept here like a handed-over one, so its result comes back the same way."""
        host = self.connections.get(host_id)
        document = {
            "session_id": payload.get("session_id"),
            "prompt": payload.get("prompt"),
            "model": None,
            "reasoning_effort": None,
            **acknowledgements(payload),
        }
        serialized = json.dumps(document, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256((host["host_id"] + serialized).encode()).hexdigest()
        now, delivery_id = time.time(), str(uuid4())
        with connection_database(self.path) as db:
            existing = db.execute("SELECT * FROM mobile_outbox WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                return self._public(existing)
            db.execute(
                "INSERT INTO mobile_outbox (delivery_id,request_id,digest,host_id,payload,state,remote_task_id,"
                "created_at,updated_at,dispatch_api) VALUES (?,?,?,?,?,'submitted',?,?,?,'mobile')",
                (delivery_id, request_id, digest, host["host_id"], serialized, remote_task_id, now, now),
            )
        return self.get(delivery_id)

    def _update(
        self,
        delivery_id,
        state,
        *,
        remote_task_id=None,
        result=None,
        error=None,
        expected_state=None,
        activity=None,
    ):
        query = (
            "UPDATE mobile_outbox SET state=?, remote_task_id=COALESCE(?,remote_task_id), "
            "result=COALESCE(?,result), error=?, activity=?, updated_at=? WHERE delivery_id=?"
        )
        values = (state, remote_task_id, result, error, activity, time.time(), delivery_id)
        if expected_state is not None:
            query += " AND state=?"
            values += (expected_state,)
        with connection_database(self.path) as db:
            db.execute(query, values)
        return self.get(delivery_id)

    def _claim_send(self, delivery_id, expected_state, dispatch_api):
        with connection_database(self.path) as db:
            return (
                db.execute(
                    "UPDATE mobile_outbox SET state='sending', dispatch_api=?, "
                    "error=NULL, updated_at=? "
                    "WHERE delivery_id=? AND state=?",
                    (dispatch_api, time.time(), delivery_id, expected_state),
                ).rowcount
                == 1
            )

    async def send(self, delivery_id):
        async with self._lock:
            job = self.get(delivery_id)
            if job["state"] == "submitted":
                return await self.reconcile(delivery_id)
            host = self.connections.get(job["host_id"])
            mobile = host["api"] == "mobile"
            retrying = (
                job["state"] == "uncertain"
                and not job["remote_task_id"]
                and job["dispatch_api"] == "mobile"
                and mobile
            )
            if job["state"] != "pending" and not retrying:
                raise ValueError(
                    "only pending or unresolved idempotent mobile requests can be sent"
                )
            previous_state = job["state"]
            try:
                # A failed preflight leaves the job pending without an ambiguous write.
                await self.connections.request(host["host_id"], "GET", "/sessions")
            except (httpx.HTTPError, ValueError):
                return self._update(
                    delivery_id,
                    previous_state,
                    error="host is unavailable; retained locally",
                    expected_state=previous_state,
                )
            if not self._claim_send(delivery_id, previous_state, host["api"]):
                return self.get(delivery_id)
            payload = {key: value for key, value in job["payload"].items() if value is not None}
            route = (
                "/mobile/tasks"
                if mobile
                else f"/sessions/{quote(payload['session_id'], safe='')}/run"
            )
            if mobile:
                payload["request_id"] = job["request_id"]
            try:
                _, result = await self.connections.request(
                    host["host_id"], "POST", route, payload, timeout=300 if not mobile else 15
                )
                if mobile:
                    task = result.get("task")
                    task_id = task.get("task_id") if isinstance(task, dict) else None
                    if not isinstance(task_id, str) or not task_id:
                        raise ValueError("remote host did not return a task id")
                    return self._update(delivery_id, "submitted", remote_task_id=task_id)
                text = result.get("text")
                if not isinstance(text, str):
                    raise ValueError("remote host did not return a run result")
                return self._update(delivery_id, "completed", result=text[:65536])
            except (httpx.HTTPError, ValueError) as exc:
                if (
                    isinstance(exc, RemoteHTTPError)
                    and exc.status_code == 404
                    and previous_state == "pending"
                ):
                    return self._update(delivery_id, "failed", error=str(exc))
                if isinstance(exc, RemoteHTTPError) and mobile and refused(exc):
                    # The desktop answered and said no: sending again would get the same answer.
                    return self._update(delivery_id, "failed", error=refusal_reason(exc))
                return self._update(
                    delivery_id,
                    "uncertain",
                    error="response unavailable; reconcile before retry"
                    if not mobile
                    else "submission may have been accepted; reconcile uses the same request id",
                )

    async def reconcile(self, delivery_id):
        job = self.get(delivery_id)
        if not job["remote_task_id"]:
            if (
                job["state"] == "uncertain"
                and job["dispatch_api"] == "mobile"
                and self.connections.get(job["host_id"])["api"] == "mobile"
            ):
                return await self.send(delivery_id)
            return job
        try:
            _, document = await self.connections.request(
                job["host_id"], "GET", f"/mobile/tasks/{quote(job['remote_task_id'], safe='')}"
            )
        except (httpx.HTTPError, ValueError):
            return job
        task = document.get("task")
        if not isinstance(task, dict):
            return job
        state = task.get("state")
        target = {
            "succeeded": "completed",
            "failed": "failed",
            "cancelled": "cancelled",
            "interrupted": "uncertain",
        }.get(state, "submitted")
        # What the other device answered (a desktop sends its last reply) or why it failed.
        result = task.get("result") if target == "completed" and isinstance(task.get("result"), str) else None
        error = task.get("error") if target != "completed" and isinstance(task.get("error"), str) else None
        activity = task.get("activity") if target == "submitted" and isinstance(task.get("activity"), str) else None
        updated = self._update(
            delivery_id,
            target,
            result=result[:65536] if result else None,
            error=error[:2000] if error else None,
            activity=" ".join(activity.split())[:120] if activity else None,
        )
        if target in {"completed", "failed", "cancelled"} and job["state"] != target and self.on_finished:
            try:
                self.on_finished(updated)
            except Exception:
                pass  # a notification that cannot be shown must not undo the reconcile
        return updated

    def abandon(self, host_id, reason="the computer was removed before the result came back"):
        """Requests still waiting on a device that is being removed: they end here, with the reason
        (they would otherwise wait for a device that is gone, and keep it from being removed)."""
        with connection_database(self.path) as db:
            return db.execute(
                "UPDATE mobile_outbox SET state='failed', error=?, activity=NULL, updated_at=? "
                "WHERE host_id=? AND state IN ('pending','sending','submitted','uncertain')",
                (reason, time.time(), host_id),
            ).rowcount

    def unsettled(self, host_id):
        with connection_database(self.path) as db:
            return db.execute(
                "SELECT COUNT(*) FROM mobile_outbox WHERE host_id=? "
                "AND state IN ('pending','sending','submitted','uncertain')",
                (host_id,),
            ).fetchone()[0]

    def cancel(self, delivery_id):
        job = self.get(delivery_id)
        if job["state"] != "pending":
            raise ValueError("only an unsent request can be cancelled")
        cancelled = self._update(delivery_id, "cancelled", expected_state="pending")
        if cancelled["state"] != "cancelled":
            raise ValueError("only an unsent request can be cancelled")
        return cancelled

    async def run(self):
        while True:
            await self.run_once()
            await asyncio.sleep(20)

    async def run_once(self):
        try:
            active = self._active()
            known = {host["host_id"] for host in self.connections.list()}
        except sqlite3.Error:
            return  # a locked or full database: the next pass tries again
        for entry in active:
            if entry["host_id"] not in known:
                # Its device was removed (by an older version, which left these behind).
                self.abandon(entry["host_id"])
                continue
            try:
                job = self.get(entry["delivery_id"])
                if job["state"] == "pending":
                    await self.send(job["delivery_id"])
                elif job["state"] in {"submitted", "uncertain"}:
                    await self.reconcile(job["delivery_id"])
            except asyncio.CancelledError:
                raise
            except Exception:
                continue  # one request that cannot be handled now must not stop the others
