"""Android-only transport for verified PRoot tooling and desktop tool contracts."""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import os
import tempfile
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from agent_workspace.coding.servers import spec_for
from agent_workspace.tools.background_jobs import StartBackgroundJobTool
from agent_workspace.tools.base import ToolArgumentError, ToolError
from agent_workspace.tools.lsp import LspDiagnosticsTool

_ORIGINALS: dict[str, Any] = {}
_WORKER_CANCEL = threading.local()
_ANDROID_DIAGNOSTIC_WAIT_SECONDS = 20.0
# The workspace of the diagnostics being run: the language server is started without being told.
_LSP_WORKSPACE: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
    "android_lsp_workspace", default=None
)


class AndroidLspDiagnosticsTool(LspDiagnosticsTool):
    """Allow a bounded mobile CPU window for the first LSP diagnostic notification."""

    hard_cancellable = False

    def _server_command(self, path: Path) -> tuple[str, ...]:
        # The toolchain's Pyright is not on PATH; the client below starts it in the toolchain.
        manager = installed_toolchain()
        spec = spec_for(path)
        if (
            manager is not None
            and spec is not None
            and spec.id == "python"
            and "pyright" in manager.executables()
        ):
            return ("pyright-langserver", "--stdio")
        return super()._server_command(path)

    async def execute(self, arguments: dict[str, Any]) -> str:
        token = _LSP_WORKSPACE.set(self.paths.root)
        try:
            return await super().execute(arguments)
        finally:
            _LSP_WORKSPACE.reset(token)

    async def _wait_for_diagnostics(self, client: Any, uri: str) -> bool:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _ANDROID_DIAGNOSTIC_WAIT_SECONDS
        while uri not in client.diagnostics:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return True
            await asyncio.sleep(min(0.05, remaining))
        return False


def installed_toolchain() -> Any:
    """The phone's one toolchain, for every workspace: wrap() is told which one a command is in."""
    if os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") != "chaquopy":
        return None
    from mobile_toolchain import ToolchainError, get_toolchain_manager

    try:
        manager = get_toolchain_manager()
        return manager if manager is not None and manager.snapshot()["available"] else None
    except ToolchainError:
        # Damaged toolchain files must not stop commands that do not need it: they run under the
        # guard, as when no toolchain is installed.
        return None


