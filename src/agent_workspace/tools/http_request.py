from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
import threading
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from agent_workspace.core.models import Capability, ToolSpec
from agent_workspace.core.usage_limits import SlidingWindowRateLimiter

from .base import ToolArgumentError, ToolError, json_result, optional_int, require_string
from .process_worker import run_in_process
from .web import _normalize_public_https_url, _PinnedHTTPSConnection, _transport_reason

if TYPE_CHECKING:
    from agent_workspace.application.ports import ToolExecutionContext

_MAX_REQUEST_BYTES = 1024 * 1024
_MAX_RESPONSE_BYTES = 256 * 1024
_MAX_HEADER_BYTES = 32 * 1024
_MAX_HEADERS = 24
_DEFAULT_RATE_LIMIT = 30
_DEFAULT_RATE_WINDOW_SECONDS = 60.0
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _parse_loopback_http_url(raw_url: str) -> tuple[str, int, str, str]:
    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        raise ToolArgumentError("URL is invalid") from None
    if parsed.scheme.casefold() != "http" or not parsed.hostname:
        raise ToolArgumentError("http_request requires HTTPS or loopback HTTP")
    hostname = parsed.hostname.casefold()
    if hostname not in _LOOPBACK_HOSTS:
        raise ToolArgumentError("http_request permits plain HTTP only on loopback")
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise ToolArgumentError("URL may not include userinfo or a fragment")
    port = parsed.port or 80
    try:
        records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ToolError("http_request DNS resolution failed") from exc
    addresses = {str(record[4][0]) for record in records}
    if not addresses:
        raise ToolError("http_request DNS resolution returned no addresses")
    try:
        if any(not ipaddress.ip_address(address).is_loopback for address in addresses):
            raise ToolError("http_request blocks non-loopback addresses")
    except ValueError:
        raise ToolError("http_request DNS resolution returned an invalid address") from None
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return hostname, port, path, next(iter(addresses))


def _validate_headers(raw_headers: object) -> dict[str, str]:
    if raw_headers is None:
        return {}
    if not isinstance(raw_headers, dict):
        raise ToolArgumentError("'headers' must be an object")
    if len(raw_headers) > _MAX_HEADERS:
        raise ToolArgumentError("too many request headers")
    headers: dict[str, str] = {}
    for name, value in raw_headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise ToolArgumentError("header names and values must be strings")
        if not name or any(character in name for character in "\r\n:") or not name.isascii():
            raise ToolArgumentError("header name is invalid")
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ToolArgumentError("header value contains control characters")
        headers[name] = value
    return headers


def _route_key(scheme: str, hostname: str, port: int, path: str) -> str:
    route_path = path.split("?", 1)[0].rstrip("/")
    return f"{scheme}://{hostname}:{port}{route_path}"


def _http_request_sync(
    method: str,
    raw_url: str,
    headers: dict[str, str],
    body: bytes,
    timeout_seconds: int,
    maximum: int,
) -> str:
    if raw_url.lower().startswith("http://"):
        hostname, port, path, address = _parse_loopback_http_url(raw_url)
        scheme = "http"
    else:
        _normalized, parsed, addresses = _normalize_public_https_url(raw_url)
        hostname = parsed.hostname or ""
        port = parsed.port or 443
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        address = addresses[0]
        scheme = "https"
    if scheme == "https":
        connection: http.client.HTTPConnection = _PinnedHTTPSConnection(
            hostname,
            address,
            port,
            float(timeout_seconds),
        )
    else:
        connection = http.client.HTTPConnection(hostname, port, timeout=float(timeout_seconds))
    try:
        connection.request(
            method,
            path,
            body=body or None,
            headers={
                "Accept": "*/*",
                "Accept-Encoding": "identity",
                "Connection": "close",
                "Content-Length": str(len(body)),
                "User-Agent": "AgentWorkspace/0.1",
                **headers,
            },
        )
        response = connection.getresponse()
        header_bytes = sum(
            len(name.encode("latin-1")) + len(value.encode("latin-1")) + 4
            for name, value in response.getheaders()
        )
        if header_bytes > _MAX_HEADER_BYTES:
            raise ToolError("http_request response headers exceed the safety limit")
        payload = response.read(maximum + 1)
    except (OSError, ssl.SSLError, http.client.HTTPException, TimeoutError) as exc:
        raise ToolError(f"http_request transport failed: {_transport_reason(exc)}") from exc
    finally:
        connection.close()
    truncated = len(payload) > maximum
    retained = payload[:maximum]
    text = retained.decode("utf-8", errors="replace")
    response_headers = {
        name: value for name, value in response.getheaders() if name.casefold() != "set-cookie"
    }
    return json_result(
        {
            "status": response.status,
            "route": _route_key(scheme, hostname, port, path),
            "headers": response_headers,
            "body_bytes": len(payload),
            "truncated": truncated,
            "text": text,
        }
    )


