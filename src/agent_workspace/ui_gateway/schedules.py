"""Scheduled tasks the desktop runs on its own, and the inbox their results land in.

A schedule names a folder, a prompt and a time rule in the computer's local time: every day,
working days, chosen weekdays, a day of the month, once, or a cron expression. When a run is
due the gateway opens a new conversation in that folder and sends the prompt there, as it does
for a phone's task; the run record follows that conversation to its answer and stays in the
inbox until it is read, here or on a phone.

Local time is wall-clock time: a rule computes the next local minute and only then becomes an
instant, so a daylight-saving change never moves "every day at 08:00". The catalog is a small
JSON file written atomically; runs are rows in SQLite so the window and a phone's request can
read and update them at the same time.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from collections.abc import Callable, Iterable
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent_workspace.core.models import Autonomy
from agent_workspace.core.scheduler import CronSchedule, ScheduleError

RULE_KINDS = ("daily", "weekdays", "weekly", "monthly", "once", "cron")
_TIME = re.compile(r"^(?P<hour>[01]\d|2[0-3]):(?P<minute>[0-5]\d)$")
MAX_SCHEDULES = 200
MAX_TITLE_CHARS = 120
MAX_PROMPT_CHARS = 16_000
# A run missed while the computer was off still runs once if it was due this recently.
CATCH_UP_WINDOW = timedelta(hours=12)
RUN_STATES = ("starting", "running", "succeeded", "failed", "cancelled", "interrupted", "missed")
OPEN_RUN_STATES = frozenset({"starting", "running"})


class ScheduleRuleError(ValueError):
    """A schedule or rule the catalog does not accept; the message is the error code."""


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat()


def _local_wall(moment: datetime) -> datetime:
    """The local wall-clock time of an instant, as a naive datetime."""
    return moment.astimezone().replace(tzinfo=None)


def _instant(wall: datetime) -> datetime:
    """The instant a naive local wall-clock time stands for."""
    return wall.astimezone().astimezone(UTC)


def _time_of(rule: dict[str, Any]) -> tuple[int, int]:
    raw = rule.get("time")
    match = _TIME.fullmatch(raw) if isinstance(raw, str) else None
    if match is None:
        raise ScheduleRuleError("invalid_time")
    return int(match["hour"]), int(match["minute"])


def normalize_rule(raw: object) -> dict[str, Any]:
    """The canonical form of a rule, or ScheduleRuleError."""
    if not isinstance(raw, dict):
        raise ScheduleRuleError("invalid_rule")
    kind = raw.get("kind")
    if kind not in RULE_KINDS:
        raise ScheduleRuleError("invalid_rule")
    if kind in {"daily", "weekdays"}:
        hour, minute = _time_of(raw)
        return {"kind": kind, "time": f"{hour:02d}:{minute:02d}"}
    if kind == "weekly":
        hour, minute = _time_of(raw)
        days = raw.get("days")
        if (
            not isinstance(days, list)
            or not days
            or any(type(day) is not int or not 1 <= day <= 7 for day in days)
        ):
            raise ScheduleRuleError("invalid_days")
        return {"kind": kind, "time": f"{hour:02d}:{minute:02d}", "days": sorted(set(days))}
    if kind == "monthly":
        hour, minute = _time_of(raw)
        day = raw.get("day")
        if type(day) is not int or not 1 <= day <= 28:
            raise ScheduleRuleError("invalid_day")
        return {"kind": kind, "time": f"{hour:02d}:{minute:02d}", "day": day}
    if kind == "once":
        at = raw.get("at")
        if not isinstance(at, str):
            raise ScheduleRuleError("invalid_at")
        try:
            moment = datetime.fromisoformat(at)
        except ValueError:
            raise ScheduleRuleError("invalid_at") from None
        if moment.tzinfo is None:
            moment = _instant(moment)
        return {"kind": kind, "at": _iso(moment.replace(second=0, microsecond=0))}
    expression = raw.get("cron")
    if not isinstance(expression, str):
        raise ScheduleRuleError("invalid_cron")
    try:
        cron = CronSchedule.parse(" ".join(expression.split()))
    except ScheduleError:
        raise ScheduleRuleError("invalid_cron") from None
    return {"kind": kind, "cron": cron.expression}


def rule_cron(rule: dict[str, Any]) -> CronSchedule | None:
    """The local-time cron expression of a recurring rule (None for a single run)."""
    kind = rule["kind"]
    if kind == "once":
        return None
    if kind == "cron":
        return CronSchedule.parse(rule["cron"])
    hour, minute = _time_of(rule)
    if kind == "daily":
        return CronSchedule.parse(f"{minute} {hour} * * *")
    if kind == "weekdays":
        return CronSchedule.parse(f"{minute} {hour} * * 1-5")
    if kind == "weekly":
        # ISO weekdays (Monday 1 .. Sunday 7) become cron's (Sunday 0 .. Saturday 6).
        days = ",".join(str(day % 7) for day in rule["days"])
        return CronSchedule.parse(f"{minute} {hour} * * {days}")
    return CronSchedule.parse(f"{minute} {hour} {rule['day']} * *")


def next_run(rule: dict[str, Any], after: datetime) -> datetime | None:
    """The first instant strictly after ``after`` the rule fires at, or None."""
    if rule["kind"] == "once":
        at = datetime.fromisoformat(rule["at"])
        return at if at > after else None
    cron = rule_cron(rule)
    assert cron is not None
    # Cron works on the wall clock; the UTC label only satisfies its aware-time check.
    wall = cron.next_after(_local_wall(after).replace(tzinfo=UTC)).replace(tzinfo=None)
    moment = _instant(wall)
    while moment <= after:  # a wall time repeated when the clocks go back
        wall = cron.next_after(wall.replace(tzinfo=UTC)).replace(tzinfo=None)
        moment = _instant(wall)
    return moment


def latest_due(rule: dict[str, Any], after: datetime, until: datetime) -> datetime | None:
    """The last instant in (after, until] the rule fired at, or None."""
    latest: datetime | None = None
    cursor = after
    for _ in range(10_000):
        moment = next_run(rule, cursor)
        if moment is None or moment > until:
            break
        latest = cursor = moment
    return latest


@dataclass(frozen=True, slots=True)
class Schedule:
    id: str
    title: str
    prompt: str
    workspace: str
    rule: dict[str, Any]
    enabled: bool
    notify_phone: bool
    autonomy: Autonomy
    created_at: str
    updated_at: str
    # Due times up to this instant were considered; a new schedule starts from its creation.
    checked_at: str

    def document(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "prompt": self.prompt,
            "workspace": self.workspace,
            "rule": dict(self.rule),
            "enabled": self.enabled,
            "notifyPhone": self.notify_phone,
            "autonomy": self.autonomy.value,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }

    def record(self) -> dict[str, object]:
        return {**self.document(), "checkedAt": self.checked_at}


@dataclass(frozen=True, slots=True)
class ScheduleRun:
    run_id: str
    schedule_id: str
    title: str
    due_at: str
    state: str
    session_id: str | None
    correlation_id: str | None
    result: str | None
    error: str | None
    manual: bool
    read: bool
    created_at: str
    updated_at: str

    def document(self) -> dict[str, object]:
        document: dict[str, object] = {
            "runId": self.run_id,
            "scheduleId": self.schedule_id,
            "title": self.title,
            "dueAt": self.due_at,
            "state": self.state,
            "manual": self.manual,
            "read": self.read,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
        if self.session_id:
            document["sessionId"] = self.session_id
        if self.result:
            document["result"] = self.result
        if self.error:
            document["error"] = self.error
        return document


def _clean_text(value: object, maximum: int, code: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ScheduleRuleError(code)
    return value.strip()


class ScheduleBook:
    """The schedule catalog and the record of their runs, under one data directory."""

    def __init__(self, directory: Path, *, clock: Callable[[], datetime] = _now) -> None:
        self.directory = directory
        self._clock = clock
        self._catalog = directory / "catalog.json"
        self._runs = directory / "runs.db"
        self._lock = threading.RLock()
        self._schedules: dict[str, Schedule] | None = None
        self._next_due: dict[str, tuple[tuple[str, str], datetime | None]] = {}

    # ---- catalog ----------------------------------------------------------------------------

    def _load(self) -> dict[str, Schedule]:
        if self._schedules is not None:
            return self._schedules
        schedules: dict[str, Schedule] = {}
        try:
            raw = json.loads(self._catalog.read_text("utf-8"))
        except FileNotFoundError:
            raw = {"schedules": []}
        except (OSError, ValueError):
            raw = {"schedules": []}
        for entry in raw.get("schedules", []) if isinstance(raw, dict) else []:
            schedule = self._from_record(entry)
            if schedule is not None:
                schedules[schedule.id] = schedule
        self._schedules = schedules
        return schedules

    @staticmethod
    def _from_record(entry: object) -> Schedule | None:
        if not isinstance(entry, dict):
            return None
        try:
            return Schedule(
                id=str(entry["id"]),
                title=_clean_text(entry["title"], MAX_TITLE_CHARS, "invalid_title"),
                prompt=_clean_text(entry["prompt"], MAX_PROMPT_CHARS, "invalid_prompt"),
                workspace=str(entry["workspace"]),
                rule=normalize_rule(entry["rule"]),
                enabled=bool(entry.get("enabled", True)),
                notify_phone=bool(entry.get("notifyPhone", False)),
                autonomy=Autonomy(entry.get("autonomy", Autonomy.WORKSPACE.value)),
                created_at=str(entry["createdAt"]),
                updated_at=str(entry["updatedAt"]),
                checked_at=str(entry.get("checkedAt") or entry["createdAt"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _save(self, schedules: dict[str, Schedule]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        document = {"version": 1, "schedules": [item.record() for item in schedules.values()]}
        temporary = self._catalog.with_name(f"{self._catalog.name}.{uuid4().hex}.tmp")
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), "utf-8")
        temporary.replace(self._catalog)
        self._schedules = schedules

    def all(self) -> list[Schedule]:
        with self._lock:
            return sorted(self._load().values(), key=lambda item: item.created_at)

    def get(self, schedule_id: str) -> Schedule | None:
        with self._lock:
            return self._load().get(schedule_id)

    def save(self, raw: object, *, workspace_exists: Callable[[str], bool]) -> Schedule:
        """Create a schedule (no id) or replace the fields of an existing one."""
        if not isinstance(raw, dict):
            raise ScheduleRuleError("invalid_schedule")
        with self._lock:
            schedules = dict(self._load())
            schedule_id = raw.get("id")
            existing = schedules.get(schedule_id) if isinstance(schedule_id, str) else None
            if schedule_id is not None and existing is None:
                raise ScheduleRuleError("schedule_not_found")
            if existing is None and len(schedules) >= MAX_SCHEDULES:
                raise ScheduleRuleError("too_many_schedules")
            workspace = raw.get("workspace", existing.workspace if existing else None)
            if not isinstance(workspace, str) or not workspace.strip():
                raise ScheduleRuleError("invalid_workspace")
            workspace = str(Path(workspace.strip()).expanduser())
            if not workspace_exists(workspace):
                raise ScheduleRuleError("invalid_workspace")
            autonomy_raw = raw.get(
                "autonomy", existing.autonomy.value if existing else Autonomy.WORKSPACE.value
            )
            try:
                autonomy = Autonomy(autonomy_raw)
            except ValueError:
                raise ScheduleRuleError("invalid_autonomy") from None
            now = _iso(self._clock())
            rule = normalize_rule(raw.get("rule", existing.rule if existing else None))
            enabled = raw.get("enabled", existing.enabled if existing else True)
            notify = raw.get("notifyPhone", existing.notify_phone if existing else False)
            if type(enabled) is not bool or type(notify) is not bool:
                raise ScheduleRuleError("invalid_schedule")
            changed_timing = (
                existing is None or existing.rule != rule or (enabled and not existing.enabled)
            )
            schedule = Schedule(
                id=existing.id if existing else str(uuid4()),
                title=_clean_text(
                    raw.get("title", existing.title if existing else None),
                    MAX_TITLE_CHARS,
                    "invalid_title",
                ),
                prompt=_clean_text(
                    raw.get("prompt", existing.prompt if existing else None),
                    MAX_PROMPT_CHARS,
                    "invalid_prompt",
                ),
                workspace=workspace,
                rule=rule,
                enabled=enabled,
                notify_phone=notify,
                autonomy=autonomy,
                created_at=existing.created_at if existing else now,
                updated_at=now,
                # A new rule, or a schedule turned back on, starts from now: no burst of the
                # runs it would have had before.
                checked_at=now if changed_timing or existing is None else existing.checked_at,
            )
            schedules[schedule.id] = schedule
            self._save(schedules)
            return schedule

    def delete(self, schedule_id: str) -> bool:
        with self._lock:
            schedules = dict(self._load())
            if schedules.pop(schedule_id, None) is None:
                return False
            self._save(schedules)
            return True

    def mark_checked(
        self, schedule_id: str, moment: datetime, *, enabled: bool | None = None
    ) -> None:
        with self._lock:
            schedules = dict(self._load())
            schedule = schedules.get(schedule_id)
            if schedule is None:
                return
            changes: dict[str, Any] = {"checked_at": _iso(moment)}
            if enabled is not None:
                changes["enabled"] = enabled
            schedules[schedule_id] = replace(schedule, **changes)
            self._save(schedules)

    def due(self, now: datetime) -> list[tuple[Schedule, datetime]]:
        """Enabled schedules with a run due by ``now`` (the latest due time of each)."""
        found: list[tuple[Schedule, datetime]] = []
        for schedule in self.all():
            if not schedule.enabled:
                continue
            # The next due time only changes with the rule or the check mark; most ticks
            # compare against the remembered one instead of walking the rule again.
            key = (schedule.checked_at, json.dumps(schedule.rule, sort_keys=True))
            cached = self._next_due.get(schedule.id)
            if cached is None or cached[0] != key:
                cached = (key, next_run(schedule.rule, datetime.fromisoformat(schedule.checked_at)))
                self._next_due[schedule.id] = cached
            if cached[1] is None or cached[1] > now:
                continue
            moment = latest_due(schedule.rule, datetime.fromisoformat(schedule.checked_at), now)
            if moment is not None:
                found.append((schedule, moment))
        return found

    def next_run_of(self, schedule: Schedule) -> datetime | None:
        if not schedule.enabled:
            return None
        return next_run(
            schedule.rule, max(self._clock(), datetime.fromisoformat(schedule.checked_at))
        )

    def import_legacy(self, workspaces: Iterable[str]) -> int:
        """Bring schedules saved inside folders by older versions into the catalog, once."""
        with self._lock:
            if self._catalog.exists():
                return 0
            schedules: dict[str, Schedule] = {}
            now = _iso(self._clock())
            for workspace in workspaces:
                path = Path(workspace) / ".agent" / "schedules.json"
                try:
                    raw = json.loads(path.read_text("utf-8"))
                except (OSError, ValueError):
                    continue
                for entry in raw.get("schedules", []) if isinstance(raw, dict) else []:
                    if not isinstance(entry, dict) or len(schedules) >= MAX_SCHEDULES:
                        continue
                    if isinstance(entry.get("cron"), str):
                        rule: object = {"kind": "cron", "cron": entry["cron"]}
                    else:
                        rule = {"kind": "once", "at": entry.get("at")}
                    schedule = self._from_record(
                        {
                            "id": str(uuid4()),
                            "title": str(entry.get("id") or "Scheduled task")[:MAX_TITLE_CHARS],
                            "prompt": entry.get("prompt"),
                            "workspace": workspace,
                            "rule": rule,
                            "enabled": entry.get("enabled", True),
                            "createdAt": now,
                            "updatedAt": now,
                        }
                    )
                    if schedule is not None:
                        schedules[schedule.id] = schedule
            self._save(schedules)
            return len(schedules)

    # ---- runs -------------------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        self.directory.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._runs, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schedule_runs (
                run_id TEXT PRIMARY KEY,
                schedule_id TEXT NOT NULL,
                title TEXT NOT NULL,
                due_at TEXT NOT NULL,
                state TEXT NOT NULL,
                session_id TEXT,
                correlation_id TEXT,
                result TEXT,
                error TEXT,
                manual INTEGER NOT NULL,
                read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (schedule_id, due_at)
            )
            """
        )
        return connection

    @staticmethod
    def _run(row: sqlite3.Row) -> ScheduleRun:
        return ScheduleRun(
            run_id=row["run_id"],
            schedule_id=row["schedule_id"],
            title=row["title"],
            due_at=row["due_at"],
            state=row["state"],
            session_id=row["session_id"],
            correlation_id=row["correlation_id"],
            result=row["result"],
            error=row["error"],
            manual=bool(row["manual"]),
            read=bool(row["read"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def claim_run(
        self, schedule: Schedule, due_at: datetime, *, manual: bool = False, state: str = "starting"
    ) -> ScheduleRun | None:
        """A new run record for this due time, or None when that time already has one."""
        now = _iso(self._clock())
        run_id = str(uuid4())
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO schedule_runs (run_id, schedule_id, title, due_at, state, "
                "manual, read, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
                (run_id, schedule.id, schedule.title, _iso(due_at), state, int(manual), now, now),
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute(
                "SELECT * FROM schedule_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return self._run(row)

    def update_run(self, run_id: str, **fields: object) -> ScheduleRun | None:
        allowed = {"state", "session_id", "correlation_id", "result", "error"}
        if not set(fields) <= allowed:
            raise ValueError("unknown run field")
        with self._lock, closing(self._connect()) as connection, connection:
            if fields:
                assignments = ", ".join(f"{name} = ?" for name in fields)
                connection.execute(
                    f"UPDATE schedule_runs SET {assignments}, updated_at = ? WHERE run_id = ?",
                    (*fields.values(), _iso(self._clock()), run_id),
                )
            row = connection.execute(
                "SELECT * FROM schedule_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return None if row is None else self._run(row)

    def get_run(self, run_id: str) -> ScheduleRun | None:
        with self._lock, closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM schedule_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return None if row is None else self._run(row)

    def runs(
        self, *, schedule_id: str | None = None, limit: int = 50, unread_only: bool = False
    ) -> list[ScheduleRun]:
        clauses: list[str] = []
        values: list[object] = []
        if schedule_id is not None:
            clauses.append("schedule_id = ?")
            values.append(schedule_id)
        if unread_only:
            clauses.append("read = 0")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock, closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT * FROM schedule_runs {where} "
                "ORDER BY created_at DESC, due_at DESC LIMIT ?",
                (*values, limit),
            ).fetchall()
        return [self._run(row) for row in rows]

    def open_runs(self) -> list[ScheduleRun]:
        with self._lock, closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM schedule_runs WHERE state IN ('starting', 'running')"
            ).fetchall()
        return [self._run(row) for row in rows]

    def unread_count(self) -> int:
        with self._lock, closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM schedule_runs WHERE read = 0 AND state NOT IN "
                "('starting', 'running')"
            ).fetchone()
        return int(row[0])

    def mark_read(self, run_ids: list[str] | None) -> int:
        """Mark the given finished runs, or all of them (None), as read."""
        with self._lock, closing(self._connect()) as connection, connection:
            if run_ids is None:
                cursor = connection.execute(
                    "UPDATE schedule_runs SET read = 1 WHERE read = 0 AND state NOT IN "
                    "('starting', 'running')"
                )
            else:
                cursor = connection.executemany(
                    "UPDATE schedule_runs SET read = 1 WHERE run_id = ?",
                    [(run_id,) for run_id in run_ids],
                )
        return cursor.rowcount

    def last_run_of(self, schedule_id: str) -> ScheduleRun | None:
        found = self.runs(schedule_id=schedule_id, limit=1)
        return found[0] if found else None
