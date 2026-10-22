"""Android accessibility observation and action tools.

The Android side owns the accessibility connection and snapshot lifecycle.  This
module validates the model-facing request, invokes the small JSON bridge, and
keeps screenshot artifacts inside the private Android workspace.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from agent_workspace.core.events import Event
from agent_workspace.core.models import MAX_IMAGE_BYTES, BinaryArtifact, Capability, ToolSpec
from agent_workspace.tools.base import (
    ToolArgumentError,
    ToolError,
    json_result,
    validate_tool_arguments,
)

if TYPE_CHECKING:
    from agent_workspace.application.ports import ToolExecutionContext


_MAX_NODES = 400
_MAX_DEPTH = 24
_MAX_TEXT = 4096
_MAX_REF = 160
_MAX_EXPECT = 300
_MAX_TIMEOUT_MS = 5000
_MAX_SCREENSHOT_BYTES = MAX_IMAGE_BYTES
# The negative lookahead requires the actual end of the string: JSON Schema's
# regex search would otherwise let an anchored pattern match before a final LF.
_PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+(?![\s\S])")
_REF_RE = re.compile(r"^n[0-9]{1,4}(?![\s\S])")
_STRING_PATTERN = r"^[^\u0000]+(?![\s\S])"
_ACTION_FIELDS = {
    "tap": ("x", "y", "confirmed"),
    "swipe": ("x", "y", "x2", "y2"),
    "ref": ("ref", "confirmed"),
    "type_text": ("ref", "text"),
    "long_press": ("ref", "x", "y", "confirmed"),
    "scroll": ("direction", "ref"),
    "enter": ("ref",),
    "launch_app": ("package_name", "app_name"),
    "back": (),
    "home": (),
    "recents": (),
    "notifications": (),
    "batch": ("steps",),
    "repeat": ("steps", "every_ms", "times"),
    "stop_repeat": (),
    "tap_text": ("text", "nth", "confirmed"),
    "scroll_to_text": ("text", "direction", "ref", "max_scrolls", "tap", "confirmed"),
    "open_page": ("page", "package_name", "app_name", "url", "query", "number"),
}
# These read the screen as it is when they run: a snapshot_version is optional.
_FRESH_ACTIONS = (
    "tap_text", "scroll_to_text", "open_page", "launch_app", "back", "home", "recents", "notifications",
)
_PAGES = (
    "settings", "wifi", "bluetooth", "mobile_network", "data_usage", "airplane", "battery",
    "display", "sound", "location", "storage", "date", "language", "accessibility", "security",
    "nfc", "vpn", "developer", "apps", "notifications", "app_details", "url", "map",
    "web_search", "dial",
)
_MAX_LABEL = 200
# What an action needs: every field of one of these groups (none listed: nothing beyond the action).
_REQUIRED = {
    "tap_text": (("text",),),
    "scroll_to_text": (("text",),),
    "open_page": (("page",),),
    "tap": (("x", "y"),),
    "swipe": (("x", "y", "x2", "y2"),),
    "ref": (("ref",),),
    "type_text": (("ref", "text"),),
    # A control or a point, not both.
    "long_press": (("ref",), ("x", "y")),
    "scroll": (("direction",),),
    # Either (or both: the package first, the name if it is not installed).
    "launch_app": (("package_name",), ("app_name",)),
    "batch": (("steps",),),
    "repeat": (("steps", "every_ms"),),
}
_EXCLUSIVE = frozenset({"long_press"})
# One approval covers a batch, so it holds no app launches and no nested batches.
_BATCH_ACTIONS = ("tap", "swipe", "ref", "type_text", "long_press", "scroll", "enter", "back", "tap_text")
_MAX_BATCH = 12
# A repeat's steps act by coordinates, scroll direction or back: a feed shows something new each
# round, so refs from one observation would not last.
_REPEAT_ACTIONS = ("tap", "swipe", "long_press", "scroll", "back")
_MAX_REPEAT_STEPS = 4
_DIRECTIONS = ("up", "down", "left", "right", "top", "bottom")
_MAX_APP_NAME = 100
_COMMON_ACTION_FIELDS = ("action", "snapshot_version", "expect", "timeout_ms")
_ALLOWED_ACTIONS = frozenset(_ACTION_FIELDS)
_EXPECT_SCHEMA = {
    "type": "object",
    "properties": {
        name: {
            "type": "string",
            "minLength": 1,
            "maxLength": _MAX_EXPECT,
            "pattern": _STRING_PATTERN,
        }
        for name in (
            "package_name",
            "activity_name",
            "text_contains",
            "view_id_exists",
            "resource_id",
        )
    },
    "minProperties": 1,
    "maxProperties": 5,
    "additionalProperties": False,
}


def _java_bridge() -> Any:
    try:
        from java import jclass  # type: ignore[import-not-found]

        return jclass("com.agentworkspace.mobile.automation.AndroidSystemBridge")
    except Exception as exc:  # pragma: no cover - JVM-only path
        raise ToolError("Android system bridge is unavailable") from exc


def _bridge_or_default(bridge: Any | None) -> Any:
    return bridge if bridge is not None else _java_bridge()


def background_screen(change: dict[str, Any] | None = None, bridge: Any | None = None) -> dict[str, Any]:
    """Device & tools → Background operation: its status, after an optional change
    ({"enabled": bool}, or {"action": "request_permission" | "open" | "bring_to_front"})."""
    target = _bridge_or_default(bridge)
    result: dict[str, Any] = {}
    if change and "enabled" in change:
        if not isinstance(change["enabled"], bool):
            raise ToolArgumentError("enabled must be true or false")
        target.setBackground(change["enabled"])
    elif change and change.get("action") == "request_permission":
        target.requestBackgroundPermission()
    elif change and change.get("action") == "open":
        opened = json.loads(str(target.openBackground()))
        if opened.get("error"):
            result["error"] = str(opened["error"])[:300]
    elif change and change.get("action") == "bring_to_front":
        moved = json.loads(str(target.bringBackgroundToFront()))
        result["moved"] = moved.get("ok") is True
        if moved.get("error"):
            result["error"] = str(moved["error"])[:300]
    elif change:
        raise ToolArgumentError("expected enabled, or action request_permission, open or bring_to_front")
    status = json.loads(str(target.backgroundStatus()))
    return {**(status if isinstance(status, dict) else {}), **result}


def background_picture(max_edge: int = 720, bridge: Any | None = None) -> bytes | None:
    """The background screen's newest picture (JPEG), or None when nothing is open there."""
    data = _bridge_or_default(bridge).backgroundPicture(max(200, min(1600, int(max_edge))))
    return bytes(data) if data is not None else None


def _status(bridge: Any | None = None) -> dict[str, Any]:
    target = _bridge_or_default(bridge)
    try:
        value = json.loads(str(target.status()))
    except Exception as exc:
        raise ToolError("Android system bridge status is unavailable") from exc
    if not isinstance(value, dict):
        raise ToolError("Android system bridge returned invalid status")
    return value


def get_android_system_status(bridge: Any | None = None) -> dict[str, Any]:
    """Return a sanitized, JSON-compatible capability status."""

    try:
        value = _status(bridge)
    except ToolError as exc:
        return {
            "available": False,
            "enabled": False,
            "connected": False,
            "reason": str(exc),
            "screenshot_supported": False,
        }
    allowed = {
        "available",
        "enabled",
        "switched_on",
        "can_repair",
        "connected",
        "local_connection",
        "paused",
        "takeover_requested",
        "screenshot_supported",
        "live_screen_active",
        "api_level",
        "reason",
        "settings_action",
        "service_component",
        "memory_total_bytes",
        "memory_available_bytes",
        "memory_usable_bytes",
        "abis",
        "device",
        "app_version",
    }
    result = {key: value[key] for key in allowed if key in value}
    result.setdefault("available", False)
    result.setdefault("enabled", False)
    result.setdefault("connected", False)
    result.setdefault("screenshot_supported", False)
    return result


