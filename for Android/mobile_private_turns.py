"""Turns the on-device model answered (privacy routing, mobile_privacy_route) stay on the phone.

The conversation still shows them, but a later turn of the same conversation that goes to a cloud
model leaves them out of the history it sends (the runner's ``exclude_correlations``). They are
recorded by correlation id, the run's id on every event it writes, in private-turns.json beside
the database; a deleted conversation leaves the record.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

_FILE = "private-turns.json"
# A conversation with more on-device turns than this keeps the latest.
_PER_SESSION = 2000
_lock = threading.Lock()


def _path() -> Path:
    return Path(os.getenv("AGENT_WORKSPACE_DATA_DIR") or ".") / _FILE


def _load() -> dict[str, list[str]]:
    try:
        document: Any = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(document, dict):
        return {}
    return {
        key: [item for item in value if isinstance(item, str) and item]
        for key, value in document.items()
        if isinstance(key, str) and isinstance(value, list)
    }


def _save(document: dict[str, list[str]]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document), encoding="utf-8")
    os.replace(temporary, path)


def record(session_id: str, correlations: Iterable[str]) -> None:
    """Keeps these runs of the conversation on the phone."""
    new = [item for item in correlations if isinstance(item, str) and item]
    if not new:
        return
    with _lock:
        document = _load()
        kept = document.get(session_id, [])
        kept.extend(item for item in new if item not in kept)
        document[session_id] = kept[-_PER_SESSION:]
        _save(document)


def excluded(session_id: str) -> frozenset[str]:
    """The runs of the conversation a cloud request leaves out."""
    with _lock:
        return frozenset(_load().get(session_id, ()))


def forget(session_ids: Iterable[str]) -> None:
    """Deleted conversations leave the record."""
    gone = set(session_ids)
    with _lock:
        document = _load()
        if gone & document.keys():
            _save({key: value for key, value in document.items() if key not in gone})
