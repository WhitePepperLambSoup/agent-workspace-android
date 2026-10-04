from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent_workspace.core.models import Capability, ToolSpec

from .base import ToolArgumentError, ToolError, json_result, optional_int, require_string
from .paths import StrPath, WorkspacePaths
from .process_worker import run_in_process

if TYPE_CHECKING:
    from agent_workspace.application.ports import ToolExecutionContext

_MAX_ARGUMENTS = 256
_MAX_ARGUMENT_CHARS = 32_767
_MAX_COMMAND_CHARS = 32_767
_MAX_STREAM_BYTES = 128 * 1024
_READ_CHUNK_BYTES = 16 * 1024
_MAX_EXECUTABLE_HASH_BYTES = 128 * 1024 * 1024


@dataclass(slots=True)
class _BoundedStream:
    retained: bytearray = field(default_factory=bytearray)
    total_bytes: int = 0
    digest: Any = field(default_factory=hashlib.sha256)

    def append(self, chunk: bytes) -> None:
        self.total_bytes += len(chunk)
        self.digest.update(chunk)
        remaining = _MAX_STREAM_BYTES - len(self.retained)
        if remaining > 0:
            self.retained.extend(chunk[:remaining])

    def result(self) -> dict[str, Any]:
        return {
            "text": bytes(self.retained).decode("utf-8", errors="replace"),
            "bytes": self.total_bytes,
            "sha256": self.digest.hexdigest(),
            "truncated": self.total_bytes > len(self.retained),
        }


def _drain_stream(stream: Any, output: _BoundedStream) -> None:
    try:
        while chunk := stream.read(_READ_CHUNK_BYTES):
            output.append(chunk)
    except (OSError, ValueError):
        return


def _safe_environment() -> dict[str, str]:
    result: dict[str, str] = {
        "CI": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_PAGER": "cat",
        "GIT_TERMINAL_PROMPT": "0",
        "NO_COLOR": "1",
        "PAGER": "cat",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONUTF8": "1",
    }
    for name in ("SystemDrive", "SystemRoot", "WINDIR", "PATHEXT", "COMSPEC"):
        value = os.environ.get(name)
        if value:
            result[name] = value
    temporary = tempfile.gettempdir()
    result["TEMP"] = temporary
    result["TMP"] = temporary
    result["HOME"] = temporary
    system_root = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR")
    if system_root:
        result["PATH"] = os.pathsep.join(
            (str(Path(system_root) / "System32"), str(Path(system_root)))
        )
    else:
        result["PATH"] = os.defpath
    return result


def _resolve_system_shell(kind: str) -> Path:
    if os.name != "nt":
        raise ToolError(f"{kind} execution is only available on Windows")
    system_root = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR")
    if not system_root:
        raise ToolError("Windows system directory is unavailable")
    relative = (
        Path("System32") / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if kind == "powershell"
        else Path("System32") / "cmd.exe"
    )
    return _resolve_executable(str(Path(system_root) / relative))


def _resolve_executable(value: str) -> Path:
    if "\x00" in value:
        raise ToolArgumentError("executable may not contain NUL")
    path = Path(value)
    if not path.is_absolute():
        raise ToolArgumentError(
            "direct process execution requires an absolute executable path; "
            "use discover_executables first"
        )
    text = str(path)
    if text.startswith("\\\\") or text.startswith("\\?\\") or text.startswith("\\.\\"):
        raise ToolArgumentError("UNC and device executable paths are not supported")
    try:
        resolved = path.resolve(strict=True)
        metadata = resolved.lstat()
    except OSError as exc:
        raise ToolError(f"cannot resolve executable: {path}") from exc
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    attributes = getattr(metadata, "st_file_attributes", 0)
    if not stat.S_ISREG(metadata.st_mode) or bool(attributes & reparse_flag):
        raise ToolError(f"executable is not a regular non-reparse file: {resolved}")
    if os.name == "nt" and resolved.suffix.casefold() not in {".exe", ".com"}:
        raise ToolArgumentError("direct Windows executables must use .exe or .com")
    return resolved


def _sha256_file(path: Path) -> str | None:
    try:
        if path.stat().st_size > _MAX_EXECUTABLE_HASH_BYTES:
            return None
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _required_executable_sha256(path: Path) -> str:
    digest = _sha256_file(path)
    if digest is None:
        raise ToolError(
            "executable identity is unavailable or exceeds "
            f"{_MAX_EXECUTABLE_HASH_BYTES} bytes: {path}"
        )
    return digest


