"""Put back the files a task created or changed (the file list under its reply).

The task's own file versions (runtime.file.version.recorded, forwarded into its events) say what
each file was before the task and what the task left; the shared core's rewind puts a file back only
while it is exactly as the task left it, and keeps what it replaces first. A file the task made is
removed; a later task's changes to the same file leave it alone ("changed").
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def task_file_versions(events: Any) -> list[dict[str, Any]]:
    """The file versions a task recorded, oldest first."""
    found: list[dict[str, Any]] = []
    for event in events:
        if getattr(event, "event_type", None) != "runtime.file.version.recorded":
            continue
        data = (getattr(event, "payload", None) or {}).get("data")
        if isinstance(data, dict) and isinstance(data.get("path"), str) and isinstance(data.get("sha256"), str):
            found.append(dict(data))
    return found


def undo_task_files(
    workspace: str | os.PathLike[str],
    session_id: str,
    versions: list[dict[str, Any]],
    paths: list[str] | None,
    *,
    apply: bool,
    data_dir: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    """Each file the task changed (all, or those in paths) and whether it is, or would be, put back:
    {"path", "action": "restore" | "remove", "reason": None | "changed" | "not_kept" | "unsafe"}."""
    from agent_workspace.application.rewind import rewind_files
    from agent_workspace.core.events import Event
    from agent_workspace.storage.file_versions import FileVersions

    wanted = None if paths is None else set(paths)
    marker = Event(session_id=session_id, type="task.files.undo", data={}, sequence=0)
    events = [marker]
    for data in versions:
        if wanted is not None and data["path"] not in wanted:
            continue
        events.append(Event(session_id=session_id, type="file.version.recorded", data=data, sequence=len(events)))
    store = Path(data_dir or os.environ["AGENT_WORKSPACE_DATA_DIR"]) / "file-versions"
    return [item.document() for item in rewind_files(Path(workspace), FileVersions(store), events, marker.id, apply=apply)]


__all__ = ["task_file_versions", "undo_task_files"]
