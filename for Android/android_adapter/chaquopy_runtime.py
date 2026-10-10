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


def _validate_database_once_per_process() -> None:
    """Validate the engine database when the engine first opens it, not for every conversation.

    Each conversation runtime opens its own SQLiteEventStore, and the core repeats the full
    database validation (a projection replay that takes seconds on a phone) whenever a WAL file
    exists, which it always does once the engine's first store is open. The engine is the
    database's only writer while it runs (the base runtime leases the writer lock until exit), so
    after a store of this process validated a file, later opens of that same file here cannot find
    changes this process did not make. A restored database is a new file and is validated again.
    """
    from pathlib import Path

    from agent_workspace.storage.sqlite import CURRENT_SCHEMA_VERSION, SQLiteEventStore

    cached = SQLiteEventStore._open_validation_cached
    if getattr(cached, "_android_once_per_process", False):
        return
    remember = SQLiteEventStore._cache_open_validation
    check_before_migration = SQLiteEventStore._validate_before_migration
    validated: dict[Path, tuple[int, int]] = {}

    def file_identity(database: Path) -> tuple[int, int] | None:
        try:
            metadata = database.stat()
        except OSError:
            return None
        return metadata.st_dev, metadata.st_ino

    def validated_here(database: Path) -> bool:
        known = validated.get(database)
        return known is not None and known == file_identity(database)

    def validate_before_migration(database: Path) -> int | None:
        # A file validated here was migrated to the current schema before its validation.
        if validated_here(database):
            return CURRENT_SCHEMA_VERSION
        return check_before_migration(database)

    def open_validation_cached(database: Path, identity: tuple[int, int] | None) -> bool:
        return cached(database, identity) or validated_here(database)

    def cache_open_validation(database: Path, identity: tuple[int, int] | None) -> None:
        remember(database, identity)
        current = file_identity(database)
        if current is not None:
            validated[database] = current

    open_validation_cached._android_once_per_process = True
    SQLiteEventStore._validate_before_migration = staticmethod(validate_before_migration)
    SQLiteEventStore._open_validation_cached = staticmethod(open_validation_cached)
    SQLiteEventStore._cache_open_validation = staticmethod(cache_open_validation)


def _share_default_tls_context() -> None:
    """Build the default TLS context once instead of once per HTTP client.

    Every conversation runtime creates its own provider client, and loading the CA bundle into a
    fresh context takes about a quarter of a second on a phone. httpx recommends sharing one
    context between clients; only the default configuration (verify=True, no client certificate)
    is shared, and no client in this app enables HTTP/2, so the ALPN list stays the same.
    """
    import threading

    from httpx._transports import default

    create = default.create_ssl_context
    if getattr(create, "_android_shared", False):
        return
    shared: dict[bool, Any] = {}
    lock = threading.Lock()

    def create_ssl_context(verify: Any = True, cert: Any = None, trust_env: bool = True) -> Any:
        if verify is not True or cert is not None:
            return create(verify=verify, cert=cert, trust_env=trust_env)
        with lock:
            context = shared.get(bool(trust_env))
            if context is None:
                context = create(verify=True, cert=None, trust_env=trust_env)
                shared[bool(trust_env)] = context
        return context

    create_ssl_context._android_shared = True
    default.create_ssl_context = create_ssl_context


def _check_each_tool_schema_once() -> None:
    """Remember tool input schemas that passed the meta-schema check.

    Every runtime registers the same ~50 tools, and checking their schemas against the JSON Schema
    meta-schema takes most of a second on a phone each time, at every engine start and for every
    conversation. A schema that passed passes again, so passing schemas are remembered by a hash of
    their content, in memory and in <data>/cache for the next engine start; failures are always
    checked again.
    """
    import hashlib
    import json
    import threading
    from pathlib import Path

    from agent_workspace.tools import base, registry

    original = base.check_tool_schema
    if getattr(original, "_android_remembered", False):
        return
    data_dir = os.getenv("AGENT_WORKSPACE_DATA_DIR")
    cache = Path(data_dir) / "cache" / "tool-schemas-passed.json" if data_dir else None
    passed: set[str] = set()
    if cache is not None:
        with contextlib.suppress(OSError, ValueError):
            stored = json.loads(cache.read_text("utf-8"))
            if isinstance(stored, list):
                passed.update(item for item in stored[:1024] if isinstance(item, str))
    lock = threading.Lock()

    def remember(key: str) -> None:
        with lock:
            if len(passed) >= 1024:
                passed.clear()
            passed.add(key)
            if cache is None:
                return
            with contextlib.suppress(OSError):
                cache.parent.mkdir(parents=True, exist_ok=True)
                staging = cache.with_name(f".{cache.name}.tmp")
                staging.write_text(json.dumps(sorted(passed)), "utf-8")
                os.replace(staging, cache)

    def check_tool_schema(spec: Any) -> None:
        try:
            canonical = json.dumps(
                [spec.input_schema, spec.advertised_input_schema], sort_keys=True
            )
        except (TypeError, ValueError):
            original(spec)
            return
        key = hashlib.sha256(canonical.encode()).hexdigest()
        if key in passed:
            return
        original(spec)
        remember(key)

    check_tool_schema._android_remembered = True
    base.check_tool_schema = check_tool_schema
    registry.check_tool_schema = check_tool_schema


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
    _validate_database_once_per_process()
    _check_each_tool_schema_once()
    _share_default_tls_context()
