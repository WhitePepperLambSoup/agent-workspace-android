"""Shizuku (rish) 驱动的 Android 系统级特权工具集。

在无需 Root 的情况下, 借由无线调试配对获得的 ADB 权限:
执行系统级设置修改、清理指定应用数据/缓存、模拟屏幕触摸与应用操控。
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result

_SAFE_PACKAGE_RE = re.compile(r"^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)+$")
_PROTECTED_PACKAGES = {
    "com.android.settings",
    "com.android.systemui",
    "com.android.phone",
    "com.tencent.mm",  # 微信
    "com.eg.android.AlipayGphone",  # 支付宝
}


def is_shizuku_available() -> bool:
    """检查 rish (Shizuku 终端接入脚本) 是否可用并已授权。"""
    rish = shutil.which("rish")
    if not rish:
        return False
    try:
        res = subprocess.run(["rish", "-c", "whoami"], capture_output=True, text=True, timeout=1.5)
        # ADB 权限下 whoami 输出为 shell
        return res.returncode == 0 and "shell" in res.stdout
    except Exception:
        return False


class AndroidAppCleanerTool:
    """清理指定第三方应用的数据与缓存 (pm clear)。"""

    _SPEC = ToolSpec(
        name="android_clean_app",
        description=(
            "Clean cache and storage data for a specific Android package via Shizuku/ADB. "
            "WARNING: This will reset the application. System critical apps are protected. "
            "Requires approval outside YOLO."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "package_name": {"type": "string", "description": "e.g. com.sina.weibo"}
            },
            "required": ["package_name"],
            "additionalProperties": False,
        },
        side_effect="destructive",
        capability=Capability.PROCESS_EXECUTE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        if not is_shizuku_available():
            raise ToolError("Shizuku (rish) is not active or not granted")

        pkg = arguments.get("package_name", "").strip()
        if not _SAFE_PACKAGE_RE.match(pkg):
            raise ToolArgumentError(f"invalid package name: {pkg}")
        if pkg in _PROTECTED_PACKAGES:
            raise ToolError(f"package '{pkg}' is protected and cannot be cleared by agent")

        cmd = ["rish", "-c", f"pm clear {pkg}"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if "Success" in res.stdout:
            return json_result(status="success", package=pkg)
        return json_result(status="failed", error=res.stderr.strip() or res.stdout.strip())


class AndroidScreenAutomatorTool:
    """模拟屏幕触摸、滑动、输入文本与按键 (ADB input)。"""

    _SPEC = ToolSpec(
        name="android_screen_action",
        description=(
            "Simulate screen actions on Android via Shizuku (input tap, swipe, text, keyevent). "
            "Use to automate UI, open browsers, or click buttons on the device."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["tap", "swipe", "text", "keyevent"]},
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "x2": {"type": "integer"},
                "y2": {"type": "integer"},
                "text": {"type": "string"},
                "key_code": {"type": "integer", "description": "3=Home, 4=Back, 66=Enter"},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
        side_effect="external",
        capability=Capability.PROCESS_EXECUTE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        if not is_shizuku_available():
            raise ToolError("Shizuku (rish) is not active or not granted")

        action = arguments.get("action")
        if action == "tap":
            try:
                x = int(arguments["x"])
                y = int(arguments["y"])
            except (KeyError, TypeError, ValueError):
                raise ToolArgumentError("tap requires integer 'x' and 'y'") from None
            subprocess.run(["rish", "-c", f"input tap {x} {y}"], check=True)
            return json_result(action="tap", x=x, y=y)
        elif action == "swipe":
            try:
                x = int(arguments["x"])
                y = int(arguments["y"])
                x2 = int(arguments["x2"])
                y2 = int(arguments["y2"])
            except (KeyError, TypeError, ValueError):
                raise ToolArgumentError("swipe requires integer 'x', 'y', 'x2', 'y2'") from None
            subprocess.run(["rish", "-c", f"input swipe {x} {y} {x2} {y2} 300"], check=True)
            return json_result(action="swipe", from_x=x, from_y=y, to_x=x2, to_y=y2)
        elif action == "text":
            raw_text = str(arguments.get("text", ""))
            safe_text = raw_text.replace(" ", "%s")
            escaped = shlex.quote(safe_text)
            subprocess.run(["rish", "-c", f"input text {escaped}"], check=True)
            return json_result(action="text", typed=raw_text)
        elif action == "keyevent":
            try:
                code = int(arguments["key_code"])
            except (KeyError, TypeError, ValueError):
                raise ToolArgumentError("keyevent requires integer 'key_code'") from None
            subprocess.run(["rish", "-c", f"input keyevent {code}"], check=True)
            return json_result(action="keyevent", code=code)

        raise ToolError(f"unsupported screen action: {action}")
