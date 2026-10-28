"""A document's sources as a whole: which files belong to it, the rules over all of them, the
labels and bibliography keys it defines, and the compiled PDF beside it."""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from agent_workspace.latex import compile as latex_compile
from agent_workspace.latex import rules
from agent_workspace.latex.issues import Issue, sort_issues

MAX_SOURCE_FILES = 300
MAX_SOURCE_BYTES = 8 * 1024 * 1024
SOURCE_SUFFIXES = frozenset({".tex", ".bib", ".sty", ".cls", ".bbx", ".cbx"})
_SKIPPED = frozenset({".git", "node_modules", ".venv", "venv", ".agent", "__pycache__"})


@dataclass
class Sources:
    """The ``.tex`` and ``.bib`` files of a document's folder (folder-relative paths)."""

    tex: dict[str, str] = field(default_factory=dict)
    bib: dict[str, str] = field(default_factory=dict)
    truncated: bool = False


def decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def gather_sources(root: Path, directory: Path) -> Sources:
    """The sources under ``directory`` (the main document's folder), within limits."""
    sources = Sources()
    total = 0
    root = root.resolve()
    for current, directories, files in os.walk(directory):
        directories[:] = sorted(
            name
            for name in directories
            if name not in _SKIPPED and name != latex_compile.BUILD_DIRECTORY
        )
        for name in sorted(files):
            path = Path(current) / name
            suffix = path.suffix.lower()
            if suffix not in {".tex", ".bib"}:
                continue
            if len(sources.tex) + len(sources.bib) >= MAX_SOURCE_FILES:
                sources.truncated = True
                return sources
            try:
                data = path.read_bytes()
            except OSError:
                continue
            total += len(data)
            if total > MAX_SOURCE_BYTES:
                sources.truncated = True
                return sources
            relative = path.resolve().relative_to(root).as_posix()
            (sources.tex if suffix == ".tex" else sources.bib)[relative] = decode(data)
    return sources


@dataclass
class CheckReport:
    issues: list[Issue]
    labels: list[dict[str, object]]
    citations: list[dict[str, object]]
    main: str
    truncated: bool


def check(
    root: Path,
    file: Path,
    *,
    content: str | None = None,
    settings: dict[str, bool] | None = None,
) -> CheckReport:
    """The rules' findings for a file (using ``content`` when the editor holds unsaved text) and
    the folder rules over its document, plus the labels and bibliography keys for completion."""
    root = root.resolve()
    file = file.resolve()
    main = latex_compile.find_root(root, file) if file.suffix.lower() == ".tex" else file
    sources = gather_sources(root, main.parent)
    relative = file.relative_to(root).as_posix()
    if content is not None:
        (sources.bib if file.suffix.lower() == ".bib" else sources.tex)[relative] = content
    enabled = rules.enabled_rules(settings)
    found: list[Issue] = []
    if file.suffix.lower() == ".tex":
        text = sources.tex.get(relative)
        if text is None:
            text = decode(file.read_bytes())
        found.extend(rules.check_source(text, relative, enabled))
    project = rules.check_project(
        sources.tex,
        sources.bib,
        enabled,
        has_bibliography=_has_bibliography(sources.tex),
    )
    # The folder rules cover every file; the editor shows the open file's and the bibliography's.
    found.extend(issue for issue in project if issue.file == relative or issue.file in sources.bib)
    labels = [
        {"key": key, "file": path, "line": line}
        for path, text in sources.tex.items()
        for key, line in rules.labels(text)
    ][:2000]
    citations: list[dict[str, object]] = []
    for path, text in sources.bib.items():
        for record in rules.parse_bib_records(text):
            title = record.field("title")
            author = record.field("author")
            year = record.field("year") or record.field("date")
            citations.append(
                {
                    "key": record.key,
                    "file": path,
                    "line": record.line,
                    "title": _plain(title.value) if title else "",
                    "author": _plain(author.value)[:120] if author else "",
                    "year": year.value.strip()[:10] if year else "",
                }
            )
    return CheckReport(
        sort_issues(found),
        labels,
        citations[:5000],
        main.relative_to(root).as_posix(),
        sources.truncated,
    )


def _has_bibliography(tex: dict[str, str]) -> bool:
    return any(
        re.search(
            r"\\(?:bibliography|addbibresource|printbibliography)\b|\\begin\{thebibliography\}",
            text,
        )
        for text in tex.values()
    )


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("{", "").replace("}", "")).strip()


def pdf_beside(main: Path) -> Path:
    return main.with_suffix(".pdf")


def publish_pdf(result: latex_compile.CompileResult) -> Path | None:
    """Copy the compiled PDF beside the document (replacing the previous one atomically)."""
    if result.pdf is None:
        return None
    target = pdf_beside(result.main)
    data = result.pdf.read_bytes()
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return target
