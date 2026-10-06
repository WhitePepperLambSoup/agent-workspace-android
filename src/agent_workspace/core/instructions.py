from __future__ import annotations

from pathlib import Path

from agent_workspace.tools.paths import StrPath, WorkspacePathError, WorkspacePaths

# Files discovered at the workspace root and injected as project instructions,
# in priority order. Content is bounded and treated as untrusted context.
INSTRUCTION_FILENAMES = ("AGENTS.md", "CLAUDE.md", ".cursorrules", ".agent/instructions.md")

MAX_INSTRUCTION_BYTES = 64 * 1024
_SKIPPED_MARKERS = frozenset(
    {
        "node_modules",
        ".git",
        ".venv",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "dist",
        "build",
        "__pycache__",
    }
)


def discover_workspace_instructions(
    workspace: WorkspacePaths | StrPath,
    *,
    max_bytes: int = MAX_INSTRUCTION_BYTES,
) -> str:
    """Load bounded project instruction files from the workspace root.

    Follows the mainstream convention (AGENTS.md / CLAUDE.md / .cursorrules)
    so repositories keep their agent instructions where other tools expect
    them. Returns an empty string when no instruction file exists.
    """
    if max_bytes <= 0:
        raise ValueError("instruction byte limit must be positive")
    try:
        paths = workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
    except (WorkspacePathError, OSError, RuntimeError):
        return ""
    root = paths.root
    if not root.is_dir():
        return ""
    sections: list[str] = []
    total = 0
    for filename in INSTRUCTION_FILENAMES:
        try:
            candidate = paths.resolve(filename)
            if not candidate.is_file():
                continue
        except (WorkspacePathError, OSError):
            continue
        remaining = max_bytes - total
        if remaining <= 0:
            break
        try:
            with candidate.open("rb") as stream:
                raw = stream.read(remaining + 1)
        except OSError:
            continue
        truncated = len(raw) > remaining
        raw = raw[:remaining]
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            if not truncated:
                continue
            content = raw.decode("utf-8", errors="ignore")
        section = f"# Instructions from {filename}\n{content.strip()}\n"
        encoded = section.encode("utf-8")
        if truncated or total + len(encoded) > max_bytes:
            retained = encoded[:remaining].decode("utf-8", errors="ignore")
            sections.append(
                f"{retained}\n[workspace instructions truncated at the {max_bytes}-byte limit]"
            )
            break
        sections.append(section)
        total += len(encoded)
    return "".join(sections).strip()


def discover_skill_files(workspace: WorkspacePaths | StrPath) -> tuple[Path, ...]:
    """Return skill definition files under the workspace .agent/skills directory."""
    try:
        paths = workspace if isinstance(workspace, WorkspacePaths) else WorkspacePaths(workspace)
    except (WorkspacePathError, OSError, RuntimeError):
        return ()
    root = paths.root
    skills_dir = root / ".agent" / "skills"
    if not skills_dir.is_dir():
        return ()
    files: list[Path] = []
    for candidate in sorted(skills_dir.rglob("*.toml")):
        try:
            safe_candidate = paths.resolve(candidate)
        except (WorkspacePathError, OSError):
            continue
        if any(part in _SKIPPED_MARKERS for part in safe_candidate.relative_to(root).parts):
            continue
        files.append(safe_candidate)
    return tuple(files)
