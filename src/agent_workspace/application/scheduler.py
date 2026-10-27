from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent_workspace.core.scheduler import (
    CronSchedule,
    OneTimeTask,
    OneTimeTaskScheduler,
    ScheduledTask,
    ScheduleError,
    TaskScheduler,
)
from agent_workspace.tools.paths import StrPath

_LOGGER = logging.getLogger(__name__)


class ScheduledTaskConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ScheduledTaskDefinition:
    id: str
    prompt: str
    cron: CronSchedule | None = None
    at: datetime | None = None


def load_scheduled_tasks(workspace: StrPath) -> tuple[ScheduledTaskDefinition, ...]:
    path = Path(workspace) / ".agent" / "schedule.toml"
    if not path.is_file():
        return ()
    try:
        with path.open("rb") as stream:
            raw: object = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ScheduledTaskConfigError(f"cannot read schedule file {path}: {exc}") from None
    if not isinstance(raw, dict) or not isinstance(raw.get("tasks"), list):
        raise ScheduledTaskConfigError(f"schedule file {path} must declare a [[tasks]] list")
    tasks: list[ScheduledTaskDefinition] = []
    for entry in raw["tasks"]:
        if not isinstance(entry, dict):
            raise ScheduledTaskConfigError("schedule task entries must be tables")
        task_id = entry.get("id")
        cron_raw = entry.get("cron")
        at_raw = entry.get("at")
        prompt = entry.get("prompt")
        if (
            not isinstance(task_id, str)
            or not task_id
            or len(task_id) > 128
            or (cron_raw is not None and at_raw is not None)
            or (cron_raw is None and at_raw is None)
            or not isinstance(prompt, str)
            or not prompt.strip()
            or len(prompt) > 128 * 1024
        ):
            raise ScheduledTaskConfigError(
                "schedule file contains an invalid task entry; each task needs "
                "exactly one of cron or at"
            )
        cron: CronSchedule | None = None
        at: datetime | None = None
        if cron_raw is not None:
            if not isinstance(cron_raw, str):
                raise ScheduledTaskConfigError("schedule task cron must be a string")
            try:
                cron = CronSchedule.parse(cron_raw)
            except ScheduleError as exc:
                raise ScheduledTaskConfigError(
                    f"schedule task {task_id!r} has an invalid cron expression: {exc}"
                ) from None
        if at_raw is not None:
            if not isinstance(at_raw, str):
                raise ScheduledTaskConfigError("schedule task 'at' must be an ISO timestamp")
            try:
                at = datetime.fromisoformat(at_raw)
            except ValueError as exc:
                raise ScheduledTaskConfigError(
                    f"schedule task {task_id!r} has an invalid 'at' timestamp: {exc}"
                ) from None
            if at.tzinfo is None:
                raise ScheduledTaskConfigError(
                    f"schedule task {task_id!r} 'at' must be timezone-aware"
                )
        if any(task.id == task_id for task in tasks):
            raise ScheduledTaskConfigError(f"schedule task id {task_id!r} is duplicated")
        tasks.append(
            ScheduledTaskDefinition(
                id=task_id,
                prompt=prompt.strip(),
                cron=cron,
                at=at,
            )
        )
    return tuple(tasks)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class TaskRunRecord:
    task_id: str
    trigger_at: str
    state: str  # "claimed" | "running" | "completed" | "failed" | "retry"
    created_at: str
    updated_at: str
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "trigger_at": self.trigger_at,
            "state": self.state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskRunRecord:
        return cls(
            task_id=str(data["task_id"]),
            trigger_at=str(data["trigger_at"]),
            state=str(data.get("state", "completed")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            error=data.get("error"),
            retry_count=int(data.get("retry_count", 0)),
            max_retries=int(data.get("max_retries", 3)),
        )


class ScheduledTaskStateStore:
    """Persistent storage for scheduled task execution records across restarts."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._path = path
        self._now = utc_now if now is None else now
        self._records: dict[str, TaskRunRecord] = {}
        self._load()

    def _key(self, task_id: str, trigger_at: str) -> str:
        return f"{task_id}::{trigger_at}"

    def _load(self) -> None:
        if self._path is None or not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                modified = False
                for k, v in raw.items():
                    if isinstance(v, dict):
                        rec = TaskRunRecord.from_dict(v)
                        # Crash recovery: if a previous process died while running/claimed,
                        # transition to retry if allowed, else failed
                        if rec.state in ("running", "claimed"):
                            if rec.retry_count < rec.max_retries:
                                rec.state = "retry"
                                rec.retry_count += 1
                                rec.error = "interrupted by restart"
                            else:
                                rec.state = "failed"
                                rec.error = "interrupted by restart and max retries exceeded"
                            rec.updated_at = self._now().isoformat()
                            modified = True
                        self._records[k] = rec
                if modified:
                    self._save()
        except Exception:
            _LOGGER.exception("failed to load schedule state from %s", self._path)

    def _save(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {k: v.to_dict() for k, v in self._records.items()}
            content = json.dumps(data, indent=2, ensure_ascii=False)
            temp_file = self._path.with_name(f"{self._path.name}.tmp.{uuid4().hex}")
            temp_file.write_text(content, encoding="utf-8")
            temp_file.replace(self._path)
        except Exception:
            _LOGGER.exception("failed to save schedule state to %s", self._path)

    def get(self, task_id: str, trigger_at: str) -> TaskRunRecord | None:
        return self._records.get(self._key(task_id, trigger_at))

    def claim(self, task_id: str, trigger_at: str, max_retries: int = 3) -> bool:
        key = self._key(task_id, trigger_at)
        existing = self._records.get(key)
        now_str = self._now().isoformat()
        if existing is not None:
            if existing.state == "completed":
                return False
            if existing.state == "failed":
                return False
            if existing.state in ("running", "claimed"):
                return False
            if existing.state == "retry":
                existing.state = "running"
                existing.updated_at = now_str
                self._save()
                return True
        rec = TaskRunRecord(
            task_id=task_id,
            trigger_at=trigger_at,
            state="running",
            created_at=now_str,
            updated_at=now_str,
            max_retries=max_retries,
        )
        self._records[key] = rec
        self._save()
        return True

    def mark_completed(self, task_id: str, trigger_at: str) -> None:
        key = self._key(task_id, trigger_at)
        existing = self._records.get(key)
        now_str = self._now().isoformat()
        if existing is None:
            existing = TaskRunRecord(
                task_id=task_id,
                trigger_at=trigger_at,
                state="completed",
                created_at=now_str,
                updated_at=now_str,
            )
            self._records[key] = existing
        else:
            existing.state = "completed"
            existing.error = None
            existing.updated_at = now_str
        self._save()

    def mark_failed(self, task_id: str, trigger_at: str, error: str) -> None:
        key = self._key(task_id, trigger_at)
        existing = self._records.get(key)
        now_str = self._now().isoformat()
        if existing is None:
            existing = TaskRunRecord(
                task_id=task_id,
                trigger_at=trigger_at,
                state="failed",
                created_at=now_str,
                updated_at=now_str,
                error=error,
            )
            self._records[key] = existing
        else:
            if existing.retry_count < existing.max_retries:
                existing.state = "retry"
                existing.retry_count += 1
            else:
                existing.state = "failed"
            existing.error = error
            existing.updated_at = now_str
        self._save()

    def completed_one_time_task_ids(self) -> set[str]:
        return {rec.task_id for rec in self._records.values() if rec.state == "completed"}

    def get_pending_retries(self) -> list[TaskRunRecord]:
        return [rec for rec in self._records.values() if rec.state == "retry"]


class ScheduledTaskHost:
    """Runs workspace-declared scheduled agent prompts on the runtime loop."""

    def __init__(
        self,
        tasks: tuple[ScheduledTaskDefinition, ...],
        run_prompt: Callable[[str], Any],
        *,
        now: Callable[[], datetime] | None = None,
        poll_seconds: float = 30.0,
        state_store: ScheduledTaskStateStore | None = None,
        state_path: Path | None = None,
        max_concurrency: int = 4,
    ) -> None:
        self._now = utc_now if now is None else now
        self._task_defs = {task.id: task for task in tasks}
        if state_store is not None:
            self._state_store = state_store
        elif state_path is not None:
            self._state_store = ScheduledTaskStateStore(state_path, now=self._now)
        else:
            self._state_store = ScheduledTaskStateStore(None, now=self._now)

        completed_ids = self._state_store.completed_one_time_task_ids()
        self._scheduler = TaskScheduler(
            (
                ScheduledTask(
                    id=task.id,
                    cron=task.cron,
                    prompt=task.prompt,
                )
                for task in tasks
                if task.cron is not None
            ),
            now=self._now,
        )
        self._one_time_scheduler = OneTimeTaskScheduler(
            (
                OneTimeTask(
                    id=task.id,
                    at=task.at,
                    prompt=task.prompt,
                )
                for task in tasks
                if task.at is not None
            ),
            now=self._now,
            completed_ids=completed_ids,
        )
        self._run_prompt = run_prompt
        self._poll_seconds = poll_seconds
        self._task: asyncio.Task[None] | None = None
        self._active_tasks: set[asyncio.Task[None]] = set()
        self._semaphore = asyncio.Semaphore(max_concurrency)

    @property
    def state_store(self) -> ScheduledTaskStateStore:
        return self._state_store

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop(), name="agent-workspace-scheduler")

    async def aclose(self) -> None:
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if self._active_tasks:
            for active in list(self._active_tasks):
                active.cancel()
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
            self._active_tasks.clear()

    async def _loop(self) -> None:
        while True:
            try:
                self._dispatch_due()
            except Exception:
                # One failed pass (a state file that could not be read or written) must not
                # stop every later schedule; the next pass tries again.
                _LOGGER.exception("scheduled task pass failed")
            await asyncio.sleep(self._poll_seconds)

    def _dispatch_due(self) -> None:
        # Check pending retries from restart / failure
        for record in self._state_store.get_pending_retries():
            if record.task_id in self._task_defs:
                task_def = self._task_defs[record.task_id]
                if self._state_store.claim(record.task_id, record.trigger_at, record.max_retries):
                    self._dispatch(task_def.id, record.trigger_at, task_def.prompt)

        # Check cron triggers
        due = self._scheduler.due()
        for cron_task, trigger in due:
            trigger_iso = trigger.isoformat()
            if self._state_store.claim(cron_task.id, trigger_iso):
                self._dispatch(cron_task.id, trigger_iso, cron_task.prompt)

        # Check one-time triggers
        for one_time_task, trigger in self._one_time_scheduler.due():
            trigger_iso = trigger.isoformat()
            if self._state_store.claim(one_time_task.id, trigger_iso):
                self._dispatch(one_time_task.id, trigger_iso, one_time_task.prompt)

    def _dispatch(self, task_id: str, trigger_at: str, prompt: str) -> None:
        task = asyncio.create_task(
            self._run_task(task_id, trigger_at, prompt),
            name=f"scheduled-task-{task_id}",
        )
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)

    async def _run_task(self, task_id: str, trigger_at: str, prompt: str) -> None:
        async with self._semaphore:
            _LOGGER.info("running scheduled task %s (trigger: %s)", task_id, trigger_at)
            try:
                result = self._run_prompt(prompt)
                if asyncio.iscoroutine(result):
                    await result
                self._state_store.mark_completed(task_id, trigger_at)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _LOGGER.exception("scheduled task %s failed", task_id)
                try:
                    self._state_store.mark_failed(task_id, trigger_at, error=str(exc))
                except Exception:
                    # The claim stays recorded; a restart retries it as an interrupted run.
                    _LOGGER.exception("scheduled task %s failure could not be recorded", task_id)


def build_scheduled_host(
    workspace: StrPath,
    run_prompt: Callable[[str], Any],
    *,
    now: Callable[[], datetime] | None = None,
    poll_seconds: float = 30.0,
    state_path: Path | None = None,
) -> ScheduledTaskHost | None:
    tasks = load_scheduled_tasks(workspace)
    if not tasks:
        return None
    default_state_path = (
        Path(workspace) / ".agent" / "schedule_state.json" if state_path is None else state_path
    )
    return ScheduledTaskHost(
        tasks,
        run_prompt,
        now=now,
        poll_seconds=poll_seconds,
        state_path=default_state_path,
    )
