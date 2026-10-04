"""POSIX / Android 下的进程监督与生命周期管理。

在 Linux / Termux 环境下, 通过 POSIX 进程会话(start_new_session / os.setpgrp)
管理子进程树, 并使用进程组信号(SIGTERM / SIGKILL)实现可靠的连根进程清理。
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import IO, Any


def get_android_default_shell() -> str:
    """获取 Termux 或 Android 环境下的首选 Shell。"""
    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    termux_bash = os.path.join(prefix, "bin", "bash")
    if os.path.exists(termux_bash):
        return termux_bash

    which_bash = shutil.which("bash")
    if which_bash:
        return which_bash

    return "/system/bin/sh"


def launch_posix_process(
    cmd: Sequence[str],
    cwd: str | Path,
    env: dict[str, str],
    stdout: int | IO[bytes] = subprocess.PIPE,
    stderr: int | IO[bytes] = subprocess.PIPE,
    stdin: int | IO[bytes] | None = subprocess.DEVNULL,
) -> subprocess.Popen[bytes]:
    """启动受控子进程, 并将其作为独立 POSIX 进程组的领头进程。"""
    return subprocess.Popen(
        list(cmd),
        cwd=str(cwd),
        env=env,
        stdout=stdout,
        stderr=stderr,
        stdin=stdin,
        start_new_session=True,  # 子进程调用 setsid() / setpgrp()
    )


def terminate_posix_process_tree(
    proc: subprocess.Popen[Any],
    grace_seconds: float = 1.5,
) -> None:
    """连根杀死进程组内的所有派生子进程。"""
    if proc.poll() is not None:
        return

    pid = proc.pid
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return

    try:
        # 1. 发送 SIGTERM 优雅退出
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return

    try:
        proc.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        # 2. 超时未退出的强制 SIGKILL
        try:
            os.killpg(pgid, signal.SIGKILL)
            proc.wait(timeout=1.0)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass
