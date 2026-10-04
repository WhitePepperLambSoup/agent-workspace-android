"""Search ranking tie-breaker policy.

When BM25 or vector scores collide (or only bucket-level relevance is
available), a deterministic tie-break keeps result order stable across
identical queries. The default priority is pinned documents, then recency,
then title; every list still ends with the document id so the order is fully
deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_ALLOWED_FIELDS = frozenset({"pinned", "updated_at", "title"})
_DESCENDING_FIELDS = frozenset({"pinned", "updated_at"})


class SearchTieBreakError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SearchCandidate:
    document_id: str
    score: float
    updated_at: float = 0.0
    pinned: bool = False
    title: str = ""

    def __post_init__(self) -> None:
        if not self.document_id:
            raise SearchTieBreakError("search candidate document id may not be empty")

    def to_document(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "score": self.score,
            "updated_at": self.updated_at,
            "pinned": self.pinned,
            "title": self.title,
        }


@dataclass(frozen=True, slots=True)
class TieBreakPolicy:
    tie_break_fields: tuple[str, ...] = ("pinned", "updated_at", "title")

    def __post_init__(self) -> None:
        if not self.tie_break_fields:
            raise SearchTieBreakError("tie-break policy requires at least one field")
        unknown = [field for field in self.tie_break_fields if field not in _ALLOWED_FIELDS]
        if unknown:
            raise SearchTieBreakError(f"unknown tie-break fields: {unknown}")
        if len(set(self.tie_break_fields)) != len(self.tie_break_fields):
            raise SearchTieBreakError("tie-break fields must be unique")

    def to_document(self) -> dict[str, Any]:
        return {"tie_break_fields": list(self.tie_break_fields)}


def _field_key(candidate: SearchCandidate, field: str) -> Any:
    if field == "pinned":
        return 1 if candidate.pinned else 0
    if field == "updated_at":
        return candidate.updated_at
    if field == "title":
        return candidate.title.casefold()
    raise AssertionError(f"unreachable tie-break field {field!r}")


def rank_search_results(
    candidates: list[SearchCandidate] | tuple[SearchCandidate, ...],
    *,
    policy: TieBreakPolicy | None = None,
    limit: int | None = None,
) -> tuple[SearchCandidate, ...]:
    """Sort candidates by score, then by the configured deterministic policy."""
    active = policy or TieBreakPolicy()
    if limit is not None and limit < 1:
        raise SearchTieBreakError("search result limit must be positive when set")
    ordered = sorted(candidates, key=lambda candidate: candidate.document_id)
    for field in reversed(active.tie_break_fields):
        ordered = sorted(
            ordered,
            key=lambda candidate: _field_key(candidate, field),
            reverse=field in _DESCENDING_FIELDS,
        )
    # The score pass is last and stable, so equal scores preserve the
    # tie-break order established above.
    ordered.sort(key=lambda candidate: candidate.score, reverse=True)
    if limit is not None:
        ordered = ordered[:limit]
    return tuple(ordered)


__all__ = [
    "SearchCandidate",
    "SearchTieBreakError",
    "TieBreakPolicy",
    "rank_search_results",
]
