from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from agent_workspace.core.models import Autonomy, Mode, Usage

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_GOAL_CHARS = 128 * 1024
_MAX_INSTRUCTIONS_CHARS = 16 * 1024
_MAX_CHECKPOINT_CHARS = 32 * 1024
_MAX_FINAL_CHARS = 128 * 1024
_MAX_DOCUMENT_BYTES = 512 * 1024
_MAX_CONTRIBUTION_BYTES = 64 * 1024


def _validate_positive_finite(value: object, label: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{label} must be finite and positive")


class CollaborationRole(StrEnum):
    PLANNER = "planner"
    RESEARCHER = "researcher"
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"
    LEAD = "lead"
    CUSTOM = "custom"


class CollaborationState(StrEnum):
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CollaborationMemberState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    RETRYABLE = "retryable"
    EXHAUSTED = "exhausted"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


class DeliveryState(StrEnum):
    RUNNABLE = "runnable"
    RUNNING = "running"
    BLOCKED = "blocked"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliverySignal(StrEnum):
    PROGRESS = "progress"
    CONTINUE = "continue"
    DELIVER = "deliver"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class CollaborationMember:
    id: str
    route_id: str
    role: CollaborationRole
    instructions: str
    mode: Mode = Mode.TASK
    allowed_tools: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier(self.id, "collaboration member id")
        _validate_identifier(self.route_id, "collaboration route id")
        if not self.instructions.strip() or len(self.instructions) > _MAX_INSTRUCTIONS_CHARS:
            raise ValueError("collaboration member instructions are empty or too large")
        if len(self.allowed_tools) > 64:
            raise ValueError("collaboration member tool allowlist is too large")
        if any(not _IDENTIFIER.fullmatch(name) for name in self.allowed_tools):
            raise ValueError("collaboration member tool allowlist contains an invalid name")
        if len({name.casefold() for name in self.allowed_tools}) != len(self.allowed_tools):
            raise ValueError("collaboration member tool allowlist contains duplicates")

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "route_id": self.route_id,
            "role": self.role.value,
            "instructions": self.instructions,
            "mode": self.mode.value,
            "allowed_tools": list(self.allowed_tools),
        }

    @classmethod
    def from_document(cls, value: object) -> CollaborationMember:
        if not isinstance(value, dict):
            raise ValueError("collaboration member document must be an object")
        allowed_tools = value.get("allowed_tools", [])
        if not isinstance(allowed_tools, list) or any(
            not isinstance(name, str) for name in allowed_tools
        ):
            raise ValueError("collaboration member tool allowlist is invalid")
        try:
            return cls(
                id=str(value["id"]),
                route_id=str(value["route_id"]),
                role=CollaborationRole(value["role"]),
                instructions=str(value["instructions"]),
                mode=Mode(value.get("mode", Mode.TASK.value)),
                allowed_tools=tuple(allowed_tools),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("collaboration member document is invalid") from exc


@dataclass(frozen=True, slots=True)
class CollaborationLimits:
    max_members: int = 64
    max_concurrency: int = 8
    max_member_attempts: int = 2
    max_contribution_bytes: int = 4 * 1024
    max_document_bytes: int = 384 * 1024
    max_duration_seconds: float = 4 * 60 * 60
    member_max_model_calls: int = 24
    member_max_tool_calls: int = 64
    member_max_input_tokens: int = 1_000_000
    member_max_output_tokens: int = 250_000

    def __post_init__(self) -> None:
        integer_values = (
            self.max_members,
            self.max_concurrency,
            self.max_member_attempts,
            self.max_contribution_bytes,
            self.max_document_bytes,
            self.member_max_model_calls,
            self.member_max_tool_calls,
            self.member_max_input_tokens,
            self.member_max_output_tokens,
        )
        if any(type(value) is not int or value <= 0 for value in integer_values):
            raise ValueError("collaboration limits must be positive")
        _validate_positive_finite(self.max_duration_seconds, "collaboration duration")
        if self.max_concurrency > self.max_members:
            raise ValueError("collaboration concurrency cannot exceed the member limit")
        if self.max_contribution_bytes > self.max_document_bytes:
            raise ValueError("collaboration contribution limit cannot exceed document limit")
        if self.max_contribution_bytes > _MAX_CONTRIBUTION_BYTES:
            raise ValueError("collaboration contribution limit exceeds the event schema limit")
        if self.max_document_bytes > _MAX_DOCUMENT_BYTES:
            raise ValueError("collaboration document limit exceeds the event schema limit")

    def to_document(self) -> dict[str, int | float]:
        return {
            "max_members": self.max_members,
            "max_concurrency": self.max_concurrency,
            "max_member_attempts": self.max_member_attempts,
            "max_contribution_bytes": self.max_contribution_bytes,
            "max_document_bytes": self.max_document_bytes,
            "max_duration_seconds": self.max_duration_seconds,
            "member_max_model_calls": self.member_max_model_calls,
            "member_max_tool_calls": self.member_max_tool_calls,
            "member_max_input_tokens": self.member_max_input_tokens,
            "member_max_output_tokens": self.member_max_output_tokens,
        }

    @classmethod
    def from_document(cls, value: object) -> CollaborationLimits:
        if not isinstance(value, dict):
            raise ValueError("collaboration limits document must be an object")
        try:
            return cls(**value)
        except (TypeError, ValueError) as exc:
            raise ValueError("collaboration limits document is invalid") from exc


@dataclass(frozen=True, slots=True)
class CollaborationRequest:
    goal: str
    members: tuple[CollaborationMember, ...]
    title: str = "Multi-agent collaboration"
    autonomy: Autonomy = Autonomy.YOLO
    limits: CollaborationLimits = CollaborationLimits()

    def __post_init__(self) -> None:
        if not isinstance(self.autonomy, Autonomy):
            raise ValueError("collaboration autonomy is invalid")
        if not self.goal.strip() or len(self.goal) > _MAX_GOAL_CHARS:
            raise ValueError("collaboration goal is empty or too large")
        if not self.members or len(self.members) > self.limits.max_members:
            raise ValueError("collaboration member count is invalid")
        member_ids = [member.id.casefold() for member in self.members]
        if len(set(member_ids)) != len(member_ids):
            raise ValueError("collaboration member ids must be unique")
        if sum(member.role is CollaborationRole.LEAD for member in self.members) != 1:
            raise ValueError("collaboration requires exactly one lead")
        if not self.title.strip() or len(self.title) > 200:
            raise ValueError("collaboration title is empty or too large")


@dataclass(frozen=True, slots=True)
class CollaborationHandle:
    id: str
    session_id: str

    def __post_init__(self) -> None:
        _validate_identifier(self.id, "collaboration id")
        if not self.session_id:
            raise ValueError("collaboration session id may not be empty")


@dataclass(frozen=True, slots=True)
class WorkDocument:
    collaboration_id: str
    revision: int
    content: str
    sha256: str
    included_members: tuple[str, ...]
    updated_at: str


@dataclass(frozen=True, slots=True)
class AgentContribution:
    member_id: str
    session_id: str
    content: str
    sha256: str
    truncated: bool
    usage: Usage


@dataclass(frozen=True, slots=True)
class CollaborationResult:
    handle: CollaborationHandle
    state: CollaborationState
    final_text: str
    document: WorkDocument
    contributions: tuple[AgentContribution, ...]


@dataclass(frozen=True, slots=True)
class CollaborationMemberProgress:
    id: str
    role: CollaborationRole
    state: CollaborationMemberState
    attempt: int
    session_id: str | None

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role.value,
            "state": self.state.value,
            "attempt": self.attempt,
            "session_id": self.session_id,
        }


