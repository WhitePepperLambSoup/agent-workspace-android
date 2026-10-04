from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from agent_workspace.application.ports import EventStore
from agent_workspace.application.shutdown import settle_tasks
from agent_workspace.core.background_jobs import BackgroundJobLimits, BackgroundJobStatus
from agent_workspace.core.events import Event
from agent_workspace.tools.command import RunProcessTool
from agent_workspace.tools.paths import StrPath, WorkspacePaths

_MAX_ACTIVE_JOBS = 4
_MAX_ACTIVE_JOBS_PER_SESSION = 2
_TERMINAL_STATES = {"succeeded", "failed", "stopped", "interrupted"}
_PROCESS_SETTLEMENT_GRACE_SECONDS = 5
_BACKGROUND_JOB_CLOSE_TIMEOUT_SECONDS = 5.0


def _consume_background_task(task: asyncio.Task[Any]) -> None:
    if not task.cancelled():
        task.exception()


class BackgroundJobManager:
    def __init__(
        self,
        workspace: WorkspacePaths | StrPath,
        store: EventStore,
        event_publisher: Callable[[Event], Awaitable[None]] | None = None,
        *,
        reconcile_on_start: bool = True,
    ) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        self.store = store
        self._tasks: dict[tuple[str, str], asyncio.Task[None]] = {}
        self._statuses: dict[tuple[str, str], BackgroundJobStatus] = {}
        self._closing = False
        self._admission_lock = asyncio.Lock()
        self._process = RunProcessTool(self.paths)
        self._event_publisher = event_publisher
        if reconcile_on_start:
            self.reconcile()

    def reconcile(self) -> None:
        active = self.store.list_background_jobs(
            str(self.paths.root),
            limit=_MAX_ACTIVE_JOBS + 1,
            active_only=True,
        )
        if len(active) > _MAX_ACTIVE_JOBS:
            raise RuntimeError("durable background jobs exceed the runtime active-job limit")
        for status in active:
            anchor = self.store.get_background_job_active_event(status.session_id, status.job_id)
            if anchor is None:
                raise RuntimeError("durable background job causal state is unavailable")
            self.store.append(
                Event(
                    session_id=status.session_id,
                    type="background.job.interrupted",
                    data={"job_id": status.job_id, "reason": "runtime restarted"},
                    causation_id=anchor.id,
                    correlation_id=anchor.correlation_id,
                )
            )

    async def _publish(self, event: Event) -> None:
        if self._event_publisher is not None:
            await self._event_publisher(event)

    def _active_count(self, session_id: str | None = None) -> int:
        return sum(
            not task.done() and (session_id is None or key[0] == session_id)
            for key, task in self._tasks.items()
        )

    def _set_terminal_status(
        self,
        current: BackgroundJobStatus,
        terminal: Event,
    ) -> BackgroundJobStatus:
        state = terminal.type.removeprefix("background.job.")
        status = BackgroundJobStatus(
            job_id=current.job_id,
            session_id=current.session_id,
            label=current.label,
            state=state,
            created_at=current.created_at,
            updated_at=terminal.created_at,
            result=(
                terminal.data.get("result")
                if isinstance(terminal.data.get("result"), str)
                else None
            ),
            terminal_reason=(
                terminal.data.get("reason")
                if isinstance(terminal.data.get("reason"), str)
                else None
            ),
        )
        self._statuses[(current.session_id, current.job_id)] = status
        return status

    async def start(
        self,
        session_id: str,
        arguments: dict[str, Any],
        label: str,
        limits: BackgroundJobLimits | None = None,
        *,
        causation_id: str | None = None,
        correlation_id: str | None = None,
    ) -> BackgroundJobStatus:
        async with self._admission_lock:
            return await self._start_locked(
                session_id,
                arguments,
                label,
                limits,
                causation_id=causation_id,
                correlation_id=correlation_id,
            )

    async def _start_locked(
        self,
        session_id: str,
        arguments: dict[str, Any],
        label: str,
        limits: BackgroundJobLimits | None = None,
        *,
        causation_id: str | None = None,
        correlation_id: str | None = None,
    ) -> BackgroundJobStatus:
        if self._closing:
            raise RuntimeError("background job manager is closing")
        if self._active_count() >= _MAX_ACTIVE_JOBS:
            raise RuntimeError("background job runtime limit is reached")
        if self._active_count(session_id) >= _MAX_ACTIVE_JOBS_PER_SESSION:
            raise RuntimeError("background job session limit is reached")
        limits = limits or BackgroundJobLimits()
        job_id = uuid4().hex
        created = self.store.append(
            Event(
                session_id=session_id,
                type="background.job.created",
                data={
                    "job_id": job_id,
                    "label": label,
                    "arguments_sha256": _arguments_digest(arguments),
                    "max_seconds": limits.max_seconds,
                    "max_output_bytes": limits.max_output_bytes,
                },
                causation_id=causation_id,
                correlation_id=correlation_id,
            )
        )
        status = BackgroundJobStatus(
            job_id,
            session_id,
            label,
            "starting",
            created.created_at,
            created.created_at,
        )
        key = (session_id, job_id)
        self._statuses[key] = status
        try:
            await self._publish(created)
        except BaseException:
            terminal = self.store.append(
                Event(
                    session_id=session_id,
                    type="background.job.interrupted",
                    data={"job_id": job_id, "reason": "job start was interrupted"},
                    causation_id=created.id,
                    correlation_id=correlation_id,
                )
            )
            self._set_terminal_status(status, terminal)
            raise
        task = asyncio.create_task(
            self._run(
                job_id,
                session_id,
                label,
                arguments,
                limits,
                created.id,
                correlation_id,
            )
        )
        self._tasks[key] = task

        def task_done(completed: asyncio.Task[None]) -> None:
            self._task_done(key, completed)

        task.add_done_callback(task_done)
        return status

    def list(self, session_id: str, limit: int = 50) -> tuple[BackgroundJobStatus, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("background job limit must be from 1 to 100")
        return tuple(
            self.store.list_background_jobs(
                str(self.paths.root),
                session_id=session_id,
                limit=limit,
            )
        )

    def status(self, session_id: str, job_id: str) -> BackgroundJobStatus:
        status = self._statuses.get((session_id, job_id))
        if status is None:
            status = self.store.get_background_job(session_id, job_id)
        if status is None:
            raise KeyError("unknown background job")
        return status

    def logs(
        self,
        session_id: str,
        job_id: str,
        *,
        offset: int = 0,
        max_bytes: int = 128 * 1024,
    ) -> dict[str, Any]:
        if type(offset) is not int or offset < 0:
            raise ValueError("background job log offset must be non-negative")
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("background job log max_bytes must be positive")
        status = self.status(session_id, job_id)
        result = status.result or ""
        encoded = result.encode("utf-8")
        offset = min(offset, len(encoded))
        data_bytes = encoded[offset : offset + max_bytes]
        return {
            "job_id": job_id,
            "state": status.state,
            "data": data_bytes.decode("utf-8", errors="ignore"),
            "bytes": len(encoded),
            "offset": offset,
            "next_offset": offset + len(data_bytes),
            "eof": status.state in _TERMINAL_STATES and offset + len(data_bytes) >= len(encoded),
            "truncated": offset > 0 or len(encoded) > max_bytes,
        }

    async def stop(self, session_id: str, job_id: str) -> BackgroundJobStatus:
        status = self.status(session_id, job_id)
        key = (session_id, job_id)
        if status.state not in _TERMINAL_STATES and key not in self._statuses:
            raise RuntimeError("background job is owned by another runtime")
        task = self._tasks.get(key)
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            status = self.status(session_id, job_id)
            if status.state in _TERMINAL_STATES:
                return status
        if status.state in _TERMINAL_STATES:
            return status
        return await self._finish(job_id, session_id, "stopped", None, "stopped by caller")

    async def aclose(self) -> None:
        async with self._admission_lock:
            self._closing = True
            # Peer runtimes can still own active jobs in this workspace's database.
            owned_keys = tuple(self._statuses)
        for task in tuple(self._tasks.values()):
            if not task.done():
                task.cancel()
        errors: list[Exception] = []
        tasks = tuple(self._tasks.values())
        errors.extend(
            await settle_tasks(
                tasks,
                timeout=_BACKGROUND_JOB_CLOSE_TIMEOUT_SECONDS,
                timeout_message="background job close deadline exceeded",
            )
        )
        finishing = tuple(
            asyncio.create_task(
                self._finish(
                    status.job_id,
                    status.session_id,
                    "stopped",
                    None,
                    "runtime closing",
                )
            )
            for session_id, job_id in owned_keys
            if (status := self.store.get_background_job(session_id, job_id)) is not None
            and status.state not in _TERMINAL_STATES
        )
        if finishing:
            errors.extend(
                await settle_tasks(
                    finishing,
                    timeout=_BACKGROUND_JOB_CLOSE_TIMEOUT_SECONDS,
                    timeout_message="background job settlement deadline exceeded",
                )
            )
        if errors:
            raise ExceptionGroup("background job shutdown failed", errors)

    async def _run(
        self,
        job_id: str,
        session_id: str,
        label: str,
        arguments: dict[str, Any],
        limits: BackgroundJobLimits,
        created_event_id: str,
        correlation_id: str | None,
    ) -> None:
        key = (session_id, job_id)
        started: Event | None = None
        try:
            started = self._record_lifecycle(
                session_id,
                "background.job.started",
                job_id,
                created_event_id,
                correlation_id,
            )
            self._statuses[key] = self._statuses[key].__class__(
                job_id,
                session_id,
                label,
                "running",
                self._statuses[key].created_at,
                started.created_at,
            )
            await self._publish(started)
            result = await asyncio.wait_for(
                self._process.execute(arguments),
                limits.max_seconds + _PROCESS_SETTLEMENT_GRACE_SECONDS,
            )
        except asyncio.CancelledError:
            await self._finish(
                job_id,
                session_id,
                "stopped",
                None,
                "stopped by caller",
                started.id if started is not None else created_event_id,
                correlation_id,
            )
            raise
        except Exception as exc:
            await self._finish(
                job_id,
                session_id,
                "failed",
                None,
                str(exc)[:1000],
                started.id if started is not None else created_event_id,
                correlation_id,
            )
        else:
            exit_code: int | None = None
            try:
                process_result = json.loads(result)
                timed_out = process_result.get("timed_out") is True
                raw_exit_code = process_result.get("exit_code")
                exit_code = raw_exit_code if type(raw_exit_code) is int else None
            except (AttributeError, json.JSONDecodeError):
                timed_out = False
            result = _truncate_utf8(result, limits.max_output_bytes)
            if timed_out or (exit_code is not None and exit_code != 0):
                await self._finish(
                    job_id,
                    session_id,
                    "failed",
                    result,
                    "background process timed out"
                    if timed_out
                    else f"background process exited with code {exit_code}",
                    started.id,
                    correlation_id,
                )
                return
            await self._finish(
                job_id,
                session_id,
                "succeeded",
                result,
                None,
                started.id,
                correlation_id,
            )

    async def _finish(
        self,
        job_id: str,
        session_id: str,
        state: str,
        result: str | None,
        reason: str | None,
        causation_id: str | None = None,
        correlation_id: str | None = None,
    ) -> BackgroundJobStatus:
        key = (session_id, job_id)
        current = self._statuses.get(key) or self.store.get_background_job(session_id, job_id)
        if current is None:
            raise RuntimeError("background job state is unavailable")
        if causation_id is None:
            anchor = self.store.get_background_job_active_event(session_id, job_id)
            if anchor is None:
                raise RuntimeError("background job causal state is unavailable")
            causation_id = anchor.id
            correlation_id = correlation_id or anchor.correlation_id
        event_type = f"background.job.{state}"
        terminal = self.store.append(
            Event(
                session_id=session_id,
                type=event_type,
                data={"job_id": job_id, "result": result, "reason": reason},
                causation_id=causation_id,
                correlation_id=correlation_id,
            )
        )
        status = self._set_terminal_status(current, terminal)
        await self._publish(terminal)
        return status

    def _record_lifecycle(
        self,
        session_id: str,
        event_type: str,
        job_id: str,
        causation_id: str,
        correlation_id: str | None,
    ) -> Event:
        event = self.store.append(
            Event(
                session_id=session_id,
                type=event_type,
                data={"job_id": job_id},
                causation_id=causation_id,
                correlation_id=correlation_id,
            )
        )
        return event

    def _task_done(
        self,
        key: tuple[str, str],
        task: asyncio.Task[None],
    ) -> None:
        # Always retire the in-memory entry: an exception after a terminal
        # store write must not leave a dead "running" status resident until
        # the next process restart.
        if not task.cancelled():
            error = task.exception()
            if error is not None:
                logging.getLogger(__name__).exception(
                    "background job task failed for %s",
                    key,
                    exc_info=error,
                )
        self._tasks.pop(key, None)
        status = self._statuses.get(key)
        if status is not None and status.state in _TERMINAL_STATES:
            self._statuses.pop(key, None)


def _truncate_utf8(value: str, max_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _arguments_digest(arguments: dict[str, Any]) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
