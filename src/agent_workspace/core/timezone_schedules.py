"""Timezone-aware schedule rules.

A cron expression plus a timezone defines local-time triggers. The timezone
may be an IANA name when the host has an IANA database (or the ``tzdata``
package), or a fixed offset such as ``UTC``, ``+09:00`` or ``-05:00`` so
schedules stay portable on Windows hosts without IANA data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agent_workspace.core.scheduler import CronSchedule

_FIXED_OFFSET = re.compile(r"^(?:UTC)?(?P<sign>[+-])(?P<hours>\d{1,2}):?(?P<minutes>\d{2})$")


class TimezoneScheduleError(ValueError):
    pass


def parse_timezone(value: str) -> tzinfo:
    if not isinstance(value, str) or not value:
        raise TimezoneScheduleError("timezone may not be empty")
    if value.upper() in {"UTC", "Z"}:
        return UTC
    match = _FIXED_OFFSET.fullmatch(value.upper())
    if match is not None:
        sign = 1 if match.group("sign") == "+" else -1
        hours = int(match.group("hours"))
        minutes = int(match.group("minutes"))
        if hours > 23 or minutes > 59:
            raise TimezoneScheduleError(f"invalid fixed timezone offset: {value}")
        offset = timedelta(hours=hours, minutes=minutes)
        return timezone(sign * offset, name=value)
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise TimezoneScheduleError(f"unknown IANA timezone: {value}") from exc


@dataclass(frozen=True, slots=True)
class TimezoneSchedule:
    expression: str
    timezone: str

    def __post_init__(self) -> None:
        parse_timezone(self.timezone)
        try:
            CronSchedule.parse(self.expression)
        except ValueError as exc:
            raise TimezoneScheduleError(f"invalid cron expression: {self.expression}") from exc

    @property
    def cron(self) -> CronSchedule:
        return CronSchedule.parse(self.expression)

    @property
    def zone(self) -> tzinfo:
        return parse_timezone(self.timezone)

    def to_document(self) -> dict[str, Any]:
        return {"expression": self.expression, "timezone": self.timezone}


@dataclass(frozen=True, slots=True)
class TimezoneSchedulePreview:
    schedule: TimezoneSchedule
    now_utc: datetime
    next_runs_utc: tuple[datetime, ...]

    def to_document(self) -> dict[str, Any]:
        return {
            "expression": self.schedule.expression,
            "timezone": self.schedule.timezone,
            "now_utc": self.now_utc.isoformat(),
            "next_runs_utc": [moment.isoformat() for moment in self.next_runs_utc],
        }


def timezone_schedule_preview(
    schedule: TimezoneSchedule,
    *,
    now_utc: datetime | None = None,
    count: int = 5,
) -> TimezoneSchedulePreview:
    if count < 1 or count > 100:
        raise TimezoneScheduleError("preview count must be from 1 to 100")
    reference = now_utc or datetime.now(UTC)
    if reference.tzinfo is None:
        raise TimezoneScheduleError("reference time must be timezone-aware")
    reference = reference.astimezone(UTC)
    local_now = reference.astimezone(schedule.zone)
    runs_utc: list[datetime] = []
    cursor = local_now
    for _ in range(count):
        cursor = schedule.cron.next_after(cursor)
        utc_run = cursor.astimezone(UTC)
        while utc_run <= reference:
            cursor = schedule.cron.next_after(cursor)
            utc_run = cursor.astimezone(UTC)
        runs_utc.append(utc_run)
    return TimezoneSchedulePreview(
        schedule=schedule,
        now_utc=reference,
        next_runs_utc=tuple(runs_utc),
    )


__all__ = [
    "TimezoneSchedule",
    "TimezoneScheduleError",
    "TimezoneSchedulePreview",
    "parse_timezone",
    "timezone_schedule_preview",
]