@dataclass(frozen=True, slots=True)
class CollaborationStatus:
    handle: CollaborationHandle
    title: str
    goal: str
    state: CollaborationState
    phase: str
    members: tuple[CollaborationMemberProgress, ...]
    document_revision: int
    final_text: str
    detail: str
    usage: Usage
    deadline: str
    updated_at: str
    active: bool

    @property
    def can_resume(self) -> bool:
        return self.state is CollaborationState.BLOCKED or (
            self.state is CollaborationState.RUNNING and not self.active
        )

    @property
    def can_cancel(self) -> bool:
        return self.state in {CollaborationState.RUNNING, CollaborationState.BLOCKED}

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.handle.id,
            "session_id": self.handle.session_id,
            "title": self.title,
            "goal": self.goal,
            "state": self.state.value,
            "phase": self.phase,
            "members": [member.to_document() for member in self.members],
            "document_revision": self.document_revision,
            "final_text": self.final_text,
            "detail": self.detail,
            "usage": _usage_to_document(self.usage),
            "deadline": self.deadline,
            "updated_at": self.updated_at,
            "active": self.active,
            "can_resume": self.can_resume,
            "can_cancel": self.can_cancel,
        }


@dataclass(frozen=True, slots=True)
class DeliveryLimits:
    max_cycles: int = 256
    max_cycles_per_run: int = 32
    max_invalid_signals: int = 2
    max_stalled_cycles: int = 4
    max_duration_seconds: float = 8 * 60 * 60
    max_slice_seconds: float = 15 * 60
    max_total_input_tokens: int = 10_000_000
    max_total_output_tokens: int = 2_000_000
    max_input_tokens_per_slice: int = 1_000_000
    max_output_tokens_per_slice: int = 250_000
    max_model_calls_per_slice: int = 24
    max_tool_calls_per_slice: int = 64

    def __post_init__(self) -> None:
        integer_values = (
            self.max_cycles,
            self.max_cycles_per_run,
            self.max_invalid_signals,
            self.max_stalled_cycles,
            self.max_total_input_tokens,
            self.max_total_output_tokens,
            self.max_input_tokens_per_slice,
            self.max_output_tokens_per_slice,
            self.max_model_calls_per_slice,
            self.max_tool_calls_per_slice,
        )
        if any(type(value) is not int or value <= 0 for value in integer_values):
            raise ValueError("delivery limits must be positive")
        _validate_positive_finite(self.max_duration_seconds, "delivery duration")
        _validate_positive_finite(self.max_slice_seconds, "delivery slice duration")
        if self.max_cycles_per_run > self.max_cycles:
            raise ValueError("per-run delivery cycles cannot exceed total cycles")
        if self.max_input_tokens_per_slice > self.max_total_input_tokens:
            raise ValueError("slice input budget cannot exceed total delivery input budget")
        if self.max_output_tokens_per_slice > self.max_total_output_tokens:
            raise ValueError("slice output budget cannot exceed total delivery output budget")

    def to_document(self) -> dict[str, int | float]:
        return {
            "max_cycles": self.max_cycles,
            "max_cycles_per_run": self.max_cycles_per_run,
            "max_invalid_signals": self.max_invalid_signals,
            "max_stalled_cycles": self.max_stalled_cycles,
            "max_duration_seconds": self.max_duration_seconds,
            "max_slice_seconds": self.max_slice_seconds,
            "max_total_input_tokens": self.max_total_input_tokens,
            "max_total_output_tokens": self.max_total_output_tokens,
            "max_input_tokens_per_slice": self.max_input_tokens_per_slice,
            "max_output_tokens_per_slice": self.max_output_tokens_per_slice,
            "max_model_calls_per_slice": self.max_model_calls_per_slice,
            "max_tool_calls_per_slice": self.max_tool_calls_per_slice,
        }

    @classmethod
    def from_document(cls, value: object) -> DeliveryLimits:
        if not isinstance(value, dict):
            raise ValueError("delivery limits document must be an object")
        try:
            return cls(**value)
        except (TypeError, ValueError) as exc:
            raise ValueError("delivery limits document is invalid") from exc


