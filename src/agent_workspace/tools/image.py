from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from agent_workspace.core.events import Event
from agent_workspace.core.models import (
    MAX_IMAGE_BYTES,
    BinaryArtifact,
    Capability,
    ToolSpec,
)
from agent_workspace.tools.base import ToolError, json_result, require_string
from agent_workspace.tools.paths import StrPath, WorkspacePaths

if TYPE_CHECKING:
    from agent_workspace.application.ports import ToolExecutionContext

_IMAGE_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def _detect_media_type(data: bytes) -> str | None:
    for magic, media_type in _IMAGE_MAGIC:
        if data.startswith(magic):
            return media_type
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def image_structure_problem(data: bytes, media_type: str) -> str | None:
    """Why ``data`` is not a well-formed image of ``media_type``, or None when it is.

    Matching the first bytes is not enough: a truncated download or a hand-written file passes
    that check, is sent to the provider, and the provider then rejects every later request in
    the conversation. These checks are structural (no pixel decoding) and cheap.
    """
    try:
        if media_type == "image/png":
            return _png_problem(data)
        if media_type == "image/jpeg":
            return _jpeg_problem(data)
        if media_type == "image/gif":
            width, height = int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
            if len(data) < 14 or not width or not height:
                return "GIF has no image size"
            return None if data.rstrip(b"\x00").endswith(b";") else "GIF is truncated"
        if media_type == "image/webp":
            declared = int.from_bytes(data[4:8], "little")
            if declared < 12 or declared + 8 > len(data) or data[12:16] not in {b"VP8 ", b"VP8L", b"VP8X"}:
                return "WebP container is truncated or malformed"
            return None
    except (IndexError, ValueError):
        return "image structure is malformed"
    return "unsupported image type"


def _png_problem(data: bytes) -> str | None:
    import zlib

    position, seen = 8, []
    while position + 12 <= len(data):
        length = int.from_bytes(data[position:position + 4], "big")
        kind = data[position + 4:position + 8]
        end = position + 12 + length
        if length > 0x7FFFFFFF or end > len(data):
            return "PNG is truncated"
        crc = int.from_bytes(data[end - 4:end], "big")
        if zlib.crc32(data[position + 4:end - 4]) & 0xFFFFFFFF != crc:
            return f"PNG chunk {kind.decode('latin-1', 'replace')} has a bad checksum"
        if not seen:
            if kind != b"IHDR" or length != 13:
                return "PNG does not start with an image header"
            width = int.from_bytes(data[position + 8:position + 12], "big")
            height = int.from_bytes(data[position + 12:position + 16], "big")
            if not width or not height:
                return "PNG has no image size"
        seen.append(kind)
        position = end
        if kind == b"IEND":
            break
    if b"IDAT" not in seen:
        return "PNG has no image data"
    return None if seen and seen[-1] == b"IEND" else "PNG is truncated"


def _jpeg_problem(data: bytes) -> str | None:
    position, frame = 2, False
    while position + 4 <= len(data):
        if data[position] != 0xFF:
            return "JPEG markers are malformed"
        marker = data[position + 1]
        if marker == 0xFF:
            position += 1
            continue
        if marker in {0x01, *range(0xD0, 0xD8)}:
            position += 2
            continue
        length = int.from_bytes(data[position + 2:position + 4], "big")
        if length < 2 or position + 2 + length > len(data):
            return "JPEG is truncated"
        if marker in {*range(0xC0, 0xC4), *range(0xC5, 0xC8), *range(0xC9, 0xCC), *range(0xCD, 0xD0)}:
            height = int.from_bytes(data[position + 5:position + 7], "big")
            width = int.from_bytes(data[position + 7:position + 9], "big")
            if not width or not height:
                return "JPEG has no image size"
            frame = True
        if marker == 0xDA:
            if not frame:
                return "JPEG has no frame header"
            return None if b"\xff\xd9" in data[position:] else "JPEG is truncated"
        position += 2 + length
    return "JPEG has no image data"


class AttachImageTool:
    """Attach a workspace image to the conversation so the model can see it."""

    hard_cancellable = True
    _SPEC = ToolSpec(
        name="attach_image",
        description=(
            "Attach a workspace image (PNG, JPEG, WebP, or GIF, up to 5 MiB) so the model "
            "can inspect it visually. Returns the image digest and media type; the image is "
            "sent to the provider with the next request."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1},
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
        raise ToolError("attach_image requires the current session context")

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext,
    ) -> str:
        raw_path = require_string(arguments, "path")
        path = self.paths.resolve(raw_path)
        try:
            if path.is_dir():
                raise ToolError(f"path is a directory: {path}")
            data = path.read_bytes()
        except OSError as exc:
            raise ToolError(f"cannot read image: {path}") from exc
        if not data:
            raise ToolError(f"image is empty: {path}")
        if len(data) > MAX_IMAGE_BYTES:
            raise ToolError(f"image exceeds the {MAX_IMAGE_BYTES}-byte limit: {path}")
        media_type = _detect_media_type(data)
        if media_type is None:
            raise ToolError("file is not a supported PNG/JPEG/WebP/GIF image")
        problem = image_structure_problem(data, media_type)
        if problem is not None:
            raise ToolError(
                f"{problem}; the file was not attached. Re-create or re-download the image "
                "with a real image tool before attaching it."
            )
        digest = hashlib.sha256(data).hexdigest()
        if context.record_artifact is not None:
            await context.record_artifact(BinaryArtifact(digest, data))
        else:
            raise ToolError("attach_image requires artifact recording support")
        await context.record_event(
            Event(
                session_id=context.session_id,
                type="image.attached",
                data={
                    "attempt_id": context.attempt_id,
                    "path": self.paths.relative(path),
                    "media_type": media_type,
                    "sha256": digest,
                    "bytes": len(data),
                },
                causation_id=context.started_event_id,
                correlation_id=context.correlation_id,
            )
        )
        return json_result(
            {
                "path": self.paths.relative(path),
                "media_type": media_type,
                "bytes": len(data),
                "sha256": digest,
            }
        )
