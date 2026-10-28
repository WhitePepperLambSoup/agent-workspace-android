# ruff: noqa: RUF001 -- Chinese headings and captions use full-width punctuation.
"""Read a paper (a PDF of the folder) the way a reader does: its outline first (title, DOI,
sections and the page each starts on, figure and table captions, abstract), then the pages
wanted, with page numbers so an answer can point at them, and its reference list.
"""

from __future__ import annotations

import asyncio
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.scholar import checks
from agent_workspace.scholar.works import normalize_doi
from agent_workspace.tools.base import (
    ToolArgumentError,
    ToolError,
    json_result,
    validate_tool_arguments,
)
from agent_workspace.tools.paths import WorkspacePathError, WorkspacePaths

MAX_PDF_BYTES = 128 * 1024 * 1024
MAX_PAGES = 2000
OUTLINE_PAGES = 400
_CACHE_SIZE = 6

_NAMED = re.compile(
    r"^(?:\d+(?:\.\d+)*\.?\s+)?(abstract|introduction|related work|background|preliminaries|"
    r"methods?|methodology|materials and methods|approach|experiments?|experimental setup|"
    r"evaluation|results?|results and discussion|discussion|limitations|conclusions?|"
    r"future work|acknowledge?ments?|references|bibliography|appendix(?: [a-z])?|"
    r"摘\s*要|引\s*言|绪\s*论|前\s*言|相关工作|研究方法|实验|结果|讨\s*论|结\s*论|致\s*谢|参考文献|附\s*录)"
    r"\s*[:：]?$",
    re.IGNORECASE,
)
_NUMBERED = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,2})\.?\s+([A-Z一-鿿][^\n]{2,90})$")
_CHAPTER = re.compile(
    r"^(第[一二三四五六七八九十百\d]+[章节]|[一二三四五六七八九十]+、)\s*\S.{0,60}$"
)
_CAPTION = re.compile(
    r"^(Fig\.?|Figure|Table|Tab\.|图|表)\s*(\d+(?:[.-]\d+)?)\s*[.:：]?\s*(.{0,200})", re.IGNORECASE
)
_DOI = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
_ARXIV = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
# TeX's T1 fonts without a Unicode map give ligatures and dashes as control codes.
_T1_CODES = str.maketrans(
    {
        "\x15": "–",
        "\x16": "—",
        "\x1b": "ff",
        "\x1c": "fi",
        "\x1d": "fl",
        "\x1e": "ffi",
        "\x1f": "ffl",
    }
)
_REFERENCES = re.compile(
    r"^(?:\d+\.?\s+)?(references|bibliography|参考文献|literature cited)\s*$", re.I
)


@dataclass
class Paper:
    pages: list[str]
    metadata_title: str = ""
    total_pages: int = 0
    problems: list[str] = field(default_factory=list)


_CACHE: OrderedDict[tuple[str, int, int], Paper] = OrderedDict()
_CACHE_LOCK = threading.Lock()


def load_paper(path: Path, *, pages: int = MAX_PAGES) -> Paper:
    """The text of each page (kept for a few papers, by file size and time)."""
    stat = path.stat()
    if stat.st_size > MAX_PDF_BYTES:
        raise ToolError("the PDF is larger than 128 MB")
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            _CACHE.move_to_end(key)
            return cached
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
        total = len(reader.pages)
    except Exception as error:  # pypdf raises several types for a broken file
        raise ToolError(f"cannot read the PDF: {error}") from None
    texts: list[str] = []
    problems: list[str] = []
    for number in range(min(total, pages)):
        try:
            texts.append((reader.pages[number].extract_text() or "").translate(_T1_CODES))
        except Exception:  # one unreadable page should not lose the others
            texts.append("")
            problems.append(f"page {number + 1} could not be read")
    title = ""
    try:
        metadata = reader.metadata
        if metadata and metadata.title and len(metadata.title.strip()) > 3:
            title = metadata.title.strip()
    except Exception:  # broken metadata is common and harmless
        title = ""
    paper = Paper(texts, title, total, problems)
    with _CACHE_LOCK:
        _CACHE[key] = paper
        while len(_CACHE) > _CACHE_SIZE:
            _CACHE.popitem(last=False)
    return paper


