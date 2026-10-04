"""Security audit export for SIEM/Webhook consumers.

Only explicitly allowlisted event types leave the machine. Payloads are
redacted with the shared policy redactor before writing.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from agent_workspace.application.ports import EventStore
from agent_workspace.policy.redaction import Redactor
from agent_workspace.storage.analytics import event_document

_AUDIT_EVENT_TYPES = frozenset(
    {
        "turn.started",
        "turn.completed",
        "turn.failed",
        "turn.cancelled",
        "tool.proposed",
        "tool.approved",
        "tool.rejected",
        "tool.approval_required",
        "tool.started",
        "tool.settled",
        "tool.failed",
        "tool.unknown",
        "tool.cancelled",
        "mode.changed",
        "model.attempted",
        "model.completed",
        "model.output.limited",
        "context.compacted",
        "session.comment.added",
        "memory.upserted",
        "memory.deleted",
        "goal.created",
        "goal.updated",
        "plan.step.upserted",
        "model.optimization.applied",
        "run_queue.enqueued",
        "run_queue.claimed",
        "run_queue.completed",
        "run_queue.failed",
        "run_queue.cancelled",
        "run_queue.heartbeat",
        "run_queue.requeued",
        "pipeline.created",
        "pipeline.started",
        "pipeline.step.started",
        "pipeline.step.completed",
        "pipeline.step.retrying",
        "pipeline.completed",
        "pipeline.failed",
    }
)


def is_audit_event_type(event_type: str) -> bool:
    return event_type in _AUDIT_EVENT_TYPES


def export_audit_events(
    store: EventStore,
    destination: str | Path,
    *,
    session_ids: Iterable[str] = (),
    redactor: Redactor | None = None,
) -> int:
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    redactor = redactor or Redactor()
    resolved_sessions = tuple(session_ids)
    if not resolved_sessions:
        resolved_sessions = tuple(session.id for session in store.list_sessions(limit=10_000))
    written = 0
    with target.open("w", encoding="utf-8", newline="\n") as stream:
        for session_id in resolved_sessions:
            for event in store.list_events(session_id):
                if not is_audit_event_type(event.type):
                    continue
                document = event_document(event)
                document["data"] = redactor.redact_value(document["data"])
                stream.write(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n")
                written += 1
    return written


__all__ = ["export_audit_events", "is_audit_event_type"]
