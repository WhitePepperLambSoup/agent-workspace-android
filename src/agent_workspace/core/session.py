from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from agent_workspace.core.models import Autonomy, ChatMessage, Mode


@dataclass(slots=True)
class Session:
    workspace: str
    mode: Mode = Mode.CODING
    autonomy: Autonomy = Autonomy.WORKSPACE
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = "New session"
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
