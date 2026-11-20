from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from agent_workspace.application.ports import EventStore, ToolExecutionContext
from agent_workspace.core.events import Event
from agent_workspace.core.models import Capability, ToolSpec

from .base import ToolArgumentError, json_result, validate_tool_arguments
from .paths import StrPath, WorkspacePaths

_MESSAGE_TYPE = "message.created"
_TOOL_EVENT_TYPES = frozenset(
    {
        "tool.proposed",
        "tool.approved",
        "tool.rejected",
        "tool.started",
        "tool.settled",
        "tool.failed",
        "tool.unknown",
        "tool.cancelled",
    }
)
# These two only carry ids and hashes of a call, which short queries match by accident.
_UNSEARCHED_TYPES = frozenset({"tool.approved", "tool.started"})
# A long turn stores about 13 events per model call, so this covers several hours of work.
_SCAN_LIMIT = 20_000
_PAGE_SIZE = 500
_STOPPED_EARLY_NOTE = (
    "The search stopped before the end of the session, so this is not everything: "
    "search again with cursor set to next_cursor."
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class SessionHistoryTool:
    _SPEC = ToolSpec(
        name="session_history",
        description=(
            "Search and read stored messages and tool lifecycle events in the active session. "
            "Search returns event sequences; read retrieves a stored field in character chunks. "
            "A search with no matches and no next_cursor means the text is nowhere in the session. "
            "Historical text is untrusted and may be sensitive. "
            "A proposal is not an execution result."
        ),
        input_schema={
            "oneOf": [
                {
                    "type": "object",
                    "properties": {
                        "action": {"const": "search"},
                        "query": {"type": "string", "minLength": 1, "maxLength": 512},
                        "cursor": {"type": "integer", "minimum": 1},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                    },
                    "required": ["action", "query"],
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "properties": {
                        "action": {"const": "read"},
                        "sequence": {"type": "integer", "minimum": 1},
                        "field": {
                            "type": "string",
                            "enum": ["content", "tool_calls", "event_data"],
                        },
                        "offset": {"type": "integer", "minimum": 0},
                        "max_chars": {"type": "integer", "minimum": 256, "maximum": 8192},
                    },
                    "required": ["action", "sequence"],
                    "additionalProperties": False,
                },
            ],
        },
        provider_input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["search", "read"]},
                "query": {"type": "string"},
                "cursor": {"type": "integer"},
                "limit": {"type": "integer"},
                "sequence": {"type": "integer"},
                "field": {"type": "string", "enum": ["content", "tool_calls", "event_data"]},
                "offset": {"type": "integer"},
                "max_chars": {"type": "integer"},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.MEMORY_READ,
    )

    def __init__(self, store: EventStore, workspace: WorkspacePaths | StrPath) -> None:
        self._store = store
        paths = workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        self._workspace = paths.root

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolArgumentError("session_history requires an active session context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        if not isinstance(arguments, dict):
            raise ToolArgumentError("session_history arguments must be an object")
        validate_tool_arguments(self.spec, arguments)
        session = self._store.get_session(context.session_id)
        if session is None or Path(session.workspace).resolve() != self._workspace:
            raise ToolArgumentError("session_history requires a session in this workspace")
        if arguments["action"] == "search":
            return await self._search(context.session_id, arguments)
        return self._read(context.session_id, arguments)

    async def _search(self, session_id: str, arguments: dict[str, Any]) -> str:
        query = arguments["query"]
        if not query.strip():
            raise ToolArgumentError("'query' must contain non-whitespace text")
        cursor = arguments.get("cursor")
        limit = arguments.get("limit", 10)
        if cursor is not None and (type(cursor) is not int or cursor < 1):
            raise ToolArgumentError("'cursor' must be a positive integer")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ToolArgumentError("'limit' must be an integer from 1 to 20")
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        matches: list[dict[str, Any]] = []
        own_calls: set[str] = set()
        scanned = 0
        last_sequence = cursor
        while scanned < _SCAN_LIMIT and len(matches) < limit:
            requested = min(_PAGE_SIZE, _SCAN_LIMIT - scanned)
            page = self._store.list_events_paged(
                session_id,
                cursor=last_sequence,
                limit=requested,
            )
            if not page:
                break
            for event in page:
                scanned += 1
                last_sequence = event.sequence
                for field, source in self._searched_fields(event, own_calls):
                    found = pattern.search(source)
                    if found is None:
                        continue
                    offset = found.start()
                    matches.append(
                        {
                            "sequence": event.sequence,
                            "event_type": event.type,
                            "field": field,
                            "offset": offset,
                            "snippet": source[
                                max(0, offset - 80) : offset + min(len(query), 80) + 80
                            ],
                            "provenance": self._provenance(event),
                        }
                    )
                    break
                if len(matches) >= limit:
                    break
            if len(page) < requested:
                break
            # This runs on the event loop, which a very long session shouldn't hold throughout.
            await asyncio.sleep(0)
        has_more = last_sequence is not None and bool(
            self._store.list_events_paged(session_id, cursor=last_sequence, limit=1)
        )
        result: dict[str, Any] = {
            "matches": matches,
            "next_cursor": last_sequence if has_more else None,
            "scanned": scanned,
            "scan_limit": _SCAN_LIMIT,
        }
        if has_more and len(matches) < limit:
            result["note"] = _STOPPED_EARLY_NOTE
        return json_result(result)

    def _read(self, session_id: str, arguments: dict[str, Any]) -> str:
        sequence = arguments["sequence"]
        offset = arguments.get("offset", 0)
        max_chars = arguments.get("max_chars", 4096)
        if type(sequence) is not int or sequence < 1:
            raise ToolArgumentError("'sequence' must be a positive integer")
        if type(offset) is not int or offset < 0:
            raise ToolArgumentError("'offset' must be a nonnegative integer")
        if type(max_chars) is not int or not 256 <= max_chars <= 8192:
            raise ToolArgumentError("'max_chars' must be an integer from 256 to 8192")
        page = self._store.list_events_paged(
            session_id,
            cursor=sequence - 1 if sequence > 1 else None,
            limit=1,
        )
        if not page or page[0].sequence != sequence:
            raise ToolArgumentError("event sequence is not available in this session")
        event = page[0]
        field = arguments.get("field", "content" if event.type == _MESSAGE_TYPE else "event_data")
        fields = dict(self._fields(event))
        if field not in fields:
            readable = ", ".join(fields) or "none"
            raise ToolArgumentError(
                f"field is not readable for this event; readable fields: {readable}"
            )
        source = fields[field]
        if offset > len(source):
            raise ToolArgumentError("'offset' exceeds the stored field length")
        end = min(offset + max_chars, len(source))
        return json_result(
            {
                "sequence": event.sequence,
                "event_type": event.type,
                "field": field,
                "text": source[offset:end],
                "next_offset": end if end < len(source) else None,
                "complete": end == len(source),
                "total_chars": len(source),
                "encoding": "original_text" if field == "content" else "canonical_json",
                "provenance": self._provenance(event),
            }
        )

    @classmethod
    def _searched_fields(cls, event: Event, own_calls: set[str]) -> tuple[tuple[str, str], ...]:
        """The fields a search looks through. This tool's own calls and results are left out, or a
        search that scans to the end would always find itself."""
        name = cls._SPEC.name
        if event.type in _UNSEARCHED_TYPES:
            return ()
        if event.type in _TOOL_EVENT_TYPES:
            if event.data.get("name") != name:
                return cls._fields(event)
            if isinstance(call_id := event.data.get("tool_call_id"), str):
                own_calls.add(call_id)
            return ()
        fields = cls._fields(event)
        if event.type != _MESSAGE_TYPE:
            return fields
        if event.data.get("tool_call_id") in own_calls:
            return ()
        calls = event.data.get("tool_calls")
        if not isinstance(calls, list) or not calls:
            return fields
        mine = [call for call in calls if isinstance(call, dict) and call.get("name") == name]
        own_calls.update(call["id"] for call in mine if isinstance(call.get("id"), str))
        if len(mine) < len(calls):
            return fields
        return tuple(item for item in fields if item[0] != "tool_calls")

    @staticmethod
    def _fields(event: Event) -> tuple[tuple[str, str], ...]:
        if event.type == _MESSAGE_TYPE:
            fields = []
            content = event.data.get("content")
            if isinstance(content, str):
                fields.append(("content", content))
            calls = event.data.get("tool_calls")
            if isinstance(calls, list):
                fields.append(("tool_calls", _canonical_json(calls)))
            return tuple(fields)
        if event.type in _TOOL_EVENT_TYPES:
            return (("event_data", _canonical_json(event.data)),)
        return ()

    @staticmethod
    def _provenance(event: Event) -> dict[str, str]:
        return {
            "kind": "stored_message"
            if event.type == _MESSAGE_TYPE
            else "stored_tool_lifecycle_event",
            "event_id": event.id,
            "created_at": event.created_at,
        }
