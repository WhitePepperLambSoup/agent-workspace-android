"""How long tasks of each kind took on this phone, for the progress line's "usually 1–3 min".

How long an agent's task takes is up to the model, step by step, so nothing here predicts it. What
the phone can say honestly is how long tasks like this one took before: a task's kind is its first
tool's (the web, the phone's apps, files, commands, the team, ...), its time runs from its first
running state to its end without the time it waited for the user's approval, and only tasks that
succeeded count. The latest 300 are kept in <data>/task-timing.json; a range is given only once five
tasks of the kind have been seen.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

MAX_RECORDS = 300
MIN_SEEN = 5
RECENT = 40
_KINDS = (
    ("phone", re.compile(r"^(android_|notification_|app_settings$|system_settings$|manage_app$|app_audit$)")),
    ("team", re.compile(r"^run_subagents$")),
    ("web", re.compile(r"^(web_|browser|http_request$|download_file$|paper_|read_paper$|check_references$)")),
    ("code", re.compile(r"^(run_|start_service$|stop_service$|check_page$)")),
    ("knowledge", re.compile(r"^(knowledge_|memory_)")),
    ("office", re.compile(r"^(create_|word_document$|spreadsheet$|pdf_tools$|slides_from_template$|office_|render_pdf$|read_document$)")),
    ("files", re.compile(r"^(write_file$|append_file$|read_file$|list_files$|search_files$|apply_patch$|copy_file$|move_path$|delete_path$)")),
)
_lock = threading.Lock()


def kind_of(tool: object) -> str:
    """The kind of a task by its first tool; "chat" when it used none."""
    if not isinstance(tool, str) or not tool:
        return "chat"
    return next((kind for kind, pattern in _KINDS if pattern.search(tool)), "other")


def _path() -> Path | None:
    folder = os.getenv("AGENT_WORKSPACE_DATA_DIR")
    return Path(folder) / "task-timing.json" if folder else None


def _load() -> list[dict[str, Any]]:
    path = _path()
    try:
        records = json.loads(path.read_text("utf-8")) if path else []
    except (OSError, ValueError):
        records = []
    return [item for item in records if isinstance(item, dict)] if isinstance(records, list) else []


def _instant(value: object) -> float | None:
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def working_seconds(transitions: list[tuple[str, object]]) -> float | None:
    """From the first running state to success, without the waits for approval; None if it did not succeed."""
    started = waiting = None
    paused = 0.0
    for state, at in transitions:
        moment = _instant(at)
        if moment is None:
            continue
        if state == "running":
            if started is None:
                started = moment
            if waiting is not None:
                paused += moment - waiting
                waiting = None
        elif state == "waiting_approval" and started is not None and waiting is None:
            waiting = moment
        elif state == "succeeded" and started is not None:
            if waiting is not None:
                paused += moment - waiting
            return max(0.0, moment - started - paused)
    return None


def record(kind: str, seconds: float, steps: int) -> None:
    path = _path()
    if path is None or seconds <= 0:
        return
    with _lock:
        records = _load()
        records.append({"kind": kind, "seconds": round(seconds, 1), "steps": int(steps)})
        records = records[-MAX_RECORDS:]
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(records), "utf-8")
        os.replace(temporary, path)


def record_task(transitions: list[tuple[str, object]], tools: list[str]) -> None:
    """A finished task: its time and steps under its first tool's kind (nothing if it did not succeed)."""
    seconds = working_seconds(transitions)
    if seconds is not None:
        record(kind_of(tools[0] if tools else ""), seconds, len(tools))


def estimate(kind: str) -> dict[str, Any]:
    """The middle half of the latest tasks of this kind, in seconds; no range before MIN_SEEN of them."""
    recent = [
        float(item["seconds"])
        for item in reversed(_load())
        if item.get("kind") == kind and isinstance(item.get("seconds"), (int, float))
    ][:RECENT]
    times = sorted(recent)
    if len(times) < MIN_SEEN:
        return {"kind": kind, "count": len(times), "low": None, "high": None}
    pick = lambda share: times[min(len(times) - 1, int(share * (len(times) - 1) + 0.5))]  # noqa: E731
    return {"kind": kind, "count": len(times), "low": round(pick(0.25)), "high": round(pick(0.75))}


__all__ = ["estimate", "kind_of", "record", "record_task", "working_seconds"]
