"""Explicitly opt-in host execution with a staged workspace.

This is the built-in execution backend for the desktop and CLI. It creates a
private workspace copy, runs a structured command under native process limits,
and returns the changes as a reviewable sandbox changeset. The child process
still runs with the host user's filesystem and network permissions, so the
backend is a workflow and change-review boundary rather than an OS security
boundary.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from agent_workspace.core.models import BinaryArtifact

from .base import ToolArgumentError, ToolError, json_result
from .command import _required_executable_sha256, _resolve_executable, _safe_environment
from .native_isolation import inspect_native_isolation
from .paths import StrPath, WorkspacePaths
from .process_worker import _WindowsJob, run_in_process
from .sandbox import (
    LocalSandboxConfig,
    SandboxExecutionResult,
    SandboxRequest,
    SandboxStatus,
    sandbox_status,
)
from .sandbox_staging import (
    StagingWorkspace,
    capture_staging_artifacts_sync,
    create_staging_workspace_sync,
    diff_staging_workspace_sync,
    recover_stale_staging_workspaces_sync,
    remove_staging_workspace_sync,
    staging_creating_root_for_execution,
    staging_root_for_execution,
)

_MAX_ARGUMENTS = 256
_MAX_ARGUMENT_CHARS = 32_767
_MAX_ARGUMENT_BYTES = 128 * 1024
_MAX_RETAINED_STREAM_BYTES = 128 * 1024
_MAX_OBSERVED_STREAM_BYTES = 2 * 1024 * 1024
_READ_CHUNK_BYTES = 16 * 1024
_MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
_MAX_ARTIFACT_BATCH_BYTES = 64 * 1024 * 1024


class _BoundedStream:
    def __init__(self) -> None:
        self.retained = bytearray()
        self.total_bytes = 0
        self.digest = hashlib.sha256()
        self.overflow = False

    def append(self, chunk: bytes) -> None:
        self.total_bytes += len(chunk)
        self.digest.update(chunk)
        remaining = _MAX_RETAINED_STREAM_BYTES - len(self.retained)
        if remaining > 0:
            self.retained.extend(chunk[:remaining])
        if self.total_bytes > _MAX_OBSERVED_STREAM_BYTES:
            self.overflow = True

    def document(self) -> dict[str, Any]:
        return {
            "text": bytes(self.retained).decode("utf-8", errors="replace"),
            "bytes": self.total_bytes,
            "sha256": self.digest.hexdigest(),
            "truncated": self.total_bytes > len(self.retained),
        }


class HostStagedSandboxBackend:
    """Run structured argv in a disposable host-side workspace copy.

    The class deliberately does not implement a network or filesystem
    boundary.  Callers must opt into it by selecting ``host-staged`` and must
    keep it out of YOLO mode.  The process worker supplies Windows Job Object
    limits and kills the child tree when the worker is cancelled.
    """

    backend_id = "host-staged"
    requires_explicit_approval = True

    def __init__(
        self,
        workspace: WorkspacePaths | StrPath,
        config: LocalSandboxConfig | None = None,
    ) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        self.config = config or LocalSandboxConfig()
        self._staging_recovery_lock = asyncio.Lock()
        self._staging_recovery_complete = False

    async def _recover_stale_staging_workspaces(self) -> None:
        """Reclaim abandoned staging trees once per backend instance.

        A cancelled or crashed host-staged run can leave a ``.creating-*`` or
        ``agent-stage-*`` directory behind.  Recovery is deliberately bounded
        and serialized so concurrent executions cannot race while quarantining
        those directories.
        """

        if self._staging_recovery_complete:
            return
        async with self._staging_recovery_lock:
            if self._staging_recovery_complete:
                return
            for _ in range(8):
                raw = await run_in_process(recover_stale_staging_workspaces_sync)
                document = json.loads(raw)
                if not isinstance(document, dict):
                    raise ToolError("staging recovery returned an invalid result")
                remaining = document.get("remaining", 0)
                if not isinstance(remaining, int) or isinstance(remaining, bool) or remaining < 0:
                    raise ToolError("staging recovery returned an invalid remaining count")
                if remaining == 0:
                    self._staging_recovery_complete = True
                    return
            raise ToolError("too many stale staging workspaces to recover in one execution")

    async def status(self) -> SandboxStatus:
        return self.status_sync_for_test()

    def status_sync_for_test(self) -> SandboxStatus:
        native_isolation = inspect_native_isolation()
        try:
            executable = Path(sys.executable).resolve(strict=True)
            executable_sha256 = _required_executable_sha256(executable)
        except (OSError, ToolError) as exc:
            capability = sandbox_status(
                native_report=native_isolation,
                available=False,
            )
            return SandboxStatus(
                backend=self.backend_id,
                available=False,
                reason=f"host process runtime is unavailable: {exc}",
                image=None,
                executable=None,
                executable_sha256=None,
                network="host",
                workspace_mount="staged-copy",
                isolation=(),
                fallback="approval_gated_run_process",
                actions=(
                    {
                        "id": "use_run_process",
                        "label": "Use the normal approved host process tool",
                        "command": "run_process",
                    },
                ),
                diagnostic_layer="executable",
                diagnostic_code="executable_unavailable",
                capability=capability.capability,
                risk_boundary=capability.risk_boundary,
                remediation=capability.remediation,
                native_isolation=native_isolation,
                code=capability.code,
                can_execute=capability.can_execute,
                verification_evidence=capability.verification_evidence,
                repair_action=capability.repair_action,
            )
        capability = sandbox_status(native_report=native_isolation)
        return SandboxStatus(
            backend=self.backend_id,
            available=True,
            reason=(
                "host staged execution is available; network and host filesystem access "
                "are not isolated and explicit approval is required"
            ),
            image=None,
            executable=str(executable),
            executable_sha256=executable_sha256,
            network="host",
            workspace_mount="staged-copy",
            isolation=(
                "workspace_staged_copy",
                "job_object_limits",
                "bounded_output",
                "network_not_isolated",
                "host_filesystem_visible",
                "explicit_approval_required",
            ),
            fallback="none",
            actions=(),
            diagnostic_layer="ready",
            diagnostic_code="ready",
            capability=capability.capability,
            risk_boundary=capability.risk_boundary,
            remediation=capability.remediation,
            native_isolation=native_isolation,
            code=capability.code,
            can_execute=capability.can_execute,
            verification_evidence=capability.verification_evidence,
            repair_action=capability.repair_action,
        )

    async def execute(self, request: SandboxRequest) -> str | SandboxExecutionResult:
        if WorkspacePaths(request.workspace).root != self.paths.root:
            raise ToolError("host staged request workspace does not match its backend workspace")
        if not request.argv:
            raise ToolArgumentError("host staged command argv may not be empty")
        if len(request.argv) > _MAX_ARGUMENTS or any(
            not isinstance(item, str)
            or not item
            or "\x00" in item
            or len(item) > _MAX_ARGUMENT_CHARS
            for item in request.argv
        ):
            raise ToolArgumentError("host staged command arguments are invalid")
        if sum(len(item.encode("utf-8")) for item in request.argv) > _MAX_ARGUMENT_BYTES:
            raise ToolArgumentError("host staged command arguments exceed their byte limit")

        await self._recover_stale_staging_workspaces()

        execution_id = request.execution_id or uuid4().hex
        staging_root = staging_root_for_execution(execution_id, uuid4().hex, os.getpid())
        creating_root = staging_creating_root_for_execution(staging_root, uuid4().hex, os.getpid())
        try:
            raw_staging = await run_in_process(
                create_staging_workspace_sync,
                str(self.paths.root),
                str(staging_root),
                execution_id,
                os.getpid(),
                None,
                self.config.max_workspace_growth_bytes,
                self.config.minimum_free_space_bytes,
                str(creating_root),
                allow_children=True,
            )
            staging = StagingWorkspace.from_document(json.loads(raw_staging))
            raw_result = await run_in_process(
                _run_host_command_sync,
                staging.workspace,
                str(self.paths.root),
                list(request.argv),
                request.cwd,
                request.timeout_seconds,
                allow_children=True,
            )
            result_document = json.loads(raw_result)
            if not isinstance(result_document, dict):
                raise ToolError("host staged worker returned an invalid result")
            raw_changes = await run_in_process(
                diff_staging_workspace_sync,
                str(self.paths.root),
                str(staging_root),
                execution_id,
            )
            changes = json.loads(raw_changes)
            if not isinstance(changes, dict):
                raise ToolError("host staged change manifest is invalid")
            result_document.update(
                {
                    "backend": self.backend_id,
                    "network": "host",
                    "workspace_mode": "read-only" if request.read_only_workspace else "staged",
                    "changes": changes,
                }
            )
            expected_files: list[tuple[str, int, str]] = []
            for change in changes.get("changes", []):
                if not isinstance(change, dict) or change.get("after_type") != "file":
                    continue
                path = change.get("path")
                byte_count = change.get("after_bytes")
                digest = change.get("after_sha256")
                if (
                    isinstance(path, str)
                    and type(byte_count) is int
                    and 0 <= byte_count <= _MAX_ARTIFACT_BYTES
                    and isinstance(digest, str)
                    and len(digest) == 64
                ):
                    expected_files.append((path, byte_count, digest))
            # There is no artifact payload to capture when the diff is empty.
            # Avoid starting another isolated worker in this common path; the
            # worker startup cost is significant on Windows and can otherwise
            # make a no-op command exceed the bounded execution deadline.
            captured = (
                ()
                if not expected_files
                else await run_in_process(
                    capture_staging_artifacts_sync,
                    str(staging_root),
                    execution_id,
                    tuple(expected_files),
                )
            )
            if not isinstance(captured, tuple) or any(
                not isinstance(item, BinaryArtifact) for item in captured
            ):
                raise ToolError("host staged artifact worker returned an invalid result")
            return SandboxExecutionResult(result_document, captured)
        finally:
            # Cleanup must finish even when the caller cancels the run.  Keep
            # the worker task alive under ``asyncio.shield`` and re-propagate
            # cancellation after the staging and creating roots are removed.
            await _shielded_host_worker_cleanup(
                remove_staging_workspace_sync,
                str(staging_root),
                execution_id,
                str(creating_root),
                allow_children=True,
            )


async def _shielded_host_worker_cleanup(
    function: Any,
    *arguments: Any,
    allow_children: bool = False,
) -> None:
    """Run host staging cleanup to completion before honoring cancellation."""

    cancelled = False
    cleanup = asyncio.create_task(
        run_in_process(function, *arguments, allow_children=allow_children)
    )
    while not cleanup.done():
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            cancelled = True
            continue
    cleanup.result()
    if cancelled:
        raise asyncio.CancelledError


def _run_host_command_sync(
    staged_workspace: str,
    source_workspace: str,
    argv: list[str],
    raw_cwd: str,
    timeout_seconds: int,
) -> str:
    source = WorkspacePaths(source_workspace)
    source.resolve(raw_cwd)  # validates the caller's relative path
    staged_root = Path(staged_workspace).resolve(strict=True)
    staged_cwd = (staged_root / Path(raw_cwd)).resolve()
    try:
        staged_cwd.relative_to(staged_root)
    except ValueError as exc:
        raise ToolError("host staged cwd escapes the staged workspace") from exc
    if not staged_cwd.is_dir():
        raise ToolError(f"host staged working directory is not a directory: {raw_cwd}")
    executable = _resolve_host_executable(argv[0], Path(source.root))
    arguments = [str(executable), *argv[1:]]
    environment = _host_environment(Path(source.root))
    creation_flags = (
        subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    )
    started = time.monotonic()
    command_job: _WindowsJob | None = None
    try:
        if os.name == "nt":
            command_job = _WindowsJob(allow_children=True)
        process = subprocess.Popen(
            arguments,
            cwd=staged_cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            creationflags=creation_flags,
            start_new_session=os.name != "nt",
        )
    except OSError as exc:
        if command_job is not None:
            command_job.close()
        raise ToolError(f"cannot start host staged executable: {executable}") from exc
    try:
        if command_job is not None:
            try:
                command_job.assign(process.pid)
            except ToolError:
                with contextlib.suppress(OSError):
                    process.kill()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=2)
                raise
        assert process.stdout is not None and process.stderr is not None
        stdout = _BoundedStream()
        stderr = _BoundedStream()
        readers = (
            threading.Thread(target=_drain_stream, args=(process.stdout, stdout), daemon=True),
            threading.Thread(target=_drain_stream, args=(process.stderr, stderr), daemon=True),
        )
        for reader in readers:
            reader.start()
        timed_out = False
        output_limit_exceeded = False
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_host_process_tree(process, command_job)
        if process.returncode is not None and any(reader.is_alive() for reader in readers):
            _terminate_host_process_tree(process, command_job)
        while not all(not reader.is_alive() for reader in readers):
            if stdout.overflow or stderr.overflow:
                output_limit_exceeded = True
                _terminate_host_process_tree(process, command_job)
                break
            for reader in readers:
                reader.join(timeout=0.05)
        for reader in readers:
            reader.join(timeout=0.2)
        process.stdout.close()
        process.stderr.close()
        return json_result(
            {
                "backend": "host-staged",
                "argv": argv,
                "cwd": raw_cwd,
                "exit_code": process.returncode,
                "timed_out": timed_out,
                "output_limit_exceeded": output_limit_exceeded,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "stdout": stdout.document(),
                "stderr": stderr.document(),
            }
        )

    finally:
        if command_job is not None:
            command_job.close()


def _terminate_host_process_tree(
    process: subprocess.Popen[bytes],
    command_job: _WindowsJob | None = None,
) -> None:
    """Terminate a host command and descendants before closing its pipes.

    A descendant can inherit stdout/stderr and keep the reader threads alive
    after the command itself exits.  Killing only the direct process therefore
    makes a timed out or output-limited sandbox invocation hang indefinitely.
    POSIX commands are started in a new process group; Windows uses the native
    ``taskkill /T`` tree operation.
    """

    pid = process.pid
    if pid is None:
        return
    if os.name == "nt" and command_job is not None:
        command_job.terminate()
    elif os.name == "nt":
        system_root = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR")
        taskkill = (
            str(Path(system_root) / "System32" / "taskkill.exe") if system_root else "taskkill"
        )
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            subprocess.run(
                [taskkill, "/PID", str(pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                shell=False,
                creationflags=creation_flags,
                timeout=2,
            )
    else:
        platform_os = cast(Any, os)
        platform_signal = cast(Any, signal)
        with contextlib.suppress(OSError):
            platform_os.killpg(pid, platform_signal.SIGKILL)
    with contextlib.suppress(OSError, ProcessLookupError):
        process.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=2)


def _drain_stream(stream: Any, output: _BoundedStream) -> None:
    try:
        while chunk := stream.read(_READ_CHUNK_BYTES):
            output.append(chunk)
    except (OSError, ValueError):
        return


def _resolve_host_executable(value: str, workspace: Path) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ToolArgumentError("host staged executable is invalid")
    if value.casefold() in {"python", "python.exe"}:
        candidate = Path(sys.executable)
    elif Path(value).is_absolute():
        candidate = Path(value)
    else:
        candidate_text = shutil.which(value, path=_host_path(workspace))
        if not candidate_text:
            raise ToolError(f"host staged executable was not found on the trusted PATH: {value}")
        candidate = Path(candidate_text)
    resolved = _resolve_executable(str(candidate))
    try:
        resolved.relative_to(workspace.resolve(strict=True))
    except ValueError:
        return resolved
    raise ToolError("host staged executable may not come from the workspace")


def _host_path(workspace: Path) -> str:
    entries: list[str] = []
    for raw in (os.environ.get("PATH") or "").split(os.pathsep):
        if not raw or raw in {".", ".."}:
            continue
        try:
            path = Path(raw).expanduser().resolve(strict=True)
        except OSError:
            continue
        if not path.is_dir():
            continue
        try:
            path.relative_to(workspace.resolve(strict=True))
        except ValueError:
            entries.append(str(path))
    return os.pathsep.join(dict.fromkeys(entries))


def _host_environment(workspace: Path) -> dict[str, str]:
    environment = _safe_environment()
    path = _host_path(workspace)
    if path:
        environment["PATH"] = path
    environment["PYTHONUNBUFFERED"] = "1"
    return environment


__all__ = ["HostStagedSandboxBackend"]
