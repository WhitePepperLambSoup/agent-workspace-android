from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, cast

PROTOCOL_VERSION: Final = 1
MAX_MESSAGE_BYTES: Final = 1_048_576
MAX_IDENTIFIER_CHARS: Final = 256
AUTONOMY_VALUES: Final = frozenset({"ask", "workspace", "yolo", "full_access"})

_COMMAND_TYPES: Final = frozenset(
    {
        "app.handshake",
        "app.bootstrap",
        "app.shutdown",
        "workspace.open",
        "workspace.sessions.list",
        "session.list",
        "session.open",
        "session.history",
        "events.replay",
        "session.create",
        "session.presentation.set",
        "session.search",
        "research.sources.list",
        "research.source.read",
        "research.citations.list",
        "workspace.summary.get",
        "changes.list",
        "changes.inspect",
        "jobs.list",
        "jobs.logs",
        "jobs.stop",
        "terminal.start",
        "terminal.input",
        "terminal.resize",
        "terminal.status",
        "terminal.list",
        "terminal.replay",
        "terminal.stop",
        "provider.list",
        "provider.get",
        "provider.set",
        "provider.clear",
        "provider.delete",
        "provider.default",
        "provider.test",
        "provider.bootstrap",
        "provider.health",
        "prompt.optimize",
        "turn.start",
        "turn.steer",
        "turn.cancel",
        "runtime.mode.set",
        "runtime.autonomy.set",
        "approval.resolve",
        "workspace.files.tree",
        "workspace.file.read",
        "workspace.file.write",
        "workspace.git.diff",
        "workspace.git.revert",
        "workspace.git.undo",
        "workspace.git.deliver",
        "workspace.context.get",
        "workspace.tasks.list",
        "workspace.tasks.create",
        "workspace.tasks.update",
        "workspace.tasks.delete",
        "workspace.schedule.list",
        "workspace.schedule.create",
        "workspace.schedule.update",
        "workspace.schedule.delete",
        "workspace.schedule.pause",
        "workspace.schedule.resume",
        "workspace.schedule.run_now",
        "workspace.schedule.preview",
        "workspace.schedules.list",
        "workspace.schedules.create",
        "workspace.schedules.update",
        "workspace.schedules.delete",
        "workspace.schedules.pause",
        "workspace.schedules.resume",
        "workspace.schedules.run_now",
        "workspace.queue.list",
        "workspace.queue.get",
        "workspace.collaborations.list",
        "workspace.collaborations.get",
        "workspace.collaborations.cancel",
        "workspace.collaborations.resume",
        "workspace.deliveries.list",
        "workspace.deliveries.get",
        "workspace.deliveries.cancel",
        "workspace.deliveries.resume",
        "workspace.runs.list",
        "workspace.runs.get",
        "workspace.runs.create",
        "workspace.runs.update",
        "workspace.runs.start",
        "workspace.runs.pause",
        "workspace.runs.resume",
        "workspace.runs.cancel",
        "workspace.runs.cleanup",
        "run.history.page",
        "workspace.runs.history",
        "run.evidence.page",
        "workspace.runs.evidence",
        "workspace.plan.retry",
        "workspace.plan.skip",
        "workspace.runs.failure.action",
        "workspace.plan.list",
        "workspace.plan.create",
        "workspace.plan.update",
        "workspace.plan.delete",
        "workspace.attention.list",
        "workspace.attention.resolve",
        "workspace.review.list",
        "workspace.review.get",
        "workspace.review.create",
        "workspace.review.comments.create",
        "workspace.review.comments.resolve",
        "workspace.review.comments.followup",
        "workspace.review.pr.create",
        "workspace.review.pr.refresh",
        "system.doctor",
    }
)
_RESPONSE_TYPES: Final = frozenset(
    {
        "app.handshake.result",
        "app.bootstrap.result",
        "app.shutdown.result",
        "workspace.open.result",
        "workspace.sessions.list.result",
        "session.list.result",
        "session.open.result",
        "session.history.result",
        "events.replay.result",
        "session.create.result",
        "session.presentation.set.result",
        "session.search.result",
        "research.sources.list.result",
        "research.source.read.result",
        "research.citations.list.result",
        "workspace.summary.get.result",
        "changes.list.result",
        "changes.inspect.result",
        "jobs.list.result",
        "jobs.logs.result",
        "jobs.stop.result",
        "terminal.start.result",
        "terminal.input.result",
        "terminal.resize.result",
        "terminal.status.result",
        "terminal.list.result",
        "terminal.replay.result",
        "terminal.stop.result",
        "provider.list.result",
        "provider.get.result",
        "provider.set.result",
        "provider.clear.result",
        "provider.delete.result",
        "provider.default.result",
        "provider.test.result",
        "provider.bootstrap.result",
        "provider.health.result",
        "prompt.optimize.result",
        "turn.start.result",
        "turn.steer.result",
        "turn.cancel.result",
        "runtime.mode.set.result",
        "runtime.autonomy.set.result",
        "approval.resolve.result",
        "workspace.files.tree.result",
        "workspace.file.read.result",
        "workspace.file.write.result",
        "workspace.git.diff.result",
        "workspace.git.revert.result",
        "workspace.git.undo.result",
        "workspace.git.deliver.result",
        "workspace.context.get.result",
        "workspace.tasks.list.result",
        "workspace.tasks.create.result",
        "workspace.tasks.update.result",
        "workspace.tasks.delete.result",
        "workspace.schedule.list.result",
        "workspace.schedule.create.result",
        "workspace.schedule.update.result",
        "workspace.schedule.delete.result",
        "workspace.schedule.pause.result",
        "workspace.schedule.resume.result",
        "workspace.schedule.run_now.result",
        "workspace.schedule.preview.result",
        "workspace.schedules.list.result",
        "workspace.schedules.create.result",
        "workspace.schedules.update.result",
        "workspace.schedules.delete.result",
        "workspace.schedules.pause.result",
        "workspace.schedules.resume.result",
        "workspace.schedules.run_now.result",
        "workspace.queue.list.result",
        "workspace.queue.get.result",
        "workspace.collaborations.list.result",
        "workspace.collaborations.get.result",
        "workspace.collaborations.cancel.result",
        "workspace.collaborations.resume.result",
        "workspace.deliveries.list.result",
        "workspace.deliveries.get.result",
        "workspace.deliveries.cancel.result",
        "workspace.deliveries.resume.result",
        "workspace.runs.list.result",
        "workspace.runs.get.result",
        "workspace.runs.create.result",
        "workspace.runs.update.result",
        "workspace.runs.start.result",
        "workspace.runs.pause.result",
        "workspace.runs.resume.result",
        "workspace.runs.cancel.result",
        "workspace.runs.cleanup.result",
        "run.history.page.result",
        "workspace.runs.history.result",
        "run.evidence.page.result",
        "workspace.runs.evidence.result",
        "workspace.plan.retry.result",
        "workspace.plan.skip.result",
        "workspace.runs.failure.action.result",
        "workspace.plan.list.result",
        "workspace.plan.create.result",
        "workspace.plan.update.result",
        "workspace.plan.delete.result",
        "workspace.attention.list.result",
        "workspace.attention.resolve.result",
        "workspace.review.list.result",
        "workspace.review.get.result",
        "workspace.review.create.result",
        "workspace.review.comments.create.result",
        "workspace.review.comments.resolve.result",
        "workspace.review.comments.followup.result",
        "workspace.review.pr.create.result",
        "workspace.review.pr.refresh.result",
        "system.doctor.result",
        "app.error",
    }
)
_EVENT_TYPES: Final = frozenset(
    {
        "app.lifecycle",
        "runtime.started",
        "runtime.failed",
        "runtime.stopped",
        "runtime.error",
        "runtime.command_rejected",
        "runtime.mode_pending",
        "runtime.mode_applied",
        "runtime.autonomy_pending",
        "runtime.autonomy_applied",
        "runtime.autonomy_failed",
        "runtime.session_switch_failed",
        "runtime.workspace_switch_failed",
        "runtime.turn_cancel_requested",
        "runtime.turn_cancelled",
        "runtime.turn_cancel_timeout",
        "runtime.cancel_rejected",
        "runtime.display_truncated",
        "runtime.close_timeout",
        "runtime.close_failed",
        "runtime.backup_failed",
        "file.version.recorded",
        "model.output.limited",
        "provider.egress.proposed",
        "provider.egress.approved",
        "provider.egress.approval_required",
        "provider.egress.rejected",
        "tool.recovery.requested",
        "tool.recovery.exhausted",
        "context.budget.halved",
        "model.optimization.applied",
        "image.attached",
        "file.rollback.conflicted",
        "file.rollback.recovered",
        "turn.profiled",
        "session.created",
        "session.opened",
        "session.presentation.changed",
        "changes.updated",
        "background.job.created",
        "background.job.started",
        "background.job.interrupted",
        "background.job.succeeded",
        "background.job.failed",
        "background.job.stopped",
        "terminal.start",
        "terminal.input",
        "terminal.resize",
        "terminal.output",
        "terminal.stop",
        "terminal.exited",
        "turn.started",
        "turn.input.received",
        "turn.input.applied",
        "turn.completed",
        "turn.cancelled",
        "turn.failed",
        "message.created",
        "model.requested",
        "model.attempted",
        "model.stream.interrupted",
        "model.stream.recovered",
        "model.output.delta",
        "model.completed",
        "usage.updated",
        "context.compacted",
        "mode.changed",
        "autonomy.changed",
        "tool.proposed",
        "tool.approval_required",
        "tool.approved",
        "tool.started",
        "tool.settled",
        "tool.failed",
        "tool.rejected",
        "tool.cancelled",
        "tool.unknown",
        "approval.requested",
        "approval.resolved",
        "agent.run.updated",
        "agent.attention.updated",
        "task.phase.started",
        "task.phase.progress",
        "task.phase.paused",
        "task.phase.failed",
        "task.phase.completed",
        "delivery.cancelled",
        "delivery.failed",
        "delivery.blocked",
        "delivery.signal_invalid",
        "delivery.running",
        "delivery.delivered",
        "delivery.checkpointed",
        "delivery.slice.started",
        "delivery.started",
        "todo.upserted",
        "todo.deleted",
        "session.imported",
        "session.comment.added",
        "sandbox.changeset.created",
        "sandbox.change.reviewed",
        "sandbox.change.applied.imported",
        "sandbox.change.applied",
        "run_queue.failed",
        "run_queue.enqueued",
        "run_queue.completed",
        "run_queue.claimed",
        "run_queue.cancelled",
        "research.source.saved",
        "research.citation.added",
        "plan.step.upserted",
        "pipeline.step.started",
        "pipeline.step.retrying",
        "pipeline.step.completed",
        "pipeline.started",
        "pipeline.failed",
        "pipeline.created",
        "pipeline.completed",
        "memory.audit",
        "memory.deleted",
        "memory.upserted",
        "goal.updated",
        "goal.created",
        "collaboration.blocked",
        "collaboration.cancelled",
        "collaboration.failed",
        "collaboration.completed",
        "collaboration.running",
        "collaboration.member.failed",
        "collaboration.member.resumed",
        "collaboration.member.completed",
        "collaboration.member.running",
        "collaboration.member.started",
        "collaboration.started",
        "collaboration.document.updated",
    }
)