def _known_executables() -> dict[str, dict[str, Any]]:
    candidates: dict[str, str | None] = {
        "python": sys.executable if not getattr(sys, "frozen", False) else shutil.which("python"),
        "python_launcher": shutil.which("py"),
        "git": shutil.which("git"),
        "uv": shutil.which("uv"),
        # Common document and artifact toolchains are discovered explicitly so
        # direct host execution can be audited in the same way as Python/Git.
        # They remain optional: missing installations are simply omitted.
        "xelatex": shutil.which("xelatex"),
        "pdflatex": shutil.which("pdflatex"),
        "lualatex": shutil.which("lualatex"),
        "latexmk": shutil.which("latexmk"),
        "tectonic": shutil.which("tectonic"),
        "pdfinfo": shutil.which("pdfinfo"),
        "pdftoppm": shutil.which("pdftoppm"),
    }
    if os.name == "nt":
        with_shells = {
            "powershell": str(_resolve_system_shell("powershell")),
            "cmd": str(_resolve_system_shell("cmd")),
        }
        candidates.update(with_shells)
    result: dict[str, dict[str, Any]] = {}
    for name, raw_path in candidates.items():
        if not raw_path:
            continue
        try:
            path = _resolve_executable(raw_path)
        except (ToolArgumentError, ToolError):
            continue
        try:
            digest = _required_executable_sha256(path)
        except ToolError:
            continue
        result[name] = {"path": str(path), "sha256": digest}
    return result


def _run_command_sync(
    workspace: str,
    kind: str,
    executable: str | None,
    argv: list[str],
    command: str | None,
    raw_cwd: str,
    timeout_seconds: int,
    environment_overrides: dict[str, str] | None = None,
    expected_executable_sha256: str | None = None,
) -> str:
    paths = WorkspacePaths(workspace)
    cwd = paths.resolve(raw_cwd)
    if not cwd.is_dir():
        raise ToolError(f"command working directory is not a directory: {cwd}")

    if kind == "direct":
        if executable is None:
            raise ToolArgumentError("direct execution requires 'executable'")
        resolved_executable = _resolve_executable(executable)
        arguments = [str(resolved_executable), *argv]
        command_digest = None
    else:
        if command is None:
            raise ToolArgumentError(f"{kind} execution requires 'command'")
        resolved_executable = (
            _resolve_executable(executable)
            if executable is not None
            else _resolve_system_shell(kind)
        )
        command_digest = hashlib.sha256(command.encode("utf-8")).hexdigest()
        arguments = (
            [
                str(resolved_executable),
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Restricted",
                "-Command",
                command,
            ]
            if kind == "powershell"
            else [str(resolved_executable), "/d", "/q", "/s", "/c", command]
        )

    executable_sha256 = _required_executable_sha256(resolved_executable)
    if (
        expected_executable_sha256 is not None
        and executable_sha256 != expected_executable_sha256.casefold()
    ):
        raise ToolError("executable changed after discovery or approval")

    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    started = time.monotonic()
    environment = _safe_environment()
    if environment_overrides:
        if any(
            not name.startswith("GIT_") or not name.isascii() or not value or "\x00" in value
            for name, value in environment_overrides.items()
        ):
            raise ToolArgumentError("internal process environment override is invalid")
        environment.update(environment_overrides)
    try:
        process = subprocess.Popen(
            arguments,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            creationflags=creation_flags,
        )
    except OSError as exc:
        raise ToolError(f"cannot start executable: {resolved_executable}") from exc

    assert process.stdout is not None
    assert process.stderr is not None
    stdout = _BoundedStream()
    stderr = _BoundedStream()
    readers = (
        threading.Thread(target=_drain_stream, args=(process.stdout, stdout), daemon=True),
        threading.Thread(target=_drain_stream, args=(process.stderr, stderr), daemon=True),
    )
    for reader in readers:
        reader.start()
    timed_out = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=2)
    finally:
        for reader in readers:
            reader.join(timeout=1)
        process.stdout.close()
        process.stderr.close()
        for reader in readers:
            reader.join(timeout=0.2)

    return json_result(
        {
            "kind": kind,
            "executable": str(resolved_executable),
            "executable_sha256": executable_sha256,
            "argv": argv if kind == "direct" else None,
            "command_sha256": command_digest,
            "cwd": paths.relative(cwd),
            "exit_code": process.returncode,
            "timed_out": timed_out,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "stdout": stdout.result(),
            "stderr": stderr.result(),
        }
    )


class DiscoverExecutablesTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="discover_executables",
        description=(
            "List absolute paths and SHA-256 identities for supported local runtimes. "
            "Use these paths with run_process."
        ),
        input_schema={"type": "object", "additionalProperties": False},
        side_effect="none",
        capability=Capability.PROCESS_EXECUTE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, _arguments: dict[str, Any]) -> str:
        return json_result({"executables": _known_executables()})


class RunProcessTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="run_process",
        description=(
            "Run an audited local process in the workspace. Direct mode requires an absolute "
            "executable whose path and SHA-256 match a runtime listed by discover_executables. "
            "PowerShell and CMD are explicit shell modes. Every invocation runs with a clean "
            "environment."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["direct", "powershell", "cmd"]},
                "executable": {"type": "string", "minLength": 1, "maxLength": 32767},
                "expected_executable_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-fA-F]{64}$",
                },
                "argv": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": _MAX_ARGUMENT_CHARS},
                    "maxItems": _MAX_ARGUMENTS,
                    "default": [],
                },
                "command": {"type": "string", "minLength": 1, "maxLength": 32767},
                "cwd": {"type": "string", "minLength": 1, "default": "."},
                "timeout_seconds": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 110,
                    "default": 60,
                },
            },
            "required": ["kind"],
            "oneOf": [
                {
                    "properties": {"kind": {"const": "direct"}},
                    "required": ["executable", "expected_executable_sha256"],
                    "not": {"required": ["command"]},
                },
                {
                    "properties": {"kind": {"enum": ["powershell", "cmd"]}},
                    "required": ["command"],
                    "not": {"required": ["executable"]},
                },
            ],
            "additionalProperties": False,
        },
        side_effect="process",
        capability=Capability.PROCESS_EXECUTE,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def prepare_for_approval(self, arguments: dict[str, Any]) -> dict[str, Any]:
        prepared = dict(arguments)
        kind = require_string(prepared, "kind")
        if kind == "direct":
            executable = _resolve_executable(require_string(prepared, "executable"))
            expected = require_string(prepared, "expected_executable_sha256").casefold()
            if len(expected) != 64 or any(
                character not in "0123456789abcdef" for character in expected
            ):
                raise ToolArgumentError("'expected_executable_sha256' must be a SHA-256 digest")
            if _required_executable_sha256(executable) != expected:
                raise ToolError("executable does not match its discovered SHA-256")
            discovered = _known_executables()
            if not any(
                str(executable) == entry["path"] and expected == entry["sha256"]
                for entry in discovered.values()
            ):
                raise ToolError(
                    "direct execution requires a runtime listed by discover_executables; "
                    "re-run discover_executables and use one of its paths"
                )
        elif kind in {"powershell", "cmd"}:
            executable = _resolve_system_shell(kind)
            expected = _required_executable_sha256(executable)
        else:
            raise ToolArgumentError("'kind' is unsupported")
        prepared["executable"] = str(executable)
        prepared["expected_executable_sha256"] = expected
        return prepared

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await self.execute_with_context(arguments, None)

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        _context: ToolExecutionContext | None,
    ) -> str:
        kind = require_string(arguments, "kind")
        if kind not in {"direct", "powershell", "cmd"}:
            raise ToolArgumentError("'kind' is unsupported")
        if kind == "direct" or "expected_executable_sha256" not in arguments:
            arguments = self.prepare_for_approval(arguments)
        raw_argv = arguments.get("argv", [])
        if not isinstance(raw_argv, list) or any(not isinstance(item, str) for item in raw_argv):
            raise ToolArgumentError("'argv' must be an array of strings")
        argv = list(raw_argv)
        if any("\x00" in item for item in argv):
            raise ToolArgumentError("'argv' items may not contain NUL")
        executable = arguments.get("executable")
        command = arguments.get("command")
        if isinstance(command, str) and "\x00" in command:
            raise ToolArgumentError("'command' may not contain NUL")
        expected_executable_sha256 = require_string(
            arguments,
            "expected_executable_sha256",
        ).casefold()
        if executable is not None and not isinstance(executable, str):
            raise ToolArgumentError("'executable' must be a string")
        if command is not None and not isinstance(command, str):
            raise ToolArgumentError("'command' must be a string")
        cwd = arguments.get("cwd", ".")
        if not isinstance(cwd, str) or not cwd:
            raise ToolArgumentError("'cwd' must be a non-empty string")
        timeout_seconds = optional_int(arguments, "timeout_seconds", 60, minimum=1, maximum=110)
        return await run_in_process(
            _run_command_sync,
            str(self.paths.root),
            kind,
            executable,
            argv,
            command,
            cwd,
            timeout_seconds,
            None,
            expected_executable_sha256,
            allow_children=True,
        )


