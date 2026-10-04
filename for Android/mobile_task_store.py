"""Durable Android task projection backed by the existing event store."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from mobile_protocol import (
    MobileEvent,
    MobileTask,
    MobileTaskRequest,
    TaskState,
    parse_mobile_artifacts,
    parse_mobile_image_refs,
)

from agent_workspace.application.ports import EventStore
from agent_workspace.core.events import Event
from agent_workspace.core.models import BinaryArtifact, ImagePart, validate_image_parts

_TERMINAL_STATES = frozenset({TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED})
_ALLOWED_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.QUEUED: frozenset({TaskState.RUNNING, TaskState.CANCELLED, TaskState.INTERRUPTED}),
    TaskState.RUNNING: frozenset(
        {
            TaskState.WAITING_APPROVAL,
            TaskState.SUCCEEDED,
            TaskState.FAILED,
            TaskState.CANCELLED,
            TaskState.INTERRUPTED,
        }
    ),
    TaskState.WAITING_APPROVAL: frozenset(
        {
            TaskState.RUNNING,
            TaskState.SUCCEEDED,
            TaskState.FAILED,
            TaskState.CANCELLED,
            TaskState.INTERRUPTED,
        }
    ),
    TaskState.INTERRUPTED: frozenset({TaskState.QUEUED, TaskState.RUNNING, TaskState.CANCELLED}),
    TaskState.SUCCEEDED: frozenset(),
    TaskState.FAILED: frozenset(),
    TaskState.CANCELLED: frozenset(),
}


def _state(value: TaskState | str) -> TaskState:
    try:
        return value if isinstance(value, TaskState) else TaskState(value)
    except ValueError:
        raise ValueError(f"unknown mobile task state: {value}") from None


def _request_content(request: MobileTaskRequest, budget_steps: int | None) -> dict[str, Any]:
    return {
        "session_id": request.session_id,
        "prompt": request.prompt,
        "model": request.model,
        "reasoning_effort": request.reasoning_effort,
        "budget_steps": budget_steps,
        **(
            {"image_refs": [ref.to_dict() for ref in request.image_refs]}
            if request.image_refs
            else {}
        ),
    }


class MobileTaskStore:
    def __init__(
        self,
        event_store: EventStore,
        *,
        workspace: str | Path | None = None,
        session_id: str | None = None,
    ) -> None:
        self.event_store = event_store
        self.workspace = Path(workspace).resolve() if workspace is not None else None
        self.session_id = session_id
        if session_id is not None and (not isinstance(session_id, str) or not session_id):
            raise ValueError("session_id must not be empty")

    def create(
        self,
        session_id: str,
        prompt: str,
        model: str | None,
        reasoning_effort: str | None = None,
        *,
        request_id: str | None = None,
        budget_steps: int | None = None,
        request: MobileTaskRequest | None = None,
        images: tuple[ImagePart, ...] = (),
    ) -> MobileTask:
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id must not be empty")
        if self.session_id is not None and session_id != self.session_id:
            raise KeyError(session_id)
        if self.workspace is not None:
            session = self.event_store.get_session(session_id)
            if session is None or Path(session.workspace).resolve() != self.workspace:
                raise KeyError(session_id)
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must not be empty")
        if budget_steps is not None and (
            type(budget_steps) is not int or not 1 <= budget_steps <= 1000
        ):
            raise ValueError("budget_steps must be an integer from 1 to 1000")
        original = request or MobileTaskRequest(session_id, prompt, model, reasoning_effort)
        if original.session_id != session_id or original.prompt != prompt:
            raise ValueError("request content does not match the task")
        validate_image_parts(images)
        if len(images) != len(original.image_refs):
            raise ValueError("verified image bytes must match the task image references")
        if request_id is not None:
            existing = self.find_request(original, request_id, budget_steps=budget_steps)
            if existing is not None:
                return existing
        task_id = str(uuid4())
        created = Event(
            session_id=session_id,
            type="mobile.task.created",
            data={
                "task_id": task_id,
                "session_id": session_id,
                "prompt": prompt,
                "model": model,
                "reasoning_effort": reasoning_effort,
                "state": TaskState.QUEUED.value,
                **(
                    {
                        "request_id": request_id,
                        "request_content": _request_content(original, budget_steps),
                    }
                    if request_id is not None
                    else {}
                ),
                **({"budget_steps": budget_steps} if budget_steps is not None else {}),
                **(
                    {"image_refs": [ref.to_dict() for ref in original.image_refs]}
                    if original.image_refs
                    else {}
                ),
            },
        )
        image_events = []
        artifacts = []
        for ref, image in zip(original.image_refs, images, strict=True):
            artifact = BinaryArtifact(sha256=ref.sha256, content=image.data)
            artifacts.append(artifact)
            image_events.append(
                Event(
                    session_id=session_id,
                    type="image.attached",
                    data={
                        "task_id": task_id,
                        "sha256": ref.sha256,
                        "media_type": image.media_type,
                        "bytes": len(image.data),
                        "path": ref.path,
                        "source": "mobile_task_input",
                        "attempt_id": task_id,
                    },
                )
            )
        if artifacts:
            event = self.event_store.append_many_with_artifacts(
                (created, *image_events), tuple(artifacts)
            )[0]
        else:
            event = self.event_store.append(created)
        return MobileTask(
            task_id=task_id,
            session_id=session_id,
            prompt=prompt,
            model=model,
            reasoning_effort=reasoning_effort,
            last_sequence=event.sequence or 0,
            created_at=event.created_at,
            updated_at=event.created_at,
            budget_steps=budget_steps,
            image_refs=original.image_refs,
        )

    def find_request(
        self,
        request: MobileTaskRequest,
        request_id: str,
        *,
        budget_steps: int | None = None,
    ) -> MobileTask | None:
        if (
            not isinstance(request_id, str)
            or not request_id
            or len(request_id) > 128
            or any(ord(c) < 33 for c in request_id)
        ):
            raise ValueError("request_id is invalid")
        if budget_steps is not None and (
            type(budget_steps) is not int or not 1 <= budget_steps <= 1000
        ):
            raise ValueError("budget_steps must be an integer from 1 to 1000")
        expected = _request_content(request, budget_steps)
        for event in self.event_store.list_events(request.session_id):
            if event.type != "mobile.task.created" or event.data.get("request_id") != request_id:
                continue
            # Older task events recorded only the resolved fields.
            actual = event.data.get("request_content") or {
                key: event.data.get(key) for key in expected
            }
            if actual != expected:
                raise ValueError("request_id belongs to different task content")
            return self.get(event.data["task_id"])
        return None

    def get(self, task_id: str) -> MobileTask:
        task = self._rebuild().get(task_id)
        if task is None:
            raise KeyError(task_id)
        return task

    def list(self, session_id: str | None = None) -> list[MobileTask]:
        tasks = list(self._rebuild().values())
        if session_id is not None:
            tasks = [task for task in tasks if task.session_id == session_id]
        return sorted(tasks, key=lambda task: (task.updated_at, task.task_id), reverse=True)

    def has_persisted_input(self, task_id: str) -> bool:
        task = self.get(task_id)
        active_task_id = None
        # RUNNING precedes input persistence; inspect core events in that execution interval.
        for event in self.event_store.list_events(task.session_id):
            if event.type == "mobile.task.running":
                active_task_id = event.data.get("task_id")
            elif (
                event.type
                in {
                    "mobile.task.interrupted",
                    "mobile.task.cancelled",
                    "mobile.task.failed",
                    "mobile.task.succeeded",
                }
                and event.data.get("task_id") == active_task_id
            ):
                active_task_id = None
            elif (
                active_task_id == task_id
                and event.type == "message.created"
                and event.data.get("role") == "user"
                and event.data.get("content") == task.prompt
                and (
                    not task.image_refs
                    or [
                        part.get("sha256")
                        for part in event.data.get("provider_metadata", {}).get(
                            "agent_workspace.images", []
                        )
                    ]
                    == [ref.sha256 for ref in task.image_refs]
                )
            ):
                return True
        return False

    def images(self, task_id: str) -> tuple[ImagePart, ...]:
        task = self.get(task_id)
        metadata = {
            event.data.get("sha256"): event.data
            for event in self.event_store.list_events(task.session_id)
            if event.type == "image.attached"
            and event.data.get("task_id") == task_id
            and event.data.get("source") == "mobile_task_input"
        }
        images = []
        for ref in task.image_refs:
            record = metadata.get(ref.sha256)
            artifact = (
                self.event_store.get_binary_artifact(ref.sha256) if record is not None else None
            )
            if artifact is None or record.get("bytes") != len(artifact.content):
                raise ValueError("the durable task image is missing or invalid")
            images.append(ImagePart(record["media_type"], artifact.content))
        result = tuple(images)
        validate_image_parts(result)
        return result

    def transition(
        self,
        task_id: str,
        state: TaskState | str,
        *,
        reason: str | None = None,
        approval_id: str | None = None,
        resume_available: bool = False,
    ) -> MobileTask:
        current = self.get(task_id)
        target = _state(state)
        if target not in _ALLOWED_TRANSITIONS[current.state]:
            raise ValueError(
                f"invalid mobile task transition: {current.state.value} -> {target.value}"
            )
        event = self.event_store.append(
            Event(
                session_id=current.session_id,
                type=f"mobile.task.{target.value}",
                data={
                    "task_id": current.task_id,
                    "session_id": current.session_id,
                    "state": target.value,
                    "reason": reason,
                    "approval_id": approval_id,
                    "resume_available": bool(resume_available),
                },
            )
        )
        return replace(
            current,
            state=target,
            last_sequence=event.sequence or current.last_sequence,
            reason=reason,
            approval_id=approval_id,
            resume_available=bool(resume_available),
            updated_at=event.created_at,
        )

    def artifact_snapshot(self, task_id: str) -> dict[str, Any] | None:
        task = self.get(task_id)
        for event in reversed(self.event_store.list_events(task.session_id)):
            if event.type == "mobile.artifacts.snapshot" and event.data.get("task_id") == task_id:
                snapshot = event.data.get("snapshot")
                return snapshot if isinstance(snapshot, dict) else None
        return None

    def save_artifact_snapshot(self, task_id: str, snapshot: dict[str, Any]) -> None:
        task = self.get(task_id)
        self.event_store.append(
            Event(
                session_id=task.session_id,
                type="mobile.artifacts.snapshot",
                data={"task_id": task_id, "snapshot": snapshot},
            )
        )

    def artifact_checkpoint(self, task_id: str) -> dict[str, Any] | None:
        task = self.get(task_id)
        for event in reversed(self.event_store.list_events(task.session_id)):
            if event.type == "mobile.artifacts.checkpoint" and event.data.get("task_id") == task_id:
                checkpoint = event.data.get("checkpoint")
                return checkpoint if isinstance(checkpoint, dict) else None
        return None

    def save_artifact_checkpoint(self, task_id: str, checkpoint: dict[str, Any]) -> None:
        task = self.get(task_id)
        self.event_store.append(
            Event(
                session_id=task.session_id,
                type="mobile.artifacts.checkpoint",
                data={"task_id": task_id, "checkpoint": checkpoint},
            )
        )

    def complete(self, task_id: str, payload: dict[str, Any]) -> MobileTask:
        current = self.get(task_id)
        if TaskState.SUCCEEDED not in _ALLOWED_TRANSITIONS[current.state]:
            raise ValueError("task cannot be completed from its current state")
        self.event_store.append_many(
            (
                Event(
                    session_id=current.session_id,
                    type="mobile.task.succeeded",
                    data={
                        "task_id": task_id,
                        "session_id": current.session_id,
                        "state": TaskState.SUCCEEDED.value,
                        "reason": None,
                        "approval_id": None,
                        "resume_available": False,
                    },
                ),
                Event(
                    session_id=current.session_id,
                    type="mobile.event",
                    data={
                        "task_id": task_id,
                        "session_id": current.session_id,
                        "event_type": "task.completed",
                        "payload": dict(payload),
                    },
                ),
            )
        )
        return self.get(task_id)

    def append_event(
        self,
        task_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> MobileEvent:
        task = self.get(task_id)
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must not be empty")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        event = self.event_store.append(
            Event(
                session_id=task.session_id,
                type="mobile.event",
                data={
                    "task_id": task.task_id,
                    "session_id": task.session_id,
                    "event_type": event_type,
                    "payload": dict(payload),
                },
            )
        )
        return MobileEvent(
            task_id=task.task_id,
            event_type=event_type,
            payload=dict(payload),
            sequence=event.sequence or 0,
            event_id=event.id,
            created_at=event.created_at,
        )

    def events(self, task_id: str, after: int = 0) -> list[MobileEvent]:
        task = self.get(task_id)
        if after < 0:
            raise ValueError("after must be non-negative")
        result: list[MobileEvent] = []
        for event in self.event_store.list_events(task.session_id):
            if event.sequence is None or event.sequence <= after:
                continue
            if event.type == "mobile.task.created" or event.type.startswith("mobile.task."):
                event_type = event.type
                payload = dict(event.data)
            elif event.type == "mobile.event":
                if event.data.get("task_id") != task_id:
                    continue
                event_type = event.data.get("event_type")
                payload = event.data.get("payload")
                if not isinstance(event_type, str) or not isinstance(payload, dict):
                    continue
            else:
                continue
            if event.data.get("task_id") != task_id:
                continue
            result.append(
                MobileEvent(
                    task_id=task_id,
                    event_type=event_type,
                    payload=payload,
                    sequence=event.sequence,
                    event_id=event.id,
                    created_at=event.created_at,
                )
            )
        return result

    def recover_after_restart(self) -> list[MobileTask]:
        recovered: list[MobileTask] = []
        for task in self.list():
            if task.state in _TERMINAL_STATES or task.state is TaskState.INTERRUPTED:
                continue
            recovered.append(
                self.transition(
                    task.task_id,
                    TaskState.INTERRUPTED,
                    reason="runtime restarted",
                    resume_available=True,
                )
            )
        return recovered

    def _rebuild(self) -> dict[str, MobileTask]:
        tasks: dict[str, MobileTask] = {}
        session_ids = {
            session.id
            for session in self.event_store.list_sessions(limit=2_147_483_647)
            if (self.workspace is None or Path(session.workspace).resolve() == self.workspace)
            and (self.session_id is None or session.id == self.session_id)
        }
        for session_id in session_ids:
            for event in self.event_store.list_events(session_id):
                task_id = event.data.get("task_id")
                if not isinstance(task_id, str):
                    continue
                if event.type == "mobile.task.created":
                    prompt = event.data.get("prompt")
                    if not isinstance(prompt, str):
                        continue
                    tasks[task_id] = MobileTask(
                        task_id=task_id,
                        session_id=event.session_id,
                        prompt=prompt,
                        model=event.data.get("model")
                        if isinstance(event.data.get("model"), str)
                        else None,
                        reasoning_effort=event.data.get("reasoning_effort")
                        if isinstance(event.data.get("reasoning_effort"), str)
                        else None,
                        last_sequence=event.sequence or 0,
                        created_at=event.created_at,
                        updated_at=event.created_at,
                        budget_steps=event.data.get("budget_steps")
                        if type(event.data.get("budget_steps")) is int
                        else None,
                        image_refs=parse_mobile_image_refs(event.data.get("image_refs", [])),
                    )
                    continue
                current = tasks.get(task_id)
                if current is None:
                    continue
                if event.type.startswith("mobile.task."):
                    try:
                        task_state = _state(event.data.get("state", event.type.rsplit(".", 1)[-1]))
                    except ValueError:
                        continue
                    tasks[task_id] = replace(
                        current,
                        state=task_state,
                        last_sequence=event.sequence or current.last_sequence,
                        reason=event.data.get("reason")
                        if isinstance(event.data.get("reason"), str)
                        else None,
                        approval_id=event.data.get("approval_id")
                        if isinstance(event.data.get("approval_id"), str)
                        else None,
                        resume_available=bool(event.data.get("resume_available", False)),
                        updated_at=event.created_at,
                    )
                elif event.type == "mobile.event":
                    updates: dict[str, Any] = {}
                    if event.data.get("event_type") == "task.completed":
                        payload = event.data.get("payload", {})
                        try:
                            artifacts = parse_mobile_artifacts(payload.get("artifacts", []))
                            artifact_error = payload.get("artifacts_error")
                        except (TypeError, ValueError):
                            artifacts = ()
                            artifact_error = "Stored artifact metadata is invalid."
                        updates = {
                            "artifacts": artifacts,
                            "artifacts_truncated": bool(payload.get("artifacts_truncated", False)),
                            "artifacts_error": artifact_error
                            if isinstance(artifact_error, str)
                            else None,
                        }
                    tasks[task_id] = replace(
                        current,
                        last_sequence=event.sequence or current.last_sequence,
                        updated_at=event.created_at,
                        **updates,
                    )
        return tasks
