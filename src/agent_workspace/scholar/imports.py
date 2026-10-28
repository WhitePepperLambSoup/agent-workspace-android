# ruff: noqa: RUF001 -- Chinese reference formats use full-width punctuation on purpose.
"""Read references in the formats researchers export: BibTeX, RIS, EndNote, RefWorks, NoteExpress
(the formats CNKI, Wanfang and most databases offer), CSL-JSON, and reference lists written in
GB/T 7714 text.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from agent_workspace.scholar import bibtex
from agent_workspace.scholar.works import Person, Work, arxiv_id, normalize_doi, parse_name

_RIS_TYPES = {
    "JOUR": "article-journal",
    "JFULL": "article-journal",
    "MGZN": "article-journal",
    "CONF": "paper-conference",
    "CPAPER": "paper-conference",
    "BOOK": "book",
    "EBOOK": "book",
    "CHAP": "chapter",
    "ECHAP": "chapter",
    "THES": "thesis",
    "RPRT": "report",
    "ELEC": "webpage",
    "WEB": "webpage",
    "DATA": "dataset",
    "PAT": "patent",
    "STAND": "standard",
    "NEWS": "article-newspaper",
    "UNPB": "article",
    "GEN": "article",
    "COMP": "software",
}
# EndNote, RefWorks and NoteExpress name types in words.
_WORD_TYPES = {
    "journal article": "article-journal",
    "期刊": "article-journal",
    "conference proceedings": "paper-conference",
    "conference paper": "paper-conference",
    "会议": "paper-conference",
    "book": "book",
    "图书": "book",
    "book section": "chapter",
    "thesis": "thesis",
    "dissertation": "thesis",
    "dissertation/thesis": "thesis",
    "学位论文": "thesis",
    "report": "report",
    "报告": "report",
    "patent": "patent",
    "专利": "patent",
    "standard": "standard",
    "标准": "standard",
    "newspaper article": "article-newspaper",
    "报纸": "article-newspaper",
    "web page": "webpage",
    "electronic source": "webpage",
    "dataset": "dataset",
}
_GBT_TYPES = {
    "J": "article-journal",
    "M": "book",
    "C": "paper-conference",
    "D": "thesis",
    "R": "report",
    "S": "standard",
    "P": "patent",
    "N": "article-newspaper",
    "EB": "webpage",
    "DB": "dataset",
    "CP": "software",
    "Z": "article",
    "G": "book",
    "A": "chapter",
}


class ImportError_(ValueError):
    """The text is in none of the formats this reads."""


def _split_names(value: str) -> list[Person]:
    names = [part.strip() for part in re.split(r"[;；]|\s+and\s+", value) if part.strip()]
    return [parse_name(name) for name in names]


def _year(value: str) -> tuple[int | None, str]:
    match = re.search(r"((?:1[5-9]|20)\d{2})(?:[-/.](\d{1,2}))?(?:[-/.](\d{1,2}))?", value or "")
    if not match:
        return None, ""
    year, month, day = match.group(1), match.group(2), match.group(3)
    date = (
        year
        + (f"-{int(month):02d}" if month else "")
        + (f"-{int(day):02d}" if month and day else "")
    )
    return int(year), date


def _pages(start: str, end: str = "") -> str:
    start, end = start.strip(), end.strip()
    return f"{start}-{end}" if start and end and end != start else start


def _finish(work: Work) -> Work:
    if not work.language and re.search(r"[一-鿿]", work.title):
        work.language = "zh"
    if not work.arxiv:
        work.arxiv = arxiv_id(work.url) or ""
    if work.type == "article-journal" and work.arxiv and not work.container:
        work.type, work.container = "article", "arXiv"
    return work


def parse_ris(text: str) -> list[Work]:
    works: list[Work] = []
    fields: dict[str, list[str]] = {}
    for raw in text.splitlines():
        match = re.match(r"^([A-Z][A-Z0-9])\s{1,2}-\s?(.*)$", raw)
        if not match:
            if fields and raw.strip() and works is not None:
                last = next(reversed(fields), None)
                if last:
                    fields[last][-1] += " " + raw.strip()
            continue
        tag, value = match.group(1), match.group(2).strip()
        if tag == "ER":
            if fields:
                works.append(_ris_work(fields))
            fields = {}
            continue
        fields.setdefault(tag, []).append(value)
    if fields:
        works.append(_ris_work(fields))
    return works


def _ris_work(fields: dict[str, list[str]]) -> Work:
    def one(*tags: str) -> str:
        return next((fields[tag][0] for tag in tags if fields.get(tag) and fields[tag][0]), "")

    year, date = _year(one("PY", "Y1", "DA"))
    _, full_date = _year(one("DA", "Y1"))
    kind = _RIS_TYPES.get(one("TY").upper(), "article-journal")
    authors = [parse_name(name) for tag in ("AU", "A1") for name in fields.get(tag, [])]
    editors = (
        [parse_name(name) for tag in ("ED", "A2") for name in fields.get(tag, [])]
        if kind in {"chapter", "paper-conference"}
        else []
    )
    serial = one("SN")
    return _finish(
        Work(
            type=kind,
            title=one("TI", "T1", "CT"),
            authors=authors,
            editors=editors,
            year=year,
            date=full_date if len(full_date) > len(date) else date,
            container=one("T2", "JO", "JF", "JA", "BT", "T3") if kind != "book" else one("T3"),
            volume=one("VL"),
            issue=one("IS"),
            pages=_pages(one("SP"), one("EP")),
            publisher=one("PB"),
            place=one("CY", "PP"),
            edition=one("ET"),
            number=one("M1") if kind in {"report", "patent", "standard"} else "",
            doi=normalize_doi(one("DO", "M3")),
            isbn=serial if kind in {"book", "chapter"} else "",
            url=one("UR", "L2"),
            abstract=one("AB", "N2"),
            language=one("LA"),
            keywords=[word for word in fields.get("KW", []) if word],
            note=one("N1"),
            source="ris",
        )
    )


def _tagged_records(text: str, pattern: str, start_tag: str) -> list[dict[str, list[str]]]:
    """Records of a tagged format: each starts at start_tag; a line without a tag continues."""
    records: list[dict[str, list[str]]] = []
    current: dict[str, list[str]] | None = None
    last_tag = ""
    for raw in text.splitlines():
        match = re.match(pattern, raw)
        if match:
            tag, value = match.group(1), match.group(2).strip()
            if tag == start_tag or current is None:
                current = {}
                records.append(current)
            current.setdefault(tag, []).append(value)
            last_tag = tag
        elif current is not None and raw.strip() and last_tag:
            current[last_tag][-1] += " " + raw.strip()
    return records


def _record_work(
    fields: dict[str, list[str]],
    tags: dict[str, tuple[str, ...]],
    *,
    source: str,
) -> Work:
    def one(name: str) -> str:
        for tag in tags.get(name, ()):
            for value in fields.get(tag, []):
                if value.strip():
                    return value.strip()
        return ""

    def every(name: str) -> list[str]:
        return [
            value for tag in tags.get(name, ()) for value in fields.get(tag, []) if value.strip()
        ]

    kind = _WORD_TYPES.get(one("type").casefold().rstrip("."), "article-journal")
    authors: list[Person] = []
    for value in every("author"):
        authors.extend(_split_names(value))
    year, date = _year(one("date") or one("year"))
    pages = one("pages")
    keywords = [
        word.strip()
        for value in every("keywords")
        for word in re.split(r"[;；,，]", value)
        if word.strip()
    ]
    container = one("journal") or one("container")
    publisher = one("publisher") or (one("school") if kind == "thesis" else "")
    return _finish(
        Work(
            type=kind,
            title=one("title"),
            authors=authors,
            year=year,
            date=date,
            container=container,
            volume=one("volume"),
            issue=one("issue").lstrip("0") or one("issue"),
            pages=pages.replace("+", ", "),
            publisher=publisher,
            place=one("place"),
            genre=one("genre"),
            doi=normalize_doi(one("doi")),
            isbn=one("isbn") if kind in {"book", "chapter"} else "",
            url=one("url"),
            abstract=one("abstract"),
            language="zh" if "中文" in one("language") else one("language"),
            keywords=keywords,
            note=one("note"),
            source=source,
        )
    )


_ENDNOTE_TAGS = {
    "type": ("%0",),
    "author": ("%A",),
    "title": ("%T",),
    "journal": ("%J", "%B"),
    "date": ("%D", "%8"),
    "volume": ("%V",),
    "issue": ("%N",),
    "pages": ("%P",),
    "publisher": ("%I",),
    "place": ("%C",),
    "keywords": ("%K",),
    "abstract": ("%X",),
    "doi": ("%R",),
    "url": ("%U",),
    "isbn": ("%@",),
    "language": ("%G",),
    "note": ("%Z",),
    "genre": ("%9",),
}
_REFWORKS_TAGS = {
    "type": ("RT",),
    "author": ("A1", "AU"),
    "title": ("T1",),
    "journal": ("JF", "JO", "T2"),
    "year": ("YR",),
    "date": ("FD",),
    "volume": ("VO",),
    "issue": ("IS",),
    "pages": ("OP", "SP"),
    "publisher": ("PB",),
    "place": ("PP",),
    "keywords": ("K1",),
    "abstract": ("AB",),
    "doi": ("DO",),
    "url": ("LK", "UL"),
    "isbn": ("SN",),
    "language": ("LA",),
    "note": ("NO",),
    "school": ("PB",),
}
_NOTEEXPRESS_TAGS = {
    "type": ("Reference Type",),
    "author": ("Author",),
    "title": ("Title",),
    "journal": ("Journal", "Secondary Title"),
    "year": ("Year",),
    "date": ("Date",),
    "volume": ("Volume",),
    "issue": ("Issue",),
    "pages": ("Pages",),
    "publisher": ("Publisher",),
    "place": ("Place Published",),
    "keywords": ("Keywords",),
    "abstract": ("Abstract",),
    "doi": ("DOI",),
    "url": ("URL",),
    "isbn": ("ISBN/ISSN",),
    "language": ("Language",),
    "note": ("Notes",),
    "school": ("Publisher", "Tertiary Author"),
    "genre": ("Type of Work",),
}


def parse_endnote(text: str) -> list[Work]:
    records = _tagged_records(text, r"^(%[0-9A-Z@+#$^&*!~>])\s(.*)$", "%0")
    return [_record_work(record, _ENDNOTE_TAGS, source="endnote") for record in records]


def parse_refworks(text: str) -> list[Work]:
    records = _tagged_records(text, r"^([A-Z][A-Z0-9])\s(.*)$", "RT")
    return [_record_work(record, _REFWORKS_TAGS, source="refworks") for record in records]


def parse_noteexpress(text: str) -> list[Work]:
    records = _tagged_records(text, r"^\{([^}]+)\}\s*[:：]\s*(.*)$", "Reference Type")
    return [_record_work(record, _NOTEEXPRESS_TAGS, source="noteexpress") for record in records]


def parse_csl_json(text: str) -> list[Work]:
    document = json.loads(text)
    items = document.get("items") if isinstance(document, dict) else document
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        raise ImportError_("CSL-JSON must be a list of items")
    return [Work.from_csl(item) for item in items if isinstance(item, dict)]


_GBT_ENTRY = re.compile(
    r"^\s*(?:\[\d+\]|\d+[.、]|［\d+］)?\s*(?P<authors>.*?)[.．]\s*(?P<title>[^\[\]]+?)"
    r"\s*\[(?P<kind>[A-Z]{1,2})(?:/OL)?\]\s*(?:/{2}(?P<parent>[^.．]*?)[.．])?\s*(?P<rest>.*)$"
)


def parse_gbt7714(text: str) -> list[Work]:
    """References written in GB/T 7714 (numbered or author-year), one per line."""
    works = []
    for line in re.split(r"\n+|(?=\[\d+\])", text):
        line = line.strip()
        if not line:
            continue
        match = _GBT_ENTRY.match(line)
        if not match:
            continue
        kind = _GBT_TYPES.get(match.group("kind"), "article")
        authors_text = re.sub(
            r"\s*(?:,|，)?\s*(?:等|et al)\.?$", "", match.group("authors").strip(), flags=re.I
        )
        authors = [
            _gbt_name(name)
            for name in re.split(r"[,，;；]\s*", authors_text)
            if name.strip() and not re.fullmatch(r"\d{4}[a-z]?", name.strip())
        ]
        rest = match.group("rest").strip().lstrip(".．").strip().rstrip(".")
        work = Work(
            type=kind, title=match.group("title").strip(), authors=authors, source="gbt7714"
        )
        doi = re.search(r"DOI\s*[:：]\s*(\S+)", rest, re.I)
        if doi:
            work.doi = normalize_doi(doi.group(1))
            rest = rest[: doi.start()].rstrip(" .")
        url = re.search(r"https?://\S+", rest)
        if url:
            work.url = url.group(0).rstrip(".")
            rest = rest[: url.start()].rstrip(" .")
        if kind == "article-journal":
            journal = re.match(
                r"(?P<journal>[^,，]+)[,，]\s*(?P<year>\d{4})[a-z]?(?:[,，]\s*(?P<volume>[^(（:：]*))?"
                r"(?:[(（](?P<issue>[^)）]*)[)）])?(?:\s*[:：]\s*(?P<pages>[\w\-–+, ]+))?",
                rest,
            )
            if journal:
                work.container = journal.group("journal").strip()
                work.year = int(journal.group("year"))
                work.volume = (journal.group("volume") or "").strip()
                work.issue = (journal.group("issue") or "").strip()
                work.pages = (journal.group("pages") or "").strip().replace("–", "-")
        else:
            work.year, work.date = _year(rest)
            place = re.match(
                r"(?:(?P<edition>[^.．]*?版)[.．]\s*)?(?P<place>[^:：,，]+)[:：]\s*(?P<publisher>[^,，]+)",
                rest,
            )
            if place:
                work.place = place.group("place").strip()
                work.publisher = place.group("publisher").strip()
                if place.group("edition"):
                    work.edition = place.group("edition").strip()
            pages = re.search(r"[:：]\s*(\d+[\-–]\d+)\s*$", rest)
            if pages:
                work.pages = pages.group(1).replace("–", "-")
            if match.group("parent"):
                work.container = match.group("parent").split("//")[-1].strip()
        works.append(_finish(work))
    return works


def _gbt_name(text: str) -> Person:
    name = text.strip().strip(".")
    if re.search(r"[一-鿿]", name):
        return parse_name(name)
    # "SMITH J A" or "Smith J A": the family name first, then initials.
    parts = name.split()
    if len(parts) >= 2 and all(len(part.strip(".")) <= 2 for part in parts[1:]):
        family = parts[0].title() if parts[0].isupper() else parts[0]
        return Person(family=family, given=" ".join(part.strip(".") for part in parts[1:]))
    return parse_name(name)


_PARSERS: tuple[tuple[str, Callable[[str], bool], Callable[[str], list[Work]]], ...] = (
    ("csl-json", lambda text: text.lstrip().startswith(("[", "{")), parse_csl_json),
    ("bibtex", lambda text: re.search(r"@\s*[A-Za-z]+\s*[{(]", text) is not None, bibtex.parse),
    ("ris", lambda text: re.search(r"^TY\s{1,2}-", text, re.M) is not None, parse_ris),
    ("noteexpress", lambda text: "{Reference Type}" in text, parse_noteexpress),
    ("endnote", lambda text: re.search(r"^%0\s", text, re.M) is not None, parse_endnote),
    ("refworks", lambda text: re.search(r"^RT\s", text, re.M) is not None, parse_refworks),
    (
        "gbt7714",
        lambda text: re.search(r"\[[JMCDRSPN](?:/OL)?\]|\[EB/OL\]", text) is not None,
        parse_gbt7714,
    ),
)


_RIS_WRITE_TYPES = {value: key for key, value in reversed(list(_RIS_TYPES.items()))}


def write_ris(works: list[Work]) -> str:
    """Records as RIS, which EndNote, NoteExpress, Zotero and Mendeley all import."""
    blocks = []
    for work in works:
        lines = [f"TY  - {_RIS_WRITE_TYPES.get(work.type, 'GEN')}"]
        lines.extend(
            f"AU  - {person.literal or (person.family + ', ' + person.given).strip(', ')}"
            for person in work.authors
        )
        lines.extend(
            f"ED  - {person.literal or (person.family + ', ' + person.given).strip(', ')}"
            for person in work.editors
        )
        start, _, end = work.pages.replace("–", "-").partition("-")
        for tag, value in (
            ("TI", work.title),
            ("T2", work.container),
            ("PY", str(work.year or "")),
            ("DA", work.date.replace("-", "/")),
            ("VL", work.volume),
            ("IS", work.issue),
            ("SP", start),
            ("EP", end),
            ("PB", work.publisher),
            ("CY", work.place),
            ("ET", work.edition),
            ("DO", work.doi),
            ("SN", work.isbn),
            ("UR", work.url or (f"https://arxiv.org/abs/{work.arxiv}" if work.arxiv else "")),
            ("AB", work.abstract),
            ("LA", work.language),
            ("N1", work.note),
            ("ID", work.key),
        ):
            if value:
                lines.append(f"{tag}  - {value}")
        lines.extend(f"KW  - {word}" for word in work.keywords)
        lines.append("ER  - ")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def detect(text: str) -> str | None:
    for name, test, _ in _PARSERS:
        if test(text):
            return name
    return None


def parse_any(text: str) -> tuple[str, list[Work]]:
    """The format the text is in, and its records."""
    for name, test, parser in _PARSERS:
        if test(text):
            try:
                works = parser(text)
            except (ValueError, json.JSONDecodeError):
                continue
            works = [work for work in works if work.title]
            if works:
                return name, works
    raise ImportError_(
        "no references found; supported: BibTeX, RIS, EndNote, RefWorks, NoteExpress, CSL-JSON, "
        "GB/T 7714 text"
    )


__all__ = [
    "ImportError_",
    "detect",
    "parse_any",
    "parse_csl_json",
    "parse_endnote",
    "parse_gbt7714",
    "parse_noteexpress",
    "parse_refworks",
    "parse_ris",
    "write_ris",
]
