from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from agent_workspace.core.models import (
    MAX_IMAGE_BYTES,
    Autonomy,
    ContentSensitivity,
    ContentTrust,
    Mode,
    Role,
)

CURRENT_EVENT_SCHEMA_VERSION = 1
_MAX_RESEARCH_ARTIFACT_BYTES = 128 * 1024
_RESEARCH_MEDIA_TYPES = frozenset(
    {
        "application/json",
        "application/xml",
        "text/csv",
        "text/html",
        "text/markdown",
        "text/plain",
        "text/xml",
    }
)
_WEB_FETCH_RECEIPT_FIELDS = (
    "source_id",
    "url",
    "title",
    "content",
    "artifact_sha256",
    "response_sha256",
    "response_bytes",
    "media_type",
    "fetched_at",
    "truncated",
)


def web_fetch_receipt_matches(raw_result: object, source_data: dict[str, Any]) -> bool:
    if not isinstance(raw_result, str):
        return False
    try:
        result = json.loads(raw_result)
    except json.JSONDecodeError:
        return False
    if not isinstance(result, dict):
        return False
    source = result.get("source")
    if not isinstance(source, dict):
        return False
    receipt = {
        "source_id": source.get("id"),
        "url": source.get("url"),
        "title": source.get("title"),
        "content": result.get("content"),
        "artifact_sha256": source.get("artifact_sha256"),
        "response_sha256": source.get("response_sha256"),
        "response_bytes": source.get("response_bytes"),
        "media_type": result.get("media_type"),
        "fetched_at": source.get("fetched_at"),
        "truncated": result.get("truncated"),
    }
    return receipt == {key: source_data.get(key) for key in _WEB_FETCH_RECEIPT_FIELDS}


def web_fetch_receipt_source_id(raw_result: object) -> str | None:
    if not isinstance(raw_result, str):
        return None
    try:
        result = json.loads(raw_result)
    except json.JSONDecodeError:
        return None
    if not isinstance(result, dict):
        return None
    source = result.get("source")
    if not isinstance(source, dict):
        return None
    source_id = source.get("id")
    return source_id if isinstance(source_id, str) else None


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_aware_timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _validate_research_source(data: dict[str, Any]) -> None:
    source_id = data.get("source_id")
    url = data.get("url")
    title = data.get("title")
    content = data.get("content")
    artifact_sha256 = data.get("artifact_sha256")
    response_sha256 = data.get("response_sha256")
    response_bytes = data.get("response_bytes")
    media_type = data.get("media_type")
    fetched_at = data.get("fetched_at")
    truncated = data.get("truncated")
    summary = data.get("summary")
    attempt_id = data.get("attempt_id")
    try:
        parsed_url = urlsplit(url) if isinstance(url, str) else None
        url_valid = (
            parsed_url is not None
            and parsed_url.scheme == "https"
            and parsed_url.hostname is not None
            and parsed_url.username is None
            and parsed_url.password is None
            and parsed_url.fragment == ""
            and parsed_url.port in {None, 443}
        )
    except ValueError:
        url_valid = False
    content_bytes = content.encode("utf-8") if isinstance(content, str) else b""
    expected_source_id = (
        hashlib.sha256(f"{url}\n{artifact_sha256}".encode()).hexdigest()
        if isinstance(url, str) and isinstance(artifact_sha256, str)
        else None
    )
    if (
        not _is_sha256(source_id)
        or source_id != expected_source_id
        or not url_valid
        or not isinstance(url, str)
        or len(url) > 4096
        or (title is not None and (not isinstance(title, str) or len(title) > 500))
        or not isinstance(content, str)
        or len(content_bytes) > _MAX_RESEARCH_ARTIFACT_BYTES
        or not _is_sha256(artifact_sha256)
        or hashlib.sha256(content_bytes).hexdigest() != artifact_sha256
        or not _is_sha256(response_sha256)
        or not isinstance(response_bytes, int)
        or isinstance(response_bytes, bool)
        or response_bytes < 0
        or response_bytes > _MAX_RESEARCH_ARTIFACT_BYTES + 1
        or not isinstance(media_type, str)
        or (
            media_type not in _RESEARCH_MEDIA_TYPES
            and not media_type.endswith("+json")
            and not media_type.endswith("+xml")
        )
        or not _is_aware_timestamp(fetched_at)
        or not isinstance(truncated, bool)
        or not isinstance(summary, str)
        or len(summary) > 10_000
        or (attempt_id is not None and (not isinstance(attempt_id, str) or not attempt_id))
    ):
        raise ValueError("research.source.saved contains invalid source metadata")


