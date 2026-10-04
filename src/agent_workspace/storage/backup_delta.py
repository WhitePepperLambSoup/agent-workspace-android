"""Incremental event backup and delta package export/import."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from agent_workspace.application.ports import EventStore
from agent_workspace.core.events import Event


@dataclass(frozen=True, slots=True)
class EventDeltaPackage:
    session_id: str
    since_seq: int
    until_seq: int
    event_count: int
    events_data: tuple[dict[str, Any], ...]
    checksum_sha256: str
    created_at: float

    def to_document(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "since_seq": self.since_seq,
            "until_seq": self.until_seq,
            "event_count": self.event_count,
            "checksum_sha256": self.checksum_sha256,
            "created_at": self.created_at,
            "events_data": list(self.events_data),
        }


def _compute_package_checksum(events_data: Sequence[dict[str, Any]]) -> str:
    raw = json.dumps(events_data, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _event_to_dict(e: Event) -> dict[str, Any]:
    return {
        "id": e.id,
        "session_id": e.session_id,
        "type": e.type,
        "data": e.data,
        "schema_version": e.schema_version,
        "sequence": e.sequence,
        "causation_id": e.causation_id,
        "correlation_id": e.correlation_id,
        "created_at": e.created_at,
    }


def export_event_delta(
    events: Sequence[Event],
    *,
    session_id: str,
    since_seq: int = 0,
) -> EventDeltaPackage:
    """Export an incremental delta package of events since a sequence number."""
    if since_seq < 0:
        raise ValueError("since_seq cannot be negative")

    # Filter events for the session and after since_seq
    selected = [
        e
        for e in events
        if e.session_id == session_id and (e.sequence is not None and e.sequence > since_seq)
    ]
    selected_data = tuple(_event_to_dict(e) for e in selected)
    until_seq = max((e.sequence for e in selected if e.sequence is not None), default=since_seq)
    checksum = _compute_package_checksum(selected_data)

    return EventDeltaPackage(
        session_id=session_id,
        since_seq=since_seq,
        until_seq=until_seq,
        event_count=len(selected),
        events_data=selected_data,
        checksum_sha256=checksum,
        created_at=time.time(),
    )


def import_event_delta(
    package: EventDeltaPackage,
    store: EventStore,
) -> int:
    """Validate and import events from an incremental delta package."""
    # 1. Verify integrity
    computed_checksum = _compute_package_checksum(package.events_data)
    if computed_checksum != package.checksum_sha256:
        raise ValueError("Delta package checksum verification failed: corrupted data")

    if not package.events_data:
        return 0

    # 2. Reconstruct Event objects
    reconstructed: list[Event] = []
    for d in package.events_data:
        raw_created_at = d.get("created_at")
        event = Event(
            id=str(d["id"]),
            session_id=str(d["session_id"]),
            type=str(d["type"]),
            data=d.get("data", {}),
            schema_version=d.get("schema_version", 1),
            causation_id=d.get("causation_id"),
            correlation_id=d.get("correlation_id"),
            created_at=str(raw_created_at) if raw_created_at is not None else "",
        )
        reconstructed.append(event)

    # 3. Append to store
    store.append_many(tuple(reconstructed))
    return len(reconstructed)
