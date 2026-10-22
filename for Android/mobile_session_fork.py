"""Fork a conversation: a new one that continues from an earlier point; the original stays as it is.

From a user's message, the fork keeps everything before the task that message started (the
console puts the message back in the input box, to change and send). From a reply, it keeps
everything up to the end of that reply's task. The copy is on the same workspace, so files are
shared, not copied. Its tasks get new ids: tasks are kept by id across conversations, and each
must stay with its own one.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any

from agent_workspace.core.events import Event
from agent_workspace.storage import fork_session

_TERMINAL = {"succeeded", "failed", "cancelled", "interrupted"}


def _is_user_message(event: Event) -> bool:
    return event.type == "message.created" and event.data.get("role") == "user"


def _task_starts(events: list[Event]) -> list[int]:
    """Where each task begins: its mobile.task.created, or for a conversation without those, a
    turn that is not the continuation of the one before."""
    starts = [index for index, event in enumerate(events) if event.type == "mobile.task.created"]
    if starts:
        return starts
    return [index for index, event in enumerate(events)
            if event.type == "turn.started" and event.data.get("continuation") is not True]


def fork_point(events: list[Event], message_id: str, *, keep_reply: bool) -> int:
    """How many of the conversation's first events the fork keeps."""
    position = next((index for index, event in enumerate(events) if event.id == message_id), None)
    if position is None or not _is_user_message(events[position]):
        raise ValueError("choose one of the user's messages in this conversation")
    starts = _task_starts(events)
    if not keep_reply:
        return max((start for start in starts if start <= position), default=position)
    return min((start for start in starts if start > position), default=len(events))


def _renumbered_tasks(events: list[Event]) -> list[Event]:
    """The copy's task events, with new task and request ids; a copied task cannot be resumed."""
    task_ids: dict[str, str] = {}
    states: dict[str, str] = {}
    copied = []
    for event in events:
        if not (event.type.startswith("mobile.task.") or event.type == "mobile.event"):
            copied.append(event)
            continue
        data: dict[str, Any] = dict(event.data)
        task_id = data.get("task_id")
        if isinstance(task_id, str):
            data["task_id"] = task_ids.setdefault(task_id, str(uuid.uuid4()))
            if event.type.startswith("mobile.task."):
                states[task_id] = str(data.get("state") or event.type.rsplit(".", 1)[-1])
        if event.type == "mobile.task.created" and isinstance(data.get("request_id"), str):
            data["request_id"] = str(uuid.uuid4())
        if data.get("resume_available"):
            data["resume_available"] = False
        copied.append(replace(event, data=data))
    if any(state not in _TERMINAL for state in states.values()):
        raise ValueError("a task is still running at that point; wait for it to finish")
    return copied


def fork_conversation(store: Any, session_id: str, message_id: str, *, keep_reply: bool, title: str) -> dict[str, Any]:
    """The new conversation, its events copied up to the chosen point: {"session": Session,
    "message_event_id": the message's copy (kept with its reply) or None, "model": the model of
    the message's task}. With the copy of the message, the same question can be asked again in
    the new conversation (a comparison with another model)."""
    events = store.list_events(session_id)
    keep = fork_point(events, message_id, keep_reply=keep_reply)
    if keep == 0:
        raise ValueError("nothing comes before this message to keep")
    position = next(index for index, event in enumerate(events) if event.id == message_id)
    created = [event for event in events[: position + 1] if event.type == "mobile.task.created"]
    forked = fork_session(store, session_id, _renumbered_tasks(events[:keep]), title=title)
    copy = store.list_events(forked.id)[position].id if position < keep else None
    model = created[-1].data.get("model") if created else None
    return {"session": forked, "message_event_id": copy, "model": model if isinstance(model, str) else None}
