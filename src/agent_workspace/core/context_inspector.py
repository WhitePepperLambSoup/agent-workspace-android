"""Explainable, content-free accounting for provider context decisions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from agent_workspace.core.models import ChatMessage

ContextStatus = Literal["included", "summarized", "deduplicated", "excluded"]


def _json_size(value: object) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def _estimate_tokens(byte_count: int) -> int:
    return max(1, (byte_count + 2) // 3)


def _summary_message(message: ChatMessage) -> bool:
    lowered = message.content.casefold()
    return "conversation summarized" in lowered or "context-compaction" in lowered


@dataclass(frozen=True, slots=True)
class ContextImageDecision:
    message_index: int
    image_index: int
    digest: str
    media_type: str
    bytes: int
    status: ContextStatus
    reason: str | None
    estimated_tokens: int

    @property
    def id(self) -> str:
        return f"image:{self.message_index}:{self.image_index}"

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "messageIndex": self.message_index,
            "imageIndex": self.image_index,
            "digest": self.digest,
            "mediaType": self.media_type,
            "bytes": self.bytes,
            "status": self.status,
            "reason": self.reason,
            "estimatedTokens": self.estimated_tokens,
        }


@dataclass(frozen=True, slots=True)
class ContextMessageDecision:
    message_index: int
    role: str
    bytes: int
    estimated_tokens: int
    status: ContextStatus
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": f"message:{self.message_index}",
            "messageIndex": self.message_index,
            "role": self.role,
            "bytes": self.bytes,
            "estimatedTokens": self.estimated_tokens,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ContextInspection:
    messages: tuple[ContextMessageDecision, ...]
    images: tuple[ContextImageDecision, ...]
    estimated_bytes: int
    estimated_tokens: int
    context_limit_bytes: int | None
    compacted_messages: int
    summary: str | None

    @property
    def excluded(self) -> tuple[ContextImageDecision, ...]:
        return tuple(image for image in self.images if image.status == "excluded")

    def to_dict(self) -> dict[str, object]:
        return {
            "version": 1,
            "messages": [message.to_dict() for message in self.messages],
            "images": [image.to_dict() for image in self.images],
            "excluded": [image.to_dict() for image in self.excluded],
            "estimatedBytes": self.estimated_bytes,
            "estimatedTokens": self.estimated_tokens,
            "contextLimitBytes": self.context_limit_bytes,
            "compactedMessages": self.compacted_messages,
            "summary": self.summary,
        }


def build_context_inspection(
    messages: Sequence[ChatMessage],
    *,
    context_limit_bytes: int | None = None,
    compacted_messages: int = 0,
    excluded_image_digests: set[str] | frozenset[str] | None = None,
) -> ContextInspection:
    """Build a bounded, content-free explanation of context inclusion decisions.

    The inspection intentionally stores image digests and sizes, never image bytes or
    message text. Duplicate image decisions are calculated before runner-side image
    deduplication so the UI can explain why a later image was not sent.
    """

    excluded_digests = excluded_image_digests or frozenset()
    seen_digests: set[str] = set()
    message_decisions: list[ContextMessageDecision] = []
    image_decisions: list[ContextImageDecision] = []
    estimated_bytes = 0
    summarized_messages = 0

    for message_index, message in enumerate(messages):
        serialized = message.to_dict()
        message_bytes = _json_size(serialized)
        is_summary = _summary_message(message)
        if is_summary:
            summarized_messages += 1
        message_status: ContextStatus = "summarized" if is_summary else "included"
        message_reason = "context_compaction_summary" if is_summary else None
        message_decisions.append(
            ContextMessageDecision(
                message_index=message_index,
                role=message.role.value,
                bytes=message_bytes,
                estimated_tokens=_estimate_tokens(message_bytes),
                status=message_status,
                reason=message_reason,
            )
        )
        estimated_bytes += message_bytes

        for image_index, image in enumerate(message.images):
            digest = hashlib.sha256(image.data).hexdigest()
            status: ContextStatus = "included"
            reason: str | None = None
            if digest in excluded_digests:
                status = "excluded"
                reason = "excluded_by_user"
            elif digest in seen_digests:
                status = "deduplicated"
                reason = "same_digest_in_previous_message"
            elif is_summary:
                status = "summarized"
                reason = "message_represented_by_compaction_summary"
            else:
                seen_digests.add(digest)
            image_decisions.append(
                ContextImageDecision(
                    message_index=message_index,
                    image_index=image_index,
                    digest=digest,
                    media_type=image.media_type,
                    bytes=len(image.data),
                    status=status,
                    reason=reason,
                    estimated_tokens=_estimate_tokens(len(image.data)),
                )
            )
            if status == "included":
                estimated_bytes += len(image.data)

    if compacted_messages > 0:
        summarized_messages = max(summarized_messages, compacted_messages)
    duplicate_count = sum(image.status == "deduplicated" for image in image_decisions)
    excluded_count = sum(image.status == "excluded" for image in image_decisions)
    summary_parts: list[str] = []
    if summarized_messages:
        summary_parts.append(
            f"{summarized_messages} message(s) represented by a compaction summary"
        )
    if duplicate_count:
        summary_parts.append(f"{duplicate_count} duplicate image(s) omitted after digest matching")
    if excluded_count:
        summary_parts.append(f"{excluded_count} image(s) excluded by the user")
    summary = "; ".join(summary_parts) if summary_parts else None

    return ContextInspection(
        messages=tuple(message_decisions),
        images=tuple(image_decisions),
        estimated_bytes=estimated_bytes,
        estimated_tokens=_estimate_tokens(estimated_bytes),
        context_limit_bytes=context_limit_bytes,
        compacted_messages=compacted_messages,
        summary=summary,
    )


_MAX_INSPECTION_ITEMS = 256
_MAX_INSPECTION_COUNTER = 1 << 40
_MAX_INSPECTION_TEXT = 512


def inspection_from_mapping(value: Mapping[str, Any]) -> ContextInspection | None:
    """Validate a stored, metadata-only projection before renderer use."""
    if not isinstance(value, Mapping) or value.get("version") != 1:
        return None
    messages = value.get("messages")
    images = value.get("images")
    if (
        not isinstance(messages, list)
        or not isinstance(images, list)
        or len(messages) > _MAX_INSPECTION_ITEMS
        or len(images) > _MAX_INSPECTION_ITEMS
    ):
        return None

    def counter(raw: object) -> int | None:
        if type(raw) is not int or raw < 0 or raw > _MAX_INSPECTION_COUNTER:
            return None
        return raw

    estimated_bytes = counter(value.get("estimatedBytes"))
    estimated_tokens = counter(value.get("estimatedTokens"))
    compacted_messages = counter(value.get("compactedMessages"))
    context_limit_raw = value.get("contextLimitBytes")
    context_limit = None if context_limit_raw is None else counter(context_limit_raw)
    summary = value.get("summary")
    if summary is not None and (
        not isinstance(summary, str) or len(summary) > _MAX_INSPECTION_TEXT
    ):
        return None
    if estimated_bytes is None or estimated_tokens is None or compacted_messages is None:
        return None
    if context_limit_raw is not None and context_limit is None:
        return None

    parsed_messages: list[ContextMessageDecision] = []
    for raw in messages:
        if not isinstance(raw, Mapping):
            return None
        message_index = raw.get("messageIndex")
        byte_count = counter(raw.get("bytes"))
        tokens = counter(raw.get("estimatedTokens"))
        role = raw.get("role")
        status = raw.get("status")
        reason = raw.get("reason")
        if (
            type(message_index) is not int
            or not 0 <= message_index < _MAX_INSPECTION_ITEMS
            or byte_count is None
            or tokens is None
            or not isinstance(role, str)
            or not role
            or len(role) > _MAX_INSPECTION_TEXT
            or status not in {"included", "summarized", "deduplicated", "excluded"}
            or (
                reason is not None
                and (not isinstance(reason, str) or len(reason) > _MAX_INSPECTION_TEXT)
            )
        ):
            return None
        parsed_messages.append(
            ContextMessageDecision(
                message_index=message_index,
                role=role,
                bytes=byte_count,
                estimated_tokens=tokens,
                status=status,
                reason=reason,
            )
        )

    parsed_images: list[ContextImageDecision] = []
    for raw in images:
        if not isinstance(raw, Mapping):
            return None
        message_index = raw.get("messageIndex")
        image_index = raw.get("imageIndex")
        digest = raw.get("digest")
        media_type = raw.get("mediaType")
        byte_count = counter(raw.get("bytes"))
        status = raw.get("status")
        reason = raw.get("reason")
        tokens = counter(raw.get("estimatedTokens"))
        if (
            type(message_index) is not int
            or not 0 <= message_index < _MAX_INSPECTION_ITEMS
            or type(image_index) is not int
            or not 0 <= image_index < _MAX_INSPECTION_ITEMS
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdefABCDEF" for char in digest)
            or not isinstance(media_type, str)
            or not media_type
            or len(media_type) > _MAX_INSPECTION_TEXT
            or byte_count is None
            or tokens is None
            or status not in {"included", "summarized", "deduplicated", "excluded"}
            or (
                reason is not None
                and (not isinstance(reason, str) or len(reason) > _MAX_INSPECTION_TEXT)
            )
        ):
            return None
        parsed_images.append(
            ContextImageDecision(
                message_index=message_index,
                image_index=image_index,
                digest=digest,
                media_type=media_type,
                bytes=byte_count,
                status=status,
                reason=reason,
                estimated_tokens=tokens,
            )
        )

    return ContextInspection(
        messages=tuple(parsed_messages),
        images=tuple(parsed_images),
        estimated_bytes=estimated_bytes,
        estimated_tokens=estimated_tokens,
        context_limit_bytes=context_limit,
        compacted_messages=compacted_messages,
        summary=summary,
    )