class HttpRequestTool:
    """Bounded GET/POST with per-route sliding-window rate limits."""

    hard_cancellable = True
    _SPEC = ToolSpec(
        name="http_request",
        description=(
            "Send a bounded GET or POST request to public HTTPS or loopback HTTP. "
            "Requests are rate-limited per route. Redirects are not followed. "
            "Returned bodies are untrusted data."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["GET", "POST"]},
                "url": {"type": "string", "minLength": 1, "maxLength": 4096},
                "headers": {
                    "type": "object",
                    "additionalProperties": {"type": "string", "maxLength": 8192},
                    "maxProperties": _MAX_HEADERS,
                },
                "body": {"type": "string", "maxLength": _MAX_REQUEST_BYTES},
                "max_bytes": {
                    "type": "integer",
                    "minimum": 1024,
                    "maximum": _MAX_RESPONSE_BYTES,
                },
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 30},
            },
            "required": ["method", "url"],
            "additionalProperties": False,
        },
        side_effect="network",
        capability=Capability.NETWORK_READ,
    )

    def __init__(
        self,
        *,
        rate_limit: int = _DEFAULT_RATE_LIMIT,
        rate_window_seconds: float = _DEFAULT_RATE_WINDOW_SECONDS,
    ) -> None:
        self.rate_limit = rate_limit
        self.rate_window_seconds = rate_window_seconds
        self._limiters: dict[str, SlidingWindowRateLimiter] = {}
        self._lock = threading.Lock()

    @property
    def spec(self) -> ToolSpec:
        return self._SPEC

    def _check_route(self, route: str) -> None:
        with self._lock:
            limiter = self._limiters.get(route)
            if limiter is None:
                limiter = SlidingWindowRateLimiter(
                    limit=self.rate_limit,
                    window_seconds=self.rate_window_seconds,
                )
                self._limiters[route] = limiter
            if not limiter.try_acquire():
                raise ToolError(f"http_request route rate limit exceeded: {route}")

    async def execute(self, arguments: dict[str, Any]) -> str:
        method = require_string(arguments, "method").upper()
        if method not in {"GET", "POST"}:
            raise ToolArgumentError("'method' must be GET or POST")
        url = require_string(arguments, "url")
        body_text = arguments.get("body", "")
        if body_text is None:
            body_text = ""
        if not isinstance(body_text, str):
            raise ToolArgumentError("'body' must be a string")
        body = body_text.encode("utf-8")
        if len(body) > _MAX_REQUEST_BYTES:
            raise ToolArgumentError("request body exceeds the 1 MiB limit")
        headers = _validate_headers(arguments.get("headers"))
        maximum = optional_int(
            arguments,
            "max_bytes",
            64 * 1024,
            minimum=1024,
            maximum=_MAX_RESPONSE_BYTES,
        )
        timeout_seconds = optional_int(
            arguments,
            "timeout_seconds",
            15,
            minimum=1,
            maximum=30,
        )
        try:
            if url.casefold().startswith("http://"):
                hostname, port, path, _address = _parse_loopback_http_url(url)
                scheme = "http"
            else:
                _normalized, parsed, _addresses = _normalize_public_https_url(url)
                hostname = parsed.hostname or ""
                port = parsed.port or 443
                path = (parsed.path or "/").split("?", 1)[0]
                scheme = "https"
        except (ToolArgumentError, ToolError):
            raise
        self._check_route(_route_key(scheme, hostname, port, path))
        return await run_in_process(
            _http_request_sync,
            method,
            url,
            headers,
            body,
            timeout_seconds,
            maximum,
        )

    async def execute_with_context(
        self,
        arguments: dict[str, Any],
        _context: ToolExecutionContext | None,
    ) -> str:
        return await self.execute(arguments)


__all__ = ["HttpRequestTool"]
