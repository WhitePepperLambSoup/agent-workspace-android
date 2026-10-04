from __future__ import annotations

import hashlib
from typing import Any

from agent_workspace.core.models import ToolSpec

_MAX_TEXT_PREVIEW_CHARS = 1000
_LARGE_TEXT_FIELDS: dict[str, tuple[str, ...]] = {
    "write_file": ("content",),
    "apply_patch": ("old_text", "new_text"),
}


def _summarize_large_text(value: str) -> dict[str, Any] | str:
    if len(value) <= _MAX_TEXT_PREVIEW_CHARS:
        return value
    return {
        "preview": value[:_MAX_TEXT_PREVIEW_CHARS],
        "characters": len(value),
        "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
    }


def approval_display_arguments(tool: ToolSpec, arguments: dict[str, Any]) -> dict[str, Any]:
    displayed = dict(arguments)
    for field in _LARGE_TEXT_FIELDS.get(tool.name, ()):
        value = displayed.get(field)
        if isinstance(value, str):
            displayed[field] = _summarize_large_text(value)

    if tool.name == "memory_write":
        content = displayed.get("content")
        if isinstance(content, str) and len(content) > _MAX_TEXT_PREVIEW_CHARS:
            displayed["content"] = {
                "preview": content[:_MAX_TEXT_PREVIEW_CHARS],
                "characters": len(content),
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
        return displayed
    if tool.name != "save_research_source":
        return displayed
    content = displayed.get("content")
    if isinstance(content, str):
        encoded = content.encode("utf-8")
        displayed["content"] = {
            "omitted_from_display": True,
            "utf8_bytes": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }
    summary = displayed.get("summary")
    if isinstance(summary, str) and len(summary) > _MAX_TEXT_PREVIEW_CHARS:
        displayed["summary"] = {
            "preview": summary[:_MAX_TEXT_PREVIEW_CHARS],
            "characters": len(summary),
            "sha256": hashlib.sha256(summary.encode("utf-8")).hexdigest(),
        }
    return displayed