def is_android_system_available(bridge: Any | None = None) -> bool:
    status = get_android_system_status(bridge)
    return bool(status.get("available") and status.get("enabled") and status.get("connected"))


def _require_available(bridge: Any | None) -> None:
    status = get_android_system_status(bridge)
    if not status.get("available"):
        raise ToolError("Android system bridge is unavailable; restart the Agent Workspace engine")
    if not status.get("enabled") or not status.get("connected"):
        action = status.get("settings_action", "android.settings.ACCESSIBILITY_SETTINGS")
        raise ToolError(
            "Android accessibility is disabled; enable Agent Workspace in Accessibility settings "
            f"({action}) and retry"
        )


def _background_allowed() -> bool:
    try:
        from mobile_screen import allowed
    except ImportError:  # outside the app
        return False
    return allowed()


def _invoke(bridge: Any | None, request: dict[str, Any]) -> dict[str, Any]:
    _require_available(bridge)
    if _background_allowed():
        # A conversation task: the phone uses the background screen when the user turned it on.
        request = {**request, "background": True}
    try:
        raw = _bridge_or_default(bridge).execute(
            json.dumps(request, ensure_ascii=False, separators=(",", ":"))
        )
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError("Android system bridge request failed") from exc
    if len(str(raw)) > 2 * 1024 * 1024:
        raise ToolError("Android system bridge response exceeds the size limit")
    try:
        response = json.loads(str(raw))
    except (ValueError, TypeError) as exc:
        raise ToolError("Android system bridge returned invalid JSON") from exc
    if not isinstance(response, dict):
        raise ToolError("Android system bridge returned invalid JSON")
    return _sanitize_response(response)


def _sanitize_response(value: dict[str, Any]) -> dict[str, Any]:
    """Drop accidental secret text from password nodes and bound model output."""

    def clean(item: Any, depth: int = 0, inherited: bool = False) -> Any:
        if depth > _MAX_DEPTH:
            return "[truncated]"
        if isinstance(item, dict):
            result: dict[str, Any] = {}
            sensitive = bool(
                inherited
                or item.get("password")
                or item.get("is_password")
                or item.get("sensitive")
            )
            for key, nested in item.items():
                if key in {"raw_text", "raw_description"}:
                    continue
                if sensitive and key in {
                    "text",
                    "content_description",
                    "description",
                    "hint",
                    "value",
                }:
                    result[key] = "[redacted]"
                else:
                    result[key] = clean(nested, depth + 1, sensitive)
            return result
        if isinstance(item, list):
            return [clean(entry, depth + 1, inherited) for entry in item[:_MAX_NODES]]
        if isinstance(item, str):
            return item[:_MAX_TEXT]
        return item

    return cast(dict[str, Any], clean(value))


_WINDOW_TYPES = {1: "app", 2: "keyboard", 3: "system", 4: "overlay", 5: "divider", 6: "magnifier"}
_MAX_LINE_TEXT = 200
# What the model reads of a screen, explained once in the tool descriptions instead of per line.
_UI_FORMAT = (
    "Its observation lists the screen as ui lines: `ref Class [left,top,right,bottom] flags "
    '"text" desc="..." hint="..." id=...`, indented under their container, grouped by window. '
    "Flags: click, long (takes a long press), edit, scroll (a list: scroll it by ref), checked or "
    "unchecked (a switch or box), selected, focused, disabled, offscreen (a ref action scrolls it "
    "into view), protected (never read or touched). Layout-only containers are left out. "
    "keyboard_shown and notification_shade_open say what covers the app (back closes either); "
    "locked means the phone is locked: stop and ask the user to unlock it. background_screen means "
    "you work on a screen the user does not see while they use the phone: open apps with "
    "launch_app (it has no home screen), act by ref, and when an app should be handed to the "
    "user, say so in your reply (they can bring it to the phone's screen)."
)


def _quoted(value: Any) -> str:
    text = " ".join(str(value).split())
    if len(text) > _MAX_LINE_TEXT:
        text = text[:_MAX_LINE_TEXT] + "…"
    return json.dumps(text, ensure_ascii=False)


def _box(bounds: Any) -> tuple[int, int, int, int]:
    bounds = bounds if isinstance(bounds, dict) else {}
    return tuple(int(bounds.get(side) or 0) for side in ("left", "top", "right", "bottom"))  # type: ignore[return-value]


def _area(bounds: Any) -> int:
    left, top, right, bottom = _box(bounds)
    return max(0, right - left) * max(0, bottom - top)


def _set_aside(observation: dict[str, Any]) -> tuple[set[Any], list[str]]:
    """Windows left out of the ui lines: the status and navigation bars (time and battery, read
    with every step for nothing), and other apps' small floating windows, as one line each."""
    screen = observation.get("screen") if isinstance(observation.get("screen"), dict) else {}
    width, height = int(screen.get("width") or 0), int(screen.get("height") or 0)
    skipped: set[Any] = set()
    summaries: list[str] = []
    for window in observation.get("windows") or []:
        if not isinstance(window, dict):
            continue
        left, top, right, bottom = _box(window.get("bounds"))
        if (
            window.get("type") == 3
            and window.get("package_name") == "com.android.systemui"
            and height
            and bottom - top < height * 0.15
        ):
            skipped.add(window.get("id"))
        elif (
            window.get("type") in (1, 4)
            and not window.get("active")
            and width
            and height
            and _area(window.get("bounds")) < width * height * 0.06
        ):
            skipped.add(window.get("id"))
            summaries.append(
                f"window {window.get('id')} floating {window.get('package_name') or 'window'} "
                f"[{left},{top},{right},{bottom}] (small; it covers taps there)"
            )
    return skipped, summaries


def _ui_lines(observation: dict[str, Any]) -> list[str]:
    """The nodes as one short line each, keeping the controls a person could read or touch."""
    skipped, summaries = _set_aside(observation)
    nodes = [
        node
        for node in observation.get("nodes") or []
        if isinstance(node, dict) and node.get("window_id") not in skipped
    ]
    parents = {node.get("ref"): node.get("parent_ref") for node in nodes}

    def protected(node: dict[str, Any]) -> bool:
        return bool(node.get("password") or node.get("sensitive"))

    def kept(node: dict[str, Any]) -> bool:
        labelled = bool(node.get("text") or node.get("description") or node.get("hint"))
        if node.get("visible") is False:
            return labelled
        return labelled or protected(node) or any(
            node.get(flag) for flag in ("clickable", "editable", "focused", "scrollable", "long_clickable")
        )

    keep = {node.get("ref") for node in nodes if kept(node)}
    windows = {
        window.get("id"): window
        for window in observation.get("windows") or []
        if isinstance(window, dict)
    }
    lines: list[str] = []
    current_window: Any = object()
    for node in nodes:
        ref = node.get("ref")
        if ref not in keep:
            continue
        if node.get("window_id") != current_window and node.get("window_id") is not None:
            current_window = node.get("window_id")
            window = windows.get(current_window, {})
            header = f"window {current_window} {_WINDOW_TYPES.get(window.get('type'), 'window')}"
            if window.get("package_name"):
                header += f" {window['package_name']}"
            if window.get("title"):
                header += f" {_quoted(window['title'])}"
            if window.get("active"):
                header += " active"
            lines.append(header)
        depth, parent, seen = 0, parents.get(ref), set()
        while parent and parent not in seen:
            seen.add(parent)
            depth += parent in keep
            parent = parents.get(parent)
        bounds = node.get("bounds") or {}
        line = (
            f"{'  ' * (depth + 1)}{ref} {str(node.get('class_name') or 'View').rsplit('.', 1)[-1]} "
            f"[{bounds.get('left')},{bounds.get('top')},{bounds.get('right')},{bounds.get('bottom')}]"
        )
        flags = [
            name
            for name, on in (
                ("click", node.get("clickable")),
                ("long", node.get("long_clickable")),
                ("edit", node.get("editable")),
                ("scroll", node.get("scrollable")),
                ("checked", node.get("checked") is True),
                ("unchecked", node.get("checked") is False),
                ("selected", node.get("selected")),
                ("focused", node.get("focused")),
                ("disabled", node.get("enabled") is False),
                ("offscreen", node.get("visible") is False),
                ("protected", protected(node)),
            )
            if on
        ]
        if flags:
            line += " " + " ".join(flags)
        text, description = node.get("text"), node.get("description")
        if text:
            line += f" {_quoted(text)}"
        if description and description != text:
            line += f" desc={_quoted(description)}"
        if node.get("hint") and node.get("hint") not in (text, description):
            line += f" hint={_quoted(node['hint'])}"
        if node.get("view_id"):
            line += f" id={str(node['view_id']).rsplit('/', 1)[-1]}"
        lines.append(line)
    return lines + summaries


