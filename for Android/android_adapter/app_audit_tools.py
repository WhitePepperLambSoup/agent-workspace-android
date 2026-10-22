"""app_audit and manage_app: looking for rogue apps (mobile_app_audit, AppAudit.kt).

- app_audit lists the apps the user installed that hold risky powers or pop up by themselves, with
  the reasons. Reading only.
- manage_app opens Android's uninstall confirmation for an app (nothing is removed until it is
  confirmed there) or the settings page that takes a power back. Asks for approval.
"""

from __future__ import annotations

import asyncio
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result

_REASONS = {
    "device_admin": "device admin (can lock or wipe the phone; blocks uninstalling until removed)",
    "accessibility": "accessibility service on (reads every screen, can tap)",
    "notification_listener": "reads all notifications",
    "sms": "can read SMS",
    "hidden_icon": "no home-screen icon",
    "old_target": "built for Android 5 or older (got every permission without asking)",
    "pops_up": "popped up by itself over other apps",
    "call_log": "can read the call log",
    "background_location": "location in the background",
    "overlay": "may draw over other apps",
    "install_others": "may install other apps",
    "usage_access": "sees which apps you use",
    "keeps_running": "starts with the phone, exempt from battery limits",
    "manual_install": "installed from an APK file, not a store",
    "installed_by_app": "installed by another app",
    "new": "installed in the last 3 days",
    "disabled": "turned off",
}
_SOURCES = {
    "store": "app store",
    "manual": "APK file opened by hand",
    "app": "installed by another app",
    "self": "updated itself",
    # Android names no installer for apps that came with the phone either.
    "unknown": "no installer recorded: came with the phone, or installed from a computer",
}


def app_audit_available() -> bool:
    import mobile_app_audit

    return mobile_app_audit.available()


class AppAuditTool:
    _SPEC = ToolSpec(
        name="app_audit",
        description=(
            "Check the apps the user installed for rogue behaviour (流氓软件): device admin, accessibility, "
            "reading notifications or SMS, no home-screen icon, popping up over other apps, installed from "
            "an APK or by another app. Returns the apps worth attention, worst first, with reasons and the "
            "pages that undo each power. Facts only, not a virus scan: report them without guessing beyond "
            "them, and let the user decide; a big app from a store with one power is usually fine. Pop-ups "
            "are recorded only while the user has that on (Menu → 应用体检)."
        ),
        input_schema={
            "type": "object",
            "properties": {"all": {"type": "boolean", "description": "Include apps with nothing worth noting."}},
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.MEMORY_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute_with_context(self, arguments: dict[str, Any], _context: Any) -> str:
        return await self.execute(arguments)

    async def execute(self, arguments: dict[str, Any]) -> str:
        import mobile_app_audit

        try:
            report = await asyncio.to_thread(mobile_app_audit.scan_phone)
        except Exception as exc:
            raise ToolError(f"the phone could not check its apps: {exc}") from None
        wanted = ("high", "medium", "low", "none", "trusted") if arguments.get("all") is True else ("high", "medium")
        apps = []
        for app in report["apps"]:
            if app["level"] not in wanted:
                continue
            source = app["source"]
            item = {
                "app": app["label"],
                "package_name": app["package"],
                "level": app["level"],
                "reasons": [_REASONS.get(code, code) for code in app["signals"]],
                "source": _SOURCES.get(source["kind"], source["kind"])
                + (f" ({source.get('by_label') or source['by']})" if source.get("by") and source["kind"] != "self" else ""),
                "undo_pages": app["actions"],
            }
            if app["popups"]:
                item["popups_7_days"] = {"came_to_front": app["popups"]["jumps"], "covered_screen": app["popups"]["overlays"]}
            apps.append(item)
        return json_result({
            "checked": report["checked"],
            "needs_attention": report["high"],
            "worth_a_look": report["medium"],
            "popup_record": "on" if report["watching"] else "off (the user can turn it on in Menu → 应用体检)",
            "apps": apps,
        })


class ManageAppTool:
    _SPEC = ToolSpec(
        name="manage_app",
        description=(
            "For an app the user wants gone or tamed (see app_audit). page uninstall opens Android's "
            "uninstall confirmation: nothing is removed until it is confirmed there. A device admin app "
            "must lose that first (page device_admin). Other pages take a power back: overlay, "
            "notifications, install_others, usage_access, notification_access, accessibility, battery, "
            "or info for the app's details (force stop, permissions). With phone control you can finish "
            "the step on that page."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "package_name": {"type": "string", "minLength": 3, "maxLength": 255},
                "page": {"type": "string", "enum": ["uninstall", "info", "notifications", "overlay", "install_others",
                                                    "usage_access", "notification_access", "accessibility",
                                                    "device_admin", "battery"]},
            },
            "required": ["package_name", "page"],
            "additionalProperties": False,
        },
        side_effect="external",
        capability=Capability.PROCESS_EXECUTE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute_with_context(self, arguments: dict[str, Any], _context: Any) -> str:
        return await self.execute(arguments)

    async def execute(self, arguments: dict[str, Any]) -> str:
        import mobile_app_audit

        try:
            await asyncio.to_thread(mobile_app_audit.open_page, arguments.get("package_name"), arguments.get("page"))
        except ValueError as exc:
            raise ToolArgumentError(str(exc)) from None
        except Exception as exc:
            raise ToolError(f"the phone could not open that page: {exc}") from None
        return json_result({"opened": arguments["page"], "package_name": arguments["package_name"]})


def app_audit_tools() -> dict[str, Any]:
    return {"app_audit": AppAuditTool, "manage_app": ManageAppTool}
