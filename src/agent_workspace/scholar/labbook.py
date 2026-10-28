"""The folder's lab notebook: dated entries in Markdown, one file a month (lab-notebook/2026-10.md),
written by the agent when the user records an experiment, and searched later."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_workspace.application.ports import ToolExecutionContext
from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.scholar.literature_tools import write_checkpointed
from agent_workspace.tools.base import ToolArgumentError, json_result, validate_tool_arguments
from agent_workspace.tools.filesystem import WriteFileTool
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths

FOLDER = "lab-notebook"
_ENTRY = re.compile(r"^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) · (.+)$", re.MULTILINE)
_MAX_TEXT = 20_000


def month_file(when: datetime) -> str:
    return f"{FOLDER}/{when:%Y-%m}.md"


def format_entry(when: datetime, title: str, text: str, tags: list[str], files: list[str]) -> str:
    lines = [f"## {when:%Y-%m-%d %H:%M} · {title.strip()}"]
    if tags:
        lines.append(
            "Tags: " + " ".join(f"#{tag.strip().lstrip('#').replace(' ', '-')}" for tag in tags)
        )
    lines.extend(["", text.strip(), ""])
    if files:
        lines.append("Files: " + ", ".join(f"`{name}`" for name in files))
        lines.append("")
    return "\n".join(lines) + "\n"


def entries(text: str, file: str) -> list[dict[str, Any]]:
    """The entries of one month file: date, title, tags, body."""
    found = list(_ENTRY.finditer(text))
    out: list[dict[str, Any]] = []
    for index, match in enumerate(found):
        end = found[index + 1].start() if index + 1 < len(found) else len(text)
        body = text[match.end() : end].strip()
        tags = re.findall(r"#([\w\-]+)", body.splitlines()[0]) if body.startswith("Tags:") else []
        out.append(
            {
                "date": match.group(1),
                "title": match.group(2).strip(),
                "tags": tags,
                "file": file,
                "line": text.count("\n", 0, match.start()) + 1,
                "text": body,
            }
        )
    return out


class LabNotebookAddTool:
    def __init__(self, workspace: Path, writer: WriteFileTool) -> None:
        self.paths = WorkspacePaths(workspace)
        self.writer = writer
        self._spec = ToolSpec(
            name="lab_notebook_add",
            description=(
                "Add a dated entry to the folder's lab notebook (lab-notebook/YYYY-MM.md, one "
                "Markdown file a month): what was done, settings, observations, results, problems. "
                "Use it when the user records an experiment or asks to note something for later. "
                "Write what happened, not plans; quote numbers as measured. files lists related "
                "files of the folder (data, figures, scripts)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "minLength": 1, "maxLength": 200},
                    "text": {"type": "string", "minLength": 1, "maxLength": _MAX_TEXT},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 40},
                        "maxItems": 12,
                    },
                    "files": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 300},
                        "maxItems": 30,
                    },
                },
                "required": ["title", "text"],
                "additionalProperties": False,
            },
            side_effect="write",
            capability=Capability.WORKSPACE_WRITE,
            durable_preimage_checkpoint=True,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, arguments: dict[str, Any]) -> str:
        raise ToolArgumentError("lab_notebook_add runs inside a conversation")

    async def execute_with_context(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> str:
        validate_tool_arguments(self._spec, arguments)
        when = datetime.now().astimezone()
        files: list[str] = []
        for raw in arguments.get("files") or []:
            try:
                files.append(self.paths.relative(raw))
            except WorkspacePathError:
                raise ToolArgumentError(f"{raw} is not a file of the folder") from None
        relative = month_file(when)
        target = self.paths.resolve(relative)
        current = (
            await asyncio.to_thread(target.read_text, encoding="utf-8") if target.is_file() else ""
        )
        if not current:
            current = f"# Lab notebook {when:%Y-%m}\n\n"
        entry = format_entry(
            when, arguments["title"], arguments["text"], list(arguments.get("tags") or []), files
        )
        written = await write_checkpointed(
            self.writer, self.paths, relative, current.rstrip("\n") + "\n\n" + entry, context
        )
        return json_result({"path": written["path"], "date": f"{when:%Y-%m-%d %H:%M}"})


class LabNotebookSearchTool:
    def __init__(self, workspace: Path) -> None:
        self.paths = WorkspacePaths(workspace)
        self._spec = ToolSpec(
            name="lab_notebook_search",
            description=(
                "Find entries of the folder's lab notebook by words, tag or month (YYYY-MM); "
                "without a query, the latest entries. Returns each entry's date, title, tags, "
                "file and line, and its text."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "maxLength": 200},
                    "month": {"type": "string", "pattern": r"^\d{4}-\d{2}$"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "additionalProperties": False,
            },
            side_effect="read",
            capability=Capability.WORKSPACE_READ,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def _search(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._spec, arguments)
        folder = self.paths.resolve(FOLDER)
        month = arguments.get("month")
        files = sorted(folder.glob(f"{month or '*'}.md"), reverse=True) if folder.is_dir() else []
        words = [word.casefold().lstrip("#") for word in str(arguments.get("query") or "").split()]
        found: list[dict[str, Any]] = []
        for file in files:
            for entry in reversed(
                entries(file.read_text(encoding="utf-8"), self.paths.relative(file))
            ):
                haystack = f"{entry['title']} {entry['text']}".casefold()
                if all(word in haystack for word in words):
                    found.append({**entry, "text": entry["text"][:4000]})
        limit = int(arguments.get("limit") or 10)
        return json_result({"entries": found[:limit], "count": len(found)})

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await asyncio.to_thread(self._search, arguments)
