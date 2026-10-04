"""Append-only event replay verifier.

Replays events in storage order and checks sequence continuity, causation
references, and the small set of tool-attempt state transitions used by the
durable projections.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_workspace.core.events import Event


@dataclass(frozen=True, slots=True)
class ReplayVerification:
    sessions: int
    events: int
    sequence_gaps: int
    dangling_causation: int
    invalid_transitions: int
    valid: bool

    def to_document(self) -> dict[str, object]:
        return {
            "sessions": self.sessions,
            "events": self.events,
            "sequence_gaps": self.sequence_gaps,
            "dangling_causation": self.dangling_causation,
            "invalid_transitions": self.invalid_transitions,
            "valid": self.valid,
        }


@dataclass(slots=True)
class _SessionState:
    next_sequence: int = 1
    seen_event_ids: set[str] = field(default_factory=set)
    tool_states: dict[str, str] = field(default_factory=dict)


def verify_event_replay(events: list[Event]) -> ReplayVerification:
    sessions: dict[str, _SessionState] = {}
    sequence_gaps = 0
    dangling_causation = 0
    invalid_transitions = 0
    for event in events:
        state = sessions.setdefault(event.session_id, _SessionState())
        if event.sequence is not None and event.sequence != state.next_sequence:
            sequence_gaps += 1
        if event.sequence is not None:
            state.next_sequence = max(state.next_sequence, event.sequence + 1)
        state.seen_event_ids.add(event.id)
        if event.causation_id is not None and event.causation_id not in state.seen_event_ids:
            dangling_causation += 1
        if event.type in {"tool.proposed", "tool.started", "tool.settled", "tool.failed"}:
            attempt_id = event.data.get("attempt_id")
            if isinstance(attempt_id, str):
                previous = state.tool_states.get(attempt_id)
                if not _valid_tool_transition(previous, event.type):
                    invalid_transitions += 1
                state.tool_states[attempt_id] = event.type
    valid = sequence_gaps == 0 and dangling_causation == 0 and invalid_transitions == 0
    return ReplayVerification(
        sessions=len(sessions),
        events=len(events),
        sequence_gaps=sequence_gaps,
        dangling_causation=dangling_causation,
        invalid_transitions=invalid_transitions,
        valid=valid,
    )


def _valid_tool_transition(previous: str | None, current: str) -> bool:
    if current == "tool.proposed":
        return previous is None
    if current == "tool.started":
        return previous == "tool.proposed"
    if current in {"tool.settled", "tool.failed"}:
        return previous == "tool.started"
    return True


__all__ = ["ReplayVerification", "verify_event_replay"]
