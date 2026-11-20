"""memory_search / memory_write backed by the phone-wide memory store (mobile_memory).

The core tools keep memory per workspace and ask for approval on every write. On the phone the
memory is about the user, shared by all workspaces, shown in every task's system prompt and kept
small by hard limits in the store, so saving a new note runs without an approval prompt (the
"session_state" effect) and every saved note stays visible and editable on the Memory page.
Deleting a memory, or rewriting one the user wrote, asks the user first (prepare_for_approval).
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result, optional_int

# The same topics as mobile_memory.TOPICS (kept here so the schema needs no store import).
_TOPICS = ("profile", "preferences", "work", "life", "people", "projects", "other")


def _store():
    from mobile_memory import get_memory_store

    return get_memory_store()


class MobileMemorySearchTool:
    _SPEC = ToolSpec(
        name="memory_search",
        description=(
            "Search the user's saved memories on this phone (short notes about the user and their "
            "preferences) by words, a topic, or both. The newest memories are already listed in the "
            "system prompt; search only for older ones that are not shown there."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "maxLength": 512},
                "topic": {"type": "string", "enum": list(_TOPICS)},
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
        topic = arguments.get("topic")
        if topic is not None and topic not in _TOPICS:
            raise ToolArgumentError(f"'topic' must be one of {', '.join(_TOPICS)}")
        return json_result({"memories": store.search(query, limit, topic)})

    async def execute_with_context(self, arguments: dict[str, Any], _context: Any) -> str:
        return await self.execute(arguments)


class MobileMemoryWriteTool:
    _SPEC = ToolSpec(
        name="memory_write",
        description=(
            "Save, update or delete one short memory about the user on this phone. upsert with "
            "content adds a memory, or replaces the memory whose id you pass; delete removes one "
            "by id. One fact per memory, at most 200 characters, with its topic. Follow the memory "
            "rules in the system prompt."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["upsert", "delete"]},
                "id": {"type": "string", "minLength": 1, "maxLength": 64},
                "content": {"type": "string", "minLength": 1, "maxLength": 400},
                "topic": {"type": "string", "enum": list(_TOPICS)},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
        # A new note is allowed without an approval prompt in workspace and YOLO modes; the store
        # enforces size, count, duplicates and secret filtering, and the user can review every note.
        side_effect="session_state",
        capability=Capability.MEMORY_WRITE,
    )

    def __init__(self) -> None:
        self._saves: OrderedDict[str, int] = OrderedDict()

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def prepare_for_approval(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Deleting a memory, or rewriting one the user wrote themselves, asks the user first: the
        policy asks for a call marked _confirm_change, and the approval shows the memory."""
        memory_id = arguments.get("id")
        if arguments.get("action") not in ("upsert", "delete") or not isinstance(memory_id, str):
            return dict(arguments)
        items = _store().snapshot()["items"]
        item = next((entry for entry in items if entry["id"] == memory_id), None)
        if item is None:
            return dict(arguments)  # Refused when it runs: no memory has that id.
        if arguments["action"] == "delete":
            kind = "delete_memory"
        elif item.get("source") == "user":
            kind = "replace_memory"
        else:
            return dict(arguments)
        return {**arguments, "_confirm_change": {"kind": kind, "text": item["content"]}}

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolArgumentError("memory_write requires an active task")

    def _count_save(self, context: Any) -> None:
        from mobile_memory import AUTO_SAVES_PER_TASK

        key = f"{getattr(context, 'session_id', '')}:{getattr(context, 'correlation_id', '')}"
        used = self._saves.get(key, 0)
        if used >= AUTO_SAVES_PER_TASK:
            raise ToolError(
                f"only {AUTO_SAVES_PER_TASK} memory saves or deletions are allowed per task; "
                "combine related facts, or tell the user they can change more on the Memory page"
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
            if action not in ("upsert", "delete"):
                raise ToolArgumentError("action must be upsert or delete")
            if action == "delete" and not memory_id:
                raise ToolArgumentError("delete needs the id of the memory to remove")
            # Deletions count too: where nobody is asked (full access), one task must not be able to
            # empty the user's memory.
            self._count_save(context)
            if action == "delete":
                store.delete(memory_id)
                return json_result({"deleted": memory_id})
            topic = arguments.get("topic")
            if memory_id:
                # A memory the user wrote stays theirs once they approved the new wording, so the
                # next rewrite asks again.
                confirmed = arguments.get("_confirm_change") or {}
                source = None if confirmed.get("kind") == "replace_memory" else "auto"
                item = store.update(memory_id, arguments.get("content"), source=source, topic=topic)
                return json_result({"updated": item})
            item = store.add(arguments.get("content"), source="auto", topic=topic)
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
