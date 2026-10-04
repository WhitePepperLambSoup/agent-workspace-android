from __future__ import annotations

from pathlib import Path

from agent_workspace.core.instructions import discover_workspace_instructions
from agent_workspace.core.skills import load_skills, render_skills_context
from agent_workspace.tools.paths import StrPath


def resolve_workspace_prompt_context(
    workspace: StrPath | None,
    *,
    custom_system_suffix: str = "",
    include_instructions: bool = True,
    include_skills: bool = True,
    max_total_bytes: int = 64 * 1024,
) -> str:
    sections: list[str] = []

    if custom_system_suffix.strip():
        sections.append(custom_system_suffix.strip())

    if workspace is not None:
        try:
            root = Path(workspace).resolve()
        except (OSError, ValueError):
            root = None

        if root is not None and root.is_dir():
            if include_instructions and "# Workspace instructions" not in custom_system_suffix:
                instructions = discover_workspace_instructions(root)
                if instructions:
                    sections.append(instructions)

            if include_skills and "# Workspace skills" not in custom_system_suffix:
                try:
                    skills = load_skills(root)
                    if skills:
                        skills_context = render_skills_context(skills)
                        if skills_context:
                            sections.append(skills_context)
                except Exception:
                    pass

    combined = "\n\n".join(sections).strip()
    encoded = combined.encode("utf-8")
    if len(encoded) > max_total_bytes:
        combined = encoded[:max_total_bytes].decode("utf-8", errors="ignore").rstrip()
    return combined
