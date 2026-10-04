> 历史方案说明：本页保留早期 Termux/原生宿主设计供参考。当前默认 APK 使用 Chaquopy Python 3.12、CPU JNI 推理和可选 PRoot 工具链；旧页的全功能/后台保活/默认工具可用性描述不是当前验收结论。安装与构建请以 [README](README.md)、[当前架构](00_PORTING_OVERVIEW_AND_ARCHITECTURE.md) 和 [构建指南](10_APK_BUILD_AND_RELEASE_GUIDE.md) 为准。

# Android (Termux) 工具集与执行引擎适配规范

> 文档编号：AW-AND-03  
> 涉及模块：`src/agent_workspace/tools/`、`tools/pty.py`、`tools/process_runner.py`、`tools/browser.py`、`tools/lsp.py`  

---

## 1. 进程生命周期与进程树清理 (Process Runner)

### 1.1 Windows 现有实现与冲突
在 Windows 环境下，当用户点击“取消”或任务超时，[`tools/process_runner.py`](file:///d:/opencode%20program/Agent/src/agent_workspace/tools/process_runner.py) 将所有子进程绑定到 **Windows 作业对象（Job Object）**。关闭 Job 句柄会促使操作系统内核彻底终止整棵进程树（包括嵌套启动的 python、git、node 等）。该 API 在 Linux/Android 上完全不可用。

### 1.2 POSIX 进程组与信号树方案 (`PosixProcessRunner`)
在 Termux / Linux 环境下，必须采用标准的 **POSIX 进程会话（Process Group）与信号连根清除机制**：

```python
import os
import signal
import subprocess
from typing import IO


def launch_posix_supervised_process(
    cmd: list[str],
    cwd: str,
    env: dict[str, str],
    stdout: int | IO[bytes] = subprocess.PIPE,
    stderr: int | IO[bytes] = subprocess.PIPE,
) -> subprocess.Popen[bytes]:
    """通过 start_new_session 创建独立的进程组领导者。"""
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,  # 相当于在子进程执行 os.setpgrp()
    )


def kill_process_tree(proc: subprocess.Popen[bytes], grace_timeout: float = 2.0) -> None:
    """连根拔起杀死进程组内的所有派生子进程。"""
    if proc.poll() is not None:
        return

    pgid = os.getpgid(proc.pid)
    try:
        # 1. 优先发送 SIGTERM 优雅退出
        os.killpg(pgid, signal.SIGTERM)
        proc.wait(timeout=grace_timeout)
    except (subprocess.TimeoutExpired, ProcessLookupError):
        # 2. 超时未退出，强制发送 SIGKILL 连根杀死
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
```

---

## 2. 伪终端 (PTY) 跨平台替换：从 ConPTY 到 POSIX PTY

### 2.1 架构替换对比
* **Windows**：调用 `CreatePseudoConsole()`，通过命名管道（Named Pipes）与 ConPTY 通信。
* **Termux / Linux**：使用 Linux 原生 `/dev/ptmx` 虚拟控制台，Python 标准库 `pty` 和 `termios` 即可提供原生支持。

### 2.2 POSIX 终端管理器实现 (`tools/pty_posix.py`)

```python
import os
import pty
import select
import termios
import struct
import fcntl
from typing import Generator


class PosixTerminalSession:
    def __init__(self, cols: int = 120, rows: int = 30) -> None:
        self._master_fd, self._slave_fd = pty.openpty()
        self.resize(cols, rows)
        # 设置非阻塞读取
        flags = fcntl.fcntl(self._master_fd, fcntl.F_GETFL)
        fcntl.fcntl(self._master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def resize(self, cols: int, rows: int) -> None:
        """调整终端虚拟尺寸 (TIOCSWINSZ)。"""
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)

    def spawn(self, cmd: list[str], env: dict[str, str], cwd: str) -> None:
        self._pid = os.fork()
        if self._pid == 0:
            # 子进程：绑定 slave PTY
            os.close(self._master_fd)
            os.setsid()
            os.dup2(self._slave_fd, 0)
            os.dup2(self._slave_fd, 1)
            os.dup2(self._slave_fd, 2)
            os.close(self._slave_fd)
            os.chdir(cwd)
            os.execvpe(cmd[0], cmd, env)
        else:
            # 父进程：关闭 slave
            os.close(self._slave_fd)

    def write(self, data: bytes) -> None:
        os.write(self._master_fd, data)

    def read_stream(self, max_bytes: int = 4096) -> bytes:
        r, _, _ = select.select([self._master_fd], [], [], 0.05)
        if r:
            return os.read(self._master_fd, max_bytes)
        return b""
```

---

## 3. 核心工具集在 Termux 的可用性与降级策略

### 3.1 路径与 Shell 解析陷阱（关键细节！）
* **陷阱**：Android 标准文件系统中**没有 `/bin/sh` 或 `/bin/bash`**！在普通 Linux 脚本第一行写的 `#!/bin/bash` 在 Termux 中会直接报错 `No such file or directory`。
* **解决方案**：
  1. Termux 提供了 `termux-exec` 机制（拦截 `execve` 自动将 `/bin/sh` 重定向为 `$PREFIX/bin/sh`）；
  2. 在 Agent 代码执行层，显式使用环境变量解析：
     ```python
     def get_default_shell() -> str:
         prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
         bash_path = os.path.join(prefix, "bin", "bash")
         return bash_path if os.path.exists(bash_path) else "/system/bin/sh"
     ```

### 3.2 工具兼容性矩阵与调整方案

| 工具名称 | 源码对应 | Termux 状态 | 适配与降级方案 |
|---|---|---|---|
| **文件读写/补丁** | `tools/filesystem.py` | **完全支持** | 纯 Python 实现，路径规范自动支持 POSIX 正斜杠。 |
| **代码正则搜索** | `tools/code_search.py` | **完全支持** | 直接调用 Termux 预装的 `ripgrep` (`rg`) 二进制。 |
| **Git 操作** | `tools/git_ops.py` | **完全支持** | Termux 官方包 `pkg install git` 完美运行。 |
| **LSP 语言服务器** | `tools/lsp.py` | **完全支持** | Python (`jedi-language-server`) 与 TS (`typescript-language-server`) 均可经由 pip/npm 直接运行。 |
| **Docker 容器** | `tools/docker.py` | **不支持 (禁用)** | Android 内核缺少 cgroup/namespace 模块；在工具清单中隐藏或直接报错提示。 |
| **CDP 浏览器** | `tools/browser.py` | **降级重构** | 见下节。 |

### 3.3 CDP 浏览器工具的移动端降级方案
在 PC 桌面端，Agent 可以通过端口 `9222` 连接本地 Chrome。在手机上该路径失效，设计**三级优雅降级**：
1. **默认降级（纯静态快照）**：
   使用已有的 `fetch_url` 工具（`httpx` + `readability`），将目标网页提取为干净的 Markdown 文本与结构化引用。90% 的资料研究需求可完全满足。
2. **高级动态抓取（Proot Headless Chromium）**：
   在 Termux 安装 `proot-distro` 并在其中安装 ARM64 Linux 版 Chromium，通过无头模式（`--headless --disable-gpu`）提供真实的 CDP DOM 快照。
