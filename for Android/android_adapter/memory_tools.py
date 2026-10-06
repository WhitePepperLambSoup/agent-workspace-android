"""memory_search / memory_write backed by the phone-wide memory store (mobile_memory).

The core tools keep memory per workspace and ask for approval on every write. On the phone the
memory is about the user, shared by all workspaces, shown in every task's system prompt and kept
small by hard limits in the store, so writes run without an approval prompt (the "session_state"
effect) and every saved note stays visible and editable on the Memory page.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result, optional_int


def _store():
    from mobile_memory import get_memory_store

    return get_memory_store()


class MobileMemorySearchTool:
    _SPEC = ToolSpec(
        name="memory_search",
        description=(
            "Search the user's saved memories on this phone (short notes about the user and their "
            "preferences). The newest memories are already listed in the system prompt; search "
            "only for older ones that are not shown there."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "maxLength": 512},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.MEMORY_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        store = _store()
        if not store.snapshot()["enabled"]:
            raise ToolError("memory is turned off on this phone")
        query = arguments.get("query", "")
        if not isinstance(query, str) or len(query) > 512:
            raise ToolArgumentError("'query' must be a string of at most 512 characters")
        limit = optional_int(arguments, "limit", 20, minimum=1, maximum=50)
        return json_result({"memories": store.search(query, limit)})

    async def execute_with_context(self, arguments: dict[str, Any], _context: Any) -> str:
        return await self.execute(arguments)


class MobileMemoryWriteTool:
    _SPEC = ToolSpec(
        name="memory_write",
        description=(
            "Save, update or delete one short memory about the user on this phone. upsert with "
            "content adds a memory, or replaces the memory whose id you pass; delete removes one "
            "by id. One fact per memory, at most 200 characters. Follow the memory rules in the "
            "system prompt."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["upsert", "delete"]},
                "id": {"type": "string", "minLength": 1, "maxLength": 64},
                "content": {"type": "string", "minLength": 1, "maxLength": 400},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
        # Allowed without an approval prompt in workspace and YOLO modes; the store enforces size,
        # count, duplicates and secret filtering, and the user can review every note.
        side_effect="session_state",
        capability=Capability.MEMORY_WRITE,
    )

    def __init__(self) -> None:
        self._saves: OrderedDict[str, int] = OrderedDict()

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolArgumentError("memory_write requires an active task")

    def _count_save(self, context: Any) -> None:
        from mobile_memory import AUTO_SAVES_PER_TASK

        key = f"{getattr(context, 'session_id', '')}:{getattr(context, 'correlation_id', '')}"
        used = self._saves.get(key, 0)
        if used >= AUTO_SAVES_PER_TASK:
            raise ToolError(
                f"only {AUTO_SAVES_PER_TASK} memory saves are allowed per task; combine related "
                "facts, or tell the user they can add more on the Memory page"
            )
        self._saves[key] = used + 1
        self._saves.move_to_end(key)
        while len(self._saves) > 64:
            self._saves.popitem(last=False)

    async def execute_with_context(self, arguments: dict[str, Any], context: Any) -> str:
        from mobile_memory import DuplicateMemory, MemoryChangeError

        store = _store()
        if not store.snapshot()["enabled"]:
            raise ToolError("memory is turned off on this phone")
        action = arguments.get("action")
        memory_id = arguments.get("id")
        if memory_id is not None and (not isinstance(memory_id, str) or not memory_id):
            raise ToolArgumentError("'id' must be a memory id from the list")
        try:
            if action == "delete":
                if not memory_id:
                    raise ToolArgumentError("delete needs the id of the memory to remove")
                store.delete(memory_id)
                return json_result({"deleted": memory_id})
            if action != "upsert":
                raise ToolArgumentError("action must be upsert or delete")
            self._count_save(context)
            if memory_id:
                item = store.update(memory_id, arguments.get("content"), source="auto")
                return json_result({"updated": item})
            item = store.add(arguments.get("content"), source="auto")
            return json_result({"saved": item})
        except KeyError:
            raise ToolError(f"no memory has the id {memory_id}") from None
        except DuplicateMemory as duplicate:
            raise ToolError(
                f"this is already remembered as {duplicate.existing['id']}: "
                f"{duplicate.existing['content']} — update that memory if it changed"
            ) from None
        except MemoryChangeError as exc:
            raise ToolError(str(exc)) from None


__all__ = ["MobileMemorySearchTool", "MobileMemoryWriteTool"]
