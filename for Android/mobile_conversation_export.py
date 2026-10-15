"""One conversation exported to share or keep: Markdown, a PDF, or long pictures.

Files go to the conversation's workspace under exports/, where the Files page lists them and the
console shares or saves them like any task output. Only what was said is exported (the user's
messages and the replies), not tool calls or hidden reasoning.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import time
from pathlib import Path
from typing import Any

FORMATS = ("md", "pdf", "image")
_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def conversation_markdown(title: str, events: list[Any]) -> str:
    """The conversation as Markdown: a title, then each message under who said it."""
    lines = [f"# {title}", "", f"_{time.strftime('%Y-%m-%d %H:%M')} · Agent Workspace_"]
    said, speaker = 0, None
    for event in events:
        data = getattr(event, "data", None) or {}
        kind = getattr(event, "type", "")
        role = data.get("role") if kind == "message.created" else ("user" if kind == "message.user" else
                                                                    "assistant" if kind == "message.assistant" else None)
        text = str(data.get("text") or data.get("content") or "").strip()
        if role not in ("user", "assistant") or not text:
            continue
        # Several replies in a row (notes between tool calls) sit under one heading.
        if role != speaker:
            lines += ["", "### 你" if role == "user" else "### Agent"]
            speaker = role
        lines += ["", text]
        said += 1
    if not said:
        lines += ["", "（这个对话还没有内容）"]
    return "\n".join(lines) + "\n"


def visible_events(events: list[Any]) -> list[Any]:
    """Drops the turns an edit or a regeneration replaced (context.rewound), as the console does."""
    shown: list[Any] = []
    for event in events:
        if getattr(event, "type", "") == "context.rewound":
            start = (getattr(event, "data", None) or {}).get("from_event_id")
            index = next((position for position, item in enumerate(shown) if getattr(item, "id", None) == start), None)
            if index is not None:
                del shown[index:]
            continue
        shown.append(event)
    return shown


def _file_stem(title: str) -> str:
    cleaned = _UNSAFE.sub(" ", title).strip(" .") or "conversation"
    return f"{cleaned[:40].strip()}-{time.strftime('%Y%m%d-%H%M%S')}"


async def export_conversation(workspace: str | Path, title: str, events: list[Any], fmt: str) -> dict[str, Any]:
    """Writes the export into <workspace>/exports and returns its workspace-relative paths."""
    if fmt not in FORMATS:
        raise ValueError(f"format must be one of {', '.join(FORMATS)}")
    root = Path(workspace)
    folder = root / "exports"
    folder.mkdir(parents=True, exist_ok=True)
    markdown = conversation_markdown(title or "Agent Workspace", visible_events(events))
    stem = _file_stem(title or "conversation")
    if fmt == "md":
        target = folder / f"{stem}.md"
        target.write_text(markdown, encoding="utf-8")
        return {"paths": [target.relative_to(root).as_posix()]}
    from android_adapter.documents import AndroidCreatePdfTool, WorkspacePaths, _Job

    tool = AndroidCreatePdfTool(root)
    pdf = f"exports/{stem}.pdf"
    await tool.execute({"path": pdf, "content": markdown, "format": "markdown", "expected_sha256": None})
    if fmt == "pdf":
        return {"paths": [pdf]}

    def pictures() -> list[str]:
        paths: list[str] = []
        with _Job(tool.bridge) as job:
            job.stage_from(WorkspacePaths(root), pdf)
            result = job.execute({"action": "long_image", "width": 1080})
            for index, output in enumerate(result.get("outputs") or [], start=1):
                source = job.output_path(output, f"long-{index}.jpg")
                name = f"{stem}.jpg" if len(result["outputs"]) == 1 else f"{stem}-{index}.jpg"
                shutil.copyfile(source, folder / name)
                paths.append(f"exports/{name}")
        return paths

    try:
        return {"paths": await asyncio.to_thread(pictures)}
    finally:
        # The PDF was only the way to the pictures.
        (root / pdf).unlink(missing_ok=True)
