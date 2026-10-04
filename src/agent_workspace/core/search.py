from __future__ import annotations

from dataclasses import dataclass

from agent_workspace.core.session import Session


class SearchIndexUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SessionSearchResult:
    session: Session
    snippet: str
    document_kind: str
    rank: float
