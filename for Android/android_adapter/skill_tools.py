"""use_skill: the instructions of an installed skill (mobile_skills), loaded when a request needs it.

The system prompt lists every enabled skill by name and description only; this tool returns one
skill's full instructions, or one of the text files a skill refers to. Reading a skill changes
nothing, so it runs without an approval prompt, like knowledge_search.
"""

from __future__ import annotations

import asyncio
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result


class UseSkillTool:
    _SPEC = ToolSpec(
        name="use_skill",
        description=(
            "Load an installed skill: instructions for a particular kind of job, listed in the "
            "skills section of the system prompt. Call it with the skill's name before doing such "
            "a job and follow what it says. With file, read one of the skill's other files (it "
            "lists them)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "skill": {"type": "string", "minLength": 1, "maxLength": 140},
                "file": {
                    "type": "string",
                    "maxLength": 300,
                    "description": "A file of the skill to read instead, as listed in its files",
                },
            },
            "required": ["skill"],
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.MEMORY_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await asyncio.to_thread(self._load, arguments)

    def _load(self, arguments: dict[str, Any]) -> str:
        from mobile_skills import SkillError, get_skill_store

        skill = arguments.get("skill")
        file = arguments.get("file")
        if not isinstance(skill, str) or not skill.strip() or len(skill) > 140:
            raise ToolArgumentError("'skill' must be the name of an installed skill")
        if file is not None and (not isinstance(file, str) or not file.strip() or len(file) > 300):
            raise ToolArgumentError("'file' must be one of the skill's files")
        try:
            return json_result(get_skill_store().load(skill.strip(), file.strip() if file else None))
        except SkillError as exc:
            raise ToolError(str(exc)) from None
        except (OSError, UnicodeDecodeError):
            raise ToolError("the skill's files could not be read; reinstall its pack") from None


class SaveSkillTool:
    """Turns what was just done into one of the user's skills, when they ask for it.

    Like memory_write it changes only app state the user sees and can delete (Skills page → 我的技能),
    so it runs without an approval prompt.
    """

    _SPEC = ToolSpec(
        name="save_skill",
        description=(
            "Save a reusable skill when the user asks to keep what was just done (\"把刚才的操作存成"
            "技能\", \"save this as a skill\"). Write the instructions as general steps someone could "
            "follow next time on a screen that may look different: which app or page to open, which "
            "buttons or tabs by their words, what to check, what to report, and when to stop and ask "
            "the user (payments, passwords, sending messages, deleting). No coordinates, refs or "
            "one-off values unless the user wants them fixed. Saving under an existing name replaces "
            "that skill. Afterwards tell the user its name; it appears under Skills → 我的技能."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 1, "maxLength": 64,
                         "description": "A short name in the user's language"},
                "description": {"type": "string", "minLength": 1, "maxLength": 1024,
                                "description": "One line: what it does and when to use it"},
                "instructions": {"type": "string", "minLength": 1, "maxLength": 24000,
                                 "description": "Markdown steps"},
            },
            "required": ["name", "description", "instructions"],
            "additionalProperties": False,
        },
        side_effect="session_state",
        capability=Capability.MEMORY_WRITE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await asyncio.to_thread(self._save, arguments)

    def _save(self, arguments: dict[str, Any]) -> str:
        from mobile_skills import SkillError, get_skill_store

        try:
            saved = get_skill_store().save_user_skill(
                arguments.get("name"), arguments.get("description"), arguments.get("instructions")
            )
        except SkillError as exc:
            raise ToolArgumentError(str(exc)) from None
        return json_result({**saved, "where": "Skills → 我的技能 (the user can turn it off or delete it)"})