def command_transport(
    argv: list[str], cwd: Path, workspace: Path | None = None
) -> tuple[list[str], dict[str, str] | None, Any]:
    """How a command the agent asked for starts: in the toolchain's Linux, else under the guard."""
    manager = installed_toolchain()
    if manager is None or not manager.owns_command(argv[0]):
        from .command_guard import guard

        guarded = guard(argv, cwd, workspace)
        if guarded is None:
            return argv, None, None
        return guarded[0], guarded[1], None
    manager.begin_process()
    try:
        transported, environment = manager.wrap(argv, cwd, workspace)
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
    manager = installed_toolchain()
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
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    manager = installed_toolchain()
    if manager is None:
        return _ORIGINALS["invoke_git"](
            workspace,
            repository,
            arguments,
            executable,
            expected_executable_sha256,
            timeout_seconds=timeout_seconds,
            index_file=index_file,
            environment=environment,
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
        argv, wrapped = manager.wrap([executable, *arguments], cwd, workspace)
        wrapped.update(environment or {})
        with contextlib.ExitStack() as temporary_files:
            if index_file is not None:
                index = index_file.resolve()
                if index.is_relative_to(Path(workspace).resolve()):
                    wrapped["GIT_INDEX_FILE"] = str(index)
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
                    wrapped["GIT_INDEX_FILE"] = guest_dir + "/index"
            result = _run_sync(
                argv,
                str(cwd),
                timeout_seconds,
                "",
                getattr(_WORKER_CANCEL, "event", threading.Event()),
                wrapped,
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


def _guarded_command_sync(
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
    """A declared custom tool's command (tools/custom.py), started as every other command the agent
    runs: in the toolchain's Linux or under the command guard, never as the app itself."""
    original = _ORIGINALS["run_command"]
    arguments = (workspace, kind, executable, argv, command, raw_cwd, timeout_seconds)
    if kind != "direct" or executable is None:
        return original(*arguments, environment_overrides, expected_executable_sha256)
    from agent_workspace.tools.base import json_result
    from agent_workspace.tools.command import _required_executable_sha256, _resolve_executable
    from agent_workspace.tools.paths import WorkspacePaths

    from .terminal import MAX_OUTPUT_BYTES, _run_sync

    paths = WorkspacePaths(workspace)
    cwd = paths.resolve(raw_cwd)
    resolved = _resolve_executable(executable)
    digest = _required_executable_sha256(resolved)
    if expected_executable_sha256 is not None and digest != expected_executable_sha256.casefold():
        raise ToolError("executable changed after discovery or approval")
    transported, environment, lease = command_transport([str(resolved), *argv], cwd, paths.root)
    if environment is None:  # Away from the phone, or a program the guard cannot find.
        return original(*arguments, environment_overrides, expected_executable_sha256)
    started = time.monotonic()
    try:
        result = _run_sync(
            transported,
            str(cwd),
            timeout_seconds,
            "",
            getattr(_WORKER_CANCEL, "event", threading.Event()),
            {**environment, **(environment_overrides or {})},
            separate_stderr=True,
        )
    finally:
        if lease is not None:
            lease.end_process()
    return json_result(
        {
            "kind": kind,
            "executable": str(resolved),
            "executable_sha256": digest,
            "argv": argv,
            "command_sha256": None,
            "cwd": paths.relative(cwd),
            "exit_code": result["returncode"],
            "timed_out": result["timed_out"],
            "duration_ms": round((time.monotonic() - started) * 1000),
            **{
                name: {
                    "text": result[name],
                    "truncated": result[name + "_bytes"] > MAX_OUTPUT_BYTES,
                    "bytes": result[name + "_bytes"],
                    "sha256": result[name + "_sha256"],
                }
                for name in ("stdout", "stderr")
            },
        }
    )


# The workspace an MCP host is being built for (build_mcp_host blocks until its servers started).
_MCP_LOCK = threading.Lock()
_MCP_WORKSPACE: list[Path] = []


def _build_mcp_host(workspace: Any, servers: Any = None) -> Any:
    with _MCP_LOCK:
        _MCP_WORKSPACE.append(Path(workspace))
        try:
            return _ORIGINALS["build_mcp_host"](workspace, servers)
        finally:
            _MCP_WORKSPACE.clear()


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
            command = list(command)
            root = _LSP_WORKSPACE.get() or (manager.workspace if manager else Path.cwd())
            if manager is not None and command and command[0] in {"pyright", "pyright-langserver"}:
                command = [
                    str(manager.rootfs / "usr/bin/node"),
                    "/opt/pyright/langserver.index.js",
                    *command[1:],
                ]
            if manager is not None and command and manager.owns_command(command[0]):
                manager.begin_process()
                try:
                    command, _environment = manager.wrap(command, root, root)
                except Exception:
                    manager.end_process()
                    raise
                self._toolchain_lease = manager
            elif command:
                # A server outside the toolchain runs under the guard, as other commands do.
                from .command_guard import guard

                guarded = guard(command, root, root)
                if guarded is not None:
                    command = guarded[0]
                    kwargs["extra_environment"] = {
                        **guarded[1],
                        **(kwargs.get("extra_environment") or {}),
                    }
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
    install_extension_guards()


def install_extension_guards() -> None:
    """A declared custom tool and an MCP server start as every other command does: in the toolchain's
    Linux or under the command guard. Run directly they would read the app's own files (serve.token,
    the conversations) and ask Android for what the app may do."""
    if "run_command" in _ORIGINALS:
        return
    from agent_workspace.application import multi_runtime, runtime
    from agent_workspace.tools import custom, mcp_host

    _ORIGINALS.update(
        run_command=custom._run_command_sync,
        mcp_client=mcp_host.StdioMcpClient,
        build_mcp_host=mcp_host.build_mcp_host,
    )
    custom._run_command_sync = _guarded_command_sync

    class AndroidMcpClient(_ORIGINALS["mcp_client"]):
        def __init__(self, command: Any, **kwargs: Any) -> None:
            root = _MCP_WORKSPACE[0] if _MCP_WORKSPACE else Path(tempfile.gettempdir())
            self._toolchain_lease: Any = None
            self._refused: ToolError | None = None
            extra: dict[str, str] | None = None
            try:
                transported, extra, self._toolchain_lease = command_transport(list(command), root, root)
            except ToolError as refused:
                # Said when the server starts, as any server that cannot start (mcp_host).
                transported, self._refused = list(command), refused
            if extra is not None and not kwargs.get("cwd"):
                kwargs["cwd"] = str(root)
            super().__init__(transported, **kwargs)
            self._declared = tuple(command)
            if extra:
                self._environment.update(extra)

        @property
        def command(self) -> tuple[str, ...]:
            return self._declared  # As the server was declared, not as it is started.

        async def connect(self) -> None:
            if self._refused is not None:
                raise self._refused
            await super().connect()

        async def aclose(self) -> None:
            try:
                await super().aclose()
            finally:
                lease, self._toolchain_lease = self._toolchain_lease, None
                if lease is not None:
                    lease.end_process()

    mcp_host.StdioMcpClient = AndroidMcpClient
    mcp_host.build_mcp_host = _build_mcp_host
    runtime.build_mcp_host = _build_mcp_host
    multi_runtime.build_mcp_host = _build_mcp_host


__all__ = [
    "AndroidLspDiagnosticsTool",
    "AndroidStartBackgroundJobTool",
    "command_transport",
    "install_toolchain_adapters",
    "installed_toolchain",
]
