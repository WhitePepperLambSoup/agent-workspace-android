"""Android-only transport for verified PRoot tooling and desktop tool contracts."""

from __future__ import annotations

import asyncio
import contextlib
import os
import tempfile
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

from agent_workspace.tools.background_jobs import StartBackgroundJobTool
from agent_workspace.tools.base import ToolArgumentError, ToolError
from agent_workspace.tools.lsp import LspDiagnosticsTool

_ORIGINALS: dict[str, Any] = {}
_WORKER_CANCEL = threading.local()
_ANDROID_DIAGNOSTIC_WAIT_SECONDS = 20.0


class AndroidLspDiagnosticsTool(LspDiagnosticsTool):
    """Allow a bounded mobile CPU window for the first LSP diagnostic notification."""

    hard_cancellable = False

    async def _wait_for_diagnostics(self, client: Any, uri: str) -> bool:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _ANDROID_DIAGNOSTIC_WAIT_SECONDS
        while uri not in client.diagnostics:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return True
            await asyncio.sleep(min(0.05, remaining))
        return False


def installed_toolchain(workspace: str | os.PathLike[str] | None = None) -> Any:
    if os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") != "chaquopy":
        return None
    from mobile_toolchain import get_toolchain_manager

    manager = get_toolchain_manager(workspace=workspace)
    return manager if manager is not None and manager.snapshot()["available"] else None


def command_transport(argv: list[str], cwd: Path) -> tuple[list[str], dict[str, str] | None, Any]:
    manager = installed_toolchain()
    if manager is None or not manager.owns_command(argv[0]):
        return argv, None, None
    manager.begin_process()
    try:
        transported, environment = manager.wrap(argv, cwd)
    except Exception:
        manager.end_process()
        raise
    return transported, environment, manager


async def _git_worker(function: Any, *arguments: Any, allow_children: bool = False) -> Any:
    cancelled = threading.Event()

    def run() -> Any:
        _WORKER_CANCEL.event = cancelled
        try:
            return function(*arguments)
        finally:
            del _WORKER_CANCEL.event

    worker = asyncio.create_task(asyncio.to_thread(run))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        cancelled.set()
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
        with contextlib.suppress(Exception):
            worker.result()
        raise


def _git_executable(workspace: Path) -> Path:
    manager = installed_toolchain(workspace)
    if manager is None:
        return _ORIGINALS["git_executable"](workspace)
    entry = manager.executables().get("git")
    if entry is None:
        raise ToolError("The installed Android Git executable is unavailable")
    return Path(entry["path"])


def _invoke_git(
    workspace: str,
    repository: str,
    arguments: list[str],
    executable: str,
    expected_executable_sha256: str,
    *,
    timeout_seconds: int = 60,
    index_file: Path | None = None,
) -> dict[str, Any]:
    manager = installed_toolchain(workspace)
    if manager is None:
        return _ORIGINALS["invoke_git"](
            workspace,
            repository,
            arguments,
            executable,
            expected_executable_sha256,
            timeout_seconds=timeout_seconds,
            index_file=index_file,
        )
    from agent_workspace.tools.command import _required_executable_sha256
    from agent_workspace.tools.paths import WorkspacePaths

    from .terminal import _run_sync

    known = manager.executables().get("git")
    if (
        known is None
        or str(Path(executable)) != known["path"]
        or expected_executable_sha256 != known["sha256"]
    ):
        raise ToolError("Use the verified Android Git executable and SHA-256")
    if _required_executable_sha256(Path(executable)) != expected_executable_sha256:
        raise ToolError("The verified Git executable changed")
    cwd = WorkspacePaths(workspace).resolve(repository)
    manager.begin_process()
    try:
        argv, environment = manager.wrap([executable, *arguments], cwd)
        with contextlib.ExitStack() as temporary_files:
            if index_file is not None:
                index = index_file.resolve()
                if index.is_relative_to(Path(workspace).resolve()):
                    environment["GIT_INDEX_FILE"] = str(index)
                else:
                    require_snapshot = (
                        index.name == "index"
                        and index.parent.name.startswith("agent-workspace-git-index-")
                        and index.parent.parent == Path(tempfile.gettempdir()).resolve()
                        and index_file.absolute() == index
                        and index.is_file()
                        and index.stat().st_size <= 64 * 1024 * 1024
                    )
                    if not require_snapshot:
                        raise ToolError("The temporary Git index is not a private runtime snapshot")
                    snapshot_dir = Path(
                        temporary_files.enter_context(
                            tempfile.TemporaryDirectory(
                                prefix="git-index-", dir=manager.root / "temporary"
                            )
                        )
                    )
                    (snapshot_dir / "index").write_bytes(index.read_bytes())
                    guest_dir = "/tmp/" + snapshot_dir.name
                    position = argv.index("-w") + 2
                    argv[position:position] = ["-b", f"{snapshot_dir}:{guest_dir}"]
                    environment["GIT_INDEX_FILE"] = guest_dir + "/index"
            result = _run_sync(
                argv,
                str(cwd),
                timeout_seconds,
                "",
                getattr(_WORKER_CANCEL, "event", threading.Event()),
                environment,
                separate_stderr=True,
            )
        return {
            "exit_code": result["returncode"],
            "timed_out": result["timed_out"],
            "stdout": {
                "text": result["stdout"],
                "truncated": result["stdout_truncated"],
                "bytes": result["stdout_bytes"],
                "sha256": result["stdout_sha256"],
            },
            "stderr": {
                "text": result["stderr"],
                "truncated": result["stderr_truncated"],
                "bytes": result["stderr_bytes"],
                "sha256": result["stderr_sha256"],
            },
        }
    finally:
        manager.end_process()


