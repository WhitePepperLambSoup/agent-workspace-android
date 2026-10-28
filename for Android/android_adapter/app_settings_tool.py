"""app_settings: the agent finds, opens and proposes changes to this app's own settings.

Users asked the agent where a setting is, or to change it, and it could not help. The tool lists
what can be changed with the current values (the page reports them), opens a settings page for the
user, and proposes a change: the conversation shows a card with the old and new value, and nothing
changes until the user taps Apply there (app/28-app-settings.js applies it the way the settings page
does). API keys, the app lock and permissions the system grants stay with the user: the agent can
only open their page.
"""

from __future__ import annotations

import threading
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, json_result

_ON_OFF = {"on": "开", "off": "关"}

# id: title, choices (value: label; None for a model name), the page it lives on, and a warning
# shown on the card for values that let the agent do more without asking.
SETTINGS: dict[str, dict[str, Any]] = {
    "theme": {"title": "深色 / 浅色", "choices": {"system": "跟随系统", "light": "浅色", "dark": "深色"}, "page": "appearance"},
    "text_size": {"title": "文字大小", "choices": {"small": "小", "normal": "标准", "large": "大"}, "page": "appearance"},
    "style": {"title": "界面风格", "choices": {"solid": "标准", "glass": "液态玻璃"}, "page": "appearance"},
    "accent": {"title": "主题色", "choices": {"teal": "青绿", "blue": "蓝", "violet": "紫", "amber": "琥珀", "rose": "玫红"}, "page": "appearance"},
    "motion": {"title": "动画", "choices": {"auto": "跟随系统", "full": "完整", "reduced": "减少", "off": "关闭"}, "page": "appearance"},
    "language": {"title": "界面语言", "choices": {"auto": "跟随系统", "zh": "简体中文", "zh-Hant": "繁體中文", "en": "English", "ja": "日本語", "ko": "한국어"}, "page": "appearance"},
    "quick_actions": {"title": "输入框上方的快捷任务", "choices": _ON_OFF, "page": "appearance"},
    "haptics": {"title": "触感反馈", "choices": _ON_OFF, "page": "appearance"},
    "model": {"title": "模型", "choices": None, "page": "model"},
    "reasoning_effort": {"title": "思考程度", "choices": {"auto": "自动", "none": "不思考", "low": "低", "medium": "中", "high": "高", "xhigh": "极高", "max": "最高"}, "page": "model"},
    "execution_mode": {
        "title": "执行模式",
        "choices": {"workspace": "仅工作区（改文件、联网等先问你）", "yolo": "YOLO（大部分操作不再询问）", "full_access": "完全访问（几乎不再询问）"},
        "page": "permission",
        "risk": {"yolo": "AI 改文件、运行命令时大多不再先问你。", "full_access": "AI 可以不经询问访问手机上的更多内容并执行操作。"},
    },
    "floating_ball": {"title": "悬浮球", "choices": _ON_OFF, "page": "globalEntry"},
    "task_notifications": {"title": "任务完成通知", "choices": _ON_OFF, "page": "notifications"},
    "offline_voice": {"title": "语音输入用离线识别", "choices": _ON_OFF, "page": "localModels"},
    "auto_update_check": {"title": "自动检查更新", "choices": _ON_OFF, "page": "about"},
}

# Settings pages the agent can open for the user, by the name in the menu.
PAGES: dict[str, str] = {
    "model": "模型与思考", "permission": "执行权限", "appearance": "界面偏好", "localModels": "本地模型",
    "connections": "设备连接", "notifications": "通知", "globalEntry": "全局入口（悬浮球、快捷开关、桌面快捷方式）",
    "elder": "长辈模式", "backup": "备份与恢复", "about": "关于与更新", "memory": "记忆", "knowledge": "知识库",
    "schedules": "定时任务", "notificationRules": "通知触发", "appCheck": "应用体检", "doctor": "设备与工具（无障碍、后台运行、权限）",
    "skills": "技能", "usage": "Token 与费用", "tasks": "任务中心", "files": "工作区文件", "workspaces": "工作区",
    "services": "后台服务", "extensions": "MCP 与扩展", "outbox": "待发送与接力", "provider": "服务商与 API 密钥",
}

# Current values, as the page last reported them (POST /mobile/app-settings/snapshot).
_snapshot: dict[str, str] = {}
_lock = threading.Lock()


def set_snapshot(values: Any) -> dict[str, str]:
    if not isinstance(values, dict):
        raise ValueError("values must be an object")
    clean = {
        key: value for key, value in values.items()
        if key in SETTINGS and isinstance(value, str) and len(value) <= 200
    }
    with _lock:
        _snapshot.clear()
        _snapshot.update(clean)
    return dict(clean)


def _current(key: str) -> str | None:
    with _lock:
        return _snapshot.get(key)


class AppSettingsTool:
    _SPEC = ToolSpec(
        name="app_settings",
        description=(
            "This app's own settings (Agent Workspace): use it when the user asks where a setting is, "
            "what it is set to, or to change one. action=list gives what can be changed, the current "
            "values and the settings pages. action=open shows the user a settings page (give 'page'). "
            "action=change proposes a new value (give 'setting' and 'value'): the user sees a card with "
            "the change and applies it with one tap; nothing changes before that, so tell them to tap "
            "Apply. API keys, the app lock and system permissions cannot be changed here: open their page."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "open", "change"]},
                "setting": {"type": "string", "maxLength": 40},
                "value": {"type": "string", "maxLength": 200},
                "page": {"type": "string", "maxLength": 40},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
        # Changes nothing by itself: a change waits for the user's tap on its card.
        side_effect="none",
        capability=Capability.MEMORY_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        action = arguments.get("action")
        if action == "list":
            return json_result({
                "settings": [
                    {
                        "setting": key,
                        "title": entry["title"],
                        "current": _current(key),
                        "values": entry["choices"] or "a model name the provider offers",
                        "page": entry["page"],
                    }
                    for key, entry in SETTINGS.items()
                ],
                "pages": PAGES,
            })
        if action == "open":
            page = arguments.get("page")
            if page not in PAGES:
                raise ToolArgumentError(f"'page' must be one of: {', '.join(PAGES)}")
            return json_result({"open": page, "title": PAGES[page],
                                "note": "The page is not open yet, so do not say you opened it. The conversation "
                                        "shows the user a button below your reply that opens it; tell them to tap it."})
        if action == "change":
            key, value = arguments.get("setting"), arguments.get("value")
            if key not in SETTINGS:
                raise ToolArgumentError(f"'setting' must be one of: {', '.join(SETTINGS)}")
            entry = SETTINGS[key]
            choices = entry["choices"]
            if not isinstance(value, str) or not value.strip() or (choices is not None and value not in choices):
                raise ToolArgumentError(
                    f"'value' for {key} must be one of: {', '.join(choices)}" if choices else "'value' must be a model name"
                )
            value = value.strip()
            current = _current(key)
            return json_result({
                "setting": key,
                "title": entry["title"],
                "from": (choices or {}).get(current, current) if current is not None else None,
                "to": (choices or {}).get(value, value),
                "risk": (entry.get("risk") or {}).get(value),
                "note": "Nothing has changed yet, so do not say it is changed. The user sees a card with "
                        "this change below your reply; it takes effect when they tap its button (Apply; "
                        "「应用更改」 in Chinese). Tell them that (or that it is already set, if 'from' equals 'to').",
            })
        raise ToolArgumentError("'action' must be list, open or change")


__all__ = ["AppSettingsTool", "PAGES", "SETTINGS", "set_snapshot"]
