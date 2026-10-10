"""Alarms, timers and the calendar through the Android app (AndroidClockCalendar.kt).

Alarms and timers go to the phone's own Clock app, where the user sees and cancels them, so
they run without an approval prompt (the "session_state" effect, as for memory). Adding a
calendar event asks for approval each time: the card shows exactly what will be written to the
user's calendar. Reading events needs the calendar permission, which the user grants on
Settings → Device & tools; until then the tools say how to turn it on.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result

_bridge_class: Any = None
_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
# java.util.Calendar numbers its days from Sunday = 1.
_CALENDAR_DAY = {"sun": 1, "mon": 2, "tue": 3, "wed": 4, "thu": 5, "fri": 6, "sat": 7}
_TIME = re.compile(r"([01]?\d|2[0-3]):([0-5]\d)")
_PERMISSION_HELP = (
    "Calendar access is off. Ask the user to allow it in this app: Menu → 设备与工具 → 日历 "
    "(Settings → Device & tools → Calendar), then try again."
)


def _bridge() -> Any:
    global _bridge_class
    if _bridge_class is None:
        from java import jclass

        _bridge_class = jclass("com.agentworkspace.mobile.capabilities.AndroidClockCalendar")
    return _bridge_class


def clock_available() -> bool:
    try:
        _bridge()
        return True
    except Exception:
        return False


def phone_now() -> dict[str, Any] | None:
    """The phone's local date, time and zone, or None outside the Android app."""
    try:
        value = json.loads(str(_bridge().now()))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


async def _call(method: str, request: dict[str, Any]) -> dict[str, Any]:
    try:
        raw = await asyncio.to_thread(getattr(_bridge(), method), json.dumps(request))
        result = json.loads(str(raw))
    except Exception as exc:
        raise ToolError(f"the phone's clock and calendar are unavailable: {exc}") from None
    if not isinstance(result, dict):
        raise ToolError("the phone returned an invalid result")
    if result.get("ok") is not True:
        if result.get("code") == "permission_required":
            raise ToolError(_PERMISSION_HELP)
        raise ToolError(str(result.get("error") or "the phone refused the request"))
    result.pop("ok", None)
    return result


def _label(arguments: dict[str, Any]) -> str:
    label = arguments.get("label", "")
    if not isinstance(label, str) or len(label) > 60:
        raise ToolArgumentError("'label' must be text of at most 60 characters")
    return label.strip()


class _Tool:
    _SPEC: ToolSpec

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute_with_context(self, arguments: dict[str, Any], _context: Any) -> str:
        return await self.execute(arguments)


class SetAlarmTool(_Tool):
    hard_cancellable = False
    _SPEC = ToolSpec(
        name="set_alarm",
        description=(
            "Set an alarm in the phone's Clock app. Give time as HH:MM (24-hour) for a time of "
            "day, or in_minutes for an alarm that many minutes from now. days repeats it on "
            "those weekdays. For a countdown use set_timer instead."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "time": {"type": "string", "pattern": r"^\d{1,2}:\d{2}$"},
                "in_minutes": {"type": "integer", "minimum": 1, "maximum": 1440},
                "label": {"type": "string", "maxLength": 60},
                "days": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(_DAYS)},
                    "maxItems": 7,
                    "uniqueItems": True,
                },
            },
            "additionalProperties": False,
        },
        # The alarm lands in the Clock app, where the user sees and removes it.
        side_effect="session_state",
        capability=Capability.PROCESS_EXECUTE,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        request: dict[str, Any] = {"label": _label(arguments)}
        time, minutes = arguments.get("time"), arguments.get("in_minutes")
        if (time is None) == (minutes is None):
            raise ToolArgumentError("give either 'time' (HH:MM) or 'in_minutes'")
        if time is not None:
            match = _TIME.fullmatch(str(time).strip())
            if match is None:
                raise ToolArgumentError("'time' must be HH:MM on a 24-hour clock")
            request.update(hour=int(match[1]), minute=int(match[2]))
        else:
            if type(minutes) is not int or not 1 <= minutes <= 1440:
                raise ToolArgumentError("'in_minutes' must be from 1 to 1440")
            request["in_minutes"] = minutes
        days = arguments.get("days") or []
        if not isinstance(days, list) or any(day not in _CALENDAR_DAY for day in days):
            raise ToolArgumentError(
                "'days' must list weekdays as mon, tue, wed, thu, fri, sat, sun"
            )
        if days:
            request["days"] = [_CALENDAR_DAY[day] for day in dict.fromkeys(days)]
        result = await _call("setAlarm", request)
        return json_result(_delivery({"alarm": result.get("time"), "label": request["label"],
                                      "repeats": list(dict.fromkeys(days))}, result))  # fmt: skip


