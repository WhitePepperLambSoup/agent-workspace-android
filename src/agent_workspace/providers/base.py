from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx

from agent_workspace.core.recovery import parse_retry_after

_MAX_ERROR_BODY_BYTES = 16 * 1024
_ERROR_BODY_TIMEOUT_SECONDS = 1.0
_MAX_ATTEMPTS = 3
_MAX_RETRY_AFTER_SECONDS = 30.0
_RETRYABLE_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504, 529})
_CONTEXT_EXCEEDED_MARKERS = (
    "context length",
    "maximum context length",
    "context_length_exceeded",
    "exceeded the maximum context",
    "input is too long",
    "prompt is too long",
    "prompt too long",
    "prompt is too large",
    "prompt too large",
    "payload too large",
    "request too large",
    "too many tokens",
    "maximum token",
    "token limit",
    "reduce the length",
)
_QUOTA_EXCEEDED_MARKERS = (
    "insufficient_quota",
    "quota exceeded",
    "rate limit reached for requests",
)
_BALANCE_EXCEEDED_MARKERS = (
    "insufficient balance",
    "balance is insufficient",
    "out of balance",
    "insufficient funds",
    "payment required",
    "payment_required",
    "billing hard limit",
)


class ProviderError(RuntimeError):
    """A provider failure with a sanitized HTTP status."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None,
        retryable: bool = False,
        retry_after_seconds: float | None = None,
        context_exceeded: bool = False,
        quota_exceeded: bool = False,
        balance_exceeded: bool = False,
        incomplete_tool_call: bool = False,
    ) -> None:
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.context_exceeded = context_exceeded
        self.quota_exceeded = quota_exceeded
        self.balance_exceeded = balance_exceeded
        self.incomplete_tool_call = incomplete_tool_call
        status = str(status_code) if status_code is not None else "unavailable"
        super().__init__(f"{message} (status={status})")


def encode_json_request(body: dict[str, object]) -> bytes:
    try:
        return json.dumps(
            body,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ProviderError(
            "provider request is not JSON serializable",
            status_code=None,
        ) from None


class ProviderHTTPError(ProviderError):
    """A non-success response from a provider endpoint."""


class ProviderTransportError(ProviderError):
    """A provider transport failure normalized without endpoint details."""


def stream_request_timeout(timeout: float | httpx.Timeout) -> float | httpx.Timeout:
    """Build the timeout used by a long-lived model stream.

    The overall turn budget owns the lifetime of a model request. A separate
    HTTPX read timeout would incorrectly terminate a valid SSE stream while a
    reasoning model is quiet between chunks, so float timeouts keep finite
    connection, write, and pool limits while disabling read inactivity expiry.
    Explicit ``httpx.Timeout`` values are preserved for callers that need a
    bounded read timeout, such as a deliberately short probe.
    """
    if isinstance(timeout, httpx.Timeout):
        return timeout
    return httpx.Timeout(
        connect=timeout,
        read=None,
        write=timeout,
        pool=timeout,
    )


async def response_http_error(
    response: httpx.Response,
    *,
    api_key: str | None,
) -> ProviderHTTPError:
    message = "provider returned an HTTP error"
    try:
        async with asyncio.timeout(_ERROR_BODY_TIMEOUT_SECONDS):
            payload = await _read_bounded_body(response)
        document = json.loads(payload) if payload is not None else None
    except Exception:
        document = None
    detail = _error_detail(document)
    detail_safe_to_report = detail is not None
    if detail is None and payload:
        # Some gateways return a plain-text 400/413 response instead of JSON.
        # Keep enough of that body to classify context overflow consistently,
        # but do not echo arbitrary upstream text into the user-facing error.
        detail = payload.decode("utf-8", errors="replace")
    context_exceeded = False
    quota_exceeded = False
    balance_exceeded = response.status_code == 402
    if detail is not None:
        lowered = detail.casefold()
        context_exceeded = any(marker in lowered for marker in _CONTEXT_EXCEEDED_MARKERS)
        if response.status_code == 413:
            context_exceeded = True
        quota_exceeded = any(marker in lowered for marker in _QUOTA_EXCEEDED_MARKERS)
        balance_exceeded = balance_exceeded or any(
            marker in lowered for marker in _BALANCE_EXCEEDED_MARKERS
        )
        if api_key:
            detail = detail.replace(api_key, "<redacted>")
        detail = "".join(character if character.isprintable() else " " for character in detail)
        detail = " ".join(detail.split())[:400]
        if detail and detail_safe_to_report:
            message = f"provider rejected the request: {detail}"
    return ProviderHTTPError(
        message,
        status_code=response.status_code,
        retryable=(
            response.status_code in _RETRYABLE_STATUS_CODES
            and not context_exceeded
            and not balance_exceeded
        ),
        retry_after_seconds=_retry_after_seconds(response.headers.get("retry-after")),
        context_exceeded=context_exceeded,
        quota_exceeded=quota_exceeded,
        balance_exceeded=balance_exceeded,
    )


def provider_stream_error(
    detail: str | None,
    *,
    status_code: int | None,
) -> ProviderError:
    """Normalize inline SSE/NDJSON errors like HTTP provider failures."""
    context_exceeded = False
    quota_exceeded = False
    balance_exceeded = status_code == 402
    if isinstance(detail, str) and detail:
        lowered = detail.casefold()
        context_exceeded = any(marker in lowered for marker in _CONTEXT_EXCEEDED_MARKERS)
        quota_exceeded = any(marker in lowered for marker in _QUOTA_EXCEEDED_MARKERS)
        balance_exceeded = balance_exceeded or any(
            marker in lowered for marker in _BALANCE_EXCEEDED_MARKERS
        )
    return ProviderError(
        "provider returned an error",
        status_code=status_code,
        context_exceeded=context_exceeded,
        quota_exceeded=quota_exceeded,
        balance_exceeded=balance_exceeded,
    )


def provider_request_error(
    error: httpx.RequestError,
    *,
    status_code: int | None,
) -> ProviderTransportError:
    timed_out = isinstance(error, httpx.TimeoutException)
    retryable = isinstance(
        error,
        (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.ProxyError,
            httpx.RemoteProtocolError,
        ),
    )
    return ProviderTransportError(
        "provider request timed out" if timed_out else "provider request failed",
        status_code=status_code,
        retryable=retryable,
    )


async def stream_with_retries[T](
    attempt_factory: Callable[[], AsyncIterator[T]],
    attempt_started: Callable[[int], Awaitable[None]] | None = None,
) -> AsyncIterator[T]:
    for attempt in range(_MAX_ATTEMPTS):
        emitted = False
        try:
            if attempt_started is not None:
                await attempt_started(attempt + 1)
            async for item in attempt_factory():
                emitted = True
                yield item
            return
        except ProviderError as exc:
            if emitted or not exc.retryable or attempt + 1 >= _MAX_ATTEMPTS:
                raise
            delay = (
                exc.retry_after_seconds
                if exc.retry_after_seconds is not None
                else min(0.25 * (2**attempt), 2.0)
            )
            await asyncio.sleep(delay)


def _retry_after_seconds(value: str | None) -> float | None:
    return parse_retry_after(value, maximum=_MAX_RETRY_AFTER_SECONDS)


async def _read_bounded_body(response: httpx.Response) -> bytes | None:
    if response.headers.get("content-encoding", "identity").casefold() != "identity":
        return None
    raw_content_length = response.headers.get("content-length")
    if raw_content_length is not None:
        try:
            content_length = int(raw_content_length)
        except ValueError:
            return None
        if content_length < 0 or content_length > _MAX_ERROR_BODY_BYTES:
            return None
    body = bytearray()
    async for chunk in response.aiter_bytes(chunk_size=4096):
        if len(body) + len(chunk) > _MAX_ERROR_BODY_BYTES:
            return None
        body.extend(chunk)
    return bytes(body)


def _error_detail(document: object) -> str | None:
    if not isinstance(document, dict):
        return None
    error = document.get("error")
    if isinstance(error, str):
        return error
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return message
    for key in ("message", "detail"):
        value = document.get(key)
        if isinstance(value, str):
            return value
    return None
