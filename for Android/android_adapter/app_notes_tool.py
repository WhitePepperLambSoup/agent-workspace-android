"""app_note: the agent keeps a short note about how an app works (mobile_app_notes).

Like memory_write, a note runs without an approval prompt in workspace and YOLO modes (the
"session_state" effect), at most a few per task, and every note stays visible and deletable under
Settings → App notes. Notes come back to later tasks when they enter that app.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result


class AppNoteTool:
    _SPEC = ToolSpec(
        name="app_note",
        description=(
            "Keep one short note about how an app works, for later tasks in that app: where a "
            "setting or page is, what a control really does, a step the app needs first. Only what "
            "you found out on the screen and that is not obvious; nothing about the user (that "
            "is memory_write), no personal data, codes or passwords. add saves a note; replace "
            "rewrites the note with that id (ids are shown in app_notes); delete removes one."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "replace", "delete"]},
                "package_name": {"type": "string", "minLength": 3, "maxLength": 255},
                "app_name": {"type": "string", "maxLength": 60},
                "text": {"type": "string", "minLength": 1, "maxLength": 300},
                "id": {"type": "string", "minLength": 1, "maxLength": 32},
            },
            "required": ["action", "package_name"],
            "additionalProperties": False,
        },
        side_effect="session_state",
        capability=Capability.MEMORY_WRITE,
    )

    def __init__(self) -> None:
        self._saves: OrderedDict[str, int] = OrderedDict()

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolArgumentError("app_note requires an active task")

    def _count_save(self, context: Any) -> None:
        from mobile_app_notes import SAVES_PER_TASK

        key = f"{getattr(context, 'session_id', '')}:{getattr(context, 'correlation_id', '')}"
        used = self._saves.get(key, 0)
        if used >= SAVES_PER_TASK:
            raise ToolError(f"only {SAVES_PER_TASK} app notes are kept per task; keep the most useful")
        self._saves[key] = used + 1
        self._saves.move_to_end(key)
        while len(self._saves) > 64:
            self._saves.popitem(last=False)

    async def execute_with_context(self, arguments: dict[str, Any], context: Any) -> str:
        from mobile_app_notes import AppNoteError, add_note, delete_note

        action = arguments.get("action")
        package = arguments.get("package_name")
        try:
            if action == "delete":
                if not arguments.get("id"):
                    raise ToolArgumentError("delete needs the id of the note")
                delete_note(package, arguments["id"])
                return json_result({"deleted": arguments["id"]})
            if action not in ("add", "replace"):
                raise ToolArgumentError("action must be add, replace or delete")
            if action == "replace" and not arguments.get("id"):
                raise ToolArgumentError("replace needs the id of the note")
            self._count_save(context)
            note = add_note(
                package,
                arguments.get("text"),
                app_name=arguments.get("app_name"),
                replace=arguments.get("id") if action == "replace" else None,
            )
            return json_result({"saved": note, "package_name": package})
        except AppNoteError as exc:
            raise ToolError(str(exc)) from None


__all__ = ["AppNoteTool"]
