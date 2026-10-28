# ruff: noqa: RUF001 -- Chinese reference lists use full-width colons and brackets.
"""Check a reference list against the scholarly databases.

Each reference is looked up by its DOI, arXiv id or PMID, or by its text; the record found is
compared with what the reference claims (title, first author, year), and checked for a retraction.
A DOI that leads to a different paper, a reference no database knows, and a retracted paper are
the usual signs of a reference that was mistyped or made up.
"""

from __future__ import annotations

import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_workspace.scholar import bibtex, imports, sources
from agent_workspace.scholar.sources import Fetcher, citation_match_score
from agent_workspace.scholar.works import Work, arxiv_id, normalize_doi, title_similarity
from agent_workspace.tools.base import ToolError

MAX_REFERENCES = 150
_HEADINGS = re.compile(
    r"^\s*(?:#+\s*|\\section\*?\{|\\chapter\*?\{)?\s*(?:references|bibliography|works cited|"
    r"literature cited|参考文献|参考资料|引用文献)\s*\}?\s*[:：]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_CJK = re.compile(r"[\u4e00-\u9fff]")


@dataclass(slots=True)
class Reference:
    index: int
    text: str
    # What the reference states, when it could be read field by field (BibTeX, GB/T 7714).
    claimed: Work | None = None


def _split_entries(block: str) -> list[str]:
    block = block.strip()
    numbered = re.split(r"\n\s*(?=\[\d+\]|［\d+］|\d{1,3}[.、]\s)", "\n" + block)
    entries = [" ".join(part.split()) for part in numbered if part.strip()]
    if len(entries) <= 1:
        # Author-year lists: one reference per paragraph, or per line.
        paragraphs = [
            " ".join(part.split()) for part in re.split(r"\n\s*\n", block) if part.strip()
        ]
        entries = (
            paragraphs
            if len(paragraphs) > 1
            else [line.strip() for line in block.splitlines() if line.strip()]
        )
    return [
        re.sub(r"^\s*(?:\[\d+\]|［\d+］|\d{1,3}[.、])\s*", "", entry)
        for entry in entries
        if len(entry) > 15
    ]


def references_from_text(text: str) -> list[Reference]:
    """The references of a manuscript: the list after a References heading, a thebibliography
    environment, or the whole text when it is only a list."""
    bibitems = re.split(r"\\bibitem(?:\[[^\]]*\])?\{[^}]*\}", text)
    if len(bibitems) > 1:
        tail = bibitems[-1].split("\\end{thebibliography}")[0]
        entries = [" ".join(item.split()) for item in [*bibitems[1:-1], tail] if item.strip()]
    else:
        headings = list(_HEADINGS.finditer(text))
        block = text[headings[-1].end() :] if headings else text
        block = re.split(r"\n\s*(?:#+\s*)?(?:附录|appendix|致谢|acknowledg)", block, flags=re.I)[0]
        entries = _split_entries(block)
    references = []
    for index, entry in enumerate(entries[:MAX_REFERENCES], start=1):
        claimed = None
        if re.search(r"\[[A-Z]{1,2}(?:/OL)?\]", entry):
            parsed = imports.parse_gbt7714(entry)
            claimed = parsed[0] if parsed else None
        references.append(Reference(index, entry, claimed))
    return references


def references_from_file(path: Path, text: str) -> list[Reference]:
    """References from a .bib file (field by field) or a manuscript's text."""
    if path.suffix.casefold() == ".bib":
        works = bibtex.parse(text)
        return [
            Reference(index, f"{work.key}: {work.title}", work)
            for index, work in enumerate(works[:MAX_REFERENCES], start=1)
        ]
    if path.suffix.casefold() == ".tex" and "\\bibitem" not in text:
        resources = re.findall(r"\\(?:addbibresource|bibliography)\{([^}]+)\}", text)
        for resource in resources:
            for name in resource.split(","):
                candidate = path.parent / (
                    name.strip() if name.strip().endswith(".bib") else f"{name.strip()}.bib"
                )
                if candidate.is_file():
                    return references_from_file(
                        candidate, candidate.read_text(encoding="utf-8", errors="replace")
                    )
    return references_from_text(text)


def _fold(text: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", text.casefold())
        if character.isalnum()
    )


def _identifiers(reference: Reference) -> tuple[str, str] | None:
    claimed = reference.claimed
    if claimed is not None and claimed.doi:
        return "doi", claimed.doi
    if claimed is not None and claimed.arxiv:
        return "arxiv", claimed.arxiv
    doi = normalize_doi(reference.text)
    if doi:
        return "doi", doi
    identifier = arxiv_id(reference.text)
    if identifier:
        return "arxiv", identifier
    return None


def _query_text(reference: Reference) -> str:
    claimed = reference.claimed
    if claimed is not None and claimed.title:
        parts = [claimed.title]
        if claimed.authors:
            parts.append(claimed.authors[0].family or claimed.authors[0].literal)
        if claimed.year:
            parts.append(str(claimed.year))
        return " ".join(parts)
    return reference.text


def compare(reference: Reference, found: Work) -> list[str]:
    """Where the record found disagrees with the reference."""
    problems = []
    claimed = reference.claimed
    if claimed is not None and claimed.title:
        if title_similarity(claimed.title, found.title) < 0.85:
            problems.append(f"title differs; the record's title is “{found.title}”")
    elif citation_match_score(reference.text, found) < 0.8:
        problems.append(f"the record's title “{found.title}” is not in the reference")
    claimed_year = claimed.year if claimed is not None else None
    if claimed_year is None:
        years = [int(year) for year in re.findall(r"\b(?:19|20)\d{2}\b", reference.text)]
        claimed_year = years[0] if len(set(years)) == 1 else None
    if claimed_year and found.year and abs(claimed_year - found.year) > 1:
        problems.append(f"year differs; the record says {found.year}")
    if found.authors:
        family = found.authors[0].family or found.authors[0].literal
        if claimed is not None and claimed.authors:
            stated = claimed.authors[0].family or claimed.authors[0].literal
            if _fold(stated) and _fold(family) and _fold(stated) != _fold(family):
                first = found.authors[0].display()
                problems.append(f"first author differs; the record's first author is {first}")
        elif family and _fold(family) not in _fold(reference.text) and not found.authors[0].cjk:
            problems.append(f"first author {found.authors[0].display()} is not in the reference")
    return problems


def check_reference(reference: Reference, fetch: Fetcher, timeout: int) -> dict[str, Any]:
    report: dict[str, Any] = {"index": reference.index, "reference": reference.text[:400]}
    cjk = bool(_CJK.search(reference.text))
    identifier = _identifiers(reference)
    found: Work | None = None
    problems: list[str] = []
    try:
        if identifier is not None:
            found = sources.lookup(*identifier, fetch=fetch, timeout=timeout)
            if found is None and identifier[0] == "doi":
                problems.append(f"the DOI {identifier[1]} does not exist")
        if found is None:
            by_text = sources.lookup("query", _query_text(reference), fetch=fetch, timeout=timeout)
            if by_text is not None:
                found = by_text
                if (
                    identifier is not None
                    and identifier[0] == "doi"
                    and by_text.doi
                    and by_text.doi.casefold() != identifier[1].casefold()
                ):
                    problems.append(f"the work's DOI is {by_text.doi}")
    except ToolError as exc:
        report.update(status="error", problems=[f"the databases could not be reached: {exc}"[:300]])
        return report
    if found is None:
        report["status"] = "unverifiable" if cjk else "not_found"
        report["problems"] = problems or (
            ["Chinese databases (CNKI, Wanfang) cannot be searched here; check it there"]
            if cjk
            else ["no database knows this work; it may be mistyped or made up"]
        )
        return report
    problems.extend(compare(reference, found))
    report["found"] = found.summary(abstract_chars=0)
    if found.retracted:
        report["status"] = "retracted"
        problems.insert(0, "the work has been retracted")
    else:
        report["status"] = "mismatch" if problems else "verified"
    if problems:
        report["problems"] = problems
    return report


def check(
    references: list[Reference],
    *,
    fetch: Fetcher | None = None,
    timeout: int = 20,
    workers: int = 4,
) -> dict[str, Any]:
    """Every reference's report and a count by status."""
    caller = fetch or sources._fetch
    with ThreadPoolExecutor(max_workers=workers) as pool:
        reports = list(
            pool.map(lambda reference: check_reference(reference, caller, timeout), references)
        )
    counts: dict[str, int] = {}
    for report in reports:
        counts[report["status"]] = counts.get(report["status"], 0) + 1
    return {"checked": len(reports), "counts": counts, "references": reports}


__all__ = [
    "MAX_REFERENCES",
    "Reference",
    "check",
    "check_reference",
    "compare",
    "references_from_file",
    "references_from_text",
]
