"""无侵入式运行时补丁注入器 (Non-invasive Runtime Patcher)。

核心设计宗旨:
绝对不修改主项目磁盘上的任何文件(保证另一位 AI 审查主干时工作树 100% 纯净),
而是在 Python 进程启动初期, 在内存中动态将 Windows 专有实现替换为 Android/POSIX 垫片。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def apply_android_patches() -> None:
    """在运行时将 Android 适配器注入到 agent_workspace 系统模块中。"""

    # 1. 确保将主项目的 src 目录加入到模块导入路径中
    agent_root = Path(__file__).resolve().parent.parent.parent
    src_dir = agent_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    # 2. 内存热替换凭据系统 (Credentials)
    import agent_workspace.credentials as cred_mod

    from . import credentials as posix_cred

    cred_mod.get_credential = posix_cred.get_credential
    cred_mod.set_credential = posix_cred.set_credential
    cred_mod.delete_credential = posix_cred.delete_credential
    cred_mod.list_credentials = posix_cred.list_credentials

    # 3. 内存热替换终端 PTY 工具 (RunTerminalTool)
    import agent_workspace.tools.pty as pty_mod

    from . import pty as posix_pty

    # Replace the class consumed by future imports. Keep the Windows module's
    # original `_conpty_sync` function intact: test processes and long-lived
    # hosts may already hold a reference to the Windows class, and rewriting
    # that module-global function would make a later Windows invocation call
    # the POSIX implementation with an incompatible signature. The Android
    # entrypoint imports the registry after this patch, while the registry
    # alias below also covers hosts that imported it earlier.
    pty_mod.RunTerminalTool = posix_pty.RunTerminalTool
    try:
        import agent_workspace.tools.registry as registry_mod
    except ImportError:
        registry_mod = None
    if registry_mod is not None:
        registry_mod.RunTerminalTool = posix_pty.RunTerminalTool

    # 4. 动态向系统工具注册表挂载 Android 系统级工具.
    # ToolRegistry exposes a classmethod factory; there is no separate
    # get_builtin_tools hook to patch. Keep the wrapper idempotent because the
    # entrypoint and tests may apply the adapter more than once.
    from agent_workspace.tools import registry as tool_reg
    from agent_workspace.tools.paths import WorkspacePaths

    from . import shizuku, termux_api
    from .capabilities import configure_android_registry

    registry_cls = tool_reg.ToolRegistry
    original_for_workspace = registry_cls.for_workspace
    if not getattr(original_for_workspace, "_android_patched", False):

        def _patched_for_workspace(
            cls: type[Any], workspace: Any, *args: Any, **kwargs: Any
        ) -> Any:
            registry = original_for_workspace(workspace, *args, **kwargs)
            if termux_api.is_termux_api_available():
                for tool in (
                    termux_api.AndroidClipboardTool(),
                    termux_api.AndroidNotificationTool(),
                    termux_api.AndroidBatteryTool(),
                ):
                    registry.register(tool)
            if shizuku.is_shizuku_available():
                for tool in (
                    shizuku.AndroidAppCleanerTool(),
                    shizuku.AndroidScreenAutomatorTool(),
                ):
                    registry.register(tool)
            workspace_root = workspace.root if isinstance(workspace, WorkspacePaths) else workspace
            configure_android_registry(registry, workspace_root)
            return registry

        _patched_for_workspace._android_patched = True  # type: ignore[attr-defined]
        registry_cls.for_workspace = classmethod(_patched_for_workspace)

    # 5. 设置针对 Termux 优化过的环境变量默认值
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    os.environ.setdefault("NO_COLOR", "0")
