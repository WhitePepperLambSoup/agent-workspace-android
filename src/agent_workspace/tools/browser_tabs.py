"""Browser tab pool over the Chrome DevTools HTTP endpoints.

This module manages tab lifecycle only; individual tab sessions still use the
existing ``CdpSession`` transport so all CDP parsing and bounds stay shared.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from agent_workspace.tools.browser import BrowserError, CdpSession

_DEFAULT_CDP_URL = "http://127.0.0.1:9222"
_REQUEST_TIMEOUT = 10.0


@dataclass(frozen=True, slots=True)
class BrowserTab:
    id: str
    url: str
    websocket_url: str


class BrowserTabPool:
    """Create, list, attach, and close CDP browser tabs."""

    def __init__(
        self,
        base_url: str = _DEFAULT_CDP_URL,
        *,
        opener: Callable[[Request, float], Any] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._opener: Callable[[Request, float], Any] = opener or (
            lambda request, timeout: urlopen(request, timeout=timeout)
        )

    def create(self, url: str) -> BrowserTab:
        query = urlencode({"url": url})
        request = Request(
            f"{self.base_url}/json/new?{query}",
            method="PUT",
        )
        payload = self._request_json(request)
        if not isinstance(payload, dict):
            raise BrowserError("CDP /json/new returned an invalid tab document")
        return self._tab_from_response(payload)

    def list(self) -> tuple[BrowserTab, ...]:
        return tuple(
            BrowserTab(
                id=str(item["id"]),
                url=str(item.get("url", "")),
                websocket_url=str(item.get("webSocketDebuggerUrl", "")),
            )
            for item in self._request_json(Request(f"{self.base_url}/json"))
            if isinstance(item, dict) and "id" in item
        )

    def attach(self, tab_id: str, *, timeout: float = 15.0) -> CdpSession:
        for tab in self.list():
            if tab.id == tab_id:
                return CdpSession(tab.websocket_url, timeout=timeout)
        raise BrowserError(f"browser tab not found: {tab_id}")

    def close(self, tab_id: str) -> None:
        request = Request(f"{self.base_url}/json/close/{tab_id}")
        self._request_json(request)

    def _tab_from_response(self, payload: dict[str, Any]) -> BrowserTab:
        websocket_url = payload.get("webSocketDebuggerUrl")
        tab_id = payload.get("id")
        url = payload.get("url")
        if (
            not isinstance(websocket_url, str)
            or not isinstance(tab_id, str)
            or not isinstance(url, str)
        ):
            raise BrowserError("CDP /json/new returned an invalid tab document")
        return BrowserTab(tab_id, url, websocket_url)

    def _request_json(self, request: Request) -> Any:
        try:
            with self._opener(request, _REQUEST_TIMEOUT) as response:
                payload = json.load(response)
        except BrowserError:
            raise
        except Exception as exc:
            raise BrowserError(f"CDP HTTP request failed: {exc}") from exc
        if not isinstance(payload, (list, dict)):
            raise BrowserError("CDP HTTP endpoint returned invalid JSON")
        return payload


__all__ = ["BrowserTab", "BrowserTabPool"]
