from __future__ import annotations

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
_SCAN_LIMIT = 200
_PAGE_SIZE = 100


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class SessionHistoryTool:
    _SPEC = ToolSpec(
        name="session_history",
        description=(
            "Search and read stored messages and tool lifecycle events in the active session. "
            "Search returns event sequences; read retrieves a stored field in character chunks. "
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
            return self._search(context.session_id, arguments)
        return self._read(context.session_id, arguments)

    def _search(self, session_id: str, arguments: dict[str, Any]) -> str:
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
                for field, source in self._fields(event):
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
        has_more = last_sequence is not None and bool(
            self._store.list_events_paged(session_id, cursor=last_sequence, limit=1)
        )
        return json_result(
            {
                "matches": matches,
                "next_cursor": last_sequence if has_more else None,
                "scanned": scanned,
                "scan_limit": _SCAN_LIMIT,
            }
        )

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
            raise ToolArgumentError("field is not readable for this event")
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
