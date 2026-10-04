from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent_workspace.application.ports import EventStore, ToolExecutionContext
from agent_workspace.core.events import Event, validate_event_payload
from agent_workspace.core.models import Capability, MemoryItem, ToolSpec
from agent_workspace.core.ranking import rank_by_bm25

from .base import ToolArgumentError, json_result, optional_int, require_string


async def _rank_memories(
    query: str,
    memories: list[MemoryItem],
    limit: int,
    *,
    workspace: str | None = None,
) -> list[MemoryItem]:
    if not query.strip() or len(memories) <= 1:
        return memories[:limit]
    documents = [memory.content for memory in memories]
    try:
        from agent_workspace.core.embeddings import (
            EmbeddingIndexError,
            EmbeddingsUnavailableError,
            configured_embedding_client,
            semantic_rank,
        )

        client = await configured_embedding_client()
        if client is not None:
            try:
                index = None
                if workspace:
                    from agent_workspace.core.embeddings import EmbeddingIndex

                    index = EmbeddingIndex(Path(workspace) / ".agent" / "memory-embeddings.json")
                order = await semantic_rank(
                    client,
                    query,
                    documents,
                    index=index,
                    item_ids=[memory.id for memory in memories],
                )
                return [memories[index] for index in order][:limit]
            except (EmbeddingIndexError, EmbeddingsUnavailableError):
                pass
            finally:
                await client.aclose()
    except ImportError:
        pass
    order = rank_by_bm25(query, documents)
    return [memories[index] for index in order][:limit]


