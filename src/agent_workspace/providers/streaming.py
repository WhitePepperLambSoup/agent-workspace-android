from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from agent_workspace.providers.base import ProviderError

MAX_STREAM_BYTES = 32 * 1024 * 1024
MAX_LINE_BYTES = 1024 * 1024
MAX_EVENT_BYTES = 1024 * 1024


async def iter_bounded_lines(
    response: httpx.Response,
    *,
    status_code: int,
) -> AsyncIterator[str]:
    if response.headers.get("content-encoding", "identity").casefold() != "identity":
        raise ProviderError(
            "provider stream used unsupported content encoding",
            status_code=status_code,
        )
    buffer = bytearray()
    total = 0
    async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
        total += len(chunk)
        if total > MAX_STREAM_BYTES:
            raise ProviderError("provider stream exceeded its size limit", status_code=status_code)
        buffer.extend(chunk)
        while True:
            newline = buffer.find(b"\n")
            if newline < 0:
                if len(buffer) > MAX_LINE_BYTES:
                    raise ProviderError(
                        "provider stream line exceeded its size limit",
                        status_code=status_code,
                    )
                break
            raw_line = bytes(buffer[:newline])
            del buffer[: newline + 1]
            if raw_line.endswith(b"\r"):
                raw_line = raw_line[:-1]
            yield _decode_line(raw_line, status_code=status_code)
    if buffer:
        if len(buffer) > MAX_LINE_BYTES:
            raise ProviderError(
                "provider stream line exceeded its size limit",
                status_code=status_code,
            )
        yield _decode_line(bytes(buffer), status_code=status_code)


def append_event_data(
    data_lines: list[str],
    value: str,
    current_bytes: int,
    *,
    status_code: int,
) -> int:
    next_bytes = current_bytes + len(value.encode("utf-8"))
    if data_lines:
        next_bytes += 1
    if next_bytes > MAX_EVENT_BYTES:
        raise ProviderError(
            "provider stream event exceeded its size limit",
            status_code=status_code,
        )
    data_lines.append(value)
    return next_bytes


def _decode_line(raw_line: bytes, *, status_code: int) -> str:
    try:
        return raw_line.decode("utf-8")
    except UnicodeDecodeError:
        raise ProviderError(
            "provider stream was not valid UTF-8",
            status_code=status_code,
        ) from None