class SetTimerTool(_Tool):
    hard_cancellable = False
    _SPEC = ToolSpec(
        name="set_timer",
        description="Start a countdown timer in the phone's Clock app.",
        input_schema={
            "type": "object",
            "properties": {
                "minutes": {"type": "integer", "minimum": 0, "maximum": 1440},
                "seconds": {"type": "integer", "minimum": 0, "maximum": 59},
                "label": {"type": "string", "maxLength": 60},
            },
            "additionalProperties": False,
        },
        side_effect="session_state",
        capability=Capability.PROCESS_EXECUTE,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        minutes, seconds = arguments.get("minutes", 0), arguments.get("seconds", 0)
        if type(minutes) is not int or type(seconds) is not int or minutes < 0 or seconds < 0:
            raise ToolArgumentError("'minutes' and 'seconds' must be whole numbers")
        total = minutes * 60 + seconds
        if not 1 <= total <= 86400:
            raise ToolArgumentError("a timer runs from 1 second to 24 hours")
        result = await _call("setTimer", {"seconds": total, "label": _label(arguments)})
        return json_result(_delivery({"timer_seconds": total, "label": _label(arguments)}, result))


def _delivery(summary: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    if result.get("delivered") == "notification":
        summary["delivered"] = "notification"
        summary["note"] = (
            "This app was not on screen, so the phone shows a notification; it takes effect "
            "when the user taps it. Tell the user."
        )
    else:
        summary["delivered"] = "clock_app"
    return summary


class ListCalendarEventsTool(_Tool):
    hard_cancellable = False
    _SPEC = ToolSpec(
        name="list_calendar_events",
        description=(
            "List the events in the user's phone calendar, from start_date (YYYY-MM-DD, default "
            "today) for the given number of days (default 1)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
                "days": {"type": "integer", "minimum": 1, "maximum": 62},
            },
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.MEMORY_READ,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        request: dict[str, Any] = {}
        if arguments.get("start_date") is not None:
            request["start_date"] = _date(arguments["start_date"], "start_date").isoformat()
        days = arguments.get("days", 1)
        if type(days) is not int or not 1 <= days <= 62:
            raise ToolArgumentError("'days' must be from 1 to 62")
        request["days"] = days
        return json_result(await _call("listEvents", request))


class AddCalendarEventTool(_Tool):
    hard_cancellable = False
    _SPEC = ToolSpec(
        name="add_calendar_event",
        description=(
            "Add an event to the user's phone calendar. start and end are local times as "
            "YYYY-MM-DD HH:MM (end defaults to one hour later); for an all-day event set all_day "
            "and give dates as YYYY-MM-DD. reminder_minutes adds an alert that long before."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "all_day": {"type": "boolean"},
                "location": {"type": "string", "maxLength": 200},
                "notes": {"type": "string", "maxLength": 2000},
                "reminder_minutes": {"type": "integer", "minimum": 0, "maximum": 40320},
            },
            "required": ["title", "start"],
            "additionalProperties": False,
        },
        # A fixed native action, approved each time so the user sees the event first.
        side_effect="process",
        capability=Capability.PROCESS_EXECUTE,
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        title = arguments.get("title")
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise ToolArgumentError("'title' must be text of at most 200 characters")
        all_day = arguments.get("all_day", False)
        if not isinstance(all_day, bool):
            raise ToolArgumentError("'all_day' must be true or false")
        request: dict[str, Any] = {"title": title.strip(), "all_day": all_day}
        for key in ("start", "end"):
            if arguments.get(key) is None:
                continue
            value = arguments[key]
            request[key] = (
                _date(value, key).isoformat() if all_day else _moment(value, key).isoformat()
            )
        if "start" not in request:
            raise ToolArgumentError("'start' is required")
        for key, limit in (("location", 200), ("notes", 2000)):
            value = arguments.get(key)
            if value is not None:
                if not isinstance(value, str) or len(value) > limit:
                    raise ToolArgumentError(f"'{key}' must be text of at most {limit} characters")
                request[key] = value
        reminder = arguments.get("reminder_minutes")
        if reminder is not None:
            if type(reminder) is not int or not 0 <= reminder <= 40320:
                raise ToolArgumentError("'reminder_minutes' must be from 0 to 40320")
            request["reminder_minutes"] = reminder
        result = await _call("addEvent", request)
        return json_result({"added": request, **result})


def _date(value: Any, key: str) -> date:
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        raise ToolArgumentError(f"'{key}' must be a date as YYYY-MM-DD") from None


def _moment(value: Any, key: str) -> datetime:
    text = str(value).strip().replace("T", " ")
    try:
        moment = datetime.strptime(text[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        raise ToolArgumentError(f"'{key}' must be a local time as YYYY-MM-DD HH:MM") from None
    return moment


def clock_calendar_tools() -> dict[str, Any]:
    return {
        "set_alarm": SetAlarmTool,
        "set_timer": SetTimerTool,
        "list_calendar_events": ListCalendarEventsTool,
        "add_calendar_event": AddCalendarEventTool,
    }


__all__ = [
    "AddCalendarEventTool",
    "ListCalendarEventsTool",
    "SetAlarmTool",
    "SetTimerTool",
    "clock_available",
    "clock_calendar_tools",
    "phone_now",
]
