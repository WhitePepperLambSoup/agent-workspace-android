"""Scheduled tasks: the book of schedules, passes over due ones and their runs."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from agent_workspace.core.events import Event
from agent_workspace.core.models import (
    Mode,
)
from agent_workspace.core.session import Session
from agent_workspace.policy.redaction import Redactor
from agent_workspace.storage import (
    SQLiteEventStore,
)
from agent_workspace.ui_gateway.gateway_common import (
    _DEVICE_TURN_ENDS,
    _LOGGER,
    _SCHEDULE_RESULT_CHARS,
    _SCHEDULE_TICK_SECONDS,
    GatewayError,
    GatewayReply,
    _is_directory,
)
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import (
    CommandEnvelope,
)
from agent_workspace.ui_gateway.schedules import (
    CATCH_UP_WINDOW,
    OPEN_RUN_STATES,
    Schedule,
    ScheduleRuleError,
    ScheduleRun,
)


class ScheduleCommands(GatewayState):
    """Scheduled tasks: the book of schedules, passes over due ones and their runs."""

    def _settle_schedule_runs_after_restart(self) -> None:
        """Runs in progress when the desktop closed: finished ones get their answer, the
        others are reported interrupted (their conversation keeps what was done)."""
        with suppress(OSError, sqlite3.DatabaseError):
            book = self._schedules
            for run in book.open_runs():
                self._refresh_schedule_run(run)
            for run in book.open_runs():
                book.update_run(run.run_id, state="interrupted")

    def _schedules_command(self, command: CommandEnvelope) -> GatewayReply:
        """Scheduled tasks the desktop runs on its own, and the inbox of their results."""
        action = command.type.rsplit(".", 1)[-1]
        book = self._schedules
        try:
            if action == "list":
                self._require_payload(command, set())
                self._refresh_open_schedule_runs()
                payload: dict[str, object] = {
                    "epoch": self.epoch,
                    "schedules": [self._schedule_document(item) for item in book.all()],
                    "unread": book.unread_count(),
                }
            elif action == "save":
                self._require_payload(command, {"schedule"})
                schedule = book.save(command.payload["schedule"], workspace_exists=_is_directory)
                payload = {"epoch": self.epoch, "schedule": self._schedule_document(schedule)}
            elif action == "delete":
                self._require_payload(command, {"scheduleId"})
                schedule_id = command.payload["scheduleId"]
                if not isinstance(schedule_id, str) or not book.delete(schedule_id):
                    raise GatewayError("schedule_not_found")
                payload = {"epoch": self.epoch, "scheduleId": schedule_id}
            elif action == "run":
                self._require_payload(command, {"scheduleId"})
                schedule_id = command.payload["scheduleId"]
                found = book.get(schedule_id) if isinstance(schedule_id, str) else None
                if found is None:
                    raise GatewayError("schedule_not_found")
                run = book.claim_run(found, datetime.now(UTC), manual=True)
                if run is None:
                    raise GatewayError("runtime_busy")
                self._start_schedule_run_in_background(found, run)
                payload = {"epoch": self.epoch, "run": run.document()}
            elif action == "runs":
                self._require_payload(command, set(), optional={"scheduleId", "limit"})
                schedule_id = command.payload.get("scheduleId")
                limit = command.payload.get("limit", 50)
                if schedule_id is not None and not isinstance(schedule_id, str):
                    raise GatewayError("schedule_not_found")
                if type(limit) is not int or not 1 <= limit <= 200:
                    raise GatewayError("invalid_limit")
                self._refresh_open_schedule_runs()
                payload = {
                    "epoch": self.epoch,
                    "runs": [
                        run.document() for run in book.runs(schedule_id=schedule_id, limit=limit)
                    ],
                    "unread": book.unread_count(),
                }
            elif action == "read":
                self._require_payload(command, set(), optional={"runIds"})
                run_ids = command.payload.get("runIds")
                if run_ids is not None and (
                    not isinstance(run_ids, list)
                    or len(run_ids) > 500
                    or not all(isinstance(item, str) for item in run_ids)
                ):
                    raise GatewayError("invalid_payload")
                book.mark_read(cast(list[str] | None, run_ids))
                payload = {"epoch": self.epoch, "unread": book.unread_count()}
            else:
                raise GatewayError("unsupported_command")
        except ScheduleRuleError as error:
            raise GatewayError(str(error)) from None
        except (OSError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        return self._reply(f"{command.type}.result", payload, session_id=command.session_id)

    def _schedule_document(self, schedule: Schedule) -> dict[str, object]:
        document = schedule.document()
        upcoming = self._schedules.next_run_of(schedule)
        document["nextRun"] = upcoming.isoformat() if upcoming is not None else None
        last = self._schedules.last_run_of(schedule.id)
        document["lastRun"] = last.document() if last is not None else None
        return document

    def _tick_schedules(self) -> None:
        """Start a pass over the schedules every so often (gateway lock held, so no work here)."""
        now = self._clock()
        if now - self._schedules_checked < _SCHEDULE_TICK_SECONDS or self._closing:
            return
        self._schedules_checked = now
        self._tick_folder_watch()
        if self._schedule_pass_thread is not None and self._schedule_pass_thread.is_alive():
            return
        thread = threading.Thread(target=self._schedule_pass, name="gateway-schedules", daemon=True)
        self._schedule_pass_thread = thread
        thread.start()

    def _schedule_pass(self) -> None:
        """Start the runs that are due, and follow the ones in progress to their answers."""
        try:
            book = self._schedules
            self._refresh_open_schedule_runs()
            now = datetime.now(UTC)
            for schedule, due_at in book.due(now):
                once = schedule.rule["kind"] == "once"
                if now - due_at > CATCH_UP_WINDOW:
                    # The computer was off or asleep for the whole window: say so, run nothing.
                    book.claim_run(schedule, due_at, state="missed")
                    book.mark_checked(schedule.id, now, enabled=False if once else None)
                    continue
                run = book.claim_run(schedule, due_at)
                book.mark_checked(schedule.id, now, enabled=False if once else None)
                if run is not None:
                    self._start_schedule_run(schedule, run)
        except Exception:
            # One failed pass (a catalog that could not be read) must not stop later ones.
            _LOGGER.exception("scheduled task pass failed")

    def _start_schedule_run_in_background(self, schedule: Schedule, run: ScheduleRun) -> None:
        threading.Thread(
            target=self._start_schedule_run,
            args=(schedule, run),
            name=f"gateway-schedule-{run.run_id[:8]}",
            daemon=True,
        ).start()

    def _start_schedule_run(self, schedule: Schedule, run: ScheduleRun) -> None:
        """Open a new conversation in the schedule's folder and send its prompt there."""
        book = self._schedules
        if not _is_directory(schedule.workspace):
            book.update_run(run.run_id, state="failed", error="folder_missing")
            return
        with self._lock:
            ready = self._provider is not None and not self._closing
        if not ready:
            book.update_run(run.run_id, state="failed", error="desktop_not_ready")
            return
        started = datetime.fromisoformat(run.due_at).astimezone()
        session = Session(
            workspace=str(Path(schedule.workspace).resolve()),
            mode=Mode.TASK,
            autonomy=schedule.autonomy,
            title=f"{schedule.title} · {started:%m-%d %H:%M}"[:200],
        )
        try:
            with SQLiteEventStore(self._database) as store:
                store.create_session(session)
        except (OSError, sqlite3.DatabaseError, ValueError):
            book.update_run(run.run_id, state="failed", error="storage_unavailable")
            return
        book.update_run(run.run_id, session_id=session.id)
        with self._lock:
            self._pending_host_events.append(
                Event(
                    session_id=session.id,
                    type="session.created",
                    data={
                        "session_id": session.id,
                        "title": session.title,
                        "mode": session.mode.value,
                        "autonomy": session.autonomy.value,
                        "activated": False,
                        # Listed in the window; the conversation open there stays open.
                        "selected": False,
                    },
                )
            )
        try:
            self._dispatch_prompt(f"schedule-{run.run_id}", session, schedule.prompt)
        except GatewayError as error:
            book.update_run(run.run_id, state="failed", error=str(error))
            return
        book.update_run(run.run_id, state="running")

    def _refresh_open_schedule_runs(self) -> None:
        for run in self._schedules.open_runs():
            self._refresh_schedule_run(run)

    def _refresh_schedule_run(self, run: ScheduleRun) -> None:
        """Follow a run through its conversation's first turn."""
        if run.state not in OPEN_RUN_STATES or run.session_id is None:
            return
        try:
            events = SQLiteEventStore.list_session_events_of_types_read_only(
                self._database,
                run.session_id,
                frozenset({"message.created", *_DEVICE_TURN_ENDS}),
            )
        except (OSError, ValueError, sqlite3.DatabaseError):
            return
        correlation = run.correlation_id
        if correlation is None:
            correlation = next(
                (
                    event.correlation_id
                    for event in events
                    if event.type == "message.created"
                    and event.data.get("role") == "user"
                    and event.correlation_id
                ),
                None,
            )
            if correlation is None:
                return
            self._schedules.update_run(run.run_id, correlation_id=correlation)
        for event in events:
            if event.correlation_id != correlation or event.type not in _DEVICE_TURN_ENDS:
                continue
            answers = [
                str(item.data.get("content"))
                for item in events
                if item.correlation_id == correlation
                and item.type == "message.created"
                and item.data.get("role") == "assistant"
                and isinstance(item.data.get("content"), str)
                and str(item.data.get("content")).strip()
            ]
            error = None
            if event.type == "turn.failed":
                message = event.data.get("message")
                error = Redactor().redact(message[:600]) if isinstance(message, str) else None
            self._schedules.update_run(
                run.run_id,
                state=_DEVICE_TURN_ENDS[event.type],
                result=answers[-1][:_SCHEDULE_RESULT_CHARS] if answers else None,
                error=error,
            )
            return
