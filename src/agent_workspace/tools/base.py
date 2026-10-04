from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from agent_workspace.core.models import ToolSpec


class ToolError(RuntimeError):
    """Base error raised by built-in tools."""


class ToolArgumentError(ToolError):
    """Raised when tool arguments do not match the tool schema."""


class ConcurrentModificationError(ToolError):
    """Raised when a file no longer has the expected content digest."""


def check_tool_schema(spec: ToolSpec) -> None:
    try:
        Draft202012Validator.check_schema(spec.input_schema)
        Draft202012Validator.check_schema(spec.advertised_input_schema)
    except SchemaError as exc:
        raise ValueError(f"tool {spec.name!r} has an invalid input schema") from exc


def validate_tool_arguments(spec: ToolSpec, arguments: dict[str, Any]) -> None:
    errors = sorted(
        Draft202012Validator(spec.input_schema).iter_errors(arguments),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if not errors:
        return
    error = errors[0]
    location = ".".join(str(part) for part in error.absolute_path)
    prefix = f"{location}: " if location else ""
    raise ToolArgumentError(f"invalid arguments for {spec.name}: {prefix}{error.message}")


def require_string(arguments: dict[str, Any], name: str, *, allow_empty: bool = False) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or (not allow_empty and not value):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise ToolArgumentError(f"{name!r} must be {qualifier}")
    return value


def optional_bool(arguments: dict[str, Any], name: str, default: bool) -> bool:
    value = arguments.get(name, default)
    if not isinstance(value, bool):
        raise ToolArgumentError(f"{name!r} must be a boolean")
    return value


def optional_int(
    arguments: dict[str, Any],
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    value = arguments.get(name, default)
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ToolArgumentError(f"{name!r} must be an integer from {minimum} to {maximum}")
    return value


def json_result(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
