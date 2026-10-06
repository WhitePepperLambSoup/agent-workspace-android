"""Lifecycle entrypoint called by the Android foreground service."""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import json
import os
import sys
import threading
from pathlib import Path

_state_lock = threading.Lock()
_running = False
_stop_requested = False
_loop: asyncio.AbstractEventLoop | None = None
_server_task: asyncio.Task[None] | None = None


def configure_environment(files_dir: str, provider_json: str) -> tuple[Path, Path]:
    provider = json.loads(provider_json or "{}")
    if not isinstance(provider, dict):
        raise ValueError("provider configuration must be a JSON object")

    def setting(*names: str, default: str = "") -> str:
        for name in names:
            value = provider.get(name)
            if value is None or value == "":
                continue
            if not isinstance(value, str):
                raise ValueError(f"provider {name} must be a string")
            return value
        return default

    context_tokens = provider.get("local_context_tokens", 0)
    if type(context_tokens) is not int or (
        context_tokens != 0 and not 512 <= context_tokens <= 262144
    ):
        raise ValueError("invalid local_context_tokens")
    memory_mode = provider.get("local_memory_mode", "balanced")
    if not isinstance(memory_mode, str) or memory_mode not in {"balanced", "extended"}:
        raise ValueError("invalid local_memory_mode")
    local_threads = provider.get("local_threads", 0)
    if type(local_threads) is not int or not 0 <= local_threads <= 64:
        raise ValueError("invalid local_threads")
    local_timeout_seconds = provider.get("local_timeout_seconds", 0)
    if type(local_timeout_seconds) is not int or not 0 <= local_timeout_seconds <= 7200:
        raise ValueError("invalid local_timeout_seconds")
    base_url = setting("base_url", "baseUrl", default="https://api.openai.com/v1")
    context_summary_enabled = provider.get(
        "context_summary_enabled",
        base_url.rstrip("/") != "http://127.0.0.1:8080/embedded-qwen/v1",
    )
    if type(context_summary_enabled) is not bool:
        raise ValueError("invalid context_summary_enabled")
    model = setting("model", default="gpt-4o-mini")
    if (
        base_url.rstrip("/") == "http://127.0.0.1:8080/embedded-qwen/v1"
        and model.startswith("qwen3-")
        and context_tokens > 32768
    ):
        raise ValueError(
            "Qwen3 本地上下文最多 32768 token。请先选择自动或不超过 32K。"
            "Qwen3.5 可选择到 262144 token。"
        )

    root = Path(files_dir).resolve()
    home, data, workspace, temporary = (
        root / "home",
        root / "agent-data",
        root / "workspace",
        root / "tmp",
    )
    for directory in (home, data, workspace, temporary):
        directory.mkdir(parents=True, exist_ok=True)

    database = data / "agent.db"
    os.environ.pop("PYTHONHOME", None)
    os.environ.pop("AGENT_WORKSPACE_API_KEY", None)
    os.environ.pop("AGENT_WORKSPACE_REASONING_EFFORT", None)
    autonomy = setting("autonomy", default="workspace")
    if autonomy not in {"workspace", "yolo", "full_access"}:
        raise ValueError("invalid execution mode")
    effort = setting("reasoning_effort", default="auto")
    if effort not in {"auto", "none", "low", "medium", "high", "xhigh", "max"}:
        raise ValueError("invalid reasoning effort")
    os.environ.update(
        HOME=str(home),
        TMPDIR=str(temporary),
        PYTHONUNBUFFERED="1",
        AGENT_WORKSPACE_EMBEDDED_PYTHON="chaquopy",
        AGENT_WORKSPACE_DATA_DIR=str(data),
        AGENT_WORKSPACE_ANDROID_WORKSPACE=str(workspace),
        AGENT_WORKSPACE_ANDROID_DATABASE=str(database),
        AGENT_WORKSPACE_SERVE_TOKEN_FILE=str(root / "serve.token"),
        AGENT_WORKSPACE_PROVIDER=setting(
            "id", "provider_id", "providerId", default="openai-compatible"
        ),
        AGENT_WORKSPACE_PROTOCOL=setting("protocol", default="openai-compatible"),
        AGENT_WORKSPACE_BASE_URL=base_url,
        AGENT_WORKSPACE_MODEL=model,
        AGENT_WORKSPACE_AUTONOMY=autonomy,
        AGENT_WORKSPACE_LOCAL_CONTEXT_TOKENS=str(context_tokens),
        AGENT_WORKSPACE_LOCAL_MEMORY_MODE=memory_mode,
        AGENT_WORKSPACE_LOCAL_THREADS=str(local_threads),
        AGENT_WORKSPACE_LOCAL_TIMEOUT_SECONDS=str(local_timeout_seconds),
        AGENT_WORKSPACE_CONTEXT_SUMMARY_ENABLED="1" if context_summary_enabled else "0",
    )
    api_key = setting("api_key", "apiKey")
    if effort != "auto":
        os.environ["AGENT_WORKSPACE_REASONING_EFFORT"] = effort
    if api_key:
        os.environ["AGENT_WORKSPACE_API_KEY"] = api_key
    return workspace, database


