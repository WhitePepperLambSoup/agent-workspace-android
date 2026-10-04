"""Versioned prompt templates with bounded rendering."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PromptTemplateError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    id: str
    version: int
    template: str
    description: str = ""
    variables: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id or len(self.id) > 128:
            raise PromptTemplateError("prompt template id must be 1-128 characters")
        if self.version < 1:
            raise PromptTemplateError("prompt template version must be positive")
        if not self.template.strip():
            raise PromptTemplateError("prompt template text may not be empty")
        if len(self.template) > 64 * 1024:
            raise PromptTemplateError("prompt template exceeds 64 KiB")
        if len(set(self.variables)) != len(self.variables):
            raise PromptTemplateError("prompt template variables must be unique")

    def render(self, variables: dict[str, str] | None = None) -> str:
        values = variables or {}
        unknown = set(values) - set(self.variables)
        if unknown:
            raise PromptTemplateError(f"unknown template variables: {', '.join(sorted(unknown))}")
        try:
            return self.template.format(**values)
        except KeyError as exc:
            raise PromptTemplateError(f"missing template variable: {exc.args[0]}") from None

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "template": self.template,
            "description": self.description,
            "variables": list(self.variables),
        }

    @classmethod
    def from_document(cls, value: object) -> PromptTemplate:
        if not isinstance(value, dict):
            raise PromptTemplateError("prompt template document must be an object")
        try:
            variables = value.get("variables", ())
            if not isinstance(variables, (list, tuple)) or not all(
                isinstance(variable, str) and variable for variable in variables
            ):
                raise PromptTemplateError("prompt template variables must be strings")
            return cls(
                id=str(value["id"]),
                version=int(value["version"]),
                template=str(value["template"]),
                description=str(value.get("description", "")),
                variables=tuple(variables),
            )
        except PromptTemplateError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise PromptTemplateError("prompt template document is invalid") from exc


class PromptTemplateRegistry:
    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {}

    def register(self, template: PromptTemplate) -> None:
        existing = self._templates.get(template.id)
        if existing is not None and existing.version > template.version:
            raise PromptTemplateError(
                f"prompt template {template.id!r} would downgrade "
                f"version {existing.version} to {template.version}"
            )
        self._templates[template.id] = template

    def get(self, template_id: str) -> PromptTemplate | None:
        return self._templates.get(template_id)

    def render(self, template_id: str, variables: dict[str, str] | None = None) -> str:
        template = self._templates.get(template_id)
        if template is None:
            raise KeyError(f"unknown prompt template: {template_id}")
        return template.render(variables)

    def load(self, path: str | Path) -> None:
        source = Path(path)
        if source.suffix == ".json":
            document = json.loads(source.read_text(encoding="utf-8"))
        else:
            with source.open("rb") as stream:
                document = tomllib.load(stream)
        if not isinstance(document, dict) or not isinstance(document.get("templates"), list):
            raise PromptTemplateError(f"prompt template file {source} is invalid")
        for raw in document["templates"]:
            self.register(PromptTemplate.from_document(raw))


__all__ = [
    "PromptTemplate",
    "PromptTemplateError",
    "PromptTemplateRegistry",
]
