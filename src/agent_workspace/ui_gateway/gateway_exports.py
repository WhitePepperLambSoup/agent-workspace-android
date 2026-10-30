"""Save an answer as a file of the open folder (exports/): Word or Markdown. The window prints
PDFs itself, from the answer as it shows it."""

from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from agent_workspace.tools.office_formats import markdown_docx
from agent_workspace.tools.paths import WorkspacePaths
from agent_workspace.ui_gateway.gateway_common import GatewayError, GatewayReply
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import CommandEnvelope

EXPORT_COMMANDS = frozenset({"answer.export"})
EXPORT_FOLDER = "exports"
_MAX_MARKDOWN = 2 * 1024 * 1024


def export_name(title: str, suffix: str, now: datetime | None = None) -> str:
    """A file name from the answer's title (letters of any script, digits, dashes) and the time."""
    words = re.sub(r"[^\w]+", "-", title.strip(), flags=re.UNICODE).strip("-_")[:40] or "answer"
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return f"{words}-{stamp}{suffix}"


class ExportCommands(GatewayState):
    def _export_command(self, command: CommandEnvelope) -> GatewayReply:
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        self._require_payload(command, {"format", "markdown"}, optional={"title"})
        payload = command.payload
        kind, markdown, title = payload["format"], payload["markdown"], payload.get("title", "")
        if (
            kind not in {"docx", "md"}
            or not isinstance(markdown, str)
            or not isinstance(title, str)
        ):
            raise GatewayError("invalid_payload")
        if not markdown.strip() or len(markdown) > _MAX_MARKDOWN or len(title) > 300:
            raise GatewayError("invalid_payload")
        with self._lock:
            workspace = self._workspace
        if workspace is None:
            raise GatewayError("runtime_unconfigured")
        paths = WorkspacePaths(workspace)
        folder = paths.resolve(EXPORT_FOLDER)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            target = unused(folder / export_name(title or markdown.splitlines()[0], f".{kind}"))
            data = markdown_docx(markdown, title) if kind == "docx" else markdown.encode("utf-8")
            write_new(target, data)
        except OSError:
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "answer.export.result",
            {"path": paths.relative(target), "bytes": len(data)},
            session_id=None,
        )


def unused(target: Path) -> Path:
    """target, or target-2, -3 … when a file of that name is there (two saves in one second)."""
    candidate, number = target, 2
    while candidate.exists():
        candidate = target.with_name(f"{target.stem}-{number}{target.suffix}")
        number += 1
    return candidate


def write_new(target: Path, data: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".export-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