def _lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def _is_heading(line: str) -> bool:
    sentence = line.endswith((".", "。", ",", "，", ";")) and not _NAMED.match(line)
    if len(line) > 100 or sentence:
        return False
    if _NAMED.match(line) or _CHAPTER.match(line):
        return True
    match = _NUMBERED.match(line)
    if match is None:
        return False
    words = match.group(2).split()
    # "3 For the" is a sentence fragment; a heading is short and mostly capitalised words.
    return len(words) <= 12 and not re.search(r"\d{3,}", match.group(2))


def outline(paper: Paper) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    figures: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    seen_captions: set[tuple[str, str]] = set()
    for number, text in enumerate(paper.pages[:OUTLINE_PAGES], 1):
        for line in _lines(text):
            if _is_heading(line):
                if not sections or sections[-1]["title"] != line:
                    sections.append({"title": line, "page": number})
                continue
            caption = _CAPTION.match(line)
            if caption is not None:
                kind = "table" if caption.group(1).lower().startswith(("tab", "表")) else "figure"
                label = f"{caption.group(1)} {caption.group(2)}"
                if (kind, caption.group(2)) in seen_captions:
                    continue  # a caption is found once; later mentions are references to it
                seen_captions.add((kind, caption.group(2)))
                entry = {"label": label, "caption": caption.group(3)[:200], "page": number}
                (tables if kind == "table" else figures).append(entry)
    # The paper's own identifiers are on its first page; later ones belong to cited works.
    head = paper.pages[0] if paper.pages else ""
    doi_match = _DOI.search(head)
    arxiv_match = _ARXIV.search(head)
    first_lines = _lines(paper.pages[0]) if paper.pages else []
    title = paper.metadata_title or next(
        (line for line in first_lines[:8] if 3 <= len(line.split()) <= 30 or len(line) >= 8), ""
    )
    return {
        "title": title,
        "doi": normalize_doi(doi_match.group(0).rstrip(".,;)")) if doi_match else None,
        "arxiv": arxiv_match.group(1) if arxiv_match else None,
        "sections": sections[:200],
        "figures": figures[:150],
        "tables": tables[:150],
        "abstract": _abstract(paper),
    }


def _abstract(paper: Paper) -> str:
    text = "\n".join(paper.pages[:2])
    match = re.search(r"(?im)^\s*(abstract|摘\s*要)\s*[:：.—-]?\s*", text)
    if match is None:
        return ""
    rest = text[match.end() :]
    stop = re.search(
        r"(?im)^\s*(?:\d+\.?\s+)?(introduction|keywords?|index terms|关键词|引\s*言|1\s+\S)", rest
    )
    body = rest[: stop.start()] if stop else rest[:2500]
    return re.sub(r"\s+", " ", body).strip()[:2500]


def page_numbers(spec: str, total: int) -> list[int]:
    """'1-3, 7' as page numbers within the paper."""
    numbers: list[int] = []
    for part in spec.replace("，", ",").split(","):
        part = part.strip()
        if not part:
            continue
        match = re.fullmatch(r"(\d+)\s*(?:-|–|~|to)\s*(\d+)", part)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
        elif part.isdigit():
            start = end = int(part)
        else:
            raise ToolArgumentError(f"pages must look like '1-3, 7', not {part!r}")
        if start < 1 or end < start:
            raise ToolArgumentError(f"page range {part!r} is not valid")
        numbers.extend(number for number in range(start, end + 1) if number <= total)
    return sorted(set(numbers))


def references(paper: Paper) -> list[dict[str, Any]]:
    """The reference list: the text after the last References heading, split into entries."""
    start: tuple[int, int] | None = None
    for number, text in enumerate(paper.pages):
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if _REFERENCES.match(line.strip()):
                start = (number, index)
    if start is None:
        return []
    page, index = start
    first = "\n".join(paper.pages[page].splitlines()[index + 1 :])
    rest = "\n".join(paper.pages[page + 1 :])
    body = f"{first}\n{rest}"
    appendix = re.search(r"(?im)^\s*(appendix|附\s*录)\b", body)
    if appendix is not None:
        body = body[: appendix.start()]
    found = checks.references_from_text("References\n" + body)
    return [{"number": reference.index, "text": reference.text[:600]} for reference in found[:400]]


