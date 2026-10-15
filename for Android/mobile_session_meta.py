"""Pinned conversations and conversation tags, kept beside the sessions in <data>/session-meta.json.

Tags are short labels the user gives conversations ("工作", "学习") to group and filter them in the
drawer; a conversation can have a few, and the whole phone a few dozen distinct ones.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

MAX_TAGS_PER_SESSION = 5
MAX_DISTINCT_TAGS = 40
MAX_TAG_CHARS = 16
_lock = threading.Lock()


def _path() -> Path:
    return Path(os.getenv("AGENT_WORKSPACE_DATA_DIR") or ".") / "session-meta.json"


def _read() -> dict[str, Any]:
    try:
        document = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        document = {}
    tags = document.get("tags") if isinstance(document, dict) else None
    pinned = document.get("pinned") if isinstance(document, dict) else None
    return {
        "tags": {
            str(key)[:128]: [str(tag)[:MAX_TAG_CHARS] for tag in value if isinstance(tag, str)][:MAX_TAGS_PER_SESSION]
            for key, value in (tags.items() if isinstance(tags, dict) else ())
            if isinstance(value, list)
        },
        "pinned": [str(item)[:128] for item in pinned if isinstance(item, str)] if isinstance(pinned, list) else [],
    }


def _write(document: dict[str, Any]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def snapshot() -> dict[str, Any]:
    with _lock:
        return _read()


def set_tags(session_id: str, tags: Any) -> dict[str, Any]:
    if not isinstance(session_id, str) or not session_id or len(session_id) > 128:
        raise ValueError("session_id is required")
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ValueError("tags must be a list of text")
    cleaned = list(dict.fromkeys(" ".join(tag.split()) for tag in tags if tag.strip()))
    if len(cleaned) > MAX_TAGS_PER_SESSION:
        raise ValueError(f"at most {MAX_TAGS_PER_SESSION} tags per conversation")
    if any(len(tag) > MAX_TAG_CHARS for tag in cleaned):
        raise ValueError(f"a tag can be at most {MAX_TAG_CHARS} characters")
    with _lock:
        document = _read()
        if cleaned:
            document["tags"][session_id] = cleaned
        else:
            document["tags"].pop(session_id, None)
        distinct = {tag for values in document["tags"].values() for tag in values}
        if len(distinct) > MAX_DISTINCT_TAGS:
            raise ValueError(f"at most {MAX_DISTINCT_TAGS} different tags; reuse an existing one")
        _write(document)
        return document


def set_pinned(session_id: str, pinned: Any) -> dict[str, Any]:
    if not isinstance(session_id, str) or not session_id or len(session_id) > 128:
        raise ValueError("session_id is required")
    if not isinstance(pinned, bool):
        raise ValueError("pinned must be true or false")
    with _lock:
        document = _read()
        rest = [item for item in document["pinned"] if item != session_id]
        document["pinned"] = ([session_id] + rest) if pinned else rest
        _write(document)
        return document


def forget(session_ids: set[str]) -> None:
    """Drops tags and pins of deleted conversations."""
    with _lock:
        document = _read()
        document["tags"] = {key: value for key, value in document["tags"].items() if key not in session_ids}
        document["pinned"] = [item for item in document["pinned"] if item not in session_ids]
        _write(document)
