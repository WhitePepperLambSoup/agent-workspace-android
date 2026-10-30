"""The map of a repository for its tour: which modules (folders of code) there are and which use
which, from the imports of its Python and JavaScript/TypeScript files."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts"}
JS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
SKIPPED = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "dist",
    "build",
    "out",
    ".next",
    ".nuxt",
    "coverage",
    ".agent",
    ".idea",
    ".vscode",
    "target",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "site-packages",
    ".tox",
    "vendor",
}
MAX_FILES = 6000
MAX_FILE_BYTES = 400_000
MAX_GROUPS = 40
_PY_IMPORT = re.compile(
    r"^\s*(?:from\s+(\.*[\w.]*)\s+import\s+([\w*, ()]+)|import\s+([\w., ]+))", re.M
)
_JS_IMPORT = re.compile(
    r"""(?:import\s[^'"]*?from\s*|import\s*\(\s*|require\s*\(\s*|export\s[^'"]*?from\s*|import\s+)['"]([^'"\n]+)['"]"""
)
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_STDLIB = frozenset(sys.stdlib_module_names) | {"__future__"}


def list_code_files(root: Path) -> list[str]:
    """The code files of the repository (as git lists them when it is one), relative, posix."""
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            # Never the gateway's own stdin: a child given a pipe another thread is reading
            # waits at start until that read ends (Windows).
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=20,
            check=False,
            creationflags=_NO_WINDOW,
        )
        if listed.returncode == 0:
            paths = [p for p in listed.stdout.decode("utf-8", "replace").split("\0") if p]
            return [
                p
                for p in paths
                if PurePosixPath(p).suffix in CODE_SUFFIXES
                and not SKIPPED.intersection(PurePosixPath(p).parts)
            ][:MAX_FILES]
    except (OSError, subprocess.TimeoutExpired):
        pass
    found: list[str] = []
    for folder, directories, files in os.walk(root):
        directories[:] = sorted(
            d for d in directories if d not in SKIPPED and not d.startswith(".")
        )
        for name in sorted(files):
            if Path(name).suffix in CODE_SUFFIXES:
                found.append(Path(folder, name).relative_to(root).as_posix())
                if len(found) >= MAX_FILES:
                    return found
    return found


@dataclass
class RepoMap:
    files: list[str]
    lines: dict[str, int] = field(default_factory=dict)
    # File-level imports inside the repository, and the packages from outside it.
    links: dict[str, set[str]] = field(default_factory=dict)
    externals: Counter[str] = field(default_factory=Counter)


def _python_roots(files: Iterable[str]) -> list[str]:
    """Folders Python imports are resolved from: the repository and its src-like folders."""
    roots = {""}
    for path in files:
        parts = PurePosixPath(path).parts
        for index, part in enumerate(parts[:-1]):
            if part in {"src", "lib", "python"}:
                roots.add("/".join(parts[: index + 1]))
    return sorted(roots, key=len, reverse=True)


def _resolve_python(module: str, origin: str, known: set[str], roots: list[str]) -> str | None:
    if module.startswith("."):
        dots = len(module) - len(module.lstrip("."))
        base = PurePosixPath(origin).parent
        for _ in range(dots - 1):
            base = base.parent
        rest = module.lstrip(".")
        candidates = [str(base / rest.replace(".", "/")) if rest else str(base)]
    else:
        candidates = [
            f"{root}/{module.replace('.', '/')}" if root else module.replace(".", "/")
            for root in roots
        ]
    for candidate in candidates:
        candidate = candidate.lstrip("./") if candidate not in {".", ""} else ""
        for option in (f"{candidate}.py", f"{candidate}/__init__.py"):
            if option.lstrip("/") in known:
                return option.lstrip("/")
    return None


def _resolve_js(specifier: str, origin: str, known: set[str]) -> str | None:
    base = PurePosixPath(origin).parent / specifier
    normalized = os.path.normpath(str(base)).replace("\\", "/")
    stem = re.sub(r"\.(js|jsx|mjs|cjs)$", "", normalized)
    for option in (
        normalized,
        *(f"{stem}{suffix}" for suffix in JS_SUFFIXES),
        *(f"{normalized}/index{suffix}" for suffix in JS_SUFFIXES),
    ):
        if option in known:
            return option
    return None


def build_map(root: Path, files: list[str] | None = None) -> RepoMap:
    files = files if files is not None else list_code_files(root)
    known = set(files)
    roots = _python_roots(files)
    result = RepoMap(files=files)
    for path in files:
        try:
            data = (root / path).read_bytes()[:MAX_FILE_BYTES]
        except OSError:
            continue
        text = data.decode("utf-8", errors="replace")
        result.lines[path] = text.count("\n") + 1
        targets: set[str] = set()
        if path.endswith(".py"):
            for found in _PY_IMPORT.finditer(text):
                if found.group(1) is not None:
                    module, names = found.group(1), found.group(2)
                    hit = _resolve_python(module, path, known, roots)
                    # `from package import module` names a module as often as a function.
                    submodules = {
                        _resolve_python(
                            f"{module}.{name}" if module.strip(".") else f"{module}{name}",
                            path,
                            known,
                            roots,
                        )
                        for name in re.findall(r"\w+", names)
                    } - {None}
                    targets.update(str(sub) for sub in submodules)
                    # The package itself only when what is imported from it are not its modules.
                    if submodules:
                        pass
                    elif hit:
                        targets.add(hit)
                    elif not module.startswith(".") and module.split(".")[0] not in _STDLIB:
                        result.externals[module.split(".")[0]] += 1
                else:
                    for module in re.split(r"\s*,\s*", found.group(3)):
                        module = module.split(" as ")[0].strip()
                        if not module:
                            continue
                        hit = _resolve_python(module, path, known, roots)
                        if hit:
                            targets.add(hit)
                        elif module.split(".")[0] not in _STDLIB:
                            result.externals[module.split(".")[0]] += 1
        else:
            for specifier in _JS_IMPORT.findall(text):
                if specifier.startswith("."):
                    hit = _resolve_js(specifier, path, known)
                    if hit:
                        targets.add(hit)
                elif not specifier.startswith(("/", "node:", "http")):
                    parts = specifier.split("/")
                    result.externals[
                        "/".join(parts[:2]) if specifier.startswith("@") else parts[0]
                    ] += 1
        targets.discard(path)
        result.links[path] = targets
    return result


def _folder(path: str, depth: int) -> str:
    parts = PurePosixPath(path).parts[:-1]
    return "/".join(parts[:depth]) if parts else "(root)"


def group_files(files: list[str], limit: int = MAX_GROUPS, small: int = 12) -> dict[str, str]:
    """Each file's module: folders, the big ones split into their subfolders for as long as the
    map stays readable, so a large app does not show as one box."""
    group = {path: _folder(path, 1) for path in files}
    depth_of = {name: 1 for name in set(group.values())}
    settled: set[str] = set()
    while True:
        sizes = Counter(group.values())
        candidates = [
            name
            for name, size in sizes.most_common()
            if size > small and name not in settled and name != "(root)"
        ]
        if not candidates:
            return group
        name = candidates[0]
        depth = depth_of[name] + 1
        members = [path for path, current in group.items() if current == name]
        split = {
            path: (_folder(path, depth) if len(PurePosixPath(path).parts) - 1 >= depth else name)
            for path in members
        }
        parts = set(split.values())
        if len(parts) == 1 and name not in parts:
            # One subfolder only: the module is that folder, look deeper.
            only = parts.pop()
            for path in members:
                group[path] = only
            depth_of[only] = depth
            settled.discard(only)
            continue
        if len(parts) == 1:
            settled.add(name)
            continue
        room = limit - len(sizes)
        if len(parts) - 1 > room:
            # Too many subfolders: the biggest become modules, the rest stay in this one.
            if room < 2:
                settled.add(name)
                continue
            kept = {part for part, _size in Counter(split.values()).most_common() if part != name}
            kept = set(sorted(kept, key=lambda part: -Counter(split.values())[part])[:room])
            split = {path: (value if value in kept else name) for path, value in split.items()}
            settled.add(name)
        for path, value in split.items():
            group[path] = value
            depth_of.setdefault(value, depth)


def _cycles(nodes: list[str], edges: dict[str, set[str]]) -> list[list[str]]:
    """Modules that use one another round in a circle (Tarjan's strongly connected parts)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    found: list[list[str]] = []
    counter = 0

    def visit(node: str) -> None:
        nonlocal counter
        index[node] = low[node] = counter
        counter += 1
        stack.append(node)
        on_stack.add(node)
        for target in edges.get(node, ()):
            if target not in index:
                visit(target)
                low[node] = min(low[node], low[target])
            elif target in on_stack:
                low[node] = min(low[node], index[target])
        if low[node] == index[node]:
            part = []
            while True:
                item = stack.pop()
                on_stack.discard(item)
                part.append(item)
                if item == node:
                    break
            if len(part) > 1:
                found.append(sorted(part))

    for node in nodes:
        if node not in index:
            visit(node)
    return found


def module_graph(root: Path) -> dict[str, object]:
    """The modules, the uses between them, cycles, outside packages and likely entry points."""
    repo = build_map(root)
    if not repo.files:
        return {"modules": [], "edges": [], "cycles": [], "externals": [], "files": 0}
    group = group_files(repo.files)
    members: dict[str, list[str]] = defaultdict(list)
    for path in repo.files:
        members[group[path]].append(path)
    weights: Counter[tuple[str, str]] = Counter()
    for path, targets in repo.links.items():
        source = group[path]
        for target in targets:
            destination = group[target]
            if destination != source:
                weights[(source, destination)] += 1
    edges: dict[str, set[str]] = defaultdict(set)
    for source, destination in weights:
        edges[source].add(destination)
    used_by = Counter(destination for _source, destination in weights)
    entry_names = {
        "main.py",
        "__main__.py",
        "cli.py",
        "app.py",
        "manage.py",
        "index.ts",
        "main.ts",
        "index.tsx",
        "main.tsx",
        "index.js",
        "server.ts",
        "server.py",
    }
    entries = [path for path in repo.files if PurePosixPath(path).name in entry_names][:12]
    used = Counter(target for targets in repo.links.values() for target in targets)
    modules = []
    for name, paths in sorted(members.items()):
        key_files = [path for path in sorted(paths, key=lambda item: -used[item]) if used[path]][:5]
        modules.append(
            {
                "id": name,
                "files": len(paths),
                "lines": sum(repo.lines.get(path, 0) for path in paths),
                "usedBy": used_by.get(name, 0),
                "uses": len(edges.get(name, ())),
                # The files others use most: where to start reading the module.
                "keyFiles": key_files or sorted(paths)[:5],
                "allFiles": sorted(paths)[:200],
            }
        )
    languages = Counter(PurePosixPath(path).suffix.lstrip(".") for path in repo.files)
    return {
        "files": len(repo.files),
        "languages": dict(languages.most_common()),
        "modules": modules,
        "edges": [
            {"from": source, "to": destination, "weight": weight}
            for (source, destination), weight in sorted(weights.items())
        ],
        "cycles": _cycles(sorted(members), edges),
        "externals": [
            {"name": name, "uses": count} for name, count in repo.externals.most_common(25)
        ],
        "entryPoints": entries,
    }


__all__ = ["build_map", "group_files", "list_code_files", "module_graph"]
