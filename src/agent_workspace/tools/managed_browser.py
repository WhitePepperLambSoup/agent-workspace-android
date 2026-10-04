"""A lazily launched, owned Chromium process with a private profile and CDP port."""
# ruff: noqa: RUF001
# User-facing Chinese diagnostics intentionally retain native punctuation.

from __future__ import annotations

import asyncio
import atexit
import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from websockets.asyncio.client import connect as ws_connect

from .base import ToolError

_EXECUTABLE_ENV = "AGENT_WORKSPACE_BROWSER_EXECUTABLE"


class ManagedBrowserError(ToolError):
    """The owned browser could not be started or closed."""


def _browser_executable() -> str:
    configured = os.environ.get(_EXECUTABLE_ENV)
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path.resolve())
        raise ManagedBrowserError("browser_executable_not_found: 配置的浏览器程序不存在。")
    candidates: list[Path] = []
    if sys.platform == "win32":
        for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            root = os.environ.get(variable)
            if root:
                candidates.extend(
                    (
                        Path(root) / "Google/Chrome/Application/chrome.exe",
                        Path(root) / "Microsoft/Edge/Application/msedge.exe",
                    )
                )
    elif sys.platform == "darwin":
        candidates.extend(
            (
                Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
            )
        )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    names = (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "chrome",
        "msedge",
    )
    for name in names:
        executable = shutil.which(name)
        if executable:
            return executable
    raise ManagedBrowserError(
        "browser_unavailable: 未找到 Chrome、Edge 或 Chromium 浏览器；"
        f"请安装浏览器，或使用 {_EXECUTABLE_ENV} 指定程序路径。"
    )


class ManagedBrowser:
    def __init__(
        self,
        *,
        profile_parent: Path | None = None,
        startup_timeout: float = 20.0,
    ) -> None:
        self._profile_parent = profile_parent
        self._startup_timeout = startup_timeout
        self._profile: tempfile.TemporaryDirectory[str] | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._endpoint: str | None = None
        self._lock = asyncio.Lock()
        self._owner_lock = threading.RLock()
        self._closed = False

    async def ensure_endpoint(self) -> str:
        async with self._lock:
            with self._owner_lock:
                if self._closed:
                    raise ManagedBrowserError("browser_closed: 受控浏览器已关闭。")
                if self._process is not None and self._process.poll() is None and self._endpoint:
                    return self._endpoint
            await self._cleanup_owned()
            executable = _browser_executable()
            try:
                with self._owner_lock:
                    if self._closed:
                        raise ManagedBrowserError("browser_closed: 受控浏览器已关闭。")
                    self._profile = tempfile.TemporaryDirectory(
                        prefix="agent-workspace-browser-",
                        dir=self._profile_parent,
                    )
                    profile = Path(self._profile.name)
                    command = [
                        executable,
                        f"--user-data-dir={profile}",
                        "--remote-debugging-address=127.0.0.1",
                        "--remote-debugging-port=0",
                        "--headless=new",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-background-networking",
                        "about:blank",
                    ]
                    process = subprocess.Popen(
                        command,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        shell=False,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                        start_new_session=sys.platform != "win32",
                    )
                    self._process = process
                    atexit.register(self.close_sync)
                deadline = asyncio.get_running_loop().time() + self._startup_timeout
                while asyncio.get_running_loop().time() < deadline:
                    if self._closed:
                        raise ManagedBrowserError("browser_closed: 受控浏览器已关闭。")
                    code = process.poll()
                    if code is not None:
                        raise ManagedBrowserError(
                            f"browser_start_failed: 浏览器启动失败（退出码 {code}）。"
                        )
                    endpoint = self._read_endpoint(profile)
                    if endpoint:
                        with self._owner_lock:
                            if self._closed or self._process is not process:
                                raise ManagedBrowserError("browser_closed: 受控浏览器已关闭。")
                            self._endpoint = endpoint
                        return endpoint
                    await asyncio.sleep(0.05)
                raise ManagedBrowserError(
                    "browser_start_timeout: 浏览器启动超时，请检查浏览器是否可运行。"
                )
            except BaseException as error:
                await self._cleanup_owned()
                if isinstance(error, OSError):
                    raise ManagedBrowserError(
                        f"browser_start_failed: 无法启动浏览器：{error}"
                    ) from error
                raise

    @staticmethod
    def _read_endpoint(profile: Path) -> str | None:
        try:
            lines = (profile / "DevToolsActivePort").read_text(encoding="utf-8").splitlines()
            port = int(lines[0])
            path = lines[1]
        except (OSError, ValueError, IndexError):
            return None
        if (
            0 < port <= 65535
            and path.startswith("/devtools/browser/")
            and not any(char.isspace() for char in path)
        ):
            return f"ws://127.0.0.1:{port}{path}"
        return None

    async def _request_browser_close(self) -> None:
        with self._owner_lock:
            endpoint, process = self._endpoint, self._process
        if not endpoint or process is None or process.poll() is not None:
            return
        with contextlib.suppress(Exception):
            async with ws_connect(endpoint, open_timeout=1.0, close_timeout=0.5) as websocket:
                await websocket.send(json.dumps({"id": 1, "method": "Browser.close"}))
                await asyncio.wait_for(websocket.recv(), timeout=0.5)

    async def aclose(self) -> None:
        async with self._lock:
            with self._owner_lock:
                self._closed = True
            try:
                await self._request_browser_close()
            finally:
                await self._cleanup_owned()

    async def _cleanup_owned(self) -> None:
        # Cancelling to_thread only abandons its awaiter: the cleanup thread
        # continues. Keep the async owner lock until that exact worker finishes,
        # including when shutdown or repeated stop requests cancel this await.
        completion = asyncio.get_running_loop().run_in_executor(None, self._cleanup_owned_sync)
        cancelled: asyncio.CancelledError | None = None
        while True:
            try:
                await asyncio.shield(completion)
                break
            except asyncio.CancelledError as error:
                if cancelled is None:
                    cancelled = error
                if completion.done():
                    break
        completion.result()
        if cancelled is not None:
            raise cancelled

    def close_sync(self) -> None:
        with self._owner_lock:
            self._closed = True
            self._cleanup_owned_sync()

    def _cleanup_owned_sync(self) -> None:
        with self._owner_lock:
            self._cleanup_snapshot_sync()

    def _cleanup_snapshot_sync(self) -> None:
        process = self._process
        profile = self._profile
        if process is not None and process.poll() is None:
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                # Only the process this owner launched is eligible for termination.
                # Never search or terminate browsers by executable name or CDP port.
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=2.0,
                        check=False,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                else:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
                try:
                    process.wait(timeout=1.0)
                except subprocess.TimeoutExpired as error:
                    raise ManagedBrowserError(
                        "browser_close_failed: 受控浏览器未能退出。"
                    ) from error
        if self._process is process:
            self._process = None
            self._endpoint = None
        if profile is not None:
            for attempt in range(6):
                try:
                    profile.cleanup()
                    if self._profile is profile:
                        self._profile = None
                    break
                except OSError:
                    if attempt == 5:
                        raise
                    time.sleep(0.05)
        if self._process is None and self._profile is None:
            atexit.unregister(self.close_sync)
