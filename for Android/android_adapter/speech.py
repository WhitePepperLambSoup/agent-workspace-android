"""Android engine speech with bounded duration and explicit cancellation."""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any
from uuid import uuid4

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result, require_string

_speech_bridge: Any = None


def _bridge() -> Any:
    global _speech_bridge
    if _speech_bridge is None:
        from java import jclass

        _speech_bridge = jclass("com.agentworkspace.mobile.capabilities.AndroidTextToSpeech")
    return _speech_bridge


def speech_status() -> dict[str, Any]:
    try:
        report = json.loads(str(_bridge().getStatusJson()))
        if not isinstance(report, dict) or type(report.get("ready")) is not bool:
            raise ValueError("invalid status")
        return report
    except Exception:
        return {"ready": False, "reason": "Android TTS bridge is unavailable in this runtime"}


class AndroidSpeakTool:
    hard_cancellable = False
    _SPEC = ToolSpec(
        name="speak_text",
        description="Read bounded text aloud using the installed Android TTS engine.",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string", "minLength": 1, "maxLength": 2000}},
            "required": ["text"],
            "additionalProperties": False,
        },
        side_effect="process",
        capability=Capability.PROCESS_EXECUTE,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        text = require_string(arguments, "text")
        if len(text) > 2000 or "\x00" in text:
            raise ToolArgumentError("'text' must have at most 2000 characters without NUL")
        status = speech_status()
        if not status.get("ready"):
            raise ToolError(str(status.get("reason") or "Android TTS engine is not ready"))
        bridge = _bridge()
        request_id = str(uuid4())
        try:
            started = json.loads(str(bridge.startSpeak(request_id, text)))
            if not started.get("accepted"):
                raise ToolError(str(started.get("reason") or "Android TTS could not start"))
            async with asyncio.timeout(120):
                while True:
                    result = json.loads(str(bridge.getUtteranceStatus(request_id)))
                    state = result.get("state")
                    if state == "completed":
                        return json_result(
                            {"spoken": True, "chars": len(text), "engine": status.get("engine")}
                        )
                    if state in {"failed", "cancelled", "unknown"}:
                        raise ToolError(
                            str(result.get("reason") or "Android speech did not complete")
                        )
                    await asyncio.sleep(0.05)
        except TimeoutError as exc:
            raise ToolError("Android speech synthesis timed out") from exc
        except (ValueError, TypeError) as exc:
            raise ToolError("Android TTS returned an invalid result") from exc
        finally:
            with contextlib.suppress(Exception):
                bridge.stop(request_id)
