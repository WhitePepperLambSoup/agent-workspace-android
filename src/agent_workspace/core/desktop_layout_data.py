"""Desktop split layout store, file tree keyboard search, and transcript
export dialog data."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SplitLayoutState:
    orientation: str
    sizes: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.orientation not in {"horizontal", "vertical"}:
            raise ValueError("split orientation must be horizontal or vertical")
        if not self.sizes or any(size < 1 for size in self.sizes):
            raise ValueError("split sizes must be positive")

    def to_document(self) -> dict[str, Any]:
        return {"orientation": self.orientation, "sizes": list(self.sizes)}


class DesktopSplitLayoutStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._layouts: dict[str, SplitLayoutState] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read split layouts: {exc}") from exc
        raw = document.get("layouts") if isinstance(document, dict) else None
        if not isinstance(raw, dict):
            raise ValueError("split layout store is invalid")
        for name, item in raw.items():
            if not isinstance(name, str) or not isinstance(item, dict):
                raise ValueError("split layout entry is invalid")
            self._layouts[name] = SplitLayoutState(
                orientation=str(item["orientation"]),
                sizes=tuple(int(size) for size in item["sizes"]),
            )

    def save_layout(self, name: str, layout: SplitLayoutState) -> SplitLayoutState:
        if not name:
            raise ValueError("layout name may not be empty")
        self._layouts[name] = layout
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(
                {"layouts": {key: value.to_document() for key, value in self._layouts.items()}},
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, self.path)
        return layout

    def load_layout(self, name: str) -> SplitLayoutState | None:
        return self._layouts.get(name)


@dataclass(frozen=True, slots=True)
class FileTreeMatch:
    path: str
    score: int
    starts_with: bool

    def to_document(self) -> dict[str, Any]:
        return {"path": self.path, "score": self.score, "starts_with": self.starts_with}


def search_file_tree(
    paths: list[str] | tuple[str, ...], query: str, *, limit: int = 20
) -> tuple[FileTreeMatch, ...]:
    if not query or limit < 1:
        raise ValueError("file tree query may not be empty and limit must be positive")
    folded = query.casefold()
    matches: list[FileTreeMatch] = []
    for path in paths:
        if not isinstance(path, str):
            continue
        folded_path = path.casefold()
        if folded in folded_path:
            starts_with = folded_path.startswith(folded) or ("/" + folded) in folded_path
            score = 2 if starts_with else 1
            matches.append(FileTreeMatch(path, score, starts_with))
    matches.sort(key=lambda match: (-match.score, len(match.path), match.path))
    return tuple(matches[:limit])


@dataclass(frozen=True, slots=True)
class TranscriptExportData:
    session_id: str
    title: str
    format: str
    include_reasoning: bool
    estimated_bytes: int

    def to_document(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "format": self.format,
            "include_reasoning": self.include_reasoning,
            "estimated_bytes": self.estimated_bytes,
        }


def transcript_export_data(
    session_id: str,
    title: str,
    text: str,
    *,
    format: str = "markdown",
    include_reasoning: bool = False,
) -> TranscriptExportData:
    if not session_id or format not in {"markdown", "json", "text"}:
        raise ValueError("session id and export format are required/invalid")
    estimated = len(text.encode("utf-8"))
    if include_reasoning:
        estimated += max(0, len(title.encode("utf-8")))
    return TranscriptExportData(session_id, title, format, include_reasoning, estimated)


__all__ = [
    "DesktopSplitLayoutStore",
    "FileTreeMatch",
    "SplitLayoutState",
    "TranscriptExportData",
    "search_file_tree",
    "transcript_export_data",
]