@dataclass(frozen=True, slots=True)
class DeliveryDirective:
    signal: DeliverySignal
    checkpoint: str = ""
    next_action: str = ""
    final: str = ""
    block_code: str = ""
    detail: str = ""

    @classmethod
    def parse(cls, text: str) -> DeliveryDirective:
        try:
            value = json.loads(text, object_pairs_hook=_unique_json_object)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError("delivery response must be exactly one JSON object") from exc
        if not isinstance(value, dict):
            raise ValueError("delivery response must be exactly one JSON object")
        try:
            signal = DeliverySignal(value["status"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("delivery response has an invalid status") from exc
        required_fields = {
            DeliverySignal.PROGRESS: {"status", "checkpoint", "next_action"},
            DeliverySignal.CONTINUE: {"status", "checkpoint", "next_action"},
            DeliverySignal.DELIVER: {"status", "final"},
            DeliverySignal.BLOCK: {"status", "block_code", "detail"},
        }[signal]
        if set(value) != required_fields:
            raise ValueError(f"delivery response fields do not match status {signal.value!r}")
        allowed = {"checkpoint", "next_action", "final", "block_code", "detail"}
        fields: dict[str, str] = {}
        for key in allowed:
            raw = value.get(key, "")
            if not isinstance(raw, str):
                raise ValueError(f"delivery response field {key!r} must be text")
            _validate_utf8(raw, f"delivery response field {key!r}")
            fields[key] = raw
        directive = cls(signal=signal, **fields)
        directive.validate()
        return directive

    def validate(self) -> None:
        if len(self.checkpoint) > _MAX_CHECKPOINT_CHARS:
            raise ValueError("delivery checkpoint is too large")
        if len(self.next_action) > _MAX_INSTRUCTIONS_CHARS:
            raise ValueError("delivery next action is too large")
        if len(self.final) > _MAX_FINAL_CHARS:
            raise ValueError("delivery final response is too large")
        if len(self.detail) > _MAX_INSTRUCTIONS_CHARS:
            raise ValueError("delivery block detail is too large")
        if self.signal in {DeliverySignal.PROGRESS, DeliverySignal.CONTINUE}:
            if not self.checkpoint.strip() or not self.next_action.strip():
                raise ValueError("continue/progress requires checkpoint and next_action")
        elif self.signal is DeliverySignal.DELIVER:
            if not self.final.strip():
                raise ValueError("deliver requires a final response")
        elif self.signal is DeliverySignal.BLOCK and (
            not _IDENTIFIER.fullmatch(self.block_code) or not self.detail.strip()
        ):
            raise ValueError("block requires a valid block_code and detail")


@dataclass(frozen=True, slots=True)
class DeliveryHandle:
    id: str
    session_id: str

    def __post_init__(self) -> None:
        _validate_identifier(self.id, "delivery id")
        if not self.session_id:
            raise ValueError("delivery session id may not be empty")


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    handle: DeliveryHandle
    state: DeliveryState
    cycles: int
    checkpoint: str
    final_text: str
    block_code: str
    detail: str
    usage: Usage


@dataclass(frozen=True, slots=True)
class DeliveryStatus:
    handle: DeliveryHandle
    goal: str
    state: DeliveryState
    route_id: str
    model: str
    allowed_tools: tuple[str, ...] | None
    cycles: int
    max_cycles: int
    checkpoint: str
    next_action: str
    final_text: str
    block_code: str
    detail: str
    usage: Usage
    deadline: str
    updated_at: str
    active: bool

    @property
    def can_resume(self) -> bool:
        return self.state in {DeliveryState.RUNNABLE, DeliveryState.BLOCKED} or (
            self.state is DeliveryState.RUNNING and not self.active
        )

    @property
    def can_cancel(self) -> bool:
        return self.state in {
            DeliveryState.RUNNABLE,
            DeliveryState.RUNNING,
            DeliveryState.BLOCKED,
        }

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.handle.id,
            "session_id": self.handle.session_id,
            "goal": self.goal,
            "state": self.state.value,
            "route_id": self.route_id,
            "model": self.model,
            "allowed_tools": (list(self.allowed_tools) if self.allowed_tools is not None else None),
            "cycles": self.cycles,
            "max_cycles": self.max_cycles,
            "checkpoint": self.checkpoint,
            "next_action": self.next_action,
            "final_text": self.final_text,
            "block_code": self.block_code,
            "detail": self.detail,
            "usage": _usage_to_document(self.usage),
            "deadline": self.deadline,
            "updated_at": self.updated_at,
            "active": self.active,
            "can_resume": self.can_resume,
            "can_cancel": self.can_cancel,
        }


@dataclass(frozen=True, slots=True)
class BranchOrchestrationResult:
    """Bounded outcome for independently retryable agent branches."""

    completed: tuple[str, ...]
    retryable: tuple[str, ...]
    exhausted: tuple[str, ...]
    attempts: dict[str, int]

    def to_document(self) -> dict[str, Any]:
        return {
            "completed": list(self.completed),
            "retryable": list(self.retryable),
            "exhausted": list(self.exhausted),
            "attempts": dict(self.attempts),
        }


def orchestrate_branches(
    branches: Sequence[str],
    *,
    failed: Collection[str] = (),
    attempts: Mapping[str, int] | None = None,
    max_attempts: int = 2,
) -> BranchOrchestrationResult:
    """Classify branch outcomes without restarting successful branches.

    ``failed`` contains branch ids that need another attempt.  ``attempts`` is
    the number of attempts already consumed for each branch, so a branch is
    retryable while its count is below ``max_attempts``.  The input order is
    preserved in every result tuple, which keeps the projection stable for UI
    updates and persisted evidence.
    """

    if type(max_attempts) is not int or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")
    normalized = tuple(branches)
    if not normalized or any(
        not isinstance(branch, str) or not branch.strip() for branch in normalized
    ):
        raise ValueError("branches must contain non-empty strings")
    if len(set(normalized)) != len(normalized):
        raise ValueError("branches must be unique")
    failed_set = set(failed)
    if any(not isinstance(branch, str) for branch in failed_set):
        raise ValueError("failed branches must be strings")
    unknown = failed_set.difference(normalized)
    if unknown:
        raise ValueError(f"unknown failed branch: {sorted(unknown)[0]}")
    supplied_attempts = dict(attempts or {})
    if any(branch not in normalized for branch in supplied_attempts):
        unknown_attempt = next(branch for branch in supplied_attempts if branch not in normalized)
        raise ValueError(f"unknown branch attempt: {unknown_attempt}")
    if any(type(value) is not int or value < 0 for value in supplied_attempts.values()):
        raise ValueError("branch attempts must be non-negative integers")

    completed: list[str] = []
    retryable: list[str] = []
    exhausted: list[str] = []
    result_attempts: dict[str, int] = {}
    for branch in normalized:
        consumed = supplied_attempts.get(branch, 0)
        result_attempts[branch] = consumed
        if branch not in failed_set:
            completed.append(branch)
        elif consumed < max_attempts:
            retryable.append(branch)
        else:
            exhausted.append(branch)
    return BranchOrchestrationResult(
        completed=tuple(completed),
        retryable=tuple(retryable),
        exhausted=tuple(exhausted),
        attempts=result_attempts,
    )


@dataclass(frozen=True, slots=True)
class RunProjection:
    """Stable cross-surface view of execution, artifacts, failure and delivery."""

    id: str
    goal: str
    phase: str
    agent: str | None
    workspace: str | None
    branch: str | None
    budget: dict[str, Any]
    cost_estimate: float | int | None
    artifact: dict[str, Any] | None
    failure: dict[str, Any] | None
    pr_status: dict[str, Any] | None

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "phase": self.phase,
            "agent": self.agent,
            "workspace": self.workspace,
            "branch": self.branch,
            "budget": dict(self.budget),
            "costEstimate": self.cost_estimate,
            "artifact": dict(self.artifact) if self.artifact is not None else None,
            "failure": dict(self.failure) if self.failure is not None else None,
            "prStatus": dict(self.pr_status) if self.pr_status is not None else None,
        }


