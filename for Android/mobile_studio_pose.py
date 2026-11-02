"""Where the agent is in its 3D studio while a task runs, for the studio widget on the home screen.

The page's studio (app/29-team.js studioCast) places the agent by its running tool; the widget,
drawn while the app may be closed, gets the same from the engine with the task list (task_summary
"pose"): at the window before its first step, at its desk between steps and while it writes, at the
shelves for books and papers, in the sandbox for commands, at the console for the phone, at the board
while helpers work. Waiting for approval (at the door) and idle come from the task's state.
"""

from __future__ import annotations

import re
from typing import Any

POSES = ("window", "desk", "shelf", "sandbox", "console", "board", "door", "idle")
_SHELF = re.compile(r"^(knowledge_|paper_|read_paper$|reference_library$|memory_search$|check_references$)")
_SANDBOX = re.compile(r"^(run_terminal|run_process|start_service|stop_service)$")
_CONSOLE = re.compile(r"^(android_|notification_reply$|notification_open$|app_settings$|system_settings$|manage_app$)")
_ENDED = {"tool.settled", "tool.failed", "tool.cancelled", "tool.unknown", "tool.rejected"}


def pose_of_tool(name: object) -> str:
    tool = str(name or "")
    if tool == "run_subagents":
        return "board"
    if _CONSOLE.search(tool):
        return "console"
    if _SANDBOX.search(tool):
        return "sandbox"
    if _SHELF.search(tool):
        return "shelf"
    return "desk"


def next_pose(event_type: str, data: dict[str, Any], current: str | None) -> str | None:
    """The pose after one of the agent's own events, or None when it does not move."""
    if event_type == "tool.started":
        return pose_of_tool(data.get("name"))
    if event_type in _ENDED:
        # Helpers at work keep it at the board until their step ends.
        return "desk"
    if event_type == "model.output.delta" and data.get("kind") != "reasoning" and current != "board":
        return "desk"
    return None


__all__ = ["POSES", "next_pose", "pose_of_tool"]