class MemorySearchTool:
    _SPEC = ToolSpec(
        name="memory_search",
        description=(
            "Search explicit long-term memory for the current workspace. Memory is not loaded "
            "automatically; results may contain stale user-authored context."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "maxLength": 512},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.MEMORY_READ,
    )

    def __init__(self, store: EventStore) -> None:
        self._store = store

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolArgumentError("memory_search requires an active session context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        session = self._store.get_session(context.session_id)
        if session is None:
            raise ToolArgumentError("memory_search requires an active session")
        query = arguments.get("query", "")
        if not isinstance(query, str) or len(query) > 512:
            raise ToolArgumentError("'query' must be a string of at most 512 characters")
        limit = optional_int(arguments, "limit", 20, minimum=1, maximum=100)
        memories = self._store.list_memories(session.workspace, query=query, limit=100)
        ranked = await _rank_memories(query, memories, limit, workspace=session.workspace)
        return json_result({"memories": [_memory_data(memory) for memory in ranked]})


class MemoryWriteTool:
    _SPEC = ToolSpec(
        name="memory_write",
        description=(
            "Create, update, or delete explicit long-term memory for the current workspace. "
            "Use only when the user explicitly asks to remember, update, or forget information."
        ),
        input_schema={
            "oneOf": [
                {
                    "type": "object",
                    "properties": {
                        "action": {"const": "upsert"},
                        "id": {"type": "string", "minLength": 1, "maxLength": 128},
                        "content": {"type": "string", "minLength": 1, "maxLength": 10000},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1, "maxLength": 64},
                            "maxItems": 16,
                            "uniqueItems": True,
                        },
                        "expires_at": {"type": "string", "maxLength": 64},
                        "ttl_seconds": {"type": "number", "minimum": 1},
                    },
                    "required": ["action", "content"],
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "properties": {
                        "action": {"const": "delete"},
                        "id": {"type": "string", "minLength": 1, "maxLength": 128},
                    },
                    "required": ["action", "id"],
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "properties": {"action": {"const": "export"}},
                    "required": ["action"],
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "properties": {
                        "action": {"const": "forget"},
                        "id": {"type": "string", "minLength": 1, "maxLength": 128},
                    },
                    "required": ["action", "id"],
                    "additionalProperties": False,
                },
            ]
        },
        side_effect="memory_write",
        capability=Capability.MEMORY_WRITE,
        provider_input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["upsert", "delete", "forget", "export"]},
                "id": {"type": "string"},
                "content": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "expires_at": {"type": "string"},
                "ttl_seconds": {"type": "number", "minimum": 1},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    )

    def __init__(self, store: EventStore) -> None:
        self._store = store

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolArgumentError("memory_write requires an active session context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        session = self._store.get_session(context.session_id)
        if session is None:
            raise ToolArgumentError("memory_write requires an active session")
        action = require_string(arguments, "action")
        if action == "export":
            memories = self._store.list_memories(session.workspace, limit=500)
            return json_result({"memories": [_memory_data(memory) for memory in memories]})
        if action == "forget":
            action = "delete"
        if action == "delete":
            memory_id = require_string(arguments, "id")
            if (
                self._store.get_memory(session.workspace, memory_id) is None
                and self._store.get_memory_owner_workspace(memory_id) != session.workspace
            ):
                raise ToolArgumentError(f"unknown memory id: {memory_id}")
            await self._record(
                context,
                "memory.deleted",
                {"memory_id": memory_id, "workspace": session.workspace},
            )
            return json_result({"memory_id": memory_id, "deleted": True})
        if action != "upsert":
            raise ToolArgumentError(f"unsupported memory action: {action}")

        memory_id = arguments.get("id", str(uuid4()))
        if not isinstance(memory_id, str) or not memory_id:
            raise ToolArgumentError("'id' must be a non-empty string")
        owner_workspace = self._store.get_memory_owner_workspace(memory_id)
        if owner_workspace is not None and owner_workspace != session.workspace:
            raise ToolArgumentError("memory id belongs to a different workspace")
        content = require_string(arguments, "content")
        tags = arguments.get("tags", [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise ToolArgumentError("'tags' must be an array of strings")
        expires_at = arguments.get("expires_at")
        ttl_seconds = arguments.get("ttl_seconds")
        if expires_at is not None and (not isinstance(expires_at, str) or not expires_at.strip()):
            raise ToolArgumentError("'expires_at' must be an ISO timestamp")
        if ttl_seconds is not None:
            if (
                isinstance(ttl_seconds, bool)
                or not isinstance(ttl_seconds, (int, float))
                or ttl_seconds <= 0
            ):
                raise ToolArgumentError("'ttl_seconds' must be positive")
            if expires_at is not None:
                raise ToolArgumentError("provide either 'expires_at' or 'ttl_seconds', not both")
            expires_at = (datetime.now(UTC) + timedelta(seconds=float(ttl_seconds))).isoformat()
        if expires_at is not None:
            try:
                parsed_expiry = datetime.fromisoformat(expires_at)
            except ValueError:
                raise ToolArgumentError("'expires_at' must be an ISO timestamp") from None
            if parsed_expiry.tzinfo is None:
                raise ToolArgumentError("'expires_at' must include a timezone")
            expires_at = parsed_expiry.astimezone(UTC).isoformat()
        await self._record(
            context,
            "memory.upserted",
            {
                "memory_id": memory_id,
                "workspace": session.workspace,
                "content": content,
                "tags": tags,
                "expires_at": expires_at,
            },
        )
        return json_result({"memory_id": memory_id, "saved": True})

    @staticmethod
    async def _record(
        context: ToolExecutionContext,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        data["attempt_id"] = context.attempt_id
        event = Event(
            session_id=context.session_id,
            type=event_type,
            data=data,
            causation_id=context.started_event_id,
            correlation_id=context.correlation_id,
        )
        try:
            validate_event_payload(event.type, event.data)
        except ValueError as exc:
            raise ToolArgumentError(str(exc)) from None
        await context.record_event(event)


def _memory_data(memory: MemoryItem) -> dict[str, object]:
    return {
        "id": memory.id,
        "content": memory.content,
        "tags": list(memory.tags),
        "source_session_id": memory.source_session_id,
        "updated_by_session_id": memory.updated_by_session_id,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
        "expires_at": memory.expires_at,
    }
