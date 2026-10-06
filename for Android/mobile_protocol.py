"""Protocol types shared by the Android Mobile Gateway and its clients."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any
from uuid import uuid4


class TaskState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class RuntimeState(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    RUNNING = "running"
    PAUSED_BY_SYSTEM = "paused_by_system"
    RECOVERING = "recovering"
    FAILED = "failed"


class CapabilityStatus(StrEnum):
    AVAILABLE = "available"
    PERMISSION_REQUIRED = "permission_required"
    DEPENDENCY_MISSING = "dependency_missing"
    DENIED = "denied"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


_MAX_PROMPT_BYTES = 256
_MAX_PROMPT_BYTES_HARD = 128 * 1024
_MAX_IDENTIFIER_LENGTH = 256
REASONING_EFFORTS = frozenset({"auto", "none", "low", "medium", "high", "xhigh", "max"})
_MAX_IMAGE_REFS = 4


@dataclass(frozen=True, slots=True)
class MobileImageRef:
    path: str
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not isinstance(self.sha256, str):
            raise ValueError("image path and sha256 must be strings")
        parts = PurePosixPath(self.path).parts
        if (
            len(self.path) > 512
            or len(parts) != 3
            or parts[0] != "uploads"
            or len(parts[1]) != 32
            or any(character not in "0123456789abcdef" for character in parts[1])
            or PureWindowsPath(self.path).is_absolute()
            or PurePosixPath(self.path).as_posix() != self.path
            or "\\" in self.path
            or any(ord(character) < 32 for character in self.path)
            or any(character in ':<>"|?*' for character in self.path)
            or parts[-1] in {".", ".."}
        ):
            raise ValueError("image path must identify an imported workspace attachment")
        if len(self.sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.sha256
        ):
            raise ValueError("image sha256 must be a lowercase SHA-256 digest")

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "sha256": self.sha256}


def parse_mobile_image_refs(value: object) -> tuple[MobileImageRef, ...]:
    if not isinstance(value, list) or len(value) > _MAX_IMAGE_REFS:
        raise ValueError("image_refs must be a list of at most four imported images")
    refs = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {"path", "sha256"}:
            raise ValueError("image_refs entries require only path and sha256")
        refs.append(MobileImageRef(item["path"], item["sha256"]))
    if len({ref.path for ref in refs}) != len(refs):
        raise ValueError("image_refs may not repeat an attachment path")
    return tuple(refs)


def _required_text(value: object, field_name: str, *, max_length: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    result = value.strip()
    if not result:
        raise ValueError(f"{field_name} must not be empty")
    if len(result) > max_length:
        raise ValueError(f"{field_name} is too long")
    return result


def _utf8_preview(value: str, max_bytes: int = _MAX_PROMPT_BYTES) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


@dataclass(frozen=True, slots=True)
class MobileWorkspaceRequest:
    name: str
    path: str
    create: bool = False


def parse_mobile_workspace_request(payload: Mapping[str, Any]) -> MobileWorkspaceRequest:
    if not isinstance(payload, Mapping):
        raise ValueError("workspace request body must be an object")
    name = _required_text(payload.get("name"), "name", max_length=120)
    path = _required_text(payload.get("path"), "path", max_length=4096)
    if any(ord(character) < 32 or ord(character) == 127 for character in name + path):
        raise ValueError("workspace name and path must not contain control characters")
    create = payload.get("create", False)
    if type(create) is not bool:
        raise ValueError("create must be boolean")
    return MobileWorkspaceRequest(name=name, path=path, create=create)


@dataclass(frozen=True, slots=True)
class MobileTaskRequest:
    session_id: str
    prompt: str
    model: str | None = None
    reasoning_effort: str | None = None
    state: TaskState = TaskState.QUEUED
    image_refs: tuple[MobileImageRef, ...] = ()
    # Edit-and-resend / regenerate: the user message this task replaces, and why.
    rewind_from_event_id: str | None = None
    rewind_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.image_refs, tuple) or any(
            not isinstance(ref, MobileImageRef) for ref in self.image_refs
        ):
            raise ValueError("image_refs must contain validated image references")
        parse_mobile_image_refs([ref.to_dict() for ref in self.image_refs])
        if (self.rewind_from_event_id is None) != (self.rewind_reason is None):
            raise ValueError("rewind_from_event_id and rewind_reason go together")
        if self.rewind_reason is not None and self.rewind_reason not in {"edit", "regenerate"}:
            raise ValueError("rewind_reason must be edit or regenerate")

    @property
    def prompt_preview(self) -> str:
        return _utf8_preview(self.prompt)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "prompt_preview": self.prompt_preview,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "state": self.state.value,
            **(
                {"image_refs": [ref.to_dict() for ref in self.image_refs]}
                if self.image_refs
                else {}
            ),
            **(
                {"rewind_from_event_id": self.rewind_from_event_id, "rewind_reason": self.rewind_reason}
                if self.rewind_from_event_id
                else {}
            ),
        }


def parse_mobile_task_request(payload: Mapping[str, Any]) -> MobileTaskRequest:
    if not isinstance(payload, Mapping):
        raise ValueError("request body must be an object")
    session_id = _required_text(
        payload.get("session_id"), "session_id", max_length=_MAX_IDENTIFIER_LENGTH
    )
    prompt = _required_text(payload.get("prompt"), "prompt", max_length=_MAX_PROMPT_BYTES_HARD)
    raw_model = payload.get("model")
    model = None
    if raw_model is not None:
        model = _required_text(raw_model, "model", max_length=_MAX_IDENTIFIER_LENGTH)
    effort = payload.get("reasoning_effort")
    if effort is not None and (not isinstance(effort, str) or effort not in REASONING_EFFORTS):
        raise ValueError("reasoning_effort is invalid")
    rewind_from = payload.get("rewind_from_event_id")
    rewind_reason = None
    if rewind_from is not None:
        rewind_from = _required_text(rewind_from, "rewind_from_event_id", max_length=_MAX_IDENTIFIER_LENGTH)
        rewind_reason = payload.get("rewind_reason", "edit")
        if rewind_reason not in {"edit", "regenerate"}:
            raise ValueError("rewind_reason must be edit or regenerate")
    return MobileTaskRequest(
        session_id=session_id,
        prompt=prompt,
        model=model,
        reasoning_effort=effort,
        image_refs=parse_mobile_image_refs(payload.get("image_refs", [])),
        rewind_from_event_id=rewind_from,
        rewind_reason=rewind_reason,
    )


@dataclass(frozen=True, slots=True)
class MobileFileArtifact:
    path: str
    name: str
    size: int
    sha256: str | None
    mime_type: str
    state: str

    def __post_init__(self) -> None:
        from mobile_workspace import _relative_path

        _relative_path(self.path)
        if (
            self.name != PurePosixPath(self.path).name
            or type(self.size) is not int
            or self.size < 0
        ):
            raise ValueError("artifact name or size is invalid")
        if self.sha256 is not None and (
            not isinstance(self.sha256, str)
            or len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            raise ValueError("artifact sha256 is invalid")
        if (
            not isinstance(self.mime_type, str)
            or not self.mime_type
            or len(self.mime_type) > 200
            or any(ord(character) < 32 for character in self.mime_type)
            or self.state not in {"created", "modified"}
        ):
            raise ValueError("artifact media type or state is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "size": self.size,
            "sha256": self.sha256,
            "mime_type": self.mime_type,
            "state": self.state,
        }


def parse_mobile_artifacts(value: object) -> tuple[MobileFileArtifact, ...]:
    if not isinstance(value, list) or len(value) > 2000:
        raise ValueError("artifacts must be a bounded list")
    result = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "path",
            "name",
            "size",
            "sha256",
            "mime_type",
            "state",
        }:
            raise ValueError("artifact metadata is invalid")
        result.append(MobileFileArtifact(**item))
    if len({artifact.path for artifact in result}) != len(result):
        raise ValueError("artifact paths must be unique")
    return tuple(result)


@dataclass(frozen=True, slots=True)
class MobileTask:
    task_id: str
    session_id: str
    prompt: str
    model: str | None
    reasoning_effort: str | None = None
    state: TaskState = TaskState.QUEUED
    last_sequence: int = 0
    reason: str | None = None
    approval_id: str | None = None
    resume_available: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    budget_steps: int | None = None
    image_refs: tuple[MobileImageRef, ...] = ()
    artifacts: tuple[MobileFileArtifact, ...] = ()
    artifacts_truncated: bool = False
    artifacts_error: str | None = None

    @property
    def prompt_preview(self) -> str:
        return _utf8_preview(self.prompt)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "prompt_preview": self.prompt_preview,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "state": self.state.value,
            "last_sequence": self.last_sequence,
            "reason": self.reason,
            "approval_id": self.approval_id,
            "resume_available": self.resume_available,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "artifacts_truncated": self.artifacts_truncated,
            "artifacts_error": self.artifacts_error,
            **({"budget_steps": self.budget_steps} if self.budget_steps is not None else {}),
            **(
                {"image_refs": [ref.to_dict() for ref in self.image_refs]}
                if self.image_refs
                else {}
            ),
        }


@dataclass(frozen=True, slots=True)
class MobileEvent:
    task_id: str
    event_type: str
    payload: dict[str, Any]
    sequence: int
    event_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "sequence": self.sequence,
            "created_at": self.created_at,
        }


def serialize_event(event: MobileEvent) -> dict[str, Any]:
    return event.to_dict()
