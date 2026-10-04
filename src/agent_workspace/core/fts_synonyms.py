"""Fulltext synonym dictionary and query expansion.

Synonyms are stored as a JSON dictionary mapping a normalized canonical term
to its variants. Query expansion wraps each term that has synonyms in an FTS5
OR group with every variant quoted, so ``disk`` expands to
``(disk OR drive OR volume)`` without letting user input inject operators.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_FTS_SPECIAL = re.compile(r'["*:^()[\]]')
_TOKEN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


class SynonymDictionaryError(ValueError):
    pass


def normalize_synonym_term(term: str) -> str:
    normalized = _FTS_SPECIAL.sub("", term).strip().casefold()
    if not normalized:
        raise SynonymDictionaryError("synonym term may not be empty")
    return normalized


class SynonymDictionary:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._entries: dict[str, tuple[str, ...]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SynonymDictionaryError(f"cannot read synonym dictionary: {exc}") from exc
        raw_entries = document.get("synonyms") if isinstance(document, dict) else None
        if not isinstance(raw_entries, dict):
            raise SynonymDictionaryError("synonym dictionary must declare a synonyms object")
        for term, raw_variants in raw_entries.items():
            if not isinstance(term, str) or not isinstance(raw_variants, list):
                raise SynonymDictionaryError("synonym dictionary entry is invalid")
            self._entries[normalize_synonym_term(term)] = self._normalize_variants(
                term, raw_variants
            )

    def _normalize_variants(self, term: str, variants: list[object]) -> tuple[str, ...]:
        normalized = tuple(normalize_synonym_term(str(variant)) for variant in variants)
        if not normalized:
            raise SynonymDictionaryError(f"synonym entry {term!r} has no variants")
        if len(set(normalized)) != len(normalized):
            raise SynonymDictionaryError(f"synonym entry {term!r} has duplicate variants")
        if normalize_synonym_term(term) in normalized:
            raise SynonymDictionaryError(f"synonym entry {term!r} contains itself")
        return normalized

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(
                {"synonyms": {term: list(values) for term, values in self._entries.items()}},
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, self.path)

    def add(self, term: str, variants: list[str] | tuple[str, ...]) -> tuple[str, ...]:
        normalized_term = normalize_synonym_term(term)
        normalized = self._normalize_variants(
            normalized_term, [str(variant) for variant in variants]
        )
        # Removing a term from another entry's variants keeps the reverse
        # lookup consistent after an update.
        for other, values in list(self._entries.items()):
            if other == normalized_term:
                continue
            if normalized_term in values:
                self._entries[other] = tuple(value for value in values if value != normalized_term)
        self._entries[normalized_term] = normalized
        self.save()
        return normalized

    def remove(self, term: str) -> bool:
        key = normalize_synonym_term(term)
        if key not in self._entries:
            return False
        del self._entries[key]
        for other, values in list(self._entries.items()):
            if key in values:
                self._entries[other] = tuple(value for value in values if value != key)
        self.save()
        return True

    def synonyms_for(self, term: str) -> tuple[str, ...]:
        return self._entries.get(normalize_synonym_term(term), ())

    def entries(self) -> dict[str, tuple[str, ...]]:
        return dict(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


@dataclass(frozen=True, slots=True)
class ExpandedFTSQuery:
    original: str
    match_query: str
    terms: tuple[str, ...]

    def to_document(self) -> dict[str, Any]:
        return {
            "original": self.original,
            "match_query": self.match_query,
            "terms": list(self.terms),
        }


def _quote_fts_token(token: str) -> str:
    return f'"{_FTS_SPECIAL.sub("", token).strip()}"'


def expand_fts_query(
    query: str, dictionary: SynonymDictionary | None = None, *, implicit_and: bool = True
) -> ExpandedFTSQuery:
    if not isinstance(query, str) or not query.strip():
        raise SynonymDictionaryError("fulltext query may not be empty")
    original = query.strip()
    groups: list[str] = []
    terms: list[str] = []
    for match in _TOKEN.finditer(original):
        token = match.group(0)
        normalized = token.casefold()
        variants = dictionary.synonyms_for(normalized) if dictionary is not None else ()
        terms.extend((normalized, *variants))
        if variants:
            quoted = [_quote_fts_token(normalized), *(_quote_fts_token(item) for item in variants)]
            groups.append(f"({' OR '.join(quoted)})")
        else:
            groups.append(_quote_fts_token(token))
    if not groups:
        raise SynonymDictionaryError("fulltext query contains no searchable terms")
    joiner = " AND " if implicit_and else " "
    return ExpandedFTSQuery(original=original, match_query=joiner.join(groups), terms=tuple(terms))


__all__ = [
    "ExpandedFTSQuery",
    "SynonymDictionary",
    "SynonymDictionaryError",
    "expand_fts_query",
    "normalize_synonym_term",
]
