"""Prompt section and dynamic context assembly.

This is the cache-safe counterpart to the DeepSeek Harness system-prompt
assembly design: sections are ordered, one optional ``complete`` section can
replace the assembled prompt, and dynamic contexts are snapshotted only when
they change.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

SectionText = str | Callable[[dict[str, Any]], str]


class PromptAssemblyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PromptSection:
    name: str
    order: int
    text: SectionText
    complete: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise PromptAssemblyError("prompt section name may not be empty")

    def render(self, context: dict[str, Any] | None = None) -> str:
        resolved = self.text(context or {}) if callable(self.text) else self.text
        if not isinstance(resolved, str):
            raise PromptAssemblyError(f"prompt section {self.name!r} did not render a string")
        return resolved


@dataclass(frozen=True, slots=True)
class PromptContext:
    name: str
    order: int
    text: SectionText

    def __post_init__(self) -> None:
        if not self.name:
            raise PromptAssemblyError("prompt context name may not be empty")

    def render(self, context: dict[str, Any] | None = None) -> str:
        resolved = self.text(context or {}) if callable(self.text) else self.text
        if not isinstance(resolved, str):
            raise PromptAssemblyError(f"prompt context {self.name!r} did not render a string")
        return resolved


@dataclass(frozen=True, slots=True)
class AssembledPrompt:
    sections: tuple[PromptSection, ...]
    text: str
    context_text: str = ""
    fingerprint: str = ""

    def to_document(self) -> dict[str, Any]:
        return {
            "sections": [section.name for section in self.sections],
            "text": self.text,
            "context_text": self.context_text,
            "fingerprint": self.fingerprint,
        }


class PromptAssembler:
    """Ordered prompt sections plus change-aware dynamic context snapshots."""

    def __init__(
        self,
        sections: Iterable[PromptSection] = (),
        contexts: Iterable[PromptContext] = (),
    ) -> None:
        self._sections: dict[str, PromptSection] = {}
        self._contexts: dict[str, PromptContext] = {}
        for section in sections:
            self.register_section(section)
        for context in contexts:
            self.register_context(context)

    def register_section(self, section: PromptSection) -> None:
        if section.name in self._sections:
            raise PromptAssemblyError(f"duplicate prompt section: {section.name}")
        self._sections[section.name] = section

    def register_context(self, context: PromptContext) -> None:
        if context.name in self._contexts:
            raise PromptAssemblyError(f"duplicate prompt context: {context.name}")
        self._contexts[context.name] = context

    def assemble(self, context: dict[str, Any] | None = None) -> AssembledPrompt:
        sections = sorted(
            self._sections.values(), key=lambda section: (section.order, section.name)
        )
        complete = [section for section in sections if section.complete]
        if len(complete) > 1:
            raise PromptAssemblyError("at most one prompt section may be complete")
        if complete:
            sections = [complete[0]]
        text = "\n\n".join(
            section.render(context) for section in sections if section.render(context).strip()
        )
        rendered_contexts = [
            (item.order, item.name, item.render(context))
            for item in self._contexts.values()
            if item.render(context).strip()
        ]
        rendered_contexts.sort(key=lambda item: (item[0], item[1]))
        context_text = "\n\n".join(item[2] for item in rendered_contexts)
        fingerprint = hashlib.sha256("\0".join((text, context_text)).encode("utf-8")).hexdigest()[
            :16
        ]
        return AssembledPrompt(tuple(sections), text, context_text, fingerprint)


__all__ = [
    "AssembledPrompt",
    "PromptAssembler",
    "PromptAssemblyError",
    "PromptContext",
    "PromptSection",
]
