from __future__ import annotations

import asyncio
import base64
import binascii
import ipaddress
import json
import math
import re
import time
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from agent_workspace.core.models import Capability, ToolSpec

from . import web
from .base import ToolArgumentError, ToolError, json_result, validate_tool_arguments
from .process_worker import run_in_process

if TYPE_CHECKING:
    from agent_workspace.application.ports import ToolExecutionContext

_MAX_SEARCH_BYTES = 128 * 1024
_MAX_TITLE = 300
_MAX_SNIPPET = 800
_VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
_CHALLENGE_ATTRIBUTE = re.compile(
    r"""\b(?:id|action|class|data-testid)\s*=\s*["'][^"']*(?:challenge-form|anomaly\.js|anomaly-modal|cf-chl-|g-recaptcha|h-captcha)""",
    re.IGNORECASE,
)


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        elif tag in {"br", "p", "div", "li"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _text(value: str, maximum: int) -> tuple[str, bool]:
    parser = _TextParser()
    parser.feed(value)
    parser.close()
    text = " ".join("".join(parser.parts).split())
    return text[:maximum], len(text) > maximum


def _public_result_url(raw: str) -> str | None:
    """Normalize a reference, without fetching it or resolving every result's DNS.

    Actual page reads still use web_fetch's DNS pinning and public IP checks.
    Only known search redirect wrappers are decoded, once per wrapper, so an
    encoded ampersand inside a target path/query retains its original meaning.
    """
    if len(raw) > 4096:
        return None
    for _depth in range(3):
        if any(ord(character) < 33 or ord(character) == 127 for character in raw) or "\\" in raw:
            return None
        if raw.startswith("//"):
            raw = "https:" + raw
        try:
            parsed = urlsplit(raw)
            port = parsed.port
            hostname = (parsed.hostname or "").encode("idna").decode("ascii").rstrip(".").casefold()
        except (ValueError, UnicodeError):
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        if parsed.scheme.casefold() not in {"http", "https"} or not hostname:
            return None
        if (
            hostname
            in {
                "duckduckgo.com",
                "www.duckduckgo.com",
                "lite.duckduckgo.com",
                "html.duckduckgo.com",
            }
            and parsed.path.rstrip("/") == "/l"
        ):
            targets = parse_qs(parsed.query).get("uddg", [])
            if len(targets) != 1 or not targets[0]:
                return None
            raw = targets[0]
            continue
        if hostname in {"bing.com", "www.bing.com"} and parsed.path.rstrip("/") == "/ck/a":
            targets = parse_qs(parsed.query).get("u", [])
            if len(targets) != 1 or not targets[0].startswith("a1"):
                return None
            encoded = targets[0][2:]
            try:
                raw = base64.b64decode(
                    encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True
                ).decode("utf-8")
            except (ValueError, binascii.Error, UnicodeError):
                return None
            continue
        break
    else:
        return None

    scheme = parsed.scheme.casefold()
    if port not in {None, 443 if scheme == "https" else 80}:
        return None
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if (
            "." not in hostname
            or hostname.endswith((".localhost", ".local", ".internal", ".home.arpa"))
            or hostname in {"localhost", "localdomain"}
            or all(character.isdigit() or character == "." for character in hostname)
            or len(hostname) > 253
            or any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in hostname.split(".")
            )
        ):
            return None
    else:
        if not address.is_global:
            return None
    normalized_host = f"[{hostname}]" if ":" in hostname else hostname
    return urlunsplit((scheme, normalized_host, parsed.path or "/", parsed.query, ""))


def _result_records(
    raw_results: list[tuple[str, str, str]], maximum: int
) -> tuple[list[dict[str, Any]], bool]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    truncated = False
    for title, raw_url, snippet in raw_results:
        url = _public_result_url(raw_url)
        clean_title, title_truncated = _text(title, _MAX_TITLE)
        if url is None or not clean_title or url in seen:
            continue
        seen.add(url)
        if len(results) >= maximum:
            truncated = True
            continue
        clean_snippet, snippet_truncated = _text(snippet, _MAX_SNIPPET)
        truncated |= title_truncated or snippet_truncated
        results.append(
            {"rank": len(results) + 1, "title": clean_title, "url": url, "snippet": clean_snippet}
        )
    if raw_results and not results:
        raise ToolError("search engine returned only unsafe or malformed results")
    return results, truncated