def _plain(text: Any) -> str:
    return "".join(str(text or "").split()).lower()


def _label(node: dict[str, Any]) -> str:
    return str(node.get("text") or node.get("description") or node.get("hint") or "")


# Buttons that put a dialog or an ad away without agreeing to anything.
_DISMISS = frozenset(
    _plain(word)
    for word in (
        "跳过", "关闭", "取消", "以后再说", "稍后", "稍后再说", "下次再说", "暂不", "暂不需要", "暂不开启",
        "不再提示", "我知道了", "知道了", "不了", "不用了", "残忍拒绝", "拒绝", "忽略", "skip", "close",
        "cancel", "not now", "later", "no thanks", "no, thanks", "dismiss", "×", "✕", "╳",
    )
)
# A splash ad's skip control: "跳过 3", "3s 跳过", "跳过广告", "Skip 5" (spaces removed, lower case).
_SKIP = re.compile(r"^(\d{1,2}s?[|/·]?)?(跳过|skip)(广告|ad)?([|/·]?\d{1,2}s?)?$")
# The close control of an ad or a pop-up layer drawn over the page, often an icon with no words.
_CLOSE = frozenset(_plain(word) for word in ("关闭", "关闭广告", "关闭弹窗", "close", "close ad", "×", "✕", "╳", "x"))
_CLOSE_ID = re.compile(r"close|dismiss|skip")
# What marks a control or a screen as an ad or a pop-up layer.
_AD_ID = re.compile(
    r"(?<![a-z])ads?(?![a-z])|splash|pop|dialog|layer|interstitial|float|mask|banner|hongbao|redpacket|coupon|promo"
)
_AD_MARK = frozenset(_plain(word) for word in ("广告", "ad", "ads", "赞助", "sponsored", "推广"))
_PERMISSION_PACKAGES = frozenset(
    {
        "com.android.permissioncontroller",
        "com.google.android.permissioncontroller",
        "com.android.packageinstaller",
        "com.lbe.security.miui",
    }
)


def _blocking(observation: dict[str, Any]) -> dict[str, Any] | None:
    """A dialog, a permission request or an ad in front of the app, with the buttons that answer
    it, so it is dealt with in one step instead of being discovered by trial."""
    screen = observation.get("screen") if isinstance(observation.get("screen"), dict) else {}
    full = int(screen.get("width") or 0) * int(screen.get("height") or 0)
    nodes = [
        node
        for node in observation.get("nodes") or []
        if isinstance(node, dict) and node.get("visible") is not False and not node.get("sensitive")
    ]
    for window in observation.get("windows") or []:
        if not isinstance(window, dict):
            continue
        package = window.get("package_name")
        permission = package in _PERMISSION_PACKAGES
        dialog = (
            window.get("type") == 1
            and full
            and full * 0.04 < _area(window.get("bounds")) < full * 0.8
        )
        if not (permission or dialog):
            continue
        inside = [node for node in nodes if node.get("window_id") == window.get("id")]
        # An ad dialog's close is often an icon known only by its id.
        buttons = [node for node in inside if node.get("clickable") and (_label(node) or _close_id(node))]
        if not buttons:
            continue
        dismiss = [node for node in buttons if _plain(_label(node)) in _DISMISS or (not _label(node) and _close_id(node))]
        says = [_label(node) for node in inside if not node.get("clickable") and _label(node)][:3]
        found: dict[str, Any] = {
            "kind": "permission" if permission else "dialog",
            "says": [" ".join(text.split())[:120] for text in says],
            "buttons": [_named(node) for node in buttons[:5]],
        }
        if dismiss and not permission:
            found["dismiss"] = _named(dismiss[0])
        return found
    return _splash_ad(nodes, full) or _ad_layer(nodes, full)


def _short_id(node: dict[str, Any]) -> str:
    return str(node.get("view_id") or "").rsplit("/", 1)[-1].lower()


def _close_id(node: dict[str, Any]) -> bool:
    return bool(_CLOSE_ID.search(_short_id(node)))


def _named(node: dict[str, Any], label: str | None = None) -> str:
    """A control as `n12 "跳过"`, or `n12 id=iv_close` for an icon without words."""
    words = label if label is not None else _label(node)
    return f"{node.get('ref')} {_quoted(words)}" if words else f"{node.get('ref')} id={_short_id(node)}"


def _tappable(node: dict[str, Any], nodes: list[dict[str, Any]], full: int) -> dict[str, Any] | None:
    """The control itself, or the small frame around it that takes the tap (a "跳过" label inside a
    tappable box). None when only something big takes it: tapping that may open the ad."""
    by_ref = {item.get("ref"): item for item in nodes}
    current, seen = node, set()
    while current is not None and current.get("ref") not in seen:
        seen.add(current.get("ref"))
        if current.get("clickable"):
            return current if not full or _area(current.get("bounds")) <= full * 0.08 else None
        current = by_ref.get(current.get("parent_ref"))
    return None


def _splash_ad(nodes: list[dict[str, Any]], full: int) -> dict[str, Any] | None:
    """A splash ad over the whole app: its skip control ("跳过 3"), by its words or its id."""
    for node in nodes:
        label = _plain(_label(node))
        if not (_SKIP.match(label) or (not label and "skip" in _short_id(node))):
            continue
        target = _tappable(node, nodes, full)
        if target is not None:
            return {"kind": "ad", "dismiss": _named(target, _label(node))}
    return None


def _ad_layer(nodes: list[dict[str, Any]], full: int) -> dict[str, Any] | None:
    """An ad or a pop-up layer (a red packet, a coupon) drawn over the page: its small close control,
    when the control or the screen says it belongs to an ad or a pop-up. A page's own close button
    is left alone."""
    marked = any(_plain(_label(node)) in _AD_MARK for node in nodes)
    for node in nodes:
        label = _plain(_label(node))
        if not (label in _CLOSE or (not label and _close_id(node))):
            continue
        if not (marked or label in {"关闭广告", "关闭弹窗", "closead"} or _AD_ID.search(_short_id(node))):
            continue
        target = _tappable(node, nodes, full)
        if target is not None and (not full or _area(target.get("bounds")) <= full * 0.03):
            return {"kind": "ad", "dismiss": _named(target, _label(node))}
    return None


def _picture_hint(observation: dict[str, Any]) -> str | None:
    """Says so when the app in front shows little as text (pictures, a game, a web canvas)."""
    windows = [
        window
        for window in observation.get("windows") or []
        if isinstance(window, dict) and window.get("type") == 1 and window.get("active")
    ]
    if not windows:
        return None
    front = windows[0]
    inside = [
        node
        for node in observation.get("nodes") or []
        if isinstance(node, dict) and node.get("window_id") == front.get("id") and node.get("visible") is not False
    ]
    labelled = sum(1 for node in inside if _label(node))
    canvas = any(
        str(node.get("class_name") or "").rsplit(".", 1)[-1] in ("WebView", "SurfaceView", "TextureView", "GLSurfaceView")
        and _area(node.get("bounds")) > _area(front.get("bounds")) * 0.4
        and not node.get("child_count")
        for node in inside
    )
    if labelled >= 6 and not canvas:
        return None
    return (
        "Little of this screen is text: android_observe with screen_text reads the words drawn in "
        "it; android_screenshot shows the picture."
    )


