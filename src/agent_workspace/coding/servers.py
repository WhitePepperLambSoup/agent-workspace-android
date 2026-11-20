"""Language servers the desktop knows: which files each serves, where it is, how to get it.

Only servers outside the folder are started: on PATH, in the app's own tools folder, or in the
Rust and Go toolchains' bin folders. A folder's own node_modules or virtual environment is not run
because a file was opened, and servers that would run them are told not to (here and in
lsp_pool.py) until the user has accepted the folder's commands. rust-analyzer runs cargo to read
the project, and cargo honours the folder's .cargo/config.toml and rust-toolchain file; no setting
of rust-analyzer closes that, so it is not started at all until then.
"""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

type Which = Callable[[str], str | None]

# Set by the desktop to its Electron executable, which runs JavaScript servers when Node is not
# installed (with ELECTRON_RUN_AS_NODE=1).
ELECTRON_NODE_ENV = "AGENT_WORKSPACE_ELECTRON_NODE"


@dataclass(frozen=True, slots=True)
class ServerSpec:
    id: str
    name: str
    # File extension -> LSP language id.
    languages: Mapping[str, str]
    # Programs looked for outside the folder, first found wins: (program, *arguments).
    commands: tuple[tuple[str, ...], ...]
    # npm packages (name@major) put in the tools folder, and the script there run with Node.
    npm: tuple[str, ...] = ()
    npm_entry: tuple[str, ...] = ()
    # How to get it when it cannot be installed from here.
    hint: str = ""
    # Told to the server until the user has accepted the folder's commands: no code of the folder.
    initialization_options: Mapping[str, object] = field(default_factory=dict)
    # Files of the tools folder's node_modules it is not started without, or it takes the folder's.
    requires: tuple[str, ...] = ()
    # Not started until the user has accepted the folder's commands: it runs the folder's code
    # whatever it is told.
    waits_for_trust: bool = False


SERVERS: tuple[ServerSpec, ...] = (
    ServerSpec(
        "python",
        "Pyright",
        {".py": "python", ".pyi": "python"},
        (("pyright-langserver", "--stdio"), ("basedpyright-langserver", "--stdio")),
        npm=("pyright@1",),
        npm_entry=("pyright/langserver.index.js", "--stdio"),
    ),
    ServerSpec(
        "typescript",
        "TypeScript",
        {
            ".ts": "typescript",
            ".mts": "typescript",
            ".cts": "typescript",
            ".tsx": "typescriptreact",
            ".js": "javascript",
            ".mjs": "javascript",
            ".cjs": "javascript",
            ".jsx": "javascriptreact",
        },
        (("typescript-language-server", "--stdio"),),
        npm=("typescript-language-server@5", "typescript@5"),
        npm_entry=("typescript-language-server/lib/cli.mjs", "--stdio"),
        # Without tsserver.path it runs the folder's node_modules/typescript (lsp_pool.py).
        requires=("typescript/lib/tsserver.js",),
    ),
    ServerSpec(
        "rust",
        "rust-analyzer",
        {".rs": "rust"},
        (("rust-analyzer",),),
        hint="rustup component add rust-analyzer",
        # By default it runs the project's build scripts and procedural macros, and cargo check.
        initialization_options={
            "cargo": {"buildScripts": {"enable": False}},
            "procMacro": {"enable": False},
            "checkOnSave": False,
        },
        # Even so it runs cargo, which follows the folder's .cargo/config.toml and rust-toolchain.
        waits_for_trust=True,
    ),
    ServerSpec(
        "go",
        "gopls",
        {".go": "go"},
        (("gopls",),),
        hint="go install golang.org/x/tools/gopls@latest",
    ),
    ServerSpec(
        "c",
        "clangd",
        {
            ".c": "c",
            ".h": "c",
            ".cc": "cpp",
            ".cpp": "cpp",
            ".cxx": "cpp",
            ".hpp": "cpp",
            ".hh": "cpp",
        },
        (("clangd",),),
        hint="https://clangd.llvm.org/installation",
    ),
)


def spec_for(path: str | Path) -> ServerSpec | None:
    suffix = Path(path).suffix.lower()
    return next((spec for spec in SERVERS if suffix in spec.languages), None)


def spec_by_id(server_id: str) -> ServerSpec | None:
    return next((spec for spec in SERVERS if spec.id == server_id), None)


def language_id(path: str | Path) -> str:
    spec = spec_for(path)
    return spec.languages[Path(path).suffix.lower()] if spec is not None else "plaintext"


def _toolchain_bins() -> list[Path]:
    home = Path.home()
    bins = [home / ".cargo" / "bin", home / "go" / "bin"]
    gopath = os.environ.get("GOPATH")
    if gopath:
        bins.extend(Path(item) / "bin" for item in gopath.split(os.pathsep) if item)
    return bins


def _in_toolchains(program: str) -> str | None:
    names = [program, f"{program}.exe"] if sys.platform == "win32" else [program]
    for folder in _toolchain_bins():
        for name in names:
            candidate = folder / name
            if candidate.is_file():
                return str(candidate)
    return None


@dataclass(frozen=True, slots=True)
class NodeRuntime:
    command: tuple[str, ...]
    environment: Mapping[str, str]


def _on_path(program: str, which: Which) -> str | None:
    found = which(program)
    # On Windows shutil.which looks in the current directory before PATH, and on the command line
    # the current directory is usually the folder.
    return None if found and Path(found).parent == Path(os.curdir) else found


def find_node(which: Which = shutil.which) -> NodeRuntime | None:
    """Node on PATH, else the desktop's Electron run as Node."""
    found = _on_path("node", which)
    if found:
        return NodeRuntime((found,), {})
    electron = os.environ.get(ELECTRON_NODE_ENV)
    if electron and Path(electron).is_file():
        return NodeRuntime((electron,), {"ELECTRON_RUN_AS_NODE": "1"})
    return None


@dataclass(frozen=True, slots=True)
class ServerCommand:
    spec: ServerSpec
    command: tuple[str, ...]
    environment: Mapping[str, str]
    # "path" (found outside the folder) or "installed" (in the tools folder).
    source: str


def find_server(
    spec: ServerSpec,
    tools_dir: Path | None,
    *,
    which: Which = shutil.which,
    node: Callable[[], NodeRuntime | None] | None = None,
) -> ServerCommand | None:
    if spec.requires and (
        tools_dir is None
        or not all((tools_dir / "node_modules" / item).is_file() for item in spec.requires)
    ):
        return None
    for program, *arguments in spec.commands:
        found = _on_path(program, which) or _in_toolchains(program)
        if found:
            return ServerCommand(spec, (found, *arguments), {}, "path")
    if spec.npm_entry and tools_dir is not None:
        script = tools_dir / "node_modules" / spec.npm_entry[0]
        if script.is_file():
            runtime = (node or (lambda: find_node(which)))()
            if runtime is not None:
                command = (*runtime.command, str(script), *spec.npm_entry[1:])
                return ServerCommand(spec, command, runtime.environment, "installed")
    return None


def installable(spec: ServerSpec, which: Which = shutil.which) -> bool:
    """npm packages this app can fetch and a Node to run them."""
    return bool(spec.npm) and find_node(which) is not None


__all__ = [
    "ELECTRON_NODE_ENV",
    "SERVERS",
    "NodeRuntime",
    "ServerCommand",
    "ServerSpec",
    "find_node",
    "find_server",
    "installable",
    "language_id",
    "spec_by_id",
    "spec_for",
]
