"""POSIX / Android Termux 下的伪终端 (PTY) 实现。

替换原项目中依赖 Windows 专有 ConPTY (CreatePseudoConsole) 的实现,
使用 Linux 原生 /dev/ptmx 虚拟控制台与 termios/pty 进行命令执行与进度抓取。
"""

from __future__ import annotations

import asyncio
import errno
import os
import select
import signal
import struct
import time
from contextlib import suppress
from typing import Any

try:
    import fcntl
    import pty
    import termios
except ImportError:
    fcntl = None  # type: ignore
    pty = None  # type: ignore
    termios = None  # type: ignore

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import (
    ToolArgumentError,
    ToolError,
    json_result,
    optional_int,
)
from agent_workspace.tools.paths import StrPath, WorkspacePaths

_MAX_OUTPUT_BYTES = 512 * 1024
_MAX_ARGUMENTS = 256
_MAX_ARGUMENT_CHARS = 32_767


def _posix_pty_sync(
    workspace: str,
    argv: list[str],
    raw_cwd: str,
    timeout_seconds: int,
) -> str:
    paths = WorkspacePaths(workspace)
    cwd = paths.resolve(raw_cwd)
    if not cwd.is_dir():
        raise ToolError(f"terminal working directory is not a directory: {cwd}")

    master_fd, slave_fd = pty.openpty()

    # 设置终端窗口大小 (120 列 x 40 行)
    winsize = struct.pack("HHHH", 40, 120, 0, 0)
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

    # 设置 master 为非阻塞读取
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    # 净化环境变量
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["CI"] = "1"
    env["NO_COLOR"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    pid = os.fork()
    if pid == 0:
        # 子进程: 绑定 slave PTY 作为标准输入/输出/错误
        try:
            os.close(master_fd)
            os.setsid()  # 创建独立进程组
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            os.close(slave_fd)
            os.chdir(str(cwd))
            os.execvpe(argv[0], argv, env)
        except Exception:
            os._exit(127)

    # 父进程
    os.close(slave_fd)
    output_chunks: list[bytes] = []
    total_bytes = 0
    start_time = time.monotonic()
    timed_out = False

    try:
        while True:
            elapsed = time.monotonic() - start_time
            if elapsed >= timeout_seconds:
                timed_out = True
                break

            # 轮询子进程退出状态
            wait_pid, _ = os.waitpid(pid, os.WNOHANG)
            if wait_pid != 0:
                # 进程已结束, 读完剩余缓冲区
                while True:
                    try:
                        chunk = os.read(master_fd, 4096)
                        if not chunk:
                            break
                        output_chunks.append(chunk)
                    except OSError:
                        break
                break

            # 读取 master 输出
            r, _, _ = select.select([master_fd], [], [], 0.05)
            if r:
                try:
                    chunk = os.read(master_fd, 4096)
                    if chunk:
                        output_chunks.append(chunk)
                        total_bytes += len(chunk)
                        if total_bytes > _MAX_OUTPUT_BYTES:
                            break
                except OSError as e:
                    if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                        pass
                    else:
                        break
    finally:
        if timed_out or wait_pid == 0:
            with suppress(OSError):
                # 连根杀死子进程组
                os.killpg(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
        with suppress(OSError):
            os.close(master_fd)

    raw_output = b"".join(output_chunks)
    text = raw_output.decode("utf-8", errors="replace")
    truncated = len(raw_output) > _MAX_OUTPUT_BYTES or total_bytes > _MAX_OUTPUT_BYTES
    if truncated:
        text = text[:_MAX_OUTPUT_BYTES] + "\n[output truncated]"

    return json_result(
        stdout=text,
        truncated=truncated,
        timed_out=timed_out,
        returncode=0 if not timed_out else -1,
    )


class RunTerminalTool:
    """Run an interactive command through a POSIX PTY and capture output."""

    hard_cancellable = False
    _SPEC = ToolSpec(
        name="run_terminal",
        description=(
            "Run an interactive command inside a POSIX pseudo terminal (PTY) in the "
            "workspace. Captures combined bounded output with no stdin; use it for test "
            "runners, installers, and commands that render progress output. Requires "
            "approval outside YOLO."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "argv": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 32767},
                    "maxItems": 256,
                    "minItems": 1,
                },
                "cwd": {"type": "string", "minLength": 1, "default": "."},
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
        raw_argv = arguments.get("argv")
        if (
            not isinstance(raw_argv, list)
            or not raw_argv
            or any(not isinstance(item, str) or not item or "\x00" in item for item in raw_argv)
            or len(raw_argv) > _MAX_ARGUMENTS
            or any(len(item) > _MAX_ARGUMENT_CHARS for item in raw_argv)
        ):
            raise ToolArgumentError("'argv' must be a bounded array of non-empty strings")
        raw_cwd = arguments.get("cwd", ".")
        if not isinstance(raw_cwd, str) or not raw_cwd:
            raise ToolArgumentError("'cwd' must be a non-empty string")
        timeout_seconds = optional_int(
            arguments,
            "timeout_seconds",
            60,
            minimum=1,
            maximum=300,
        )
        return await asyncio.to_thread(
            _posix_pty_sync,
            str(self.paths.root),
            list(raw_argv),
            raw_cwd,
            timeout_seconds,
        )