class PreviewProcessTool:
    """Validate and preview a process invocation without running it.

    The preview performs exactly the same executable identity, working
    directory, and argument validation as :class:`RunProcessTool`, then
    returns the final argv/environment plan instead of spawning a process.
    """

    hard_cancellable = True
    _SPEC = ToolSpec(
        name="preview_process",
        description=(
            "Preview a local process invocation without executing it. Direct mode requires "
            "an absolute executable whose path and SHA-256 match a runtime listed by "
            "discover_executables. PowerShell and CMD are explicit shell modes. Returns the "
            "exact argv, cwd, and environment that run_process would use."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["direct", "powershell", "cmd"]},
                "executable": {"type": "string", "minLength": 1, "maxLength": 32767},
                "expected_executable_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-fA-F]{64}$",
                },
                "argv": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": _MAX_ARGUMENT_CHARS},
                    "maxItems": _MAX_ARGUMENTS,
                    "default": [],
                },
                "command": {"type": "string", "minLength": 1, "maxLength": 32767},
                "cwd": {"type": "string", "minLength": 1, "default": "."},
            },
            "required": ["kind"],
            "oneOf": [
                {
                    "properties": {"kind": {"const": "direct"}},
                    "required": ["executable", "expected_executable_sha256"],
                    "not": {"required": ["command"]},
                },
                {
                    "properties": {"kind": {"enum": ["powershell", "cmd"]}},
                    "required": ["command"],
                    "not": {"required": ["executable"]},
                },
            ],
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.PROCESS_EXECUTE,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def prepare_for_approval(self, arguments: dict[str, Any]) -> dict[str, Any]:
        prepared = dict(arguments)
        kind = require_string(prepared, "kind")
        if kind == "direct":
            executable = _resolve_executable(require_string(prepared, "executable"))
            expected = require_string(prepared, "expected_executable_sha256").casefold()
            if len(expected) != 64 or any(
                character not in "0123456789abcdef" for character in expected
            ):
                raise ToolArgumentError("'expected_executable_sha256' must be a SHA-256 digest")
            if _required_executable_sha256(executable) != expected:
                raise ToolError("executable does not match its discovered SHA-256")
            discovered = _known_executables()
            if not any(
                str(executable) == entry["path"] and expected == entry["sha256"]
                for entry in discovered.values()
            ):
                raise ToolError(
                    "direct execution requires a runtime listed by discover_executables; "
                    "re-run discover_executables and use one of its paths"
                )
        elif kind in {"powershell", "cmd"}:
            executable = _resolve_system_shell(kind)
            expected = _required_executable_sha256(executable)
        else:
            raise ToolArgumentError("'kind' is unsupported")
        prepared["executable"] = str(executable)
        prepared["expected_executable_sha256"] = expected
        return prepared

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await self.execute_with_context(arguments, None)

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        _context: ToolExecutionContext | None,
    ) -> str:
        kind = require_string(arguments, "kind")
        if kind not in {"direct", "powershell", "cmd"}:
            raise ToolArgumentError("'kind' is unsupported")
        arguments = self.prepare_for_approval(arguments)
        raw_argv = arguments.get("argv", [])
        if not isinstance(raw_argv, list) or any(not isinstance(item, str) for item in raw_argv):
            raise ToolArgumentError("'argv' must be an array of strings")
        argv = list(raw_argv)
        if any("\x00" in item for item in argv):
            raise ToolArgumentError("'argv' items may not contain NUL")
        command = arguments.get("command")
        if command is not None and not isinstance(command, str):
            raise ToolArgumentError("'command' must be a string")
        if isinstance(command, str) and "\x00" in command:
            raise ToolArgumentError("'command' may not contain NUL")
        executable = require_string(arguments, "executable")
        expected_executable_sha256 = require_string(
            arguments,
            "expected_executable_sha256",
        ).casefold()
        cwd = arguments.get("cwd", ".")
        if not isinstance(cwd, str) or not cwd:
            raise ToolArgumentError("'cwd' must be a non-empty string")
        resolved_cwd = self.paths.resolve(cwd)
        if not resolved_cwd.is_dir():
            raise ToolError(f"command working directory is not a directory: {resolved_cwd}")
        environment = _safe_environment()
        return json_result(
            {
                "kind": kind,
                "executable": executable,
                "executable_sha256": expected_executable_sha256,
                "argv": argv if kind == "direct" else None,
                "command": command if kind in {"powershell", "cmd"} else None,
                "command_sha256": (
                    hashlib.sha256(command.encode("utf-8")).hexdigest()
                    if command is not None
                    else None
                ),
                "cwd": self.paths.relative(resolved_cwd),
                "environment_keys": sorted(environment),
            }
        )
