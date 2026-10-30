"""A tour of a repository for someone new to it, written by the model from the module map, the
manifests and the README, and kept in the project as .agent/tour.md."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_workspace.config import ProviderConfig

from .model_call import ModelCallError, ask_model
from .repo_map import module_graph

TOUR_FILE = Path(".agent") / "tour.md"
TOUR_SECONDS = 180
MANIFESTS = (
    "README.md",
    "README.rst",
    "README.txt",
    "readme.md",
    "package.json",
    "pyproject.toml",
    "setup.cfg",
    "Cargo.toml",
    "go.mod",
    "requirements.txt",
)
_LANGUAGES = {
    "zh-CN": "Simplified Chinese",
    "zh-TW": "Traditional Chinese",
    "ja-JP": "Japanese",
    "en-US": "English",
}


class TourError(RuntimeError):
    pass


def _head(path: Path, chars: int) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text if len(text) <= chars else text[:chars] + "\n…"


def _package_json(path: Path) -> str:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(document, dict):
        return ""
    keep = {
        "name": document.get("name"),
        "description": document.get("description"),
        "main": document.get("main"),
        "scripts": document.get("scripts"),
        "dependencies": sorted(document.get("dependencies") or {}),
        "devDependencies": sorted(document.get("devDependencies") or {}),
    }
    return json.dumps(
        {key: value for key, value in keep.items() if value}, ensure_ascii=False, indent=1
    )


def tour_context(root: Path, graph: dict[str, Any]) -> str:
    """What the model is shown: the manifests, the map, and the start of the entry points."""
    parts = [f"Repository folder: {root.name}"]
    for name in MANIFESTS:
        path = root / name
        if path.is_file():
            body = (
                _package_json(path)
                if name == "package.json"
                else _head(path, 3000 if name.lower().startswith("readme") else 1500)
            )
            if body:
                parts.append(f"## {name}\n{body}")
    modules = sorted(
        graph.get("modules", []), key=lambda item: (-int(item["usedBy"]), str(item["id"]))
    )
    parts.append(
        f"## Code: {graph.get('files', 0)} files; "
        f"languages {json.dumps(graph.get('languages', {}))}\n"
        "Modules (folder: files, lines, used by N modules, uses N; files others use most):\n"
        + "\n".join(
            f"- {item['id']}: {item['files']} files, {item['lines']} lines, "
            f"used by {item['usedBy']}, "
            f"uses {item['uses']}; {', '.join(item['keyFiles'][:4])}"
            for item in modules
        )
    )
    edges = sorted(graph.get("edges", []), key=lambda edge: -int(edge["weight"]))[:100]
    parts.append(
        "Which module uses which (imports):\n"
        + "\n".join(f"- {e['from']} -> {e['to']} ({e['weight']})" for e in edges)
    )
    if graph.get("cycles"):
        parts.append(
            "Modules that use one another in a circle:\n"
            + "\n".join(", ".join(cycle) for cycle in graph["cycles"])
        )
    if graph.get("externals"):
        parts.append(
            "Outside packages most imported: "
            + ", ".join(f"{item['name']} ({item['uses']})" for item in graph["externals"])
        )
    for entry in graph.get("entryPoints", [])[:4]:
        head = _head(root / entry, 1800)
        if head:
            parts.append(f"## Entry point {entry} (start)\n{head}")
    return "\n\n".join(parts)


def write_tour(config: ProviderConfig, root: Path, language: str = "en-US") -> dict[str, object]:
    graph = module_graph(root)
    if not graph.get("files"):
        raise TourError("tour_no_code")
    system = (
        "You write the tour of a code repository for a developer who is new to it and wants to "
        f"find their way in an afternoon. Write in {_LANGUAGES.get(language, 'English')}, in "
        "Markdown with headings: what the project is and does; how it is laid out (the modules "
        "in the order to read them, each with its role and the files to start with, as paths); "
        "how a run or a request goes through it, from the entry points; the outside packages "
        "that matter and what they are used for; where to start for common changes; and what "
        "to watch for (modules that depend on each other in a circle, very large modules). "
        "Use the module names and file paths exactly as given and do not invent any. About 900 "
        "words. Begin with a level-1 heading naming the repository."
    )
    try:
        text = ask_model(
            config,
            system,
            tour_context(root, graph),
            max_output_tokens=4096,
            seconds=TOUR_SECONDS,
            temperature=0.3,
            error_prefix="tour",
        )
    except ModelCallError as error:
        raise TourError(str(error)) from None
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    if not text:
        raise TourError("tour_empty")
    destination = root / TOUR_FILE
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text + "\n", encoding="utf-8")
    return read_tour(root)


def read_tour(root: Path) -> dict[str, object]:
    path = root / TOUR_FILE
    try:
        return {
            "text": path.read_text(encoding="utf-8"),
            "path": TOUR_FILE.as_posix(),
            "written": path.stat().st_mtime,
        }
    except OSError:
        return {"text": None, "path": TOUR_FILE.as_posix(), "written": None}


__all__ = ["TOUR_FILE", "TourError", "read_tour", "tour_context", "write_tour"]