def _screen_text(response: dict[str, Any], observation: dict[str, Any]) -> list[str]:
    """Words read off the screenshot that no control reports, as `[l,t,r,b] "words"`."""
    read = response.get("screen_text")
    if not isinstance(read, list):
        return []
    known = [_plain(_label(node)) for node in observation.get("nodes") or [] if isinstance(node, dict)]
    lines = []
    for item in read:
        if not isinstance(item, dict) or not item.get("text"):
            continue
        words = _plain(item["text"])
        if any(words and words in label for label in known if label):
            continue
        left, top, right, bottom = _box(item.get("bounds"))
        lines.append(f"[{left},{top},{right},{bottom}] {_quoted(item['text'])}")
    return lines[:80]


class _Screens:
    """What each conversation last read of the screen, so an action's result can list only what
    changed (refs stay the same while the same windows show), and actions that change nothing,
    time after time, are pointed out."""

    def __init__(self) -> None:
        self._state: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any]:
        state = self._state.pop(key, None) or {"identity": None, "lines": {}, "still": 0, "last": None, "same": 0}
        self._state[key] = state
        while len(self._state) > 32:
            self._state.pop(next(iter(self._state)))
        return state


_SCREENS = _Screens()


async def _wait_if_paused() -> None:
    """The user paused the task (phone control window): no new look or action until they go on."""
    try:
        from mobile_pause import wait_if_paused
    except ImportError:  # pragma: no cover - the engine always has it
        return
    await wait_if_paused()


def _going_in_circles(session: str, arguments: dict[str, Any], response: dict[str, Any]) -> str | None:
    """After the third action in a row that changed nothing on the screen, or the same action three
    times running: a word to try something else instead of spending more steps the same way."""
    state = _SCREENS.get(session)
    signature = json.dumps(
        {key: value for key, value in arguments.items() if key != "snapshot_version"}, sort_keys=True
    )
    state["same"] = state["same"] + 1 if state["last"] == signature else 1
    state["last"] = signature
    executed = response.get("executed") is True
    state["idle"] = state.get("idle", 0) + 1 if executed and state["still"] > 0 else 0
    if state["idle"] >= 3:
        return (
            f"The last {state['idle']} actions changed nothing on the screen. Do not repeat them: "
            "try another control (tap_text, scroll_to_text, back), a screenshot to see what is "
            "really shown, or ask the user."
        )
    # Paging through a list the same way is normal; tapping the same thing over and over is not.
    if state["same"] >= 3 and arguments.get("action") not in ("scroll", "swipe", "scroll_to_text"):
        return (
            "This is the same action for the third time in a row. If it is not getting closer to "
            "the goal, try another way or ask the user."
        )
    return None
_REF_IN_LINE = re.compile(r"^\s*(n\d+) ")
# A ui line's flags, then its words and its description (see _ui_lines).
_LINE_WORDS = re.compile(
    r'^\S+ \S+ \[[^\]]*\]((?: [a-z]+(?= |$))*)(?: ("(?:[^"\\]|\\.)*"))?(?: desc=("(?:[^"\\]|\\.)*"))?'
)


def _tapped_label(arguments: dict[str, Any], state: dict[str, Any]) -> str | None:
    """The words of the control a tap is aimed at, as the screen showed them before it (never a
    field being typed into or a protected one)."""
    if arguments.get("action") == "tap_text":
        return arguments.get("text") if isinstance(arguments.get("text"), str) else None
    if arguments.get("action") != "ref" or not isinstance(arguments.get("ref"), str):
        return None
    match = _LINE_WORDS.match(state.get("lines", {}).get(arguments["ref"]) or "")
    if not match or {"edit", "protected"} & set(match.group(1).split()):
        return None
    words = match.group(2) or match.group(3)
    return json.loads(words) if words else None


def _record_tap(package: str, label: str, changed: bool, before: Any, after: Any) -> None:
    try:
        from mobile_app_notes import record_tap
    except ImportError:  # outside the app
        return
    record_tap(package, label, changed=changed, before=before, after=after)


def _app_notes(session: str, observation: dict[str, Any]) -> str | None:
    """What earlier tasks learned about the app in front, once per conversation and app."""
    package = observation.get("package_name")
    if not isinstance(package, str) or not package or package in _NOT_LEFT_FOR:
        return None
    shown = _SCREENS.get(session).setdefault("noted", set())
    if package in shown:
        return None
    shown.add(package)
    try:
        from mobile_app_notes import notes_for
    except ImportError:  # outside the app
        return None
    return notes_for(package)


_CHANGES_NOTE = (
    "Only ui_changes (new or different lines) and ui_gone (refs no longer shown) are listed; "
    "every other line, and its ref, is as in the previous result."
)


# Actions that touch something on the screen; one that lands in another app may have hit an ad.
_TOUCHES = frozenset({"ref", "tap", "tap_text", "long_press", "batch", "scroll_to_text"})
# Apps whose windows show up on their own over others (this app's panel, keyboards, installers).
_NOT_LEFT_FOR = frozenset({"com.agentworkspace.mobile", "android", "com.android.systemui"}) | _PERMISSION_PACKAGES


def _phone_state(observation: dict[str, Any]) -> dict[str, bool]:
    """What covers the app, said outright: the keyboard (it hides what is under it, and back closes
    it first) and the pulled-down notification shade (taps land in it, not in the app)."""
    screen = observation.get("screen") if isinstance(observation.get("screen"), dict) else {}
    height = int(screen.get("height") or 0)
    state: dict[str, bool] = {}
    for window in observation.get("windows") or []:
        if not isinstance(window, dict):
            continue
        if window.get("type") == 2:
            state["keyboard_shown"] = True
        _, top, _, bottom = _box(window.get("bounds"))
        if (
            window.get("type") == 3
            and window.get("package_name") == "com.android.systemui"
            and height
            and bottom - top > height * 0.5
            and (window.get("active") or window.get("focused"))
            and not observation.get("locked")
        ):
            state["notification_shade_open"] = True
    return state


