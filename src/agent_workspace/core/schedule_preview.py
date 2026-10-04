"""Cron next-run previews for schedules and the CLI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from agent_workspace.core.scheduler import CronSchedule, ScheduleError


@dataclass(frozen=True, slots=True)
class SchedulePreview:
    expression: str
    now: datetime
    next_runs: tuple[datetime, ...]

    def to_document(self) -> dict[str, Any]:
        return {
            "expression": self.expression,
            "now": self.now.isoformat(),
            "next_runs": [moment.isoformat() for moment in self.next_runs],
        }


def schedule_next_runs(
    expression: str,
    *,
    now: datetime | None = None,
    count: int = 5,
) -> SchedulePreview:
    if count < 1 or count > 100:
        raise ScheduleError("preview count must be between 1 and 100")
    reference = now or datetime.now(UTC)
    if reference.tzinfo is None:
        raise ScheduleError("preview reference time must be timezone-aware")
    schedule = CronSchedule.parse(expression)
    runs: list[datetime] = []
    cursor = reference
    for _ in range(count):
        cursor = schedule.next_after(cursor)
        runs.append(cursor)
    return SchedulePreview(
        expression=schedule.expression,
        now=reference,
        next_runs=tuple(runs),
    )


__all__ = ["SchedulePreview", "schedule_next_runs"]
