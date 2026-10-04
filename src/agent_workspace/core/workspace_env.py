"""Workspace environment variable manager.

Variables are stored in ``<workspace>/.agent/env.toml`` so they travel with
the workspace and can be committed to version control when they are not
secret. Values never appear in memory outside this module's requested entries.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_NAME_LENGTH = 128
_MAX_VALUE_LENGTH = 32_767
_ATOMIC_SUFFIX = ".tmp"


@dataclass(frozen=True, slots=True)
class WorkspaceEnvironmentVariable:
    name: str
    value: str
    secret: bool
    path: Path

    def to_document(self, *, redact_secrets: bool = False) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": "<redacted>" if redact_secrets and self.secret else self.value,
            "secret": self.secret,
            "path": str(self.path),
        }


class WorkspaceEnvironmentError(ValueError):
    pass


def _validate_name(name: str) -> None:
    if not isinstance(name, str) or not _NAME_PATTERN.fullmatch(name):
        raise WorkspaceEnvironmentError(
            f"environment variable name must match {_NAME_PATTERN.pattern!r}"
        )
    if len(name) > _MAX_NAME_LENGTH:
        raise WorkspaceEnvironmentError("environment variable name is too long")


def _validate_value(value: str) -> None:
    if not isinstance(value, str) or "\x00" in value:
        raise WorkspaceEnvironmentError("environment variable value must be text without NUL")
    if len(value) > _MAX_VALUE_LENGTH:
        raise WorkspaceEnvironmentError("environment variable value is too long")


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _render_document(variables: dict[str, WorkspaceEnvironmentVariable]) -> str:
    lines: list[str] = [
        "# Workspace environment variables. Secret values stay in this file.",
        "",
    ]
    for name in sorted(variables):
        variable = variables[name]
        lines.append(f'[variables."{name}"]')
        lines.append(f"value = {_toml_string(variable.value)}")
        lines.append(f"secret = {'true' if variable.secret else 'false'}")
        lines.append("")
    return "\n".join(lines)


class WorkspaceEnvironment:
    """Read and update the environment variable file for one workspace."""

    def __init__(self, workspace: str | Path) -> None:
        root = Path(workspace).expanduser().resolve()
        if not root.is_dir():
            raise WorkspaceEnvironmentError("workspace is not a directory")
        self.root = root
        self.path = root / ".agent" / "env.toml"
        self._variables: dict[str, WorkspaceEnvironmentVariable] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            document = tomllib.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise WorkspaceEnvironmentError(f"cannot read workspace env file: {exc}") from exc
        raw_variables = document.get("variables", {})
        if not isinstance(raw_variables, dict):
            raise WorkspaceEnvironmentError("workspace env file has an invalid variables table")
        for name, raw in raw_variables.items():
            if not isinstance(name, str) or not isinstance(raw, dict):
                raise WorkspaceEnvironmentError("workspace env file has an invalid variable")
            value = raw.get("value", "")
            secret = raw.get("secret", False)
            if not isinstance(value, str) or not isinstance(secret, bool):
                raise WorkspaceEnvironmentError("workspace env file has an invalid variable")
            _validate_name(name)
            _validate_value(value)
            self._variables[name] = WorkspaceEnvironmentVariable(
                name=name,
                value=value,
                secret=secret,
                path=self.path,
            )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}{_ATOMIC_SUFFIX}")
        temporary.write_text(_render_document(self._variables), encoding="utf-8", newline="\n")
        temporary.replace(self.path)

    def list(self) -> tuple[WorkspaceEnvironmentVariable, ...]:
        return tuple(sorted(self._variables.values(), key=lambda variable: variable.name))

    def get(self, name: str) -> WorkspaceEnvironmentVariable | None:
        _validate_name(name)
        return self._variables.get(name)

    def set(self, name: str, value: str, *, secret: bool = False) -> WorkspaceEnvironmentVariable:
        _validate_name(name)
        _validate_value(value)
        variable = WorkspaceEnvironmentVariable(name, value, secret, self.path)
        self._variables[name] = variable
        self.save()
        return variable

    def unset(self, name: str) -> bool:
        _validate_name(name)
        if name not in self._variables:
            return False
        del self._variables[name]
        self.save()
        return True

    def apply(self, environment: dict[str, str] | None = None) -> dict[str, str]:
        """Return a copy of ``environment`` with workspace variables applied."""
        merged = dict(environment or {})
        for variable in self.list():
            merged[variable.name] = variable.value
        return merged


__all__ = [
    "WorkspaceEnvironment",
    "WorkspaceEnvironmentError",
    "WorkspaceEnvironmentVariable",
]
