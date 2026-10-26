"""Forks of a desktop conversation, and the comparison of two models' answers.

A fork is a new conversation that continues from an earlier point; the original stays as it is.
From a user's message it keeps everything before the turn that message started, and the message
goes back to the composer to change and send. From the message's reply it keeps that whole
turn. The copy is on the same workspace, so files are shared, not copied.

A comparison fork asks the same question of another model: it keeps what came before the
question, and its first turn is the question sent with that model. ``comparison`` reads both
answers with the time their models took and the tokens they used.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from agent_workspace.core.events import Event
from agent_workspace.core.session import Session
from agent_workspace.storage import fork_session
from agent_workspace.storage.sqlite import SQLiteEventStore

FORK_EVENT = "session.forked"
_TURN_ENDS = {"turn.completed": "completed", "turn.failed": "failed", "turn.cancelled": "cancelled"}
_MAX_ANSWER_CHARS = 30_000


class ForkError(ValueError):
    """A fork the conversation cannot make; ``code`` is a stable gateway error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ForkResult:
    session: Session
    # The message to put back in the composer (a fork from a message) or to send again (a
    # comparison); None for a fork from a reply.
    prompt: str | None
    source_model: str | None


def _turn_starts(events: Sequence[Event]) -> list[int]:
    return [
        index
        for index, event in enumerate(events)
        if event.type == "turn.started" and event.data.get("continuation") is not True
    ]


def _message_position(events: Sequence[Event], message_id: str) -> int:
    """Where the user's message is: its message.created, or a message sent while the turn ran
    (shown by the id of its turn.input.received)."""
    for index, event in enumerate(events):
        if event.id != message_id:
            continue
        if event.type == "turn.input.received":
            return index
        if event.type == "message.created" and event.data.get("role") == "user":
            return index
        break
    raise ForkError("fork_unknown_message")


def fork_point(events: Sequence[Event], message_id: str, *, keep_reply: bool) -> int:
    """How many of the conversation's first events the fork keeps."""
    position = _message_position(events, message_id)
    starts = _turn_starts(events)
    if not keep_reply:
        message = events[position]
        # A message sent while a turn ran is part of that turn; only the message a turn
        # started with can be asked again on its own.
        if message.type != "message.created" or isinstance(message.data.get("input_id"), str):
            raise ForkError("fork_unavailable")
        return max((start for start in starts if start <= position), default=position)
    return min((start for start in starts if start > position), default=len(events))


def _turn_model(events: Sequence[Event], position: int) -> str | None:
    start = max(
        (index for index in _turn_starts(events) if index <= position),
        default=None,
    )
    if start is None:
        return None
    model = events[start].data.get("model")
    return model if isinstance(model, str) and model else None


def fork_conversation(
    store: SQLiteEventStore,
    session_id: str,
    message_id: str,
    *,
    keep_reply: bool,
    title: str,
    compare_model: str | None = None,
) -> ForkResult:
    """Make the fork and mark where it came from with a ``session.forked`` event."""
    source = store.get_session(session_id)
    if source is None:
        raise ForkError("unknown_session")
    if compare_model is not None and keep_reply:
        raise ForkError("invalid_fork")
    events = store.list_events(session_id)
    keep = fork_point(events, message_id, keep_reply=keep_reply)
    position = _message_position(events, message_id)
    message = events[position]
    prompt = None if keep_reply else str(message.data.get("content") or "").strip() or None
    if not keep_reply and prompt is None:
        raise ForkError("fork_unavailable")
    if keep == 0:
        # Nothing comes before the first question: the fork starts empty.
        forked = Session(
            workspace=source.workspace,
            mode=source.mode,
            autonomy=source.autonomy,
            title=title[:500],
        )
        store.create_session(forked)
    else:
        try:
            forked = fork_session(store, session_id, events[:keep], title=title)
        except ValueError as exc:
            if "middle of a turn" in str(exc):
                raise ForkError("fork_turn_running") from None
            raise ForkError("fork_unavailable") from None
    source_model = _turn_model(events, position)
    marker: dict[str, Any] = {
        "source_session_id": source.id,
        "source_message_id": message_id,
        "keep_reply": keep_reply,
    }
    if source_model is not None:
        marker["source_model"] = source_model
    if compare_model is not None:
        marker["compare_model"] = compare_model
    store.append(Event(session_id=forked.id, type=FORK_EVENT, data=marker))
    return ForkResult(forked, prompt, source_model)


