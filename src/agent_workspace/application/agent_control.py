"""Durable control-plane state for desktop agent runs.

The conversational event stream remains append-only. This module stores the
operator-facing lifecycle that spans several turns or runtime hosts and uses
short SQLite transactions so renderer requests never hold the gateway lock
while waiting on an agent.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from agent_workspace.core.models import (
    AgentRun,
    AgentRunState,
    AttentionItem,
    AttentionKind,
    AttentionState,
    PlanStep,
    PlanStepState,
    RunIsolation,
)
from agent_workspace.storage.sqlite import SQLiteEventStore

_TERMINAL_RUN_STATES = frozenset(
    {AgentRunState.SUCCEEDED, AgentRunState.FAILED, AgentRunState.CANCELLED}
)
_RUNNING_RECOVERY_STATES = (AgentRunState.STARTING.value, AgentRunState.RUNNING.value)
_MAX_TEXT = 100_000
_UNSET = object()


class AgentControlError(ValueError):
    """Stable validation error for control-plane operations."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _text(value: str, name: str, *, allow_empty: bool = False, limit: int = _MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise AgentControlError(f"invalid_{name}")
    normalized = value.strip()
    if (not allow_empty and not normalized) or len(normalized) > limit:
        raise AgentControlError(f"invalid_{name}")
    return normalized


