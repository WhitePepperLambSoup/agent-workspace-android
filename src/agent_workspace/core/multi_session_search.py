"""Multi-session batch search aggregation.

Several queries can be run against a session store and their ranked results
merged into one dashboard. Hits are deduplicated per (query, session), scored
0..1 per query, and then ranked by the sum of their per-query scores followed
by the number of distinct queries that matched.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from agent_workspace.core.search import SessionSearchResult


@dataclass(frozen=True, slots=True)
class BatchSearchHit:
    session_id: str
    title: str
    snippet: str
    queries: tuple[str, ...]
    score: float

    def to_document(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "snippet": self.snippet,
            "queries": list(self.queries),
            "score": self.score,
        }


@dataclass(frozen=True, slots=True)
class BatchSearchResult:
    queries: tuple[str, ...]
    hits: tuple[BatchSearchHit, ...]
    total_query_hits: int

    def to_document(self) -> dict[str, Any]:
        return {
            "queries": list(self.queries),
            "hits": [hit.to_document() for hit in self.hits],
            "total_query_hits": self.total_query_hits,
        }


def merge_batch_search_results(
    query_results: Mapping[str, Iterable[SessionSearchResult]],
) -> BatchSearchResult:
    if not query_results:
        raise ValueError("at least one query result set is required")
    for query in query_results:
        if not query.strip():
            raise ValueError("search queries may not be blank")
    # Per-query best rank is normalized to 1.0; lower ranks score proportionally.
    best_rank = {
        query: min((result.rank for result in results), default=0.0)
        for query, results in query_results.items()
    }
    aggregated: dict[str, dict[str, Any]] = {}
    total_query_hits = 0
    for query, results in query_results.items():
        seen_sessions: set[str] = set()
        for result in results:
            total_query_hits += 1
            session_id = result.session.id
            if session_id in seen_sessions:
                entry = aggregated.get(session_id)
                if entry is not None and len(entry["snippet"]) < len(result.snippet):
                    entry["snippet"] = result.snippet
                continue
            seen_sessions.add(session_id)
            best = best_rank[query]
            score = 1.0 if best <= 0 else min(1.0, best / max(result.rank, best))
            entry = aggregated.get(session_id)
            if entry is None:
                entry = {
                    "session_id": session_id,
                    "title": result.session.title,
                    "snippet": result.snippet,
                    "queries": [],
                    "score": 0.0,
                }
                aggregated[session_id] = entry
            if len(entry["snippet"]) < len(result.snippet):
                entry["snippet"] = result.snippet
            if query not in entry["queries"]:
                entry["queries"].append(query)
            entry["score"] += score
    hits = [
        BatchSearchHit(
            session_id=entry["session_id"],
            title=entry["title"],
            snippet=entry["snippet"],
            queries=tuple(entry["queries"]),
            score=round(entry["score"], 4),
        )
        for entry in aggregated.values()
    ]
    hits.sort(key=lambda hit: (-hit.score, -len(hit.queries), hit.title, hit.session_id))
    return BatchSearchResult(
        queries=tuple(query_results),
        hits=tuple(hits),
        total_query_hits=total_query_hits,
    )


__all__ = [
    "BatchSearchHit",
    "BatchSearchResult",
    "merge_batch_search_results",
]
