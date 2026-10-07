from __future__ import annotations

import base64
import contextlib
import os
import subprocess
from typing import TYPE_CHECKING, Any

import httpx

from agent_workspace.core.models import Capability, ToolSpec

from .base import ToolArgumentError, ToolError, json_result, require_string
from .command import _resolve_system_shell
from .paths import StrPath, WorkspacePaths
from .process_worker import run_in_process

if TYPE_CHECKING:
    from agent_workspace.application.ports import ToolExecutionContext

_MAX_SPEAK_CHARS = 2000
_SPEAK_TIMEOUT_SECONDS = 120
_SPEAK_ERROR_CHARS = 500
_MAX_AUDIO_BYTES = 25 * 1024 * 1024
_MAX_TRANSCRIBE_RESPONSE_BYTES = 2 * 1024 * 1024
_TRANSCRIBE_TIMEOUT_SECONDS = 120.0
_DEFAULT_TRANSCRIBE_MODEL = "whisper-1"
_SPEAK_SCRIPT = (
    "Add-Type -AssemblyName System.Speech; "
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "$t = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[0])); "
    "$s.Speak($t); "
    "$s.Dispose()"
)
_AUDIO_MIME_TYPES: dict[str, str] = {
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
}


def _speak_sync(text: str) -> str:
    """Speak text through the Windows SAPI synthesizer in a fresh PowerShell process."""
    if os.name != "nt":
        raise ToolError("speak_text is only available on Windows")
    # PowerShell's console input uses the OEM codepage, so UTF-8 text cannot travel
    # through stdin safely; the Base64-encoded text travels as a positional argument
    # instead and is decoded inside the script.
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    arguments = [
        str(_resolve_system_shell("powershell")),
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        _SPEAK_SCRIPT,
        encoded,
    ]
    try:
        process = subprocess.Popen(
            arguments,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except OSError as exc:
        raise ToolError("cannot start PowerShell for speech synthesis") from exc
    try:
        stderr_bytes = process.communicate(timeout=_SPEAK_TIMEOUT_SECONDS)[1]
    except subprocess.TimeoutExpired:
        process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.communicate(timeout=2)
        raise ToolError("speech synthesis timed out") from None
    if process.returncode != 0:
        detail = stderr_bytes.decode("utf-8", errors="replace").strip()[:_SPEAK_ERROR_CHARS]
        raise ToolError(f"speech synthesis failed: {detail or f'exit code {process.returncode}'}")
    return json_result({"spoken": True, "chars": len(text)})


class SpeakTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="speak_text",
        description="Read a bounded text aloud using the Windows text-to-speech engine.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "minLength": 1, "maxLength": _MAX_SPEAK_CHARS},
            },
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
        if len(text) > _MAX_SPEAK_CHARS:
            raise ToolArgumentError(f"'text' exceeds the {_MAX_SPEAK_CHARS}-character limit")
        if os.name != "nt":
            raise ToolError("speak_text is only available on Windows")
        # The worker is attached to a Job Object with a single active process
        # limit, so the PowerShell child must be explicitly allowed.
        return await run_in_process(_speak_sync, text, allow_children=True)

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        _context: ToolExecutionContext | None,
    ) -> str:
        return await self.execute(arguments)


def _audio_mime(suffix: str) -> str | None:
    return _AUDIO_MIME_TYPES.get(suffix.casefold())


def _has_valid_audio_signature(data: bytes, suffix: str) -> bool:
    if suffix == ".mp3":
        return data.startswith(b"ID3") or data.startswith(b"\xff\xfb")
    if suffix == ".wav":
        return data.startswith(b"RIFF")
    if suffix == ".ogg":
        return data.startswith(b"OggS")
    if suffix == ".flac":
        return data.startswith(b"fLaC")
    if suffix == ".m4a":
        return len(data) >= 8 and data[4:8] == b"ftyp"
    return False


def _transcribe_endpoint() -> str:
    base_url = os.environ.get("AGENT_WORKSPACE_AUDIO_BASE_URL")
    if not base_url:
        raise ToolError("transcription endpoint is not configured")
    return f"{base_url.rstrip('/')}/audio/transcriptions"


class TranscribeTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="transcribe_audio",
        description=(
            "Transcribe a bounded audio file (mp3/m4a/wav/ogg/flac, ≤25 MiB) using an "
            "OpenAI-compatible /v1/audio/transcriptions endpoint "
            "(requires AGENT_WORKSPACE_AUDIO_BASE_URL; AGENT_WORKSPACE_AUDIO_API_KEY and "
            "AGENT_WORKSPACE_AUDIO_MODEL are optional)."
        ),
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "minLength": 1}},
            "required": ["path"],
            "additionalProperties": False,
        },
        side_effect="network",
        capability=Capability.NETWORK_READ,
    )

    def __init__(
        self,
        workspace: WorkspacePaths | StrPath,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.paths = (
            workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
        )
        self._client = client

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await self.execute_with_context(arguments, None)

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        _context: ToolExecutionContext | None,
    ) -> str:
        raw_path = require_string(arguments, "path")
        resolved = self.paths.resolve(raw_path)
        if not resolved.is_file():
            raise ToolError(f"path is not a file: {resolved}")
        suffix = resolved.suffix.casefold()
        mime = _audio_mime(suffix)
        if mime is None:
            raise ToolError(f"unsupported audio extension: {suffix or resolved.name}")
        try:
            size = resolved.stat().st_size
        except OSError as exc:
            raise ToolError(f"cannot inspect audio file: {resolved}") from exc
        if size > _MAX_AUDIO_BYTES:
            raise ToolError("audio file exceeds the 25 MiB limit")
        try:
            data = resolved.read_bytes()
        except OSError as exc:
            raise ToolError(f"cannot read audio file: {resolved}") from exc
        if not _has_valid_audio_signature(data, suffix):
            raise ToolError(
                f"audio file content does not match extension {suffix}: {resolved.name}"
            )
        endpoint = _transcribe_endpoint()
        model = os.environ.get("AGENT_WORKSPACE_AUDIO_MODEL") or _DEFAULT_TRANSCRIBE_MODEL
        api_key = os.environ.get("AGENT_WORKSPACE_AUDIO_API_KEY")
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        client = self._client if self._client is not None else httpx.AsyncClient(trust_env=False)
        try:
            try:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    files={"file": (resolved.name, data, mime)},
                    data={"model": model},
                    timeout=_TRANSCRIBE_TIMEOUT_SECONDS,
                )
            except httpx.HTTPError as exc:
                raise ToolError("transcription request failed") from exc
            if response.status_code != 200:
                raise ToolError(
                    f"transcription endpoint returned HTTP status {response.status_code}"
                )
            declared = response.headers.get("content-length")
            if declared is not None:
                try:
                    declared_bytes = int(declared)
                except ValueError:
                    declared_bytes = None
                if declared_bytes is not None and declared_bytes > _MAX_TRANSCRIBE_RESPONSE_BYTES:
                    raise ToolError("transcription endpoint response exceeds the size limit")
            if len(response.content) > _MAX_TRANSCRIBE_RESPONSE_BYTES:
                raise ToolError("transcription endpoint response exceeds the size limit")
            try:
                payload = response.json()
            except ValueError as exc:
                raise ToolError("transcription endpoint returned invalid JSON") from exc
            if not isinstance(payload, dict):
                raise ToolError("transcription endpoint returned an invalid payload")
            text = payload.get("text")
            if not isinstance(text, str) or not text:
                raise ToolError("transcription endpoint returned no text")
        finally:
            if self._client is None:
                await client.aclose()
        return json_result({"path": self.paths.relative(resolved), "text": text})
