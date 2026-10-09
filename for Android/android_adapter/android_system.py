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
_REF_RE = re.compile(r"^n[0-9]{1,3}(?![\s\S])")
_STRING_PATTERN = r"^[^\u0000]+(?![\s\S])"
_ACTION_FIELDS = {
    "tap": ("x", "y"),
    "swipe": ("x", "y", "x2", "y2"),
    "ref": ("ref",),
    "type_text": ("ref", "text"),
    "launch_app": ("package_name",),
    "back": (),
    "home": (),
}
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
        "connected",
        "local_connection",
        "paused",
        "takeover_requested",
        "screenshot_supported",
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


def _invoke(bridge: Any | None, request: dict[str, Any]) -> dict[str, Any]:
    _require_available(bridge)
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
        return json_result(await asyncio.to_thread(self._run, arguments))

    def _run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class AndroidObserveTool(_BridgeTool):
    _SPEC = ToolSpec(
        name="android_observe",
        description=(
            "Observe the current Android app, window, bounded accessibility UI tree, and screen."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "max_nodes": {"type": "integer", "minimum": 1, "maximum": _MAX_NODES},
                "max_depth": {"type": "integer", "minimum": 1, "maximum": _MAX_DEPTH},
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
        return _invoke(
            self.bridge, {"action": "observe", "max_nodes": max_nodes, "max_depth": max_depth}
        )


class AndroidScreenshotTool(_BridgeTool):
    _SPEC = ToolSpec(
        name="android_screenshot",
        description="Capture the Android display into the private workspace and attach the image.",
        input_schema={"type": "object", "additionalProperties": False},
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
        response = _invoke(self.bridge, {"action": "screenshot"})
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
        return json_result(response)


class AndroidActionTool(_BridgeTool):
    _SPEC = ToolSpec(
        name="android_action",
        description=(
            "Perform one Android action using snapshot_version from the latest android_observe. "
            "Required action parameters: tap x,y; swipe x,y,x2,y2; ref ref; "
            "type_text ref,text; launch_app package_name. back/home require only "
            "action,snapshot_version. Supply only fields belonging to the chosen action."
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
                "package_name": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 255,
                    "pattern": _PACKAGE_RE.pattern,
                },
                "expect": _EXPECT_SCHEMA,
                "timeout_ms": {"type": "integer", "minimum": 100, "maximum": _MAX_TIMEOUT_MS},
            },
            "required": ["action", "snapshot_version"],
            "allOf": [
                {
                    "if": {"properties": {"action": {"const": action}}, "required": ["action"]},
                    "then": {
                        "required": list(fields),
                        "propertyNames": {"enum": [*_COMMON_ACTION_FIELDS, *fields]},
                    },
                }
                for action, fields in _ACTION_FIELDS.items()
            ],
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
        return json_result(response)

    @staticmethod
    def prepare_for_approval(arguments: dict[str, Any]) -> dict[str, Any]:
        action = arguments.get("action")
        prepared = {
            "action": action,
            "snapshot_version": arguments.get("snapshot_version"),
        }
        if action == "tap":
            prepared.update(x=arguments.get("x"), y=arguments.get("y"))
        elif action == "swipe":
            prepared.update(
                x=arguments.get("x"),
                y=arguments.get("y"),
                x2=arguments.get("x2"),
                y2=arguments.get("y2"),
            )
        elif action == "ref":
            prepared["ref"] = arguments.get("ref")
        elif action == "type_text":
            prepared.update(
                ref=arguments.get("ref"), text_length=len(str(arguments.get("text", "")))
            )
        elif action == "launch_app":
            prepared["package_name"] = arguments.get("package_name")
        if "expect" in arguments:
            prepared["expect"] = arguments["expect"]
        return prepared

    def _run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        validate_tool_arguments(self.spec, arguments)
        action = _string(arguments, "action", maximum=32)
        if action not in _ALLOWED_ACTIONS:
            raise ToolArgumentError(f"unsupported Android action: {action}")
        payload: dict[str, Any] = {"action": action, "snapshot_version": _version(arguments)}
        permitted = set(_COMMON_ACTION_FIELDS) | set(_ACTION_FIELDS[action])
        if set(arguments) - permitted:
            raise ToolArgumentError(f"unexpected arguments for Android action {action}")
        if action in {"tap", "swipe"}:
            payload.update(
                x=_int(arguments, "x", minimum=0, maximum=10000),
                y=_int(arguments, "y", minimum=0, maximum=10000),
            )
        if action == "tap":
            if "x2" in arguments or "y2" in arguments:
                raise ToolArgumentError("tap does not accept x2 or y2")
        elif action == "swipe":
            payload.update(
                x2=_int(arguments, "x2", minimum=0, maximum=10000),
                y2=_int(arguments, "y2", minimum=0, maximum=10000),
            )
        elif action == "ref":
            payload["ref"] = _ref(arguments)
        elif action == "type_text":
            payload.update(ref=_ref(arguments), text=_string(arguments, "text"))
        elif action == "launch_app":
            package = _string(arguments, "package_name", maximum=255)
            if not _PACKAGE_RE.fullmatch(package):
                raise ToolArgumentError("'package_name' is not a valid Android package")
            payload["package_name"] = package
        if "expect" in arguments:
            expect = arguments["expect"]
            if not isinstance(expect, dict) or not expect or len(expect) > 5:
                raise ToolArgumentError("'expect' must be a non-empty object with at most 5 fields")
            payload["expect"] = _validate_expect(expect)
        if "timeout_ms" in arguments:
            payload["timeout_ms"] = _int(
                arguments, "timeout_ms", minimum=100, maximum=_MAX_TIMEOUT_MS
            )
        return _invoke(self.bridge, payload)


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
            "Android screenshots require Android 11 (API 30) or newer and enabled Accessibility"
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
