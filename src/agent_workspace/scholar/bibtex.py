# ruff: noqa: RUF001 -- LaTeX accents map to letters like the dotless i, and page ranges use en dashes.
"""BibTeX: read .bib files (entries, @string macros, LaTeX accents) and write records as BibTeX."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from agent_workspace.scholar.works import Person, Work, arxiv_id, normalize_doi, parse_name

_MONTHS = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}
_TYPES = {
    "article": "article-journal",
    "inproceedings": "paper-conference",
    "conference": "paper-conference",
    "proceedings": "book",
    "book": "book",
    "inbook": "chapter",
    "incollection": "chapter",
    "phdthesis": "thesis",
    "mastersthesis": "thesis",
    "thesis": "thesis",
    "techreport": "report",
    "report": "report",
    "online": "webpage",
    "electronic": "webpage",
    "www": "webpage",
    "dataset": "dataset",
    "patent": "patent",
    "standard": "standard",
    "software": "software",
    "unpublished": "article",
    "misc": "article",
}
_ACCENTS = {
    "'": "\u0301",
    "`": "\u0300",
    "^": "\u0302",
    '"': "\u0308",
    "~": "\u0303",
    "=": "\u0304",
    ".": "\u0307",
    "u": "\u0306",
    "v": "\u030c",
    "H": "\u030b",
    "c": "\u0327",
    "k": "\u0328",
    "r": "\u030a",
}
_SYMBOLS = {
    r"\ss": "ß",
    r"\o": "ø",
    r"\O": "Ø",
    r"\ae": "æ",
    r"\AE": "Æ",
    r"\oe": "œ",
    r"\OE": "Œ",
    r"\aa": "å",
    r"\AA": "Å",
    r"\l": "ł",
    r"\L": "Ł",
    r"\i": "ı",
    r"\j": "ȷ",
}


class BibtexError(ValueError):
    """The text is not BibTeX the reader can use."""


def _read_braced(text: str, start: int) -> tuple[str, int]:
    """The contents of the braced group opening at ``start``, and the index after it."""
    depth = 0
    for index in range(start, len(text)):
        character = text[index]
        if character == "\\":
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
    raise BibtexError("a brace is not closed")


def _read_quoted(text: str, start: int) -> tuple[str, int]:
    depth = 0
    for index in range(start + 1, len(text)):
        character = text[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
        elif character == '"' and depth == 0 and text[index - 1] != "\\":
            return text[start + 1 : index], index + 1
    raise BibtexError("a quote is not closed")


def _read_value(text: str, start: int, macros: dict[str, str]) -> tuple[str, int]:
    """A field value: braced or quoted parts, numbers and macros joined with #."""
    parts: list[str] = []
    index = start
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        character = text[index]
        if character == "{":
            part, index = _read_braced(text, index)
        elif character == '"':
            part, index = _read_quoted(text, index)
        else:
            match = re.compile(r"[^\s,#}]+").match(text, index)
            if not match:
                break
            word = match.group(0)
            index = match.end()
            part = (
                word
                if word.isdigit()
                else macros.get(word.casefold(), _MONTHS.get(word.casefold()[:3], word))
            )
        parts.append(part)
        while index < len(text) and text[index].isspace():
            index += 1
        if index < len(text) and text[index] == "#":
            index += 1
            continue
        break
    return "".join(parts), index


def latex_to_text(value: str) -> str:
    """Plain Unicode text from a BibTeX value: accents, escapes and protective braces resolved."""
    text = value
    text = re.sub(
        r"\\([`'^\"~=.uvHckr])\s*\{?\\?([A-Za-z])\}?",
        lambda match: match.group(2) + _ACCENTS[match.group(1)],
        text,
    )
    for command, symbol in _SYMBOLS.items():
        text = re.sub(re.escape(command) + r"(?![A-Za-z])\s*", symbol, text)
    text = re.sub(
        r"\\(?:textit|textbf|emph|textrm|textsf|texttt|mathrm|mbox|text)\s*\{([^{}]*)\}",
        r"\1",
        text,
    )
    text = text.replace(r"\&", "&").replace(r"\%", "%").replace(r"\$", "$").replace(r"\_", "_")
    text = text.replace(r"\#", "#").replace("---", "—").replace("--", "–").replace("~", " ")
    text = text.replace("``", "“").replace("''", "”")
    text = re.sub(r"(?<!\\)[{}]", "", text)
    return " ".join(unicodedata.normalize("NFC", text).split())