def _projection_value(source: object, *keys: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        for key in keys:
            if key in source:
                return source[key]
        return default
    for key in keys:
        if hasattr(source, key):
            return getattr(source, key)
    return default


def _mapping_copy(value: object, label: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return dict(value)


def build_run_projection(
    source: object | None = None,
    *,
    id: str | None = None,
    goal: str | None = None,
    phase: str | None = None,
    agent: str | None = None,
    workspace: str | None = None,
    branch: str | None = None,
    budget: Mapping[str, Any] | None = None,
    cost_estimate: float | int | None = None,
    artifact: Mapping[str, Any] | None = None,
    failure: Mapping[str, Any] | None = None,
    pr_status: Mapping[str, Any] | None = None,
) -> RunProjection:
    """Build the UI/API projection from a run status or explicit fields.

    The source form is intentionally duck-typed so collaboration, delivery
    and persisted AgentRun records can share one projection without importing
    application-layer services into the core model module.
    """

    source_value = source
    source_id = (
        _projection_value(source_value, "id", default="") if source_value is not None else ""
    )
    if source_value is not None and hasattr(source_value, "handle"):
        handle = source_value.handle
        source_id = _projection_value(handle, "id", default=source_id)
    resolved_id = id if id is not None else str(source_id or "")
    resolved_goal = (
        goal if goal is not None else str(_projection_value(source_value, "goal", default=""))
    )
    source_phase = _projection_value(source_value, "phase", "state", default="")
    if hasattr(source_phase, "value"):
        source_phase = source_phase.value
    resolved_phase = phase if phase is not None else str(source_phase)
    source_agent = _projection_value(source_value, "agent", "model", "route_id", default=None)
    if agent is None and source_agent is not None:
        agent = str(source_agent)
    if workspace is None:
        workspace_value = _projection_value(source_value, "workspace", default=None)
        workspace = str(workspace_value) if workspace_value is not None else None
    if branch is None:
        branch_value = _projection_value(source_value, "branch", "head_branch", default=None)
        branch = str(branch_value) if branch_value is not None else None
    resolved_budget = (
        dict(budget)
        if budget is not None
        else _mapping_copy(
            _projection_value(source_value, "budget", "limits", default={}), "budget"
        )
        or {}
    )
    if cost_estimate is None:
        source_cost = _projection_value(source_value, "cost_estimate", "costEstimate", default=None)
        if source_cost is not None and (
            isinstance(source_cost, bool) or not isinstance(source_cost, (int, float))
        ):
            raise ValueError("cost estimate must be numeric")
        cost_estimate = source_cost
    resolved_artifact = (
        dict(artifact)
        if artifact is not None
        else _mapping_copy(_projection_value(source_value, "artifact", default=None), "artifact")
    )
    if resolved_artifact is None:
        checkpoint = _projection_value(source_value, "checkpoint", default=None)
        if isinstance(checkpoint, str) and checkpoint:
            resolved_artifact = {"kind": "checkpoint", "value": checkpoint}
    resolved_failure = (
        dict(failure)
        if failure is not None
        else _mapping_copy(_projection_value(source_value, "failure", default=None), "failure")
    )
    if resolved_failure is None:
        block_code = _projection_value(source_value, "block_code", "blocking_reason", default=None)
        detail = _projection_value(source_value, "detail", default=None)
        if block_code or detail:
            resolved_failure = {
                key: value
                for key, value in {
                    "code": block_code,
                    "detail": detail,
                }.items()
                if value not in (None, "")
            }
    resolved_pr = (
        dict(pr_status)
        if pr_status is not None
        else _mapping_copy(
            _projection_value(source_value, "pr_status", "prStatus", default=None), "pr status"
        )
    )
    return RunProjection(
        id=resolved_id,
        goal=resolved_goal,
        phase=resolved_phase,
        agent=agent,
        workspace=workspace,
        branch=branch,
        budget=resolved_budget,
        cost_estimate=cost_estimate,
        artifact=resolved_artifact,
        failure=resolved_failure,
        pr_status=resolved_pr,
    )


def _validate_identifier(value: object, label: str) -> None:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{label} is invalid")


def _usage_to_document(usage: Usage) -> dict[str, int | bool]:
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cached_tokens": usage.cached_tokens,
        "estimated": usage.estimated,
    }


def _validate_utf8(value: str, label: str) -> None:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} must be valid UTF-8 text") from exc


