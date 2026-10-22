"""What a message will roughly cost before it is sent, from how this phone's recent tasks went.

An agent task makes a varying number of model calls, so the estimate is a range drawn from the last
two weeks in this workspace: how large this conversation's requests are now (a new conversation:
how large a first request usually is), how many calls a task takes (usually, and for the longer
tenth), how much the model writes per call, and how much of each request the provider's cache
covered. Prices are the ones the Tokens & cost page uses. No history yet: typical values, marked.
"""

from __future__ import annotations

import math
import sqlite3
import statistics
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from agent_workspace.storage.sqlite import SQLiteEventStore

_DAYS = 14
# Typical values when this phone has no history yet (a phone request: prompt + tools is ~20K tokens).
_DEFAULT_CONTEXT = 20_000
_DEFAULT_OUTPUT = 600
_DEFAULT_CALLS = 3.0
_MAX_CALLS = 20.0


def _calls(database: Path, workspace: Path, cutoff: datetime) -> list[dict[str, Any]]:
    """Recent model calls of tasks in [workspace] (summaries left out), oldest first."""
    connection = SQLiteEventStore._open_read_only(database)
    try:
        rows = connection.execute(
            """
            SELECT u.session_id, u.correlation_id,
                   json_extract(u.data_json, '$.input_tokens') AS input_tokens,
                   json_extract(u.data_json, '$.output_tokens') AS output_tokens,
                   COALESCE(json_extract(u.data_json, '$.cached_tokens'), 0) AS cached_tokens
            FROM events AS u JOIN sessions AS s ON s.id = u.session_id
            WHERE u.type = 'usage.updated' AND s.workspace = ?
              AND julianday(u.created_at) >= julianday(?)
              AND json_extract(u.data_json, '$.kind') IS NULL
              AND json_type(u.data_json, '$.input_tokens') = 'integer'
              AND json_type(u.data_json, '$.output_tokens') = 'integer'
            ORDER BY u.session_id, u.sequence
            """,
            (str(workspace), cutoff.isoformat()),
        ).fetchall()
    except sqlite3.Error as exc:
        raise OSError("usage database could not be read") from exc
    finally:
        connection.close()
    return [{"session_id": row[0], "task": row[1], "input": int(row[2]), "output": int(row[3]),
             "cached": int(row[4] or 0)} for row in rows]  # fmt: skip


def project(calls: list[dict[str, Any]], session_id: str | None, pricing: dict[str, Any], message_chars: int) -> dict[str, Any]:
    """The range from recent calls and prices (pure, for tests)."""
    first: dict[str, int] = {}
    latest = None
    for call in calls:
        first.setdefault(call["session_id"], call["input"])
        if call["session_id"] == session_id:
            latest = call["input"]
    context = latest if latest is not None else (int(statistics.median(first.values())) if first else _DEFAULT_CONTEXT)
    message = math.ceil(max(0, int(message_chars)) / 1.5)
    output = statistics.fmean(call["output"] for call in calls) if calls else _DEFAULT_OUTPUT
    inputs = sum(call["input"] for call in calls)
    cache = min(0.95, sum(call["cached"] for call in calls) / inputs) if inputs else 0.0
    per_task = sorted(Counter(call["task"] for call in calls if call["task"]).values())
    usual = min(_MAX_CALLS, statistics.fmean(per_task)) if per_task else _DEFAULT_CALLS
    longer = min(_MAX_CALLS, float(per_task[min(len(per_task) - 1, math.ceil(len(per_task) * 0.9) - 1)])) if per_task else usual * 2.5

    def cost(count: float) -> float:
        total = 0.0
        for index in range(max(1, math.ceil(count))):
            weight = min(1.0, count - index) if count > index else 1.0
            # Each call carries what came before, plus what the earlier calls of the task added.
            prompt = context + message + index * output
            cached = prompt * cache
            total += weight * (
                (prompt - cached) / 1e6 * pricing["input_usd_per_million"]
                + cached / 1e6 * pricing["cached_usd_per_million"]
                + output / 1e6 * pricing["output_usd_per_million"]
            )
        return total

    return {
        "low_usd": round(cost(1), 6),
        "expected_usd": round(cost(usual), 6),
        "high_usd": round(cost(max(usual, longer)), 6),
        "calls": round(usual, 1),
        "context_tokens": context,
        "cache_ratio": round(cache, 2),
        "from_history": bool(calls),
    }


def estimate(runtime: Any, session_id: str | None, model: str, message_chars: int = 0) -> dict[str, Any]:
    from mobile_usage import _pricing, _read_pricing
    from mobile_workspace import runtime_workspace

    _, document, _ = _read_pricing(runtime)
    pricing = _pricing(model, document["models"])
    if pricing is None:
        return {"priced": False, "model": model}
    if not any(pricing[key] for key in ("input_usd_per_million", "output_usd_per_million")):
        return {"priced": True, "free": True, "model": model}
    cutoff = datetime.now(UTC) - timedelta(days=_DAYS)
    calls = _calls(Path(runtime.database), runtime_workspace(runtime), cutoff)
    return {"priced": True, "free": False, "model": model, **project(calls, session_id, pricing, message_chars)}
