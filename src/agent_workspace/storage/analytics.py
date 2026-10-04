"""Analytics export helpers.

Exports are intentionally read-only projections over the event log. They
never mutate the database and are suitable for CI dashboards and offline
analysis tools.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_workspace.application.ports import EventStore
from agent_workspace.core.events import Event


def event_document(event: Event) -> dict[str, Any]:
    return {
        "id": event.id,
        "session_id": event.session_id,
        "type": event.type,
        "data": event.data,
        "schema_version": event.schema_version,
        "sequence": event.sequence,
        "causation_id": event.causation_id,
        "correlation_id": event.correlation_id,
        "created_at": event.created_at,
    }


def export_events_ndjson(
    store: EventStore,
    destination: str | Path,
    session_ids: Iterable[str] = (),
) -> int:
    """Write selected sessions' events as one JSON object per line.

    Returns the number of events written. When ``session_ids`` is empty, all
    sessions currently visible to the store are exported.
    """
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    resolved_session_ids = tuple(session_ids)
    if not resolved_session_ids:
        resolved_session_ids = tuple(session.id for session in store.list_sessions(limit=10_000))
    written = 0
    with target.open("w", encoding="utf-8", newline="\n") as stream:
        for session_id in resolved_session_ids:
            for event in store.list_events(session_id):
                stream.write(
                    json.dumps(
                        event_document(event),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                written += 1
    return written


def tool_call_summary(events: Iterable[Event]) -> dict[str, Any]:
    """Aggregate started/settled/failed tool calls by tool name."""
    summary: dict[str, dict[str, int]] = {}
    for event in events:
        if event.type not in {"tool.started", "tool.settled", "tool.failed", "tool.rejected"}:
            continue
        name = event.data.get("name")
        if not isinstance(name, str):
            continue
        bucket = summary.setdefault(name, {"started": 0, "settled": 0, "failed": 0, "rejected": 0})
        if event.type == "tool.started":
            bucket["started"] += 1
        elif event.type == "tool.settled":
            bucket["settled"] += 1
        elif event.type == "tool.failed":
            bucket["failed"] += 1
        elif event.type == "tool.rejected":
            bucket["rejected"] += 1
    return {"tool_calls": summary}


def tool_latency_summary(events: Iterable[Event]) -> dict[str, Any]:
    """Pair tool.started with its terminal event and report durations in ms."""
    started: dict[str, tuple[str, datetime]] = {}
    durations: dict[str, list[int]] = {}
    for event in events:
        attempt_id = event.data.get("attempt_id")
        if not isinstance(attempt_id, str):
            continue
        if event.type == "tool.started":
            name = event.data.get("name")
            if isinstance(name, str):
                started[attempt_id] = (name, _event_time(event))
        elif event.type in {"tool.settled", "tool.failed", "tool.unknown", "tool.cancelled"}:
            entry = started.pop(attempt_id, None)
            if entry is None:
                continue
            name, start_time = entry
            end_time = _event_time(event)
            durations.setdefault(name, []).append(
                max(0, round((end_time - start_time).total_seconds() * 1000))
            )
    return {
        "tools": [
            {
                "name": name,
                "samples": values,
                "minimum_ms": min(values),
                "maximum_ms": max(values),
                "average_ms": round(sum(values) / len(values), 3),
            }
            for name, values in sorted(durations.items())
        ]
    }


def _event_time(event: Event) -> datetime:
    value = datetime.fromisoformat(event.created_at)
    if value.tzinfo is None:
        raise ValueError("event timestamps must be timezone-aware")
    return value


__all__ = [
    "event_document",
    "export_events_ndjson",
    "tool_call_summary",
]
