"""Session transcript merge tool.

Multiple transcripts are flattened and sorted chronologically. Exact duplicate
events (same type, data, and timestamp) are counted and dropped; conflicting
same-sequence events from different sources are preserved as-is and reported
so a caller can review them instead of silently choosing a winner.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from agent_workspace.core.events import Event


@dataclass(frozen=True, slots=True)
class MergedTranscriptEntry:
    source_session: str
    event: Event

    def to_document(self) -> dict[str, Any]:
        return {
            "source_session": self.source_session,
            "event_id": self.event.id,
            "type": self.event.type,
            "sequence": self.event.sequence,
            "created_at": self.event.created_at,
        }


@dataclass(frozen=True, slots=True)
class TranscriptMergeOptions:
    deduplicate: bool = True
    sort_key: str = "created_at"

    def validate(self) -> None:
        if self.sort_key not in {"created_at", "sequence"}:
            raise ValueError("merge sort_key must be 'created_at' or 'sequence'")
        if not isinstance(self.deduplicate, bool):
            raise ValueError("merge deduplicate flag must be a boolean")


@dataclass(frozen=True, slots=True)
class TranscriptMergeResult:
    entries: tuple[MergedTranscriptEntry, ...]
    sources: tuple[str, ...]
    duplicates_removed: int
    sequence_conflicts: int

    def to_document(self) -> dict[str, Any]:
        return {
            "entries": [entry.to_document() for entry in self.entries],
            "sources": list(self.sources),
            "duplicates_removed": self.duplicates_removed,
            "sequence_conflicts": self.sequence_conflicts,
        }


def _event_signature(event: Event) -> str:
    payload = json.dumps(
        {
            "type": event.type,
            "data": event.data,
            "created_at": event.created_at,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _event_order(event: Event) -> tuple[str, int]:
    sequence = event.sequence if event.sequence is not None else 0
    return event.created_at, sequence


def merge_session_transcripts(
    sources: dict[str, list[Event]],
    *,
    options: TranscriptMergeOptions | None = None,
) -> TranscriptMergeResult:
    options = options or TranscriptMergeOptions()
    options.validate()
    if not sources:
        raise ValueError("at least one transcript source is required")
    flattened: list[tuple[str, Event]] = []
    for source_session, events in sources.items():
        if not source_session:
            raise ValueError("transcript source session ids may not be empty")
        flattened.extend((source_session, event) for event in events)

    if options.sort_key == "sequence":
        flattened.sort(
            key=lambda item: (
                item[1].created_at[:10],
                item[1].sequence if item[1].sequence is not None else 0,
                item[1].created_at,
                item[0],
                item[1].id,
            )
        )
    else:
        flattened.sort(key=lambda item: (item[1].created_at, item[0], item[1].id))

    entries: list[MergedTranscriptEntry] = []
    seen_signatures: set[str] = set()
    duplicates_removed = 0
    sequence_owners: dict[tuple[str, int], str] = {}
    sequence_conflicts = 0
    for source_session, event in flattened:
        if options.deduplicate:
            signature = _event_signature(event)
            if signature in seen_signatures:
                duplicates_removed += 1
                continue
            seen_signatures.add(signature)
        if event.sequence is not None:
            key = (event.created_at[:10], event.sequence)
            owner = sequence_owners.get(key)
            if owner is not None and owner != source_session:
                sequence_conflicts += 1
            sequence_owners[key] = source_session
        entries.append(MergedTranscriptEntry(source_session=source_session, event=event))
    return TranscriptMergeResult(
        entries=tuple(entries),
        sources=tuple(sorted(sources)),
        duplicates_removed=duplicates_removed,
        sequence_conflicts=sequence_conflicts,
    )


__all__ = [
    "MergedTranscriptEntry",
    "TranscriptMergeOptions",
    "TranscriptMergeResult",
    "merge_session_transcripts",
]
