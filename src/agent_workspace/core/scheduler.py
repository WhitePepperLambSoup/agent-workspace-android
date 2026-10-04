"""Pure scheduling core: cron parsing, next-trigger computation and a task registry.

This module is side-effect free: it never touches storage or the network, and
every datetime it accepts or returns is timezone-aware (naive inputs raise
:class:`ScheduleError`).

Semantics
---------
* Cron fields support ``*``, lists (``,``), ranges (``-``), steps (``/``) and
  single values. Ranges must be ascending; named values (``mon``, ``jan``) are
  rejected. Value ranges: minute 0-59, hour 0-23, day-of-month 1-31, month
  1-12, day-of-week 0-6 (0 = Sunday).
* When both ``day_of_month`` and ``day_of_week`` are restricted (not exactly
  ``*``) a day matches if *either* field matches, the standard cron OR
  semantics; when only one is restricted it acts alone.
* ``next_after`` returns the first trigger strictly after the given moment at
  minute granularity and raises :class:`ScheduleError` after a bounded scan of
  four years (enough to cover every possible date, including leap days).
* ``TaskScheduler`` consumes triggers: each trigger instant is delivered
  exactly once per process by ``due`` and ``advance`` (they move an internal
  cursor). Persistence across restarts and any external re-entrancy policy are
  the caller's responsibility; the injectable clock is the recovery hook.
* Tasks with ``enabled=False`` never fire and are ignored by ``due``,
  ``advance`` and ``next_due``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


class ScheduleError(ValueError):
    """Raised for invalid cron expressions or scheduling operations."""


_FIELD_RANGES: dict[str, tuple[int, int]] = {
    "minute": (0, 59),
    "hour": (0, 23),
    "day_of_month": (1, 31),
    "month": (1, 12),
    "day_of_week": (0, 6),
}
_MAX_SCAN_YEARS = 4


def _field_label(name: str, index: int) -> str:
    return f"{name} (field {index} of 5)"


def _parse_int(raw: str, name: str, lo: int, hi: int) -> int:
    if not raw.isdecimal():
        raise ScheduleError(f"{name}: expected an integer in [{lo}, {hi}], got {raw!r}")
    value = int(raw)
    if not lo <= value <= hi:
        raise ScheduleError(f"{name}: value {value} out of range [{lo}, {hi}]")
    return value


def _parse_field(raw: str, name: str, lo: int, hi: int) -> frozenset[int]:
    values: set[int] = set()
    for element in raw.split(","):
        element = element.strip()
        if not element:
            raise ScheduleError(f"{name}: empty element in field {raw!r}")
        body, separator, step_raw = element.partition("/")
        has_step = bool(separator)
        step = 1
        if has_step:
            step_raw = step_raw.strip()
            if not step_raw.isdecimal() or int(step_raw) < 1:
                raise ScheduleError(f"{name}: step {step_raw!r} must be a positive integer")
            step = int(step_raw)
        if body == "*":
            values.update(range(lo, hi + 1, step))
            continue
        if "-" in body:
            start_raw, _, end_raw = body.partition("-")
            start = _parse_int(start_raw.strip(), name, lo, hi)
            end = _parse_int(end_raw.strip(), name, lo, hi)
            if start > end:
                raise ScheduleError(f"{name}: range {body!r} must be ascending")
            values.update(range(start, end + 1, step))
            continue
        value = _parse_int(body.strip(), name, lo, hi)
        if has_step:
            values.update(range(value, hi + 1, step))
        else:
            values.add(value)
    return frozenset(values)


@dataclass(frozen=True, slots=True)
class CronSchedule:
    """A validated five-field cron expression restricted to the numeric subset.

    Field order is minute, hour, day of month, month, day of week. The parsed
    value sets are precomputed once so repeated :meth:`next_after` calls stay
    cheap; equality and hashing are based on the raw expressions only.
    """

    minute: str
    hour: str
    day_of_month: str
    month: str
    day_of_week: str

    _minutes: frozenset[int] = field(init=False, repr=False, compare=False)
    _hours: frozenset[int] = field(init=False, repr=False, compare=False)
    _days_of_month: frozenset[int] | None = field(init=False, repr=False, compare=False)
    _months: frozenset[int] = field(init=False, repr=False, compare=False)
    _days_of_week: frozenset[int] | None = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        minutes = _parse_field(self.minute, _field_label("minute", 1), 0, 59)
        hours = _parse_field(self.hour, _field_label("hour", 2), 0, 23)
        days_of_month = _parse_field(self.day_of_month, _field_label("day_of_month", 3), 1, 31)
        months = _parse_field(self.month, _field_label("month", 4), 1, 12)
        days_of_week = _parse_field(self.day_of_week, _field_label("day_of_week", 5), 0, 6)
        object.__setattr__(self, "_minutes", minutes)
        object.__setattr__(self, "_hours", hours)
        object.__setattr__(
            self, "_days_of_month", None if self.day_of_month == "*" else days_of_month
        )
        object.__setattr__(self, "_months", months)
        object.__setattr__(
            self,
            "_days_of_week",
            None
            if self.day_of_week == "*"
            else frozenset((value + 6) % 7 for value in days_of_week),
        )

    @classmethod
    def parse(cls, expression: str) -> CronSchedule:
        """Parse a five-field cron expression, raising :class:`ScheduleError` on any issue."""
        if not isinstance(expression, str):
            raise ScheduleError(
                f"cron expression must be a string, got {type(expression).__name__}"
            )
        fields = expression.split()
        if len(fields) != 5:
            raise ScheduleError(
                f"cron expression must have 5 fields, got {len(fields)}: {expression!r}"
            )
        minute, hour, day_of_month, month, day_of_week = fields
        return cls(minute, hour, day_of_month, month, day_of_week)

    @property
    def expression(self) -> str:
        """The canonical five-field expression string."""
        return f"{self.minute} {self.hour} {self.day_of_month} {self.month} {self.day_of_week}"

    def __str__(self) -> str:
        return self.expression

    def next_after(self, moment: datetime) -> datetime:
        """Return the first trigger instant strictly after *moment*.

        The result keeps *moment*'s timezone and has second and microsecond set
        to zero. A bounded minute-granularity scan of four years is performed;
        if nothing matches within the window a :class:`ScheduleError` is raised.
        """
        if moment.tzinfo is None:
            raise ScheduleError("moment must be timezone-aware")
        limit = moment + timedelta(days=_MAX_SCAN_YEARS * 366)
        candidate = moment.replace(second=0, microsecond=0) + timedelta(minutes=1)
        while candidate <= limit:
            if candidate.month not in self._months:
                candidate = self._first_of_next_month(candidate)
                continue
            if not self._day_matches(candidate):
                candidate = candidate.replace(hour=0, minute=0) + timedelta(days=1)
                continue
            if candidate.hour not in self._hours:
                candidate = self._next_hour(candidate)
                continue
            if candidate.minute not in self._minutes:
                candidate = self._next_minute(candidate)
                continue
            return candidate
        raise ScheduleError(
            f"no trigger within {_MAX_SCAN_YEARS} years for cron {self.expression!r}"
        )

    def _day_matches(self, moment: datetime) -> bool:
        days_of_month = self._days_of_month
        days_of_week = self._days_of_week
        day_of_month_ok = days_of_month is None or moment.day in days_of_month
        day_of_week_ok = days_of_week is None or moment.weekday() in days_of_week
        if days_of_month is not None and days_of_week is not None:
            return day_of_month_ok or day_of_week_ok
        return day_of_month_ok and day_of_week_ok

    @staticmethod
    def _first_of_next_month(moment: datetime) -> datetime:
        first_of_month = moment.replace(day=1, hour=0, minute=0)
        return (first_of_month + timedelta(days=32)).replace(day=1, hour=0, minute=0)

    def _next_hour(self, moment: datetime) -> datetime:
        for hour in sorted(self._hours):
            if hour > moment.hour:
                return moment.replace(hour=hour, minute=0)
        tomorrow = moment.replace(hour=0, minute=0) + timedelta(days=1)
        return tomorrow.replace(hour=min(self._hours), minute=0)

    def _next_minute(self, moment: datetime) -> datetime:
        for minute in sorted(self._minutes):
            if minute > moment.minute:
                return moment.replace(minute=minute)
        return self._next_hour(moment.replace(minute=0))


@dataclass(frozen=True, slots=True)
class ScheduledTask:
    """A named task bound to a cron schedule and a prompt."""

    id: str
    cron: CronSchedule
    prompt: str
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ScheduleError("task id must be a non-empty string")
        if not isinstance(self.cron, CronSchedule):
            raise ScheduleError("task cron must be a CronSchedule")
        if not isinstance(self.prompt, str):
            raise ScheduleError("task prompt must be a string")
        if not isinstance(self.enabled, bool):
            raise ScheduleError("task enabled must be a bool")

    def to_document(self) -> dict[str, Any]:
        """Serialize to a plain dict; ``cron`` is stored as its expression string."""
        return {
            "id": self.id,
            "cron": self.cron.expression,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }

    @classmethod
    def from_document(cls, value: object) -> ScheduledTask:
        """Rebuild a task from a :meth:`to_document` dict, raising on malformed input."""
        if not isinstance(value, dict):
            raise ScheduleError("task document must be an object")
        try:
            cron_raw = value["cron"]
            if not isinstance(cron_raw, str):
                raise ScheduleError("task document cron must be a string")
            enabled_raw = value.get("enabled", True)
            if not isinstance(enabled_raw, bool):
                raise ScheduleError("task document enabled must be a bool")
            return cls(
                id=str(value["id"]),
                cron=CronSchedule.parse(cron_raw),
                prompt=str(value["prompt"]),
                enabled=enabled_raw,
            )
        except ScheduleError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ScheduleError("task document is invalid") from exc


@dataclass(frozen=True, slots=True)
class OneTimeTask:
    """A task scheduled for one specific timezone-aware instant."""

    id: str
    at: datetime
    prompt: str
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ScheduleError("one-time task id must be a non-empty string")
        if not isinstance(self.at, datetime) or self.at.tzinfo is None:
            raise ScheduleError("one-time task 'at' must be a timezone-aware datetime")
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ScheduleError("one-time task prompt must be a non-empty string")
        if not isinstance(self.enabled, bool):
            raise ScheduleError("one-time task enabled must be a bool")

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "at": self.at.isoformat(),
            "prompt": self.prompt,
            "enabled": self.enabled,
        }

    @classmethod
    def from_document(cls, value: object) -> OneTimeTask:
        if not isinstance(value, dict):
            raise ScheduleError("one-time task document must be an object")
        try:
            enabled_raw = value.get("enabled", True)
            if not isinstance(enabled_raw, bool):
                raise ScheduleError("one-time task document enabled must be a bool")
            at_raw = value["at"]
            if not isinstance(at_raw, str):
                raise ScheduleError("one-time task document 'at' must be a string")
            at = datetime.fromisoformat(at_raw)
            if at.tzinfo is None:
                raise ScheduleError("one-time task document 'at' must be timezone-aware")
            return cls(
                id=str(value["id"]),
                at=at,
                prompt=str(value["prompt"]),
                enabled=enabled_raw,
            )
        except ScheduleError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ScheduleError("one-time task document is invalid") from exc


class OneTimeTaskScheduler:
    """Delivers each one-time task at most once per process."""

    def __init__(
        self,
        tasks: Iterable[OneTimeTask] = (),
        *,
        now: Callable[[], datetime] | None = None,
        completed_ids: Iterable[str] = (),
    ) -> None:
        self._now = _utc_now if now is None else now
        self._tasks = {task.id: task for task in tasks}
        self._fired: set[str] = set(completed_ids)

    def register(self, task: OneTimeTask) -> None:
        if task.id in self._tasks:
            raise ScheduleError(f"duplicate one-time task id {task.id!r}")
        self._tasks[task.id] = task

    def get(self, task_id: str) -> OneTimeTask | None:
        return self._tasks.get(task_id)

    def due(self) -> tuple[tuple[OneTimeTask, datetime], ...]:
        moment = self._now()
        due: list[tuple[OneTimeTask, datetime]] = []
        for task in self._tasks.values():
            if task.enabled and task.id not in self._fired and task.at <= moment:
                due.append((task, task.at))
                self._fired.add(task.id)
        due.sort(key=lambda item: (item[1], item[0].id))
        return tuple(due)

    def next_due(self) -> tuple[OneTimeTask, datetime] | None:
        candidates = [
            (task, task.at)
            for task in self._tasks.values()
            if task.enabled and task.id not in self._fired
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda item: (item[1], item[0].id))


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TaskScheduler:
    """In-memory scheduler that delivers each trigger instant exactly once.

    The internal clock starts at ``now()`` (default: ``datetime.now(UTC)``).
    ``advance`` moves the clock to an explicit moment and returns every
    (task, trigger) pair in the traversed interval, ordered by trigger time
    (ties keep registration order). ``due`` is ``advance`` applied to the
    injected clock, i.e. everything due at the current moment. ``next_due``
    peeks at the earliest future trigger without consuming it.
    """

    def __init__(
        self,
        tasks: Iterable[ScheduledTask] = (),
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._now: Callable[[], datetime] = _utc_now if now is None else now
        self._clock = self._now()
        self._tasks: dict[str, ScheduledTask] = {}
        self._cursor: dict[str, datetime] = {}
        self.paused = False
        for task in tasks:
            self.register(task)

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def register(self, task: ScheduledTask) -> None:
        """Add a task; duplicate ids raise :class:`ScheduleError`."""
        if task.id in self._tasks:
            raise ScheduleError(f"duplicate task id {task.id!r}")
        self._tasks[task.id] = task
        self._cursor[task.id] = self._clock

    def remove(self, task_id: str) -> None:
        """Remove a task by id, raising ``KeyError`` when it is unknown."""
        self._tasks.pop(task_id)
        self._cursor.pop(task_id)

    def get(self, task_id: str) -> ScheduledTask | None:
        """Return the task with the given id, or ``None`` when unknown."""
        return self._tasks.get(task_id)

    def advance(self, moment: datetime) -> tuple[tuple[ScheduledTask, datetime], ...]:
        """Advance the internal clock to *moment* and return every trigger in the interval.

        Triggers are delivered for each task in ``(cursor, moment]`` order, and
        the per-task cursor moves past them so nothing is delivered twice.
        Disabled tasks are skipped. Naive moments are rejected.
        """
        if moment.tzinfo is None:
            raise ScheduleError("moment must be timezone-aware")
        self._clock = moment
        if self.paused:
            return ()
        pending: list[tuple[datetime, int, ScheduledTask]] = []
        for index, task in enumerate(self._tasks.values()):
            if not task.enabled:
                continue
            trigger = task.cron.next_after(self._cursor[task.id])
            while trigger <= moment:
                pending.append((trigger, index, task))
                self._cursor[task.id] = trigger
                trigger = task.cron.next_after(trigger)
        pending.sort(key=lambda item: (item[0], item[1]))
        return tuple((task, trigger) for trigger, _index, task in pending)

    def due(self) -> tuple[tuple[ScheduledTask, datetime], ...]:
        """Deliver every trigger whose time is at or before the injected now."""
        return self.advance(self._now())

    def next_due(self) -> tuple[ScheduledTask, datetime] | None:
        """Return the earliest not-yet-delivered (task, trigger), or ``None``."""
        if self.paused:
            return None
        best_trigger: datetime | None = None
        best_task: ScheduledTask | None = None
        for task in self._tasks.values():
            if not task.enabled:
                continue
            trigger = task.cron.next_after(self._cursor[task.id])
            if best_trigger is None or trigger < best_trigger:
                best_trigger = trigger
                best_task = task
        if best_task is None or best_trigger is None:
            return None
        return (best_task, best_trigger)
