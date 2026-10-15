"""Phone switches and personal info through the Android app (AndroidSystemSettings.kt,
AndroidPersonalInfo.kt).

- system_status reads volume, brightness, Do Not Disturb, Wi-Fi and Bluetooth state.
- system_settings changes volume, brightness and Do Not Disturb, presses media keys, or opens the
  Wi-Fi / Bluetooth / other panels (Android lets only the user flip those). Asks for approval.
- find_contacts and current_location work once the user allows contacts or location in this app
  (Settings → Device & tools), like the calendar; until then they say how to turn it on.
- compose_sms opens the Messages app with the text filled in; the user sends it. Asks for approval.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result

_classes: dict[str, Any] = {}
_ACCESS_HELP = {
    "contacts": "Contacts access is off. Ask the user to allow it in this app: Menu → 设备与工具 → 联系人 "
    "(Settings → Device & tools → Contacts), then try again.",
    "location": "Location access is off. Ask the user to allow it in this app: Menu → 设备与工具 → 位置 "
    "(Settings → Device & tools → Location), then try again.",
}


def _bridge(name: str) -> Any:
    if name not in _classes:
        from java import jclass

        _classes[name] = jclass(f"com.agentworkspace.mobile.capabilities.{name}")
    return _classes[name]


def personal_tools_available() -> bool:
    try:
        _bridge("AndroidSystemSettings")
        _bridge("AndroidPersonalInfo")
        return True
    except Exception:
        return False


async def _call(bridge: str, request: dict[str, Any]) -> dict[str, Any]:
    try:
        result = json.loads(str(await asyncio.to_thread(_bridge(bridge).execute, json.dumps(request))))
    except Exception as exc:
        raise ToolError(f"the phone could not do that: {exc}") from None
    if not isinstance(result, dict):
        raise ToolError("the phone returned an invalid result")
    if result.get("ok") is not True:
        detail = str(result.get("error") or "the phone refused the request")
        if result.get("code") == "permission_required" and detail in _ACCESS_HELP:
            raise ToolError(_ACCESS_HELP[detail])
        raise ToolError(detail)
    result.pop("ok", None)
    return result


class _Tool:
    _SPEC: ToolSpec

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute_with_context(self, arguments: dict[str, Any], _context: Any) -> str:
        return await self.execute(arguments)


class SystemStatusTool(_Tool):
    _SPEC = ToolSpec(
        name="system_status",
        description=(
            "Read the phone's switches: volume of media, ring, alarm and notifications (percent), "
            "brightness, Do Not Disturb, Wi-Fi and Bluetooth on or off, whether music is playing, "
            "and whether this app may change brightness and Do Not Disturb."
        ),
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        side_effect="none",
        capability=Capability.MEMORY_READ,
    )

    async def execute(self, _arguments: dict[str, Any]) -> str:
        return json_result(await _call("AndroidSystemSettings", {"action": "status"}))


_SETTINGS_ACTIONS = ("volume", "brightness", "dnd", "media", "open")


class SystemSettingsTool(_Tool):
    _SPEC = ToolSpec(
        name="system_settings",
        description=(
            "Change a phone switch. action volume: stream (media, ring, alarm, notification) and "
            "percent. brightness: percent, or auto=true. dnd: on true/false (Do Not Disturb). media: "
            "key play, pause, play_pause, next or previous (for whatever app is playing). open: "
            "panel wifi, internet, bluetooth, nfc or volume opens that switch for the user (Android "
            "lets only the user turn Wi-Fi and Bluetooth on or off; with phone control you can tap "
            "it), or write_settings / dnd_access to let the user allow brightness or Do Not Disturb "
            "changes when a result says that permission is needed."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": list(_SETTINGS_ACTIONS)},
                "stream": {"type": "string", "enum": ["media", "ring", "alarm", "notification"]},
                "percent": {"type": "integer", "minimum": 0, "maximum": 100},
                "auto": {"type": "boolean"},
                "on": {"type": "boolean"},
                "key": {"type": "string", "enum": ["play", "pause", "play_pause", "next", "previous"]},
                "panel": {"type": "string", "enum": ["wifi", "internet", "bluetooth", "nfc", "volume", "write_settings", "dnd_access"]},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
        side_effect="external",
        capability=Capability.PROCESS_EXECUTE,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        action = arguments.get("action")
        if action not in _SETTINGS_ACTIONS:
            raise ToolArgumentError(f"action must be one of {', '.join(_SETTINGS_ACTIONS)}")
        needs = {"volume": ("percent",), "dnd": ("on",), "media": ("key",), "open": ("panel",)}.get(action, ())
        if action == "brightness" and "percent" not in arguments and arguments.get("auto") is not True:
            raise ToolArgumentError("brightness needs percent or auto=true")
        missing = [name for name in needs if name not in arguments]
        if missing:
            raise ToolArgumentError(f"{action} needs {', '.join(missing)}")
        return json_result(await _call("AndroidSystemSettings", dict(arguments)))


class FindContactsTool(_Tool):
    _SPEC = ToolSpec(
        name="find_contacts",
        description=(
            "Find people in the phone's contacts by name or number and get their phone numbers "
            "(works after the user allows contacts in this app)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 60},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.MEMORY_READ,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip() or len(query) > 60:
            raise ToolArgumentError("query must be 1 to 60 characters")
        request = {"action": "find_contacts", "query": query.strip(), "limit": arguments.get("limit", 10)}
        return json_result(await _call("AndroidPersonalInfo", request))


class CurrentLocationTool(_Tool):
    _SPEC = ToolSpec(
        name="current_location",
        description=(
            "Where the phone is now: latitude, longitude, accuracy and, when available, the street "
            "address (works after the user allows location in this app). For directions or places "
            "nearby, open the map with android_action open_page map."
        ),
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        side_effect="none",
        capability=Capability.MEMORY_READ,
    )

    async def execute(self, _arguments: dict[str, Any]) -> str:
        return json_result(await _call("AndroidPersonalInfo", {"action": "location"}))


class ComposeSmsTool(_Tool):
    _SPEC = ToolSpec(
        name="compose_sms",
        description=(
            "Open the phone's Messages app with a text message to these numbers filled in. It is "
            "not sent: the user reads it and taps send. Use find_contacts for a number."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "to": {"type": "string", "minLength": 3, "maxLength": 200},
                "body": {"type": "string", "maxLength": 2000},
            },
            "required": ["to", "body"],
            "additionalProperties": False,
        },
        side_effect="external",
        capability=Capability.PROCESS_EXECUTE,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        request = {"action": "compose_sms", "to": arguments.get("to", ""), "body": arguments.get("body", "")}
        return json_result(await _call("AndroidPersonalInfo", request))


class RecentNotificationsTool(_Tool):
    _SPEC = ToolSpec(
        name="recent_notifications",
        description=(
            "Notifications the phone received in the last hours (newest first: time, app, title, text), "
            "kept on the phone while the user has the notification digest on (Settings → Notification "
            "rules → Notification digest). Verification codes are already hidden. For a digest: sort "
            "them into needs attention / can wait / ads, and pull out pickup codes, flights or trains, "
            "meeting changes and bills due; a checklist card suits the things to do."
        ),
        input_schema={
            "type": "object",
            "properties": {"hours": {"type": "number", "minimum": 0.1, "maximum": 48}},
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.MEMORY_READ,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        import mobile_notification_journal as journal

        state = journal.status()
        if not state["enabled"]:
            raise ToolError("The notification digest is off, so no notifications are kept. Ask the user to turn "
                            "it on: Menu → 通知触发 → 通知摘要 (Notification rules → Notification digest).")
        hours = arguments.get("hours", 2)
        if not isinstance(hours, (int, float)) or not 0.1 <= hours <= 48:
            raise ToolArgumentError("hours must be from 0.1 to 48")
        entries = await asyncio.to_thread(journal.recent, hours)
        return json_result({"hours": hours, "count": len(entries), "notifications": entries})


def personal_tools() -> dict[str, Any]:
    return {
        "system_status": SystemStatusTool,
        "system_settings": SystemSettingsTool,
        "find_contacts": FindContactsTool,
        "current_location": CurrentLocationTool,
        "compose_sms": ComposeSmsTool,
        "recent_notifications": RecentNotificationsTool,
    }