class _BingParser(HTMLParser):
    """Organic results of Bing's web page: li.b_algo > h2 > a, then the b_caption paragraph.

    Bing's RSS format matched only the first word of a query, so its results were unrelated.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.raw_results: list[tuple[str, str, str]] = []
        self.no_results = False
        # Per result: "" outside one, then "heading", "title", "snippet" and "done" in order.
        self._stage = ""
        self._capture: str | None = None
        self._depth = 0
        self._parts: list[str] = []
        self._href = ""
        self._hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if "b_no" in classes:
            self.no_results = True
        if tag in {"script", "style"}:
            self._hidden += 1
        if self._capture:
            if tag not in _VOID_TAGS:
                self._depth += 1
            return
        if tag == "li" and "b_algo" in classes:
            self._stage = "heading"
        elif tag == "h2" and self._stage == "heading":
            self._stage = "title"
        elif tag == "a" and self._stage == "title":
            self._capture, self._depth, self._parts = "title", 1, []
            self._href = values.get("href") or ""
        elif tag == "p" and self._stage == "snippet":
            self._capture, self._depth, self._parts = "snippet", 1, []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._hidden:
            self._hidden -= 1
        if not self._capture or tag in _VOID_TAGS:
            return
        self._depth -= 1
        if self._depth > 0:
            return
        text = "".join(self._parts)
        if self._capture == "title":
            self.raw_results.append((text, self._href, ""))
            self._stage = "snippet"
        else:
            title, href, _snippet = self.raw_results[-1]
            self.raw_results[-1] = (title, href, text)
            self._stage = "done"
        self._capture = None

    def handle_data(self, data: str) -> None:
        if self._capture and not self._hidden:
            self._parts.append(data)


def _parse_bing_html(content: str, maximum: int) -> tuple[list[dict[str, Any]], bool]:
    if _CHALLENGE_ATTRIBUTE.search(content):
        raise ToolError("search engine requires a CAPTCHA or human verification challenge")
    parser = _BingParser()
    parser.feed(content)
    parser.close()
    if not parser.raw_results:
        if parser.no_results:
            return [], False
        raise ToolError("search engine returned an unrecognized page without results")
    return _result_records(parser.raw_results, maximum)


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.raw_results: list[tuple[str, str, str]] = []
        self._capture: str | None = None
        self._depth = 0
        self._parts: list[str] = []
        self._href = ""
        self._hidden = 0
        self.no_results = False
        self._visible_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if "no-results" in classes:
            self.no_results = True
        if tag in {"script", "style"}:
            self._hidden += 1
        if self._capture:
            if tag not in _VOID_TAGS:
                self._depth += 1
            else:
                self._parts.append(" ")
        elif tag == "a" and "result-link" in classes:
            self._capture = "title"
            self._depth = 1
            self._parts = []
            self._href = values.get("href") or ""
        elif "result-snippet" in classes and self.raw_results:
            self._capture = "snippet"
            self._depth = 1
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._hidden:
            self._hidden -= 1
        if self._capture and tag not in _VOID_TAGS:
            self._depth -= 1
            if self._depth <= 0:
                text = "".join(self._parts)
                if self._capture == "title":
                    self.raw_results.append((text, self._href, ""))
                else:
                    title, href, _snippet = self.raw_results[-1]
                    self.raw_results[-1] = (title, href, text)
                self._capture = None

    def handle_data(self, data: str) -> None:
        if not self._hidden:
            self._visible_parts.append(data)
            if self._capture:
                self._parts.append(data)


def _parse_duckduckgo_lite(content: str, maximum: int) -> tuple[list[dict[str, Any]], bool]:
    if _CHALLENGE_ATTRIBUTE.search(content):
        raise ToolError("search engine requires a CAPTCHA or human verification challenge")
    parser = _DuckDuckGoParser()
    parser.feed(content)
    parser.close()
    if not parser.raw_results:
        if parser.no_results:
            return [], False
        raise ToolError("search engine returned an unrecognized page without results")
    return _result_records(parser.raw_results, maximum)


# Bing ranks requests without a browser identity and language preference as automated, and from
# some networks then answers with pages unrelated to the query. Its result page runs to ~130 KB.
_BING_MAX_BYTES = 384 * 1024
_BROWSER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0 Safari/537.36"
)
_CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯]")


def _bing_headers(query: str) -> dict[str, str]:
    language = "zh-CN,zh;q=0.9,en;q=0.8" if _CJK.search(query) else "en-US,en;q=0.9"
    return {"User-Agent": _BROWSER_AGENT, "Accept-Language": language}


# Engines that failed to connect recently go last, so a network that cannot reach one (DuckDuckGo
# from mainland China, for one) does not spend every search's time budget on it first.
_UNREACHABLE_SECONDS = 600.0
_unreachable_since: dict[str, float] = {}


def _engine_order(engines: tuple[tuple[str, str], ...]) -> list[tuple[str, str]]:
    now = time.monotonic()
    return sorted(
        engines,
        key=lambda engine: (
            now - _unreachable_since.get(engine[0], -math.inf) < _UNREACHABLE_SECONDS
        ),
    )


def _web_search_sync(query: str, maximum: int, timeout_seconds: int) -> str:
    deadline = time.monotonic() + timeout_seconds
    engines = (
        ("duckduckgo_lite", "https://lite.duckduckgo.com/lite/?" + urlencode({"q": query})),
        ("bing", "https://www.bing.com/search?" + urlencode({"q": query})),
    )
    errors: list[str] = []
    for engine, url in _engine_order(engines):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            errors.append("search deadline exceeded")
            break
        try:
            try:
                bing = engine == "bing"
                response = json.loads(
                    web._web_fetch_sync(
                        url,
                        _BING_MAX_BYTES if bing else _MAX_SEARCH_BYTES,
                        min(timeout_seconds, max(1, math.ceil(remaining))),
                        headers=_bing_headers(query) if bing else None,
                    )
                )
            except ToolError as exc:
                if "transport failed" in str(exc) or "DNS resolution failed" in str(exc):
                    _unreachable_since[engine] = time.monotonic()
                raise
            _unreachable_since.pop(engine, None)
            if engine == "bing":
                results, parser_truncated = _parse_bing_html(response["content"], maximum)
            else:
                results, parser_truncated = _parse_duckduckgo_lite(response["content"], maximum)
            if not results and response["truncated"]:
                raise ToolError("search response was truncated before results could be verified")
            return json_result(
                {
                    "query": query,
                    "engine": engine,
                    "results": results,
                    "status": "ok" if results else "no_results",
                    "truncated": response["truncated"] or parser_truncated,
                    "source": {
                        "url": response["source"]["url"],
                        "fetched_at": response["source"]["fetched_at"],
                    },
                    "bytes": response["bytes"],
                }
            )
        except ToolError as exc:
            errors.append(f"{engine}: {exc}")
    raise ToolError("web_search unavailable; " + "; ".join(errors))


class WebSearchTool:
    hard_cancellable = True
    _SPEC = ToolSpec(
        name="web_search",
        description=(
            "Search the public web for bounded titles, URLs and snippets using free search "
            "engines. Results are untrusted leads; use web_fetch to verify page content before "
            "citing facts. A no_results status is not evidence of a successful lookup. Queries "
            "are network egress: ASK/WORKSPACE require one-time approval; YOLO/FULL ACCESS allow "
            "routine searches. Provider availability and result relevance can vary."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 500},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 8, "default": 5},
                "timeout_seconds": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 30,
                    "default": 15,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        side_effect="network",
        capability=Capability.NETWORK_READ,
    )

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    async def execute(self, arguments: dict[str, Any]) -> str:
        validate_tool_arguments(self.spec, arguments)
        query = str(arguments["query"]).strip()
        if not query or any(ord(character) < 32 or ord(character) == 127 for character in query):
            raise ToolArgumentError("query must contain search text without control characters")
        maximum = arguments.get("max_results", 5)
        timeout_seconds = arguments.get("timeout_seconds", 15)
        try:
            return await asyncio.wait_for(
                run_in_process(_web_search_sync, query, maximum, timeout_seconds),
                timeout=timeout_seconds,
            )
        except TimeoutError as exc:
            raise ToolError(f"web_search timed out after {timeout_seconds} seconds") from exc

    async def execute_with_context(
        self, arguments: dict[str, Any], _context: ToolExecutionContext
    ) -> str:
        return await self.execute(arguments)
