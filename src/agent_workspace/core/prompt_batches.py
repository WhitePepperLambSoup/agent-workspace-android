"""Batch prompt import/export.

The batch format is intentionally simple so humans and CI scripts can author
it: JSONL with one object per line, or a JSON array of objects. Every entry
is ``{"id": str, "prompt": str, "metadata": {}}``; the id is generated from
the prompt digest when omitted.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_MAX_PROMPT_CHARS = 32_767


class PromptBatchError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PromptBatchEntry:
    id: str
    prompt: str
    metadata: dict[str, Any]

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class PromptBatchSummary:
    path: Path
    entries: int
    unique_prompts: int
    duplicate_prompts: int
    total_chars: int

    def to_document(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "entries": self.entries,
            "unique_prompts": self.unique_prompts,
            "duplicate_prompts": self.duplicate_prompts,
            "total_chars": self.total_chars,
        }


def _validate_prompt(prompt: str) -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        raise PromptBatchError("batch prompt must be a non-empty string")
    if "\x00" in prompt or len(prompt) > _MAX_PROMPT_CHARS:
        raise PromptBatchError("batch prompt is invalid or too long")
    return prompt


def _entry_from_document(document: object) -> PromptBatchEntry:
    if not isinstance(document, dict):
        raise PromptBatchError("batch entry must be an object")
    raw_prompt = document.get("prompt")
    prompt = _validate_prompt(raw_prompt)  # type: ignore[arg-type]
    raw_id = document.get("id", "")
    entry_id = raw_id if isinstance(raw_id, str) and raw_id else _prompt_id(prompt)
    raw_metadata = document.get("metadata", {})
    if not isinstance(raw_metadata, dict):
        raise PromptBatchError("batch entry metadata must be an object")
    return PromptBatchEntry(id=entry_id, prompt=prompt, metadata=dict(raw_metadata))


def _prompt_id(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def load_prompt_batch(path: str | Path) -> tuple[PromptBatchEntry, ...]:
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise PromptBatchError(f"cannot read prompt batch: {source}") from exc
    if source.suffix.casefold() == ".jsonl":
        documents: list[object] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                documents.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise PromptBatchError(f"invalid JSON on line {line_number}: {exc}") from exc
    else:
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PromptBatchError(f"invalid prompt batch JSON: {exc}") from exc
        if not isinstance(raw, list):
            raise PromptBatchError("prompt batch JSON must be an array")
        documents = raw
    entries = tuple(_entry_from_document(document) for document in documents)
    if not entries:
        raise PromptBatchError("prompt batch is empty")
    return entries


def save_prompt_batch(
    path: str | Path,
    entries: list[PromptBatchEntry] | tuple[PromptBatchEntry, ...],
    *,
    format: str = "jsonl",
) -> Path:
    destination = Path(path)
    if not entries:
        raise PromptBatchError("prompt batch may not be empty")
    documents = [entry.to_document() for entry in entries]
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f"{destination.suffix}.tmp")
    if format == "jsonl":
        temporary.write_text(
            "".join(
                json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n"
                for document in documents
            ),
            encoding="utf-8",
            newline="\n",
        )
    elif format == "json":
        temporary.write_text(
            json.dumps(documents, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    else:
        raise PromptBatchError(f"unsupported prompt batch format: {format}")
    temporary.replace(destination)
    return destination


def summarize_prompt_batch(
    entries: list[PromptBatchEntry] | tuple[PromptBatchEntry, ...],
) -> PromptBatchSummary:
    prompts = [entry.prompt for entry in entries]
    unique = len(set(prompts))
    return PromptBatchSummary(
        path=Path("<memory>"),
        entries=len(entries),
        unique_prompts=unique,
        duplicate_prompts=len(prompts) - unique,
        total_chars=sum(len(prompt) for prompt in prompts),
    )


def summarize_prompt_batch_file(path: str | Path) -> PromptBatchSummary:
    source = Path(path)
    summary = summarize_prompt_batch(load_prompt_batch(source))
    return PromptBatchSummary(
        path=source,
        entries=summary.entries,
        unique_prompts=summary.unique_prompts,
        duplicate_prompts=summary.duplicate_prompts,
        total_chars=summary.total_chars,
    )


__all__ = [
    "PromptBatchEntry",
    "PromptBatchError",
    "PromptBatchSummary",
    "load_prompt_batch",
    "save_prompt_batch",
    "summarize_prompt_batch",
    "summarize_prompt_batch_file",
]
