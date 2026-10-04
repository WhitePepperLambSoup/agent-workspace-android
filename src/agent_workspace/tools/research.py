from __future__ import annotations

from typing import Any
from uuid import uuid4

from agent_workspace.application.ports import EventStore, ToolExecutionContext
from agent_workspace.core.events import (
    Event,
    validate_event_payload,
    web_fetch_receipt_matches,
    web_fetch_receipt_source_id,
)
from agent_workspace.core.models import Capability, Citation, ResearchSource, ToolSpec

from .base import ToolArgumentError, json_result, optional_int, require_string

_MAX_ARTIFACT_BYTES = 128 * 1024


class SaveResearchSourceTool:
    _SPEC = ToolSpec(
        name="save_research_source",
        description=(
            "Persist one bounded web_fetch result as content-addressed research evidence in the "
            "current session. Metadata and digests must match the fetched content."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "source_id": {"type": "string", "pattern": "^[0-9a-fA-F]{64}$"},
                "url": {"type": "string", "minLength": 1, "maxLength": 4096},
                "title": {"type": ["string", "null"], "maxLength": 500},
                "content": {"type": "string", "maxLength": _MAX_ARTIFACT_BYTES},
                "artifact_sha256": {"type": "string", "pattern": "^[0-9a-fA-F]{64}$"},
                "response_sha256": {"type": "string", "pattern": "^[0-9a-fA-F]{64}$"},
                "response_bytes": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": _MAX_ARTIFACT_BYTES + 1,
                },
                "media_type": {"type": "string", "minLength": 1, "maxLength": 255},
                "fetched_at": {"type": "string", "minLength": 1, "maxLength": 64},
                "truncated": {"type": "boolean"},
                "summary": {"type": "string", "maxLength": 10000},
            },
            "required": [
                "source_id",
                "url",
                "content",
                "artifact_sha256",
                "response_sha256",
                "response_bytes",
                "media_type",
                "fetched_at",
                "truncated",
                "summary",
            ],
            "additionalProperties": False,
        },
        side_effect="session_state",
        capability=Capability.RESEARCH_SOURCE,
        provider_input_schema={
            "type": "object",
            "properties": {
                "source_id": {"type": "string"},
                "url": {"type": "string"},
                "title": {"type": "string"},
                "content": {"type": "string"},
                "artifact_sha256": {"type": "string"},
                "response_sha256": {"type": "string"},
                "response_bytes": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": _MAX_ARTIFACT_BYTES + 1,
                },
                "media_type": {"type": "string"},
                "fetched_at": {"type": "string"},
                "truncated": {"type": "boolean"},
                "summary": {"type": "string"},
            },
            "required": [
                "source_id",
                "url",
                "content",
                "artifact_sha256",
                "response_sha256",
                "response_bytes",
                "media_type",
                "fetched_at",
                "truncated",
                "summary",
            ],
            "additionalProperties": False,
        },
    )

    def __init__(self, store: EventStore) -> None:
        self._store = store

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolArgumentError("save_research_source requires an active session context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        data: dict[str, Any] = {
            "source_id": require_string(arguments, "source_id").lower(),
            "url": require_string(arguments, "url"),
            "title": arguments.get("title"),
            "content": require_string(arguments, "content", allow_empty=True),
            "artifact_sha256": require_string(arguments, "artifact_sha256").lower(),
            "response_sha256": require_string(arguments, "response_sha256").lower(),
            "response_bytes": arguments.get("response_bytes"),
            "media_type": require_string(arguments, "media_type").casefold(),
            "fetched_at": require_string(arguments, "fetched_at"),
            "truncated": arguments.get("truncated"),
            "summary": require_string(arguments, "summary", allow_empty=True),
            "attempt_id": context.attempt_id,
        }
        if data["title"] is not None and not isinstance(data["title"], str):
            raise ToolArgumentError("'title' must be a string or null")
        self._verify_web_fetch_receipt(context.session_id, data)
        event = Event(
            session_id=context.session_id,
            type="research.source.saved",
            data=data,
            causation_id=context.started_event_id,
            correlation_id=context.correlation_id,
        )
        try:
            validate_event_payload(event.type, event.data)
        except ValueError as exc:
            raise ToolArgumentError(str(exc)) from None
        await context.record_event(event)
        return json_result(
            {
                "source_id": data["source_id"],
                "artifact_sha256": data["artifact_sha256"],
                "saved": True,
            }
        )

    def _verify_web_fetch_receipt(self, session_id: str, data: dict[str, Any]) -> None:
        source_id = data["source_id"]
        for raw_result in self._store.list_settled_tool_results(session_id, "web_fetch"):
            if web_fetch_receipt_source_id(raw_result) != source_id:
                continue
            if not web_fetch_receipt_matches(raw_result, data):
                raise ToolArgumentError(
                    "saved source metadata does not match its web_fetch receipt"
                )
            return
        raise ToolArgumentError("save_research_source requires a matching prior web_fetch receipt")


