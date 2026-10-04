"""Android JVM storage and thread workers for the embedded Python interpreter."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import os
import signal
import sys
import time
from collections.abc import Callable
from typing import Any

_secrets_bridge: Any = None


def _secrets() -> Any:
    global _secrets_bridge
    if _secrets_bridge is None:
        from java import jclass

        _secrets_bridge = jclass("com.agentworkspace.mobile.embedded.EmbeddedSecrets")
    return _secrets_bridge


def _secure_call(method: str, *arguments: str) -> Any:
    try:
        return getattr(_secrets(), method)(*arguments)
    except Exception as exc:
        raise OSError("Android secure storage operation failed") from exc


class AndroidCredentialStore:
    def get(self, target: str) -> str | None:
        value = _secure_call("getCredential", target)
        return None if value is None else str(value)

    def set(self, target: str, secret: str) -> None:
        _secure_call("setCredential", target, secret)

    def delete(self, target: str) -> None:
        _secure_call("deleteCredential", target)

    def list(self) -> list[str]:
        return [str(value) for value in _secure_call("listCredentials")]


_credential_store = AndroidCredentialStore()


def default_credential_store() -> AndroidCredentialStore:
    return _credential_store


def _protect(data: bytes, entropy: bytes, method: str) -> bytes:
    if not entropy:
        raise ValueError("protection entropy may not be empty")
    encoded = base64.b64encode(data).decode("ascii")
    aad = base64.b64encode(entropy).decode("ascii")
    result = _secure_call(method, encoded, aad)
    try:
        return base64.b64decode(str(result), validate=True)
    except (TypeError, ValueError) as exc:
        raise OSError("Android secure storage returned invalid protected data") from exc


def protect_current_user_data(data: bytes, *, entropy: bytes) -> bytes:
    return _protect(data, entropy, "protectBase64")


def unprotect_current_user_data(data: bytes, *, entropy: bytes) -> bytes:
    return _protect(data, entropy, "unprotectBase64")


async def run_in_process[T](
    function: Callable[..., T], *arguments: Any, allow_children: bool = False
) -> T:
    return await asyncio.to_thread(function, *arguments)


def __getattr__(name: str) -> Any:
    if name not in {"ToolWorkerError", "ToolWorkerPreconditionError"}:
        raise AttributeError(name)
    # The tools package imports its base before workers; delay this dependency
    # so installing the worker redirect cannot start a circular package import.
    from agent_workspace.tools.base import ToolError

    class ToolWorkerError(ToolError):
        pass

    class ToolWorkerPreconditionError(ToolWorkerError):
        pass

    globals().update(
        ToolWorkerError=ToolWorkerError,
        ToolWorkerPreconditionError=ToolWorkerPreconditionError,
    )
    return globals()[name]


class _WindowsJob:
    def __init__(self, *, allow_children: bool = False) -> None:
        error = sys.modules[__name__].ToolWorkerPreconditionError
        raise error("Windows Job Objects are unavailable in the Android runtime")


def run_serialized_tool_worker() -> int:
    error = sys.modules[__name__].ToolWorkerPreconditionError
    raise error("standalone Python worker processes are unavailable in the Android runtime")


def terminate_process_tree_pid(pid: int, *, timeout: float = 2.0) -> None:
    if type(pid) is not int or pid <= 0 or pid == os.getpid():
        raise ValueError("process id must identify a child process")

    def send(signum: int) -> None:
        try:
            get_group = getattr(os, "getpgid", None)
            if get_group is not None and get_group(pid) == pid:
                os.killpg(pid, signum)
            else:
                os.kill(pid, signum)
        except ProcessLookupError:
            pass

    send(signal.SIGTERM)
    deadline = time.monotonic() + max(0.0, timeout)
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
    with contextlib.suppress(ProcessLookupError):
        send(signal.SIGKILL)


def install_android_runtime() -> None:
    import agent_workspace.credentials as credentials

    from .local_provider import install_local_provider_factory

    install_local_provider_factory()

    credentials.default_credential_store = default_credential_store
    credentials.protect_current_user_data = protect_current_user_data
    credentials.unprotect_current_user_data = unprotect_current_user_data
    sys.modules["agent_workspace.tools.process_worker"] = sys.modules[__name__]

    from .toolchain import install_toolchain_adapters

    install_toolchain_adapters()

    checkpoint = sys.modules.get("agent_workspace.storage.checkpoint_crypto")
    if checkpoint is not None:
        checkpoint.protect_current_user_data = protect_current_user_data
        checkpoint.unprotect_current_user_data = unprotect_current_user_data

    from agent_workspace.tools.paths import WorkspacePaths
    from agent_workspace.tools.registry import ToolRegistry

    from .capabilities import configure_android_registry

    original_register = ToolRegistry.register
    if not getattr(original_register, "_chaquopy_threads", False):

        def register(registry: Any, tool: Any) -> None:
            if getattr(tool, "hard_cancellable", False):
                tool.hard_cancellable = False
            original_register(registry, tool)

        register._chaquopy_threads = True
        ToolRegistry.register = register

    original_for_workspace = ToolRegistry.for_workspace
    if not getattr(original_for_workspace, "_chaquopy_capabilities", False):

        def for_workspace(cls: type[Any], workspace: Any, *args: Any, **kwargs: Any) -> Any:
            registry = original_for_workspace(workspace, *args, **kwargs)
            workspace_root = workspace.root if isinstance(workspace, WorkspacePaths) else workspace
            configure_android_registry(registry, workspace_root)
            return registry

        for_workspace._chaquopy_capabilities = True
        ToolRegistry.for_workspace = classmethod(for_workspace)

    from .local_context import install_local_context_profile

    install_local_context_profile()
