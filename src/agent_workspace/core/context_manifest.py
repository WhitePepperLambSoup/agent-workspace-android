"""Content-free accounting of the logical request passed to a provider adapter."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from agent_workspace.core.models import ProviderRequest

_MAX_ITEMS = 96
_CONTEXT_STATUSES = frozenset({"included", "summarized", "deduplicated", "excluded"})


def _encoded(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def build_context_manifest(
    request: ProviderRequest,
    message_documents: Sequence[Mapping[str, Any]],
    *,
    context_limit_bytes: int,
    compacted_messages: int = 0,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    totals: dict[str, int] = {}
    statuses: dict[str, int] = {status: 0 for status in _CONTEXT_STATUSES}
    image_decisions: list[dict[str, Any]] = []
    digest = hashlib.sha256(request.model.encode("utf-8"))
    logical_bytes = 0
    count = 0

    def account(
        identifier: str,
        kind: str,
        document: object,
        *,
        label: str,
        sensitive: bool = False,
        status: str = "included",
        reason: str | None = None,
    ) -> None:
        nonlocal logical_bytes, count
        if status not in _CONTEXT_STATUSES:
            status = "included"
        encoded = _encoded(document)
        size = len(encoded)
        logical_bytes += size
        count += 1
        totals[kind] = totals.get(kind, 0) + size
        statuses[status] += 1
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        item = {
            "id": identifier,
            "kind": kind,
            "label": label[:128],
            "bytes": size,
            "estimatedTokens": (size + 2) // 3,
            "estimated": True,
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "sensitive": sensitive,
            "status": status,
            "reason": reason,
        }
        # Keep the system entry and the most recent rows without an unbounded event payload.
        if len(items) == _MAX_ITEMS:
            del items[1]
        items.append(item)

    for index, (message, document) in enumerate(
        zip(request.messages, message_documents, strict=True)
    ):
        raw_content = document.get("content")
        is_summary = isinstance(raw_content, str) and (
            "[Earlier conversation summarized]" in raw_content
            or "context-compaction" in raw_content.casefold()
        )
        account(
            f"message:{index}",
            message.role.value,
            document,
            label=f"{message.role.value} #{index + 1}",
            sensitive=message.sensitivity.value == "sensitive",
            status="summarized" if is_summary else "included",
            reason="context_compaction_summary" if is_summary else None,
        )
        for image_index, image in enumerate(message.images):
            image_digest = hashlib.sha256(image.data).hexdigest()
            account(
                f"image:{index}:{image_index}",
                "image",
                {
                    "bytes": len(image.data),
                    "sha256": image_digest,
                    "mediaType": image.media_type,
                },
                label=image.media_type,
                sensitive=message.sensitivity.value == "sensitive",
            )
            image_decisions.append(
                {
                    "id": f"image:{index}:{image_index}",
                    "messageIndex": index,
                    "imageIndex": image_index,
                    "digest": image_digest,
                    "mediaType": image.media_type,
                    "bytes": len(image.data),
                    "status": "included",
                    "reason": None,
                    "estimatedTokens": (len(image.data) + 2) // 3,
                }
            )
        raw_decisions = message.provider_metadata.get("agent_workspace.context_images")
        if isinstance(raw_decisions, list):
            for decision_index, raw_decision in enumerate(raw_decisions[:16]):
                if not isinstance(raw_decision, Mapping):
                    continue
                raw_image_digest = raw_decision.get("sha256")
                media_type = raw_decision.get("media_type")
                image_bytes = raw_decision.get("bytes")
                status = raw_decision.get("status")
                reason = raw_decision.get("reason")
                if (
                    not isinstance(raw_image_digest, str)
                    or len(raw_image_digest) != 64
                    or not isinstance(media_type, str)
                    or type(image_bytes) is not int
                    or image_bytes < 0
                    or not isinstance(status, str)
                    or status not in _CONTEXT_STATUSES
                ):
                    continue
                decision = {
                    "id": f"image:{index}:{raw_decision.get('image_index', decision_index)}",
                    "messageIndex": index,
                    "imageIndex": raw_decision.get("image_index", decision_index),
                    "digest": raw_image_digest,
                    "mediaType": media_type,
                    "bytes": image_bytes,
                    "status": status,
                    "reason": reason if isinstance(reason, str) else None,
                    "estimatedTokens": (image_bytes + 2) // 3,
                }
                # Included images already have a provider-payload entry above. Duplicate and
                # excluded images are absent from the payload but remain visible here.
                if status != "included":
                    image_decisions.append(decision)
                if status == "included":
                    continue
                account(
                    decision["id"],
                    "image",
                    {"bytes": image_bytes, "sha256": raw_image_digest, "mediaType": media_type},
                    label=media_type,
                    sensitive=message.sensitivity.value == "sensitive",
                    status=status,
                    reason=decision["reason"],
                )
    for index, tool in enumerate(request.tools):
        account(f"tool:{index}", "tool_schema", tool.to_openai(), label=tool.name)

    summary = None
    summary_parts: list[str] = []
    if compacted_messages:
        summary_parts.append(f"{compacted_messages} message(s) represented by a compaction summary")
    duplicate_count = statuses["deduplicated"]
    excluded_count = statuses["excluded"]
    if duplicate_count:
        summary_parts.append(f"{duplicate_count} duplicate image(s) omitted after digest matching")
    if excluded_count:
        summary_parts.append(f"{excluded_count} image(s) excluded by the user")
    if summary_parts:
        summary = "; ".join(summary_parts)

    return {
        "version": 1,
        "source": "logical_provider_request",
        "model": request.model,
        "sha256": digest.hexdigest(),
        "items": items,
        "omittedItems": count - len(items),
        "messageCount": len(request.messages),
        "toolCount": len(request.tools),
        "logicalBytes": logical_bytes,
        "estimatedTokens": (logical_bytes + 2) // 3,
        "groupBytes": totals,
        "statusCounts": statuses,
        "imageDecisions": image_decisions,
        "summary": summary,
        "estimated": True,
        "estimateMethod": "utf8_json_bytes_divided_by_3",
        "imageTokenEstimateIncluded": False,
        "contextLimitBytes": context_limit_bytes,
        "requestBudgetBytes": request.metadata.get("estimated_request_bytes"),
        "maxOutputTokens": request.max_output_tokens,
        "compactedMessages": compacted_messages,
    }
