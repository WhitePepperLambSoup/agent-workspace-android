# ruff: noqa: RUF001 -- abstracts in Chinese start with a full-width colon.
"""Scholarly databases: search them and look works up by DOI, arXiv id, PMID or citation.

OpenAlex, Crossref, arXiv, PubMed and Semantic Scholar answer without an account. Every request
goes through the app's public-HTTPS fetch (DNS and address checks, size and time limits). A
database that could not be reached recently is asked last, so a network that cannot reach one
does not spend each search's time on it first.
"""

from __future__ import annotations

import difflib
import json
import math
import re
import time
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from typing import Any
from urllib.parse import quote, urlencode

from agent_workspace.scholar.works import (
    Person,
    Work,
    arxiv_id,
    normalize_doi,
    normalize_title,
    parse_name,
    title_similarity,
)
from agent_workspace.tools import web
from agent_workspace.tools.base import ToolError

SOURCES = ("openalex", "crossref", "arxiv", "pubmed", "semantic_scholar")
DEFAULT_SOURCES = ("openalex", "arxiv")
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_USER_AGENT = (
    "AgentWorkspace/0.1 (desktop research assistant; "
    "+https://github.com/WhitePepperLambSoup/agent-workspace-desktop)"
)
_UNREACHABLE_SECONDS = 600.0
_unreachable_since: dict[str, float] = {}

type Fetcher = Callable[[str, int], str]


def _fetch(url: str, timeout_seconds: int) -> str:
    """The body of a public HTTPS response (JSON or XML)."""
    response = json.loads(
        web._web_fetch_sync(
            url, _MAX_RESPONSE_BYTES, timeout_seconds, headers={"User-Agent": _USER_AGENT}
        )
    )
    if response.get("truncated"):
        raise ToolError("the response was larger than the limit")
    return str(response["content"])


@dataclass(slots=True)
class SearchFilters:
    year_from: int | None = None
    year_to: int | None = None
    open_access: bool = False
    # relevance, cited or newest
    sort: str = "relevance"


@dataclass(slots=True)
class SourceResult:
    works: list[Work] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


def _remember(source: str, error: Exception) -> None:
    text = str(error)
    if "transport failed" in text or "DNS resolution failed" in text or "timed out" in text:
        _unreachable_since[source] = time.monotonic()


def ordered_sources(sources: Iterable[str]) -> list[str]:
    now = time.monotonic()
    chosen = list(dict.fromkeys(source for source in sources if source in SOURCES))
    return sorted(
        chosen,
        key=lambda source: now - _unreachable_since.get(source, -math.inf) < _UNREACHABLE_SECONDS,
    )


# ---------------------------------------------------------------------------------- OpenAlex

_OPENALEX_FIELDS = (
    "id,doi,title,display_name,publication_year,publication_date,type,authorships,"
    "primary_location,biblio,cited_by_count,open_access,best_oa_location,"
    "abstract_inverted_index,language,ids,is_retracted"
)
_OPENALEX_TYPES = {
    "article": "article-journal",
    "review": "article-journal",
    "letter": "article-journal",
    "editorial": "article-journal",
    "book": "book",
    "book-chapter": "chapter",
    "dissertation": "thesis",
    "preprint": "article",
    "report": "report",
    "dataset": "dataset",
    "standard": "standard",
    "proceedings-article": "paper-conference",
    "conference-paper": "paper-conference",
}
# Records that are not works one cites: errata, peer reviews, front matter, library guides.
_OPENALEX_SKIPPED = frozenset(
    {"paratext", "erratum", "peer-review", "libguides", "supplementary-materials", "retraction"}
)