def _arm_stall_dump(files_dir: str):
    """If the final loop cleanup hangs, record every thread's stack before Android replaces the process."""
    import faulthandler

    try:
        log = Path(files_dir) / "agent-data" / "logs" / "engine-stalls.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        handle = log.open("a", encoding="utf-8")
        handle.write("--- engine loop cleanup started\n")
        handle.flush()
        faulthandler.dump_traceback_later(6.0, repeat=False, file=handle)
        return handle
    except OSError:
        return None


def _disarm_stall_dump(handle) -> None:
    import faulthandler

    if handle is None:
        return
    faulthandler.cancel_dump_traceback_later()
    with contextlib.suppress(OSError):
        handle.close()


_STARTUP_LOG_BYTES = 128 * 1024
_startup_dump = None


def _startup_log(files_dir: str, message: str) -> None:
    """One line per start-up step in agent-data/logs/engine-startup.log, so a hang shows where."""
    import time

    with contextlib.suppress(OSError):
        log = Path(files_dir) / "agent-data" / "logs" / "engine-startup.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        if log.exists() and log.stat().st_size > _STARTUP_LOG_BYTES:
            log.replace(log.with_suffix(".log.1"))
        with log.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{os.getpid()}] {message}\n")


def _arm_startup_dump(files_dir: str) -> None:
    """If start-up has not reached a listening server in 45 s, record every thread's stack once.

    The engine's own watchdog re-arms the same timer once the server runs, which cancels this one.
    """
    import faulthandler

    global _startup_dump
    with contextlib.suppress(OSError):
        log = Path(files_dir) / "agent-data" / "logs" / "engine-stalls.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        _startup_dump = log.open("a", encoding="utf-8")
        _startup_dump.write(f"--- [{os.getpid()}] engine start-up began\n")
        _startup_dump.flush()
        faulthandler.dump_traceback_later(45.0, repeat=False, file=_startup_dump)


def run(files_dir: str, provider_json: str = "{}") -> None:
    """Run until stopped; the caller must use a background Java thread."""
    global _running, _stop_requested, _loop, _server_task, _startup_dump
    with _state_lock:
        if _running:
            raise RuntimeError("the embedded Python service is already running")
        _running = True
        _stop_requested = False

    loop: asyncio.AbstractEventLoop | None = None
    _startup_log(files_dir, "engine starting")
    _arm_startup_dump(files_dir)
    try:
        workspace, database = configure_environment(files_dir, provider_json)
        _startup_log(files_dir, "environment configured")
        root = Path(files_dir).resolve() / "agent"
        for path in (root / "src", root / "for Android"):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        (Path(files_dir) / "serve.token").unlink(missing_ok=True)
        entrypoint = importlib.import_module("entrypoint")
        _startup_log(files_dir, "engine modules loaded")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        task = loop.create_task(
            entrypoint._run_mobile_web_server(
                "127.0.0.1", 8080, workspace=workspace, database=database
            )
        )
        with _state_lock:
            _loop, _server_task = loop, task
            requested = _stop_requested
        if requested:
            loop.call_soon(task.cancel)
        with contextlib.suppress(asyncio.CancelledError):
            loop.run_until_complete(task)
        _startup_log(files_dir, "engine stopped")
    except BaseException as exc:
        _startup_log(files_dir, f"engine failed: {type(exc).__name__}: {str(exc)[:500]}")
        raise
    finally:
        stall_log = _arm_stall_dump(files_dir)
        try:
            if loop is not None:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.run_until_complete(loop.shutdown_default_executor(timeout=5.0))
                asyncio.set_event_loop(None)
                loop.close()
        finally:
            _disarm_stall_dump(stall_log)
            if _startup_dump is not None:
                with contextlib.suppress(OSError):
                    _startup_dump.close()
                _startup_dump = None
        with _state_lock:
            _loop = _server_task = None
            _running = False


def stop() -> None:
    """Cancel the server task so its existing finally block closes the runtime."""
    global _stop_requested
    with _state_lock:
        if not _running or _stop_requested:
            return
        _stop_requested = True
        loop, task = _loop, _server_task
    if loop is not None and task is not None:
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(task.cancel)
