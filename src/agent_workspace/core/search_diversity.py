"""Diversity reranker to prevent single-session result flooding in hybrid search."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ScoredSearchResult:
    session_id: str
    item_id: str
    score: float
    snippet: str
    metadata: dict[str, Any] | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "item_id": self.item_id,
            "score": round(self.score, 4),
            "snippet": self.snippet,
        }


def rerank_search_diversity(
    results: Sequence[ScoredSearchResult],
    *,
    max_per_session: int = 2,
    decay_factor: float = 0.6,
    limit: int | None = None,
) -> list[ScoredSearchResult]:
    """Rerank search results applying session diversity decay and cap."""
    if max_per_session <= 0:
        raise ValueError("max_per_session must be positive")
    if not (0.0 < decay_factor <= 1.0):
        raise ValueError("decay_factor must be in (0, 1]")

    session_counts: dict[str, int] = {}
    reranked: list[tuple[float, ScoredSearchResult]] = []

    for item in sorted(results, key=lambda r: r.score, reverse=True):
        count = session_counts.get(item.session_id, 0)
        if count >= max_per_session:
            # Skip beyond max cap
            continue

        adjusted_score = item.score * (decay_factor**count)
        session_counts[item.session_id] = count + 1
        reranked.append((adjusted_score, item))

    # Sort primarily by adjusted score
    reranked.sort(key=lambda pair: pair[0], reverse=True)
    final_list = [pair[1] for pair in reranked]
    if limit is not None and limit > 0:
        return final_list[:limit]
    return final_list
