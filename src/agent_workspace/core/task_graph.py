"""Durable phase graph and bounded failure recovery for long agent runs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class TaskGraphError(ValueError):
    """Raised when a phase graph is invalid or a transition is impossible."""


class PhaseState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FailureClass(StrEnum):
    TRANSIENT = "transient"
    USER_ACTION = "user_action"
    INVALID_ARGUMENTS = "invalid_arguments"
    PERMISSION = "permission"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PROVIDER = "provider"
    CONTEXT = "context"
    PERMANENT = "permanent"

    # Stable names used by the run control plane.  The canonical values above
    # remain compatible with existing callers while these aliases make the
    # user-facing failure taxonomy explicit.
    PARAMETER_ERROR = "invalid_arguments"
    PERMISSION_REQUIRED = "permission"
    UNAVAILABLE = "transient"
    FATAL = "permanent"


@dataclass(frozen=True, slots=True)
class RetryDecision:
    retryable: bool
    requires_user_action: bool
    failure_class: FailureClass
    attempt: int
    next_state: PhaseState
    reason: str


@dataclass(slots=True)
class TaskPhase:
    id: str
    name: str
    depends_on: tuple[str, ...] = ()
    state: PhaseState = PhaseState.QUEUED
    attempts: int = 0
    max_attempts: int = 3
    last_failure: str | None = None
    failure_class: FailureClass | None = None
    progress: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        data["failure_class"] = self.failure_class.value if self.failure_class else None
        data["depends_on"] = list(self.depends_on)
        return data


_TRANSIENT_MARKERS = (
    "timeout",
    "timed out",
    "temporarily unavailable",
    "rate limit",
    "too many requests",
    "connection reset",
    "connection refused",
    "503",
    "502",
    "504",
    "eof",
)


def classify_failure(error: str | BaseException) -> FailureClass:
    text = str(error).strip().casefold()
    if any(marker in text for marker in ("cancel", "aborted by user", "interrupted")):
        return FailureClass.CANCELLED
    if any(
        marker in text
        for marker in ("permission denied", "access denied", "forbidden", "not permitted")
    ):
        return FailureClass.PERMISSION
    if any(
        marker in text
        for marker in ("invalid argument", "invalid arguments", "missing required", "malformed")
    ):
        return FailureClass.INVALID_ARGUMENTS
    if any(
        marker in text
        for marker in ("context window", "context length", "prompt too large", "token limit")
    ):
        return FailureClass.CONTEXT
    if any(marker in text for marker in _TRANSIENT_MARKERS):
        return FailureClass.TRANSIENT
    if any(
        marker in text
        for marker in ("provider", "upstream", "model response", "api key", "authentication")
    ):
        return FailureClass.PROVIDER
    if "user action" in text or "approval required" in text:
        return FailureClass.USER_ACTION
    return FailureClass.PERMANENT


class TaskGraph:
    def __init__(self, *, max_attempts: int = 3) -> None:
        if type(max_attempts) is not int or max_attempts < 1:
            raise TaskGraphError("max_attempts must be a positive integer")
        self.max_attempts = max_attempts
        self._phases: dict[str, TaskPhase] = {}
        self._checkpoints: dict[str, tuple[str, ...]] = {}
        self._failure_fingerprints: dict[tuple[str, str], int] = {}

    @property
    def completed_steps(self) -> tuple[str, ...]:
        """Return completed phase ids in deterministic graph order."""

        return tuple(
            phase.id for phase in self._phases.values() if phase.state is PhaseState.COMPLETED
        )

    def add_phase(
        self,
        phase_id: str,
        name: str,
        *,
        depends_on: Iterable[str] = (),
        max_attempts: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> TaskPhase:
        if not phase_id or phase_id in self._phases:
            raise TaskGraphError(f"phase id is empty or already exists: {phase_id}")
        dependencies = tuple(dict.fromkeys(depends_on))
        missing = [item for item in dependencies if item not in self._phases]
        if missing:
            raise TaskGraphError(f"unknown phase dependency: {missing[0]}")
        phase = TaskPhase(
            id=phase_id,
            name=name,
            depends_on=dependencies,
            max_attempts=max_attempts if max_attempts is not None else self.max_attempts,
            metadata=dict(metadata or {}),
        )
        self._phases[phase_id] = phase
        try:
            self._assert_acyclic()
        except Exception:
            self._phases.pop(phase_id, None)
            raise
        return phase

    def add_dependency(self, phase_id: str, dependency_id: str) -> None:
        phase = self.phase(phase_id)
        if dependency_id not in self._phases:
            raise TaskGraphError(f"unknown phase dependency: {dependency_id}")
        if dependency_id == phase_id:
            raise TaskGraphError("phase dependency cycle detected")
        if dependency_id in phase.depends_on:
            return
        previous = phase.depends_on
        phase.depends_on = (*previous, dependency_id)
        try:
            self._assert_acyclic()
        except Exception:
            phase.depends_on = previous
            raise

    def phase(self, phase_id: str) -> TaskPhase:
        try:
            return self._phases[phase_id]
        except KeyError as exc:
            raise TaskGraphError(f"unknown phase: {phase_id}") from exc

    def phases(self) -> tuple[TaskPhase, ...]:
        return tuple(self._phases.values())

    def ready_phases(self) -> tuple[str, ...]:
        return tuple(
            phase.id
            for phase in self._phases.values()
            if phase.state == PhaseState.QUEUED
            and all(self.phase(dep).state == PhaseState.COMPLETED for dep in phase.depends_on)
        )

    def start(self, phase_id: str) -> TaskPhase:
        phase = self.phase(phase_id)
        if phase.state not in {PhaseState.QUEUED, PhaseState.PAUSED}:
            raise TaskGraphError(f"phase {phase_id} cannot start from {phase.state.value}")
        if phase_id not in self.ready_phases():
            raise TaskGraphError(f"phase {phase_id} has incomplete dependencies")
        phase.state = PhaseState.RUNNING
        return phase

    def update_progress(self, phase_id: str, progress: float) -> TaskPhase:
        phase = self.phase(phase_id)
        if not 0.0 <= progress <= 1.0:
            raise TaskGraphError("phase progress must be between 0 and 1")
        phase.progress = progress
        return phase

    def complete(self, phase_id: str) -> TaskPhase:
        phase = self.phase(phase_id)
        if phase.state != PhaseState.RUNNING:
            raise TaskGraphError(f"phase {phase_id} is not running")
        phase.state = PhaseState.COMPLETED
        phase.progress = 1.0
        self._checkpoints.setdefault(phase_id, ())
        return phase

    def pause(self, phase_id: str, reason: str = "paused") -> TaskPhase:
        phase = self.phase(phase_id)
        if phase.state not in {PhaseState.RUNNING, PhaseState.QUEUED}:
            raise TaskGraphError(f"phase {phase_id} cannot pause from {phase.state.value}")
        phase.state = PhaseState.PAUSED
        phase.last_failure = reason
        return phase

    def cancel(self, phase_id: str, reason: str = "cancelled") -> TaskPhase:
        phase = self.phase(phase_id)
        if phase.state in {PhaseState.COMPLETED, PhaseState.CANCELLED}:
            return phase
        phase.state = PhaseState.CANCELLED
        phase.last_failure = reason
        phase.failure_class = FailureClass.CANCELLED
        return phase

    def record_failure(
        self,
        phase_id: str,
        reason: str | Mapping[str, Any],
        failure_class: FailureClass | str | None = None,
        *,
        tool_arguments: Mapping[str, Any] | None = None,
    ) -> RetryDecision:
        """Record one failure and return a bounded recovery decision.

        ``reason`` may be a plain message (the original API) or a tool
        argument mapping.  The latter form lets callers fingerprint the same
        tool invocation and avoid retrying an identical failing request
        forever.  The positional third argument is accepted for the compact
        ``record_failure(tool, args, class)`` form used by the control plane.
        """
        if isinstance(reason, Mapping):
            args = dict(reason)
            requested_class = failure_class
            reason_text = str(requested_class or "tool failure")
            failure_class = (
                tool_arguments
                if isinstance(tool_arguments, (str, FailureClass))
                else requested_class
            )
            tool_arguments = args
        else:
            reason_text = reason
        if phase_id not in self._phases:
            if not isinstance(reason, Mapping):
                raise TaskGraphError(f"unknown phase: {phase_id}")
            self.add_phase(phase_id, phase_id)
        phase = self.phase(phase_id)
        if phase.state not in {PhaseState.RUNNING, PhaseState.QUEUED, PhaseState.PAUSED}:
            raise TaskGraphError(f"phase {phase_id} cannot record failure from {phase.state.value}")
        category = (
            _coerce_failure_class(failure_class)
            if failure_class is not None
            else classify_failure(reason_text)
        )
        fingerprint = _failure_fingerprint(phase_id, tool_arguments)
        if fingerprint is not None:
            self._failure_fingerprints[fingerprint] = (
                self._failure_fingerprints.get(fingerprint, 0) + 1
            )
        phase.attempts += 1
        phase.last_failure = reason_text
        phase.failure_class = category
        retryable_class = category in {
            FailureClass.TRANSIENT,
            FailureClass.TIMEOUT,
            FailureClass.PROVIDER,
            FailureClass.CONTEXT,
        }
        retryable = retryable_class and phase.attempts < phase.max_attempts
        requires_user_action = category in {
            FailureClass.PERMISSION,
            FailureClass.INVALID_ARGUMENTS,
            FailureClass.USER_ACTION,
        }
        if requires_user_action:
            next_state = PhaseState.PAUSED
        elif category == FailureClass.CANCELLED:
            next_state = PhaseState.CANCELLED
        elif retryable:
            next_state = PhaseState.QUEUED
        else:
            next_state = PhaseState.FAILED
        phase.state = next_state
        return RetryDecision(
            retryable=retryable,
            requires_user_action=requires_user_action,
            failure_class=category,
            attempt=phase.attempts,
            next_state=next_state,
            reason=reason_text,
        )

    def next_action(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
        *,
        failure_class: FailureClass | str | None = None,
    ) -> str:
        """Return the operator/model action for a tool invocation.

        This is deliberately side-effect free.  It is used before a retry to
        make permission and parameter failures actionable instead of silently
        looping.
        """
        category = _coerce_failure_class(failure_class) if failure_class is not None else None
        if category is None:
            phase = self._phases.get(tool_name)
            category = phase.failure_class if phase is not None else None
        if category in {
            FailureClass.PERMISSION,
            FailureClass.INVALID_ARGUMENTS,
            FailureClass.USER_ACTION,
        }:
            return "ask_user"
        fingerprint = _failure_fingerprint(tool_name, arguments)
        attempts = self._failure_fingerprints.get(fingerprint, 0) if fingerprint else 0
        phase = self._phases.get(tool_name)
        limit = phase.max_attempts if phase is not None else self.max_attempts
        if attempts >= limit:
            return "ask_user"
        return (
            "retry"
            if category
            in {
                None,
                FailureClass.TRANSIENT,
                FailureClass.TIMEOUT,
                FailureClass.PROVIDER,
                FailureClass.CONTEXT,
            }
            else "stop"
        )

    def checkpoint(self, checkpoint_id: str, *, completed_steps: Sequence[str] = ()) -> bool:
        """Persist an idempotent logical checkpoint in memory.

        Replaying an identical checkpoint returns ``False`` and never mutates
        the stored value; a new checkpoint returns ``True``.
        """
        if not checkpoint_id or len(checkpoint_id) > 256:
            raise TaskGraphError("checkpoint id is invalid")
        normalized = tuple(dict.fromkeys(str(item) for item in completed_steps))
        previous = self._checkpoints.get(checkpoint_id)
        if previous == normalized:
            return False
        self._checkpoints[checkpoint_id] = normalized
        return True

    def export(self) -> dict[str, Any]:
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "phases": [phase.snapshot() for phase in self._phases.values()],
            "completed_steps": list(self.completed_steps),
            "checkpoints": {key: list(value) for key, value in self._checkpoints.items()},
            "failure_fingerprints": {
                f"{key[0]}::{key[1]}": value for key, value in self._failure_fingerprints.items()
            },
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> TaskGraph:
        graph = cls(max_attempts=int(snapshot.get("max_attempts", 3)))
        raw_phases = snapshot.get("phases", ())
        if not isinstance(raw_phases, list):
            raise TaskGraphError("task graph snapshot phases must be a list")
        for raw in raw_phases:
            if not isinstance(raw, Mapping):
                raise TaskGraphError("task graph phase snapshot must be an object")
            phase_id = str(raw.get("id", ""))
            dependencies = tuple(str(item) for item in raw.get("depends_on", ()))
            phase = graph.add_phase(
                phase_id,
                str(raw.get("name", phase_id)),
                depends_on=dependencies,
                max_attempts=int(raw.get("max_attempts", graph.max_attempts)),
                metadata=raw.get("metadata") if isinstance(raw.get("metadata"), Mapping) else None,
            )
            phase.state = PhaseState(str(raw.get("state", PhaseState.QUEUED.value)))
            phase.attempts = int(raw.get("attempts", 0))
            phase.last_failure = (
                raw.get("last_failure") if isinstance(raw.get("last_failure"), str) else None
            )
            raw_class = raw.get("failure_class")
            phase.failure_class = FailureClass(str(raw_class)) if raw_class else None
            phase.progress = float(raw.get("progress", 0.0))
        raw_checkpoints = snapshot.get("checkpoints", {})
        if isinstance(raw_checkpoints, Mapping):
            graph._checkpoints = {
                str(key): tuple(str(item) for item in value)
                for key, value in raw_checkpoints.items()
                if isinstance(value, (list, tuple))
            }
        raw_fingerprints = snapshot.get("failure_fingerprints", {})
        if isinstance(raw_fingerprints, Mapping):
            for key, value in raw_fingerprints.items():
                if not isinstance(key, str) or "::" not in key:
                    continue
                tool, digest = key.split("::", 1)
                graph._failure_fingerprints[(tool, digest)] = int(value)
        return graph

    @classmethod
    def restore(cls, snapshot: Mapping[str, Any]) -> TaskGraph:
        return cls.from_snapshot(snapshot)

    def _assert_acyclic(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(phase_id: str) -> None:
            if phase_id in visiting:
                raise TaskGraphError("phase dependency cycle detected")
            if phase_id in visited:
                return
            visiting.add(phase_id)
            for dependency in self.phase(phase_id).depends_on:
                visit(dependency)
            visiting.remove(phase_id)
            visited.add(phase_id)

        for phase_id in self._phases:
            visit(phase_id)


def _coerce_failure_class(value: FailureClass | str | None) -> FailureClass:
    if value is None:
        return FailureClass.PERMANENT
    if isinstance(value, FailureClass):
        return value
    aliases = {
        "parameter_error": FailureClass.INVALID_ARGUMENTS,
        "permission_required": FailureClass.PERMISSION,
        "unavailable": FailureClass.TRANSIENT,
        "fatal": FailureClass.PERMANENT,
    }
    if value in aliases:
        return aliases[value]
    try:
        return FailureClass(value)
    except ValueError as exc:
        raise TaskGraphError(f"unknown failure class: {value}") from exc


def _failure_fingerprint(
    tool_name: str, arguments: Mapping[str, Any] | None
) -> tuple[str, str] | None:
    if arguments is None:
        return None
    try:
        encoded = json.dumps(
            dict(arguments), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        )
    except (TypeError, ValueError):
        encoded = repr(dict(arguments))
    return tool_name, hashlib.sha256(encoded.encode("utf-8")).hexdigest()
