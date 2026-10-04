"""Background Task Center Service and Persistence.

Provides a unified model and controller for background tasks, durable run queue
tasks, scheduled tasks, and subagents with status tracking, cancellation,
and retry capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent_workspace.application.ports import EventStore
from agent_workspace.core.durable_run_queue import (
    DurableRunQueue,
    RunQueueError,
    RunQueueStatus,
)


class TaskKind(StrEnum):
    QUEUE = "queue"
    SCHEDULED = "scheduled"
    SUBAGENT = "subagent"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class TaskItem:
    id: str
    kind: TaskKind
    title: str
    workspace: str
    model: str
    status: TaskStatus
    progress: str = ""
    error: str | None = None
    created_at: str = ""
    updated_at: str = ""
    cost_usd: float | None = None
    priority: int = 0

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "title": self.title,
            "workspace": self.workspace,
            "model": self.model,
            "status": self.status.value,
            "progress": self.progress,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "cost_usd": self.cost_usd,
            "priority": self.priority,
        }


class TaskCenterService:
    """Aggregates and manages background tasks across queue, scheduler, and agents."""

    def __init__(self, store: EventStore, workspace: Path | str | None = None) -> None:
        self._store = store
        self._workspace = str(Path(workspace).resolve()) if workspace else "."
        self._queue = DurableRunQueue(store)
        self._adhoc_tasks: dict[str, TaskItem] = {}

    def list_tasks(self, status_filter: TaskStatus | None = None) -> list[TaskItem]:
        """List all tasks, converting durable queue tasks and adhoc tasks."""
        items: list[TaskItem] = []

        # 1. Project tasks from DurableRunQueue
        queue_tasks = self._queue.list()
        for q in queue_tasks:
            status = self._map_queue_status(q.status)
            if status_filter is not None and status != status_filter:
                continue
            items.append(
                TaskItem(
                    id=q.id,
                    kind=TaskKind.QUEUE,
                    title=q.prompt,
                    workspace=q.workspace,
                    model=q.model,
                    status=status,
                    error=q.error,
                    created_at=q.created_at,
                    updated_at=q.updated_at,
                    priority=q.priority,
                )
            )

        # 2. Add ad-hoc registered tasks (e.g. scheduled or subagents)
        for task in self._adhoc_tasks.values():
            if status_filter is not None and task.status != status_filter:
                continue
            items.append(task)

        items.sort(key=lambda t: t.updated_at or t.created_at, reverse=True)
        return items

    async def enqueue_task(
        self,
        prompt: str,
        model: str,
        *,
        workspace: str | None = None,
        task_id: str | None = None,
        priority: int = 0,
    ) -> TaskItem:
        """Enqueue a new persistent task."""
        ws = workspace or self._workspace
        q_task = await self._queue.enqueue(
            ws,
            prompt,
            model,
            task_id=task_id,
            priority=priority,
        )
        return TaskItem(
            id=q_task.id,
            kind=TaskKind.QUEUE,
            title=q_task.prompt,
            workspace=q_task.workspace,
            model=q_task.model,
            status=TaskStatus.PENDING,
            created_at=q_task.created_at,
            updated_at=q_task.updated_at,
            priority=q_task.priority,
        )

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel an in-flight or pending task."""
        if task_id in self._adhoc_tasks:
            current = self._adhoc_tasks[task_id]
            self._adhoc_tasks[task_id] = TaskItem(
                id=current.id,
                kind=current.kind,
                title=current.title,
                workspace=current.workspace,
                model=current.model,
                status=TaskStatus.CANCELLED,
                progress="Cancelled by user",
                error=current.error,
                created_at=current.created_at,
                updated_at=datetime.now(UTC).isoformat(),
            )
            return True

        q_task = self._queue.get(task_id)
        if q_task is not None and q_task.status in {RunQueueStatus.PENDING, RunQueueStatus.CLAIMED}:
            try:
                await self._queue.cancel(task_id)
                return True
            except Exception:
                return False
        return False

    async def retry_task(self, task_id: str) -> TaskItem | None:
        """Retry a failed or cancelled queue task while preserving its ID."""
        q_task = self._queue.get(task_id)
        if q_task is not None:
            try:
                retried = await self._queue.retry(task_id)
            except RunQueueError:
                return None
            return TaskItem(
                id=retried.id,
                kind=TaskKind.QUEUE,
                title=retried.prompt,
                workspace=retried.workspace,
                model=retried.model,
                status=self._map_queue_status(retried.status),
                error=retried.error,
                created_at=retried.created_at,
                updated_at=retried.updated_at,
                priority=retried.priority,
            )

        if task_id in self._adhoc_tasks:
            adhoc = self._adhoc_tasks[task_id]
            new_id = f"{task_id}-retry-{uuid4().hex[:6]}"
            return await self.enqueue_task(
                prompt=adhoc.title,
                model=adhoc.model,
                workspace=adhoc.workspace,
                task_id=new_id,
            )
        return None

    def register_adhoc_task(self, task: TaskItem) -> None:
        """Register a running subagent or scheduled job."""
        self._adhoc_tasks[task.id] = task

    @staticmethod
    def _map_queue_status(status: RunQueueStatus) -> TaskStatus:
        if status == RunQueueStatus.PENDING:
            return TaskStatus.PENDING
        if status == RunQueueStatus.CLAIMED:
            return TaskStatus.RUNNING
        if status == RunQueueStatus.COMPLETED:
            return TaskStatus.COMPLETED
        if status == RunQueueStatus.FAILED:
            return TaskStatus.FAILED
        if status == RunQueueStatus.CANCELLED:
            return TaskStatus.CANCELLED
        return TaskStatus.PENDING


__all__ = [
    "TaskCenterService",
    "TaskItem",
    "TaskKind",
    "TaskStatus",
]
