from __future__ import annotations

import json
from pathlib import Path

from agent_workspace.tools.paths import StrPath

MAX_REPO_MAP_ENTRIES = 500
MAX_REPO_MAP_BYTES = 32 * 1024


def build_repo_map_context(
    workspace: StrPath,
    *,
    limit: int = 120,
) -> str:
    """Render a bounded top-level symbol outline for context injection.

    Uses the same extraction rules as the code_map tool so the injected
    orientation always matches what the agent can query with the tool.
    """
    if not 1 <= limit <= MAX_REPO_MAP_ENTRIES:
        raise ValueError("repo map entry limit must be from 1 to 500")
    from agent_workspace.tools.code_map import CodeMapTool

    root = Path(workspace)
    if not root.is_dir():
        return ""
    document = json.loads(
        CodeMapTool(root)._execute_sync(
            {
                "path": ".",
                "file_glob": "*",
                "max_results": limit,
                "max_files": 2000,
                "max_file_bytes": 262144,
            }
        )
    )
    entries = document.get("entries")
    if not isinstance(entries, list) or not entries:
        return ""
    lines: list[str] = []
    total = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        line = entry.get("line")
        kind = entry.get("kind")
        name = entry.get("name")
        if not all(isinstance(value, str) for value in (path, kind, name)) or not isinstance(
            line, int
        ):
            continue
        signature = entry.get("signature")
        suffix = f": {signature}" if isinstance(signature, str) and signature else ""
        rendered = f"{path}:{line} {kind} {name}{suffix}"
        encoded = rendered.encode("utf-8")
        if total + len(encoded) + 1 > MAX_REPO_MAP_BYTES:
            break
        lines.append(rendered)
        total += len(encoded) + 1
    return "# Workspace code map (top-level symbols)\n" + "\n".join(lines)
