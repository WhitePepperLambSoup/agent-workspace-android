"""Server graceful shutdown budget planner.

Distributes a fixed shutdown budget across ordered drain steps (stop accepting
requests, drain webhooks, flush writes, close websockets, ...) by declared
weights and computes the remaining budget for each completed step. The module
is pure policy/data logic; callers own the actual async shutdown work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_MIN_STEP_SECONDS = 0.05


class ShutdownBudgetError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ShutdownStep:
    name: str
    weight: float
    budget_seconds: float

    def to_document(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "weight": self.weight,
            "budget_seconds": round(self.budget_seconds, 3),
        }


@dataclass(frozen=True, slots=True)
class ShutdownPlan:
    total_budget_seconds: float
    reserve_seconds: float
    steps: tuple[ShutdownStep, ...]

    @property
    def drain_budget_seconds(self) -> float:
        return max(0.0, self.total_budget_seconds - self.reserve_seconds)

    def step_by_name(self, name: str) -> ShutdownStep | None:
        return next((step for step in self.steps if step.name == name), None)

    def budget_after(self, completed_steps: set[str] | frozenset[str]) -> float:
        """Remaining budget assuming ``completed_steps`` finished exactly on time."""
        consumed = sum(step.budget_seconds for step in self.steps if step.name in completed_steps)
        return max(0.0, self.total_budget_seconds - consumed)

    def to_document(self) -> dict[str, Any]:
        return {
            "total_budget_seconds": self.total_budget_seconds,
            "reserve_seconds": self.reserve_seconds,
            "drain_budget_seconds": round(self.drain_budget_seconds, 3),
            "steps": [step.to_document() for step in self.steps],
        }


def plan_shutdown_steps(
    steps: list[tuple[str, float]] | tuple[tuple[str, float], ...],
    *,
    total_budget_seconds: float = 30.0,
    reserve_seconds: float = 0.5,
) -> ShutdownPlan:
    """Allocate ``total_budget_seconds`` across weighted shutdown steps.

    Weights must be positive and step names must be unique. The reserve is
    kept outside the drain allocation and is not distributed to any step.
    """
    if total_budget_seconds <= 0 or reserve_seconds < 0:
        raise ShutdownBudgetError("shutdown budget must be positive and reserve non-negative")
    if reserve_seconds >= total_budget_seconds:
        raise ShutdownBudgetError("shutdown reserve must be smaller than the total budget")
    if not steps:
        raise ShutdownBudgetError("shutdown plan requires at least one step")
    names = [name for name, _ in steps]
    if len(names) != len(set(names)):
        raise ShutdownBudgetError("shutdown step names must be unique")
    if any(not name.strip() for name in names):
        raise ShutdownBudgetError("shutdown step names may not be empty")
    if any(weight <= 0 for _, weight in steps):
        raise ShutdownBudgetError("shutdown step weights must be positive")
    drain_budget = total_budget_seconds - reserve_seconds
    total_weight = sum(weight for _, weight in steps)
    budgets = [max(_MIN_STEP_SECONDS, drain_budget * weight / total_weight) for _, weight in steps]
    overage = sum(budgets) - drain_budget
    while overage > 1e-9:
        reducible = [
            index for index, budget in enumerate(budgets) if budget > _MIN_STEP_SECONDS + 1e-9
        ]
        if not reducible:
            raise ShutdownBudgetError(
                "shutdown budget is too small for the requested number of steps"
            )
        reduction = overage / len(reducible)
        for index in reducible:
            actual_reduction = min(budgets[index] - _MIN_STEP_SECONDS, reduction)
            budgets[index] -= actual_reduction
            overage -= actual_reduction
    planned = [
        ShutdownStep(name, weight, budget)
        for (name, weight), budget in zip(steps, budgets, strict=True)
    ]
    return ShutdownPlan(total_budget_seconds, reserve_seconds, tuple(planned))


__all__ = [
    "ShutdownBudgetError",
    "ShutdownPlan",
    "ShutdownStep",
    "plan_shutdown_steps",
]
