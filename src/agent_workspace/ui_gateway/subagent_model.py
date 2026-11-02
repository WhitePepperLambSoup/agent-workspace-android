"""Which model sub-agents run on and how hard they think: one choice for every conversation.

Sub-agents are the agent runs a conversation starts with delegate_tasks, an expert team's experts
among them. Stored as subagent-model.json beside the gateway database. What is left unset follows
the conversation: its model, and the thinking effort of the turn that handed out the work. An
effort the sub-agents' model does not offer is left to the model's default.
"""

from __future__ import annotations

import json
import os
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

EFFORTS = frozenset({"off", "low", "medium", "high", "xhigh", "max"})


@dataclass(frozen=True, slots=True)
class SubagentModel:
    # A saved provider profile, or None for the conversation's own.
    provider_id: str | None = None
    # Another model on that profile's provider, or None for the profile's model.
    model: str | None = None
    # A thinking effort, or None for the effort of the turn that delegated.
    effort: str | None = None


def load(path: Path) -> SubagentModel:
    """The saved choice, or one that follows the conversation in everything. Never raises."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return SubagentModel()
    if not isinstance(document, dict):
        return SubagentModel()
    provider_id = document.get("providerId")
    model = document.get("model")
    effort = document.get("effort")
    if not isinstance(provider_id, str) or not provider_id:
        provider_id = None
    return SubagentModel(
        provider_id,
        model if provider_id is not None and isinstance(model, str) and model else None,
        effort if effort in EFFORTS else None,
    )


def save(path: Path, choice: SubagentModel) -> None:
    staging = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        staging.write_text(
            json.dumps(
                {"providerId": choice.provider_id, "model": choice.model, "effort": choice.effort}
            ),
            encoding="utf-8",
        )
        os.replace(staging, path)
    finally:
        staging.unlink(missing_ok=True)


def effort_for(
    choice: SubagentModel, delegating: str | None, supported: Collection[str]
) -> str | None:
    """The effort a sub-agent's turns ask for: the chosen one, else the delegating turn's, as long
    as the sub-agents' model offers it. None leaves it to the model."""
    effort = choice.effort or delegating
    return effort if effort is not None and effort in supported else None


__all__ = ["EFFORTS", "SubagentModel", "effort_for", "load", "save"]
