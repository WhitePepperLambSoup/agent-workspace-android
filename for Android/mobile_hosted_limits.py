"""Limits for phone tasks that run without asking: hosted mode in the phone control window,
schedules, triggers and other tasks approved in advance. When one is used up the task stops and
says which (the user reads what was done and can continue). Stored in <data>/hosted-limits.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agent_workspace.core.budgets import TaskBudget

DEFAULTS = {"max_steps": 60, "max_minutes": 20}
RANGES = {"max_steps": (5, 300), "max_minutes": (1, 240)}
# The reasons a stopped task gives (the console's i18n.js translates them word for word).
STEPS_REASON = ("Hosted limit reached (steps): the task stopped. Raise it under Device & tools → "
                "Hosted limits, or ask the AI to go on.")
TIME_REASON = ("Hosted limit reached (time): the task stopped. Raise it under Device & tools → "
               "Hosted limits, or ask the AI to go on.")


def _path() -> Path:
    return Path(os.getenv("AGENT_WORKSPACE_DATA_DIR") or ".") / "hosted-limits.json"


def get() -> dict[str, int]:
    try:
        saved = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    limits = dict(DEFAULTS)
    for key, (low, high) in RANGES.items():
        value = saved.get(key) if isinstance(saved, dict) else None
        if type(value) is int and low <= value <= high:
            limits[key] = value
    return limits


def set_limits(payload: Any) -> dict[str, int]:
    if not isinstance(payload, dict) or set(payload) - set(RANGES):
        raise ValueError("hosted limits take max_steps and max_minutes")
    limits = get()
    for key, value in payload.items():
        low, high = RANGES[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{key} must be a whole number from {low} to {high}")
        limits[key] = value
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(limits), encoding="utf-8")
    os.replace(temporary, path)
    return limits


def budget() -> TaskBudget:
    """The budget of an unattended phone task: each step is a model call and a tool call."""
    limits = get()
    steps = limits["max_steps"]
    return TaskBudget(
        max_tool_calls=steps,
        max_model_calls=steps + 5,
        max_provider_attempts=2 * steps + 10,
        max_turn_seconds=float(limits["max_minutes"] * 60),
    )


def reason(error: BaseException) -> str | None:
    """What a stopped unattended phone task says when one of these limits stopped it, else None.
    The time limit ends the turn with TimeoutError; the step limits with BudgetExceededError."""
    from agent_workspace.core.budgets import BudgetExceededError

    if isinstance(error, TimeoutError):
        return TIME_REASON
    if isinstance(error, BudgetExceededError) and any(
        word in str(error) for word in ("model call", "tool call", "provider attempt")
    ):
        return STEPS_REASON
    return None
