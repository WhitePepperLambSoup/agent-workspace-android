from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from agent_workspace.core.instructions import discover_skill_files

StrPath = str | Path

_SKILL_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
MAX_SKILL_CONTEXT_BYTES = 24 * 1024


class SkillError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Skill:
    id: str
    name: str
    description: str
    instructions: str
    path: str

    @property
    def context_header(self) -> str:
        return (
            f"# Available skill: {self.name} ({self.id})\n"
            f"{self.description.strip()}\n\n## Skill instructions\n{self.instructions.strip()}"
        )


def load_skills(workspace: StrPath) -> tuple[Skill, ...]:
    """Load bounded skill definitions from .agent/skills/*.toml in the workspace."""
    skills: list[Skill] = []
    for path in discover_skill_files(workspace):
        try:
            with path.open("rb") as stream:
                raw: object = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
            raise SkillError(f"cannot read skill file {path}: {exc}") from None
        if not isinstance(raw, dict):
            raise SkillError(f"skill file {path} must contain a table")
        skill_id = raw.get("id")
        name = raw.get("name")
        description = raw.get("description")
        instructions = raw.get("instructions")
        if (
            not isinstance(skill_id, str)
            or _SKILL_ID_PATTERN.fullmatch(skill_id) is None
            or not isinstance(name, str)
            or not name.strip()
            or len(name) > 200
            or not isinstance(description, str)
            or not description.strip()
            or len(description) > 4000
            or not isinstance(instructions, str)
            or not instructions.strip()
            or len(instructions.encode("utf-8")) > MAX_SKILL_CONTEXT_BYTES
        ):
            raise SkillError(f"skill file {path} contains invalid fields")
        if any(skill.id == skill_id for skill in skills):
            raise SkillError(f"skill id {skill_id!r} is duplicated")
        skills.append(
            Skill(
                id=skill_id,
                name=name.strip(),
                description=description.strip(),
                instructions=instructions.strip(),
                path=str(path),
            )
        )
    return tuple(skills)


def render_skills_context(skills: tuple[Skill, ...], *, max_bytes: int = 16 * 1024) -> str:
    if not skills:
        return ""
    if max_bytes <= 0:
        return ""

    # Build catalog header so all skills remain discoverable even under tight budgets
    catalog_lines = ["# Workspace skills", "", "Available skills:"]
    for skill in skills:
        catalog_lines.append(f"- {skill.name} ({skill.id}): {skill.description.strip()}")
    catalog_lines.append("")
    catalog_str = "\n".join(catalog_lines) + "\n"
    catalog_bytes = catalog_str.encode("utf-8")

    if len(catalog_bytes) >= max_bytes:
        truncated = catalog_bytes[:max_bytes].decode("utf-8", errors="ignore")
        return truncated.rstrip()

    budget = max_bytes - len(catalog_bytes)
    sections: list[str] = [catalog_str]

    for skill in skills:
        full_section = f"{skill.context_header}\n\n"
        full_bytes = full_section.encode("utf-8")
        if len(full_bytes) <= budget:
            sections.append(full_section)
            budget -= len(full_bytes)
        else:
            # Skill instructions cannot fit entirely within remaining budget.
            # Emit an omission notice and continue processing subsequent smaller skills.
            instr_len = len(skill.instructions.encode("utf-8"))
            note = (
                f"# Available skill: {skill.name} ({skill.id})\n"
                f"{skill.description.strip()}\n\n"
                f"## Skill instructions\n"
                f"[Skill instructions omitted: content ({instr_len} bytes) "
                f"exceeds remaining context budget ({budget} bytes)]\n\n"
            )
            note_bytes = note.encode("utf-8")
            if len(note_bytes) <= budget:
                sections.append(note)
                budget -= len(note_bytes)

    return "".join(sections).strip()
