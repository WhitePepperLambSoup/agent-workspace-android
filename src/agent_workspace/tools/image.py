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