def _for_model(
    response: dict[str, Any], memory_key: str | None = None, changes_only: bool = False,
    action: str | None = None,
) -> dict[str, Any]:
    """A bridge response as the model reads it: the screen as short lines instead of every field of
    every node (about a tenth of the size, and each later request carries it again). After an
    action on the same screen, only what changed."""
    observation = response.get("observation")
    if not isinstance(observation, dict) or not isinstance(observation.get("nodes"), list):
        return response
    compact = {
        key: observation[key]
        for key in ("package_name", "activity_name", "snapshot_version", "screen", "stable")
        if key in observation
    }
    for flag in ("truncated", "content_changing", "sensitive_content_redacted", "locked", "background_screen"):
        if observation.get(flag):
            compact[flag] = True
    compact.update(_phone_state(observation))
    lines = _ui_lines(observation)
    identity = (observation.get("ref_epoch"), observation.get("package_name"))
    by_ref = {match.group(1): line.strip() for line in lines if (match := _REF_IN_LINE.match(line))}
    state = _SCREENS.get(memory_key) if memory_key else None
    previous = state["lines"] if state and state["identity"] == identity and identity[0] is not None else None
    was = state["identity"][1] if state and state["identity"] else None
    now = observation.get("package_name")
    if action in _TOUCHES and was and now and was != now and not {was, now} & _NOT_LEFT_FOR:
        compact["left_app"] = (
            f"This tap took the phone from {was} to {now}. If that was not the goal (an ad or a "
            "link opened it), go back (back, or launch_app the app you were in) and do not "
            "download, install or allow anything there."
        )
    if changes_only and previous is not None:
        changed: list[str] = []
        header = None
        for line in lines:
            match = _REF_IN_LINE.match(line)
            if not match:
                header = line
                continue
            if previous.get(match.group(1)) != line.strip():
                if header is not None:
                    changed.append(header)
                    header = None
                changed.append(line)
        gone = [ref for ref in previous if ref not in by_ref]
        if len(changed) + len(gone) <= max(12, len(by_ref) // 2):
            compact["ui_changes"] = changed
            if gone:
                compact["ui_gone"] = gone[:80]
            compact["ui_unchanged"] = len(by_ref) - sum(1 for line in changed if _REF_IN_LINE.match(line))
            compact["note"] = _CHANGES_NOTE
        else:
            compact["ui"] = lines
    else:
        compact["ui"] = lines
    if state is not None:
        # Whether the action left the screen as it was: a tap that did nothing is seen at once.
        if changes_only and response.get("executed") is True and state["identity"] is not None:
            compact["screen_changed"] = previous is None or previous != by_ref
        state["still"] = state["still"] + 1 if previous is not None and previous == by_ref else 0
        state["identity"], state["lines"] = identity, by_ref
        state["activity"] = observation.get("activity_name")
    text = _screen_text(response, observation)
    if text:
        compact["text_on_screen"] = text
    blocking = _blocking(observation)
    if blocking:
        compact["blocking"] = blocking
    hint = _picture_hint(observation)
    if hint and not text:
        compact["hint"] = hint
    result = {**response, "observation": compact}
    result.pop("screen_text", None)
    return result


def _string(arguments: dict[str, Any], key: str, *, maximum: int = _MAX_TEXT) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value or len(value) > maximum or "\0" in value:
        raise ToolArgumentError(
            f"{key!r} must be a non-empty string of at most {maximum} characters without NUL"
        )
    return value


def _int(arguments: dict[str, Any], key: str, *, minimum: int, maximum: int) -> int:
    value = arguments.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ToolArgumentError(f"{key!r} must be an integer from {minimum} to {maximum}")
    return value


def _version(arguments: dict[str, Any]) -> str:
    return _string(arguments, "snapshot_version", maximum=128)


def _ref(arguments: dict[str, Any]) -> str:
    value = _string(arguments, "ref", maximum=_MAX_REF)
    if not _REF_RE.fullmatch(value):
        raise ToolArgumentError("'ref' contains unsupported characters")
    return value


class _BridgeTool:
    bridge: Any | None

    def __init__(self, bridge: Any | None = None) -> None:
        self.bridge = bridge

    @property
    def spec(self) -> ToolSpec:
        raise NotImplementedError

    async def execute(self, arguments: dict[str, Any]) -> str:
        return json_result(_for_model(await asyncio.to_thread(self._run, arguments)))

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        await _wait_if_paused()
        # Looking at the screen gives it whole, and is what later actions report changes against.
        response = await asyncio.to_thread(self._run, arguments)
        result = _for_model(response, memory_key=context.session_id)
        observation = result.get("observation")
        notes = _app_notes(context.session_id, observation if isinstance(observation, dict) else {})
        if notes:
            result["app_notes"] = notes
        return json_result(result)

    def _run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class AndroidObserveTool(_BridgeTool):
    _SPEC = ToolSpec(
        name="android_observe",
        description=(
            "Observe the current Android app, window, bounded accessibility UI tree, and screen. "
            + _UI_FORMAT
        ),
        input_schema={
            "type": "object",
            "properties": {
                "max_nodes": {"type": "integer", "minimum": 1, "maximum": _MAX_NODES},
                "max_depth": {"type": "integer", "minimum": 1, "maximum": _MAX_DEPTH},
                "wait_ms": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 5000,
                    "description": "Wait up to this long for the screen to stop changing (a page "
                    "still loading after an app opened) before reading it.",
                },
                "until_text": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": _MAX_LABEL,
                    "pattern": _STRING_PATTERN,
                    "description": "Wait until these words show (a download finished, a code "
                    "arrived), then read the screen; met says whether they did.",
                },
                "until_gone": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": _MAX_LABEL,
                    "pattern": _STRING_PATTERN,
                    "description": "Wait until these words are gone (加载中, Loading).",
                },
                "max_wait_ms": {
                    "type": "integer",
                    "minimum": 500,
                    "maximum": 120000,
                    "description": "How long until_text or until_gone waits (default 15000).",
                },
                "screen_text": {
                    "type": "boolean",
                    "description": "Also read the words drawn in the screen's picture (badges, "
                    "images, games, web canvases) offline; they come as text_on_screen with bounds.",
                },
            },
            "additionalProperties": False,
        },
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def _run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        validate_tool_arguments(self.spec, arguments)
        if "until_text" in arguments or "until_gone" in arguments:
            # The phone watches the screen; the model is not woken for every look.
            request: dict[str, Any] = {"action": "wait_for"}
            if "until_text" in arguments:
                request["text"] = _string(arguments, "until_text", maximum=_MAX_LABEL)
            if "until_gone" in arguments:
                request["gone_text"] = _string(arguments, "until_gone", maximum=_MAX_LABEL)
            if "max_wait_ms" in arguments:
                request["max_wait_ms"] = _int(arguments, "max_wait_ms", minimum=500, maximum=120_000)
            waited = _invoke(self.bridge, request)
            if arguments.get("screen_text") is not True:
                return waited
        if arguments.get("screen_text") is True:
            return _invoke(self.bridge, {"action": "ocr"})
        max_nodes = arguments.get("max_nodes", _MAX_NODES)
        max_depth = arguments.get("max_depth", _MAX_DEPTH)
        if (
            not isinstance(max_nodes, int)
            or isinstance(max_nodes, bool)
            or not 1 <= max_nodes <= _MAX_NODES
        ):
            raise ToolArgumentError("'max_nodes' must be an integer from 1 to 400")
        if (
            not isinstance(max_depth, int)
            or isinstance(max_depth, bool)
            or not 1 <= max_depth <= _MAX_DEPTH
        ):
            raise ToolArgumentError("'max_depth' must be an integer from 1 to 24")
        request = {"action": "observe", "max_nodes": max_nodes, "max_depth": max_depth}
        if "wait_ms" in arguments:
            request["wait_ms"] = _int(arguments, "wait_ms", minimum=0, maximum=5000)
        observed = _invoke(self.bridge, request)
        # A screen of pictures says little as controls: read its words too, unless told not to.
        observation = observed.get("observation")
        if (
            arguments.get("screen_text") is not False
            and isinstance(observation, dict)
            and _picture_hint(observation)
        ):
            try:
                read = _invoke(self.bridge, {"action": "ocr"})
            except ToolError:
                return observed
            if read.get("ok") and isinstance(read.get("screen_text"), list):
                return read
        return observed


