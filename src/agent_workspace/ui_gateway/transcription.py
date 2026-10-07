"""Speech-to-text for composer voice input through an OpenAI-compatible endpoint."""

from __future__ import annotations

import base64
import binascii
from typing import Final

import httpx

from agent_workspace.config import ProviderConfig, is_loopback_endpoint

# Recordings travel inside one bounded protocol message, so keep them well
# below the 1 MiB frame once base64-encoded (about two minutes of Opus).
MAX_RECORDING_BYTES: Final = 720 * 1024
_MAX_RESPONSE_BYTES: Final = 1_048_576
_MAX_TRANSCRIPT_CHARS: Final = 20_000
_TIMEOUT_SECONDS: Final = 120.0
_AUDIO_FORMATS: Final = {
    "audio/webm": (b"\x1a\x45\xdf\xa3", "speech.webm"),
    "audio/ogg": (b"OggS", "speech.ogg"),
    "audio/wav": (b"RIFF", "speech.wav"),
}


class TranscriptionError(RuntimeError):
    pass


def decode_recording(media_type: object, data: object) -> tuple[bytes, str, str]:
    """Validate a base64 recording; returns its bytes, file name and media type."""
    if not isinstance(media_type, str) or not isinstance(data, str):
        raise ValueError("recording is invalid")
    base_type = media_type.split(";", 1)[0].strip().casefold()
    audio_format = _AUDIO_FORMATS.get(base_type)
    if audio_format is None:
        raise ValueError("recording format is unsupported")
    if len(data) > (MAX_RECORDING_BYTES * 4) // 3 + 4:
        raise ValueError("recording is too long")
    try:
        audio = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("recording is not valid base64") from None
    signature, filename = audio_format
    if not audio or len(audio) > MAX_RECORDING_BYTES or not audio.startswith(signature):
        raise ValueError("recording content does not match its format")
    return audio, filename, base_type


def transcribe(
    config: ProviderConfig, model: str, audio: bytes, filename: str, media_type: str
) -> str:
    """Post one recording to ``{base_url}/audio/transcriptions`` and return its text."""
    endpoint = f"{config.base_url.rstrip('/')}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
    try:
        with httpx.Client(
            trust_env=not is_loopback_endpoint(config.base_url), timeout=_TIMEOUT_SECONDS
        ) as client:
            response = client.post(
                endpoint,
                headers=headers,
                files={"file": (filename, audio, media_type)},
                data={"model": model},
            )
    except httpx.HTTPError:
        raise TranscriptionError("transcription request failed") from None
    if response.status_code != 200:
        raise TranscriptionError(f"transcription endpoint returned HTTP {response.status_code}")
    if len(response.content) > _MAX_RESPONSE_BYTES:
        raise TranscriptionError("transcription response is too large")
    try:
        payload = response.json()
    except ValueError:
        raise TranscriptionError("transcription response is not JSON") from None
    text = payload.get("text") if isinstance(payload, dict) else None
    if not isinstance(text, str):
        raise TranscriptionError("transcription response has no text")
    return text.strip()[:_MAX_TRANSCRIPT_CHARS]
