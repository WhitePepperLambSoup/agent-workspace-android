"""Models by purpose: a cheaper model of the same provider for phone control and for summarizing
long conversations, while ordinary conversations keep the main model.

Stored as <data>/model-roles.json. An empty role uses the main model. A model the user picks for
one task (the panel's model picker, the chat's model sheet) always wins over a role.
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

ROLES = ("phone", "summary")
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$")
_lock = threading.Lock()


def _path() -> Path:
    return Path(os.getenv("AGENT_WORKSPACE_DATA_DIR") or ".") / "model-roles.json"


def get_roles() -> dict[str, str]:
    """The saved roles, each a model name or "" (use the main model). Never raises."""
    try:
        document = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        document = {}
    if not isinstance(document, dict):
        document = {}
    return {
        role: value if isinstance(value := document.get(role), str) and _MODEL.match(value) else ""
        for role in ROLES
    }


def set_roles(changes: dict[str, Any]) -> dict[str, str]:
    """Saves the roles given ("" or null clears one); refuses names that cannot be model ids."""
    unknown = set(changes) - set(ROLES)
    if unknown:
        raise ValueError(f"unknown model roles: {', '.join(sorted(unknown))}")
    with _lock:
        roles = get_roles()
        for role, value in changes.items():
            value = "" if value is None else str(value).strip()
            if value and not _MODEL.match(value):
                raise ValueError(f"{role}: not a model name")
            roles[role] = value
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(roles, ensure_ascii=False), encoding="utf-8")
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