class ProtocolError(ValueError):
    """A stable protocol error that is safe to return across the process boundary."""


@dataclass(frozen=True, slots=True)
class CommandEnvelope:
    v: int
    request_id: str
    type: str
    payload: dict[str, object]
    session_id: str | None

    def to_document(self) -> dict[str, object]:
        return {
            "v": self.v,
            "kind": "command",
            "requestId": self.request_id,
            "type": self.type,
            "payload": self.payload,
            "sessionId": self.session_id,
        }


def parse_command_line(line: bytes) -> CommandEnvelope:
    if len(line) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message_too_large")
    try:
        document = json.loads(line, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ProtocolError("invalid_json") from error
    return validate_command_document(document)


def validate_command_document(document: object) -> CommandEnvelope:
    envelope = _validate_document(document, allowed_types=_COMMAND_TYPES, kind="command")
    message_type = cast(str, envelope["type"])
    payload = cast(Mapping[str, object], envelope["payload"])
    if message_type == "runtime.autonomy.set" and (
        set(payload) != {"autonomy"} or payload.get("autonomy") not in AUTONOMY_VALUES
    ):
        raise ProtocolError("invalid_payload")
    return CommandEnvelope(
        v=PROTOCOL_VERSION,
        request_id=cast(str, envelope["requestId"]),
        type=cast(str, envelope["type"]),
        payload=dict(payload),
        session_id=cast(str | None, envelope["sessionId"]),
    )


def encode_message(message: Mapping[str, object]) -> bytes:
    kind = message.get("kind")
    message_type = message.get("type")
    if kind == "command":
        _validate_document(message, allowed_types=_COMMAND_TYPES, kind="command")
    elif kind == "response":
        _validate_document(message, allowed_types=_RESPONSE_TYPES, kind="response")
        if message_type == "app.error":
            payload = cast(Mapping[str, object], message["payload"])
            code = payload.get("code")
            if (
                not isinstance(code, str)
                or re.fullmatch(r"[a-z][a-z0-9_]*", code, flags=re.ASCII) is None
            ):
                raise ProtocolError("invalid_envelope")
    elif kind == "event":
        _validate_document(message, allowed_types=_EVENT_TYPES, kind="event")
    else:
        raise ProtocolError("invalid_envelope")
    try:
        encoded = json.dumps(
            message,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ProtocolError("invalid_envelope") from error
    if len(encoded) + 1 > MAX_MESSAGE_BYTES:
        raise ProtocolError("message_too_large")
    return encoded + b"\n"


def _validate_document(
    document: object,
    *,
    allowed_types: frozenset[str],
    kind: str,
) -> Mapping[str, object]:
    if not isinstance(document, Mapping) or not all(isinstance(key, str) for key in document):
        raise ProtocolError("invalid_envelope")
    expected_keys = {"v", "kind", "type", "payload", "sessionId"}
    if kind in {"command", "response"}:
        expected_keys.add("requestId")
    if kind in {"response", "event"}:
        expected_keys.add("sequence")
    if kind == "event" and "requestId" in document:
        expected_keys.add("requestId")
    if set(document) != expected_keys:
        raise ProtocolError("invalid_envelope")

    version = document.get("v")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ProtocolError("invalid_envelope")
    if version != PROTOCOL_VERSION:
        raise ProtocolError("unsupported_protocol")

    if document.get("kind") != kind:
        raise ProtocolError("invalid_envelope")

    message_type = document.get("type")
    if not isinstance(message_type, str):
        raise ProtocolError("invalid_envelope")
    if message_type not in allowed_types:
        raise ProtocolError("unsupported_command")

    if kind in {"command", "response"} or "requestId" in document:
        request_id = document.get("requestId")
        if (
            not isinstance(request_id, str)
            or not request_id
            or len(request_id) > MAX_IDENTIFIER_CHARS
        ):
            raise ProtocolError("invalid_envelope")
    payload = document.get("payload")
    if not isinstance(payload, Mapping) or not all(isinstance(key, str) for key in payload):
        raise ProtocolError("invalid_envelope")
    if not _is_json_value(payload):
        raise ProtocolError("invalid_envelope")
    session_id = document.get("sessionId")
    if session_id is not None and (
        not isinstance(session_id, str) or not session_id or len(session_id) > MAX_IDENTIFIER_CHARS
    ):
        raise ProtocolError("invalid_envelope")
    if kind in {"response", "event"}:
        sequence = document.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
            raise ProtocolError("invalid_envelope")
    return document


def _reject_json_constant(_value: str) -> object:
    raise ValueError("non-finite JSON number")


def _is_json_value(value: object) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _is_json_value(item) for key, item in value.items())
    return False
