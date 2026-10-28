"""Read the user's Zotero library through Zotero 7's local API (http://127.0.0.1:23119).

The local API is read-only and answers only on this computer, while Zotero runs and after the user
turns on "Allow other applications on this computer to communicate with Zotero" in Zotero's
Settings → Advanced.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import quote, urlencode

from agent_workspace.scholar.works import Work

ZOTERO_URL = "http://127.0.0.1:23119/api/users/0"
_PAGE = 100
_MAX_ITEMS = 5000


class ZoteroUnavailable(RuntimeError):
    """Zotero is not running, or its local API is off."""


def _get(path: str, parameters: dict[str, Any] | None = None, timeout: float = 10.0) -> Any:
    url = f"{ZOTERO_URL}{path}" + (f"?{urlencode(parameters)}" if parameters else "")
    # Only this computer is asked; no proxy may stand in between.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(
        url, headers={"Zotero-API-Version": "3", "Accept": "application/json"}
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            return json.loads(response.read(32 * 1024 * 1024).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403, 404}:
            raise ZoteroUnavailable(
                "Zotero's local API is off: in Zotero 7 open Settings → Advanced and turn on "
                '"Allow other applications on this computer to communicate with Zotero"'
            ) from None
        raise ZoteroUnavailable(f"Zotero answered with HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise ZoteroUnavailable(
            "Zotero is not running on this computer (or is older than Zotero 7)"
        ) from exc


def collections() -> list[dict[str, str]]:
    """The user's collections: key, name and parent key."""
    found = []
    start = 0
    while True:
        page = _get("/collections", {"limit": _PAGE, "start": start})
        if not isinstance(page, list) or not page:
            break
        for item in page:
            data = item.get("data") if isinstance(item, dict) else None
            if isinstance(data, dict) and data.get("key"):
                found.append(
                    {
                        "key": str(data["key"]),
                        "name": str(data.get("name") or ""),
                        "parent": str(data.get("parentCollection") or ""),
                    }
                )
        if len(page) < _PAGE:
            break
        start += _PAGE
    return found


def items(collection: str | None = None) -> list[Work]:
    """The top-level items of the library, or of one collection (by name or key), as records."""
    path = "/items/top"
    if collection:
        match = next(
            (
                entry
                for entry in collections()
                if entry["key"] == collection or entry["name"].casefold() == collection.casefold()
            ),
            None,
        )
        if match is None:
            raise ZoteroUnavailable(f"Zotero has no collection named {collection}")
        path = f"/collections/{quote(match['key'])}/items/top"
    works: list[Work] = []
    start = 0
    while len(works) < _MAX_ITEMS:
        page = _get(path, {"format": "csljson", "limit": _PAGE, "start": start})
        entries = page.get("items") if isinstance(page, dict) else page
        if not isinstance(entries, list) or not entries:
            break
        for entry in entries:
            if isinstance(entry, dict) and entry.get("title"):
                work = Work.from_csl({**entry, "id": ""})
                work.source = "zotero"
                works.append(work)
        if len(entries) < _PAGE:
            break
        start += _PAGE
    return works


__all__ = ["ZOTERO_URL", "ZoteroUnavailable", "collections", "items"]
