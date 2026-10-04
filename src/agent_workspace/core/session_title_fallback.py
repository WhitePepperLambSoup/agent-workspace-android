"""Session title fallback generator.

Produces deterministic titles for sessions that contain no user-authored
text and de-duplicates titles across the session list with `` (2)`` suffixes.
Builds on ``session_titles.generate_session_title`` so normal sessions keep
their heuristic titles.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime

from agent_workspace.core.events import Event
from agent_workspace.core.session_titles import generate_session_title

_TRAILING_NUMBER = re.compile(r"^(.*?)(?: \((\d+)\))?$", re.DOTALL)
_MAX_TITLE_LENGTH = 120


class SessionTitleFallbackError(ValueError):
    pass


def fallback_session_title(
    events: Iterable[Event], *, now: float | None = None, max_chars: int = 120
) -> str:
    """Title for a session whose event stream has no usable user message."""
    if max_chars < 12:
        raise SessionTitleFallbackError("title length must be at least 12 characters")
    event_list = list(events)
    prefix = "New session"
    for event in event_list:
        if event.type != "message.created":
            continue
        role = event.data.get("role")
        if role == "assistant":
            prefix = "Assistant session"
            break
        if role == "tool":
            prefix = "Tool session"
            break
    timestamp = now if now is not None else _timestamp_from_events(event_list)
    try:
        stamp = datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError) as exc:
        raise SessionTitleFallbackError("session fallback timestamp is invalid") from exc
    title = f"{prefix} · {stamp}"
    if len(title) > max_chars:
        title = title[: max_chars - 1].rstrip() + "…"
    return title


def ensure_unique_title(
    title: str,
    existing_titles: Sequence[str] | set[str],
    *,
    max_length: int = _MAX_TITLE_LENGTH,
) -> str:
    """Append `` (2)``, `` (3)``, ... until the title is unique."""
    if not title.strip():
        raise SessionTitleFallbackError("session title may not be empty")
    if max_length < 12:
        raise SessionTitleFallbackError("title length must be at least 12 characters")
    base = title.strip()
    if len(base) > max_length:
        base = base[: max_length - 1].rstrip() + "…"
    taken = {item.casefold() for item in existing_titles}
    candidate = base
    counter = 2
    while candidate.casefold() in taken:
        match = _TRAILING_NUMBER.fullmatch(base)
        stem = (match.group(1) if match else base) or base
        candidate = f"{stem} ({counter})"
        if len(candidate) > max_length:
            available = max_length - len(f" ({counter})")
            candidate = f"{stem[:available].rstrip()} ({counter})"
        counter += 1
        if counter > 10_000:
            raise SessionTitleFallbackError("could not find a unique session title")
    return candidate


def generate_title_with_fallback(
    events: Iterable[Event],
    existing_titles: Sequence[str] | set[str] = (),
    *,
    now: float | None = None,
    max_chars: int = 120,
) -> str:
    event_list = list(events)
    title = generate_session_title(event_list, max_chars=max_chars)
    if title == "New session":
        title = fallback_session_title(event_list, now=now, max_chars=max_chars)
    return ensure_unique_title(title, existing_titles, max_length=max_chars)


def _timestamp_from_events(events: Sequence[Event]) -> float:
    for event in events:
        raw = event.created_at
        if not isinstance(raw, str):
            continue
        try:
            return datetime.fromisoformat(raw).timestamp()
        except ValueError:
            continue
    return datetime.now(UTC).timestamp()


__all__ = [
    "SessionTitleFallbackError",
    "ensure_unique_title",
    "fallback_session_title",
    "generate_title_with_fallback",
]
