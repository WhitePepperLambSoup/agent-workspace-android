"""Onboarding checklist data.

Declares the ordered first-run checklist and persists per-user progress.
Completion is computed from required steps only; optional steps affect the
displayed progress fraction but never block the ``ready`` flag.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class OnboardingChecklistError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OnboardingStep:
    id: str
    title: str
    category: str
    required: bool = False
    order: int = 0

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "required": self.required,
            "order": self.order,
        }


@dataclass(frozen=True, slots=True)
class OnboardingChecklist:
    steps: tuple[OnboardingStep, ...]

    def __post_init__(self) -> None:
        ids = [step.id for step in self.steps]
        if not ids or len(ids) != len(set(ids)):
            raise OnboardingChecklistError("onboarding checklist steps must have unique ids")
        if any(
            not step.id or not step.title.strip() or not step.category.strip()
            for step in self.steps
        ):
            raise OnboardingChecklistError("onboarding step fields may not be empty")

    @property
    def required_steps(self) -> tuple[OnboardingStep, ...]:
        return tuple(step for step in self.steps if step.required)

    def ordered(self) -> tuple[OnboardingStep, ...]:
        return tuple(sorted(self.steps, key=lambda step: (step.order, step.id)))

    def step_by_id(self, step_id: str) -> OnboardingStep | None:
        return next((step for step in self.steps if step.id == step_id), None)

    def to_document(self) -> dict[str, Any]:
        return {"steps": [step.to_document() for step in self.ordered()]}


@dataclass(frozen=True, slots=True)
class OnboardingProgress:
    user: str
    completed: frozenset[str]
    completed_required: int
    total_required: int
    optional_completed: int
    optional_total: int
    ready: bool

    def to_document(self) -> dict[str, Any]:
        return {
            "user": self.user,
            "completed": sorted(self.completed),
            "completed_required": self.completed_required,
            "total_required": self.total_required,
            "optional_completed": self.optional_completed,
            "optional_total": self.optional_total,
            "ready": self.ready,
        }


def build_default_checklist() -> OnboardingChecklist:
    """The built-in first-run checklist for a workspace."""
    steps = (
        OnboardingStep("workspace_create", "Create the workspace", "workspace", True, 10),
        OnboardingStep("provider_configure", "Configure a model provider", "provider", True, 20),
        OnboardingStep("api_key_store", "Store a credential", "security", True, 30),
        OnboardingStep("tool_review", "Review available tools", "workspace", False, 40),
        OnboardingStep("desktop_shortcut", "Create a desktop shortcut", "desktop", False, 50),
        OnboardingStep("backup_schedule", "Schedule a backup", "security", False, 60),
    )
    return OnboardingChecklist(steps)


class OnboardingProgressStore:
    """Persist completed step ids per user as one JSON document."""

    def __init__(self, path: str | Path, *, clock: Any = time.time) -> None:
        self.path = Path(path)
        self._clock = clock
        self._completed: dict[str, dict[str, float]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OnboardingChecklistError(f"cannot read onboarding progress: {exc}") from exc
        raw_progress = document.get("progress") if isinstance(document, dict) else None
        if not isinstance(raw_progress, dict):
            raise OnboardingChecklistError("onboarding progress must declare a progress object")
        for user, raw_steps in raw_progress.items():
            if not isinstance(user, str) or not isinstance(raw_steps, dict):
                raise OnboardingChecklistError("onboarding progress entry is invalid")
            completed: dict[str, float] = {}
            for step_id, raw_timestamp in raw_steps.items():
                try:
                    completed[str(step_id)] = float(raw_timestamp)
                except (TypeError, ValueError) as exc:
                    raise OnboardingChecklistError(
                        "onboarding progress timestamp is invalid"
                    ) from exc
            self._completed[user] = completed

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps({"progress": self._completed}, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, self.path)

    def complete(self, user: str, step_id: str) -> float:
        if not user or not step_id:
            raise OnboardingChecklistError("onboarding user and step id may not be empty")
        timestamp = float(self._clock())
        self._completed.setdefault(user, {})[step_id] = timestamp
        self.save()
        return timestamp

    def completed_steps(self, user: str) -> frozenset[str]:
        return frozenset(self._completed.get(user, {}))

    def progress(
        self, user: str, checklist: OnboardingChecklist | None = None
    ) -> OnboardingProgress:
        checklist = checklist or build_default_checklist()
        completed = self.completed_steps(user)
        unknown = sorted(completed - {step.id for step in checklist.steps})
        if unknown:
            raise OnboardingChecklistError(
                f"onboarding progress references unknown steps: {unknown}"
            )
        required = {step.id for step in checklist.steps if step.required}
        optional = {step.id for step in checklist.steps if not step.required}
        completed_required = len(required & completed)
        return OnboardingProgress(
            user=user,
            completed=completed,
            completed_required=completed_required,
            total_required=len(required),
            optional_completed=len(optional & completed),
            optional_total=len(optional),
            ready=completed_required == len(required),
        )


__all__ = [
    "OnboardingChecklist",
    "OnboardingChecklistError",
    "OnboardingProgress",
    "OnboardingProgressStore",
    "OnboardingStep",
    "build_default_checklist",
]
