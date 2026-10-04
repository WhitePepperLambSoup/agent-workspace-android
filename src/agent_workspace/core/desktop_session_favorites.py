"""Desktop session favorites store.

Favorites are persisted per workspace as a small JSON document. Pinning and
favorites are deliberately separate concepts: pinning controls the switcher
ordering while favorites power the session quick-access rail and never store
prompt content.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SessionFavoritesError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FavoriteSession:
    session_id: str
    label: str
    workspace: str
    favorited_at: float
    order: int

    def to_document(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "label": self.label,
            "workspace": self.workspace,
            "favorited_at": self.favorited_at,
            "order": self.order,
        }


class SessionFavoritesStore:
    """JSON-persisted favorite sessions with deterministic rail ordering."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_favorites: int = 100,
        clock: Any = time.time,
    ) -> None:
        if max_favorites < 1:
            raise SessionFavoritesError("max favorites must be positive")
        self.path = Path(path)
        self.max_favorites = max_favorites
        self._clock = clock
        self._favorites: dict[str, FavoriteSession] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SessionFavoritesError(f"cannot read session favorites: {exc}") from exc
        raw_favorites = document.get("favorites") if isinstance(document, dict) else None
        if not isinstance(raw_favorites, list):
            raise SessionFavoritesError("session favorites must declare a favorites array")
        for raw in raw_favorites:
            favorite = self._parse(raw)
            self._favorites[favorite.session_id] = favorite
        if len(self._favorites) > self.max_favorites:
            raise SessionFavoritesError(
                f"session favorites exceed the configured maximum of {self.max_favorites}"
            )

    def _parse(self, raw: object) -> FavoriteSession:
        if not isinstance(raw, dict):
            raise SessionFavoritesError("favorite session is invalid")
        try:
            return FavoriteSession(
                session_id=str(raw["session_id"]),
                label=str(raw["label"]),
                workspace=str(raw["workspace"]),
                favorited_at=float(raw["favorited_at"]),
                order=int(raw["order"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SessionFavoritesError("favorite session is invalid") from exc

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(
                {"favorites": [favorite.to_document() for favorite in self.ordered()]},
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, self.path)

    def add(
        self,
        session_id: str,
        *,
        workspace: str,
        label: str = "",
        favorited_at: float | None = None,
    ) -> FavoriteSession:
        if not session_id or not workspace:
            raise SessionFavoritesError("session id and workspace may not be empty")
        if session_id in self._favorites:
            raise SessionFavoritesError(f"session {session_id!r} is already a favorite")
        if len(self._favorites) >= self.max_favorites:
            raise SessionFavoritesError(f"cannot favorite more than {self.max_favorites} sessions")
        existing_orders = {favorite.order for favorite in self._favorites.values()}
        next_order = max(existing_orders, default=0) + 1
        favorite = FavoriteSession(
            session_id=session_id,
            label=label.strip(),
            workspace=workspace,
            favorited_at=float(favorited_at) if favorited_at is not None else float(self._clock()),
            order=next_order,
        )
        self._favorites[session_id] = favorite
        self.save()
        return favorite

    def remove(self, session_id: str) -> bool:
        favorite = self._favorites.pop(session_id, None)
        if favorite is None:
            return False
        self.save()
        return True

    def get(self, session_id: str) -> FavoriteSession | None:
        return self._favorites.get(session_id)

    def ordered(self) -> tuple[FavoriteSession, ...]:
        return tuple(
            sorted(
                self._favorites.values(), key=lambda favorite: (favorite.order, favorite.session_id)
            )
        )

    def __len__(self) -> int:
        return len(self._favorites)


__all__ = [
    "FavoriteSession",
    "SessionFavoritesError",
    "SessionFavoritesStore",
]
