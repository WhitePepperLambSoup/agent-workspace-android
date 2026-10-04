"""Durable goal/plan projection over the append-only event log.

Goals and steps are domain events; their current state is derived by replaying
session events, matching the storage layer's projection pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from agent_workspace.application.ports import EventStore
from agent_workspace.core.events import Event


class GoalStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StepStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class Goal:
    id: str
    session_id: str
    title: str
    status: GoalStatus = GoalStatus.ACTIVE
    created_at: str = ""
    updated_at: str = ""

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "title": self.title,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class PlanStep:
    id: str
    goal_id: str
    title: str
    status: StepStatus = StepStatus.PENDING
    position: int = 0
    parent_step_id: str | None = None
    updated_at: str = ""

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal_id": self.goal_id,
            "title": self.title,
            "status": self.status.value,
            "position": self.position,
            "parent_step_id": self.parent_step_id,
            "updated_at": self.updated_at,
        }


class PlanError(ValueError):
    pass


class PlanManager:
    """Create and update durable goals and hierarchical plan steps."""

    def __init__(self, store: EventStore) -> None:
        self._store = store

    async def create_goal(self, session_id: str, goal_id: str, title: str) -> Goal:
        self._validate_id(session_id, "session")
        self._validate_id(goal_id, "goal")
        title = self._validate_title(title)
        now = datetime.now(UTC).isoformat()
        self._store.append(
            Event(
                session_id=session_id,
                type="goal.created",
                data={"goal_id": goal_id, "title": title, "created_at": now},
            )
        )
        return Goal(goal_id, session_id, title, GoalStatus.ACTIVE, now, now)

    async def update_goal(self, session_id: str, goal_id: str, status: GoalStatus) -> Goal:
        goals = self.list_goals(session_id)
        goal = next((item for item in goals if item.id == goal_id), None)
        if goal is None:
            raise PlanError(f"unknown goal: {goal_id}")
        now = datetime.now(UTC).isoformat()
        self._store.append(
            Event(
                session_id=session_id,
                type="goal.updated",
                data={"goal_id": goal_id, "status": status.value, "updated_at": now},
            )
        )
        return Goal(goal.id, goal.session_id, goal.title, status, goal.created_at, now)

    async def upsert_step(
        self,
        session_id: str,
        step_id: str,
        goal_id: str,
        title: str,
        *,
        status: StepStatus = StepStatus.PENDING,
        position: int = 0,
        parent_step_id: str | None = None,
    ) -> PlanStep:
        self._validate_id(session_id, "session")
        self._validate_id(step_id, "step")
        self._validate_id(goal_id, "goal")
        title = self._validate_title(title)
        if position < 0:
            raise PlanError("step position must be non-negative")
        if parent_step_id is not None:
            self._validate_id(parent_step_id, "parent step")
        if parent_step_id == step_id:
            raise PlanError("step may not be its own parent")
        now = datetime.now(UTC).isoformat()
        self._store.append(
            Event(
                session_id=session_id,
                type="plan.step.upserted",
                data={
                    "step_id": step_id,
                    "goal_id": goal_id,
                    "title": title,
                    "status": status.value,
                    "position": position,
                    "parent_step_id": parent_step_id,
                    "updated_at": now,
                },
            )
        )
        return PlanStep(step_id, goal_id, title, status, position, parent_step_id, now)

    def list_goals(self, session_id: str) -> list[Goal]:
        events = self._store.list_events(session_id)
        goals: dict[str, dict[str, Any]] = {}
        for event in events:
            if event.type == "goal.created":
                data = event.data
                if _goal_payload(data):
                    goals[data["goal_id"]] = {
                        "goal_id": data["goal_id"],
                        "session_id": event.session_id,
                        "title": data["title"],
                        "status": GoalStatus.ACTIVE,
                        "created_at": data["created_at"],
                        "updated_at": data["created_at"],
                    }
            elif event.type == "goal.updated":
                data = event.data
                goal_id = data.get("goal_id")
                if (
                    isinstance(goal_id, str)
                    and goal_id in goals
                    and isinstance(data.get("status"), str)
                    and isinstance(data.get("updated_at"), str)
                ):
                    try:
                        goals[goal_id]["status"] = GoalStatus(data["status"])
                    except ValueError:
                        continue
                    goals[goal_id]["updated_at"] = data["updated_at"]
        return [
            Goal(
                id=item["goal_id"],
                session_id=item["session_id"],
                title=item["title"],
                status=item["status"],
                created_at=item["created_at"],
                updated_at=item["updated_at"],
            )
            for item in goals.values()
        ]

    def list_steps(self, session_id: str, goal_id: str | None = None) -> list[PlanStep]:
        events = self._store.list_events(session_id)
        steps: dict[str, dict[str, Any]] = {}
        for event in events:
            if event.type != "plan.step.upserted":
                continue
            data = event.data
            if not _step_payload(data):
                continue
            if goal_id is not None and data["goal_id"] != goal_id:
                continue
            steps[data["step_id"]] = {
                "step_id": data["step_id"],
                "goal_id": data["goal_id"],
                "title": data["title"],
                "status": StepStatus(data["status"]),
                "position": data["position"],
                "parent_step_id": data["parent_step_id"],
                "updated_at": data["updated_at"],
            }
        return [
            PlanStep(
                id=item["step_id"],
                goal_id=item["goal_id"],
                title=item["title"],
                status=item["status"],
                position=item["position"],
                parent_step_id=item["parent_step_id"],
                updated_at=item["updated_at"],
            )
            for item in steps.values()
        ]

    @staticmethod
    def _validate_id(value: str, label: str) -> None:
        if not isinstance(value, str) or not value or len(value) > 128:
            raise PlanError(f"{label} id must be 1-128 characters")

    @staticmethod
    def _validate_title(value: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 10_000:
            raise PlanError("plan title must be 1-10000 characters")
        return value.strip()


def _goal_payload(data: dict[str, Any]) -> bool:
    return (
        isinstance(data.get("goal_id"), str)
        and bool(data.get("goal_id"))
        and isinstance(data.get("title"), str)
        and bool(data.get("title"))
        and isinstance(data.get("created_at"), str)
    )


def _step_payload(data: dict[str, Any]) -> bool:
    position = data.get("position")
    parent = data.get("parent_step_id")
    return (
        isinstance(data.get("step_id"), str)
        and bool(data.get("step_id"))
        and isinstance(data.get("goal_id"), str)
        and bool(data.get("goal_id"))
        and isinstance(data.get("title"), str)
        and bool(data.get("title"))
        and isinstance(data.get("status"), str)
        and data["status"] in {item.value for item in StepStatus}
        and type(position) is int
        and position >= 0
        and (parent is None or isinstance(parent, str))
        and isinstance(data.get("updated_at"), str)
    )


__all__ = [
    "Goal",
    "GoalStatus",
    "PlanError",
    "PlanManager",
    "PlanStep",
    "StepStatus",
]