def _is_aware_timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _validate_usage_document(value: object, label: str) -> None:
    if not isinstance(value, dict) or set(value) != {
        "input_tokens",
        "output_tokens",
        "cached_tokens",
        "estimated",
    }:
        raise ValueError(f"{label} contains invalid usage")
    if any(
        type(value[key]) is not int or value[key] < 0
        for key in ("input_tokens", "output_tokens", "cached_tokens")
    ) or not isinstance(value["estimated"], bool):
        raise ValueError(f"{label} contains invalid usage")


def _validate_cycle(value: object, label: str, *, allow_zero: bool = False) -> None:
    minimum = 0 if allow_zero else 1
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} contains an invalid cycle")


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("delivery response contains duplicate fields")
        result[key] = value
    return result


def validate_orchestration_event(event_type: str, data: dict[str, Any]) -> bool:
    if not event_type.startswith(("collaboration.", "delivery.")):
        return False
    identity_key = "collaboration_id" if event_type.startswith("collaboration.") else "delivery_id"
    identity = data.get(identity_key)
    _validate_identifier(identity, identity_key)

    if event_type == "collaboration.started":
        goal = data.get("goal")
        members = data.get("members")
        if not isinstance(goal, str) or not goal.strip() or len(goal) > _MAX_GOAL_CHARS:
            raise ValueError("collaboration.started contains an invalid goal")
        if not isinstance(members, list) or not members or len(members) > 64:
            raise ValueError("collaboration.started contains invalid members")
        if data.get("workflow_version") != "role_document_v1":
            raise ValueError("collaboration.started has an unsupported workflow version")
        parsed = tuple(CollaborationMember.from_document(member) for member in members)
        try:
            raw_title = data["title"]
            raw_routes = data["routes"]
            if not isinstance(raw_title, str) or not isinstance(raw_routes, dict):
                raise ValueError("collaboration title or routes are invalid")
            if set(raw_routes) != {member.route_id for member in parsed} or any(
                not isinstance(route_id, str) or not isinstance(model, str) or not model.strip()
                for route_id, model in raw_routes.items()
            ):
                raise ValueError("collaboration routes are invalid")
            CollaborationRequest(
                goal=goal,
                members=parsed,
                title=raw_title,
                autonomy=Autonomy(data["autonomy"]),
                limits=CollaborationLimits.from_document(data["limits"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("collaboration.started contains invalid workflow data") from exc
        if not _is_aware_timestamp(data.get("deadline")):
            raise ValueError("collaboration.started contains an invalid deadline")
        return True
    if event_type == "collaboration.document.updated":
        content = data.get("content")
        digest = data.get("sha256")
        revision = data.get("revision")
        included = data.get("included_members")
        if (
            not isinstance(content, str)
            or len(content.encode("utf-8")) > 512 * 1024
            or not isinstance(digest, str)
            or _SHA256.fullmatch(digest) is None
            or not isinstance(revision, int)
            or isinstance(revision, bool)
            or revision <= 0
            or type(data.get("expected_revision")) is not int
            or data.get("expected_revision") != revision - 1
            or not isinstance(included, list)
            or any(
                not isinstance(member_id, str) or _IDENTIFIER.fullmatch(member_id) is None
                for member_id in included
            )
            or len(set(included)) != len(included)
            or hashlib.sha256(content.encode("utf-8")).hexdigest() != digest
        ):
            raise ValueError("collaboration.document.updated contains invalid document data")
        return True
    if event_type in {
        "collaboration.member.started",
        "collaboration.member.resumed",
        "collaboration.member.completed",
        "collaboration.member.failed",
    }:
        _validate_identifier(data.get("member_id"), "collaboration member id")
        session_id = data.get("member_session_id")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("collaboration member event contains an invalid session id")
        contribution = data.get("content")
        if contribution is not None and (
            not isinstance(contribution, str)
            or len(contribution.encode("utf-8")) > _MAX_CONTRIBUTION_BYTES
        ):
            raise ValueError("collaboration member event contains invalid content")
        attempt = data.get("attempt")
        if type(attempt) is not int or attempt <= 0:
            raise ValueError("collaboration member event contains an invalid attempt")
        if event_type == "collaboration.member.completed":
            digest = data.get("sha256")
            if (
                not isinstance(contribution, str)
                or not isinstance(digest, str)
                or hashlib.sha256(contribution.encode("utf-8")).hexdigest() != digest
                or not isinstance(data.get("truncated"), bool)
            ):
                raise ValueError("collaboration member completion is invalid")
            _validate_usage_document(data.get("usage"), event_type)
        return True
    if event_type == "collaboration.running":
        return True
    if event_type in {
        "collaboration.blocked",
        "collaboration.failed",
        "collaboration.cancelled",
    }:
        reason = data.get("reason")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise ValueError(f"{event_type} contains an invalid reason")
        return True
    if event_type == "collaboration.completed":
        final = data.get("final")
        digest = data.get("final_sha256")
        if (
            not isinstance(final, str)
            or not final.strip()
            or not isinstance(digest, str)
            or hashlib.sha256(final.encode("utf-8")).hexdigest() != digest
        ):
            raise ValueError("collaboration.completed contains invalid final content")
        return True

    if event_type == "delivery.started":
        goal = data.get("goal")
        DeliveryLimits.from_document(data.get("limits"))
        allowed_tools = data.get("allowed_tools")
        if not isinstance(goal, str) or not goal.strip() or len(goal) > _MAX_GOAL_CHARS:
            raise ValueError("delivery.started contains an invalid goal")
        if data.get("autonomy") not in {
            Autonomy.YOLO.value,
            Autonomy.FULL_ACCESS.value,
        }:
            raise ValueError("delivery.started must use YOLO or Full access autonomy")
        if allowed_tools is not None and (
            not isinstance(allowed_tools, list)
            or len(allowed_tools) > 64
            or any(
                not isinstance(name, str) or _IDENTIFIER.fullmatch(name) is None
                for name in allowed_tools
            )
            or allowed_tools != sorted(set(allowed_tools))
        ):
            raise ValueError("delivery.started contains an invalid tool allowlist")
        _validate_identifier(data.get("route_id"), "delivery route id")
        model = data.get("model")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("delivery.started contains an invalid model")
        if not _is_aware_timestamp(data.get("deadline")):
            raise ValueError("delivery.started contains an invalid deadline")
        return True
    if event_type == "delivery.slice.started":
        _validate_cycle(data.get("cycle"), event_type)
        return True
    if event_type == "delivery.checkpointed":
        checkpoint = data.get("checkpoint")
        next_action = data.get("next_action")
        if (
            not isinstance(checkpoint, str)
            or not checkpoint.strip()
            or len(checkpoint) > _MAX_CHECKPOINT_CHARS
            or not isinstance(next_action, str)
            or not next_action.strip()
            or len(next_action) > _MAX_INSTRUCTIONS_CHARS
            or data.get("checkpoint_sha256")
            != hashlib.sha256(checkpoint.encode("utf-8")).hexdigest()
        ):
            raise ValueError("delivery.checkpointed contains invalid progress data")
        _validate_cycle(data.get("cycle"), event_type)
        if data.get("signal") not in {
            DeliverySignal.PROGRESS.value,
            DeliverySignal.CONTINUE.value,
        }:
            raise ValueError("delivery.checkpointed contains an invalid signal")
        stalled_cycles = data.get("stalled_cycles")
        if type(stalled_cycles) is not int or stalled_cycles < 0:
            raise ValueError("delivery.checkpointed contains an invalid stall count")
        _validate_usage_document(data.get("usage"), event_type)
        return True
    if event_type == "delivery.delivered":
        final = data.get("final")
        if (
            not isinstance(final, str)
            or not final.strip()
            or len(final) > _MAX_FINAL_CHARS
            or data.get("final_sha256") != hashlib.sha256(final.encode("utf-8")).hexdigest()
        ):
            raise ValueError("delivery.delivered contains invalid final content")
        _validate_cycle(data.get("cycle"), event_type)
        _validate_usage_document(data.get("usage"), event_type)
        return True
    if event_type == "delivery.running":
        _validate_cycle(data.get("cycle"), event_type, allow_zero=True)
        return True
    if event_type == "delivery.signal_invalid":
        _validate_cycle(data.get("cycle"), event_type)
        reason = data.get("reason")
        invalid_signals = data.get("invalid_signals")
        if (
            not isinstance(reason, str)
            or not reason
            or len(reason) > 2000
            or type(invalid_signals) is not int
            or invalid_signals <= 0
            or _SHA256.fullmatch(str(data.get("response_sha256"))) is None
        ):
            raise ValueError("delivery.signal_invalid contains invalid signal data")
        _validate_usage_document(data.get("usage"), event_type)
        return True
    if event_type == "delivery.blocked":
        _validate_cycle(data.get("cycle"), event_type)
        detail = data.get("detail")
        if (
            _IDENTIFIER.fullmatch(str(data.get("block_code"))) is None
            or not isinstance(detail, str)
            or not detail.strip()
            or len(detail) > 4000
        ):
            raise ValueError("delivery.blocked contains invalid block data")
        _validate_usage_document(data.get("usage"), event_type)
        return True
    if event_type == "delivery.failed":
        _validate_cycle(data.get("cycle"), event_type, allow_zero=True)
        reason = data.get("reason")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise ValueError("delivery.failed contains an invalid reason")
        _validate_usage_document(data.get("usage"), event_type)
        return True
    if event_type == "delivery.cancelled":
        reason = data.get("reason")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise ValueError("delivery.cancelled contains an invalid reason")
        return True
    raise ValueError(f"unsupported orchestration event type: {event_type}")
