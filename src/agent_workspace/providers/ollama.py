from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from types import TracebackType
from typing import Any, Never, cast

import httpx

from agent_workspace.config import is_loopback_endpoint
from agent_workspace.core.models import (
    ChatMessage,
    DeltaKind,
    ProviderDelta,
    ProviderRequest,
    Role,
    ToolCall,
    Usage,
    ollama_message_images,
)
from agent_workspace.providers.base import (
    ProviderError,
    encode_json_request,
    provider_request_error,
    provider_stream_error,
    response_http_error,
    stream_request_timeout,
    stream_with_retries,
)
from agent_workspace.providers.streaming import iter_bounded_lines


class OllamaProvider:
    """Ollama native chat NDJSON streaming adapter."""

    def __init__(
        self,
        provider_id: str,
        base_url: str,
        api_key: str | None = None,
        *,
        timeout: float | httpx.Timeout = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._id = provider_id
        self._endpoint = f"{base_url.rstrip('/')}/api/chat"
        self._api_key = api_key
        self._timeout = timeout
        self._client = client or httpx.AsyncClient(trust_env=not is_loopback_endpoint(base_url))
        self._owns_client = client is None

    @property
    def id(self) -> str:
        return self._id

    @property
    def reasoning_protocol(self) -> None:
        return None

    def encode_request(self, request: ProviderRequest) -> bytes:
        return encode_json_request(cast(dict[str, object], self._request_body(request)))

    async def __aenter__(self) -> OllamaProvider:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def stream(self, request: ProviderRequest) -> AsyncIterator[ProviderDelta]:
        async for delta in stream_with_retries(lambda: self._stream_once(request)):
            yield delta

    async def stream_with_attempts(
        self,
        request: ProviderRequest,
        attempt_started: Callable[[int], Awaitable[None]],
    ) -> AsyncIterator[ProviderDelta]:
        async for delta in stream_with_retries(
            lambda: self._stream_once(request),
            attempt_started,
        ):
            yield delta

    async def _stream_once(self, request: ProviderRequest) -> AsyncIterator[ProviderDelta]:
        headers = {"Accept": "application/x-ndjson", "Accept-Encoding": "identity"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        status_code: int | None = None
        saw_done = False
        emitted_content = False
        usage: Usage | None = None
        tool_call_index = 0
        tool_call_ids: set[str] = set()

        try:
            body = self._request_body(request)
            call_seed = _stable_seed(body)
            async with self._client.stream(
                "POST",
                self._endpoint,
                headers=headers,
                json=body,
                timeout=stream_request_timeout(self._timeout),
            ) as response:
                status_code = response.status_code
                if not response.is_success:
                    raise await response_http_error(response, api_key=self._api_key)

                async for line in iter_bounded_lines(response, status_code=status_code):
                    if not line.strip():
                        continue
                    chunk = _decode_object(line, status_code=status_code)
                    if chunk.get("error") is not None:
                        raw_error = chunk.get("error")
                        detail = raw_error if isinstance(raw_error, str) else None
                        raise provider_stream_error(detail, status_code=status_code)

                    raw_done = chunk.get("done")
                    if not isinstance(raw_done, bool):
                        raise ProviderError(
                            "provider sent an invalid completion marker",
                            status_code=status_code,
                        )

                    raw_reason = chunk.get("done_reason")
                    finish_reason: str | None = None
                    if raw_reason is not None:
                        if not isinstance(raw_reason, str) or not raw_reason.strip():
                            raise ProviderError(
                                "provider sent an invalid finish reason",
                                status_code=status_code,
                            )
                        finish_reason = raw_reason

                    if "prompt_eval_count" in chunk or "eval_count" in chunk:
                        usage = _parse_usage(chunk, status_code=status_code)

                    raw_message = chunk.get("message")
                    if raw_message is not None:
                        message = _require_object(
                            raw_message,
                            status_code=status_code,
                            label="message",
                        )
                        content = _optional_text(
                            message,
                            "content",
                            status_code=status_code,
                        )
                        if content:
                            emitted_content = True
                            yield ProviderDelta(kind=DeltaKind.TEXT, text=content)

                        thinking = _optional_text(
                            message,
                            "thinking",
                            status_code=status_code,
                        )
                        if thinking:
                            emitted_content = True
                            yield ProviderDelta(kind=DeltaKind.REASONING, text=thinking)

                        if "tool_calls" in message:
                            raw_tool_calls = message["tool_calls"]
                            if not isinstance(raw_tool_calls, list):
                                raise ProviderError(
                                    "provider sent invalid tool calls",
                                    status_code=status_code,
                                )
                            for raw_tool_call in raw_tool_calls:
                                tool_call = _parse_tool_call(
                                    raw_tool_call,
                                    call_seed=call_seed,
                                    call_index=tool_call_index,
                                    status_code=status_code,
                                )
                                if tool_call.id in tool_call_ids:
                                    raise ProviderError(
                                        "provider returned duplicate tool call ids",
                                        status_code=status_code,
                                    )
                                tool_call_ids.add(tool_call.id)
                                tool_call_index += 1
                                emitted_content = True
                                yield ProviderDelta(
                                    kind=DeltaKind.TOOL_CALL,
                                    tool_call=tool_call,
                                )

                    if raw_done:
                        saw_done = True
                        if usage is not None:
                            yield ProviderDelta(kind=DeltaKind.USAGE, usage=usage)
                        yield ProviderDelta(
                            kind=DeltaKind.FINISH,
                            finish_reason=finish_reason or "stop",
                        )
                        break

                if not saw_done:
                    raise ProviderError(
                        "provider stream ended before completion",
                        status_code=status_code,
                        retryable=emitted_content,
                    )
        except ProviderError:
            raise
        except httpx.RequestError as exc:
            raise provider_request_error(exc, status_code=status_code) from None

    @staticmethod
    def _request_body(request: ProviderRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": request.model,
            "messages": _messages_to_ollama(request.messages),
            "stream": True,
        }
        if request.tools:
            body["tools"] = [tool.to_openai() for tool in request.tools]

        options: dict[str, Any] = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            options["num_predict"] = request.max_output_tokens
        if options:
            body["options"] = options

        try:
            json.dumps(body, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError):
            raise ProviderError(
                "provider request is not JSON serializable",
                status_code=None,
            ) from None
        return body


def _messages_to_ollama(messages: tuple[ChatMessage, ...]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    call_names: dict[str, str] = {}
    for message in messages:
        converted: dict[str, Any] = {
            "role": message.role.value,
            "content": message.provider_content(),
        }
        if message.images:
            converted["images"] = ollama_message_images(message)
        if message.tool_calls:
            converted["tool_calls"] = [
                {
                    "function": {
                        "name": call.name,
                        "arguments": call.arguments,
                    }
                }
                for call in message.tool_calls
            ]
            call_names.update((call.id, call.name) for call in message.tool_calls)
        if message.role is Role.TOOL:
            call_id = message.tool_call_id
            if not call_id or call_id not in call_names:
                raise ProviderError(
                    "tool result cannot be matched to an Ollama tool name",
                    status_code=None,
                )
            converted["tool_name"] = call_names[call_id]
        result.append(converted)
    return result


def _decode_object(data: str, *, status_code: int) -> dict[str, object]:
    try:
        value = cast(
            object,
            json.loads(data, parse_constant=_reject_json_constant),
        )
    except (json.JSONDecodeError, ValueError):
        raise ProviderError(
            "provider sent invalid JSON in NDJSON stream",
            status_code=status_code,
        ) from None
    return _require_object(value, status_code=status_code, label="NDJSON event")


def _reject_json_constant(value: str) -> Never:
    raise ValueError(f"invalid JSON constant: {value}")


def _require_object(
    value: object,
    *,
    status_code: int,
    label: str,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProviderError(
            f"provider sent invalid {label}",
            status_code=status_code,
        )
    return cast(dict[str, object], value)


def _optional_text(
    values: dict[str, object],
    key: str,
    *,
    status_code: int,
) -> str:
    if key not in values:
        return ""
    value = values[key]
    if not isinstance(value, str):
        raise ProviderError(
            f"provider sent invalid message {key}",
            status_code=status_code,
        )
    return value


def _parse_tool_call(
    value: object,
    *,
    call_seed: str,
    call_index: int,
    status_code: int,
) -> ToolCall:
    tool_call = _require_object(value, status_code=status_code, label="tool call")
    function = _require_object(
        tool_call.get("function"),
        status_code=status_code,
        label="tool call function",
    )
    name = function.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ProviderError(
            "provider sent an invalid tool name",
            status_code=status_code,
        )

    raw_arguments = function.get("arguments", {})
    if not isinstance(raw_arguments, dict):
        raise ProviderError(
            "provider sent invalid tool arguments",
            status_code=status_code,
        )
    arguments = cast(dict[str, Any], raw_arguments)

    raw_id = tool_call.get("id")
    if raw_id is not None:
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise ProviderError(
                "provider sent an invalid tool call id",
                status_code=status_code,
            )
        call_id = raw_id
    else:
        call_id = _stable_call_id(call_seed, call_index, name, arguments)
    return ToolCall(id=call_id, name=name, arguments=arguments)


def _parse_usage(values: dict[str, object], *, status_code: int) -> Usage:
    return Usage(
        input_tokens=_token_count(values, "prompt_eval_count", status_code=status_code),
        output_tokens=_token_count(values, "eval_count", status_code=status_code),
    )


def _token_count(values: dict[str, object], key: str, *, status_code: int) -> int:
    value = values.get(key, 0)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProviderError(
            "provider sent invalid token usage",
            status_code=status_code,
        )
    return value


def _stable_seed(body: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(body).encode()).hexdigest()


def _stable_call_id(
    seed: str,
    index: int,
    name: str,
    arguments: dict[str, Any],
) -> str:
    value = {"seed": seed, "index": index, "name": name, "arguments": arguments}
    digest = hashlib.sha256(_canonical_json(value).encode()).hexdigest()
    return f"call_{digest[:24]}"


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