class ListResearchSourcesTool:
    _SPEC = ToolSpec(
        name="list_research_sources",
        description="List durable research source metadata for the current session.",
        input_schema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 200}},
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.RESEARCH_SOURCE,
    )

    def __init__(self, store: EventStore) -> None:
        self._store = store

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolArgumentError("list_research_sources requires an active session context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        limit = optional_int(arguments, "limit", 100, minimum=1, maximum=200)
        sources = self._store.list_research_sources(context.session_id)
        return json_result(
            {
                "sources": [_source_data(source) for source in sources[:limit]],
                "truncated": len(sources) > limit,
            }
        )


class ReadResearchSourceTool:
    _SPEC = ToolSpec(
        name="read_research_source",
        description="Read a bounded slice of one saved research source artifact.",
        input_schema={
            "type": "object",
            "properties": {
                "source_id": {"type": "string", "pattern": "^[0-9a-fA-F]{64}$"},
                "offset": {"type": "integer", "minimum": 0},
                "max_chars": {"type": "integer", "minimum": 1, "maximum": 32768},
            },
            "required": ["source_id"],
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.RESEARCH_SOURCE,
    )

    def __init__(self, store: EventStore) -> None:
        self._store = store

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolArgumentError("read_research_source requires an active session context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        source_id = require_string(arguments, "source_id").lower()
        source = next(
            (
                item
                for item in self._store.list_research_sources(context.session_id)
                if item.id == source_id
            ),
            None,
        )
        if source is None:
            raise ToolArgumentError(f"unknown research source id: {source_id}")
        artifact = self._store.get_text_artifact(source.artifact_sha256)
        if artifact is None:
            raise ToolArgumentError("research source artifact is unavailable")
        try:
            content = artifact.content.decode("utf-8")
        except UnicodeDecodeError:
            raise ToolArgumentError("research source artifact is not valid UTF-8") from None
        offset = optional_int(arguments, "offset", 0, minimum=0, maximum=_MAX_ARTIFACT_BYTES)
        maximum = optional_int(arguments, "max_chars", 16000, minimum=1, maximum=32768)
        retained = content[offset : offset + maximum]
        return json_result(
            {
                "source": _source_data(source),
                "content": retained,
                "offset": offset,
                "total_chars": len(content),
                "truncated": offset + len(retained) < len(content),
            }
        )


class AddCitationTool:
    _SPEC = ToolSpec(
        name="add_citation",
        description=(
            "Add a durable claim-to-source citation. If quote is provided, it must occur exactly "
            "in the saved source artifact."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "source_id": {"type": "string", "pattern": "^[0-9a-fA-F]{64}$"},
                "claim": {"type": "string", "minLength": 1, "maxLength": 10000},
                "locator": {"type": "string", "maxLength": 2000},
                "quote": {"type": "string", "maxLength": 10000},
            },
            "required": ["source_id", "claim"],
            "additionalProperties": False,
        },
        side_effect="session_state",
        capability=Capability.CITATION,
    )

    def __init__(self, store: EventStore) -> None:
        self._store = store

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolArgumentError("add_citation requires an active session context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        source_id = require_string(arguments, "source_id").lower()
        source = next(
            (
                item
                for item in self._store.list_research_sources(context.session_id)
                if item.id == source_id
            ),
            None,
        )
        if source is None:
            raise ToolArgumentError(f"unknown research source id: {source_id}")
        claim = require_string(arguments, "claim")
        locator = arguments.get("locator")
        quote = arguments.get("quote")
        if locator is not None and not isinstance(locator, str):
            raise ToolArgumentError("'locator' must be a string")
        if quote is not None and not isinstance(quote, str):
            raise ToolArgumentError("'quote' must be a string")
        if quote:
            artifact = self._store.get_text_artifact(source.artifact_sha256)
            if artifact is None or quote not in artifact.content.decode("utf-8"):
                raise ToolArgumentError("citation quote does not occur in the saved source")
        citation_id = str(uuid4())
        event = Event(
            session_id=context.session_id,
            type="research.citation.added",
            data={
                "citation_id": citation_id,
                "source_id": source_id,
                "claim": claim,
                "locator": locator,
                "quote": quote,
                "attempt_id": context.attempt_id,
            },
            causation_id=context.started_event_id,
            correlation_id=context.correlation_id,
        )
        try:
            validate_event_payload(event.type, event.data)
        except ValueError as exc:
            raise ToolArgumentError(str(exc)) from None
        await context.record_event(event)
        return json_result({"citation_id": citation_id, "source_id": source_id, "saved": True})


class ListCitationsTool:
    _SPEC = ToolSpec(
        name="list_citations",
        description="List durable citations for the current research session.",
        input_schema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 500}},
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.CITATION,
    )

    def __init__(self, store: EventStore) -> None:
        self._store = store

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        raise ToolArgumentError("list_citations requires an active session context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        limit = optional_int(arguments, "limit", 200, minimum=1, maximum=500)
        citations = self._store.list_citations(context.session_id)
        return json_result(
            {
                "citations": [_citation_data(citation) for citation in citations[:limit]],
                "truncated": len(citations) > limit,
            }
        )


def _source_data(source: ResearchSource) -> dict[str, object]:
    return {
        "id": source.id,
        "url": source.url,
        "title": source.title,
        "artifact_sha256": source.artifact_sha256,
        "artifact_bytes": source.artifact_bytes,
        "response_sha256": source.response_sha256,
        "response_bytes": source.response_bytes,
        "media_type": source.media_type,
        "fetched_at": source.fetched_at,
        "truncated": source.truncated,
        "summary": source.summary,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


def _citation_data(citation: Citation) -> dict[str, object]:
    return {
        "id": citation.id,
        "source_id": citation.source_id,
        "claim": citation.claim,
        "locator": citation.locator,
        "quote": citation.quote,
        "created_at": citation.created_at,
    }