def _validate_citation(data: dict[str, Any]) -> None:
    citation_id = data.get("citation_id")
    source_id = data.get("source_id")
    claim = data.get("claim")
    locator = data.get("locator")
    quote = data.get("quote")
    attempt_id = data.get("attempt_id")
    if (
        not isinstance(citation_id, str)
        or not citation_id
        or len(citation_id) > 128
        or not _is_sha256(source_id)
        or not isinstance(claim, str)
        or not claim
        or len(claim) > 10_000
        or (locator is not None and (not isinstance(locator, str) or len(locator) > 2000))
        or (quote is not None and (not isinstance(quote, str) or len(quote) > 10_000))
        or (attempt_id is not None and (not isinstance(attempt_id, str) or not attempt_id))
    ):
        raise ValueError("research.citation.added contains invalid citation metadata")


def _validate_memory_event(event_type: str, data: dict[str, Any]) -> None:
    memory_id = data.get("memory_id")
    workspace = data.get("workspace")
    attempt_id = data.get("attempt_id")
    if (
        not isinstance(memory_id, str)
        or not memory_id
        or len(memory_id) > 128
        or not isinstance(workspace, str)
        or not workspace
        or len(workspace) > 32767
        or (attempt_id is not None and (not isinstance(attempt_id, str) or not attempt_id))
    ):
        raise ValueError(f"{event_type} contains invalid memory metadata")
    if event_type == "memory.deleted":
        return
    expires_at = data.get("expires_at")
    if expires_at is not None:
        if not isinstance(expires_at, str) or len(expires_at) > 64:
            raise ValueError("memory.upserted contains invalid expiration")
        try:
            parsed_expiry = datetime.fromisoformat(expires_at)
        except ValueError:
            raise ValueError("memory.upserted contains invalid expiration") from None
        if parsed_expiry.tzinfo is None:
            raise ValueError("memory.upserted contains invalid expiration")
    content = data.get("content")
    tags = data.get("tags")
    if (
        not isinstance(content, str)
        or not content
        or len(content) > 10_000
        or not isinstance(tags, list)
        or len(tags) > 16
        or any(not isinstance(tag, str) or not tag or len(tag) > 64 for tag in tags)
        or len({tag.casefold() for tag in tags}) != len(tags)
    ):
        raise ValueError("memory.upserted contains invalid memory content")


def _validate_image_attached(data: dict[str, Any]) -> None:
    sha256 = data.get("sha256")
    byte_count = data.get("bytes")
    media_type = data.get("media_type")
    path = data.get("path")
    attempt_id = data.get("attempt_id")
    if (
        not _is_sha256(sha256)
        or type(byte_count) is not int
        or not 1 <= byte_count <= MAX_IMAGE_BYTES
        or media_type not in {"image/png", "image/jpeg", "image/gif", "image/webp"}
        or not isinstance(path, str)
        or not path
        or len(path) > 4096
        or not isinstance(attempt_id, str)
        or not attempt_id
        or len(attempt_id) > 128
    ):
        raise ValueError("image.attached contains invalid image metadata")


def _validate_context_compacted(data: dict[str, Any]) -> None:
    summary = data.get("summary")
    if (
        type(data.get("original_bytes")) is not int
        or data["original_bytes"] < 0
        or type(data.get("compacted_bytes")) is not int
        or data["compacted_bytes"] < 0
        or type(data.get("dropped_messages")) is not int
        or data["dropped_messages"] < 0
        or type(data.get("retained_messages")) is not int
        or data["retained_messages"] < 0
        or not isinstance(data.get("summarized"), bool)
        or (
            summary is not None
            and (not isinstance(summary, str) or len(summary.encode("utf-8")) > 16 * 1024)
        )
    ):
        raise ValueError("context.compacted contains invalid compaction metadata")


def _validate_session_comment(data: dict[str, Any]) -> None:
    comment_id = data.get("comment_id")
    text = data.get("text")
    author = data.get("author")
    if (
        not isinstance(comment_id, str)
        or not comment_id
        or len(comment_id) > 128
        or not isinstance(text, str)
        or not text.strip()
        or len(text) > 4000
        or not isinstance(author, str)
        or not author.strip()
        or len(author) > 200
    ):
        raise ValueError("session.comment.added contains invalid comment metadata")