class AndroidScreenshotTool(_BridgeTool):
    _SPEC = ToolSpec(
        name="android_screenshot",
        description=(
            "Capture the Android display into the private workspace and attach the image, with "
            "an observation of the same screen (ui lines as in android_observe). Its "
            "snapshot_version works for android_action; screen coordinates are image pixels "
            "times pixel_to_screen_x/y. The numbers drawn on the picture are refs of controls you "
            "can act on (12 is n12): act on them by ref. marks=false gives a clean picture."
        ),
        input_schema={
            "type": "object",
            "properties": {"marks": {"type": "boolean"}},
            "additionalProperties": False,
        },
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def _run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._capture(arguments)[0]

    def _capture(self, arguments: dict[str, Any]) -> tuple[dict[str, Any], bytes | None]:
        validate_tool_arguments(self.spec, arguments)
        marks = arguments.get("marks", True)
        if not isinstance(marks, bool):
            raise ToolArgumentError("'marks' must be true or false")
        response = _invoke(self.bridge, {"action": "screenshot", "marks": marks})
        screenshot = response.get("screenshot")
        if not isinstance(screenshot, dict):
            return response, None
        path_value = screenshot.get("absolute_path")
        if not isinstance(path_value, str):
            raise ToolError("Android screenshot did not include a private path")
        path = Path(path_value).resolve()
        workspace = Path(os.environ.get("AGENT_WORKSPACE_ANDROID_WORKSPACE", Path.cwd())).resolve()
        capture_root = (workspace / "automation" / "screenshots").resolve()
        try:
            path.relative_to(capture_root)
        except ValueError as exc:
            raise ToolError(
                "Android screenshot path is outside the private capture directory"
            ) from exc
        try:
            if path.stat().st_size > _MAX_SCREENSHOT_BYTES:
                raise ToolError("Android screenshot exceeds the size limit")
            data = path.read_bytes()
        except OSError as exc:
            raise ToolError("Android screenshot could not be read") from exc
        if not data or len(data) > _MAX_SCREENSHOT_BYTES:
            raise ToolError("Android screenshot is empty or exceeds the size limit")
        media_type = screenshot.get("media_type", "image/png")
        if not (
            (media_type == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n"))
            or (media_type == "image/jpeg" and data.startswith(b"\xff\xd8\xff"))
        ):
            raise ToolError("Android screenshot has an unsupported media type")
        screenshot = dict(screenshot)
        screenshot.pop("absolute_path", None)
        screenshot["sha256"] = hashlib.sha256(data).hexdigest()
        screenshot["bytes"] = len(data)
        response["screenshot"] = screenshot
        return response, data

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        response, data = await asyncio.to_thread(self._capture, arguments)
        screenshot = response.get("screenshot")
        if isinstance(screenshot, dict) and data is not None:
            if context.record_artifact is None:
                raise ToolError("Android screenshots require artifact recording support")
            digest = hashlib.sha256(data).hexdigest()
            await context.record_artifact(BinaryArtifact(digest, data))
            await context.record_event(
                Event(
                    session_id=context.session_id,
                    type="image.attached",
                    data={
                        "attempt_id": context.attempt_id,
                        "path": screenshot.get("path", ""),
                        "media_type": screenshot.get("media_type", "image/png"),
                        "sha256": digest,
                        "bytes": len(data),
                    },
                    causation_id=context.started_event_id,
                    correlation_id=context.correlation_id,
                )
            )
            screenshot = dict(screenshot)
            screenshot["sha256"] = digest
            screenshot["bytes"] = len(data)
            response["screenshot"] = screenshot
        return json_result(_for_model(response, memory_key=context.session_id))


_FIELD_SCHEMAS: dict[str, dict[str, Any]] = {
    "ref": {
        "type": "string",
        "minLength": 1,
        "maxLength": _MAX_REF,
        "pattern": _REF_RE.pattern,
        "description": "Copy the exact node ref (such as n1) from android_observe.",
    },
    "x": {"type": "integer", "minimum": 0, "maximum": 10000},
    "y": {"type": "integer", "minimum": 0, "maximum": 10000},
    "x2": {"type": "integer", "minimum": 0, "maximum": 10000},
    "y2": {"type": "integer", "minimum": 0, "maximum": 10000},
    "text": {
        "type": "string",
        "minLength": 1,
        "maxLength": _MAX_TEXT,
        "pattern": _STRING_PATTERN,
    },
    "direction": {
        "type": "string",
        "enum": list(_DIRECTIONS),
        "description": (
            "down shows what is further down (as a finger swiping up would); top and bottom go "
            "all the way."
        ),
    },
    "package_name": {
        "type": "string",
        "minLength": 1,
        "maxLength": 255,
        "pattern": _PACKAGE_RE.pattern,
    },
    "app_name": {
        "type": "string",
        "minLength": 1,
        "maxLength": _MAX_APP_NAME,
        "pattern": _STRING_PATTERN,
        "description": "The app's name under its icon, such as Calculator or 微信.",
    },
    "every_ms": {
        "type": "integer",
        "minimum": 300,
        "maximum": 3_600_000,
        "description": "repeat: milliseconds from the start of one round to the start of the next.",
    },
    "times": {
        "type": "integer",
        "minimum": 1,
        "maximum": 10_000,
        "description": "repeat: how many rounds; leave out to run until stopped (4 hours at most).",
    },
    "nth": {
        "type": "integer",
        "minimum": 1,
        "maximum": 50,
        "description": "tap_text: which of several controls showing the text (1 is the first listed).",
    },
    "max_scrolls": {"type": "integer", "minimum": 1, "maximum": 40},
    "tap": {"type": "boolean", "description": "scroll_to_text: tap it once found."},
    "confirmed": {
        "type": "boolean",
        "description": "Only after the user said yes in this conversation to pressing a control that "
        "deletes, clears, uninstalls or stops an app (a result's needs_confirmation names it). It never "
        "unlocks paying: payments are always the user's.",
    },
    "page": {"type": "string", "enum": list(_PAGES)},
    "url": {
        "type": "string",
        "minLength": 1,
        "maxLength": 2000,
        "pattern": r"^https?://[^\u0000\s]+(?![\s\S])",
    },
    "query": {"type": "string", "minLength": 1, "maxLength": 300, "pattern": _STRING_PATTERN},
    "number": {"type": "string", "minLength": 1, "maxLength": 40, "pattern": r"^[0-9+*#() -]{1,40}(?![\s\S])"},
}


def _action_branch(action: str, common: tuple[str, ...]) -> dict[str, Any]:
    """The JSON Schema branch for one action: its own fields only, and what it needs."""
    then: dict[str, Any] = {"propertyNames": {"enum": [*common, *_ACTION_FIELDS[action]]}}
    groups = _REQUIRED.get(action, ())
    if len(groups) == 1:
        then["required"] = list(groups[0])
    elif groups:
        then["oneOf" if action in _EXCLUSIVE else "anyOf"] = [
            {"required": list(group)} for group in groups
        ]
    return {"if": {"properties": {"action": {"const": action}}, "required": ["action"]}, "then": then}


_STEP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": list(_BATCH_ACTIONS)},
        **{
            name: schema
            for name, schema in _FIELD_SCHEMAS.items()
            if any(name in _ACTION_FIELDS[action] for action in _BATCH_ACTIONS)
        },
    },
    "required": ["action"],
    "allOf": [_action_branch(action, ("action",)) for action in _BATCH_ACTIONS],
    "additionalProperties": False,
}


# On top of the batch step rules: fewer actions, and no refs.
_REPEAT_STEP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"action": {"type": "string", "enum": list(_REPEAT_ACTIONS)}},
    "not": {"required": ["ref"]},
}


# These return the screen they end on (a repeat runs on its own): nothing to verify afterwards.
_UNVERIFIED_ACTIONS = ("repeat", "stop_repeat", "scroll_to_text", "open_page")


def _action_branches() -> list[dict[str, Any]]:
    branches: list[dict[str, Any]] = [
        {
            "if": {"properties": {"action": {"not": {"enum": list(_FRESH_ACTIONS)}}}, "required": ["action"]},
            "then": {"required": ["snapshot_version"]},
        }
    ]
    for action in _ACTION_FIELDS:
        common = ("action", "snapshot_version") if action in _UNVERIFIED_ACTIONS else _COMMON_ACTION_FIELDS
        branch = _action_branch(action, common)
        if action == "repeat":
            branch["then"]["properties"] = {
                "steps": {"maxItems": _MAX_REPEAT_STEPS, "items": _REPEAT_STEP_SCHEMA}
            }
        branches.append(branch)
    return branches


