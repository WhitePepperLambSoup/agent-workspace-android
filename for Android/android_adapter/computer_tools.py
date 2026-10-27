"""ask_computer: the phone's agent hands one part of a task to a paired computer (mobile_link).

Offered when a computer is paired with this phone (Device connections). Each call sends the task's
words to another device, so it asks the user every time (mobile_approval._ALWAYS_ASK_TOOLS: a
task-wide approval does not cover it); only a conversation set to approve everything skips that.
The computer runs the part in a new conversation of its own (or in one the agent names) with its
own model, tools and approvals, and the answer comes back here.
"""

from __future__ import annotations

import hashlib
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result

MAX_TASK_CHARS = 20_000


class AskComputerTool:
    _SPEC = ToolSpec(
        name="ask_computer",
        description=(
            "Hand one part of the task to the user's paired computer (Agent Workspace on their PC) "
            "and wait for its answer, up to 30 minutes. Use it only for what needs that computer: "
            "running a project's tests or scripts there, working on large files that are on the "
            "computer, using websites the computer is signed in to. The computer works in a new "
            "conversation of its own unless you name one of its conversations; it does not see this "
            "conversation, so the task must stand alone: what to do, where, and what to report back. "
            "The user approves each call. Do not send passwords, codes or ID numbers."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task": {"type": "string", "minLength": 1, "maxLength": MAX_TASK_CHARS},
                "computer": {
                    "type": "string",
                    "maxLength": 100,
                    "description": "The paired computer's name; only needed when several are paired.",
                },
                "conversation": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Title of an existing conversation on the computer to continue instead "
                    "of starting a new one.",
                },
            },
            "required": ["task"],
            "additionalProperties": False,
        },
        # Sends the task to another device: approved like a network action, each time.
        side_effect="network",
        capability=Capability.NETWORK_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolError("ask_computer can only be used from a running task in this app")

    async def execute_with_context(self, arguments: dict[str, Any], context: Any) -> str:
        import mobile_link

        link = mobile_link.current()
        if link is None:
            raise ToolError("the phone connection is not running")
        task = arguments.get("task")
        if not isinstance(task, str) or not task.strip() or len(task) > MAX_TASK_CHARS:
            raise ToolArgumentError(f"'task' must be 1 to {MAX_TASK_CHARS} characters")
        computer = arguments.get("computer") if isinstance(arguments.get("computer"), str) else None
        conversation = arguments.get("conversation") if isinstance(arguments.get("conversation"), str) else None
        # The same call (an interrupted task resumed) reuses its request, so the computer runs it once.
        digest = hashlib.sha256(f"{task}\0{computer}\0{conversation}".encode()).hexdigest()[:16]
        request_id = f"ask:{getattr(context, 'correlation_id', '')}:{digest}"[:128]
        try:
            outcome = await link.ask_computer(task.strip(), computer=computer, conversation=conversation,
                                              request_id=request_id)
        except ValueError as error:
            raise ToolError(str(error)) from None
        if outcome["state"] != "completed":
            raise ToolError(f"{outcome['computer']} did not finish: {outcome.get('error') or outcome['state']}")
        return json_result({
            "computer": outcome["computer"],
            "answer": outcome.get("result") or "",
            "note": "This is the computer's own report; check what matters before relying on it.",
        })


def computer_tools_available() -> bool:
    """A computer that takes tasks is paired (mobile_link reads the same database)."""
    import os
    from pathlib import Path

    data = os.getenv("AGENT_WORKSPACE_DATA_DIR")
    if not data:
        return False
    path = Path(data) / "mobile-management.db"
    if not path.is_file():
        return False
    try:
        from mobile_connections import MobileConnections

        return any(
            host["api"] == "mobile" and (not host["scopes"] or "tasks" in host["scopes"])
            for host in MobileConnections(path, credentials=object()).list()
        )
    except Exception:
        return False


__all__ = ["AskComputerTool", "computer_tools_available"]
