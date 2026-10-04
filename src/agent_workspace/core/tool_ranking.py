"""Simple relevance ranking over advertised tool schemas."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from agent_workspace.core.models import ToolSpec

_TOKEN = re.compile(r"[a-z0-9_]{2,}")


def _tokens(text: str) -> Counter[str]:
    return Counter(_TOKEN.findall(text.casefold()))


@dataclass(frozen=True, slots=True)
class RankedTool:
    name: str
    score: float


def rank_tools(tools: tuple[ToolSpec, ...], query: str, limit: int = 10) -> list[RankedTool]:
    if limit < 1:
        raise ValueError("rank limit must be positive")
    query_tokens = _tokens(query)
    if not query_tokens:
        return [RankedTool(tool.name, 0.0) for tool in tools[:limit]]
    scored: list[RankedTool] = []
    for tool in tools:
        text = " ".join((tool.name, tool.description))
        tool_tokens = _tokens(text)
        overlap = sum(min(count, tool_tokens[token]) for token, count in query_tokens.items())
        if not overlap:
            continue
        score = overlap / (sum(query_tokens.values()) ** 0.5 * sum(tool_tokens.values()) ** 0.5)
        scored.append(RankedTool(tool.name, round(score, 4)))
    scored.sort(key=lambda item: (-item.score, item.name))
    return scored[:limit]


__all__ = ["RankedTool", "rank_tools"]