def _action_payload(arguments: dict[str, Any], *, in_batch: bool = False) -> dict[str, Any]:
    """The bridge request for one action (or one step of a batch), checked field by field."""
    if not isinstance(arguments, dict):
        raise ToolArgumentError("each batch step must be an object")
    action = _string(arguments, "action", maximum=32)
    if action not in (_BATCH_ACTIONS if in_batch else _ALLOWED_ACTIONS):
        raise ToolArgumentError(
            f"unsupported {'batch step' if in_batch else 'Android action'}: {action}"
        )
    if in_batch:
        common: tuple[str, ...] = ("action",)
    elif action in _UNVERIFIED_ACTIONS:
        common = ("action", "snapshot_version")
    else:
        common = _COMMON_ACTION_FIELDS
    if set(arguments) - set(common) - set(_ACTION_FIELDS[action]):
        raise ToolArgumentError(f"unexpected arguments for Android action {action}")
    groups = _REQUIRED.get(action, ())
    present = [group for group in groups if all(name in arguments for name in group)]
    if groups and not present:
        needed = " or ".join(", ".join(group) for group in groups)
        raise ToolArgumentError(f"{action} requires {needed}")
    if action in _EXCLUSIVE and len(present) > 1:
        raise ToolArgumentError(f"{action} takes a ref or coordinates, not both")
    payload: dict[str, Any] = {"action": action}
    if not in_batch and ("snapshot_version" in arguments or action not in _FRESH_ACTIONS):
        payload["snapshot_version"] = _version(arguments)
    for name in ("x", "y", "x2", "y2"):
        if name in arguments:
            payload[name] = _int(arguments, name, minimum=0, maximum=10000)
    if "ref" in arguments:
        payload["ref"] = _ref(arguments)
    if "text" in arguments:
        payload["text"] = _string(
            arguments, "text", maximum=_MAX_TEXT if action == "type_text" else _MAX_LABEL
        )
    if "nth" in arguments:
        payload["nth"] = _int(arguments, "nth", minimum=1, maximum=50)
    if "max_scrolls" in arguments:
        payload["max_scrolls"] = _int(arguments, "max_scrolls", minimum=1, maximum=40)
    for flag in ("tap", "confirmed"):
        if flag in arguments:
            if not isinstance(arguments[flag], bool):
                raise ToolArgumentError(f"'{flag}' must be true or false")
            payload[flag] = arguments[flag]
    if action == "scroll_to_text" and arguments.get("direction") in ("top", "bottom"):
        raise ToolArgumentError("scroll_to_text scrolls up, down, left or right")
    if action == "open_page":
        page = arguments.get("page")
        if page not in _PAGES:
            raise ToolArgumentError(f"'page' must be one of {', '.join(_PAGES)}")
        payload["page"] = page
        needs = {"url": "url", "map": "query", "web_search": "query", "dial": "number"}.get(page)
        if needs and needs not in arguments:
            raise ToolArgumentError(f"open_page {page} requires {needs}")
        if page == "app_details" and not ({"package_name", "app_name"} & set(arguments)):
            raise ToolArgumentError("open_page app_details requires package_name or app_name")
        if "url" in arguments:
            url = _string(arguments, "url", maximum=2000)
            if not re.fullmatch(r"https?://\S+", url):
                raise ToolArgumentError("'url' must be an http(s) address")
            payload["url"] = url
        if "query" in arguments:
            payload["query"] = _string(arguments, "query", maximum=300)
        if "number" in arguments:
            number = _string(arguments, "number", maximum=40)
            if not re.fullmatch(r"[0-9+*#() -]{1,40}", number):
                raise ToolArgumentError("'number' may hold digits, spaces and + * # ( ) - only")
            payload["number"] = number
    if "direction" in arguments:
        if arguments["direction"] not in _DIRECTIONS:
            raise ToolArgumentError("'direction' must be up, down, left, right, top or bottom")
        payload["direction"] = arguments["direction"]
    if "package_name" in arguments:
        package = _string(arguments, "package_name", maximum=255)
        if not _PACKAGE_RE.fullmatch(package):
            raise ToolArgumentError("'package_name' is not a valid Android package")
        payload["package_name"] = package
    if "app_name" in arguments:
        payload["app_name"] = _string(arguments, "app_name", maximum=_MAX_APP_NAME)
    if action == "batch":
        steps = arguments.get("steps")
        if not isinstance(steps, list) or not 1 <= len(steps) <= _MAX_BATCH:
            raise ToolArgumentError(f"'steps' must list 1 to {_MAX_BATCH} actions")
        payload["steps"] = [_action_payload(step, in_batch=True) for step in steps]
    if action == "repeat":
        steps = arguments.get("steps")
        if not isinstance(steps, list) or not 1 <= len(steps) <= _MAX_REPEAT_STEPS:
            raise ToolArgumentError(f"'steps' of a repeat must list 1 to {_MAX_REPEAT_STEPS} actions")
        for step in steps:
            if not isinstance(step, dict) or step.get("action") not in _REPEAT_ACTIONS or "ref" in step:
                raise ToolArgumentError(
                    "a repeat taps, long-presses or swipes by coordinates, scrolls by direction or goes "
                    "back; refs do not last in a feed that changes every round"
                )
        payload["steps"] = [_action_payload(step, in_batch=True) for step in steps]
        payload["every_ms"] = _int(arguments, "every_ms", minimum=300, maximum=3_600_000)
        if "times" in arguments:
            payload["times"] = _int(arguments, "times", minimum=1, maximum=10_000)
    if not in_batch and "expect" in arguments:
        expect = arguments["expect"]
        if not isinstance(expect, dict) or not expect or len(expect) > 5:
            raise ToolArgumentError("'expect' must be a non-empty object with at most 5 fields")
        payload["expect"] = _validate_expect(expect)
    if not in_batch and "timeout_ms" in arguments:
        payload["timeout_ms"] = _int(arguments, "timeout_ms", minimum=100, maximum=_MAX_TIMEOUT_MS)
    return payload


# Ads come at any moment in Chinese apps; the model is told once, with every phone task.
_ADS = (
    "Ads can show at any moment: a splash ad as an app opens, a pop-up or red-packet layer over a "
    "page, a full-screen ad after a tap or a video. Expect one after every action, close it before "
    "going on, and never tap into it. A result's blocking names it with its dismiss control; "
    "otherwise close it by its own 跳过 / 关闭 / × / close control: small, usually in a corner or "
    "just under the picture, often an icon with no words (an id with close or skip, or a "
    "screenshot shows it). A splash ad with no skip control ends by itself in a few seconds: wait "
    "(android_observe wait_ms) instead of tapping. Never tap the ad's picture or its 立即下载 / "
    "去看看 / 了解详情 / 打开 / 领取 buttons. If an ad opened anyway (left_app in a result, an app "
    "store, a browser or mini program, a download or \"打开…?\" prompt, a page you did not tap "
    "for): cancel any download or open-app prompt, go back (back, again if needed, or launch_app "
    "the app you were in) and carry on with the task."
)