def fork_marker(events: Sequence[Event]) -> tuple[int, Event] | None:
    for index in range(len(events) - 1, -1, -1):
        if events[index].type == FORK_EVENT:
            return index, events[index]
    return None


def _seconds_between(start: str, end: str) -> float | None:
    try:
        elapsed = datetime.fromisoformat(end) - datetime.fromisoformat(start)
        return max(0.0, elapsed.total_seconds())
    except (TypeError, ValueError):
        return None


def _answer(events: Sequence[Event], start: int | None) -> dict[str, Any]:
    """One turn's answer: its model, final text, model time (the sum of each request's time,
    so time spent waiting for approvals is left out), tokens, and how it ended."""
    if start is None:
        return {"state": "missing"}
    model = events[start].data.get("model")
    end = len(events)
    for index in range(start + 1, len(events)):
        event = events[index]
        if event.type == "turn.started" and event.data.get("continuation") is not True:
            end = index
            break
    state = "running"
    answer = ""
    requested: dict[str, str] = {}
    model_seconds = 0.0
    input_tokens = output_tokens = cached_tokens = 0
    for event in events[start + 1 : end]:
        data = event.data
        if event.type in _TURN_ENDS:
            state = _TURN_ENDS[event.type]
        elif event.type == "message.created" and data.get("role") == "assistant":
            content = data.get("content")
            if isinstance(content, str) and content.strip():
                answer = content
        elif event.type == "model.requested" and data.get("kind") != "context_summary":
            requested[event.id] = event.created_at
        elif event.type == "model.completed":
            request_id = data.get("model_request_id") or event.causation_id
            began = requested.pop(request_id, None) if isinstance(request_id, str) else None
            if began is not None:
                model_seconds += _seconds_between(began, event.created_at) or 0.0
        elif event.type == "usage.updated":
            inputs, outputs, cached = (
                data.get("input_tokens"),
                data.get("output_tokens"),
                data.get("cached_tokens"),
            )
            if type(inputs) is int and type(outputs) is int and inputs >= 0 and outputs >= 0:
                input_tokens += inputs
                output_tokens += outputs
                if type(cached) is int and cached >= 0:
                    cached_tokens += cached
    return {
        "state": state,
        "model": model if isinstance(model, str) else None,
        "answer": answer[:_MAX_ANSWER_CHARS],
        "answerTruncated": len(answer) > _MAX_ANSWER_CHARS,
        "modelSeconds": round(model_seconds, 3),
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "cachedTokens": cached_tokens,
    }


def comparison(source_events: Sequence[Event], fork_events: Sequence[Event]) -> dict[str, Any]:
    """Both answers of a comparison fork, or ``ForkError`` when the session is not one."""
    found = fork_marker(fork_events)
    if found is None or not isinstance(found[1].data.get("compare_model"), str):
        raise ForkError("fork_not_comparison")
    marker_index, marker = found
    message_id = marker.data.get("source_message_id")
    try:
        position = _message_position(source_events, str(message_id))
    except ForkError:
        original: dict[str, Any] = {"state": "missing"}
        question = None
    else:
        start = max((i for i in _turn_starts(source_events) if i <= position), default=None)
        original = _answer(source_events, start)
        content = source_events[position].data.get("content")
        question = content if isinstance(content, str) else None
    candidate_start = next(
        (i for i in _turn_starts(fork_events) if i > marker_index),
        None,
    )
    return {
        "sourceSessionId": marker.data.get("source_session_id"),
        "question": question,
        "compareModel": marker.data.get("compare_model"),
        "original": original,
        "candidate": _answer(fork_events, candidate_start),
    }


__all__ = [
    "FORK_EVENT",
    "ForkError",
    "ForkResult",
    "comparison",
    "fork_conversation",
    "fork_marker",
    "fork_point",
]
