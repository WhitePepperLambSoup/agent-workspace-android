from __future__ import annotations

from dataclasses import dataclass

from agent_workspace.application.ports import EventStore
from agent_workspace.core.events import Event
from agent_workspace.core.models import ToolAttempt, ToolAttemptState
from agent_workspace.tools.base import ToolError
from agent_workspace.tools.filesystem import rollback_file_checkpoint

_FILE_RECOVERY_STRATEGY = "file-preimage-v1"


class WorkspaceRecoveryConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FileRecovery:
    events: tuple[Event, ...]
    conflict_path: str | None = None


def reconcile_file_attempt(store: EventStore, attempt: ToolAttempt) -> FileRecovery | None:
    if attempt.state is not ToolAttemptState.STARTED or attempt.started_event_id is None:
        return None
    started = store.get_event(attempt.started_event_id)
    if started is None or started.data.get("recovery_strategy") != _FILE_RECOVERY_STRATEGY:
        return None
    try:
        checkpoint = store.get_file_checkpoint(attempt.id)
    except OSError as exc:
        # The preimage cannot be decrypted (for example after a backup was
        # restored by a different Windows user). The database must still open:
        # mark the attempt terminal without attempting a rollback.
        return FileRecovery(
            (
                Event(
                    session_id=attempt.session_id,
                    type="tool.unknown",
                    data={
                        "attempt_id": attempt.id,
                        "tool_call_id": attempt.tool_call_id,
                        "name": attempt.tool_name,
                        "reason": (
                            "file checkpoint cannot be decrypted by the current Windows user; "
                            f"workspace write outcome is unknown: {exc}"
                        ),
                        "recovered": True,
                    },
                    causation_id=attempt.started_event_id,
                    correlation_id=started.correlation_id,
                ),
            )
        )
    if checkpoint is None:
        return FileRecovery(
            (
                Event(
                    session_id=attempt.session_id,
                    type="tool.failed",
                    data={
                        "attempt_id": attempt.id,
                        "tool_call_id": attempt.tool_call_id,
                        "name": attempt.tool_name,
                        "error": "interrupted before the durable file checkpoint was prepared",
                        "recovered": True,
                    },
                    causation_id=attempt.started_event_id,
                    correlation_id=started.correlation_id,
                ),
            )
        )

    try:
        outcome = rollback_file_checkpoint(checkpoint)
    except (OSError, ToolError, ValueError) as exc:
        outcome = "conflict"
        reason = str(exc)
    else:
        reason = "workspace file differs from both checkpoint images"
    recovery_data = {
        "attempt_id": attempt.id,
        "tool_call_id": attempt.tool_call_id,
        "name": attempt.tool_name,
        "path": checkpoint.relative_path,
        "preimage_sha256": checkpoint.preimage_sha256,
        "postimage_sha256": checkpoint.postimage_sha256,
    }
    if outcome == "conflict":
        return FileRecovery(
            (
                Event(
                    session_id=attempt.session_id,
                    type="file.rollback.conflicted",
                    data={**recovery_data, "reason": reason},
                    causation_id=attempt.started_event_id,
                    correlation_id=started.correlation_id,
                ),
            ),
            conflict_path=checkpoint.relative_path,
        )
    return FileRecovery(
        (
            Event(
                session_id=attempt.session_id,
                type="file.rollback.recovered",
                data={**recovery_data, "outcome": outcome},
                causation_id=attempt.started_event_id,
                correlation_id=started.correlation_id,
            ),
            Event(
                session_id=attempt.session_id,
                type="tool.failed",
                data={
                    "attempt_id": attempt.id,
                    "tool_call_id": attempt.tool_call_id,
                    "name": attempt.tool_name,
                    "error": "workspace file write was rolled back after interruption",
                    "recovered": True,
                },
                causation_id=attempt.started_event_id,
                correlation_id=started.correlation_id,
            ),
        )
    )


def recover_workspace_file_writes(store: EventStore, workspace: str) -> None:
    for attempt in store.list_incomplete_tool_attempts_for_workspace(workspace):
        recovery = reconcile_file_attempt(store, attempt)
        if recovery is None:
            continue
        store.append_many(recovery.events)
        if recovery.conflict_path is not None:
            raise WorkspaceRecoveryConflictError(
                f"workspace recovery conflict requires manual resolution: {recovery.conflict_path}"
            )
