"""What a message will roughly cost before it is sent, from how recent tasks went.

An agent task makes a varying number of model calls, so the estimate is a range drawn from the last
two weeks in the workspace: how large this conversation's requests are now (a new conversation:
how large a first request usually is), how many calls a task takes (usually, and for the longer
tenth), how much the model writes per call, and how much of each request the provider's cache
covered. With no history yet the caller's typical values are used, and the result says so.
"""

from __future__ import annotations

import math
import sqlite3
import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_workspace.core.cost import ModelPricing
from agent_workspace.storage.sqlite import SQLiteEventStore

_MAX_CALLS = 20.0
_DEFAULT_OUTPUT = 600
_DEFAULT_CALLS = 3.0
# Characters per token of a typed message; mixed Chinese and English text runs about this.
_CHARS_PER_TOKEN = 1.5


@dataclass(frozen=True, slots=True)
class RecordedCall:
    session_id: str
    task: str | None
    input_tokens: int
    output_tokens: int
    cached_tokens: int


def recent_calls(database: Path, workspace: str, since: datetime) -> list[RecordedCall]:
    """Model calls of tasks in [workspace] since [since] (context summaries left out)."""
    connection = SQLiteEventStore._open_read_only(database)
    try:
        rows = connection.execute(
            """
            SELECT u.session_id, u.correlation_id,
                   json_extract(u.data_json, '$.input_tokens'),
                   json_extract(u.data_json, '$.output_tokens'),
                   COALESCE(json_extract(u.data_json, '$.cached_tokens'), 0)
            FROM events AS u JOIN sessions AS s ON s.id = u.session_id
            WHERE u.type = 'usage.updated' AND s.workspace = ?
              AND julianday(u.created_at) >= julianday(?)
              AND json_extract(u.data_json, '$.kind') IS NULL
              AND json_type(u.data_json, '$.input_tokens') = 'integer'
              AND json_type(u.data_json, '$.output_tokens') = 'integer'
            ORDER BY u.session_id, u.sequence
            """,
            (workspace, since.isoformat()),
        ).fetchall()
    except sqlite3.Error as exc:
        raise OSError("usage history could not be read") from exc
    finally:
        connection.close()
    return [
        RecordedCall(row[0], row[1], int(row[2]), int(row[3]), int(row[4] or 0)) for row in rows
    ]


def project(
    calls: Sequence[RecordedCall],
    session_id: str | None,
    pricing: ModelPricing,
    message_chars: int,
    *,
    default_context: int,
) -> dict[str, Any]:
    """The range of a task's cost from recent calls and list prices (pure)."""
    first: dict[str, int] = {}
    latest: int | None = None
    for call in calls:
        first.setdefault(call.session_id, call.input_tokens)
        if call.session_id == session_id:
            latest = call.input_tokens
    if latest is not None:
        context = latest
    else:
        context = int(statistics.median(first.values())) if first else default_context
    message = math.ceil(max(0, message_chars) / _CHARS_PER_TOKEN)
    output = statistics.fmean(call.output_tokens for call in calls) if calls else _DEFAULT_OUTPUT
    inputs = sum(call.input_tokens for call in calls)
    cache = min(0.95, sum(call.cached_tokens for call in calls) / inputs) if inputs else 0.0
    per_task = sorted(Counter(call.task for call in calls if call.task).values())
    usual = min(_MAX_CALLS, statistics.fmean(per_task)) if per_task else _DEFAULT_CALLS
    if per_task:
        longer = min(_MAX_CALLS, float(per_task[max(0, math.ceil(len(per_task) * 0.9) - 1)]))
    else:
        longer = usual * 2.5
    cached_price = (
        pricing.cached_usd_per_million
        if pricing.cached_usd_per_million is not None
        else pricing.input_usd_per_million
    )

    def cost(count: float) -> float:
        total = 0.0
        for index in range(max(1, math.ceil(count))):
            weight = min(1.0, count - index) if count > index else 1.0
            # Each call carries what came before, plus what the task's earlier calls added.
            prompt = context + message + index * output
            cached = prompt * cache
            total += weight * (
                (prompt - cached) / 1e6 * pricing.input_usd_per_million
                + cached / 1e6 * cached_price
                + output / 1e6 * pricing.output_usd_per_million
            )
        return total

    return {
        "lowUsd": round(cost(1), 6),
        "expectedUsd": round(cost(usual), 6),
        "highUsd": round(cost(max(usual, longer)), 6),
        "calls": round(usual, 1),
        "contextTokens": context,
        "cacheRatio": round(cache, 2),
        "fromHistory": bool(calls),
    }


__all__ = ["RecordedCall", "project", "recent_calls"]
