"""Versioned prompt template diff helper."""

from __future__ import annotations

import difflib

from agent_workspace.core.prompt_templates import PromptTemplate


def prompt_version_diff(
    older: PromptTemplate,
    newer: PromptTemplate,
    *,
    context_lines: int = 3,
) -> str:
    if older.id != newer.id:
        raise ValueError("prompt versions must share the same template id")
    if older.version == newer.version:
        return ""
    old_lines = older.template.splitlines()
    new_lines = newer.template.splitlines()
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"{older.id}@v{older.version}",
        tofile=f"{newer.id}@v{newer.version}",
        lineterm="",
        n=context_lines,
    )
    return "\n".join(diff)


__all__ = ["prompt_version_diff"]
