"""Termux:API 官方扩展工具集包装。

提供与 Android 系统硬件与框架的桥接能力:
剪贴板读写、系统通知栏推送、电池电量感知、设备休眠锁 (WakeLock)。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolError, json_result


def is_termux_api_available() -> bool:
    """检测系统中是否已安装 termux-api 命令。"""
    return shutil.which("termux-clipboard-get") is not None


class AndroidClipboardTool:
    """读取或写入 Android 系统剪贴板。"""

    _SPEC = ToolSpec(
        name="android_clipboard",
        description=(
            "Read from or write text to the Android system clipboard via Termux:API. "
            "Action can be 'get' or 'set'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["get", "set"]},
                "text": {"type": "string", "description": "Text to copy when action is set"},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
        side_effect="external",
        capability=Capability.WORKSPACE_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        if not is_termux_api_available():
            raise ToolError("termux-api is not installed (run 'pkg install termux-api')")

        action = arguments["action"]
        if action == "get":
            res = subprocess.run(["termux-clipboard-get"], capture_output=True, text=True)
            return json_result(clipboard=res.stdout)
        elif action == "set":
            text = arguments.get("text", "")
            subprocess.run(["termux-clipboard-set"], input=text, text=True, check=True)
            return json_result(status="copied", length=len(text))
        raise ToolError(f"unknown clipboard action: {action}")


class AndroidNotificationTool:
    """向 Android 系统通知栏推送交互消息。"""

    _SPEC = ToolSpec(
        name="android_notify",
        description="Push a system notification banner to Android notification drawer.",
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": 100},
                "content": {"type": "string", "maxLength": 1000},
                "priority": {
                    "type": "string",
                    "enum": ["low", "default", "high"],
                    "default": "high",
                },
            },
            "required": ["title", "content"],
            "additionalProperties": False,
        },
        side_effect="external",
        capability=Capability.PROCESS_EXECUTE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        if not shutil.which("termux-notification"):
            raise ToolError("termux-notification is not available")

        title = arguments["title"]
        content = arguments["content"]
        priority = arguments.get("priority", "high")

        cmd = [
            "termux-notification",
            "--title",
            title,
            "--content",
            content,
            "--priority",
            priority,
            "--id",
            "agent_workspace_status",
        ]
        subprocess.run(cmd, check=True)
        return json_result(status="notified", title=title)


class AndroidBatteryTool:
    """获取设备电池状态(电量、充电状态、温度)。"""

    _SPEC = ToolSpec(
        name="android_battery",
        description="Check Android device battery level, charging status, and temperature.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        side_effect="none",
        capability=Capability.WORKSPACE_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        if not shutil.which("termux-battery-status"):
            raise ToolError("termux-battery-status is not available")

        res = subprocess.run(["termux-battery-status"], capture_output=True, text=True)
        try:
            data = json.loads(res.stdout)
            return json_result(**data)
        except Exception as e:
            raise ToolError(f"failed to parse battery status: {e}") from e