def _json_mapping(value: Mapping[str, Any] | None) -> str:
    return json.dumps(dict(value or {}), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _json_strings(value: Sequence[str]) -> str:
    items = tuple(_text(item, "list_item", limit=4_000) for item in value)
    if len(items) > 256:
        raise AgentControlError("too_many_items")
    return json.dumps(items, ensure_ascii=False, separators=(",", ":"))


class AgentControlService:
    def __init__(self, database: str | Path) -> None:
        self.database = Path(database).expanduser().resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        # Reuse the event store's verified migration and recovery path.
        with SQLiteEventStore(self.database):
            pass

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.database), timeout=5, isolation_level="DEFERRED", check_same_thread=False
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create_run(
        self,
        *,
        workspace: str | Path,
        session_id: str,
        goal: str,
        title: str | None = None,
        isolation: RunIsolation = RunIsolation.WORKTREE,
        parent_run_id: str | None = None,
        run_id: str | None = None,
        checkout_path: str | None = None,
        branch: str | None = None,
        base_sha: str | None = None,
    ) -> AgentRun:
        root = str(Path(workspace).expanduser().resolve())
        normalized_goal = _text(goal, "goal")
        normalized_title = _text(title or normalized_goal[:120], "title", limit=200)
        identifier = run_id or str(uuid4())
        timestamp = _now()
        with self._connection() as connection:
            session = connection.execute(
                "SELECT workspace FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if session is None or str(Path(cast(str, session["workspace"])).resolve()) != root:
                raise AgentControlError("invalid_session")
            if parent_run_id is not None:
                parent = connection.execute(
                    "SELECT workspace FROM agent_runs WHERE id = ?", (parent_run_id,)
                ).fetchone()
                if parent is None or cast(str, parent["workspace"]) != root:
                    raise AgentControlError("invalid_parent_run")
            connection.execute(
                """
                INSERT INTO agent_runs (
                    id, workspace, session_id, parent_run_id, title, goal, state,
                    resume_state, isolation, checkout_path, branch, base_sha,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'draft', 'draft', ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    root,
                    session_id,
                    parent_run_id,
                    normalized_title,
                    normalized_goal,
                    isolation.value,
                    checkout_path,
                    branch,
                    base_sha,
                    timestamp,
                    timestamp,
                ),
            )
        run = self.get_run(identifier)
        assert run is not None
        return run

    def get_run(self, run_id: str) -> AgentRun | None:
        with self._connection() as connection:
            row = connection.execute(
                self._run_select() + " WHERE r.id = ? GROUP BY r.id", (run_id,)
            ).fetchone()
        return self._run_from_row(row) if row is not None else None

    def save_checkpoint(
        self,
        run_id: str,
        *,
        revision: int,
        state: Mapping[str, Any],
        reason: str = "",
        checkpoint_id: str | None = None,
    ) -> dict[str, Any]:
        """Persist an immutable run checkpoint and make repeated writes idempotent."""

        if type(revision) is not int or revision < 1:
            raise AgentControlError("invalid_checkpoint_revision")
        if not isinstance(state, Mapping):
            raise AgentControlError("invalid_checkpoint_state")
        normalized_reason = _text(reason, "checkpoint_reason", allow_empty=True, limit=2_000)
        state_json = json.dumps(
            dict(state), ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        if len(state_json.encode("utf-8")) > 1_048_576:
            raise AgentControlError("checkpoint_too_large")
        identifier = checkpoint_id or str(uuid4())
        _text(identifier, "checkpoint_id", limit=128)
        timestamp = _now()
        with self._connection() as connection:
            run = connection.execute("SELECT 1 FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
            if run is None:
                raise AgentControlError("unknown_run")
            existing = connection.execute(
                "SELECT * FROM run_checkpoints WHERE run_id = ? AND revision = ?",
                (run_id, revision),
            ).fetchone()
            if existing is not None:
                if (
                    cast(str, existing["state_json"]) != state_json
                    or cast(str, existing["reason"]) != normalized_reason
                ):
                    raise AgentControlError("checkpoint_conflict")
                return self._checkpoint_from_row(existing)
            try:
                connection.execute(
                    """
                    INSERT INTO run_checkpoints (
                        id, run_id, revision, state_json, reason, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (identifier, run_id, revision, state_json, normalized_reason, timestamp),
                )
            except sqlite3.IntegrityError as exc:
                raise AgentControlError("checkpoint_conflict") from exc
            row = connection.execute(
                "SELECT * FROM run_checkpoints WHERE id = ?", (identifier,)
            ).fetchone()
        assert row is not None
        return self._checkpoint_from_row(row)

    def list_checkpoints(self, run_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        if type(limit) is not int or not 1 <= limit <= 1_000:
            raise AgentControlError("invalid_limit")
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM run_checkpoints
                WHERE run_id = ?
                ORDER BY revision DESC, id DESC
                LIMIT ?
                """,
                (run_id, limit),
            ).fetchall()
        return [self._checkpoint_from_row(row) for row in rows]

    def record_operation(
        self,
        run_id: str,
        *,
        idempotency_key: str,
        phase_id: str | None,
        tool_name: str | None,
        request: Mapping[str, Any],
        state: str,
        result: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create or update one idempotent external operation record."""

        key = _text(idempotency_key, "idempotency_key", limit=256)
        if state not in {"started", "completed", "failed"}:
            raise AgentControlError("invalid_operation_state")
        if not isinstance(request, Mapping) or (
            result is not None and not isinstance(result, Mapping)
        ):
            raise AgentControlError("invalid_operation_payload")
        request_json = json.dumps(
            dict(request), ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        result_json = json.dumps(
            dict(result or {}), ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        if (
            len(request_json.encode("utf-8")) > 1_048_576
            or len(result_json.encode("utf-8")) > 1_048_576
        ):
            raise AgentControlError("operation_payload_too_large")
        normalized_phase = (
            _text(phase_id, "phase_id", allow_empty=True, limit=256) if phase_id else None
        )
        normalized_tool = (
            _text(tool_name, "tool_name", allow_empty=True, limit=256) if tool_name else None
        )
        timestamp = _now()
        with self._connection() as connection:
            if (
                connection.execute("SELECT 1 FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
                is None
            ):
                raise AgentControlError("unknown_run")
            existing = connection.execute(
                "SELECT * FROM operation_ledger WHERE idempotency_key = ?", (key,)
            ).fetchone()
            if existing is not None:
                if (
                    cast(str, existing["run_id"]) != run_id
                    or existing["phase_id"] != normalized_phase
                    or existing["tool_name"] != normalized_tool
                    or cast(str, existing["request_json"]) != request_json
                ):
                    raise AgentControlError("operation_conflict")
                if (
                    cast(str, existing["state"]) == state
                    and cast(str, existing["result_json"]) == result_json
                ):
                    return self._operation_from_row(existing)
                connection.execute(
                    """
                    UPDATE operation_ledger
                    SET state = ?, result_json = ?, updated_at = ?
                    WHERE idempotency_key = ?
                    """,
                    (state, result_json, timestamp, key),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO operation_ledger (
                        idempotency_key, run_id, phase_id, tool_name,
                        request_json, state, result_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key,
                        run_id,
                        normalized_phase,
                        normalized_tool,
                        request_json,
                        state,
                        result_json,
                        timestamp,
                        timestamp,
                    ),
                )
            row = connection.execute(
                "SELECT * FROM operation_ledger WHERE idempotency_key = ?", (key,)
            ).fetchone()
        assert row is not None
        return self._operation_from_row(row)

    def get_operation(self, idempotency_key: str) -> dict[str, Any] | None:
        key = _text(idempotency_key, "idempotency_key", limit=256)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM operation_ledger WHERE idempotency_key = ?", (key,)
            ).fetchone()
        return self._operation_from_row(row) if row is not None else None

    def list_runs(
        self,
        workspace: str | Path,
        *,
        states: Sequence[AgentRunState] | None = None,
        limit: int = 200,
    ) -> list[AgentRun]:
        if not 1 <= limit <= 1_000:
            raise AgentControlError("invalid_limit")
        root = str(Path(workspace).expanduser().resolve())
        arguments: list[object] = [root]
        where = " WHERE r.workspace = ?"
        if states:
            values = tuple(state.value for state in states)
            where += f" AND r.state IN ({','.join('?' for _ in values)})"
            arguments.extend(values)
        arguments.append(limit)
        with self._connection() as connection:
            rows = connection.execute(
                self._run_select()
                + where
                + " GROUP BY r.id ORDER BY r.updated_at DESC, r.id LIMIT ?",
                arguments,
            ).fetchall()
        return [self._run_from_row(row) for row in rows]

    def update_run(
        self,
        run_id: str,
        *,
        state: AgentRunState | None = None,
        title: str | None = None,
        goal: str | None = None,
        active_turn_id: str | object | None = _UNSET,
        active_step_id: str | object | None = _UNSET,
        blocking_reason: str | object | None = _UNSET,
        pause_requested: bool | None = None,
        checkout_path: str | None = None,
        branch: str | None = None,
        base_sha: str | None = None,
    ) -> AgentRun:
        timestamp = _now()
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise AgentControlError("unknown_run")
            current = AgentRunState(cast(str, row["state"]))
            if current in _TERMINAL_RUN_STATES and state is not None and state is not current:
                raise AgentControlError("terminal_run")
            target = state or current
            if target is AgentRunState.SUCCEEDED:
                incomplete = connection.execute(
                    """
                    SELECT 1 FROM plan_steps
                    WHERE run_id = ? AND state NOT IN ('completed', 'skipped') LIMIT 1
                    """,
                    (run_id,),
                ).fetchone()
                if incomplete is not None:
                    raise AgentControlError("plan_incomplete")
            if pause_requested is not None and type(pause_requested) is not bool:
                raise AgentControlError("invalid_pause_requested")
            values = {
                "state": target.value,
                "title": _text(title, "title", limit=200) if title is not None else row["title"],
                "goal": _text(goal, "goal") if goal is not None else row["goal"],
                # Optional lifecycle fields use an explicit sentinel so a
                # partial update preserves the current value while callers can
                # still clear a field intentionally by passing None.
                "active_turn_id": row["active_turn_id"]
                if active_turn_id is _UNSET
                else active_turn_id,
                "active_step_id": row["active_step_id"]
                if active_step_id is _UNSET
                else active_step_id,
                "blocking_reason": row["blocking_reason"]
                if blocking_reason is _UNSET
                else blocking_reason,
                "pause_requested": row["pause_requested"]
                if pause_requested is None
                else int(pause_requested),
                "checkout_path": checkout_path
                if checkout_path is not None
                else row["checkout_path"],
                "branch": branch if branch is not None else row["branch"],
                "base_sha": base_sha if base_sha is not None else row["base_sha"],
            }
            if target is not AgentRunState.NEEDS_ATTENTION:
                resume_state = target.value
            else:
                resume_state = cast(str, row["resume_state"])
            connection.execute(
                """
                UPDATE agent_runs SET state = ?, resume_state = ?, title = ?, goal = ?,
                    active_turn_id = ?, active_step_id = ?, blocking_reason = ?,
                    pause_requested = ?, checkout_path = ?, branch = ?, base_sha = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    values["state"],
                    resume_state,
                    values["title"],
                    values["goal"],
                    values["active_turn_id"],
                    values["active_step_id"],
                    values["blocking_reason"],
                    values["pause_requested"],
                    values["checkout_path"],
                    values["branch"],
                    values["base_sha"],
                    timestamp,
                    run_id,
                ),
            )
        updated = self.get_run(run_id)
        assert updated is not None
        return updated

    def apply_recovery_action(
        self,
        run_id: str,
        *,
        action: str,
        idempotency_key: str,
    ) -> AgentRun:
        """Apply one durable recovery action exactly once per caller key."""

        normalized_action = _text(action, "recovery_action", limit=32).casefold()
        if normalized_action not in {"resume", "retry", "cancel"}:
            raise AgentControlError("invalid_recovery_action")
        caller_key = _text(idempotency_key, "idempotency_key", limit=200)
        ledger_key = f"run-action:{caller_key}"
        request = {"action": normalized_action, "run_id": run_id}
        existing = self.get_operation(ledger_key)
        if existing is not None:
            if existing["request"] != request:
                raise AgentControlError("operation_conflict")
            if existing["state"] == "completed":
                updated = self.get_run(run_id)
                if updated is None:
                    raise AgentControlError("unknown_run")
                return updated
        self.record_operation(
            run_id,
            idempotency_key=ledger_key,
            phase_id=None,
            tool_name="run.recovery",
            request=request,
            state="started",
        )
        if normalized_action == "resume":
            updated = self.update_run(
                run_id,
                state=AgentRunState.STARTING,
                active_turn_id=None,
                active_step_id=None,
                blocking_reason=None,
            )
        elif normalized_action == "retry":
            updated = self.update_run(
                run_id,
                state=AgentRunState.QUEUED,
                active_turn_id=None,
                active_step_id=None,
                blocking_reason=None,
            )
        else:
            updated = self.finish_run(run_id, AgentRunState.CANCELLED, reason="cancelled_by_user")
        self.record_operation(
            run_id,
            idempotency_key=ledger_key,
            phase_id=None,
            tool_name="run.recovery",
            request=request,
            state="completed",
            result={"run_id": updated.id, "state": updated.state.value},
        )
        return updated

    def request_pause(self, run_id: str) -> AgentRun:
        """Persist a cooperative pause request without interrupting the active turn."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT state, blocking_reason FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise AgentControlError("unknown_run")
            current = AgentRunState(cast(str, row["state"]))
            if current in _TERMINAL_RUN_STATES:
                raise AgentControlError("terminal_run")
            if (
                current is AgentRunState.NEEDS_ATTENTION
                and row["blocking_reason"] == "paused_by_user"
            ):
                return self.get_run(run_id)  # type: ignore[return-value]
            # An approval pauses the visible run while the host is still
            # waiting inside the active turn. Preserve a user pause request
            # across that approval instead of forcing the user to choose
            # between resolving the approval and pausing the run.
            approval_pending = (
                current is AgentRunState.NEEDS_ATTENTION
                and isinstance(row["blocking_reason"], str)
                and row["blocking_reason"].startswith("approval:")
            )
            if (
                current not in {AgentRunState.STARTING, AgentRunState.RUNNING}
                and not approval_pending
            ):
                raise AgentControlError("run_not_active")
            connection.execute(
                "UPDATE agent_runs SET pause_requested = 1, updated_at = ? WHERE id = ?",
                (_now(), run_id),
            )
        updated = self.get_run(run_id)
        assert updated is not None
        return updated

    def apply_pause(self, run_id: str) -> AgentRun:
        """Apply a previously requested pause at a completed-turn boundary."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT state, resume_state, blocking_reason, pause_requested "
                "FROM agent_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise AgentControlError("unknown_run")
            current = AgentRunState(cast(str, row["state"]))
            if current in _TERMINAL_RUN_STATES:
                raise AgentControlError("terminal_run")
            if (
                current is AgentRunState.NEEDS_ATTENTION
                and row["blocking_reason"] == "paused_by_user"
            ):
                return self.get_run(run_id)  # type: ignore[return-value]
            if current not in {AgentRunState.STARTING, AgentRunState.RUNNING}:
                raise AgentControlError("run_not_active")
            if not bool(row["pause_requested"]):
                updated = self.get_run(run_id)
                assert updated is not None
                return updated
            connection.execute(
                """
                UPDATE agent_runs
                SET state = 'needs_attention', resume_state = ?, pause_requested = 0,
                    active_turn_id = NULL, blocking_reason = 'paused_by_user', updated_at = ?
                WHERE id = ?
                """,
                (current.value, _now(), run_id),
            )
        updated = self.get_run(run_id)
        assert updated is not None
        return updated

    def bind_execution_context(
        self,
        run_id: str,
        *,
        session_id: str,
        checkout_path: str,
        branch: str | None,
        base_sha: str | None,
    ) -> AgentRun:
        timestamp = _now()
        with self._connection() as connection:
            run = connection.execute(
                "SELECT workspace, state FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            session = connection.execute(
                "SELECT workspace FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if run is None:
                raise AgentControlError("unknown_run")
            if session is None or str(Path(cast(str, session["workspace"])).resolve()) != str(
                Path(checkout_path).resolve()
            ):
                raise AgentControlError("invalid_session")
            if AgentRunState(cast(str, run["state"])) in _TERMINAL_RUN_STATES:
                raise AgentControlError("terminal_run")
            connection.execute(
                """
                UPDATE agent_runs
                SET session_id = ?, checkout_path = ?, branch = ?, base_sha = ?,
                    state = 'starting', resume_state = 'starting', blocking_reason = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (session_id, checkout_path, branch, base_sha, timestamp, run_id),
            )
        updated = self.get_run(run_id)
        assert updated is not None
        return updated

    def record_checkout(
        self,
        run_id: str,
        *,
        checkout_path: str,
        branch: str | None,
        base_sha: str | None,
    ) -> AgentRun:
        """Persist a newly created checkout before any later startup step can fail."""
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE agent_runs
                SET checkout_path = ?, branch = ?, base_sha = ?, updated_at = ?
                WHERE id = ? AND state NOT IN ('succeeded', 'failed', 'cancelled')
                """,
                (str(Path(checkout_path).resolve()), branch, base_sha, _now(), run_id),
            )
            if cursor.rowcount != 1:
                raise AgentControlError("unknown_or_terminal_run")
        updated = self.get_run(run_id)
        assert updated is not None
        return updated

    def finish_run(
        self, run_id: str, state: AgentRunState, *, reason: str | None = None
    ) -> AgentRun:
        if state not in _TERMINAL_RUN_STATES:
            raise AgentControlError("invalid_terminal_state")
        timestamp = _now()
        with self._connection() as connection:
            row = connection.execute(
                "SELECT state FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise AgentControlError("unknown_run")
            current = AgentRunState(cast(str, row["state"]))
            if current in _TERMINAL_RUN_STATES and current is not state:
                raise AgentControlError("terminal_run")
            if state is AgentRunState.SUCCEEDED:
                incomplete = connection.execute(
                    "SELECT 1 FROM plan_steps WHERE run_id = ? "
                    "AND state NOT IN ('completed', 'skipped') LIMIT 1",
                    (run_id,),
                ).fetchone()
                if incomplete is not None:
                    state = AgentRunState.NEEDS_ATTENTION
                    reason = "plan_verification_required"
                connection.execute(
                    """
                    UPDATE plan_steps SET state = 'blocked', updated_at = ?
                    WHERE run_id = ? AND state = 'running'
                    """,
                    (timestamp, run_id),
                )
            elif state is AgentRunState.FAILED:
                connection.execute(
                    """
                    UPDATE plan_steps SET state = 'failed', updated_at = ?
                    WHERE run_id = ? AND state = 'running'
                    """,
                    (timestamp, run_id),
                )
            connection.execute(
                """
                UPDATE agent_runs SET state = ?, resume_state = ?, pause_requested = 0,
                    active_turn_id = NULL, active_step_id = NULL, blocking_reason = ?,
                    updated_at = ? WHERE id = ?
                """,
                (
                    state.value,
                    "draft" if state is AgentRunState.NEEDS_ATTENTION else state.value,
                    reason,
                    timestamp,
                    run_id,
                ),
            )
        updated = self.get_run(run_id)
        assert updated is not None
        return updated

    def clear_checkout(self, run_id: str) -> AgentRun:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE agent_runs SET checkout_path = NULL, updated_at = ?
                WHERE id = ? AND state IN ('succeeded', 'failed', 'cancelled')
                """,
                (_now(), run_id),
            )
            if cursor.rowcount != 1:
                raise AgentControlError("run_not_terminal")
        updated = self.get_run(run_id)
        assert updated is not None
        return updated

    def create_plan_step(
        self,
        run_id: str,
        *,
        title: str,
        detail: str = "",
        acceptance: str = "",
        position: int = 0,
        dependencies: Sequence[str] = (),
        step_id: str | None = None,
    ) -> PlanStep:
        if not isinstance(position, int) or position < 0 or position > 1_000_000:
            raise AgentControlError("invalid_position")
        identifier = step_id or str(uuid4())
        timestamp = _now()
        with self._connection() as connection:
            if (
                connection.execute("SELECT 1 FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
                is None
            ):
                raise AgentControlError("unknown_run")
            self._validate_dependencies(connection, run_id, identifier, dependencies)
            connection.execute(
                """
                INSERT INTO plan_steps (
                    id, run_id, title, detail, acceptance, state, position,
                    dependencies_json, evidence_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, '[]', ?, ?)
                """,
                (
                    identifier,
                    run_id,
                    _text(title, "title", limit=500),
                    _text(detail, "detail", allow_empty=True),
                    _text(acceptance, "acceptance", allow_empty=True),
                    position,
                    _json_strings(dependencies),
                    timestamp,
                    timestamp,
                ),
            )
        step = self.get_plan_step(identifier)
        assert step is not None
        return step

    def append_plan_step_evidence(self, step_id: str, evidence: Sequence[str]) -> PlanStep:
        incoming = tuple(_text(item, "evidence", limit=4_000) for item in evidence)
        if len(incoming) > 256:
            raise AgentControlError("too_many_items")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT evidence_json FROM plan_steps WHERE id = ?", (step_id,)
            ).fetchone()
            if row is None:
                raise AgentControlError("unknown_step")
            existing = tuple(cast(list[str], json.loads(cast(str, row["evidence_json"]))))
            merged = list(existing)
            for item in incoming:
                if item not in merged:
                    merged.append(item)
            if len(merged) > 256:
                merged = merged[-256:]
            connection.execute(
                "UPDATE plan_steps SET evidence_json = ?, updated_at = ? WHERE id = ?",
                (_json_strings(merged), _now(), step_id),
            )
        step = self.get_plan_step(step_id)
        assert step is not None
        return step

    def get_plan_step(self, step_id: str) -> PlanStep | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM plan_steps WHERE id = ?", (step_id,)).fetchone()
        return self._step_from_row(row) if row is not None else None

    def list_plan_steps(self, run_id: str) -> list[PlanStep]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM plan_steps WHERE run_id = ? ORDER BY position, id", (run_id,)
            ).fetchall()
        return [self._step_from_row(row) for row in rows]

    def select_ready_step(self, run_id: str) -> PlanStep | None:
        steps = self.list_plan_steps(run_id)
        finished = {
            step.id
            for step in steps
            if step.state in {PlanStepState.COMPLETED, PlanStepState.SKIPPED}
        }
        for step in steps:
            if step.state in {
                PlanStepState.PENDING,
                PlanStepState.RUNNING,
                PlanStepState.BLOCKED,
                PlanStepState.FAILED,
            } and all(dep in finished for dep in step.dependencies):
                return self.update_plan_step(step.id, state=PlanStepState.RUNNING)
        return None

    def update_plan_step(
        self,
        step_id: str,
        *,
        title: str | None = None,
        detail: str | None = None,
        acceptance: str | None = None,
        state: PlanStepState | None = None,
        position: int | None = None,
        dependencies: Sequence[str] | None = None,
        evidence: Sequence[str] | None = None,
    ) -> PlanStep:
        if position is not None and (
            not isinstance(position, int) or not 0 <= position <= 1_000_000
        ):
            raise AgentControlError("invalid_position")
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM plan_steps WHERE id = ?", (step_id,)).fetchone()
            if row is None:
                raise AgentControlError("unknown_step")
            run_id = cast(str, row["run_id"])
            next_dependencies = (
                tuple(dependencies)
                if dependencies is not None
                else tuple(cast(list[str], json.loads(cast(str, row["dependencies_json"]))))
            )
            self._validate_dependencies(connection, run_id, step_id, next_dependencies)
            next_state = state or PlanStepState(cast(str, row["state"]))
            if (
                next_state is PlanStepState.COMPLETED
                and row["state"] != "completed"
                and evidence is None
            ):
                previous_evidence = cast(list[str], json.loads(row["evidence_json"]))
                evidence = [*previous_evidence[-255:], "User confirmed acceptance criteria"]
            if next_state in {PlanStepState.RUNNING, PlanStepState.COMPLETED} and next_dependencies:
                placeholders = ",".join("?" for _ in next_dependencies)
                incomplete = connection.execute(
                    f"SELECT 1 FROM plan_steps WHERE id IN ({placeholders}) "
                    "AND state NOT IN ('completed', 'skipped') LIMIT 1",
                    next_dependencies,
                ).fetchone()
                if incomplete is not None:
                    raise AgentControlError("dependencies_not_completed")
            connection.execute(
                """
                UPDATE plan_steps SET title = ?, detail = ?, acceptance = ?, state = ?,
                    position = ?, dependencies_json = ?, evidence_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    _text(title, "title", limit=500) if title is not None else row["title"],
                    _text(detail, "detail", allow_empty=True)
                    if detail is not None
                    else row["detail"],
                    _text(acceptance, "acceptance", allow_empty=True)
                    if acceptance is not None
                    else row["acceptance"],
                    next_state.value,
                    position if position is not None else row["position"],
                    _json_strings(next_dependencies),
                    _json_strings(evidence) if evidence is not None else row["evidence_json"],
                    _now(),
                    step_id,
                ),
            )
            if next_state is PlanStepState.RUNNING:
                connection.execute(
                    "UPDATE plan_steps SET state = 'pending', updated_at = ? "
                    "WHERE run_id = ? AND id != ? AND state = 'running'",
                    (_now(), run_id, step_id),
                )
                connection.execute(
                    "UPDATE agent_runs SET active_step_id = ?, updated_at = ? WHERE id = ?",
                    (step_id, _now(), run_id),
                )
            elif row["state"] == PlanStepState.RUNNING.value:
                connection.execute(
                    "UPDATE agent_runs SET active_step_id = NULL, updated_at = ? "
                    "WHERE id = ? AND active_step_id = ?",
                    (_now(), run_id, step_id),
                )
        step = self.get_plan_step(step_id)
        assert step is not None
        return step

    def delete_plan_step(self, step_id: str) -> bool:
        with self._connection() as connection:
            reference = connection.execute(
                "SELECT 1 FROM plan_steps WHERE dependencies_json LIKE ? LIMIT 1",
                (f'%"{step_id}"%',),
            ).fetchone()
            if reference is not None:
                raise AgentControlError("step_has_dependants")
            cursor = connection.execute("DELETE FROM plan_steps WHERE id = ?", (step_id,))
        return cursor.rowcount == 1

    def open_attention(
        self,
        *,
        kind: AttentionKind,
        severity: str,
        title: str,
        detail: str = "",
        run_id: str | None = None,
        session_id: str | None = None,
        source_key: str | None = None,
        action: Mapping[str, Any] | None = None,
    ) -> AttentionItem:
        if severity not in {"info", "warning", "critical"}:
            raise AgentControlError("invalid_severity")
        timestamp = _now()
        with self._connection() as connection:
            if source_key is not None:
                existing = connection.execute(
                    "SELECT * FROM attention_items WHERE source_key = ? AND state = 'open'",
                    (source_key,),
                ).fetchone()
                if existing is not None:
                    return self._attention_from_row(existing)
            if run_id is not None:
                run = connection.execute(
                    "SELECT state, resume_state, session_id FROM agent_runs WHERE id = ?", (run_id,)
                ).fetchone()
                if run is None:
                    raise AgentControlError("unknown_run")
                if session_id is None:
                    session_id = cast(str, run["session_id"])
                current = AgentRunState(cast(str, run["state"]))
                if current not in _TERMINAL_RUN_STATES:
                    resume = (
                        current.value
                        if current is not AgentRunState.NEEDS_ATTENTION
                        else run["resume_state"]
                    )
                    connection.execute(
                        """
                        UPDATE agent_runs SET state = 'needs_attention', resume_state = ?,
                            blocking_reason = ?, updated_at = ? WHERE id = ?
                        """,
                        (resume, source_key or kind.value, timestamp, run_id),
                    )
            identifier = str(uuid4())
            connection.execute(
                """
                INSERT INTO attention_items (
                    id, run_id, session_id, kind, severity, title, detail, state,
                    source_key, action_json, resolution_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, '{}', ?, ?)
                """,
                (
                    identifier,
                    run_id,
                    session_id,
                    kind.value,
                    severity,
                    _text(title, "title", limit=500),
                    _text(detail, "detail", allow_empty=True),
                    source_key,
                    _json_mapping(action),
                    timestamp,
                    timestamp,
                ),
            )
            row = connection.execute(
                "SELECT * FROM attention_items WHERE id = ?", (identifier,)
            ).fetchone()
            assert row is not None
            return self._attention_from_row(row)

    def resolve_attention(
        self,
        attention_id: str,
        *,
        resolution: Mapping[str, Any] | None = None,
        dismissed: bool = False,
    ) -> AttentionItem:
        timestamp = _now()
        target = AttentionState.DISMISSED if dismissed else AttentionState.RESOLVED
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM attention_items WHERE id = ?", (attention_id,)
            ).fetchone()
            if row is None:
                raise AgentControlError("unknown_attention")
            if row["state"] != AttentionState.OPEN.value:
                raise AgentControlError("attention_already_closed")
            connection.execute(
                """
                UPDATE attention_items
                SET state = ?, resolution_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (target.value, _json_mapping(resolution), timestamp, attention_id),
            )
            run_id = cast(str | None, row["run_id"])
            if run_id is not None:
                remaining = connection.execute(
                    "SELECT 1 FROM attention_items WHERE run_id = ? AND state = 'open' LIMIT 1",
                    (run_id,),
                ).fetchone()
                if remaining is None:
                    run = connection.execute(
                        "SELECT state, resume_state FROM agent_runs WHERE id = ?", (run_id,)
                    ).fetchone()
                    if run is not None and run["state"] == AgentRunState.NEEDS_ATTENTION.value:
                        connection.execute(
                            """
                            UPDATE agent_runs
                            SET state = resume_state, blocking_reason = NULL, updated_at = ?
                            WHERE id = ?
                            """,
                            (timestamp, run_id),
                        )
            updated = connection.execute(
                "SELECT * FROM attention_items WHERE id = ?", (attention_id,)
            ).fetchone()
            assert updated is not None
            return self._attention_from_row(updated)

    def get_attention(self, attention_id: str) -> AttentionItem | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM attention_items WHERE id = ?", (attention_id,)
            ).fetchone()
        return self._attention_from_row(row) if row is not None else None

    def resolve_attention_by_source(
        self, source_key: str, *, resolution: Mapping[str, Any] | None = None
    ) -> AttentionItem | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT id FROM attention_items
                WHERE source_key = ? AND state = 'open'
                ORDER BY created_at LIMIT 1
                """,
                (source_key,),
            ).fetchone()
        if row is None:
            return None
        return self.resolve_attention(cast(str, row["id"]), resolution=resolution)

    def list_attention(
        self,
        *,
        run_id: str | None = None,
        workspace: str | Path | None = None,
        state: AttentionState | None = None,
        limit: int = 500,
    ) -> list[AttentionItem]:
        conditions: list[str] = []
        arguments: list[object] = []
        joins = ""
        if run_id is not None:
            conditions.append("a.run_id = ?")
            arguments.append(run_id)
        if workspace is not None:
            joins = (
                " LEFT JOIN agent_runs r ON r.id = a.run_id"
                " LEFT JOIN sessions s ON s.id = a.session_id"
            )
            conditions.append("COALESCE(r.workspace, s.workspace) = ?")
            arguments.append(str(Path(workspace).expanduser().resolve()))
        if state is not None:
            conditions.append("a.state = ?")
            arguments.append(state.value)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        arguments.append(limit)
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT a.* FROM attention_items a" + joins + where + " ORDER BY CASE a.severity"
                " WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,"
                " a.updated_at DESC, a.id LIMIT ?",
                arguments,
            ).fetchall()
        return [self._attention_from_row(row) for row in rows]

    def recover_interrupted_runs(self, workspace: str | Path) -> int:
        root = str(Path(workspace).expanduser().resolve())
        timestamp = _now()
        recovered: list[tuple[str, str]] = []
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, session_id, state FROM agent_runs
                WHERE workspace = ? AND state IN (?, ?)
                """,
                (root, *_RUNNING_RECOVERY_STATES),
            ).fetchall()
            for row in rows:
                run_id = cast(str, row["id"])
                connection.execute(
                    """
                    UPDATE agent_runs
                    SET state = 'needs_attention', resume_state = 'queued',
                        blocking_reason = 'runtime_interrupted', active_turn_id = NULL,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (timestamp, run_id),
                )
                recovered.append((run_id, cast(str, row["session_id"])))
            for run_id, session_id in recovered:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO attention_items (
                        id, run_id, session_id, kind, severity, title, detail, state,
                        source_key, action_json, resolution_json, created_at, updated_at
                    ) VALUES (?, ?, ?, 'failure', 'warning', ?, ?, 'open', ?, ?, '{}', ?, ?)
                    """,
                    (
                        str(uuid4()),
                        run_id,
                        session_id,
                        "Agent run was interrupted",
                        "The application stopped while this run was active. Resume or cancel it.",
                        f"runtime-interrupted:{run_id}",
                        '{"kind":"resume_run"}',
                        timestamp,
                        timestamp,
                    ),
                )
        return len(recovered)

    @staticmethod
    def _validate_dependencies(
        connection: sqlite3.Connection,
        run_id: str,
        step_id: str,
        dependencies: Sequence[str],
    ) -> None:
        if step_id in dependencies or len(set(dependencies)) != len(dependencies):
            raise AgentControlError("invalid_dependencies")
        if not dependencies:
            return
        placeholders = ",".join("?" for _ in dependencies)
        count = connection.execute(
            f"SELECT COUNT(*) FROM plan_steps WHERE run_id = ? AND id IN ({placeholders})",
            (run_id, *dependencies),
        ).fetchone()[0]
        if count != len(dependencies):
            raise AgentControlError("invalid_dependencies")

    @staticmethod
    def _run_select() -> str:
        return """
            SELECT r.*,
                COALESCE(SUM(CASE WHEN p.state IN ('completed', 'skipped') THEN 1 ELSE 0 END), 0)
                    AS completed_steps,
                COUNT(p.id) AS total_steps
            FROM agent_runs r LEFT JOIN plan_steps p ON p.run_id = r.id
        """

    @staticmethod
    def _run_from_row(row: sqlite3.Row) -> AgentRun:
        completed = cast(int, row["completed_steps"])
        total = cast(int, row["total_steps"])
        return AgentRun(
            id=cast(str, row["id"]),
            workspace=cast(str, row["workspace"]),
            session_id=cast(str, row["session_id"]),
            title=cast(str, row["title"]),
            goal=cast(str, row["goal"]),
            state=AgentRunState(cast(str, row["state"])),
            isolation=RunIsolation(cast(str, row["isolation"])),
            parent_run_id=cast(str | None, row["parent_run_id"]),
            checkout_path=cast(str | None, row["checkout_path"]),
            branch=cast(str | None, row["branch"]),
            base_sha=cast(str | None, row["base_sha"]),
            active_turn_id=cast(str | None, row["active_turn_id"]),
            active_step_id=cast(str | None, row["active_step_id"]),
            blocking_reason=cast(str | None, row["blocking_reason"]),
            pause_requested=bool(row["pause_requested"]),
            completed_steps=completed,
            total_steps=total,
            progress=1.0
            if total == 0 and row["state"] == AgentRunState.SUCCEEDED.value
            else (completed / total if total else 0.0),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
        )

    @staticmethod
    def _checkpoint_from_row(row: sqlite3.Row) -> dict[str, Any]:
        try:
            state = json.loads(cast(str, row["state_json"]))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AgentControlError("invalid_checkpoint_state") from exc
        if not isinstance(state, dict):
            raise AgentControlError("invalid_checkpoint_state")
        return {
            "id": cast(str, row["id"]),
            "run_id": cast(str, row["run_id"]),
            "revision": cast(int, row["revision"]),
            "state": state,
            "reason": cast(str, row["reason"]),
            "created_at": cast(str, row["created_at"]),
        }

    @staticmethod
    def _operation_from_row(row: sqlite3.Row) -> dict[str, Any]:
        try:
            request = json.loads(cast(str, row["request_json"]))
            result = json.loads(cast(str, row["result_json"]))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AgentControlError("invalid_operation_payload") from exc
        if not isinstance(request, dict) or not isinstance(result, dict):
            raise AgentControlError("invalid_operation_payload")
        return {
            "idempotency_key": cast(str, row["idempotency_key"]),
            "run_id": cast(str, row["run_id"]),
            "phase_id": cast(str | None, row["phase_id"]),
            "tool_name": cast(str | None, row["tool_name"]),
            "request": request,
            "state": cast(str, row["state"]),
            "result": result,
            "created_at": cast(str, row["created_at"]),
            "updated_at": cast(str, row["updated_at"]),
        }

    @staticmethod
    def _step_from_row(row: sqlite3.Row) -> PlanStep:
        return PlanStep(
            id=cast(str, row["id"]),
            run_id=cast(str, row["run_id"]),
            title=cast(str, row["title"]),
            detail=cast(str, row["detail"]),
            acceptance=cast(str, row["acceptance"]),
            state=PlanStepState(cast(str, row["state"])),
            position=cast(int, row["position"]),
            dependencies=tuple(cast(list[str], json.loads(cast(str, row["dependencies_json"])))),
            evidence=tuple(cast(list[str], json.loads(cast(str, row["evidence_json"])))),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
        )

    @staticmethod
    def _attention_from_row(row: sqlite3.Row) -> AttentionItem:
        return AttentionItem(
            id=cast(str, row["id"]),
            run_id=cast(str | None, row["run_id"]),
            session_id=cast(str | None, row["session_id"]),
            kind=AttentionKind(cast(str, row["kind"])),
            severity=cast(str, row["severity"]),
            title=cast(str, row["title"]),
            detail=cast(str, row["detail"]),
            state=AttentionState(cast(str, row["state"])),
            source_key=cast(str | None, row["source_key"]),
            action=cast(dict[str, Any], json.loads(cast(str, row["action_json"]))),
            resolution=cast(dict[str, Any], json.loads(cast(str, row["resolution_json"]))),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
        )


__all__ = ["AgentControlError", "AgentControlService"]