def _openalex_abstract(index: Any) -> str:
    if not isinstance(index, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, places in index.items():
        if isinstance(places, list):
            positions.extend((place, word) for place in places if isinstance(place, int))
    return " ".join(word for _, word in sorted(positions))


def _openalex_work(item: dict[str, Any]) -> Work:
    location = item.get("primary_location") or {}
    source = location.get("source") or {}
    biblio = item.get("biblio") or {}
    best = item.get("best_oa_location") or {}
    ids = item.get("ids") or {}
    authors = [
        parse_name(str((entry.get("author") or {}).get("display_name") or ""))
        for entry in item.get("authorships") or []
        if isinstance(entry, dict)
    ]
    landing = str(location.get("landing_page_url") or "")
    kind = _OPENALEX_TYPES.get(str(item.get("type") or ""), "article-journal")
    if source.get("type") == "conference" and kind == "article-journal":
        kind = "paper-conference"
    first, last = biblio.get("first_page"), biblio.get("last_page")
    work = Work(
        type=kind,
        title=str(item.get("title") or item.get("display_name") or ""),
        authors=[author for author in authors if author.family or author.literal],
        year=item.get("publication_year")
        if isinstance(item.get("publication_year"), int)
        else None,
        date=str(item.get("publication_date") or ""),
        container=str(source.get("display_name") or ""),
        volume=str(biblio.get("volume") or ""),
        issue=str(biblio.get("issue") or ""),
        pages=f"{first}-{last}" if first and last and first != last else str(first or ""),
        doi=normalize_doi(str(item.get("doi") or "")),
        pmid=str(ids.get("pmid") or "").rstrip("/").rsplit("/", 1)[-1],
        url=landing or str(item.get("id") or ""),
        abstract=_openalex_abstract(item.get("abstract_inverted_index")),
        language=str(item.get("language") or ""),
        cited_by=item.get("cited_by_count")
        if isinstance(item.get("cited_by_count"), int)
        else None,
        oa_url=str(best.get("pdf_url") or (item.get("open_access") or {}).get("oa_url") or ""),
        retracted=item.get("is_retracted") if isinstance(item.get("is_retracted"), bool) else None,
        source="openalex",
    )
    work.arxiv = arxiv_id(landing) or arxiv_id(work.oa_url) or ""
    if work.arxiv and "arxiv" in work.container.casefold():
        work.type, work.container = "article", "arXiv"
    return work


def openalex_search(
    query: str, limit: int, filters: SearchFilters, fetch: Fetcher, timeout: int
) -> list[Work]:
    parameters: dict[str, Any] = {"search": query, "per-page": limit, "select": _OPENALEX_FIELDS}
    conditions = []
    if filters.year_from or filters.year_to:
        conditions.append(f"publication_year:{filters.year_from or 1000}-{filters.year_to or 3000}")
    if filters.open_access:
        conditions.append("is_oa:true")
    if conditions:
        parameters["filter"] = ",".join(conditions)
    if filters.sort == "cited":
        parameters["sort"] = "cited_by_count:desc"
    elif filters.sort == "newest":
        parameters["sort"] = "publication_date:desc"
    document = json.loads(fetch("https://api.openalex.org/works?" + urlencode(parameters), timeout))
    return [
        _openalex_work(item)
        for item in document.get("results") or []
        if isinstance(item, dict) and item.get("type") not in _OPENALEX_SKIPPED
    ]


def openalex_lookup(kind: str, value: str, fetch: Fetcher, timeout: int) -> Work | None:
    key = {"doi": f"doi:{value}", "pmid": f"pmid:{value}"}.get(kind)
    if key is None:
        return None
    url = f"https://api.openalex.org/works/{quote(key, safe=':/')}?select={_OPENALEX_FIELDS}"
    try:
        return _openalex_work(json.loads(fetch(url, timeout)))
    except ToolError as exc:
        if "status 404" in str(exc):
            return None
        raise


# ---------------------------------------------------------------------------------- Crossref

_CROSSREF_TYPES = {
    "journal-article": "article-journal",
    "proceedings-article": "paper-conference",
    "book-chapter": "chapter",
    "book-section": "chapter",
    "book": "book",
    "monograph": "book",
    "edited-book": "book",
    "reference-book": "book",
    "posted-content": "article",
    "dissertation": "thesis",
    "report": "report",
    "dataset": "dataset",
    "standard": "standard",
}


def _jats_text(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", value) if isinstance(value, str) else ""
    text = re.sub(r"^\s*(abstract|摘要)\s*[:：]?\s*", "", " ".join(text.split()), flags=re.I)
    return text


def crossref_work(item: dict[str, Any]) -> Work:
    def first(value: Any) -> str:
        return str(value[0]) if isinstance(value, list) and value else str(value or "")

    parts: list[int] = []
    for key in ("issued", "published-print", "published-online", "created"):
        date_parts = (item.get(key) or {}).get("date-parts")
        if isinstance(date_parts, list) and date_parts and date_parts[0] and date_parts[0][0]:
            parts = [part for part in date_parts[0] if isinstance(part, int)]
            break
    authors = []
    for person in item.get("author") or []:
        if not isinstance(person, dict):
            continue
        if person.get("family"):
            authors.append(
                Person(family=str(person["family"]), given=str(person.get("given") or ""))
            )
        elif person.get("name"):
            authors.append(Person(literal=str(person["name"])))
    editors = [
        Person(family=str(person["family"]), given=str(person.get("given") or ""))
        for person in item.get("editor") or []
        if isinstance(person, dict) and person.get("family")
    ]
    retracted = any(
        isinstance(update, dict)
        and str(update.get("type", "")).casefold() in {"retraction", "removal"}
        for update in item.get("updated-by") or []
    ) or first(item.get("title")).upper().startswith(("RETRACTED", "WITHDRAWN"))
    kind = _CROSSREF_TYPES.get(str(item.get("type") or ""), "article-journal")
    container = first(item.get("container-title"))
    isbn = first(item.get("ISBN"))
    work = Work(
        type=kind,
        title=" ".join(first(item.get("title")).split()),
        authors=authors,
        editors=editors,
        year=parts[0] if parts else None,
        date="-".join(
            f"{part:04d}" if index == 0 else f"{part:02d}" for index, part in enumerate(parts[:3])
        ),
        container=container,
        volume=str(item.get("volume") or ""),
        issue=str(item.get("issue") or ""),
        pages=str(item.get("page") or item.get("article-number") or ""),
        publisher=str(item.get("publisher") or ""),
        place=first(item.get("publisher-location")),
        doi=normalize_doi(str(item.get("DOI") or "")),
        isbn=isbn,
        url=str(item.get("URL") or ""),
        abstract=_jats_text(item.get("abstract")),
        language=str(item.get("language") or ""),
        cited_by=item.get("is-referenced-by-count")
        if isinstance(item.get("is-referenced-by-count"), int)
        else None,
        retracted=True if retracted else None,
        source="crossref",
    )
    institutions = item.get("institution")
    if kind == "thesis" and not work.publisher and isinstance(institutions, list) and institutions:
        institution = institutions[0]
        work.publisher = str(institution.get("name") or "") if isinstance(institution, dict) else ""
    return work


def crossref_search(
    query: str, limit: int, filters: SearchFilters, fetch: Fetcher, timeout: int
) -> list[Work]:
    parameters: dict[str, Any] = {"query.bibliographic": query, "rows": limit}
    conditions = []
    if filters.year_from:
        conditions.append(f"from-pub-date:{filters.year_from}")
    if filters.year_to:
        conditions.append(f"until-pub-date:{filters.year_to}")
    if conditions:
        parameters["filter"] = ",".join(conditions)
    if filters.sort == "cited":
        parameters["sort"], parameters["order"] = "is-referenced-by-count", "desc"
    elif filters.sort == "newest":
        parameters["sort"], parameters["order"] = "published", "desc"
    document = json.loads(fetch("https://api.crossref.org/works?" + urlencode(parameters), timeout))
    items = (document.get("message") or {}).get("items") or []
    # Figures, peer reviews and grants have DOIs too; only works one cites are kept.
    return [
        crossref_work(item)
        for item in items
        if isinstance(item, dict) and item.get("type") in _CROSSREF_TYPES
    ]


def crossref_lookup(doi: str, fetch: Fetcher, timeout: int) -> Work | None:
    try:
        document = json.loads(
            fetch(f"https://api.crossref.org/works/{quote(doi, safe='/')}", timeout)
        )
    except ToolError as exc:
        if "status 404" in str(exc):
            return None
        raise
    message = document.get("message")
    return crossref_work(message) if isinstance(message, dict) else None


def crossref_match(citation: str, fetch: Fetcher, timeout: int, rows: int = 3) -> list[Work]:
    parameters = {"query.bibliographic": citation[:500], "rows": rows}
    document = json.loads(fetch("https://api.crossref.org/works?" + urlencode(parameters), timeout))
    items = (document.get("message") or {}).get("items") or []
    return [crossref_work(item) for item in items if isinstance(item, dict)]


# ------------------------------------------------------------------------------------- arXiv

_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV = "{http://arxiv.org/schemas/atom}"


def _arxiv_works(content: str) -> list[Work]:
    root = ElementTree.fromstring(content)
    works = []
    for entry in root.findall(f"{_ATOM}entry"):
        identifier = arxiv_id(entry.findtext(f"{_ATOM}id") or "") or ""
        title = " ".join((entry.findtext(f"{_ATOM}title") or "").split())
        if not identifier or not title or title == "Error":
            continue
        published = (entry.findtext(f"{_ATOM}published") or "")[:10]
        pdf = next(
            (
                link.get("href", "")
                for link in entry.findall(f"{_ATOM}link")
                if link.get("title") == "pdf" or link.get("type") == "application/pdf"
            ),
            "",
        )
        journal = " ".join((entry.findtext(f"{_ARXIV}journal_ref") or "").split())
        works.append(
            Work(
                type="article",
                title=title,
                authors=[
                    parse_name(author.findtext(f"{_ATOM}name") or "")
                    for author in entry.findall(f"{_ATOM}author")
                ],
                year=int(published[:4]) if published[:4].isdigit() else None,
                date=published,
                container="arXiv",
                doi=normalize_doi(entry.findtext(f"{_ARXIV}doi") or ""),
                arxiv=identifier,
                url=f"https://arxiv.org/abs/{identifier}",
                abstract=" ".join((entry.findtext(f"{_ATOM}summary") or "").split()),
                oa_url=pdf.replace("http://", "https://"),
                note=f"Published in {journal}" if journal else "",
                language="en",
                source="arxiv",
            )
        )
    return works


def _arxiv_query(query: str) -> str:
    phrases = re.findall(r'"([^"]+)"', query)
    rest = re.sub(r'"[^"]+"', " ", query)
    words = [word for word in re.findall(r"[\w\-]+", rest) if len(word) > 1][:8]
    terms = [f'all:"{phrase}"' for phrase in phrases[:3]] + [f"all:{word}" for word in words]
    return " AND ".join(terms) or f"all:{query}"


def arxiv_search(
    query: str, limit: int, filters: SearchFilters, fetch: Fetcher, timeout: int
) -> list[Work]:
    sort = {"newest": "submittedDate"}.get(filters.sort, "relevance")
    parameters = {
        "search_query": _arxiv_query(query),
        "start": 0,
        "max_results": limit * 2 if filters.year_from or filters.year_to else limit,
        "sortBy": sort,
        "sortOrder": "descending",
    }
    works = _arxiv_works(
        fetch("https://export.arxiv.org/api/query?" + urlencode(parameters), timeout)
    )
    if filters.year_from or filters.year_to:
        works = [
            work
            for work in works
            if work.year is not None
            and (filters.year_from or 0) <= work.year <= (filters.year_to or 9999)
        ]
    return works[:limit]


def arxiv_lookup(identifiers: list[str], fetch: Fetcher, timeout: int) -> list[Work]:
    parameters = {"id_list": ",".join(identifiers), "max_results": len(identifiers)}
    return _arxiv_works(
        fetch("https://export.arxiv.org/api/query?" + urlencode(parameters), timeout)
    )


# ------------------------------------------------------------------------------------ PubMed

_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _pubmed_works(content: str) -> list[Work]:
    root = ElementTree.fromstring(content)
    works = []
    for article in root.iter("PubmedArticle"):
        citation = article.find("MedlineCitation")
        if citation is None:
            continue
        body = citation.find("Article")
        if body is None:
            continue
        number = citation.findtext("PMID") or ""
        title_element = body.find("ArticleTitle")
        title = (
            " ".join("".join(title_element.itertext()).split()) if title_element is not None else ""
        )
        abstract_parts = []
        for part in body.findall("Abstract/AbstractText"):
            text = " ".join("".join(part.itertext()).split())
            label = part.get("Label")
            abstract_parts.append(f"{label}: {text}" if label else text)
        authors = []
        for author in body.findall("AuthorList/Author"):
            if author.findtext("LastName"):
                authors.append(
                    Person(
                        family=author.findtext("LastName") or "",
                        given=author.findtext("ForeName") or author.findtext("Initials") or "",
                    )
                )
            elif author.findtext("CollectiveName"):
                authors.append(Person(literal=author.findtext("CollectiveName") or ""))
        journal = body.find("Journal")
        issue = journal.find("JournalIssue") if journal is not None else None
        year_text = ""
        if issue is not None:
            year_text = (
                issue.findtext("PubDate/Year") or (issue.findtext("PubDate/MedlineDate") or "")[:4]
            )
        doi = ""
        for location in body.findall("ELocationID"):
            if location.get("EIdType") == "doi":
                doi = location.text or ""
        for identifier in article.findall("PubmedData/ArticleIdList/ArticleId"):
            if identifier.get("IdType") == "doi" and not doi:
                doi = identifier.text or ""
        publication_types = {
            element.text for element in body.findall("PublicationTypeList/PublicationType")
        }
        works.append(
            Work(
                type="article-journal",
                title=title.rstrip("."),
                authors=authors,
                year=int(year_text) if year_text.isdigit() else None,
                container=journal.findtext("Title") or "" if journal is not None else "",
                volume=issue.findtext("Volume") or "" if issue is not None else "",
                issue=issue.findtext("Issue") or "" if issue is not None else "",
                pages=body.findtext("Pagination/MedlinePgn") or "",
                doi=normalize_doi(doi),
                pmid=number,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{number}/",
                abstract=" ".join(abstract_parts),
                language="en",
                retracted=True if "Retracted Publication" in publication_types else None,
                source="pubmed",
            )
        )
    return works


def pubmed_lookup(numbers: list[str], fetch: Fetcher, timeout: int) -> list[Work]:
    if not numbers:
        return []
    url = f"{_EUTILS}/efetch.fcgi?" + urlencode(
        {"db": "pubmed", "id": ",".join(numbers), "retmode": "xml"}
    )
    return _pubmed_works(fetch(url, timeout))


def pubmed_search(
    query: str, limit: int, filters: SearchFilters, fetch: Fetcher, timeout: int
) -> list[Work]:
    parameters: dict[str, Any] = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": limit,
        "sort": "pub_date" if filters.sort == "newest" else "relevance",
    }
    if filters.year_from or filters.year_to:
        parameters.update(
            {
                "datetype": "pdat",
                "mindate": filters.year_from or 1800,
                "maxdate": filters.year_to or 3000,
            }
        )
    found = json.loads(fetch(f"{_EUTILS}/esearch.fcgi?" + urlencode(parameters), timeout))
    numbers = [str(number) for number in (found.get("esearchresult") or {}).get("idlist") or []]
    return pubmed_lookup(numbers[:limit], fetch, timeout)


# -------------------------------------------------------------------------- Semantic Scholar

_S2_FIELDS = (
    "title,authors,year,venue,externalIds,citationCount,abstract,openAccessPdf,publicationTypes,"
    "journal,publicationDate"
)


def _s2_work(item: dict[str, Any]) -> Work:
    ids = item.get("externalIds") or {}
    journal = item.get("journal") or {}
    types = item.get("publicationTypes") or []
    kind = "paper-conference" if "Conference" in types else "article-journal"
    if ids.get("ArXiv") and not ids.get("DOI") and not journal.get("name"):
        kind = "article"
    return Work(
        type=kind,
        title=str(item.get("title") or ""),
        authors=[
            parse_name(str(author.get("name") or ""))
            for author in item.get("authors") or []
            if isinstance(author, dict)
        ],
        year=item.get("year") if isinstance(item.get("year"), int) else None,
        date=str(item.get("publicationDate") or ""),
        container=str(journal.get("name") or item.get("venue") or ""),
        volume=str(journal.get("volume") or ""),
        pages=str(journal.get("pages") or "").strip(),
        doi=normalize_doi(str(ids.get("DOI") or "")),
        arxiv=str(ids.get("ArXiv") or ""),
        pmid=str(ids.get("PubMed") or ""),
        url=f"https://www.semanticscholar.org/paper/{item.get('paperId')}"
        if item.get("paperId")
        else "",
        abstract=str(item.get("abstract") or ""),
        cited_by=item.get("citationCount") if isinstance(item.get("citationCount"), int) else None,
        oa_url=str((item.get("openAccessPdf") or {}).get("url") or ""),
        source="semantic_scholar",
    )


def semantic_scholar_search(
    query: str, limit: int, filters: SearchFilters, fetch: Fetcher, timeout: int
) -> list[Work]:
    parameters: dict[str, Any] = {"query": query, "limit": limit, "fields": _S2_FIELDS}
    if filters.year_from or filters.year_to:
        parameters["year"] = f"{filters.year_from or ''}-{filters.year_to or ''}"
    if filters.open_access:
        parameters["openAccessPdf"] = ""
    document = json.loads(
        fetch(
            "https://api.semanticscholar.org/graph/v1/paper/search?" + urlencode(parameters),
            timeout,
        )
    )
    return [_s2_work(item) for item in document.get("data") or [] if isinstance(item, dict)]


_SEARCHES: dict[str, Callable[[str, int, SearchFilters, Fetcher, int], list[Work]]] = {
    "openalex": openalex_search,
    "crossref": crossref_search,
    "arxiv": arxiv_search,
    "pubmed": pubmed_search,
    "semantic_scholar": semantic_scholar_search,
}


def merge_works(groups: Iterable[list[Work]]) -> list[Work]:
    """One record per work, in the order first seen, with fields filled in from the others."""
    merged: dict[str, Work] = {}
    order: list[str] = []
    aliases: dict[str, str] = {}
    for works in groups:
        for work in works:
            keys = [key for key in _match_keys(work)]
            known = next((aliases[key] for key in keys if key in aliases), None)
            if known is None:
                known = keys[0]
                merged[known] = work
                order.append(known)
            else:
                merged[known] = merged[known].merged(work)
                if merged[known].source and work.source and work.source not in merged[known].source:
                    merged[known].source = f"{merged[known].source}, {work.source}"
            for key in keys:
                aliases.setdefault(key, known)
    return [merged[key] for key in order]


def _match_keys(work: Work) -> list[str]:
    """Every key the work is known by: its identifiers, then its title and year."""
    keys = [
        key
        for key in (
            f"doi:{work.doi.casefold()}" if work.doi else "",
            f"arxiv:{work.arxiv.casefold()}" if work.arxiv else "",
            f"pmid:{work.pmid}" if work.pmid else "",
        )
        if key
    ]
    keys.append(f"title:{normalize_title(work.title)[:80]}:{work.year or ''}")
    return keys


def search(
    query: str,
    sources: Iterable[str],
    limit: int,
    filters: SearchFilters,
    *,
    fetch: Fetcher = _fetch,
    timeout: int = 20,
) -> SourceResult:
    """Ask the databases at the same time and merge what they find."""
    chosen = ordered_sources(sources)
    result = SourceResult()
    groups: dict[str, list[Work]] = {}
    # Text match alone ranks a fresh, uncited paper that repeats the query's words first; more
    # candidates are asked for and ranked again with how often each is cited.
    asked = min(limit * 3, 25) if filters.sort == "relevance" else limit
    # Sorted by citations, a database orders everything its loose text match lets in, so the most
    # cited papers of other fields come first ("growth curve" brings structural equation
    # models). The classics of a topic are the most cited of its relevant candidates.
    by_citations = filters.sort == "cited"
    asked_filters = replace(filters, sort="relevance") if by_citations else filters
    if by_citations:
        asked = min(limit * 4, 40)

    def ask(source: str) -> tuple[str, list[Work] | Exception]:
        try:
            return source, _SEARCHES[source](query, asked, asked_filters, fetch, timeout)
        except (
            ToolError,
            ValueError,
            KeyError,
            ElementTree.ParseError,
            json.JSONDecodeError,
        ) as exc:
            return source, exc

    with ThreadPoolExecutor(max_workers=max(1, len(chosen))) as pool:
        for source, outcome in pool.map(ask, chosen):
            if isinstance(outcome, Exception):
                _remember(source, outcome)
                result.errors[source] = str(outcome)[:300]
            else:
                _unreachable_since.pop(source, None)
                groups[source] = outcome
    works = merge_works(groups[source] for source in chosen if source in groups)
    if filters.sort == "newest":
        works.sort(key=lambda work: work.date or str(work.year or ""), reverse=True)
    else:
        rank = {
            id(work): position / max(len(group), 1)
            for group in groups.values()
            for position, work in enumerate(group)
        }
        merged_rank = {id(work): _best_rank(work, groups, rank) for work in works}
        works.sort(
            key=lambda work: relevance_score(query, work, merged_rank[id(work)]), reverse=True
        )
    if filters.open_access:
        works = [work for work in works if work.oa_url or work.arxiv]
    if by_citations:
        works = sorted(works[: max(limit * 2, 10)], key=lambda work: -(work.cited_by or 0))
    result.works = works[:limit]
    return result


def _best_rank(work: Work, groups: dict[str, list[Work]], rank: dict[int, float]) -> float:
    keys = set(_match_keys(work))
    positions = [
        rank[id(candidate)]
        for group in groups.values()
        for candidate in group
        if keys & set(_match_keys(candidate))
    ]
    return min(positions, default=1.0)


def relevance_score(query: str, work: Work, position: float) -> float:
    """Higher is better: the databases' order, the query's words in the title, and citations."""
    words = {word for word in re.findall(r"\w+", query.casefold()) if len(word) > 2}
    title = work.title.casefold()
    overlap = sum(word in title for word in words) / len(words) if words else 0.0
    citations = math.log10(1 + (work.cited_by or 0)) / 4  # 10,000 citations count as 1
    return (1 - position) + 0.6 * overlap + 0.5 * min(citations, 1.0)


def lookup(kind: str, value: str, *, fetch: Fetcher = _fetch, timeout: int = 20) -> Work | None:
    """One work by identifier, filled in from the databases that know it."""
    found: list[Work] = []
    errors: list[str] = []

    def attempt(call: Callable[[], Work | list[Work] | None], source: str) -> None:
        try:
            value = call()
        except (
            ToolError,
            ValueError,
            KeyError,
            ElementTree.ParseError,
            json.JSONDecodeError,
        ) as exc:
            _remember(source, exc)
            errors.append(f"{source}: {exc}")
            return
        if isinstance(value, list):
            found.extend(value)
        elif value is not None:
            found.append(value)

    if kind == "doi":
        attempt(lambda: crossref_lookup(value, fetch, timeout), "crossref")
        attempt(lambda: openalex_lookup("doi", value, fetch, timeout), "openalex")
        if value.casefold().startswith("10.48550/arxiv."):
            attempt(lambda: arxiv_lookup([value.split("arxiv.", 1)[-1]], fetch, timeout), "arxiv")
    elif kind == "arxiv":
        attempt(lambda: arxiv_lookup([value], fetch, timeout), "arxiv")
    elif kind == "pmid":
        attempt(lambda: pubmed_lookup([value], fetch, timeout), "pubmed")
        attempt(lambda: openalex_lookup("pmid", value, fetch, timeout), "openalex")
    elif kind == "query":
        candidates: list[Work] = []
        attempt(lambda: crossref_match(value, fetch, timeout), "crossref")
        candidates.extend(found)
        found.clear()
        attempt(
            lambda: openalex_search(value[:300], 3, SearchFilters(), fetch, timeout), "openalex"
        )
        candidates.extend(found)
        found.clear()
        best = best_match(value, candidates)
        if best is not None:
            found.append(best)
    if not found:
        if errors and len(errors) >= 1 and kind != "query":
            raise ToolError("; ".join(errors))
        return None
    merged = merge_works([found])
    return merged[0] if merged else None


def best_match(citation: str, candidates: list[Work]) -> Work | None:
    """The candidate whose title appears in a citation (or matches a title), if one does."""
    best: tuple[float, Work] | None = None
    for work in candidates:
        if not work.title:
            continue
        score = citation_match_score(citation, work)
        if best is None or score > best[0]:
            best = (score, work)
    return best[1] if best is not None and best[0] >= 0.8 else None


def citation_match_score(citation: str, work: Work) -> float:
    """0 to 1: how well a work matches a citation's text (its title, and the year when given)."""
    text = normalize_title(citation)
    title = normalize_title(work.title)
    if not text or not title:
        return 0.0
    if title in text:
        score = 1.0
    else:
        score = max(title_similarity(citation, work.title), _contained_ratio(title, text))
    years = set(re.findall(r"(?:19|20)\d{2}", citation))
    if years and work.year is not None and str(work.year) not in years:
        # Databases date some works by the online year, a year before the issue.
        score -= 0.05 if any(abs(int(year) - work.year) <= 1 for year in years) else 0.25
    return score


def _contained_ratio(title: str, text: str) -> float:
    """How much of the title appears, in order, in the text (for citations with typos)."""
    matcher = difflib.SequenceMatcher(None, title, text, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / len(title)


__all__ = [
    "DEFAULT_SOURCES",
    "SOURCES",
    "SearchFilters",
    "SourceResult",
    "best_match",
    "citation_match_score",
    "crossref_work",
    "lookup",
    "merge_works",
    "search",
]
