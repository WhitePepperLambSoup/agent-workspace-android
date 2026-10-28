"""Bibliographic records: a work, its people, identifiers, and the keys a library files it under.

The fields follow CSL-JSON (the format Zotero, Pandoc and citeproc share), so records convert to
and from it without loss; everything else here (BibTeX, RIS, formatted references) is built from
these records.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field, replace
from typing import Any

# CSL item types this app formats; others are kept and formatted as a generic work.
WORK_TYPES = frozenset(
    {
        "article-journal",
        "paper-conference",
        "book",
        "chapter",
        "thesis",
        "report",
        "article",  # a preprint
        "webpage",
        "dataset",
        "patent",
        "standard",
        "article-newspaper",
        "software",
    }
)

_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>{}]+)", re.IGNORECASE)
_ARXIV_NEW = re.compile(r"(?:arxiv[:\s/]*|abs/|pdf/)?(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
_ARXIV_OLD = re.compile(r"(?:arxiv[:\s/]*|abs/|pdf/)([a-z\-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?", re.I)
_PMID = re.compile(r"^(?:pmid[:\s]*)?(\d{5,9})$", re.IGNORECASE)
_CJK = re.compile(r"[㐀-䶿一-鿿豈-﫿]")


@dataclass(slots=True)
class Person:
    family: str = ""
    given: str = ""
    # An organisation, or a name that does not split into family and given names.
    literal: str = ""

    @property
    def cjk(self) -> bool:
        return bool(_CJK.search(self.family + self.given + self.literal))

    def display(self) -> str:
        if self.literal:
            return self.literal
        if self.cjk:
            return f"{self.family}{self.given}"
        return f"{self.given} {self.family}".strip()

    def to_csl(self) -> dict[str, str]:
        if self.literal:
            return {"literal": self.literal}
        return {
            key: value for key, value in (("family", self.family), ("given", self.given)) if value
        }

    @classmethod
    def from_csl(cls, value: Any) -> Person | None:
        if isinstance(value, str):
            return parse_name(value)
        if not isinstance(value, dict):
            return None
        literal = _text(value.get("literal")) or _text(value.get("name"))
        family = _text(value.get("family"))
        given = _text(value.get("given"))
        if not (literal or family or given):
            return None
        if literal and not family:
            return cls(literal=literal)
        return cls(family=family, given=given)


def _looks_like_organisation(name: str) -> bool:
    words = name.split()
    return len(words) > 4 or any(
        word.casefold()
        in {"university", "institute", "group", "consortium", "committee", "society"}
        for word in words
    )


def parse_name(text: str) -> Person:
    """A name as people write it: "Smith, John A.", "John A. Smith", "张三" or an organisation."""
    name = " ".join(text.split()).strip().strip(",")
    if not name:
        return Person()
    if _CJK.search(name) and "," not in name and " " not in name:
        # A Chinese name: one- or two-character family names, the common compound ones first.
        family_length = 2 if name[:2] in _COMPOUND_SURNAMES and len(name) > 2 else 1
        return Person(family=name[:family_length], given=name[family_length:])
    if "," in name:
        family, _, given = name.partition(",")
        return Person(family=family.strip(), given=given.strip())
    if _looks_like_organisation(name):
        return Person(literal=name)
    parts = name.split(" ")
    if len(parts) == 1:
        return Person(family=parts[0])
    # Particles stay with the family name: "Ludwig van Beethoven", "Vincent de la Cruz".
    index = len(parts) - 1
    while index > 1 and parts[index - 1].casefold() in {
        "van",
        "von",
        "de",
        "der",
        "da",
        "di",
        "la",
        "le",
        "du",
        "dos",
        "del",
    }:
        index -= 1
    return Person(family=" ".join(parts[index:]), given=" ".join(parts[:index]))


_COMPOUND_SURNAMES = frozenset(
    {
        "欧阳",
        "司马",
        "上官",
        "诸葛",
        "东方",
        "皇甫",
        "尉迟",
        "公孙",
        "慕容",
        "长孙",
        "宇文",
        "司徒",
        "令狐",
        "夏侯",
        "轩辕",
        "端木",
    }
)


@dataclass(slots=True)
class Work:
    type: str = "article-journal"
    title: str = ""
    authors: list[Person] = field(default_factory=list)
    editors: list[Person] = field(default_factory=list)
    year: int | None = None
    # YYYY, YYYY-MM or YYYY-MM-DD.
    date: str = ""
    # Journal, proceedings, book (for a chapter), website or repository.
    container: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    publisher: str = ""
    place: str = ""
    edition: str = ""
    # The degree (Ph.D., 硕士) or report number, as the type needs.
    genre: str = ""
    number: str = ""
    doi: str = ""
    arxiv: str = ""
    pmid: str = ""
    isbn: str = ""
    url: str = ""
    accessed: str = ""
    abstract: str = ""
    language: str = ""
    keywords: list[str] = field(default_factory=list)
    note: str = ""
    # Facts from the database the record came from.
    cited_by: int | None = None
    oa_url: str = ""
    retracted: bool | None = None
    source: str = ""
    # The citation key, unique in a library.
    key: str = ""

    @property
    def cjk(self) -> bool:
        return self.language.startswith("zh") or bool(_CJK.search(self.title))

    def identity(self) -> str:
        """What makes two records the same work: DOI, arXiv id, PMID, or title and year."""
        if self.doi:
            return f"doi:{self.doi.casefold()}"
        if self.arxiv:
            return f"arxiv:{self.arxiv.casefold()}"
        if self.pmid:
            return f"pmid:{self.pmid}"
        return f"title:{normalize_title(self.title)}:{self.year or ''}"

    def merged(self, other: Work) -> Work:
        """This record with the fields it lacks taken from another record of the same work."""
        updates: dict[str, Any] = {}
        for name in self.__dataclass_fields__:
            mine, theirs = getattr(self, name), getattr(other, name)
            if name == "key":
                continue
            if mine in ("", None, []) and theirs not in ("", None, []):
                updates[name] = theirs
        if self.cited_by is not None and other.cited_by is not None:
            updates["cited_by"] = max(self.cited_by, other.cited_by)
        if other.retracted:
            updates["retracted"] = True
        return replace(self, **updates)

    def to_csl(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "id": self.key or self.identity(),
            "type": self.type,
            "title": self.title,
        }
        if self.authors:
            item["author"] = [person.to_csl() for person in self.authors]
        if self.editors:
            item["editor"] = [person.to_csl() for person in self.editors]
        if self.date or self.year:
            parts = [
                int(part) for part in (self.date or str(self.year)).split("-") if part.isdigit()
            ]
            item["issued"] = {"date-parts": [parts[:3]]}
        for name, key in (
            ("container", "container-title"),
            ("volume", "volume"),
            ("issue", "issue"),
            ("pages", "page"),
            ("publisher", "publisher"),
            ("place", "publisher-place"),
            ("edition", "edition"),
            ("genre", "genre"),
            ("number", "number"),
            ("doi", "DOI"),
            ("pmid", "PMID"),
            ("isbn", "ISBN"),
            ("url", "URL"),
            ("abstract", "abstract"),
            ("language", "language"),
            ("note", "note"),
        ):
            value = getattr(self, name)
            if value:
                item[key] = value
        if self.arxiv:
            item["arxiv"] = self.arxiv
        if self.accessed:
            item["accessed"] = {
                "date-parts": [[int(part) for part in self.accessed.split("-") if part.isdigit()]]
            }
        if self.keywords:
            item["keyword"] = ", ".join(self.keywords)
        for name in ("cited_by", "oa_url", "retracted", "source"):
            value = getattr(self, name)
            if value not in ("", None):
                item[f"x-{name.replace('_', '-')}"] = value
        return item

    @classmethod
    def from_csl(cls, item: dict[str, Any]) -> Work:
        def people(key: str) -> list[Person]:
            values = item.get(key)
            found = [Person.from_csl(value) for value in values] if isinstance(values, list) else []
            return [person for person in found if person is not None]

        date = _csl_date(item.get("issued"))
        accessed = _csl_date(item.get("accessed"))
        kind = _text(item.get("type")) or "article-journal"
        work = cls(
            type=kind if kind in WORK_TYPES else kind or "article-journal",
            title=_first_text(item.get("title")),
            authors=people("author"),
            editors=people("editor"),
            date=date,
            year=int(date[:4]) if date[:4].isdigit() else None,
            container=_first_text(item.get("container-title")),
            volume=_text(item.get("volume")),
            issue=_text(item.get("issue")),
            pages=_text(item.get("page")),
            publisher=_text(item.get("publisher")),
            place=_text(item.get("publisher-place")),
            edition=_text(item.get("edition")),
            genre=_text(item.get("genre")),
            number=_text(item.get("number")),
            doi=normalize_doi(_text(item.get("DOI"))),
            arxiv=_text(item.get("arxiv")),
            pmid=_text(item.get("PMID")),
            isbn=_text(item.get("ISBN")),
            url=_text(item.get("URL")),
            accessed=accessed,
            abstract=_text(item.get("abstract")),
            language=_text(item.get("language")),
            keywords=[
                word.strip() for word in _text(item.get("keyword")).split(",") if word.strip()
            ],
            note=_text(item.get("note")),
            key=_text(item.get("id"))
            if not _text(item.get("id")).startswith(("doi:", "title:"))
            else "",
        )
        cited = item.get("x-cited-by")
        work.cited_by = cited if isinstance(cited, int) and not isinstance(cited, bool) else None
        work.oa_url = _text(item.get("x-oa-url"))
        retracted = item.get("x-retracted")
        work.retracted = retracted if isinstance(retracted, bool) else None
        work.source = _text(item.get("x-source"))
        if not work.arxiv:
            work.arxiv = arxiv_id(work.url) or ""
        if not work.language:
            work.language = "zh" if _CJK.search(work.title) else ""
        return work

    def summary(self, *, abstract_chars: int = 1200) -> dict[str, Any]:
        """The record as a tool reports it: short, without empty fields."""
        names = [person.display() for person in self.authors[:6]]
        if len(self.authors) > 6:
            names.append(f"… ({len(self.authors)} authors)")
        document: dict[str, Any] = {
            "title": self.title,
            "authors": names,
            "year": self.year,
            "type": self.type,
            "venue": self.container,
            "volume": self.volume,
            "issue": self.issue,
            "pages": self.pages,
            "publisher": self.publisher,
            "doi": self.doi,
            "arxiv": self.arxiv,
            "pmid": self.pmid,
            "url": self.url,
            "cited_by": self.cited_by,
            "pdf": self.oa_url,
            "retracted": self.retracted,
            "key": self.key,
            "abstract": self.abstract[:abstract_chars]
            + ("…" if len(self.abstract) > abstract_chars else ""),
        }
        return {key: value for key, value in document.items() if value not in ("", None, [])}


def _text(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return " ".join(value.split()) if isinstance(value, str) else ""


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        return next((_text(item) for item in value if _text(item)), "")
    return _text(value)


def _csl_date(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    parts = value.get("date-parts")
    if isinstance(parts, list) and parts and isinstance(parts[0], list):
        numbers = [
            int(part)
            for part in parts[0][:3]
            if isinstance(part, (int, str)) and str(part).isdigit()
        ]
        if numbers:
            return "-".join(
                f"{number:04d}" if index == 0 else f"{number:02d}"
                for index, number in enumerate(numbers)
            )
    raw = value.get("raw") or value.get("literal")
    match = re.search(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", raw) if isinstance(raw, str) else None
    return match.group(0) if match else ""


def normalize_doi(value: str) -> str:
    """A DOI as stored: the bare 10.x/... form, without resolver prefix or trailing punctuation."""
    match = _DOI.search(value or "")
    if not match:
        return ""
    return match.group(1).rstrip(".,;)]}>").strip()


def arxiv_id(value: str) -> str | None:
    """The arXiv identifier in an id, an arXiv URL or "arXiv:…", without its version."""
    if not value:
        return None
    text = value.strip()
    if "arxiv" not in text.casefold() and not re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", text):
        return None
    for pattern in (_ARXIV_NEW, _ARXIV_OLD):
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def pmid(value: str) -> str | None:
    match = _PMID.match((value or "").strip())
    return match.group(1) if match else None


def identifier_kind(value: str) -> tuple[str, str]:
    """What an identifier the user or the model gave is: ("doi", …), ("arxiv", …), ("pmid", …),
    ("isbn", …) or ("query", the text itself) for a title or a citation."""
    text = value.strip()
    doi = normalize_doi(text)
    if doi and (
        text.casefold().startswith(("10.", "doi", "https://doi", "http://doi", "https://dx.doi"))
        or len(text) < len(doi) + 30
    ):
        return "doi", doi
    arxiv = arxiv_id(text)
    if arxiv and len(text) < 80:
        return "arxiv", arxiv
    number = pmid(text)
    if number:
        return "pmid", number
    isbn = re.sub(r"[\s-]", "", text.removeprefix("ISBN").removeprefix("isbn").strip(": "))
    if re.fullmatch(r"\d{9}[\dXx]|\d{13}", isbn):
        return "isbn", isbn.upper()
    return "query", text


def normalize_title(title: str) -> str:
    folded = unicodedata.normalize("NFKC", title or "").casefold()
    folded = re.sub(r"<[^>]+>", "", folded)  # markup some databases keep in titles
    return re.sub(r"[^\w㐀-鿿]+", "", folded)


def title_similarity(first: str, second: str) -> float:
    """0 to 1: how alike two titles are, ignoring case, punctuation, spaces and markup."""
    left, right = normalize_title(first), normalize_title(second)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return difflib.SequenceMatcher(None, left, right, autojunk=False).ratio()


# The pinyin of common Chinese family names, for citation keys in ASCII.
_SURNAME_PINYIN = {
    "王": "wang",
    "李": "li",
    "张": "zhang",
    "刘": "liu",
    "陈": "chen",
    "杨": "yang",
    "黄": "huang",
    "赵": "zhao",
    "吴": "wu",
    "周": "zhou",
    "徐": "xu",
    "孙": "sun",
    "马": "ma",
    "朱": "zhu",
    "胡": "hu",
    "郭": "guo",
    "何": "he",
    "高": "gao",
    "林": "lin",
    "罗": "luo",
    "郑": "zheng",
    "梁": "liang",
    "谢": "xie",
    "宋": "song",
    "唐": "tang",
    "许": "xu",
    "韩": "han",
    "冯": "feng",
    "邓": "deng",
    "曹": "cao",
    "彭": "peng",
    "曾": "zeng",
    "肖": "xiao",
    "田": "tian",
    "董": "dong",
    "袁": "yuan",
    "潘": "pan",
    "于": "yu",
    "蒋": "jiang",
    "蔡": "cai",
    "余": "yu",
    "杜": "du",
    "叶": "ye",
    "程": "cheng",
    "苏": "su",
    "魏": "wei",
    "吕": "lv",
    "丁": "ding",
    "任": "ren",
    "沈": "shen",
    "姚": "yao",
    "卢": "lu",
    "姜": "jiang",
    "崔": "cui",
    "钟": "zhong",
    "谭": "tan",
    "陆": "lu",
    "汪": "wang",
    "范": "fan",
    "金": "jin",
    "石": "shi",
    "廖": "liao",
    "贾": "jia",
    "夏": "xia",
    "韦": "wei",
    "付": "fu",
    "方": "fang",
    "白": "bai",
    "邹": "zou",
    "孟": "meng",
    "熊": "xiong",
    "秦": "qin",
    "邱": "qiu",
    "江": "jiang",
    "尹": "yin",
    "薛": "xue",
    "闫": "yan",
    "段": "duan",
    "雷": "lei",
    "侯": "hou",
    "龙": "long",
    "史": "shi",
    "陶": "tao",
    "黎": "li",
    "贺": "he",
    "顾": "gu",
    "毛": "mao",
    "郝": "hao",
    "龚": "gong",
    "邵": "shao",
    "万": "wan",
    "钱": "qian",
    "严": "yan",
    "覃": "qin",
    "武": "wu",
    "戴": "dai",
    "莫": "mo",
    "孔": "kong",
    "向": "xiang",
    "汤": "tang",
    "常": "chang",
    "温": "wen",
    "康": "kang",
    "施": "shi",
    "文": "wen",
    "牛": "niu",
    "樊": "fan",
    "葛": "ge",
    "邢": "xing",
    "安": "an",
    "齐": "qi",
    "易": "yi",
    "乔": "qiao",
    "伍": "wu",
    "庞": "pang",
    "颜": "yan",
    "倪": "ni",
    "庄": "zhuang",
    "聂": "nie",
    "章": "zhang",
    "鲁": "lu",
    "岳": "yue",
    "翟": "zhai",
    "殷": "yin",
    "詹": "zhan",
    "申": "shen",
    "欧阳": "ouyang",
    "司马": "sima",
    "上官": "shangguan",
    "诸葛": "zhuge",
}

_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "on",
        "of",
        "in",
        "for",
        "to",
        "and",
        "with",
        "towards",
        "toward",
        "via",
        "from",
        "at",
        "by",
    }
)


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def citation_key(work: Work, taken: set[str] | frozenset[str] = frozenset()) -> str:
    """A key like smith2020deep or zhang2021: family name, year and the title's first word."""
    first = work.authors[0] if work.authors else None
    family = ""
    if first is not None:
        if first.cjk:
            name = first.family or first.literal
            family = _SURNAME_PINYIN.get(name[:2]) or _SURNAME_PINYIN.get(name[:1], "")
        else:
            family = re.sub(r"[^a-z]", "", _ascii(first.family or first.literal).casefold())
    word = next(
        (
            cleaned
            for raw in _ascii(work.title).split()
            if (cleaned := re.sub(r"[^a-z0-9]", "", raw.casefold())) and cleaned not in _STOP_WORDS
        ),
        "",
    )
    base = f"{family or 'ref'}{work.year or ''}{word[:12]}" or "ref"
    if base not in taken:
        return base
    for suffix in "abcdefghijklmnopqrstuvwxyz":
        if f"{base}{suffix}" not in taken:
            return f"{base}{suffix}"
    index = 2
    while f"{base}{index}" in taken:
        index += 1
    return f"{base}{index}"


__all__ = [
    "WORK_TYPES",
    "Person",
    "Work",
    "arxiv_id",
    "citation_key",
    "identifier_kind",
    "normalize_doi",
    "normalize_title",
    "parse_name",
    "pmid",
    "title_similarity",
]
