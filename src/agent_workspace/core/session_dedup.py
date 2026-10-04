"""Duplicate session detection from user message fingerprints."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from agent_workspace.core.events import Event
from agent_workspace.core.models import Role


def session_fingerprint(events: Iterable[Event], limit: int = 20) -> str | None:
    """Hash up to ``limit`` non-empty user messages into a stable fingerprint."""
    digest = hashlib.sha256()
    counted = 0
    for event in events:
        if counted >= limit:
            break
        if event.type != "message.created":
            continue
        role = event.data.get("role")
        content = event.data.get("content")
        if role != Role.USER.value or not isinstance(content, str) or not content.strip():
            continue
        digest.update(content.strip().encode("utf-8"))
        digest.update(b"\0")
        counted += 1
    if counted == 0:
        return None
    return digest.hexdigest()


def find_duplicate_sessions(
    sessions: dict[str, list[Event]],
    *,
    limit_per_session: int = 20,
) -> list[tuple[str, str]]:
    """Return (session_id, duplicate_of_session_id) pairs, earliest wins."""
    seen: dict[str, str] = {}
    duplicates: list[tuple[str, str]] = []
    for session_id, events in sessions.items():
        fingerprint = session_fingerprint(events, limit_per_session)
        if fingerprint is None:
            continue
        original = seen.get(fingerprint)
        if original is None:
            seen[fingerprint] = session_id
        else:
            duplicates.append((session_id, original))
    return duplicates


__all__ = ["find_duplicate_sessions", "session_fingerprint"]
