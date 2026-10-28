"""Skills on the desktop: instructions for particular kinds of job, used in every folder.

A skill is a folder with a ``SKILL.md`` file: YAML front matter with ``name`` and ``description``,
then the instructions in Markdown (the format the Android app and other agents use). The official
pack ships with the app (``desktop/skills/official``, adapted from the Android app's pack without
the skills that operate a phone); skills the user copies into ``<data>/skills`` are theirs. The
system prompt lists each enabled skill by name and description only; the agent reads one with the
use_skill tool when a request matches it, so many skills cost little context. Which skills are
turned off is kept in ``<data>/skills.json``. A skill only instructs the agent; its tool calls
still need the usual approvals.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.tools.base import ToolArgumentError, ToolError, json_result

OFFICIAL_PACK = "official"
USER_PACK = "user"
MANIFEST = "skill-pack.json"
MAX_INSTRUCTION_BYTES = 64 * 1024
MAX_READ_BYTES = 64 * 1024
MAX_DESCRIPTION = 1024
MAX_SKILLS = 200
# The skills section of the system prompt; descriptions past this are left out, names stay.
CATALOG_BYTES = 6 * 1024
_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
_TEXT_SUFFIXES = {
    ".md", ".markdown", ".txt", ".json", ".yaml", ".yml", ".toml", ".csv", ".tsv", ".xml",
    ".html", ".htm", ".css", ".js", ".mjs", ".ts", ".py", ".ps1", ".ini", ".cfg", ".sql", ".rst",
}  # fmt: skip


class SkillError(ValueError):
    """A problem the agent or the window reports as is."""


def bundled_skills_directory() -> Path:
    """Where the packs that ship with the app are: set by the window, else found beside the
    sidecar (packaged: resources/skills) or in the source tree (desktop/skills)."""
    configured = os.environ.get("AGENT_WORKSPACE_SKILLS_DIR")
    if configured:
        return Path(configured)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent / "skills"
    return Path(__file__).resolve().parents[3] / "desktop" / "skills"


# ----- SKILL.md --------------------------------------------------------------------------------


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        inner = value[1:-1]
        return inner.replace("''", "'") if value[0] == "'" else inner.replace('\\"', '"')
    return value


def _front_matter(lines: list[str]) -> dict[str, str]:
    """The YAML subset skills use: top-level ``key: value``, quoted values and ``|``/``>``
    blocks. Nested maps and lists are skipped."""
    result: dict[str, str] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line.strip() or line.lstrip().startswith("#") or line[:1] in " \t":
            continue
        key, separator, value = line.partition(":")
        if not separator or not re.fullmatch(r"[A-Za-z0-9_-]+", key.strip()):
            continue
        key, value = key.strip(), value.strip()
        if value in {"|", ">", "|-", ">-", "|+", ">+"}:
            block = []
            while index < len(lines) and (not lines[index].strip() or lines[index][:1] in " \t"):
                block.append(lines[index].strip())
                index += 1
            result[key] = ("\n" if value.startswith("|") else " ").join(block).strip()
        elif value:
            result[key] = _scalar(value)
    return result


def parse_skill_md(text: str) -> tuple[dict[str, str], str]:
    """Front matter and Markdown body of a SKILL.md file."""
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        raise SkillError("SKILL.md must start with front matter (--- name / description ---)")
    for end in range(1, min(len(lines), 400)):
        if lines[end].strip() in {"---", "..."}:
            return _front_matter(lines[1:end]), "\n".join(lines[end + 1 :]).strip()
    raise SkillError("SKILL.md front matter is not closed with ---")


def _read_text(path: Path, limit: int) -> str:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise SkillError(f"{path.name} is larger than {limit // 1024} KB")
    return data.decode("utf-8")


def _slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9._-]+", "-", text.strip().lower()).strip("-._")[:64].rstrip("-._")
    return value if _ID.fullmatch(value) else ""


def _skills_in(root: Path) -> list[dict[str, str]]:
    """Every readable SKILL.md below root (at most three folders down)."""
    found: list[dict[str, str]] = []
    if not root.is_dir():
        return found
    for document in sorted(root.rglob("*")):
        relative = document.relative_to(root)
        if (
            document.name.lower() != "skill.md"
            or len(relative.parts) > 4
            or any(part.startswith(".") for part in relative.parts)
            or not document.is_file()
            or document.is_symlink()
        ):
            continue
        try:
            meta, body = parse_skill_md(_read_text(document, MAX_INSTRUCTION_BYTES))
        except (SkillError, OSError, UnicodeDecodeError):
            continue
        name, description = meta.get("name", ""), meta.get("description", "")
        skill_id = _slug(name) or _slug(document.parent.name)
        if not name.strip() or not description.strip() or not body or not skill_id:
            continue
        # What the window shows: the instructions' first heading ("# AA 分账"), else the name.
        heading = next(
            (line[2:].strip() for line in body.splitlines() if line.startswith("# ")), ""
        )
        found.append(
            {
                "id": skill_id,
                "name": name.strip()[:200],
                "title": (heading or name.strip())[:200],
                "description": " ".join(description.split())[:MAX_DESCRIPTION],
                "folder": str(document.parent),
            }
        )
        if len(found) >= MAX_SKILLS:
            break
    return found


class SkillLibrary:
    """The official pack and the user's own skills, and which of them are turned off."""

    def __init__(self, bundled: Path, user: Path, state: Path) -> None:
        self.bundled = bundled
        self.user = user
        self.state = state
        self._lock = threading.Lock()

    def _official_pack(self) -> dict[str, str]:
        root = self.bundled / OFFICIAL_PACK
        try:
            manifest = json.loads(_read_text(root / MANIFEST, 64 * 1024))
        except (OSError, SkillError, UnicodeDecodeError, ValueError):
            manifest = {}
        if not isinstance(manifest, dict):
            manifest = {}
        return {
            "name": str(manifest.get("name") or "Agent Workspace"),
            "version": str(manifest.get("version") or ""),
            "description": str(manifest.get("description") or ""),
        }

    def _disabled(self) -> set[str]:
        try:
            document = json.loads(self.state.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            return set()
        disabled = document.get("disabled") if isinstance(document, dict) else None
        return (
            {item for item in disabled if isinstance(item, str)}
            if isinstance(disabled, list)
            else set()
        )

    def skills(self) -> list[dict[str, Any]]:
        """Every skill with the key the agent uses (the user's own take ``user/`` when an
        official skill has the same id) and whether it is on."""
        disabled = self._disabled()
        entries: list[dict[str, Any]] = []
        for pack, root in ((OFFICIAL_PACK, self.bundled / OFFICIAL_PACK), (USER_PACK, self.user)):
            taken = {entry["key"] for entry in entries}
            for skill in _skills_in(root):
                key = skill["id"] if skill["id"] not in taken else f"{pack}/{skill['id']}"
                if key in taken:
                    continue
                taken.add(key)
                entries.append({**skill, "key": key, "pack": pack, "enabled": key not in disabled})
        return entries

    def set_enabled(self, key: str, enabled: bool) -> list[dict[str, Any]]:
        with self._lock:
            entries = self.skills()
            if not any(entry["key"] == key for entry in entries):
                raise SkillError("unknown_skill")
            disabled = self._disabled() & {entry["key"] for entry in entries}
            if enabled:
                disabled.discard(key)
            else:
                disabled.add(key)
            self.state.parent.mkdir(parents=True, exist_ok=True)
            staging = self.state.with_name(f".{self.state.name}.tmp")
            staging.write_text(
                json.dumps({"version": 1, "disabled": sorted(disabled)}, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(staging, self.state)
        return self.skills()

    def document(self) -> dict[str, Any]:
        """What the Skills settings show."""
        pack = self._official_pack()
        return {
            "official": {**pack, "available": (self.bundled / OFFICIAL_PACK).is_dir()},
            "userFolder": str(self.user),
            "skills": [
                {
                    key: entry[key]
                    for key in ("key", "name", "title", "description", "pack", "enabled")
                }
                for entry in self.skills()
            ],
        }

    def open_user_folder(self) -> Path:
        """Create the user's skills folder and show it in Explorer."""
        self.user.mkdir(parents=True, exist_ok=True)
        startfile = getattr(os, "startfile", None)
        if startfile is None:
            raise SkillError("unsupported")
        startfile(self.user)
        return self.user

    def catalog_block(self) -> str:
        """The skills section of the system prompt: enabled skills by name and description."""
        enabled = [entry for entry in self.skills() if entry["enabled"]]
        if not enabled:
            return ""
        lines = [
            "# Skills",
            "Instructions for particular kinds of job. When a request matches one, call "
            "use_skill with its name first and follow what it says; the user's own words take "
            "precedence over a skill.",
        ]
        size = sum(len(line.encode("utf-8")) + 1 for line in lines)
        omitted: list[str] = []
        for entry in enabled:
            line = f"- {entry['key']}: {entry['description'][:300]}"
            if size + len(line.encode("utf-8")) + 1 > CATALOG_BYTES:
                omitted.append(entry["key"])
                continue
            lines.append(line)
            size += len(line.encode("utf-8")) + 1
        if omitted:
            lines.append("- Also available (no room for descriptions): " + ", ".join(omitted))
        return "\n".join(lines)

    def load(self, key: str, file: str | None = None) -> dict[str, Any]:
        """A skill's instructions and the names of its other files, or one of those files."""
        entries = [entry for entry in self.skills() if entry["enabled"]]
        entry = next((item for item in entries if item["key"] == key), None)
        if entry is None:
            named = [item for item in entries if item["name"].casefold() == key.casefold()]
            entry = named[0] if len(named) == 1 else None
        if entry is None:
            raise SkillError(
                f"no enabled skill {key!r}; the skills section lists the ones available"
            )
        folder = Path(entry["folder"]).resolve()
        if file is not None:
            target = (folder / file).resolve()
            if folder not in target.parents or not target.is_file() or target.is_symlink():
                raise SkillError(f"{file} is not a file of this skill")
            if target.suffix.lower() not in _TEXT_SUFFIXES:
                raise SkillError(f"{file} is not a text file")
            data = target.read_bytes()[: MAX_READ_BYTES + 1]
            return {
                "skill": entry["key"],
                "file": file,
                "truncated": len(data) > MAX_READ_BYTES,
                "content": data[:MAX_READ_BYTES].decode("utf-8", errors="replace"),
            }
        document = next(
            (path for path in folder.iterdir() if path.name.lower() == "skill.md"), None
        )
        if document is None:
            raise SkillError("the skill's SKILL.md is missing")
        _meta, body = parse_skill_md(_read_text(document, MAX_INSTRUCTION_BYTES))
        files = sorted(
            path.relative_to(folder).as_posix()
            for path in folder.rglob("*")
            if path.is_file()
            and path.name.lower() != "skill.md"
            and path.suffix.lower() in _TEXT_SUFFIXES
        )[:100]
        return {
            "skill": entry["key"],
            "name": entry["name"],
            "description": entry["description"],
            "instructions": body,
            "files": files,
        }


class UseSkillTool:
    """Reads a skill's instructions; it changes nothing, so it needs no approval."""

    _SPEC = ToolSpec(
        name="use_skill",
        description=(
            "Load a skill: instructions for a particular kind of job, listed in the skills "
            "section of the system prompt. Call it with the skill's name before doing such a job "
            "and follow what it says. With file, read one of the skill's other files (it lists "
            "them)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "skill": {"type": "string", "minLength": 1, "maxLength": 140},
                "file": {
                    "type": "string",
                    "maxLength": 300,
                    "description": "A file of the skill to read instead, as listed in its files",
                },
            },
            "required": ["skill"],
            "additionalProperties": False,
        },
        side_effect="none",
        capability=Capability.MEMORY_READ,
    )

    def __init__(self, library: SkillLibrary) -> None:
        self.library = library

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await asyncio.to_thread(self._load, arguments)

    def _load(self, arguments: dict[str, Any]) -> str:
        skill = arguments.get("skill")
        file = arguments.get("file")
        if not isinstance(skill, str) or not skill.strip() or len(skill) > 140:
            raise ToolArgumentError("'skill' must be the name of a skill")
        if file is not None and (not isinstance(file, str) or not file.strip() or len(file) > 300):
            raise ToolArgumentError("'file' must be one of the skill's files")
        try:
            return json_result(self.library.load(skill.strip(), file.strip() if file else None))
        except SkillError as exc:
            raise ToolError(str(exc)) from None
        except (OSError, UnicodeDecodeError):
            raise ToolError("the skill's files could not be read") from None
