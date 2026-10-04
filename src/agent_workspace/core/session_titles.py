"""Heuristic session title generation from user messages."""

from __future__ import annotations

import re
from collections.abc import Iterable

from agent_workspace.core.events import Event
from agent_workspace.core.models import Role

_WHITESPACE = re.compile(r"\s+")


def generate_session_title(
    events: Iterable[Event],
    *,
    max_chars: int = 80,
) -> str:
    if max_chars < 12:
        raise ValueError("title length must be at least 12 characters")
    for event in events:
        if event.type != "message.created":
            continue
        if event.data.get("role") != Role.USER.value:
            continue
        content = event.data.get("content")
        if not isinstance(content, str):
            continue
        normalized = _WHITESPACE.sub(" ", content).strip()
        if not normalized:
            continue
        if len(normalized) <= max_chars:
            return normalized
        return normalized[: max_chars - 1].rstrip() + "…"
    return "New session"


__all__ = ["generate_session_title"]
