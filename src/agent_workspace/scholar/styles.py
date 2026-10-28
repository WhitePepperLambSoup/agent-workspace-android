# ruff: noqa: RUF001 -- the styles print en dashes and Chinese punctuation on purpose.
"""Reference lists and in-text citations in the styles journals and theses ask for most:
GB/T 7714-2015 (numeric and author-year), APA 7, IEEE, Vancouver and Nature.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from agent_workspace.scholar.works import _SURNAME_PINYIN, Person, Work

STYLES = {
    "gb7714-numeric": "GB/T 7714-2015 顺序编码制",
    "gb7714-author-year": "GB/T 7714-2015 著者-出版年制",
    "apa": "APA 7th",
    "ieee": "IEEE",
    "vancouver": "Vancouver",
    "nature": "Nature",
}
NUMERIC_STYLES = frozenset({"gb7714-numeric", "ieee", "vancouver", "nature"})
_GBT_CODES = {
    "article-journal": "J",
    "book": "M",
    "chapter": "M",
    "paper-conference": "C",
    "thesis": "D",
    "report": "R",
    "standard": "S",
    "patent": "P",
    "article-newspaper": "N",
    "webpage": "EB/OL",
    "dataset": "DS",
    "software": "CP",
    "article": "EB/OL",
}


@dataclass(frozen=True, slots=True)
class Markup:
    markdown: bool = False

    def italic(self, text: str) -> str:
        return f"*{text}*" if self.markdown and text else text


def _initials(given: str, *, dots: bool, space: bool = True) -> str:
    parts = []
    for word in re.split(r"\s+", given.strip()):
        if not word:
            continue
        pieces = [piece for piece in word.split("-") if piece]
        if not pieces:
            continue
        joined = "-".join(piece[0].upper() + ("." if dots else "") for piece in pieces)
        parts.append(joined)
    return (" " if space else "").join(parts)


def _clean(text: str) -> str:
    return " ".join(text.split()).rstrip(".")


def _dash(pages: str) -> str:
    return re.sub(r"\s*[-–—]+\s*", "–", pages)


def _year_label(work: Work, suffix: str = "") -> str:
    return f"{work.year}{suffix}" if work.year else "n.d."


# ----------------------------------------------------------------------------- name lists


def _gbt_name(person: Person) -> str:
    if person.literal:
        return person.literal
    if person.cjk:
        return f"{person.family}{person.given}"
    return f"{person.family.upper()} {_initials(person.given, dots=False)}".strip()


def _gbt_authors(people: Sequence[Person], cjk: bool) -> str:
    if not people:
        return ""
    names = [_gbt_name(person) for person in people[:3]]
    text = ", ".join(names)
    if len(people) > 3:
        text += ", 等" if cjk else ", et al"
    return text


def _apa_name(person: Person) -> str:
    if person.literal:
        return person.literal
    if person.cjk:
        return f"{person.family}{person.given}"
    initials = _initials(person.given, dots=True)
    return f"{person.family}, {initials}" if initials else person.family


def _apa_authors(people: Sequence[Person]) -> str:
    names = [_apa_name(person) for person in people]
    if not names:
        return ""
    if len(names) > 20:
        return ", ".join(names[:19]) + ", . . . " + names[-1]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + ", & " + names[-1]


def _ieee_name(person: Person) -> str:
    if person.literal:
        return person.literal
    if person.cjk:
        return f"{person.family}{person.given}"
    initials = _initials(person.given, dots=True)
    return f"{initials} {person.family}".strip()


def _ieee_authors(people: Sequence[Person]) -> str:
    if not people:
        return ""
    if len(people) > 6:
        return f"{_ieee_name(people[0])} et al."
    names = [_ieee_name(person) for person in people]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + ", and " + names[-1]


def _vancouver_name(person: Person) -> str:
    if person.literal:
        return person.literal
    if person.cjk:
        return f"{person.family}{person.given}"
    return f"{person.family} {_initials(person.given, dots=False, space=False)}".strip()


def _vancouver_authors(people: Sequence[Person]) -> str:
    names = [_vancouver_name(person) for person in people[:6]]
    text = ", ".join(names)
    if len(people) > 6:
        text += ", et al"
    return text


def _nature_name(person: Person) -> str:
    if person.literal:
        return person.literal
    if person.cjk:
        return f"{person.family}{person.given}"
    initials = _initials(person.given, dots=True)
    return f"{person.family}, {initials}" if initials else person.family


def _nature_authors(people: Sequence[Person]) -> str:
    if not people:
        return ""
    if len(people) > 5:
        return f"{_nature_name(people[0])} et al."
    names = [_nature_name(person) for person in people]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " & " + names[-1]


# ------------------------------------------------------------------------------- entries


def _gbt_entry(work: Work, *, author_year: bool, suffix: str = "") -> str:
    code = _GBT_CODES.get(work.type, "Z")
    authors = _gbt_authors(work.authors, work.cjk) or (
        work.publisher if work.type == "standard" else ""
    )
    title = _clean(work.title)
    if work.type in {"standard", "patent"} and work.number:
        title = f"{title}: {work.number}"
    year = _year_label(work, suffix) if author_year else (str(work.year) if work.year else "")
    head = f"{authors}, {year}. " if author_year and authors else f"{authors}. " if authors else ""
    if author_year and not authors:
        head = f"{year}. "
    body = f"{title}[{code}]"
    place_publisher = ": ".join(part for part in (work.place, work.publisher) if part)
    pages = work.pages.replace("–", "-")
    year_part = "" if author_year else year
    if work.type == "article-journal":
        source = _clean(work.container)
        volume = work.volume + (f"({work.issue})" if work.issue else "")
        pieces = ", ".join(part for part in (source, year_part, volume) if part)
        if author_year:
            pieces = ", ".join(part for part in (source, volume) if part)
        body += f". {pieces}" if pieces else ""
        body += f": {pages}" if pages else ""
    elif work.type in {"chapter", "paper-conference"}:
        editors = _gbt_authors(work.editors, work.cjk)
        parent = ". ".join(part for part in (editors, _clean(work.container)) if part)
        body += f"//{parent}" if parent else ""
        if place_publisher:
            body += f". {place_publisher}"
            body += f", {year_part}" if year_part else ""
        elif year_part:
            body += f", {year_part}"
        body += f": {pages}" if pages else ""
    elif work.type in {"book", "thesis", "report", "standard"}:
        if work.edition and work.edition not in {"1", "1st", "第1版", "第一版"}:
            edition = (
                work.edition
                if re.search(r"版|ed", work.edition)
                else (f"{work.edition}版" if work.cjk else f"{work.edition} ed")
            )
            body += f". {edition}"
        if place_publisher:
            body += f". {place_publisher}"
            body += f", {year_part}" if year_part else ""
        elif year_part:
            body += f". {year_part}"
        body += f": {pages}" if pages and work.type == "book" else ""
    elif work.type == "patent":
        body += f". {work.date or year_part}" if (work.date or year_part) else ""
    elif work.type == "article-newspaper":
        body += f". {_clean(work.container)}, {work.date or year_part}" + (
            f"({pages})" if pages else ""
        )
    else:  # webpages, preprints, datasets, software
        published = work.date or (year_part if not author_year else "")
        body += f". ({published})" if published else ""
        body += f"[{work.accessed}]" if work.accessed else ""
        link = work.url or (f"https://arxiv.org/abs/{work.arxiv}" if work.arxiv else "")
        body += f". {link}" if link else ""
    text = head + body + "."
    if work.doi:
        text += f" DOI:{work.doi}."
    return text


def _apa_entry(work: Work, markup: Markup, suffix: str = "") -> str:
    authors = _apa_authors(work.authors)
    date = f"({_year_label(work, suffix)})"
    title = _clean(work.title)
    link = f"https://doi.org/{work.doi}" if work.doi else work.url
    pages = _dash(work.pages)
    if work.type == "article-journal":
        source = markup.italic(_clean(work.container))
        volume = (
            markup.italic(work.volume) + (f"({work.issue})" if work.issue else "")
            if work.volume
            else (f"({work.issue})" if work.issue else "")
        )
        tail = ", ".join(part for part in (source, volume, pages) if part)
        text = f"{title}. {tail}." if tail else f"{title}."
    elif work.type in {"book", "report", "standard"}:
        edition = (
            f" ({work.edition} ed.)" if work.edition and work.edition not in {"1", "1st"} else ""
        )
        report = f" ({work.number})" if work.number else ""
        text = (
            f"{markup.italic(title)}{edition}{report}. {work.publisher}."
            if work.publisher
            else f"{markup.italic(title)}{edition}{report}."
        )
    elif work.type in {"chapter", "paper-conference"}:
        editors = ""
        if work.editors:
            names = [
                f"{_initials(person.given, dots=True)} {person.family}".strip()
                if not person.literal
                else person.literal
                for person in work.editors
            ]
            joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + ", & " + names[-1]
            editors = f"{joined} (Ed{'s' if len(names) > 1 else ''}.), "
        pages_text = f" (pp. {pages})" if pages else ""
        container = markup.italic(_clean(work.container))
        text = f"{title}. In {editors}{container}{pages_text}." + (
            f" {work.publisher}." if work.publisher else ""
        )
    elif work.type == "thesis":
        degree = work.genre or "Doctoral dissertation"
        text = (
            f"{markup.italic(title)} [{degree}{', ' + work.publisher if work.publisher else ''}]."
        )
    elif work.type == "article" and work.arxiv:
        text = f"{markup.italic(title)} (arXiv:{work.arxiv}). arXiv."
        link = f"https://doi.org/10.48550/arXiv.{work.arxiv}" if not work.doi else link
    else:
        site = f" {work.container}." if work.container else ""
        text = f"{markup.italic(title)}.{site}"
    head = f"{authors} {date}. " if authors else f"{markup.italic(title)} {date}. "
    if not authors:
        text = (
            text.replace(markup.italic(title), "", 1).lstrip(". ")
            if markup.italic(title) in text
            else text
        )
    return (head + text + (f" {link}" if link else "")).replace("..", ".").strip()


def _ieee_entry(work: Work, markup: Markup) -> str:
    authors = _ieee_authors(work.authors)
    title = _clean(work.title)
    pages = _dash(work.pages)
    year = str(work.year) if work.year else ""
    if work.type == "article-journal":
        parts = [f"“{title},” {markup.italic(_clean(work.container))}"]
        if work.volume:
            parts.append(f"vol. {work.volume}")
        if work.issue:
            parts.append(f"no. {work.issue}")
        if pages:
            parts.append(f"{'pp.' if '–' in pages else 'p.'} {pages}")
        if year:
            parts.append(year)
        body = ", ".join(parts)
    elif work.type == "paper-conference":
        parts = [f"“{title},” in {markup.italic(_clean(work.container))}"]
        if work.place:
            parts.append(work.place)
        if year:
            parts.append(year)
        if pages:
            parts.append(f"pp. {pages}")
        body = ", ".join(parts)
    elif work.type in {"book", "report", "standard"}:
        edition = (
            f", {work.edition} ed." if work.edition and work.edition not in {"1", "1st"} else ""
        )
        publisher = ": ".join(part for part in (work.place, work.publisher) if part)
        body = f"{markup.italic(title)}{edition}" + (
            f". {publisher}, {year}" if publisher else f", {year}" if year else ""
        )
    elif work.type == "chapter":
        body = (
            f"“{title},” in {markup.italic(_clean(work.container))}"
            + (f", {work.publisher}" if work.publisher else "")
            + (f", {year}" if year else "")
            + (f", pp. {pages}" if pages else "")
        )
    elif work.type == "thesis":
        degree = (
            "Ph.D. dissertation"
            if not re.search(r"master|硕士", work.genre, re.I)
            else "M.S. thesis"
        )
        body = (
            f"“{title},” {degree}"
            + (f", {work.publisher}" if work.publisher else "")
            + (f", {year}" if year else "")
        )
    elif work.type == "article" and work.arxiv:
        body = f"“{title},” {year + ', ' if year else ''}arXiv:{work.arxiv}"
    else:
        body = (
            f"“{title}.”"
            + (f" {work.container}." if work.container else "")
            + (f" [Online]. Available: {work.url}" if work.url else "")
        )
        return f"{authors}, {body}" if authors else body
    text = f"{authors}, {body}" if authors else body
    text += f", doi: {work.doi}." if work.doi else "."
    return text


def _vancouver_entry(work: Work) -> str:
    authors = _vancouver_authors(work.authors)
    title = _clean(work.title)
    year = str(work.year) if work.year else ""
    if work.type == "article-journal":
        volume = work.volume + (f"({work.issue})" if work.issue else "")
        tail = (
            f"{_clean(work.container)}. {year}"
            + (f";{volume}" if volume else "")
            + (f":{work.pages}" if work.pages else "")
        )
        text = f"{authors}. {title}. {tail}."
    elif work.type in {"book", "report"}:
        publisher = ": ".join(part for part in (work.place, work.publisher) if part)
        text = f"{authors}. {title}. " + (f"{publisher}; " if publisher else "") + f"{year}."
    else:
        text = (
            f"{authors}. {title}. "
            + (f"{_clean(work.container)}. " if work.container else "")
            + f"{year}."
        )
    if work.doi:
        text += f" doi:{work.doi}"
    return text.lstrip(". ")


def _nature_entry(work: Work, markup: Markup) -> str:
    authors = _nature_authors(work.authors)
    title = _clean(work.title)
    year = str(work.year) if work.year else ""
    pages = _dash(work.pages)
    if work.type == "article-journal":
        volume = (
            f" **{work.volume}**"
            if markup.markdown and work.volume
            else f" {work.volume}"
            if work.volume
            else ""
        )
        text = (
            f"{authors} {title}. {markup.italic(_clean(work.container))}{volume}"
            + (f", {pages}" if pages else "")
            + f" ({year})."
        )
    elif work.type == "article" and work.arxiv:
        text = f"{authors} {title}. Preprint at https://arxiv.org/abs/{work.arxiv} ({year})."
    elif work.type in {"book", "report"}:
        publisher = f"{work.publisher}, " if work.publisher else ""
        text = f"{authors} {markup.italic(title)} ({publisher}{year})."
    elif work.type in {"chapter", "paper-conference"}:
        text = (
            f"{authors} {title}. in {markup.italic(_clean(work.container))}"
            + (f" {pages}" if pages else "")
            + f" ({work.publisher + ', ' if work.publisher else ''}{year})."
        )
    else:
        text = (
            f"{authors} {title}."
            + (f" {work.url}" if work.url else "")
            + (f" ({year})." if year else "")
        )
    return text.strip()


# --------------------------------------------------------------------------- lists, citations


def _sort_name(work: Work) -> tuple[int, str, str]:
    first = work.authors[0] if work.authors else None
    if first is None:
        return (1, work.title.casefold(), str(work.year or ""))
    if first.cjk:
        surname = first.family or first.literal
        pinyin = _SURNAME_PINYIN.get(surname[:2]) or _SURNAME_PINYIN.get(surname[:1], surname)
        return (0, pinyin + (first.given or ""), str(work.year or ""))
    return (
        1,
        (first.family or first.literal).casefold() + " " + first.given.casefold(),
        str(work.year or ""),
    )


def _year_suffixes(works: Sequence[Work], style: str) -> dict[int, str]:
    """2020a, 2020b for works by the same first author (and year) in author-year styles."""
    if style in NUMERIC_STYLES:
        return {}
    groups: dict[tuple[str, str], list[int]] = {}
    for index, work in enumerate(works):
        head = work.authors[0].display() if work.authors else work.title
        groups.setdefault((head.casefold(), str(work.year)), []).append(index)
    suffixes: dict[int, str] = {}
    for members in groups.values():
        if len(members) > 1:
            ordered = sorted(members, key=lambda index: works[index].title.casefold())
            for position, index in enumerate(ordered):
                suffixes[index] = "abcdefghijklmnopqrstuvwxyz"[position % 26]
    return suffixes


def bibliography(works: Sequence[Work], style: str, *, markdown: bool = False) -> list[str]:
    """The reference list: numbered in the given order for numeric styles, sorted otherwise."""
    if style not in STYLES:
        raise ValueError(f"unknown style: {style}")
    markup = Markup(markdown)
    ordered = list(works) if style in NUMERIC_STYLES else sorted(works, key=_sort_name)
    suffixes = _year_suffixes(ordered, style)
    lines = []
    for index, work in enumerate(ordered, start=1):
        suffix = suffixes.get(index - 1, "")
        if style == "gb7714-numeric":
            lines.append(f"[{index}] {_gbt_entry(work, author_year=False)}")
        elif style == "gb7714-author-year":
            lines.append(_gbt_entry(work, author_year=True, suffix=suffix))
        elif style == "apa":
            lines.append(_apa_entry(work, markup, suffix))
        elif style == "ieee":
            lines.append(f"[{index}] {_ieee_entry(work, markup)}")
        elif style == "vancouver":
            lines.append(f"{index}. {_vancouver_entry(work)}")
        else:
            lines.append(f"{index}. {_nature_entry(work, markup)}")
    return lines


def _citation_names(work: Work, style: str) -> str:
    people = work.authors
    if not people:
        return _clean(work.title)[:40]
    first = people[0]
    if style == "gb7714-author-year":
        name = first.display() if first.cjk else (first.family or first.literal).upper()
        others = " 等" if work.cjk else " et al."
        return name + (
            others
            if len(people) > 2
            else (
                f", {people[1].display() if people[1].cjk else people[1].family.upper()}"
                if len(people) == 2
                else ""
            )
        )
    name = first.display() if first.cjk else first.family or first.literal
    if len(people) == 1:
        return name
    if len(people) == 2:
        second = people[1].display() if people[1].cjk else people[1].family or people[1].literal
        return f"{name} & {second}"
    return f"{name} et al."


def citation(works: Sequence[Work], style: str, numbers: Sequence[int] = ()) -> str:
    """The in-text citation of one or more works: [1-3], (Smith et al., 2020; Lee, 2021)…"""
    if style in NUMERIC_STYLES:
        return f"[{compress_numbers(numbers)}]"
    suffixes = _year_suffixes(works, style)
    parts = [
        f"{_citation_names(work, style)}, {_year_label(work, suffixes.get(index, ''))}"
        for index, work in enumerate(works)
    ]
    cjk = all(work.cjk for work in works) and style == "gb7714-author-year"
    return ("（" + "；".join(parts) + "）") if cjk else ("(" + "; ".join(parts) + ")")


def compress_numbers(numbers: Sequence[int]) -> str:
    """1, 2, 3, 5 -> "1-3, 5"."""
    values = sorted(set(numbers))
    ranges: list[str] = []
    start = previous = None
    for value in values:
        if start is None:
            start = previous = value
        elif previous is not None and value == previous + 1:
            previous = value
        else:
            ranges.append(_range(start, previous))
            start = previous = value
    if start is not None:
        ranges.append(_range(start, previous))
    return ", ".join(ranges)


def _range(start: int, end: int | None) -> str:
    if end is None or end == start:
        return str(start)
    return f"{start}, {end}" if end == start + 1 else f"{start}-{end}"


__all__ = ["NUMERIC_STYLES", "STYLES", "bibliography", "citation", "compress_numbers"]