class AndroidActionTool(_BridgeTool):
    _SPEC = ToolSpec(
        name="android_action",
        description=(
            "Act on the phone using snapshot_version from a recent android_observe or "
            "android_screenshot (not needed for tap_text, scroll_to_text, open_page, launch_app, "
            "back, home, recents, notifications). A snapshot stays valid while the same window is shown, even if "
            "content in it keeps moving; if the target changed, the result says target_changed "
            "with a fresh observation. Each result shows the screen once it settled; "
            "screen_changed false means the action left it exactly as it was. Quickest: "
            "tap_text text (taps the control showing those words, on the screen as it is now; no "
            "snapshot needed; if several show them it lists them, then pass nth; words drawn in "
            "pictures are found too); scroll_to_text text (scrolls the list until the words show, "
            "tap=true taps them too); open_page page (a system page such as wifi, bluetooth, "
            "battery, display, sound, location, storage, apps, notifications, app_details with "
            "app_name, url with url, map or web_search with query, dial with number: it only "
            "opens). Others: ref (tap a control by its ref; prefer it to "
            "coordinates); tap x,y; long_press ref or x,y; type_text ref,text (replaces the field's "
            "text; pasted when the field refuses); enter (the keyboard's search/go/send key, on "
            "ref or the focused field); scroll direction (up/down/left/right, or top/bottom for all "
            "the way; the list ref or the main list; better than guessing swipe coordinates); "
            "swipe x,y,x2,y2; launch_app "
            "app_name (the name under the app's icon) or package_name; back, home, recents, "
            "notifications. batch runs up to 12 steps (tap, long_press, swipe, scroll, ref, "
            "type_text, enter, back, tap_text) in order with one approval, such as calculator keys or a "
            "form; refs and coordinates in the steps come from this snapshot, and the batch stops "
            "where the screen changed so a step no longer fits (look again and continue). repeat "
            "runs steps (tap, long_press or swipe by coordinates, scroll by direction, back; at most "
            "4) every every_ms milliseconds, times times or until stopped (4 hours at most): the "
            "phone keeps the time exactly and the call returns at once, so use it for anything at "
            "fixed intervals (the next video every 10 seconds) instead of acting at those times "
            "yourself, then reply without watching it. It stops when the user leaves that app (do "
            "not reopen it), the screen goes off or they tap stop; stop_repeat ends it. Supply only "
            "fields belonging to the chosen action. A control that deletes, clears (cache or data), "
            "uninstalls or stops an app is refused with needs_confirmation even when the task was "
            "approved: ask the user about that very control and end your turn; after their yes, repeat "
            "the action with confirmed=true. Paying, transferring, withdrawing, placing an order and "
            "payment password screens are refused with payment_blocked in every mode: stop and tell the "
            "user to finish that step themselves. " + _ADS
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": sorted(_ALLOWED_ACTIONS)},
                "snapshot_version": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 128,
                    "pattern": _STRING_PATTERN,
                },
                **_FIELD_SCHEMAS,
                "steps": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": _MAX_BATCH,
                    "items": _STEP_SCHEMA,
                },
                "expect": _EXPECT_SCHEMA,
                "timeout_ms": {"type": "integer", "minimum": 100, "maximum": _MAX_TIMEOUT_MS},
            },
            # snapshot_version is required by every action but those in _FRESH_ACTIONS.
            "required": ["action"],
            "allOf": _action_branches(),
            "additionalProperties": False,
        },
        side_effect="external",
        capability=Capability.PROCESS_EXECUTE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        await _wait_if_paused()
        response = await asyncio.to_thread(self._run, arguments)
        error = response.get("error")
        await context.record_event(
            Event(
                session_id=context.session_id,
                type="android.action.result",
                data={
                    "attempt_id": context.attempt_id,
                    "action": arguments.get("action"),
                    "snapshot_version": arguments.get("snapshot_version"),
                    "executed": response.get("executed"),
                    "verified": response.get("verified"),
                    "error_code": error.get("code") if isinstance(error, dict) else None,
                },
                causation_id=context.started_event_id,
                correlation_id=context.correlation_id,
            )
        )
        before = _SCREENS.get(context.session_id)
        tapped = _tapped_label(arguments, before)
        was_app = before["identity"][1] if before["identity"] else None
        was_page = before.get("activity")
        compact = _for_model(
            response, memory_key=context.session_id, changes_only=True, action=arguments.get("action")
        )
        observation = compact.get("observation") if isinstance(compact.get("observation"), dict) else {}
        if tapped and "screen_changed" in observation and was_app and was_app == observation.get("package_name"):
            await asyncio.to_thread(
                _record_tap, was_app, tapped, observation["screen_changed"], was_page, observation.get("activity_name")
            )
        notes = _app_notes(context.session_id, observation)
        if notes:
            compact["app_notes"] = notes
        warning = _going_in_circles(context.session_id, arguments, response)
        if warning:
            compact["warning"] = warning
        return json_result(compact)

    @staticmethod
    def prepare_for_approval(arguments: dict[str, Any]) -> dict[str, Any]:
        """The action exactly as it will run: the runner executes what was approved, so this keeps
        every field of the chosen action (the text to type too, which the person approving should
        see) and drops nothing else of use."""
        action = arguments.get("action")
        common = ("action", "snapshot_version") if action in _UNVERIFIED_ACTIONS else _COMMON_ACTION_FIELDS
        permitted = (*common, *_ACTION_FIELDS.get(str(action), ()))
        return {name: arguments[name] for name in permitted if name in arguments}

    def _run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        validate_tool_arguments(self.spec, arguments)
        return _invoke(self.bridge, _action_payload(arguments))


def _validate_expect(expect: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in expect.items():
        if key not in {
            "package_name",
            "activity_name",
            "text_contains",
            "view_id_exists",
            "resource_id",
        }:
            raise ToolArgumentError(f"unsupported verification field: {key}")
        if not isinstance(value, str) or not value or len(value) > _MAX_EXPECT or "\0" in value:
            raise ToolArgumentError(f"verification field {key!r} must be a bounded string")
        result[key] = value
    return result


class AndroidVerifyTool(_BridgeTool):
    _SPEC = ToolSpec(
        name="android_verify",
        description=(
            "Verify visible Android state using package, activity, text, or resource ID predicates."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "expect": _EXPECT_SCHEMA,
                "snapshot_version": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 128,
                    "pattern": _STRING_PATTERN,
                },
                "timeout_ms": {"type": "integer", "minimum": 100, "maximum": _MAX_TIMEOUT_MS},
            },
            "required": ["expect"],
            "additionalProperties": False,
        },
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def _run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        validate_tool_arguments(self.spec, arguments)
        expect = arguments.get("expect")
        if not isinstance(expect, dict) or not expect:
            raise ToolArgumentError("'expect' must be a non-empty object")
        payload: dict[str, Any] = {"action": "verify", "expect": _validate_expect(expect)}
        if "snapshot_version" in arguments:
            payload["snapshot_version"] = _version(arguments)
        if "timeout_ms" in arguments:
            payload["timeout_ms"] = _int(
                arguments, "timeout_ms", minimum=100, maximum=_MAX_TIMEOUT_MS
            )
        return _invoke(self.bridge, payload)


def register_android_system_tools(registry: Any, bridge: Any | None = None) -> dict[str, Any]:
    """Register only tools runnable with the currently connected Android service."""

    status = get_android_system_status(bridge)
    unavailable: dict[str, str] = {}
    if status.get("available") and status.get("enabled") and status.get("connected"):
        tools: tuple[_BridgeTool, ...] = (
            AndroidObserveTool(bridge),
            AndroidActionTool(bridge),
            AndroidVerifyTool(bridge),
        )
        for tool in tools:
            if tool.spec.name not in {spec.name for spec in registry.specs()}:
                registry.register(tool)
    else:
        reason = "Enable Agent Workspace in Android Accessibility settings and restart the engine"
        for name in ("android_observe", "android_action", "android_verify"):
            unavailable[name] = reason
    if status.get("screenshot_supported") and status.get("enabled") and status.get("connected"):
        screenshot_tool = AndroidScreenshotTool(bridge)
        if screenshot_tool.spec.name not in {spec.name for spec in registry.specs()}:
            registry.register(screenshot_tool)
    else:
        unavailable["android_screenshot"] = (
            "Android screenshots require enabled Accessibility and Android 11 (API 30) or newer, "
            "or the live screen (Device & tools)"
        )
    previous = dict(getattr(registry, "_android_unavailable", {}))
    # Capability refresh owns only these native tools.  Other adapters may use
    # the same registry and keep their own unavailable reasons.
    registered = getattr(registry, "_tools", {})
    for name in unavailable:
        if isinstance(registered.get(name), _BridgeTool):
            registered.pop(name, None)
    for name in ("android_observe", "android_action", "android_verify", "android_screenshot"):
        previous.pop(name, None)
    previous.update(unavailable)
    registry._android_unavailable = previous
    return status


def execute_android_system_request(
    request: dict[str, Any], bridge: Any | None = None
) -> dict[str, Any]:
    """Entry point for the authenticated mobile gateway route."""

    if not isinstance(request, dict):
        raise ToolArgumentError("Android system request must be an object")
    action = request.get("action")
    arguments = {key: value for key, value in request.items() if key != "action"}
    if action == "observe":
        return AndroidObserveTool(bridge)._run(arguments)
    if action == "screenshot":
        return AndroidScreenshotTool(bridge)._run(arguments)
    if action == "verify":
        return AndroidVerifyTool(bridge)._run(arguments)
    return AndroidActionTool(bridge)._run(request)
