"""Persist handoffs before sending and never replay an ambiguous legacy run."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import httpx
from mobile_connections import MobileConnections, RemoteHTTPError, connection_database
from mobile_protocol import parse_mobile_task_request


class MobileOutbox:
    def __init__(self, path: Path, connections: MobileConnections):
        self.path = path
        self.connections = connections
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

    def _update(
        self,
        delivery_id,
        state,
        *,
        remote_task_id=None,
        result=None,
        error=None,
        expected_state=None,
    ):
        query = (
            "UPDATE mobile_outbox SET state=?, remote_task_id=COALESCE(?,remote_task_id), "
            "result=COALESCE(?,result), error=?, updated_at=? WHERE delivery_id=?"
        )
        values = (state, remote_task_id, result, error, time.time(), delivery_id)
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
        return self._update(delivery_id, target)

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
            for entry in self._active():
                try:
                    job = self.get(entry["delivery_id"])
                    if job["state"] == "pending":
                        await self.send(job["delivery_id"])
                    elif job["state"] in {"submitted", "uncertain"}:
                        await self.reconcile(job["delivery_id"])
                except (KeyError, ValueError, httpx.HTTPError):
                    continue
            await asyncio.sleep(20)