def _people(value: str) -> list[Person]:
    names = [part.strip() for part in re.split(r"\s+and\s+(?![^{}]*\})", value) if part.strip()]
    people = []
    for name in names:
        if name.casefold() == "others":
            continue
        if name.startswith("{") and name.endswith("}") and name.count("{") == 1:
            people.append(Person(literal=latex_to_text(name)))
            continue
        people.append(parse_name(latex_to_text(name)))
    return people


def parse(text: str) -> list[Work]:
    """Every entry of a .bib file as a record; @comment and @preamble are skipped."""
    works: list[Work] = []
    macros: dict[str, str] = {}
    index = 0
    while True:
        at = text.find("@", index)
        if at < 0:
            break
        match = re.compile(r"@\s*([A-Za-z]+)\s*([{(])").match(text, at)
        if not match:
            index = at + 1
            continue
        kind = match.group(1).casefold()
        opener = match.end() - 1
        if match.group(2) == "(":
            closing = text.find(")", opener)
            body = text[opener + 1 : closing if closing > 0 else len(text)]
            index = closing + 1 if closing > 0 else len(text)
        else:
            body, index = _read_braced(text, opener)
        if kind in {"comment", "preamble"}:
            continue
        if kind == "string":
            name, _, rest = body.partition("=")
            value, _ = _read_value(rest, 0, macros)
            macros[name.strip().casefold()] = value
            continue
        works.append(_entry(kind, body, macros))
    return works


def _entry(kind: str, body: str, macros: dict[str, str]) -> Work:
    key, _, rest = body.partition(",")
    fields: dict[str, str] = {}
    index = 0
    while index < len(rest):
        match = re.compile(r"\s*([A-Za-z][\w\-:.]*)\s*=\s*").match(rest, index)
        if not match:
            next_comma = rest.find(",", index)
            if next_comma < 0:
                break
            index = next_comma + 1
            continue
        value, index = _read_value(rest, match.end(), macros)
        fields[match.group(1).casefold()] = value
        comma = rest.find(",", index)
        index = comma + 1 if comma >= 0 else len(rest)
    work_type = _TYPES.get(kind, "article-journal")
    eprint = fields.get("eprint", "")
    archive = fields.get("archiveprefix", fields.get("eprinttype", "")).casefold()
    if (
        kind == "misc"
        and not eprint
        and fields.get("howpublished", "").casefold().startswith("\\url")
    ):
        work_type = "webpage"
    date = latex_to_text(fields.get("date", ""))
    year_text = latex_to_text(fields.get("year", "")) or date[:4]
    month = latex_to_text(fields.get("month", ""))
    if not date and year_text.isdigit():
        month_number = _MONTHS.get(month.casefold()[:3], month.zfill(2) if month.isdigit() else "")
        date = f"{year_text}-{month_number}" if month_number else year_text
    container = fields.get("journal") or fields.get("journaltitle") or fields.get("booktitle") or ""
    publisher = fields.get("publisher") or fields.get("school") or fields.get("institution") or ""
    url = latex_to_text(
        re.sub(r"\\url\{([^}]*)\}", r"\1", fields.get("url", "") or fields.get("howpublished", ""))
    )
    work = Work(
        type=work_type,
        title=latex_to_text(fields.get("title", "")),
        authors=_people(fields.get("author", "")),
        editors=_people(fields.get("editor", "")),
        year=int(year_text) if year_text[:4].isdigit() else None,
        date=date,
        container=latex_to_text(container),
        volume=latex_to_text(fields.get("volume", "")),
        issue=latex_to_text(fields.get("number", fields.get("issue", ""))),
        pages=latex_to_text(fields.get("pages", "")).replace("–", "-"),
        publisher=latex_to_text(publisher),
        place=latex_to_text(fields.get("address", fields.get("location", ""))),
        edition=latex_to_text(fields.get("edition", "")),
        genre={"phdthesis": "PhD thesis", "mastersthesis": "Master's thesis"}.get(
            kind, latex_to_text(fields.get("type", ""))
        ),
        number=latex_to_text(fields.get("number", ""))
        if work_type in {"report", "patent", "standard"}
        else "",
        doi=normalize_doi(fields.get("doi", "")),
        arxiv=(arxiv_id(f"arXiv:{eprint}") or "")
        if eprint and (archive == "arxiv" or not archive)
        else "",
        pmid=latex_to_text(fields.get("pmid", "")),
        isbn=latex_to_text(fields.get("isbn", "")),
        url=url if url.startswith("http") else "",
        accessed=latex_to_text(fields.get("urldate", "")),
        abstract=latex_to_text(fields.get("abstract", "")),
        language=latex_to_text(fields.get("langid", fields.get("language", ""))),
        keywords=[
            word.strip()
            for word in latex_to_text(fields.get("keywords", "")).split(",")
            if word.strip()
        ],
        note=latex_to_text(fields.get("note", "")),
        key=key.strip(),
        source="bibtex",
    )
    if work.arxiv and work_type in {"article-journal"} and not work.container:
        work.type = "article"
    if work.type == "article" and work.arxiv:
        work.container = work.container or "arXiv"
    if not work.language and re.search(r"[\u4e00-\u9fff]", work.title):
        work.language = "zh"
    if work.number:
        work.issue = ""  # a report's or patent's number, not an issue
    return work


