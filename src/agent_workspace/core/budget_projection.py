"""Cost budget projection from session cost averages."""

from __future__ import annotations

from dataclasses import dataclass

from agent_workspace.core.cost import SessionCost


@dataclass(frozen=True, slots=True)
class BudgetProjection:
    remaining_runs: int
    estimated_remaining_cost: float
    estimated_days_remaining: float

    def to_document(self) -> dict[str, float | int]:
        return {
            "remaining_runs": self.remaining_runs,
            "estimated_remaining_cost": self.estimated_remaining_cost,
            "estimated_days_remaining": self.estimated_days_remaining,
        }


def project_budget(
    history: list[SessionCost],
    *,
    max_cost_usd: float,
    average_runs_per_day: float = 1.0,
) -> BudgetProjection:
    if max_cost_usd < 0:
        raise ValueError("max cost must be non-negative")
    if average_runs_per_day <= 0:
        raise ValueError("average runs per day must be positive")
    spent = sum(item.cost_usd for item in history)
    average_cost = (sum(item.cost_usd for item in history) / len(history)) if history else 0.0
    remaining_cost = max(0.0, max_cost_usd - spent)
    if average_cost <= 0:
        return BudgetProjection(0, remaining_cost, 0.0)
    runs = int(remaining_cost // average_cost)
    days = runs / average_runs_per_day if average_runs_per_day > 0 else 0.0
    return BudgetProjection(runs, remaining_cost, days)


__all__ = ["BudgetProjection", "project_budget"]
