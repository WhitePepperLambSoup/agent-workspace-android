from __future__ import annotations

from typing import Any
from uuid import uuid4

from agent_workspace.application.ports import EventStore
from agent_workspace.core.events import Event


def add_comment(
    store: EventStore,
    session_id: str,
    text: str,
    author: str,
) -> str:
    if not text.strip() or len(text) > 4000:
        raise ValueError("comment text must be 1-4000 characters")
    if not author.strip() or len(author) > 200:
        raise ValueError("comment author must be 1-200 characters")
    if store.get_session(session_id) is None:
        raise KeyError(f"unknown session: {session_id}")
    comment_id = str(uuid4())
    store.append(
        Event(
            session_id=session_id,
            type="session.comment.added",
            data={"comment_id": comment_id, "text": text, "author": author},
        )
    )
    return comment_id


def list_comments(store: EventStore, session_id: str) -> list[dict[str, Any]]:
    if store.get_session(session_id) is None:
        raise KeyError(f"unknown session: {session_id}")
    comments: list[dict[str, Any]] = []
    for event in store.list_events(session_id):
        if event.type != "session.comment.added":
            continue
        text = event.data.get("text")
        author = event.data.get("author")
        comment_id = event.data.get("comment_id")
        if isinstance(text, str) and isinstance(author, str) and isinstance(comment_id, str):
            comments.append(
                {
                    "comment_id": comment_id,
                    "text": text,
                    "author": author,
                    "created_at": event.created_at,
                }
            )
    return comments
