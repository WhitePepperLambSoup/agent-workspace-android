from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError
from agent_workspace.tools.command import _resolve_executable, _run_command_sync
from agent_workspace.tools.paths import StrPath, WorkspacePaths
from agent_workspace.tools.process_worker import run_in_process

_TOOL_NAME_PATTERN = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")
_MAX_ARGUMENT_ITEM_CHARS = 32_767


class CustomToolError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CustomToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    argv_template: tuple[str, ...]
    executable: str
    executable_sha256: str
    timeout_seconds: int
    cwd: str
    append_workspace: bool
    path: str


def _custom_tool_files(workspace: StrPath) -> tuple[Path, ...]:
    root = Path(workspace)
    try:
        root = root.resolve(strict=True)
    except (OSError, RuntimeError):
        return ()
    directory = root / ".agent" / "tools"
    if not directory.is_dir():
        return ()
    return tuple(sorted(directory.glob("*.toml")))


def _substitute(argv_template: tuple[str, ...], arguments: dict[str, Any]) -> list[str]:
    resolved: list[str] = []
    for item in argv_template:
        if item == "{args}":
            resolved.append(
                json.dumps(
                    arguments,
                    sort_keys=True,
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            )
        elif item.startswith("{arg:") and item.endswith("}"):
            key = item[len("{arg:") : -1]
            if key not in arguments:
                raise ToolArgumentError(f"custom tool argument {key!r} is missing")
            value = arguments[key]
            if isinstance(value, bool):
                value = "true" if value else "false"
            if not isinstance(value, (str, int, float)):
                raise ToolArgumentError(f"custom tool argument {key!r} must be scalar")
            resolved.append(str(value))
        else:
            resolved.append(item)
    for item in resolved:
        if len(item) > _MAX_ARGUMENT_ITEM_CHARS:
            raise ToolArgumentError("custom tool argument exceeds its size limit")
    return resolved


def load_custom_tool_definitions(workspace: StrPath) -> tuple[CustomToolDefinition, ...]:
    """Load declarative custom tools from .agent/tools/*.toml.

    Declared commands run through the same audited direct-execution contract
    as run_process: an absolute executable, a pinned SHA-256 identity, a clean
    environment, bounded output, and the active autonomy policy's approval
    rules (FULL ACCESS can run it without a routine prompt).
    """
    definitions: list[CustomToolDefinition] = []
    for path in _custom_tool_files(workspace):
        try:
            with path.open("rb") as stream:
                raw: object = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
            raise CustomToolError(f"cannot read custom tool file {path}: {exc}") from None
        if not isinstance(raw, dict):
            raise CustomToolError(f"custom tool file {path} must contain a table")
        name = raw.get("name")
        description = raw.get("description")
        parameters = raw.get("parameters")
        command = raw.get("command")
        executable_sha256 = raw.get("executable_sha256")
        timeout_seconds = raw.get("timeout_seconds", 60)
        cwd = raw.get("cwd", ".")
        append_workspace = raw.get("append_workspace", False)
        if (
            not isinstance(name, str)
            or _TOOL_NAME_PATTERN.fullmatch(name) is None
            or not isinstance(description, str)
            or not description.strip()
            or len(description) > 4000
            or not isinstance(parameters, dict)
            or parameters.get("type") != "object"
            or not isinstance(command, list)
            or len(command) < 1
            or any(not isinstance(item, str) or not item for item in command)
            or not isinstance(executable_sha256, str)
            or _SHA256_PATTERN.fullmatch(executable_sha256) is None
            or type(timeout_seconds) is not int
            or not 1 <= timeout_seconds <= 110
            or not isinstance(cwd, str)
            or not cwd
            or type(append_workspace) is not bool
        ):
            raise CustomToolError(f"custom tool file {path} contains invalid fields")
        try:
            Draft202012Validator.check_schema(parameters)
        except SchemaError as exc:
            raise CustomToolError(f"custom tool {name!r} has an invalid schema: {exc}") from None
        try:
            executable = _resolve_executable(command[0])
        except (ToolArgumentError, ToolError) as exc:
            raise CustomToolError(f"custom tool {name!r} executable is invalid: {exc}") from None
        properties = parameters.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        for item in command[1:]:
            if item.startswith("{arg:") and item.endswith("}"):
                key = item[len("{arg:") : -1]
                if key not in properties:
                    raise CustomToolError(
                        f"custom tool {name!r} references unknown argument {key!r}"
                    )
        if any(definition.name == name for definition in definitions):
            raise CustomToolError(f"custom tool name {name!r} is duplicated")
        definitions.append(
            CustomToolDefinition(
                name=name,
                description=description.strip(),
                input_schema=parameters,
                argv_template=tuple(command[1:]),
                executable=str(executable),
                executable_sha256=executable_sha256.casefold(),
                timeout_seconds=timeout_seconds,
                cwd=cwd,
                append_workspace=append_workspace,
                path=str(path),
            )
        )
    return tuple(definitions)


class CustomCommandTool:
    """A workspace-declared command wrapped as an auditable agent tool."""

    hard_cancellable = True

    def __init__(
        self,
        workspace: WorkspacePaths | StrPath,
        definition: CustomToolDefinition,
    ) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        self.definition = definition
        self._spec = ToolSpec(
            name=definition.name,
            description=(
                f"{definition.description} Declared custom workspace tool; executes an "
                "audited pinned executable with a clean environment."
            ),
            input_schema=definition.input_schema,
            side_effect="process",
            capability=Capability.PROCESS_EXECUTE,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def prepare_for_approval(self, arguments: dict[str, Any]) -> dict[str, Any]:
        # Declared tools execute with a strict schema: undeclared keys are
        # rejected so a model cannot smuggle extra parameters into the argv
        # template or the audited command.
        strict_schema = dict(self.definition.input_schema)
        strict_schema["additionalProperties"] = False
        errors = tuple(Draft202012Validator(strict_schema).iter_errors(arguments))
        if errors:
            raise ToolArgumentError(
                f"invalid arguments for {self.definition.name}: {errors[0].message}"
            )
        cwd = self.paths.resolve(self.definition.cwd)
        if not cwd.is_dir():
            raise ToolError(f"custom tool working directory is not a directory: {cwd}")
        return {
            "_custom_cwd": self.paths.relative(cwd),
            "_custom_argv": tuple(_substitute(self.definition.argv_template, arguments)),
            "_custom_append_workspace": self.definition.append_workspace,
            "cwd": self.paths.relative(cwd),
        }

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await self.execute_with_context(arguments, None)

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        _context: object | None,
    ) -> str:
        if "_custom_argv" not in arguments:
            arguments = self.prepare_for_approval(arguments)
        raw_argv = arguments.get("_custom_argv")
        raw_cwd = arguments.get("_custom_cwd")
        if not isinstance(raw_argv, tuple) or not isinstance(raw_cwd, str):
            raise ToolArgumentError("custom tool execution context is invalid")
        argv = list(raw_argv)
        if arguments.get("_custom_append_workspace") is True:
            argv.append(str(self.paths.root))
        return await run_in_process(
            _run_command_sync,
            str(self.paths.root),
            "direct",
            self.definition.executable,
            argv,
            None,
            raw_cwd,
            self.definition.timeout_seconds,
            None,
            self.definition.executable_sha256,
            allow_children=True,
        )
