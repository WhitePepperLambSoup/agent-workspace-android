"""Bounded Android subprocess execution without a Windows console or a forked VM."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import signal
import subprocess
import threading
import time
from dataclasses import replace
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result, optional_int
from agent_workspace.tools.command import (
    RunProcessTool,
    _required_executable_sha256,
    _resolve_executable,
)
from agent_workspace.tools.paths import StrPath, WorkspacePaths

MAX_OUTPUT_BYTES = 512 * 1024
_MAX_INPUT_CHARS = 100_000
_MAX_ARGUMENT_BYTES = 128 * 1024


def _environment() -> dict[str, str]:
    from agent_workspace.tools.command import _safe_environment

    environment = _safe_environment()
    for name in ("PATH", "TMPDIR", "PREFIX", "ANDROID_ROOT", "ANDROID_DATA"):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    return environment


def _terminate(process: subprocess.Popen[bytes]) -> None:
    # Kill the session even if its leader exited: descendants may retain the pipes.
    if os.name == "nt":
        if process.poll() is None:
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                subprocess.run(
                    [
                        str(
                            os.path.join(
                                os.environ.get("SYSTEMROOT", "C:\\Windows"),
                                "System32",
                                "taskkill.exe",
                            )
                        ),
                        "/PID",
                        str(process.pid),
                        "/T",
                        "/F",
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
    if process.poll() is None:
        with contextlib.suppress(OSError):
            process.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=2)


def _run_sync(
    argv: list[str],
    cwd: str,
    timeout: int,
    startup_input: str,
    cancelled: threading.Event,
    environment: dict[str, str] | None = None,
    *,
    separate_stderr: bool = False,
) -> dict[str, Any]:
    options: dict[str, Any] = {"start_new_session": os.name != "nt"}
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env={**_environment(), **(environment or {})},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if separate_stderr else subprocess.STDOUT,
            shell=False,
            **options,
        )
    except OSError as exc:
        raise ToolError(f"cannot start Android command: {argv[0]}") from exc
    streams: dict[str, dict[str, Any]] = {
        name: {"retained": bytearray(), "bytes": 0, "digest": hashlib.sha256()}
        for name in ("stdout", "stderr")
    }
    output_exceeded = threading.Event()
    assert process.stdout is not None and process.stdin is not None

    def read(pipe: Any, name: str) -> None:
        record = streams[name]
        try:
            while chunk := pipe.read(16 * 1024):
                record["bytes"] += len(chunk)
                record["digest"].update(chunk)
                retained = record["retained"]
                remaining = MAX_OUTPUT_BYTES - len(retained)
                if remaining > 0:
                    retained.extend(chunk[:remaining])
                if record["bytes"] > MAX_OUTPUT_BYTES:
                    output_exceeded.set()
        except (OSError, ValueError):
            return

    def write() -> None:
        try:
            if startup_input:
                process.stdin.write(startup_input.encode("utf-8"))
                process.stdin.flush()
        except (OSError, ValueError):
            pass
        finally:
            with contextlib.suppress(OSError):
                process.stdin.close()

    readers = [
        threading.Thread(
            target=read, args=(process.stdout, "stdout"), daemon=True, name="android-command-output"
        )
    ]
    if separate_stderr:
        assert process.stderr is not None
        readers.append(
            threading.Thread(
                target=read,
                args=(process.stderr, "stderr"),
                daemon=True,
                name="android-command-error",
            )
        )
    writer = threading.Thread(target=write, daemon=True, name="android-command-input")
    for reader in readers:
        reader.start()
    writer.start()
    deadline = time.monotonic() + timeout
    timed_out = False
    try:
        while process.poll() is None or any(reader.is_alive() for reader in readers):
            timed_out = time.monotonic() >= deadline
            if timed_out or cancelled.is_set() or output_exceeded.is_set():
                _terminate(process)
                break
            if process.poll() is not None:
                # A background child must not extend the lifecycle after its parent exits.
                _terminate(process)
                for reader in readers:
                    reader.join(timeout=0.2)
                break
            cancelled.wait(0.02)
    finally:
        _terminate(process)
        for reader in readers:
            reader.join(timeout=2)
        writer.join(timeout=2)
        with contextlib.suppress(OSError):
            process.stdout.close()
        with contextlib.suppress(OSError):
            process.stdin.close()
        if process.stderr is not None:
            with contextlib.suppress(OSError):
                process.stderr.close()
    result = {
        "returncode": process.returncode,
        "timed_out": timed_out,
        "truncated": streams["stdout"]["bytes"] > MAX_OUTPUT_BYTES,
        "output_limit_exceeded": output_exceeded.is_set(),
        "terminal": "android-pipes",
    }
    for name, record in streams.items():
        result[name] = bytes(record["retained"]).decode("utf-8", errors="replace")
        result[name + "_bytes"] = record["bytes"]
        result[name + "_sha256"] = record["digest"].hexdigest()
        result[name + "_truncated"] = record["bytes"] > MAX_OUTPUT_BYTES
    return result


async def run_bounded_command(
    paths: WorkspacePaths,
    argv: list[str],
    raw_cwd: str,
    timeout: int,
    startup_input: str = "",
) -> dict[str, Any]:
    if (
        not argv
        or len(argv) > 256
        or any(
            not isinstance(item, str) or not item or "\x00" in item or len(item) > 32767
            for item in argv
        )
        or sum(len(item.encode("utf-8")) for item in argv) > _MAX_ARGUMENT_BYTES
    ):
        raise ToolArgumentError("'argv' must be a bounded array of non-empty strings")
    if (
        not isinstance(startup_input, str)
        or len(startup_input) > _MAX_INPUT_CHARS
        or "\x00" in startup_input
    ):
        raise ToolArgumentError("'input' must be bounded text without NUL")
    if not isinstance(raw_cwd, str) or not raw_cwd:
        raise ToolArgumentError("'cwd' must be a non-empty workspace path")
    cwd = paths.resolve(raw_cwd)
    if not cwd.is_dir():
        raise ToolError("terminal working directory is not a directory")
    cancelled = threading.Event()
    from .toolchain import command_transport

    transported, environment, lease = command_transport(argv, cwd)
    argv = transported
    worker = asyncio.create_task(
        asyncio.to_thread(_run_sync, argv, str(cwd), timeout, startup_input, cancelled, environment)
    )
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        cancelled.set()
        # Cancellation must finish cleanup before the task is reported cancelled.
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
        with contextlib.suppress(Exception):
            worker.result()
        raise
    finally:
        if lease is not None:
            lease.end_process()


class AndroidRunTerminalTool:
    hard_cancellable = False
    _SPEC = ToolSpec(
        name="run_terminal",
        description=(
            "Run bounded argv using Android app permissions and pipe-backed output. "
            "Use discovered executables. Verified optional Linux tools use the packaged "
            "PRoot launcher; /system/bin/sh remains available without that installation. "
            "This does not provide an interactive PTY or an OS security sandbox."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "argv": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1, "maxLength": 32767},
                    "minItems": 1,
                    "maxItems": 256,
                },
                "cwd": {"type": "string", "minLength": 1, "default": "."},
                "input": {"type": "string", "maxLength": _MAX_INPUT_CHARS},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 300},
            },
            "required": ["argv"],
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

    async def execute(self, arguments: dict[str, Any]) -> str:
        argv = arguments.get("argv")
        if not isinstance(argv, list):
            raise ToolArgumentError("'argv' must be an array")
        timeout = optional_int(arguments, "timeout_seconds", 60, minimum=1, maximum=300)
        return json_result(
            await run_bounded_command(
                self.paths, argv, arguments.get("cwd", "."), timeout, arguments.get("input", "")
            )
        )


class AndroidRunProcessTool(RunProcessTool):
    hard_cancellable = False
    _SPEC = replace(
        RunProcessTool._SPEC,
        description=(
            "Run an approved Android executable with bounded output and a clean environment. "
            "Direct execution requires a path and SHA-256 returned by discover_executables."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["direct"]},
                "executable": {"type": "string", "minLength": 1, "maxLength": 32767},
                "expected_executable_sha256": {"type": "string", "pattern": "^[0-9a-fA-F]{64}$"},
                "argv": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 32767},
                    "maxItems": 256,
                },
                "cwd": {"type": "string", "minLength": 1, "default": "."},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 110},
            },
            "required": ["kind", "executable", "expected_executable_sha256"],
            "additionalProperties": False,
        },
    )

    def prepare_for_approval(self, arguments: dict[str, Any]) -> dict[str, Any]:
        from .capabilities import discover_runnable_executables

        if arguments.get("kind") != "direct":
            raise ToolArgumentError("Android process execution supports only direct mode")
        raw_executable = arguments.get("executable")
        if not isinstance(raw_executable, str):
            raise ToolArgumentError("'executable' must be an absolute path")
        executable = _resolve_executable(raw_executable)
        expected = arguments.get("expected_executable_sha256")
        if not isinstance(expected, str) or len(expected) != 64:
            raise ToolArgumentError("'expected_executable_sha256' must be a SHA-256 digest")
        digest = _required_executable_sha256(executable)
        if digest != expected.casefold():
            raise ToolError("executable changed from its discovered SHA-256")
        if not any(
            str(executable) == entry["path"] and digest == entry["sha256"]
            for entry in discover_runnable_executables(self.paths.root).values()
        ):
            raise ToolError("Android executable is unavailable; use discover_executables")
        return {**arguments, "executable": str(executable), "expected_executable_sha256": digest}

    async def execute_with_context(self, arguments: dict[str, Any], _context: Any) -> str:
        prepared = self.prepare_for_approval(arguments)
        argv = prepared.get("argv", [])
        if not isinstance(argv, list):
            raise ToolArgumentError("'argv' must be an array")
        timeout = optional_int(prepared, "timeout_seconds", 60, minimum=1, maximum=110)
        result = await run_bounded_command(
            self.paths, [prepared["executable"], *argv], prepared.get("cwd", "."), timeout
        )
        result.update(
            {
                "kind": "direct",
                "exit_code": result["returncode"],
                "executable": prepared["executable"],
                "executable_sha256": prepared["expected_executable_sha256"],
            }
        )
        return json_result(result)