class AndroidStartBackgroundJobTool(StartBackgroundJobTool):
    hard_cancellable = False

    def __init__(self, manager: Any) -> None:
        super().__init__(manager)
        from .terminal import AndroidRunProcessTool

        process = AndroidRunProcessTool(manager.paths)
        manager._process = process
        schema = dict(process.spec.input_schema)
        properties = dict(schema["properties"])
        properties.pop("timeout_seconds", None)
        properties.update(
            {
                key: self._spec.input_schema["properties"][key]
                for key in ("label", "max_seconds", "max_output_bytes")
            }
        )
        schema["properties"] = properties
        self._spec = replace(self._spec, input_schema=schema)

    def prepare_for_approval(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if "timeout_seconds" in arguments:
            raise ToolArgumentError("Use max_seconds for a background process")
        process_arguments = {
            key: value
            for key, value in arguments.items()
            if key not in {"label", "max_seconds", "max_output_bytes"}
        }
        prepared = self.manager._process.prepare_for_approval(process_arguments)
        for key in ("label", "max_seconds", "max_output_bytes"):
            if key in arguments:
                prepared[key] = arguments[key]
        return prepared


def install_toolchain_adapters() -> None:
    if os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") != "chaquopy" or _ORIGINALS:
        return
    from agent_workspace.tools import git, lsp

    _ORIGINALS.update(
        git_executable=git._git_executable,
        invoke_git=git._invoke_git,
        git_worker=git.run_in_process,
        lsp_client=lsp.StdioLspClient,
        lsp_environment=lsp._lsp_environment,
    )
    git._git_executable = _git_executable
    git._invoke_git = _invoke_git
    git.run_in_process = _git_worker

    class AndroidLspClient(_ORIGINALS["lsp_client"]):
        def __init__(self, command: Any, **kwargs: Any) -> None:
            manager = installed_toolchain()
            self._toolchain_lease = None
            if manager is not None:
                command = list(command)
                if command and command[0] in {"pyright", "pyright-langserver"}:
                    command = [
                        str(manager.rootfs / "usr/bin/node"),
                        "/opt/pyright/langserver.index.js",
                        *command[1:],
                    ]
                if command and manager.owns_command(command[0]):
                    manager.begin_process()
                    try:
                        command, _environment = manager.wrap(command, manager.workspace)
                    except Exception:
                        manager.end_process()
                        raise
                    self._toolchain_lease = manager
            super().__init__(command, **kwargs)

        async def shutdown_exit(self) -> None:
            try:
                await super().shutdown_exit()
            finally:
                if self._toolchain_lease is not None:
                    self._toolchain_lease.end_process()
                    self._toolchain_lease = None

    def environment() -> dict[str, str]:
        result = _ORIGINALS["lsp_environment"]()
        manager = installed_toolchain()
        if manager is not None:
            _command, controlled = manager.wrap(
                [str(manager.rootfs / "usr/bin/node")], manager.workspace
            )
            result.update(controlled)
        return result

    lsp.StdioLspClient = AndroidLspClient
    lsp._lsp_environment = environment


__all__ = [
    "AndroidLspDiagnosticsTool",
    "AndroidStartBackgroundJobTool",
    "command_transport",
    "install_toolchain_adapters",
    "installed_toolchain",
]