_ESCAPES = str.maketrans({"&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_", "$": r"\$"})
_WRITE_TYPES = {
    "article-journal": "article",
    "paper-conference": "inproceedings",
    "book": "book",
    "chapter": "incollection",
    "report": "techreport",
    "webpage": "online",
    "dataset": "misc",
    "patent": "patent",
    "standard": "misc",
    "software": "software",
    "article-newspaper": "article",
    "article": "misc",
}


def _escape(value: str) -> str:
    return value.translate(_ESCAPES)


def _names(people: Iterable[Person]) -> str:
    rendered = []
    for person in people:
        if person.literal:
            rendered.append("{" + _escape(person.literal) + "}")
        elif person.cjk:
            rendered.append(
                _escape(f"{person.family}, {person.given}" if person.given else person.family)
            )
        else:
            rendered.append(_escape(f"{person.family}, {person.given}".strip(", ")))
    return " and ".join(rendered)


def write_entry(work: Work) -> str:
    """One record as a BibTeX entry, keyed by its citation key."""
    kind = _WRITE_TYPES.get(work.type, "misc")
    if work.type == "thesis":
        kind = "mastersthesis" if re.search(r"master|硕士", work.genre, re.I) else "phdthesis"
    fields: list[tuple[str, str]] = []
    if work.authors:
        fields.append(("author", _names(work.authors)))
    if work.editors:
        fields.append(("editor", _names(work.editors)))
    fields.append(("title", _escape(work.title)))
    container_field = {
        "article": "journal",
        "inproceedings": "booktitle",
        "incollection": "booktitle",
    }.get(kind)
    if container_field and work.container:
        fields.append((container_field, _escape(work.container)))
    elif kind == "misc" and work.container and work.container != "arXiv":
        fields.append(("howpublished", _escape(work.container)))
    if work.year is not None:
        fields.append(("year", str(work.year)))
    if work.date and len(work.date) >= 7:
        fields.append(("month", str(int(work.date[5:7]))))
    for name, value in (
        ("volume", work.volume),
        ("number", work.issue if kind == "article" else work.number),
        ("pages", work.pages.replace("-", "--") if "--" not in work.pages else work.pages),
        ("edition", work.edition),
    ):
        if value:
            fields.append((name, _escape(value)))
    if work.publisher:
        fields.append(
            (
                {"phdthesis": "school", "mastersthesis": "school", "techreport": "institution"}.get(
                    kind, "publisher"
                ),
                _escape(work.publisher),
            )
        )
    if work.place:
        fields.append(("address", _escape(work.place)))
    if work.doi:
        fields.append(("doi", work.doi))
    if work.arxiv:
        fields.extend((("eprint", work.arxiv), ("archiveprefix", "arXiv")))
    if work.pmid:
        fields.append(("pmid", work.pmid))
    if work.isbn:
        fields.append(("isbn", work.isbn))
    if work.url and not work.doi:
        fields.append(("url", work.url))
    if work.accessed:
        fields.append(("urldate", work.accessed))
    if work.language.startswith("zh"):
        fields.append(("langid", "chinese"))
    if work.note:
        fields.append(("note", _escape(work.note)))
    width = max(len(name) for name, _ in fields)
    lines = [f"@{kind}{{{work.key or 'ref'},"]
    lines.extend(f"  {name.ljust(width)} = {{{value}}}," for name, value in fields)
    lines.append("}")
    return "\n".join(lines)


def write(works: Iterable[Work]) -> str:
    return "\n\n".join(write_entry(work) for work in works) + "\n"


__all__ = ["BibtexError", "latex_to_text", "parse", "write", "write_entry"]
