"""Durable pipeline state machine projected from session events.

Pipelines are deterministic: dependencies block a step until they complete,
retries are explicit event transitions, and a failure without retries moves
the pipeline to ``failed``. Compensation steps are recorded as ordinary steps
and can be executed by callers when the pipeline fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from agent_workspace.application.ports import EventStore
from agent_workspace.core.events import Event
from agent_workspace.core.models import Autonomy, Mode
from agent_workspace.core.session import Session


class PipelineStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PipelineStep:
    id: str
    name: str
    depends_on: tuple[str, ...] = ()
    max_retries: int = 0
    compensation: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.name:
            raise PipelineError("pipeline step id and name may not be empty")
        if self.max_retries < 0:
            raise PipelineError("pipeline step max_retries must be non-negative")
        if self.id in self.depends_on:
            raise PipelineError("pipeline step may not depend on itself")


@dataclass(frozen=True, slots=True)
class PipelineDefinition:
    id: str
    name: str
    steps: tuple[PipelineStep, ...]

    def __post_init__(self) -> None:
        if not self.id or not self.name:
            raise PipelineError("pipeline id and name may not be empty")
        if not self.steps:
            raise PipelineError("pipeline needs at least one step")
        ids = [step.id for step in self.steps]
        if len(set(ids)) != len(ids):
            raise PipelineError("pipeline step ids must be unique")
        known = set(ids)
        for step in self.steps:
            missing = [step_id for step_id in step.depends_on if step_id not in known]
            if missing:
                raise PipelineError(
                    f"pipeline step {step.id!r} depends on unknown steps: {', '.join(missing)}"
                )


@dataclass(frozen=True, slots=True)
class PipelineState:
    definition: PipelineDefinition
    status: PipelineStatus
    steps: dict[str, PipelineStepStatus]
    retries_used: dict[str, int]

    def ready_steps(self) -> tuple[str, ...]:
        if self.status not in {PipelineStatus.PENDING, PipelineStatus.RUNNING}:
            return ()
        return tuple(
            step.id
            for step in self.definition.steps
            if self.steps[step.id] is PipelineStepStatus.PENDING
            and all(
                self.steps[dependency] is PipelineStepStatus.COMPLETED
                for dependency in step.depends_on
            )
        )


class PipelineManager:
    """Event-sourced pipeline execution state."""

    def __init__(self, store: EventStore, *, pipeline_session_id: str = "pipelines") -> None:
        self._store = store
        self.pipeline_session_id = pipeline_session_id
        if self._store.get_session(self.pipeline_session_id) is None:
            self._store.create_session(
                Session(
                    ".",
                    mode=Mode.TASK,
                    autonomy=Autonomy.WORKSPACE,
                    id=self.pipeline_session_id,
                    title="Durable pipelines",
                )
            )

    async def create(self, definition: PipelineDefinition) -> PipelineState:
        if self.get(definition.id) is not None:
            raise PipelineError(f"pipeline already exists: {definition.id}")
        now = datetime.now(UTC).isoformat()
        self._store.append(
            Event(
                session_id=self.pipeline_session_id,
                type="pipeline.created",
                data={
                    "pipeline_id": definition.id,
                    "name": definition.name,
                    "steps": [
                        {
                            "id": step.id,
                            "name": step.name,
                            "depends_on": list(step.depends_on),
                            "max_retries": step.max_retries,
                            "compensation": step.compensation,
                        }
                        for step in definition.steps
                    ],
                    "created_at": now,
                },
            )
        )
        return self.get(definition.id) or self._initial_state(definition, now)

    async def start(self, pipeline_id: str) -> PipelineState:
        state = self._required_state(pipeline_id)
        if state.status is not PipelineStatus.PENDING:
            raise PipelineError(f"pipeline is not pending: {pipeline_id}")
        self._store.append(
            Event(
                session_id=self.pipeline_session_id,
                type="pipeline.started",
                data={"pipeline_id": pipeline_id, "updated_at": datetime.now(UTC).isoformat()},
            )
        )
        return self._required_state(pipeline_id)

    async def start_step(self, pipeline_id: str, step_id: str) -> PipelineState:
        state = self._required_state(pipeline_id)
        _step(state.definition, step_id)
        if step_id not in state.ready_steps():
            raise PipelineError(f"pipeline step is not ready: {step_id}")
        self._store.append(
            Event(
                session_id=self.pipeline_session_id,
                type="pipeline.step.started",
                data={"pipeline_id": pipeline_id, "step_id": step_id},
            )
        )
        if state.status is PipelineStatus.PENDING:
            await self.start(pipeline_id)
        return self._required_state(pipeline_id)

    async def complete_step(self, pipeline_id: str, step_id: str) -> PipelineState:
        state = self._required_state(pipeline_id)
        if state.steps.get(step_id) is not PipelineStepStatus.RUNNING:
            raise PipelineError(f"pipeline step is not running: {step_id}")
        self._store.append(
            Event(
                session_id=self.pipeline_session_id,
                type="pipeline.step.completed",
                data={"pipeline_id": pipeline_id, "step_id": step_id},
            )
        )
        updated = self._required_state(pipeline_id)
        if all(
            updated.steps[step.id] is PipelineStepStatus.COMPLETED
            for step in updated.definition.steps
        ):
            self._store.append(
                Event(
                    session_id=self.pipeline_session_id,
                    type="pipeline.completed",
                    data={"pipeline_id": pipeline_id},
                )
            )
        return self._required_state(pipeline_id)

    async def fail_step(self, pipeline_id: str, step_id: str, error: str) -> PipelineState:
        state = self._required_state(pipeline_id)
        if state.steps.get(step_id) is not PipelineStepStatus.RUNNING:
            raise PipelineError(f"pipeline step is not running: {step_id}")
        step = _step(state.definition, step_id)
        used = state.retries_used[step_id]
        if used < step.max_retries:
            self._store.append(
                Event(
                    session_id=self.pipeline_session_id,
                    type="pipeline.step.retrying",
                    data={
                        "pipeline_id": pipeline_id,
                        "step_id": step_id,
                        "error": error[:2000],
                        "retry": used + 1,
                    },
                )
            )
        else:
            self._store.append(
                Event(
                    session_id=self.pipeline_session_id,
                    type="pipeline.failed",
                    data={"pipeline_id": pipeline_id, "step_id": step_id, "error": error[:2000]},
                )
            )
        return self._required_state(pipeline_id)

    def get(self, pipeline_id: str) -> PipelineState | None:
        states = self.list()
        return {state.definition.id: state for state in states}.get(pipeline_id)

    def list(self) -> list[PipelineState]:
        events = self._store.list_events(self.pipeline_session_id)
        definitions: dict[str, dict[str, Any]] = {}
        statuses: dict[str, PipelineStatus] = {}
        step_statuses: dict[str, dict[str, PipelineStepStatus]] = {}
        retries: dict[str, dict[str, int]] = {}
        for event in events:
            data = event.data
            pipeline_id = data.get("pipeline_id")
            if not isinstance(pipeline_id, str):
                continue
            if event.type == "pipeline.created":
                definition = _definition_from_data(data)
                if definition is not None:
                    definitions[pipeline_id] = {
                        "definition": definition,
                        "created_at": str(data.get("created_at", "")),
                    }
                    statuses[pipeline_id] = PipelineStatus.PENDING
                    step_statuses[pipeline_id] = {
                        step.id: PipelineStepStatus.PENDING for step in definition.steps
                    }
                    retries[pipeline_id] = {step.id: 0 for step in definition.steps}
            elif pipeline_id not in definitions:
                continue
            elif event.type == "pipeline.started":
                statuses[pipeline_id] = PipelineStatus.RUNNING
            elif event.type == "pipeline.step.started":
                step_id = data.get("step_id")
                if isinstance(step_id, str) and step_id in step_statuses[pipeline_id]:
                    step_statuses[pipeline_id][step_id] = PipelineStepStatus.RUNNING
            elif event.type == "pipeline.step.retrying":
                step_id = data.get("step_id")
                if isinstance(step_id, str) and step_id in step_statuses[pipeline_id]:
                    step_statuses[pipeline_id][step_id] = PipelineStepStatus.PENDING
                    retries[pipeline_id][step_id] += 1
            elif event.type == "pipeline.step.completed":
                step_id = data.get("step_id")
                if isinstance(step_id, str) and step_id in step_statuses[pipeline_id]:
                    step_statuses[pipeline_id][step_id] = PipelineStepStatus.COMPLETED
            elif event.type == "pipeline.completed":
                statuses[pipeline_id] = PipelineStatus.COMPLETED
            elif event.type == "pipeline.failed":
                statuses[pipeline_id] = PipelineStatus.FAILED
                step_id = data.get("step_id")
                if isinstance(step_id, str) and step_id in step_statuses[pipeline_id]:
                    step_statuses[pipeline_id][step_id] = PipelineStepStatus.FAILED
        return [
            PipelineState(
                definition=item["definition"],
                status=statuses[pipeline_id],
                steps=step_statuses[pipeline_id],
                retries_used=retries[pipeline_id],
            )
            for pipeline_id, item in definitions.items()
        ]

    def _required_state(self, pipeline_id: str) -> PipelineState:
        state = self.get(pipeline_id)
        if state is None:
            raise PipelineError(f"unknown pipeline: {pipeline_id}")
        return state

    @staticmethod
    def _initial_state(definition: PipelineDefinition, created_at: str) -> PipelineState:
        return PipelineState(
            definition=definition,
            status=PipelineStatus.PENDING,
            steps={step.id: PipelineStepStatus.PENDING for step in definition.steps},
            retries_used={step.id: 0 for step in definition.steps},
        )


def _step(definition: PipelineDefinition, step_id: str) -> PipelineStep:
    for step in definition.steps:
        if step.id == step_id:
            return step
    raise PipelineError(f"unknown pipeline step: {step_id}")


def _definition_from_data(data: dict[str, Any]) -> PipelineDefinition | None:
    pipeline_id = data.get("pipeline_id")
    name = data.get("name")
    raw_steps = data.get("steps")
    if (
        not isinstance(pipeline_id, str)
        or not isinstance(name, str)
        or not isinstance(raw_steps, list)
    ):
        return None
    steps: list[PipelineStep] = []
    for raw in raw_steps:
        if not isinstance(raw, dict):
            return None
        try:
            steps.append(
                PipelineStep(
                    id=str(raw["id"]),
                    name=str(raw["name"]),
                    depends_on=tuple(str(item) for item in raw.get("depends_on", ())),
                    max_retries=int(raw.get("max_retries", 0)),
                    compensation=(
                        str(raw["compensation"]) if raw.get("compensation") is not None else None
                    ),
                )
            )
        except (KeyError, TypeError, ValueError):
            return None
    try:
        return PipelineDefinition(pipeline_id, name, tuple(steps))
    except PipelineError:
        return None


__all__ = [
    "PipelineDefinition",
    "PipelineError",
    "PipelineManager",
    "PipelineState",
    "PipelineStatus",
    "PipelineStep",
    "PipelineStepStatus",
]
