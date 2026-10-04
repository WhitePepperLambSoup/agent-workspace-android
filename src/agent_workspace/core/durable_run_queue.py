"""Durable run queue projected from append-only domain events.

The queue intentionally uses the same event store as sessions, so queued work
survives process restarts without a new schema. Claims are optimistic; callers
reconcile stale claimed tasks after restart using ``claim``/``fail``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

from agent_workspace.application.ports import EventStore
from agent_workspace.core.events import Event
from agent_workspace.core.models import Autonomy, Mode
from agent_workspace.core.session import Session


class RunQueueStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class RunQueueTask:
    id: str
    workspace: str
    prompt: str
    model: str
    status: RunQueueStatus
    claim_token: str | None = None
    error: str | None = None
    created_at: str = ""
    updated_at: str = ""
    priority: int = 0
    owner: str | None = None
    lease_until: str | None = None
    attempt: int = 0

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workspace": self.workspace,
            "prompt": self.prompt,
            "model": self.model,
            "status": self.status.value,
            "claim_token": self.claim_token,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "priority": self.priority,
            "owner": self.owner,
            "lease_until": self.lease_until,
            "attempt": self.attempt,
        }


class RunQueueError(ValueError):
    pass


class DurableRunQueue:
    """Create, claim, settle, and project run queue tasks from events."""

    def __init__(self, store: EventStore, *, queue_session_id: str = "run-queue") -> None:
        self._store = store
        self.queue_session_id = queue_session_id
        self._ensure_queue_session()

    def _ensure_queue_session(self) -> None:
        if self._store.get_session(self.queue_session_id) is None:
            self._store.create_session(
                Session(
                    ".",
                    mode=Mode.TASK,
                    autonomy=Autonomy.WORKSPACE,
                    id=self.queue_session_id,
                    title="Durable run queue",
                )
            )

    async def enqueue(
        self,
        workspace: str,
        prompt: str,
        model: str,
        *,
        task_id: str | None = None,
        priority: int = 0,
        owner: str | None = None,
    ) -> RunQueueTask:
        resolved_id = task_id or str(uuid4())
        self._validate_id(resolved_id)
        prompt = self._validate_prompt(prompt)
        workspace = self._validate_workspace(workspace)
        self._validate_model(model)
        priority = self._validate_priority(priority)
        owner = self._validate_owner(owner)
        now = datetime.now(UTC).isoformat()
        existing = self.get(resolved_id)
        if existing is not None:
            raise RunQueueError(f"run queue task already exists: {resolved_id}")
        self._store.append(
            Event(
                session_id=self.queue_session_id,
                type="run_queue.enqueued",
                data={
                    "task_id": resolved_id,
                    "workspace": workspace,
                    "prompt": prompt,
                    "model": model,
                    "created_at": now,
                    "priority": priority,
                    "owner": owner,
                },
            )
        )
        return RunQueueTask(
            resolved_id,
            workspace,
            prompt,
            model,
            RunQueueStatus.PENDING,
            created_at=now,
            updated_at=now,
            priority=priority,
            owner=owner,
        )

    async def claim(
        self,
        task_id: str,
        *,
        worker_id: str = "default",
        lease_seconds: int = 60,
    ) -> RunQueueTask:
        task = self.get(task_id)
        if task is None:
            raise RunQueueError(f"unknown run queue task: {task_id}")
        if task.status is not RunQueueStatus.PENDING:
            raise RunQueueError(f"run queue task is not pending: {task_id}")
        worker_id = self._validate_owner(worker_id) or "default"
        lease_seconds = self._validate_lease_seconds(lease_seconds)
        token = str(uuid4())
        now = datetime.now(UTC).isoformat()
        lease_until = _add_seconds(now, lease_seconds)
        self._store.append(
            Event(
                session_id=self.queue_session_id,
                type="run_queue.claimed",
                data={
                    "task_id": task_id,
                    "claim_token": token,
                    "worker_id": worker_id,
                    "lease_until": lease_until,
                    "attempt": task.attempt + 1,
                    "updated_at": now,
                },
            )
        )
        return RunQueueTask(
            task.id,
            task.workspace,
            task.prompt,
            task.model,
            RunQueueStatus.CLAIMED,
            token,
            None,
            task.created_at,
            now,
            task.priority,
            worker_id,
            lease_until,
            task.attempt + 1,
        )

    async def claim_next(
        self,
        *,
        worker_id: str = "default",
        lease_seconds: int = 60,
        workspace: str | None = None,
    ) -> RunQueueTask | None:
        """Claim the highest-priority pending task for a worker.

        Reclaiming expired leases before selecting the next task makes a
        restarted worker able to make progress without a separate repair job.
        The event log remains the source of truth if two workers race; a
        caller that loses the race can simply call this method again.
        """

        await self.reclaim_stale()
        pending = self.list(status=RunQueueStatus.PENDING, workspace=workspace)
        if not pending:
            return None
        for task in pending:
            try:
                return await self.claim(
                    task.id,
                    worker_id=worker_id,
                    lease_seconds=lease_seconds,
                )
            except RunQueueError as exc:
                if "not pending" not in str(exc):
                    raise
        return None

    async def heartbeat(
        self,
        task_id: str,
        claim_token: str,
        *,
        lease_seconds: int = 60,
    ) -> RunQueueTask:
        """Extend an active worker lease without changing its attempt."""

        task = self._settle_checked(task_id, claim_token)
        lease_seconds = self._validate_lease_seconds(lease_seconds)
        now = datetime.now(UTC).isoformat()
        lease_until = _add_seconds(now, lease_seconds)
        self._store.append(
            Event(
                session_id=self.queue_session_id,
                type="run_queue.heartbeat",
                data={
                    "task_id": task_id,
                    "claim_token": claim_token,
                    "worker_id": task.owner,
                    "lease_until": lease_until,
                    "updated_at": now,
                },
            )
        )
        return RunQueueTask(
            task.id,
            task.workspace,
            task.prompt,
            task.model,
            RunQueueStatus.CLAIMED,
            task.claim_token,
            task.error,
            task.created_at,
            now,
            task.priority,
            task.owner,
            lease_until,
            task.attempt,
        )

    async def reclaim_stale(self, *, now: datetime | None = None) -> int:
        """Return expired claims to the pending state and invalidate tokens."""

        current = now or datetime.now(UTC)
        reclaimed = 0
        for task in self.list(status=RunQueueStatus.CLAIMED):
            if not _lease_expired(task.lease_until, current):
                continue
            updated = current.isoformat()
            self._store.append(
                Event(
                    session_id=self.queue_session_id,
                    type="run_queue.requeued",
                    data={
                        "task_id": task.id,
                        "reason": "lease_expired",
                        "previous_claim_token": task.claim_token,
                        "previous_worker_id": task.owner,
                        "updated_at": updated,
                    },
                )
            )
            reclaimed += 1
        return reclaimed

    async def retry(self, task_id: str) -> RunQueueTask:
        """Requeue a failed or cancelled task while preserving its identity."""

        task = self.get(task_id)
        if task is None:
            raise RunQueueError(f"unknown run queue task: {task_id}")
        if task.status is RunQueueStatus.PENDING:
            return task
        if task.status not in {RunQueueStatus.FAILED, RunQueueStatus.CANCELLED}:
            raise RunQueueError(f"run queue task is not retryable: {task_id}")
        now = datetime.now(UTC).isoformat()
        self._store.append(
            Event(
                session_id=self.queue_session_id,
                type="run_queue.requeued",
                data={
                    "task_id": task.id,
                    "reason": "manual_retry",
                    "previous_status": task.status.value,
                    "updated_at": now,
                },
            )
        )
        return RunQueueTask(
            task.id,
            task.workspace,
            task.prompt,
            task.model,
            RunQueueStatus.PENDING,
            None,
            None,
            task.created_at,
            now,
            task.priority,
            None,
            None,
            task.attempt,
        )

    async def complete(self, task_id: str, claim_token: str) -> RunQueueTask:
        task = self._settle_checked(task_id, claim_token)
        now = datetime.now(UTC).isoformat()
        self._store.append(
            Event(
                session_id=self.queue_session_id,
                type="run_queue.completed",
                data={"task_id": task_id, "claim_token": claim_token, "updated_at": now},
            )
        )
        return RunQueueTask(
            task.id,
            task.workspace,
            task.prompt,
            task.model,
            RunQueueStatus.COMPLETED,
            task.claim_token,
            None,
            task.created_at,
            now,
            task.priority,
            task.owner,
            None,
            task.attempt,
        )

    async def fail(self, task_id: str, claim_token: str, error: str) -> RunQueueTask:
        task = self._settle_checked(task_id, claim_token)
        now = datetime.now(UTC).isoformat()
        self._store.append(
            Event(
                session_id=self.queue_session_id,
                type="run_queue.failed",
                data={
                    "task_id": task_id,
                    "claim_token": claim_token,
                    "error": error[:2000],
                    "updated_at": now,
                },
            )
        )
        return RunQueueTask(
            task.id,
            task.workspace,
            task.prompt,
            task.model,
            RunQueueStatus.FAILED,
            task.claim_token,
            error[:2000],
            task.created_at,
            now,
            task.priority,
            task.owner,
            None,
            task.attempt,
        )

    async def cancel(self, task_id: str) -> RunQueueTask:
        task = self.get(task_id)
        if task is None:
            raise RunQueueError(f"unknown run queue task: {task_id}")
        if task.status in {
            RunQueueStatus.COMPLETED,
            RunQueueStatus.FAILED,
            RunQueueStatus.CANCELLED,
        }:
            raise RunQueueError(f"run queue task is already terminal: {task_id}")
        now = datetime.now(UTC).isoformat()
        self._store.append(
            Event(
                session_id=self.queue_session_id,
                type="run_queue.cancelled",
                data={"task_id": task_id, "updated_at": now},
            )
        )
        return RunQueueTask(
            task.id,
            task.workspace,
            task.prompt,
            task.model,
            RunQueueStatus.CANCELLED,
            task.claim_token,
            task.error,
            task.created_at,
            now,
            task.priority,
            None,
            None,
            task.attempt,
        )

    def _settle_checked(self, task_id: str, claim_token: str) -> RunQueueTask:
        task = self.get(task_id)
        if task is None:
            raise RunQueueError(f"unknown run queue task: {task_id}")
        if task.status is not RunQueueStatus.CLAIMED:
            raise RunQueueError(f"run queue task is not claimed: {task_id}")
        if task.claim_token != claim_token:
            raise RunQueueError(f"run queue task claim token is stale: {task_id}")
        if _lease_expired(task.lease_until, datetime.now(UTC)):
            raise RunQueueError(f"run queue task lease expired: {task_id}")
        return task

    def get(self, task_id: str) -> RunQueueTask | None:
        return {task.id: task for task in self.list()}.get(task_id)

    def list(
        self,
        *,
        status: RunQueueStatus | None = None,
        workspace: str | None = None,
    ) -> list[RunQueueTask]:
        if not self._store.list_events(self.queue_session_id):
            return []
        tasks: dict[str, dict[str, Any]] = {}
        for event in self._store.list_events(self.queue_session_id):
            data = event.data
            task_id = data.get("task_id")
            if not isinstance(task_id, str):
                continue
            if event.type == "run_queue.enqueued":
                if _enqueue_payload(data):
                    tasks[task_id] = {
                        "id": task_id,
                        "workspace": data["workspace"],
                        "prompt": data["prompt"],
                        "model": data["model"],
                        "status": RunQueueStatus.PENDING,
                        "claim_token": None,
                        "error": None,
                        "created_at": data["created_at"],
                        "updated_at": data["created_at"],
                        "priority": data.get("priority", 0),
                        "owner": data.get("owner"),
                        "lease_until": None,
                        "attempt": 0,
                    }
            elif event.type == "run_queue.claimed" and task_id in tasks:
                token = data.get("claim_token")
                updated = data.get("updated_at")
                if isinstance(token, str) and isinstance(updated, str):
                    tasks[task_id]["status"] = RunQueueStatus.CLAIMED
                    tasks[task_id]["claim_token"] = token
                    tasks[task_id]["owner"] = data.get("worker_id")
                    tasks[task_id]["lease_until"] = data.get("lease_until")
                    tasks[task_id]["attempt"] = _nonnegative_int(
                        data.get("attempt"), tasks[task_id]["attempt"] + 1
                    )
                    tasks[task_id]["updated_at"] = updated
            elif event.type == "run_queue.heartbeat" and task_id in tasks:
                updated = data.get("updated_at")
                lease_until = data.get("lease_until")
                if isinstance(updated, str) and isinstance(lease_until, str):
                    tasks[task_id]["lease_until"] = lease_until
                    tasks[task_id]["updated_at"] = updated
            elif event.type == "run_queue.completed" and task_id in tasks:
                updated = data.get("updated_at")
                if isinstance(updated, str):
                    tasks[task_id]["status"] = RunQueueStatus.COMPLETED
                    tasks[task_id]["lease_until"] = None
                    tasks[task_id]["updated_at"] = updated
            elif event.type == "run_queue.failed" and task_id in tasks:
                updated = data.get("updated_at")
                if isinstance(updated, str):
                    tasks[task_id]["status"] = RunQueueStatus.FAILED
                    tasks[task_id]["error"] = str(data.get("error") or "")
                    tasks[task_id]["lease_until"] = None
                    tasks[task_id]["updated_at"] = updated
            elif event.type == "run_queue.cancelled" and task_id in tasks:
                updated = data.get("updated_at")
                if isinstance(updated, str):
                    tasks[task_id]["status"] = RunQueueStatus.CANCELLED
                    tasks[task_id]["lease_until"] = None
                    tasks[task_id]["owner"] = None
                    tasks[task_id]["updated_at"] = updated
            elif event.type == "run_queue.requeued" and task_id in tasks:
                updated = data.get("updated_at")
                if isinstance(updated, str):
                    tasks[task_id]["status"] = RunQueueStatus.PENDING
                    tasks[task_id]["claim_token"] = None
                    tasks[task_id]["owner"] = None
                    tasks[task_id]["lease_until"] = None
                    if data.get("reason") == "manual_retry":
                        tasks[task_id]["error"] = None
                    tasks[task_id]["updated_at"] = updated
        result = [
            RunQueueTask(
                id=item["id"],
                workspace=item["workspace"],
                prompt=item["prompt"],
                model=item["model"],
                status=item["status"],
                claim_token=item["claim_token"],
                error=item["error"],
                created_at=item["created_at"],
                updated_at=item["updated_at"],
                priority=_nonnegative_int(item.get("priority"), 0),
                owner=item.get("owner") if isinstance(item.get("owner"), str) else None,
                lease_until=(
                    item.get("lease_until") if isinstance(item.get("lease_until"), str) else None
                ),
                attempt=_nonnegative_int(item.get("attempt"), 0),
            )
            for item in tasks.values()
            if (status is None or item["status"] is status)
            and (workspace is None or item["workspace"] == workspace)
        ]
        result.sort(key=lambda task: (-task.priority, task.created_at, task.id))
        return result

    @staticmethod
    def _validate_id(value: str) -> None:
        if not value or len(value) > 128:
            raise RunQueueError("run queue task id must be 1-128 characters")

    @staticmethod
    def _validate_prompt(value: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 128 * 1024:
            raise RunQueueError("run queue prompt must be 1-131072 characters")
        return value.strip()

    @staticmethod
    def _validate_workspace(value: str) -> str:
        if not isinstance(value, str) or not value or len(value) > 32767:
            raise RunQueueError("run queue workspace is invalid")
        return value

    @staticmethod
    def _validate_model(value: str) -> None:
        if not isinstance(value, str) or not value or len(value) > 200:
            raise RunQueueError("run queue model is invalid")

    @staticmethod
    def _validate_priority(value: int) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not -100_000 <= value <= 100_000
        ):
            raise RunQueueError("run queue priority must be an integer from -100000 to 100000")
        return value

    @staticmethod
    def _validate_owner(value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            raise RunQueueError("run queue worker id is invalid")
        return value.strip()

    @staticmethod
    def _validate_lease_seconds(value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 86_400:
            raise RunQueueError("run queue lease must be from 1 to 86400 seconds")
        return value


def _enqueue_payload(data: dict[str, Any]) -> bool:
    return (
        isinstance(data.get("workspace"), str)
        and bool(data.get("workspace"))
        and isinstance(data.get("prompt"), str)
        and bool(data.get("prompt"))
        and isinstance(data.get("model"), str)
        and bool(data.get("model"))
        and isinstance(data.get("created_at"), str)
    )


def _nonnegative_int(value: object, fallback: int) -> int:
    return (
        value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else fallback
    )


def _add_seconds(timestamp: str, seconds: int) -> str:
    return (datetime.fromisoformat(timestamp) + timedelta(seconds=seconds)).isoformat()


def _lease_expired(lease_until: str | None, now: datetime) -> bool:
    if not lease_until:
        return True
    try:
        parsed = datetime.fromisoformat(lease_until)
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed <= now


__all__ = [
    "DurableRunQueue",
    "RunQueueError",
    "RunQueueStatus",
    "RunQueueTask",
]
