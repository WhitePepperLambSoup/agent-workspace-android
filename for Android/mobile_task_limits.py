"""A spending limit per task, its helpers included (Model & reasoning → per-task limit).

A task can be capped by cost (US dollars, at the prices shown on the usage page) and by tokens
(input plus output, cached input included). Spending is counted as the model reports it, for the
task's own conversation and the helpers it started (mobile_subagents); once a limit is passed the
task stops with a message that says which limit it reached, and no helper starts after that. A
model without a known price is held to the token limit only.

Stored as <data>/task-limits.json. Zero means no limit; both are off by default.
"""

from __future__ import annotations

import json
import math
import os
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_workspace.core.budgets import BudgetExceededError

COST_REASON = (
    "Task limit reached (cost): the task stopped. Raise it under Model & reasoning → "
    "Per-task limit, or ask the AI to go on."
)
TOKEN_REASON = (
    "Task limit reached (tokens): the task stopped. Raise it under Model & reasoning → "
    "Per-task limit, or ask the AI to go on."
)
MAX_COST_USD = 1000.0
MAX_TOKENS = 1_000_000_000
_lock = threading.Lock()


class TaskLimitReached(BudgetExceededError):
    """The task's own spending limit (not a provider or hosted limit) was passed."""


def _path() -> Path:
    return Path(os.getenv("AGENT_WORKSPACE_DATA_DIR") or ".") / "task-limits.json"


def get_limits() -> dict[str, Any]:
    """The saved limits, {"max_cost_usd": float, "max_tokens": int}; 0 is no limit. Never raises."""
    try:
        document = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        document = {}
    if not isinstance(document, dict):
        document = {}
    cost = document.get("max_cost_usd")
    tokens = document.get("max_tokens")
    return {
        "max_cost_usd": float(cost)
        if type(cost) in (int, float) and math.isfinite(cost) and 0 <= cost <= MAX_COST_USD
        else 0.0,
        "max_tokens": tokens if type(tokens) is int and 0 <= tokens <= MAX_TOKENS else 0,
    }


def set_limits(changes: Mapping[str, Any]) -> dict[str, Any]:
    unknown = set(changes) - {"max_cost_usd", "max_tokens"}
    if unknown:
        raise ValueError(f"unknown limits: {', '.join(sorted(unknown))}")
    with _lock:
        limits = get_limits()
        if "max_cost_usd" in changes:
            cost = changes["max_cost_usd"]
            cost = 0.0 if cost is None else cost
            if type(cost) not in (int, float) or not math.isfinite(cost) or not 0 <= cost <= MAX_COST_USD:
                raise ValueError(f"max_cost_usd must be a number from 0 to {MAX_COST_USD:g}")
            limits["max_cost_usd"] = float(cost)
        if "max_tokens" in changes:
            tokens = changes["max_tokens"]
            tokens = 0 if tokens is None else tokens
            if type(tokens) is not int or not 0 <= tokens <= MAX_TOKENS:
                raise ValueError(f"max_tokens must be a whole number from 0 to {MAX_TOKENS}")
            limits["max_tokens"] = tokens
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(limits), encoding="utf-8")
        os.replace(temporary, path)
    return limits


@dataclass(slots=True)
class TaskLimits:
    """What one task has spent so far against its limits."""

    max_cost_usd: float
    max_tokens: int
    price: Callable[[str], Mapping[str, Any] | None]
    cost_usd: float = 0.0
    tokens: int = 0
    unpriced_calls: int = 0

    def add(self, model: str, inputs: int, outputs: int, cached: int) -> None:
        if any(type(value) is not int or value < 0 for value in (inputs, outputs, cached)):
            return
        cached = min(cached, inputs)
        self.tokens += inputs + outputs
        pricing = None
        try:
            pricing = self.price(model)
        except Exception:
            pricing = None
        if pricing is None:
            self.unpriced_calls += 1
            return
        self.cost_usd += (
            (inputs - cached) / 1_000_000 * float(pricing["input_usd_per_million"])
            + outputs / 1_000_000 * float(pricing["output_usd_per_million"])
            + cached / 1_000_000 * float(pricing["cached_usd_per_million"])
        )

    def reached(self) -> str | None:
        """The reason to stop, or None while the task is within its limits."""
        if self.max_cost_usd > 0 and self.cost_usd >= self.max_cost_usd:
            return COST_REASON
        if self.max_tokens > 0 and self.tokens >= self.max_tokens:
            return TOKEN_REASON
        return None

    def check(self) -> None:
        reason = self.reached()
        if reason is not None:
            raise TaskLimitReached(reason)

    def snapshot(self) -> dict[str, Any]:
        return {
            "max_cost_usd": self.max_cost_usd,
            "max_tokens": self.max_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "tokens": self.tokens,
            "unpriced_calls": self.unpriced_calls,
        }


def limits_for_task(price: Callable[[str], Mapping[str, Any] | None]) -> TaskLimits | None:
    """A tracker for a new task, or None when no limit is set."""
    limits = get_limits()
    if not limits["max_cost_usd"] and not limits["max_tokens"]:
        return None
    return TaskLimits(limits["max_cost_usd"], limits["max_tokens"], price)


__all__ = [
    "COST_REASON",
    "TOKEN_REASON",
    "TaskLimitReached",
    "TaskLimits",
    "get_limits",
    "limits_for_task",
    "set_limits",
]