def _validate_turn_event(event_type: str, data: dict[str, Any]) -> None:
    if event_type == "turn.started":
        if "model" in data or "provider" in data or "mode" in data:
            raw_mode = data.get("mode")
            try:
                mode_valid = isinstance(raw_mode, str) and Mode(raw_mode) is not None
            except ValueError:
                mode_valid = False
            agent_id = data.get("agent_id")
            if (
                not isinstance(data.get("model"), str)
                or not data["model"]
                or len(data["model"]) > 512
                or not mode_valid
                or not isinstance(data.get("provider"), str)
                or not data["provider"]
                or len(data["provider"]) > 128
                or (agent_id is not None and (not isinstance(agent_id, str) or len(agent_id) > 128))
                or not isinstance(data.get("continuation"), bool)
            ):
                raise ValueError("turn.started contains invalid turn metadata")
        return
    if event_type == "turn.completed":
        for key in ("model_calls", "provider_attempts", "tool_calls"):
            if key in data and (type(data.get(key)) is not int or data[key] < 0):
                raise ValueError("turn.completed contains invalid turn metadata")
        return
    if event_type == "turn.failed":
        if ("error_type" in data or "message" in data) and (
            not isinstance(data.get("error_type"), str)
            or not data["error_type"]
            or len(data["error_type"]) > 256
            or not isinstance(data.get("message"), str)
            or len(data["message"].encode("utf-8")) > 4000
        ):
            raise ValueError("turn.failed contains invalid turn metadata")
        return
    if event_type == "turn.cancelled":
        if "reason" in data and (
            not isinstance(data.get("reason"), str) or len(data["reason"]) > 2000
        ):
            raise ValueError("turn.cancelled contains invalid turn metadata")
        return
    raise ValueError(f"{event_type} is not a recognized turn event")


def _validate_model_output_delta(data: dict[str, Any]) -> None:
    if (
        data.get("kind") not in {"text", "reasoning"}
        or not isinstance(data.get("text"), str)
        or len(data["text"].encode("utf-8")) > 1024 * 1024
    ):
        raise ValueError("model.output.delta contains invalid delta metadata")


def _validate_file_rollback(event_type: str, data: dict[str, Any]) -> None:
    reason = data.get("reason")
    outcome = data.get("outcome")
    if (
        not isinstance(data.get("attempt_id"), str)
        or not data["attempt_id"]
        or len(data["attempt_id"]) > 128
        or not isinstance(data.get("tool_call_id"), str)
        or not data["tool_call_id"]
        or len(data["tool_call_id"]) > 128
        or not isinstance(data.get("name"), str)
        or not data["name"]
        or len(data["name"]) > 128
        or not isinstance(data.get("path"), str)
        or not data["path"]
        or len(data["path"]) > 4096
        or (data.get("preimage_sha256") is not None and not _is_sha256(data.get("preimage_sha256")))
        or (
            data.get("postimage_sha256") is not None
            and not _is_sha256(data.get("postimage_sha256"))
        )
        or (
            event_type == "file.rollback.conflicted"
            and (not isinstance(reason, str) or len(reason) > 4000)
        )
        or (
            event_type == "file.rollback.recovered"
            and (not isinstance(outcome, str) or not outcome or len(outcome) > 128)
        )
    ):
        raise ValueError(f"{event_type} contains invalid rollback metadata")


