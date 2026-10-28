"""The reference library of a folder: the works a project cites, kept in .agent/references.json
beside the project so it travels with it.

Works are kept once each (by DOI, arXiv id, PMID, or title and year) under a citation key; adding
a work the library has fills in what it lacked. Recently looked-up works are remembered for a while
so the agent can add them by DOI or key without asking the databases again.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections import OrderedDict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_workspace.scholar.works import Work, citation_key, identifier_kind

LIBRARY_FILE = Path(".agent") / "references.json"
MAX_WORKS = 20_000
_LOCK = threading.Lock()


class LibraryError(ValueError):
    """The library file cannot be read or a request names works it does not have."""


class ReferenceLibrary:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.path = workspace / LIBRARY_FILE

    def _load(self) -> list[Work]:
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LibraryError(f"the reference library could not be read: {exc}") from None
        items = document.get("items") if isinstance(document, dict) else None
        if not isinstance(items, list):
            raise LibraryError("the reference library file is not a library")
        return [Work.from_csl(item) for item in items if isinstance(item, dict)]

    def _save(self, works: Sequence[Work]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "version": 1,
            "updated": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "items": [work.to_csl() for work in works],
        }
        descriptor, temporary = tempfile.mkstemp(prefix=".references-", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(document, stream, ensure_ascii=False, indent=1)
            os.replace(temporary, self.path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def works(self) -> list[Work]:
        with _LOCK:
            return self._load()

    def add(self, incoming: Iterable[Work]) -> tuple[list[Work], list[Work]]:
        """Add works; return those added and those the library already had (now filled in)."""
        with _LOCK:
            works = self._load()
            by_identity = {work.identity(): index for index, work in enumerate(works)}
            aliases = _aliases(works)
            taken = {work.key for work in works}
            added: list[Work] = []
            known: list[Work] = []
            for work in incoming:
                if not work.title:
                    continue
                index = next((aliases[key] for key in _keys(work) if key in aliases), None)
                if index is None:
                    index = by_identity.get(work.identity())
                if index is not None:
                    works[index] = works[index].merged(work)
                    known.append(works[index])
                    continue
                if len(works) >= MAX_WORKS:
                    raise LibraryError(f"the library holds at most {MAX_WORKS} works")
                stored = Work.from_csl(work.to_csl())
                stored.key = (
                    work.key if work.key and work.key not in taken else citation_key(work, taken)
                )
                taken.add(stored.key)
                works.append(stored)
                for key in _keys(stored):
                    aliases.setdefault(key, len(works) - 1)
                by_identity[stored.identity()] = len(works) - 1
                added.append(stored)
            if added or known:
                self._save(works)
            return added, known

    def remove(self, keys: Iterable[str]) -> list[str]:
        wanted = set(keys)
        with _LOCK:
            works = self._load()
            kept = [work for work in works if work.key not in wanted]
            removed = [work.key for work in works if work.key in wanted]
            if removed:
                self._save(kept)
            return removed

    def update(self, key: str, fields: dict[str, Any]) -> Work:
        """Change a work's fields (as CSL-JSON names or this app's names)."""
        with _LOCK:
            works = self._load()
            for index, work in enumerate(works):
                if work.key != key:
                    continue
                item = work.to_csl()
                for name, value in fields.items():
                    item[_CSL_NAMES.get(name, name)] = value
                updated = Work.from_csl(item)
                new_key = fields.get("key")
                updated.key = new_key if isinstance(new_key, str) and new_key.strip() else key
                if updated.key != key and any(other.key == updated.key for other in works):
                    raise LibraryError(f"the key {updated.key} is taken")
                works[index] = updated
                self._save(works)
                return updated
        raise LibraryError(f"no work with the key {key}")

    def find(self, references: Iterable[str]) -> tuple[list[Work], list[str]]:
        """Works by key, DOI, arXiv id or PMID; and the references not found."""
        works = self.works()
        by_key = {work.key: work for work in works}
        aliases = {key: works[index] for key, index in _aliases(works).items()}
        found: list[Work] = []
        missing: list[str] = []
        for reference in references:
            work = by_key.get(reference.strip())
            if work is None:
                kind, value = identifier_kind(reference)
                work = aliases.get(f"{kind}:{value.casefold()}") if kind != "query" else None
            if work is None:
                missing.append(reference)
            elif work not in found:
                found.append(work)
        return found, missing

    def search(self, query: str, limit: int = 50) -> list[Work]:
        words = [word.casefold() for word in query.split() if word]
        results = []
        for work in self.works():
            haystack = " ".join(
                [
                    work.key,
                    work.title,
                    work.container,
                    work.doi,
                    str(work.year or ""),
                    " ".join(person.display() for person in work.authors),
                    " ".join(work.keywords),
                ]
            ).casefold()
            if all(word in haystack for word in words):
                results.append(work)
                if len(results) >= limit:
                    break
        return results


_CSL_NAMES = {
    "container": "container-title",
    "pages": "page",
    "doi": "DOI",
    "url": "URL",
    "isbn": "ISBN",
    "pmid": "PMID",
    "place": "publisher-place",
}


def _keys(work: Work) -> list[str]:
    keys = []
    if work.doi:
        keys.append(f"doi:{work.doi.casefold()}")
    if work.arxiv:
        keys.append(f"arxiv:{work.arxiv.casefold()}")
    if work.pmid:
        keys.append(f"pmid:{work.pmid}")
    keys.append(work.identity().casefold())
    return keys


def _aliases(works: Sequence[Work]) -> dict[str, int]:
    aliases: dict[str, int] = {}
    for index, work in enumerate(works):
        for key in _keys(work):
            aliases.setdefault(key, index)
    return aliases


class RecentWorks:
    """Works the databases returned lately, by every identifier they carry (bounded, in memory)."""

    def __init__(self, capacity: int = 1000) -> None:
        self.capacity = capacity
        self._items: OrderedDict[str, Work] = OrderedDict()
        self._lock = threading.Lock()

    def remember(self, works: Iterable[Work]) -> None:
        with self._lock:
            for work in works:
                for key in _keys(work):
                    self._items[key] = work
                    self._items.move_to_end(key)
            while len(self._items) > self.capacity:
                self._items.popitem(last=False)

    def get(self, reference: str) -> Work | None:
        kind, value = identifier_kind(reference)
        if kind == "query":
            return None
        with self._lock:
            return self._items.get(f"{kind}:{value.casefold()}")


__all__ = ["LIBRARY_FILE", "LibraryError", "RecentWorks", "ReferenceLibrary"]
