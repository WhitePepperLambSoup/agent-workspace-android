"""Event replay patch planning and application.

Sequence gaps can be repaired deterministically: the first event of a session
becomes sequence 1 and every later event is numbered consecutively in storage
order. Causation and tool-state defects are reported but never rewritten
because no safe target can be inferred for a dangling reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_workspace.core.events import Event
from agent_workspace.core.replay_verifier import ReplayVerification, verify_event_replay


@dataclass(frozen=True, slots=True)
class EventReplayPatchEntry:
    session_id: str
    event_id: str
    old_sequence: int | None
    new_sequence: int

    def to_document(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "event_id": self.event_id,
            "old_sequence": self.old_sequence,
            "new_sequence": self.new_sequence,
        }


@dataclass(frozen=True, slots=True)
class EventReplayPatch:
    entries: tuple[EventReplayPatchEntry, ...]
    before: ReplayVerification
    after: ReplayVerification

    @property
    def changed(self) -> bool:
        return bool(self.entries)

    def to_document(self) -> dict[str, Any]:
        return {
            "before": self.before.to_document(),
            "after": self.after.to_document(),
            "entries": [entry.to_document() for entry in self.entries],
        }


def build_event_replay_patch(events: list[Event]) -> EventReplayPatch:
    before = verify_event_replay(events)
    entries: list[EventReplayPatchEntry] = []
    next_sequences: dict[str, int] = {}
    for event in events:
        expected = next_sequences.get(event.session_id, 1)
        if event.sequence != expected:
            entries.append(
                EventReplayPatchEntry(
                    session_id=event.session_id,
                    event_id=event.id,
                    old_sequence=event.sequence,
                    new_sequence=expected,
                )
            )
        next_sequences[event.session_id] = expected + 1
    patched = apply_event_replay_patch(events, entries)
    after = verify_event_replay(patched)
    return EventReplayPatch(entries=tuple(entries), before=before, after=after)


def apply_event_replay_patch(
    events: list[Event],
    entries: list[EventReplayPatchEntry] | tuple[EventReplayPatchEntry, ...],
) -> list[Event]:
    by_event_id = {entry.event_id: entry.new_sequence for entry in entries}
    return [
        event.with_sequence(by_event_id[event.id]) if event.id in by_event_id else event
        for event in events
    ]


def event_replay_patch_document(events: list[Event]) -> dict[str, Any]:
    return build_event_replay_patch(events).to_document()


__all__ = [
    "EventReplayPatch",
    "EventReplayPatchEntry",
    "apply_event_replay_patch",
    "build_event_replay_patch",
    "event_replay_patch_document",
]
