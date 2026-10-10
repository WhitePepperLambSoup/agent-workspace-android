"""transcribe_audio: offline speech recognition of workspace audio (AudioTranscriber.kt).

The audio is recognized on the phone with SenseVoice Small, which the user downloads on the
Local models page; nothing is uploaded. Like read_file, the tool only reads a workspace file.
Long recordings are covered in pieces: each call transcribes up to max_seconds from
start_seconds and says where the next call should continue.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result
from agent_workspace.tools.paths import StrPath, WorkspacePaths, is_sensitive_workspace_path

AUDIO_SUFFIXES = frozenset(
    {
        ".m4a",
        ".aac",
        ".mp3",
        ".wav",
        ".ogg",
        ".oga",
        ".opus",
        ".amr",
        ".3gp",
        ".flac",
        ".mp4",
        ".webm",
        ".mkv",
        ".mov",
    }
)
# Text returned in one call; a longer transcript is cut at a segment boundary and continued.
_MAX_TEXT = 24_000
# Wall-clock budget of one call on the phone CPU (about 5-10x faster than real time).
_DEADLINE_SECONDS = 600
_MODEL_HELP = (
    "Offline speech recognition needs its model. Ask the user to download it in this app: "
    "Menu → 本地模型 → 离线语音识别 (Local models → Offline speech recognition), about 240 MB."
)
_bridge_class: Any = None


def _bridge() -> Any:
    global _bridge_class
    if _bridge_class is None:
        from java import jclass

        _bridge_class = jclass("com.agentworkspace.mobile.voice.AudioTranscriber")
    return _bridge_class


def speech_runtime_status() -> dict[str, Any] | None:
    """runtime_available / model_installed from the Android app, or None outside it."""
    try:
        value = json.loads(str(_bridge().status()))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _join(segments: list[dict[str, Any]]) -> str:
    """Joins segment texts the way AudioPcm.join does: a space only between Latin words."""
    text = ""
    for segment in segments:
        piece = segment["text"].strip()
        if not piece:
            continue
        before = text[-1:] or " "
        if (
            text
            and (before.isalnum() or before in ".,!?;:")
            and ord(before) < 0x2E80
            and (piece[0].isalnum() and ord(piece[0]) < 0x2E80)
        ):
            text += " "
        text += piece
    return text


class TranscribeAudioTool:
    hard_cancellable = False
    _SPEC = ToolSpec(
        name="transcribe_audio",
        description=(
            "Transcribe speech in a workspace audio or video file (m4a, mp3, wav, ogg/opus, amr, "
            "flac, mp4...) to text, offline on the phone. Chinese, English, Japanese, Korean "
            "and Cantonese. Returns the text and timed segments. For long recordings it covers "
            "max_seconds per call; continue from next_start_seconds when complete is false."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1, "maxLength": 1024},
                "start_seconds": {"type": "number", "minimum": 0},
                "max_seconds": {"type": "integer", "minimum": 10, "maximum": 3600},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        side_effect="read",
        capability=Capability.WORKSPACE_READ,
    )

    def __init__(self, workspace: WorkspacePaths | StrPath) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        request, relative = self._request(arguments)
        try:
            raw = await asyncio.to_thread(_bridge().transcribe, json.dumps(request))
            result = json.loads(str(raw))
        except Exception as exc:
            raise ToolError(f"speech recognition is unavailable: {exc}") from None
        if not isinstance(result, dict):
            raise ToolError("the phone returned an invalid result")
        if result.get("ok") is not True:
            code = result.get("code")
            if code == "model_missing":
                raise ToolError(_MODEL_HELP)
            if code == "unsupported_device":
                raise ToolError(
                    "offline speech recognition runs on 64-bit ARM phones only; this device "
                    "cannot transcribe audio"
                )
            raise ToolError(f"could not transcribe {relative}: {result.get('error')}")
        return json_result(self._shape(result, relative))

    async def execute_with_context(self, arguments: dict[str, Any], _context: Any) -> str:
        return await self.execute(arguments)

    def _request(self, arguments: dict[str, Any]) -> tuple[dict[str, Any], str]:
        raw = arguments.get("path")
        if not isinstance(raw, str) or not raw.strip():
            raise ToolArgumentError("'path' must be an audio file in the workspace")
        path = self.paths.resolve(raw)
        relative = self.paths.relative(path)
        if is_sensitive_workspace_path(relative):
            raise ToolError("sensitive files cannot be transcribed")
        if not Path(path).is_file():
            raise ToolError(f"not a file: {relative}")
        if Path(path).suffix.lower() not in AUDIO_SUFFIXES:
            raise ToolError(
                f"{relative} is not an audio file this tool reads"
                + (
                    "; WeChat .silk voice notes need converting first"
                    if Path(path).suffix.lower() == ".silk"
                    else ""
                )
            )
        start = arguments.get("start_seconds", 0)
        if (
            isinstance(start, bool)
            or not isinstance(start, (int, float))
            or not 0 <= start < 86_400
        ):
            raise ToolArgumentError("'start_seconds' must be a position in seconds")
        length = arguments.get("max_seconds", 1800)
        if isinstance(length, bool) or not isinstance(length, int) or not 10 <= length <= 3600:
            raise ToolArgumentError("'max_seconds' must be 10 to 3600")
        return (
            {
                "path": str(path),
                "start_seconds": float(start),
                "max_seconds": float(length),
                "deadline_seconds": float(_DEADLINE_SECONDS),
            },
            relative,
        )

    @staticmethod
    def _shape(result: dict[str, Any], relative: str) -> dict[str, Any]:
        segments = [item for item in result.get("segments") or [] if isinstance(item, dict)]
        kept, used = [], 0
        for segment in segments:
            text = str(segment.get("text", ""))
            if kept and used + len(text) > _MAX_TEXT:
                break
            kept.append({"start": segment.get("start"), "end": segment.get("end"), "text": text})
            used += len(text) + 1
        complete = bool(result.get("complete")) and len(kept) == len(segments)
        next_start = result.get("next_start_seconds")
        if len(kept) < len(segments):
            next_start = kept[-1]["end"] if kept else result.get("start_seconds")
        payload: dict[str, Any] = {
            "path": relative,
            "text": str(result.get("text", "")) if len(kept) == len(segments) else _join(kept),
            "segments": kept,
            "start_seconds": result.get("start_seconds"),
            "covered_seconds": result.get("covered_seconds"),
            "total_seconds": result.get("total_seconds"),
            "complete": complete,
            "recognizer": result.get("model"),
        }
        if not complete:
            payload["next_start_seconds"] = next_start
        if not kept:
            payload["note"] = "no speech was recognized in this part of the file"
        return payload


__all__ = ["AUDIO_SUFFIXES", "TranscribeAudioTool", "speech_runtime_status"]
