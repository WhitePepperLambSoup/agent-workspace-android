"""Models by purpose: a cheaper model of the same provider for phone control, for summarizing
long conversations and for helpers (mobile_subagents), while ordinary conversations keep the main
model. Helpers also have a thinking effort of their own.

Stored as <data>/model-roles.json. An empty role uses the main model, an empty effort the effort of
the task that started the helpers. A model the user picks for one task (the panel's model picker,
the chat's model sheet) always wins over a role.
"""

from __future__ import annotations

import json
import os
import re
import threading
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from mobile_protocol import REASONING_EFFORTS

ROLES = ("phone", "summary", "subagent")
# Roles with a thinking effort of their own.
EFFORT_ROLES = ("subagent",)
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$")
_lock = threading.Lock()


def _path() -> Path:
    return Path(os.getenv("AGENT_WORKSPACE_DATA_DIR") or ".") / "model-roles.json"


def _document() -> dict[str, Any]:
    try:
        document = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return document if isinstance(document, dict) else {}


def _effort(value: Any) -> str:
    return value if isinstance(value, str) and value in REASONING_EFFORTS else ""


def get_roles() -> dict[str, str]:
    """The saved roles, each a model name or "" (use the main model). Never raises."""
    document = _document()
    return {
        role: value if isinstance(value := document.get(role), str) and _MODEL.match(value) else ""
        for role in ROLES
    }


def get_efforts() -> dict[str, str]:
    """The saved thinking efforts by role, each an effort or "" (the task's own). Never raises."""
    saved = _document().get("efforts")
    saved = saved if isinstance(saved, dict) else {}
    return {role: _effort(saved.get(role)) for role in EFFORT_ROLES}


def set_roles(
    changes: dict[str, Any],
    efforts: dict[str, Any] | None = None,
    *,
    supported: Callable[[str], Iterable[str]] | None = None,
) -> dict[str, str]:
    """Saves the roles given ("" or null clears one) and the efforts given ("" or null: the task's
    own); refuses names that cannot be model ids, and an effort the role's model does not offer
    (``supported`` gives a model's efforts, "" standing for the main model)."""
    efforts = efforts or {}
    unknown = set(changes) - set(ROLES)
    if unknown:
        raise ValueError(f"unknown model roles: {', '.join(sorted(unknown))}")
    unknown = set(efforts) - set(EFFORT_ROLES)
    if unknown:
        raise ValueError(f"unknown effort roles: {', '.join(sorted(unknown))}")
    with _lock:
        roles = get_roles()
        chosen = get_efforts()
        for role, value in changes.items():
            value = "" if value is None else str(value).strip()
            if value and not _MODEL.match(value):
                raise ValueError(f"{role}: not a model name")
            roles[role] = value
        for role, value in efforts.items():
            value = "" if value is None else str(value).strip()
            if value and not _effort(value):
                raise ValueError(f"{role}: not a thinking effort")
            chosen[role] = value
        if supported is not None:
            for role, value in chosen.items():
                if value and value != "auto" and value not in tuple(supported(roles[role])):
                    raise ValueError("the sub-task model does not offer this thinking effort")
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({**roles, "efforts": chosen}, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
    return roles


def model_for_task(
    *, requested: str | None, default: str | None, phone_control: bool, local: bool
) -> str | None:
    """The model a task runs on: what was picked for it when that differs from the main model,
    else the phone-control role for phone tasks, else the main model. An on-device model has no
    other models to pick from."""
    if local or (requested and requested != default):
        return requested or default
    if phone_control:
        role = get_roles()["phone"]
        if role:
            return role
    return requested or default


def summary_model(*, local: bool) -> str | None:
    """The model that summarizes dropped history, or None for the task's own model."""
    return None if local else (get_roles()["summary"] or None)


def subagent_model(*, task_model: str, local: bool) -> str:
    """The model helpers run on: the helper role, else the task's own model."""
    return task_model if local else (get_roles()["subagent"] or task_model)


def subagent_effort(
    *,
    task_effort: str,
    helper_model: str,
    supported: Callable[[str], Iterable[str]] | None,
    local: bool,
) -> str:
    """How hard helpers think: their own effort, else the task's, as long as the helpers' model
    offers it (else automatic: a cheaper helper model often has no effort levels). An on-device
    model keeps the task's."""
    if local:
        return task_effort
    effort = get_efforts()["subagent"] or task_effort
    if effort == "auto" or supported is None or effort in tuple(supported(helper_model)):
        return effort
    return "auto"