class ReadPaperTool:
    hard_cancellable = True

    def __init__(self, workspace: Path) -> None:
        self.paths = WorkspacePaths(workspace)
        self._spec = ToolSpec(
            name="read_paper",
            description=(
                "Read a paper (a PDF in the folder). part=outline (start here): title, DOI, "
                "sections with the page each starts on, figure and table captions with pages, "
                "the abstract. part=text with pages='3-5,9': the text of those pages, each "
                "marked with its page number. part=find with query: the pages that mention "
                "it, with the passage. part=references: the numbered reference list (check it "
                "with check_references, look works up with paper_lookup). When you cite the "
                "paper in an answer, link the page as [p. 5](path/to/paper.pdf#page=5): the "
                "window opens the PDF at that page. A scanned PDF has no text; say so."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1, "maxLength": 1024},
                    "part": {
                        "type": "string",
                        "enum": ["outline", "text", "find", "references"],
                    },
                    "pages": {"type": "string", "maxLength": 200},
                    "query": {"type": "string", "minLength": 1, "maxLength": 200},
                    "max_chars": {"type": "integer", "minimum": 2000, "maximum": 120000},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            side_effect="read",
            capability=Capability.WORKSPACE_READ,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def _run(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self._spec, arguments)
        try:
            path = self.paths.resolve(arguments["path"])
        except WorkspacePathError as error:
            raise ToolArgumentError(str(error)) from None
        if path.suffix.lower() != ".pdf" or not path.is_file():
            raise ToolArgumentError("path must be a PDF file in the folder")
        part = arguments.get("part", "outline")
        maximum = int(arguments.get("max_chars", 40000))
        paper = load_paper(path)
        relative = self.paths.relative(path)
        report: dict[str, Any] = {"path": relative, "pages": paper.total_pages}
        if paper.total_pages > len(paper.pages):
            report["read_pages"] = len(paper.pages)
        if not any(text.strip() for text in paper.pages[:20]):
            report["note"] = "the PDF has no text layer (scanned pages): the text cannot be read"
            return json_result(report)
        if part == "outline":
            report.update(outline(paper))
            report["references"] = len(references(paper))
            report["link"] = f"[p. N]({relative}#page=N)"
        elif part == "text":
            wanted = page_numbers(str(arguments.get("pages") or "1-3"), len(paper.pages))
            chunks: list[str] = []
            used = 0
            shown: list[int] = []
            for number in wanted:
                block = f"--- page {number} ---\n{paper.pages[number - 1].strip()}\n"
                if used + len(block) > maximum and shown:
                    break
                chunks.append(block[: maximum - used])
                used += len(block)
                shown.append(number)
            report["shown_pages"] = shown
            if len(shown) < len(wanted):
                report["more_pages"] = wanted[len(shown) :][:50]
            report["text"] = "\n".join(chunks)
        elif part == "find":
            query = str(arguments.get("query") or "").strip()
            if not query:
                raise ToolArgumentError("part=find needs a query")
            report["matches"] = _find(paper, query)
        else:
            report["references"] = references(paper)
        if paper.problems:
            report["problems"] = paper.problems[:20]
        return json_result(report)

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await asyncio.to_thread(self._run, arguments)


def _find(paper: Paper, query: str, limit: int = 30) -> list[dict[str, Any]]:
    words = [re.escape(word) for word in query.split()]
    pattern = re.compile(r"\s+".join(words), re.IGNORECASE)
    matches: list[dict[str, Any]] = []
    for number, text in enumerate(paper.pages, 1):
        flat = re.sub(r"\s+", " ", text)
        for match in pattern.finditer(flat):
            start = max(0, match.start() - 160)
            matches.append({"page": number, "passage": flat[start : match.end() + 160]})
            if len(matches) >= limit:
                return matches
    return matches
