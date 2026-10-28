"""Compile a LaTeX document with the TeX installed on this computer, or with Tectonic.

The engine runs in the document's folder with its output in a ``.latex-build`` folder beside the
document, as many times as cross-references and the bibliography need (BibTeX or Biber in
between). Shell escape is never enabled. Each engine runs without a console window and is
stopped (with the processes it started) when the compile is cancelled or takes too long.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from agent_workspace.latex import log as latex_log
from agent_workspace.latex.issues import Issue

BUILD_DIRECTORY = ".latex-build"
PROGRAMS = ("xelatex", "lualatex", "pdflatex")
ENGINES = ("auto", "tectonic", *PROGRAMS)
PASS_SECONDS = 300.0
TOTAL_SECONDS = 600.0
MAX_PASSES = 4
_HEAD_CHARS = 64 * 1024
_MAGIC_PROGRAM = re.compile(
    r"^\s*%\s*!\s*TEX\s+(?:TS-)?program\s*=\s*(\w+)", re.IGNORECASE | re.MULTILINE
)
_MAGIC_ROOT = re.compile(r"^\s*%\s*!\s*TEX\s+root\s*=\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_UNICODE_PACKAGES = re.compile(
    r"\\documentclass(?:\[[^\]]*\])?\{ctex\w*\}|"
    r"\\usepackage(?:\[[^\]]*\])?\{[^}]*\b(?:ctex|xeCJK|fontspec|unicode-math|luatexja)\b"
)
_INCLUDES = re.compile(r"\\(?:input|include|subfile|import\{[^}]*\})\s*\{([^}]+)\}")
_CREATE_NO_WINDOW = 0x08000000


class CompileError(Exception):
    """A compile that could not start: no engine, a missing document, a bad engine name."""


@dataclass
class Engines:
    """The TeX programs found on this computer (absolute paths)."""

    programs: dict[str, str] = field(default_factory=dict)
    tectonic: str | None = None
    bibtex: str | None = None
    biber: str | None = None
    distribution: str | None = None  # "miktex", "texlive" or None

    def available(self) -> bool:
        return bool(self.programs) or self.tectonic is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "programs": dict(self.programs),
            "tectonic": self.tectonic,
            "bibtex": self.bibtex,
            "biber": self.biber,
            "distribution": self.distribution,
        }


def tectonic_install_path(data_dir: Path) -> Path:
    name = "tectonic.exe" if sys.platform == "win32" else "tectonic"
    return data_dir / "tools" / "tectonic" / name


def _windows_tex_directories() -> list[Path]:
    found: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        found.append(Path(local) / "Programs" / "MiKTeX" / "miktex" / "bin" / "x64")
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(variable)
        if base:
            found.append(Path(base) / "MiKTeX" / "miktex" / "bin" / "x64")
    texlive = Path(os.environ.get("SYSTEMDRIVE", "C:") + "\\") / "texlive"
    try:
        years = sorted(
            (entry for entry in texlive.iterdir() if entry.name.isdigit()),
            key=lambda entry: entry.name,
            reverse=True,
        )
    except OSError:
        years = []
    for year in years:
        found.extend(year / "bin" / name for name in ("windows", "win64", "win32"))
    return found


def _which(name: str, extra: list[Path]) -> str | None:
    found = shutil.which(name)
    if found:
        return str(Path(found).resolve())
    suffix = ".exe" if sys.platform == "win32" else ""
    for directory in extra:
        candidate = directory / f"{name}{suffix}"
        if candidate.is_file():
            return str(candidate)
    return None


_DETECTED: tuple[float, Path | None, Engines] | None = None
_DETECT_LOCK = threading.Lock()


def detect_engines(data_dir: Path | None = None, *, fresh: bool = False) -> Engines:
    """The engines on PATH and in the usual MiKTeX and TeX Live folders (kept for a minute)."""
    global _DETECTED
    with _DETECT_LOCK:
        if (
            not fresh
            and _DETECTED is not None
            and _DETECTED[1] == data_dir
            and time.monotonic() - _DETECTED[0] < 60
        ):
            return _DETECTED[2]
        extra = _windows_tex_directories() if sys.platform == "win32" else []
        engines = Engines()
        for program in PROGRAMS:
            path = _which(program, extra)
            if path:
                engines.programs[program] = path
        engines.bibtex = _which("bibtex", extra)
        engines.biber = _which("biber", extra)
        installed = tectonic_install_path(data_dir) if data_dir is not None else None
        if installed is not None and installed.is_file():
            engines.tectonic = str(installed)
        else:
            engines.tectonic = _which("tectonic", [])
        first = next(iter(engines.programs.values()), "")
        if "miktex" in first.lower():
            engines.distribution = "miktex"
        elif first:
            engines.distribution = "texlive"
        _DETECTED = (time.monotonic(), data_dir, engines)
        return engines


def read_head(path: Path) -> str:
    """The start of a source file (where the class, packages and magic comments are)."""
    with path.open("rb") as stream:
        data = stream.read(_HEAD_CHARS)
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def find_root(folder: Path, file: Path, *, max_files: int = 400) -> Path:
    """The document a source file belongs to: a ``% !TEX root`` comment, the file itself when it
    has a ``\\documentclass``, or a document in the folder that inputs it."""
    file = file.resolve()
    head = read_head(file)
    magic = _MAGIC_ROOT.search(head)
    if magic is not None:
        candidate = (file.parent / magic.group(1).strip()).resolve()
        if candidate.suffix != ".tex":
            candidate = candidate.with_suffix(".tex")
        if candidate.is_file() and _inside(folder, candidate):
            return candidate
    if re.search(r"^[^%\n]*\\documentclass", head, re.MULTILINE):
        return file
    target = file
    candidates: list[Path] = []
    for count, path in enumerate(_tex_files(folder)):
        if count >= max_files:
            break
        if path.resolve() == target:
            continue
        try:
            text = read_head(path)
        except OSError:
            continue
        if not re.search(r"^[^%\n]*\\documentclass", text, re.MULTILINE):
            continue
        for match in _INCLUDES.finditer(text):
            name = match.group(1).strip()
            included = (path.parent / name).resolve()
            if target in {included, included.with_name(included.name + ".tex")}:
                candidates.append(path)
                break
    if not candidates:
        return file
    candidates.sort(key=lambda path: (path.name != "main.tex", len(path.parts)))
    return candidates[0].resolve()


def _inside(folder: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(folder.resolve())
    except ValueError:
        return False
    return True


_SKIPPED_DIRECTORIES = frozenset(
    {".git", "node_modules", ".venv", "venv", ".agent", BUILD_DIRECTORY, "__pycache__"}
)


def _tex_files(folder: Path, depth: int = 6) -> list[Path]:
    found: list[Path] = []

    def walk(directory: Path, level: int) -> None:
        try:
            entries = sorted(directory.iterdir(), key=lambda entry: entry.name)
        except OSError:
            return
        for entry in entries:
            if entry.is_dir():
                if level < depth and entry.name not in _SKIPPED_DIRECTORIES:
                    walk(entry, level + 1)
            elif entry.suffix.lower() == ".tex":
                found.append(entry)

    walk(folder, 0)
    return found


def choose_program(head: str, engines: Engines, preference: str = "auto") -> str:
    """Which engine compiles a document: the one asked for, a ``% !TEX program`` comment,
    XeLaTeX for documents with Chinese or system fonts, otherwise pdfLaTeX."""
    if preference not in ENGINES:
        raise CompileError("unknown_engine")
    if preference == "tectonic":
        if engines.tectonic is None:
            raise CompileError("engine_unavailable")
        return "tectonic"
    if preference in PROGRAMS:
        if preference not in engines.programs:
            raise CompileError("engine_unavailable")
        return preference
    magic = _MAGIC_PROGRAM.search(head)
    wanted = magic.group(1).lower() if magic else None
    if wanted in engines.programs:
        return wanted
    unicode = bool(_UNICODE_PACKAGES.search(head))
    order = ("xelatex", "lualatex", "pdflatex") if unicode else ("pdflatex", "xelatex", "lualatex")
    for program in order:
        if program in engines.programs:
            return program
    if engines.tectonic is not None:
        return "tectonic"
    raise CompileError("engine_unavailable")


@dataclass
class CompileResult:
    ok: bool
    engine: str
    main: Path
    build: Path
    pdf: Path | None
    log: Path | None
    issues: list[Issue]
    passes: int
    seconds: float
    cancelled: bool = False
    timed_out: bool = False

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "error"]


class _Runner:
    """Runs one engine pass after another, stopping them on cancel or timeout."""

    def __init__(self, cancel: threading.Event | None, deadline: float) -> None:
        self.cancel = cancel
        self.deadline = deadline
        self.cancelled = False
        self.timed_out = False

    def run(self, command: list[str], cwd: Path, env: dict[str, str], output: Path) -> int | None:
        if self.cancel is not None and self.cancel.is_set():
            self.cancelled = True
            return None
        flags = _CREATE_NO_WINDOW if sys.platform == "win32" else 0
        with output.open("wb") as stream:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
            limit = min(time.monotonic() + PASS_SECONDS, self.deadline)
            while True:
                code = process.poll()
                if code is not None:
                    return code
                if self.cancel is not None and self.cancel.is_set():
                    self.cancelled = True
                elif time.monotonic() > limit:
                    self.timed_out = True
                if self.cancelled or self.timed_out:
                    _stop(process)
                    return None
                time.sleep(0.05)


def _stop(process: subprocess.Popen[bytes]) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW,
            check=False,
        )
    else:
        process.kill()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def _search_path(*directories: Path) -> str:
    # The trailing separator keeps the distribution's own search paths.
    return os.pathsep.join(str(directory) for directory in directories) + os.pathsep


def _mirror_directories(main_dir: Path, build: Path) -> None:
    """``\\include{chapters/a}`` writes ``chapters/a.aux`` under the output folder."""
    for path in _tex_files(main_dir, depth=4):
        relative = path.parent.relative_to(main_dir)
        if relative.parts:
            (build / relative).mkdir(parents=True, exist_ok=True)


def compile_document(
    folder: Path,
    main: Path,
    *,
    engines: Engines,
    preference: str = "auto",
    cancel: threading.Event | None = None,
    installer: bool = True,
    progress: Callable[[str], None] | None = None,
) -> CompileResult:
    """Compile ``main`` (a document inside ``folder``) and read what went wrong."""
    main = main.resolve()
    if not main.is_file():
        raise CompileError("document_missing")
    head = read_head(main)
    program = choose_program(head, engines, preference)
    build = main.parent / BUILD_DIRECTORY
    build.mkdir(parents=True, exist_ok=True)
    stem = main.stem
    for leftover in (f"{stem}.pdf", f"{stem}.log", f"{stem}.synctex.gz"):
        (build / leftover).unlink(missing_ok=True)
    started = time.monotonic()
    runner = _Runner(cancel, started + TOTAL_SECONDS)
    env = dict(os.environ)
    if program == "tectonic":
        assert engines.tectonic is not None
        passes, output = _run_tectonic(runner, engines.tectonic, main, build, env, progress)
    else:
        passes, output = _run_tex(
            runner, engines, program, main, build, env, installer=installer, progress=progress
        )
    log_path = build / f"{stem}.log"
    log_text = _read_text(log_path) if log_path.is_file() else ""
    issues = latex_log.parse_log(log_text) if log_text else []
    if program == "tectonic":
        _relocate_from_stderr(issues, output)
    exit_ok = output is not None and output[0] == 0
    pdf = build / f"{stem}.pdf"
    produced = pdf.is_file() and pdf.stat().st_size > 0
    if not exit_ok and not any(issue.severity == "error" for issue in issues):
        detail = _tail(output[1]) if output is not None else ""
        if runner.cancelled:
            issues.insert(0, Issue("error", "cancelled", "the compile was cancelled"))
        elif runner.timed_out:
            issues.insert(
                0, Issue("error", "timed_out", "the compile took too long and was stopped")
            )
        else:
            issues.insert(
                0,
                Issue(
                    "error",
                    "engine_failed",
                    f"{program} stopped without saying why" + (f": {detail}" if detail else ""),
                    raw=output[1][-6000:] if output is not None else None,
                ),
            )
    _place_issues(issues, folder.resolve(), main)
    return CompileResult(
        ok=exit_ok and produced and not any(issue.severity == "error" for issue in issues),
        engine=program,
        main=main,
        build=build,
        pdf=pdf if produced else None,
        log=log_path if log_path.is_file() else None,
        issues=issues,
        passes=passes,
        seconds=round(time.monotonic() - started, 2),
        cancelled=runner.cancelled,
        timed_out=runner.timed_out,
    )


def _run_tex(
    runner: _Runner,
    engines: Engines,
    program: str,
    main: Path,
    build: Path,
    env: dict[str, str],
    *,
    installer: bool,
    progress: Callable[[str], None] | None,
) -> tuple[int, tuple[int, str] | None]:
    main_dir = main.parent
    _mirror_directories(main_dir, build)
    env["BIBINPUTS"] = _search_path(main_dir) + env.get("BIBINPUTS", "")
    env["BSTINPUTS"] = _search_path(main_dir) + env.get("BSTINPUTS", "")
    command = [
        engines.programs[program],
        "-interaction=nonstopmode",
        "-file-line-error",
        "-synctex=1",
        f"-output-directory={BUILD_DIRECTORY}",
    ]
    # Only the distribution's list of safe programs may run from a document (restricted mode),
    # whatever its configuration says.
    if engines.distribution == "miktex":
        command.append("-restrict-write18")
        if not installer:
            command.append("-disable-installer")
    else:
        command.append("-shell-restricted")
    command.append(main.name)
    console = build / f"{main.stem}.console.txt"
    passes = 0
    result: tuple[int, str] | None = None
    bibliography_done = False
    while passes < MAX_PASSES:
        passes += 1
        if progress is not None:
            progress(f"{program} pass {passes}")
        code = runner.run(command, main_dir, env, console)
        if code is None:
            return passes, None
        result = (code, _read_text(console))
        if code != 0:
            break
        log_text = _read_text(build / f"{main.stem}.log")
        if not bibliography_done:
            bibliography_done = True
            tool = _bibliography_tool(build, main.stem, engines)
            state = _bibliography_state(build, main.stem, main_dir) if tool is not None else ""
            state_file = build / f"{main.stem}.bibstate"
            if tool is not None and _read_text(state_file) == state and _has_bbl(build, main.stem):
                tool = None  # the same citations and .bib files as last time: the .bbl holds
            if tool is not None:
                if progress is not None:
                    progress(Path(tool[0]).stem)
                # BibTeX reads the .aux in the output folder; Biber is told where it is.
                cwd = build if tool[0] == engines.bibtex else main_dir
                bib_console = build / f"{main.stem}.bibliography.txt"
                bib_code = runner.run(tool, cwd, env, bib_console)
                if bib_code is None:
                    return passes, None
                if bib_code == 0:
                    state_file.write_text(state, encoding="utf-8")
                else:
                    state_file.unlink(missing_ok=True)
                continue
        if not latex_log.needs_rerun(log_text):
            break
    return passes, result


def _bibliography_tool(build: Path, stem: str, engines: Engines) -> list[str] | None:
    if (build / f"{stem}.bcf").is_file() and engines.biber is not None:
        return [
            engines.biber,
            "--input-directory",
            str(build),
            "--output-directory",
            str(build),
            stem,
        ]
    aux = build / f"{stem}.aux"
    if engines.bibtex is not None and aux.is_file() and "\\bibdata" in _read_text(aux):
        return [engines.bibtex, stem]
    return None


def _has_bbl(build: Path, stem: str) -> bool:
    return (build / f"{stem}.bbl").is_file()


def _bibliography_state(build: Path, stem: str, main_dir: Path) -> str:
    """What the bibliography depends on: the citations and styles the .aux files (or Biber's
    .bcf) ask for, and the size and time of every .bib file beside the document."""
    digest = hashlib.sha256()
    names: list[str] = []
    bcf = build / f"{stem}.bcf"
    if bcf.is_file():
        text = _read_text(bcf)
        digest.update(text.encode("utf-8"))
        names.extend(re.findall(r"<bcf:datasource[^>]*>([^<]+)</bcf:datasource>", text))
    for aux in sorted(build.rglob("*.aux"))[:200]:
        for line in _read_text(aux).splitlines():
            if line.startswith(("\\citation", "\\bibdata", "\\bibstyle", "\\abx@aux@cite")):
                digest.update(line.encode("utf-8", errors="replace"))
            if line.startswith("\\bibdata{"):
                names.extend(line[len("\\bibdata{") :].rstrip("}").split(","))
    for name in sorted(set(names)):
        bib = main_dir / name.strip()
        if bib.suffix.lower() != ".bib":
            bib = bib.with_name(bib.name + ".bib")
        try:
            stat = bib.stat()
        except OSError:
            continue
        digest.update(f"{bib}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    return digest.hexdigest()


def _run_tectonic(
    runner: _Runner,
    binary: str,
    main: Path,
    build: Path,
    env: dict[str, str],
    progress: Callable[[str], None] | None,
) -> tuple[int, tuple[int, str] | None]:
    if progress is not None:
        progress("tectonic")
    command = [
        binary,
        "--outdir",
        str(build),
        "--keep-logs",
        "--color",
        "never",
        "--chatter",
        "minimal",
        "-r",
        "2",
        "--synctex",
        main.name,
    ]
    console = build / f"{main.stem}.console.txt"
    code = runner.run(command, main.parent, env, console)
    if code is None:
        return 1, None
    return 1, (code, _read_text(console))


def _relocate_from_stderr(issues: list[Issue], output: tuple[int, str] | None) -> None:
    """Tectonic runs without ``-file-line-error``; its own messages carry the exact place."""
    if output is None:
        return
    locations = latex_log.stderr_locations(output[1])
    errors = [issue for issue in issues if issue.severity == "error"]
    for issue, (file, line) in zip(errors, locations, strict=False):
        issue.file, issue.line = file, line


def _place_issues(issues: list[Issue], folder: Path, main: Path) -> None:
    """Make each problem's file relative to the folder; a problem with a line but no file is in
    the document itself."""
    for issue in issues:
        if issue.file is None:
            if issue.line is not None:
                issue.file = _relative(folder, main)
            continue
        path = Path(issue.file.replace("\\", "/"))
        if not path.is_absolute():
            path = main.parent / path
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if _inside(folder, resolved):
            issue.file = _relative(folder, resolved)
        else:
            issue.params.setdefault("outside", True)


def _relative(folder: Path, path: Path) -> str:
    return path.resolve().relative_to(folder).as_posix()


def _read_text(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def _tail(text: str, lines: int = 3) -> str:
    kept = [line.strip() for line in text.strip().splitlines() if line.strip()][-lines:]
    return " ".join(kept)[:400]
