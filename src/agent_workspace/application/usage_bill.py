"""What a month of model calls cost, from the usage every call recorded.

Each call's usage is priced with the model it went to (the ``model.requested`` event it answers)
at list prices, so totals are estimates. Agent runs keep their own databases; the caller passes
those along with the main one. Months and days follow the computer's local calendar.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path

from agent_workspace.core.cost import UNKNOWN_PRICING, estimate_cost_usd, resolve_pricing
from agent_workspace.storage.sqlite import SQLiteEventStore


@dataclass(frozen=True, slots=True)
class ModelBill:
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float
    priced: bool


@dataclass(frozen=True, slots=True)
class MonthBill:
    month: str  # YYYY-MM
    calls: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float
    models: tuple[ModelBill, ...]
    days: tuple[tuple[str, float], ...]  # (YYYY-MM-DD, cost) for each day with calls
    unpriced_calls: int

    @property
    def cache_ratio(self) -> float:
        """The share of input the provider's cache covered."""
        return self.cached_tokens / self.input_tokens if self.input_tokens else 0.0


def _local_zone() -> tzinfo:
    zone = datetime.now().astimezone().tzinfo
    return zone if zone is not None else UTC


def month_bounds(month: str, zone: tzinfo | None = None) -> tuple[datetime, datetime]:
    """The first moment of the month and of the next one, in UTC."""
    local = zone or _local_zone()
    start = datetime.strptime(month, "%Y-%m").replace(tzinfo=local)
    following = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start.astimezone(UTC), following.astimezone(UTC)


def current_month(now: datetime | None = None, zone: tzinfo | None = None) -> str:
    moment = (now or datetime.now(UTC)).astimezone(zone or _local_zone())
    return moment.strftime("%Y-%m")


def _calls(database: Path, start: datetime, end: datetime) -> list[tuple[str, str, int, int, int]]:
    connection = SQLiteEventStore._open_read_only(database)
    try:
        rows = connection.execute(
            """
            SELECT COALESCE(json_extract(m.data_json, '$.model'), ''), u.created_at,
                   json_extract(u.data_json, '$.input_tokens'),
                   json_extract(u.data_json, '$.output_tokens'),
                   COALESCE(json_extract(u.data_json, '$.cached_tokens'), 0)
            FROM events AS u LEFT JOIN events AS m ON m.id = u.causation_id
            WHERE u.type = 'usage.updated'
              AND julianday(u.created_at) >= julianday(?)
              AND julianday(u.created_at) < julianday(?)
              AND json_type(u.data_json, '$.input_tokens') = 'integer'
              AND json_type(u.data_json, '$.output_tokens') = 'integer'
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    except sqlite3.Error as error:
        raise OSError("usage history could not be read") from error
    finally:
        connection.close()
    return [(str(row[0]), str(row[1]), int(row[2]), int(row[3]), int(row[4] or 0)) for row in rows]


def month_bill(databases: Iterable[Path], month: str, *, zone: tzinfo | None = None) -> MonthBill:
    local = zone or _local_zone()
    start, end = month_bounds(month, local)
    per_model: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    per_day: dict[str, float] = defaultdict(float)
    model_cost: dict[str, float] = defaultdict(float)
    for database in databases:
        if not database.is_file():
            continue
        for model, created_at, input_tokens, output_tokens, cached in _calls(database, start, end):
            cost = estimate_cost_usd(model, input_tokens, output_tokens, min(cached, input_tokens))
            totals = per_model[model]
            totals[0] += 1
            totals[1] += input_tokens
            totals[2] += output_tokens
            totals[3] += cached
            model_cost[model] += cost
            try:
                day = datetime.fromisoformat(created_at).astimezone(local).strftime("%Y-%m-%d")
            except ValueError:
                continue
            per_day[day] += cost
    models = tuple(
        sorted(
            (
                ModelBill(
                    model=model or "unknown",
                    calls=totals[0],
                    input_tokens=totals[1],
                    output_tokens=totals[2],
                    cached_tokens=totals[3],
                    cost_usd=round(model_cost[model], 6),
                    priced=bool(model) and resolve_pricing(model) is not UNKNOWN_PRICING,
                )
                for model, totals in per_model.items()
            ),
            key=lambda item: item.cost_usd,
            reverse=True,
        )
    )
    return MonthBill(
        month=month,
        calls=sum(item.calls for item in models),
        input_tokens=sum(item.input_tokens for item in models),
        output_tokens=sum(item.output_tokens for item in models),
        cached_tokens=sum(item.cached_tokens for item in models),
        cost_usd=round(sum(model_cost.values()), 6),
        models=models,
        days=tuple(sorted((day, round(cost, 6)) for day, cost in per_day.items())),
        unpriced_calls=sum(item.calls for item in models if not item.priced),
    )


__all__ = ["ModelBill", "MonthBill", "current_month", "month_bill", "month_bounds"]
