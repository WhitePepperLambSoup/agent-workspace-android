# ruff: noqa: RUF001 -- the transcript is written in Chinese.
"""Meeting recordings turned into a timed transcript: long recordings are cut into parts (with
ffmpeg when the computer has it, WAV files without it), each part goes to the speech-to-text
service chosen in Settings → Voice, and the text comes back with its times."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from agent_workspace.config import is_loopback_endpoint
from agent_workspace.office.ooxml import OfficeError

PART_SECONDS = 600
MAX_UPLOAD = 24 * 1024 * 1024
_CREATE_NO_WINDOW = 0x08000000
_MIME = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
    ".aac": "audio/aac",
    ".amr": "audio/amr",
    ".mp4": "video/mp4",
}


@dataclass
class Part:
    path: Path
    start: float


@dataclass
class Line:
    start: float
    text: str
    speaker: str = ""


def ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def split(source: Path, folder: Path) -> list[Part]:
    """The recording as parts of at most ten minutes (small enough to upload)."""
    tool = ffmpeg()
    if tool:
        pattern = folder / "part%03d.mp3"
        done = subprocess.run(
            [
                tool,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "48k",
                "-f",
                "segment",
                "-segment_time",
                str(PART_SECONDS),
                "-reset_timestamps",
                "1",
                str(pattern),
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            creationflags=_CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            check=False,
        )
        if done.returncode != 0:
            raise OfficeError(
                f"ffmpeg could not read the recording: {(done.stderr or '').strip()[-300:]}"
            )
        parts = sorted(folder.glob("part*.mp3"))
        return [Part(path, index * PART_SECONDS) for index, path in enumerate(parts)]
    if source.suffix.lower() == ".wav":
        out = []
        with wave.open(str(source), "rb") as reader:
            frames_per_part = reader.getframerate() * PART_SECONDS
            index = 0
            while True:
                frames = reader.readframes(frames_per_part)
                if not frames:
                    break
                path = folder / f"part{index:03d}.wav"
                with wave.open(str(path), "wb") as writer:
                    writer.setnchannels(reader.getnchannels())
                    writer.setsampwidth(reader.getsampwidth())
                    writer.setframerate(reader.getframerate())
                    writer.writeframes(frames)
                out.append(Part(path, index * PART_SECONDS))
                index += 1
        return out
    if source.stat().st_size <= MAX_UPLOAD:
        return [Part(source, 0.0)]
    raise OfficeError(
        "the recording is over 24 MB and this computer has no ffmpeg to cut it: install ffmpeg "
        "(winget install ffmpeg) or save the recording as WAV"
    )


Transcriber = Callable[[bytes, str, str], dict[str, Any]]


def http_transcriber(base_url: str, api_key: str, model: str, timeout: float = 600) -> Transcriber:
    """Posts a part to {base_url}/audio/transcriptions, asking for segment times."""

    def post(audio: bytes, filename: str, mime: str) -> dict[str, Any]:
        endpoint = f"{base_url.rstrip('/')}/audio/transcriptions"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        with httpx.Client(timeout=timeout, trust_env=not is_loopback_endpoint(base_url)) as client:
            for response_format in ("verbose_json", "json"):
                try:
                    response = client.post(
                        endpoint,
                        headers=headers,
                        files={"file": (filename, audio, mime)},
                        data={"model": model, "response_format": response_format},
                    )
                except httpx.HTTPError as error:
                    raise OfficeError(f"the transcription request failed: {error}") from None
                if response.status_code == 200:
                    try:
                        payload = response.json()
                    except ValueError:
                        raise OfficeError(
                            "the transcription service did not answer with JSON"
                        ) from None
                    return payload if isinstance(payload, dict) else {}
                if response.status_code not in (400, 422):
                    break
            raise OfficeError(f"the transcription service answered HTTP {response.status_code}")

    return post


def transcribe(
    source: Path, transcriber: Transcriber, progress: Callable[[int, int], None] | None = None
) -> list[Line]:
    with tempfile.TemporaryDirectory(prefix="aw-meeting-") as folder:
        parts = split(source, Path(folder))
        lines: list[Line] = []
        for number, part in enumerate(parts, start=1):
            if progress:
                progress(number, len(parts))
            data = part.path.read_bytes()
            payload = transcriber(
                data,
                part.path.name,
                _MIME.get(part.path.suffix.lower(), "application/octet-stream"),
            )
            segments = payload.get("segments")
            if isinstance(segments, list) and segments:
                for segment in segments:
                    if not isinstance(segment, dict):
                        continue
                    text = str(segment.get("text", "")).strip()
                    if text:
                        lines.append(
                            Line(
                                part.start + float(segment.get("start", 0) or 0),
                                text,
                                str(segment.get("speaker", "") or ""),
                            )
                        )
            elif str(payload.get("text", "")).strip():
                lines.append(Line(part.start, str(payload["text"]).strip()))
        return lines


def clock(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def markdown(title: str, lines: list[Line]) -> str:
    out = [f"# {title}", ""]
    for line in lines:
        speaker = f"**{line.speaker}**：" if line.speaker else ""
        out.append(f"[{clock(line.start)}] {speaker}{line.text}")
        out.append("")
    return "\n".join(out)


__all__ = ["Line", "clock", "ffmpeg", "http_transcriber", "markdown", "split", "transcribe"]
