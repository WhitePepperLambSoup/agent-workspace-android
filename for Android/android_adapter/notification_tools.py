"""Notifications as things to act on (NotificationActions.kt, through notification access).

- active_notifications lists what is in the notification shade now: app, title, text (verification
  codes hidden), whether it can be answered or opened, and its key.
- notification_reply answers a message from its notification, through the app's own quick reply,
  without opening the app. It sends a message as the user, so it asks every time (mobile_approval).
- notification_open opens the page a notification leads to (the chat, the order), as a tap on it would.

The app's own notifications, ongoing ones (music, downloads) and apps the user keeps the agent away
from are left out. All of it needs notification access (Settings → Notification rules).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result

_ACCESS_HELP = (
    "Notification access is off. Ask the user to allow it: Menu → 通知触发 → 通知使用权 "
    "(Notification rules → Notification access), then try again."
)
_bridge_class: Any = None


def _bridge() -> Any:
    global _bridge_class
    if _bridge_class is None:
        from java import jclass

        _bridge_class = jclass("com.agentworkspace.mobile.notifications.NotificationActions")
    return _bridge_class


def notification_tools_available() -> bool:
    try:
        _bridge()
        return True
    except Exception:
        return False


async def _call(request: dict[str, Any]) -> dict[str, Any]:
    try:
        result = json.loads(str(await asyncio.to_thread(_bridge().execute, json.dumps(request))))
    except Exception as exc:
        raise ToolError(f"the phone could not do that: {exc}") from None
    if not isinstance(result, dict):
        raise ToolError("the phone returned an invalid result")
    if result.get("ok") is not True:
        if result.get("code") == "access_off":
            raise ToolError(_ACCESS_HELP)
        raise ToolError(str(result.get("error") or "the phone refused the request"))
    result.pop("ok", None)
    return result


def _key(arguments: dict[str, Any]) -> str:
    key = arguments.get("key")
    if not isinstance(key, str) or not key or len(key) > 1024:
        raise ToolArgumentError("'key' must be a notification key from active_notifications")
    return key


class _Tool:
    _SPEC: ToolSpec

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute_with_context(self, arguments: dict[str, Any], _context: Any) -> str:
        return await self.execute(arguments)


class ActiveNotificationsTool(_Tool):
    _SPEC = ToolSpec(
        name="active_notifications",
        description=(
            "List the notifications in the phone's notification shade now (newest first): app, "
            "title, text, time, whether it can be answered (can_reply) or opened (can_open), and its "
            "key for notification_reply or notification_open. Verification codes are hidden."
        ),
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        side_effect="none",
        capability=Capability.MEMORY_READ,
    )

    async def execute(self, _arguments: dict[str, Any]) -> str:
        from mobile_notification_journal import mask_codes

        result = await _call({"action": "list"})
        items = []
        for item in result.get("notifications") or []:
            if not isinstance(item, dict):
                continue
            posted = item.get("posted_ms")
            items.append(
                {
                    "key": item.get("key"),
                    "app": item.get("app"),
                    "title": mask_codes(str(item.get("title") or "")),
                    "text": mask_codes(str(item.get("text") or "")),
                    "time": datetime.fromtimestamp(posted / 1000).strftime("%m-%d %H:%M")
                    if isinstance(posted, (int, float)) and posted > 0
                    else None,
                    "can_reply": item.get("can_reply") is True,
                    "can_open": item.get("can_open") is True,
                }
            )
        return json_result({"count": len(items), "notifications": items})


class NotificationReplyTool(_Tool):
    _SPEC = ToolSpec(
        name="notification_reply",
        description=(
            "Answer a message from its notification with the app's own quick reply (WeChat, QQ, "
            "Messages, Telegram and other apps that offer one), without opening the app. The text is "
            "sent as the user, so the user approves each reply. Get the key from "
            "active_notifications and use only notifications with can_reply true; for the others, "
            "open the app (notification_open) and type there."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "minLength": 1, "maxLength": 1024},
                "text": {"type": "string", "minLength": 1, "maxLength": 2000},
                "to": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Who the reply goes to, as the notification shows them (for the approval)",
                },
            },
            "required": ["key", "text"],
            "additionalProperties": False,
        },
        side_effect="external",
        capability=Capability.PROCESS_EXECUTE,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        text = arguments.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ToolArgumentError("'text' must be 1 to 2000 characters")
        return json_result(await _call({"action": "reply", "key": _key(arguments), "text": text}))


class NotificationOpenTool(_Tool):
    _SPEC = ToolSpec(
        name="notification_open",
        description=(
            "Open what a notification leads to (the chat, the order, the email), as a tap on it "
            "would. Get the key from active_notifications. Then read the screen with android_observe."
        ),
        input_schema={
            "type": "object",
            "properties": {"key": {"type": "string", "minLength": 1, "maxLength": 1024}},
            "required": ["key"],
            "additionalProperties": False,
        },
        side_effect="external",
        capability=Capability.PROCESS_EXECUTE,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        return json_result(await _call({"action": "open", "key": _key(arguments)}))


def notification_tools() -> dict[str, Any]:
    return {
        "active_notifications": ActiveNotificationsTool,
        "notification_reply": NotificationReplyTool,
        "notification_open": NotificationOpenTool,
    }


__all__ = ["notification_tools", "notification_tools_available"]