def validate_event_payload(event_type: str, data: dict[str, Any]) -> None:
    from agent_workspace.core.background_jobs import validate_background_job_event
    from agent_workspace.core.orchestration import validate_orchestration_event
    from agent_workspace.core.sandbox_changes import validate_sandbox_changeset_event

    if validate_orchestration_event(event_type, data):
        return
    if validate_background_job_event(event_type, data):
        return
    if validate_sandbox_changeset_event(event_type, data):
        return
    if event_type in {"memory.upserted", "memory.deleted"}:
        _validate_memory_event(event_type, data)
        return
    if event_type == "research.source.saved":
        _validate_research_source(data)
        return
    if event_type == "research.citation.added":
        _validate_citation(data)
        return
    if event_type == "image.attached":
        _validate_image_attached(data)
        return
    if event_type == "context.compacted":
        _validate_context_compacted(data)
        return
    if event_type == "context.rewound":
        # Edit-and-resend / regenerate: later context starts again before this user message.
        if (
            not isinstance(data.get("from_event_id"), str)
            or not data["from_event_id"]
            or type(data.get("from_sequence")) is not int
            or data["from_sequence"] <= 0
            or data.get("reason") not in {"edit", "regenerate"}
        ):
            raise ValueError("context.rewound contains invalid rewind metadata")
        return
    if event_type.startswith("task.phase."):
        if (
            not isinstance(data.get("run_id"), str)
            or not data["run_id"]
            or not isinstance(data.get("phase_id"), str)
            or not data["phase_id"]
            or (
                "progress" in data
                and (type(data["progress"]) is not float and type(data["progress"]) is not int)
            )
        ):
            raise ValueError(f"{event_type} contains invalid phase metadata")
        return
    if event_type == "session.comment.added":
        _validate_session_comment(data)
        return
    if event_type in {"turn.started", "turn.completed", "turn.failed", "turn.cancelled"}:
        _validate_turn_event(event_type, data)
        return
    if event_type == "model.output.delta":
        _validate_model_output_delta(data)
        return
    if event_type in {"file.rollback.recovered", "file.rollback.conflicted"}:
        _validate_file_rollback(event_type, data)
        return
    if event_type == "mode.changed":
        from_mode = data.get("from_mode")
        to_mode = data.get("to_mode")
        try:
            valid = (
                isinstance(from_mode, str)
                and isinstance(to_mode, str)
                and Mode(from_mode) is not Mode(to_mode)
            )
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise ValueError("mode.changed contains invalid mode metadata")
        return
    if event_type == "autonomy.changed":
        from_autonomy = data.get("from_autonomy")
        to_autonomy = data.get("to_autonomy")
        try:
            valid = (
                isinstance(from_autonomy, str)
                and isinstance(to_autonomy, str)
                and Autonomy(from_autonomy) is not Autonomy(to_autonomy)
            )
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise ValueError("autonomy.changed contains invalid autonomy metadata")
        return
    if event_type != "message.created":
        return
    role = data.get("role")
    content = data.get("content")
    reasoning = data.get("reasoning", "")
    tool_call_id = data.get("tool_call_id")
    raw_calls = data.get("tool_calls")
    raw_trust = data.get("trust")
    raw_sensitivity = data.get("sensitivity")
    raw_provider_metadata = data.get("provider_metadata", {})
    if not isinstance(role, str):
        raise ValueError("message.created contains an unsupported role")
    try:
        Role(role)
    except ValueError:
        raise ValueError("message.created contains an unsupported role") from None
    if not isinstance(content, str):
        raise ValueError("message.created contains invalid content")
    if not isinstance(reasoning, str):
        raise ValueError("message.created contains invalid reasoning")
    if tool_call_id is not None and not isinstance(tool_call_id, str):
        raise ValueError("message.created contains an invalid tool call id")
    if not isinstance(raw_calls, list):
        raise ValueError("message.created contains an invalid tool call list")
    if raw_trust is not None:
        try:
            ContentTrust(raw_trust)
        except (TypeError, ValueError):
            raise ValueError("message.created contains invalid trust metadata") from None
    if raw_sensitivity is not None:
        try:
            ContentSensitivity(raw_sensitivity)
        except (TypeError, ValueError):
            raise ValueError("message.created contains invalid sensitivity metadata") from None
    if not isinstance(raw_provider_metadata, dict):
        raise ValueError("message.created contains invalid provider metadata")
    call_ids: set[str] = set()
    for raw_call in raw_calls:
        if not isinstance(raw_call, dict):
            raise ValueError("message.created contains an invalid tool call")
        if (
            not isinstance(raw_call.get("id"), str)
            or not raw_call.get("id")
            or not isinstance(raw_call.get("name"), str)
            or not isinstance(raw_call.get("arguments"), dict)
            or not isinstance(raw_call.get("provider_metadata", {}), dict)
        ):
            raise ValueError("message.created contains an invalid tool call")
        call_id = raw_call["id"]
        if call_id in call_ids:
            raise ValueError("message.created contains duplicate tool call ids")
        call_ids.add(call_id)


@dataclass(frozen=True, slots=True)
class Event:
    session_id: str
    type: str
    data: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: int = CURRENT_EVENT_SCHEMA_VERSION
    sequence: int | None = None
    causation_id: str | None = None
    correlation_id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def with_sequence(self, sequence: int) -> Event:
        return Event(
            id=self.id,
            session_id=self.session_id,
            type=self.type,
            data=self.data,
            schema_version=self.schema_version,
            sequence=sequence,
            causation_id=self.causation_id,
            correlation_id=self.correlation_id,
            created_at=self.created_at,
        )
