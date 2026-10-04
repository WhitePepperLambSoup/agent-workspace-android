from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, cast

import httpx

from agent_workspace.config import is_loopback_endpoint, provider_origin
from agent_workspace.core.models import (
    ChatMessage,
    DeltaKind,
    ProviderDelta,
    ProviderRequest,
    ToolCall,
    Usage,
    openai_message_content,
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
from agent_workspace.providers.openai_responses import (
    REASONING_PROTOCOL,
    OpenAIResponsesAdapter,
    is_gpt6_model,
)
from agent_workspace.providers.reasoning import supported_reasoning_efforts
from agent_workspace.providers.streaming import append_event_data, iter_bounded_lines


@dataclass(slots=True)
class _ToolCallParts:
    call_id: str = ""
    name: str = ""
    argument_fragments: list[str] = field(default_factory=list)
    argument_objects: list[dict[str, object]] = field(default_factory=list)
    invalid_argument_type: bool = False


class OpenAICompatibleProvider:
    """OpenAI-compatible Chat Completions streaming adapter."""

    def __init__(
        self,
        provider_id: str,
        base_url: str,
        api_key: str | None,
        *,
        timeout: float | httpx.Timeout = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._id = provider_id
        self._base_url = base_url
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._official_openai = provider_origin(base_url) == ("https", "api.openai.com", 443)
        self._official_moonshot = provider_origin(base_url) in {
            ("https", "api.moonshot.ai", 443),
            ("https", "api.moonshot.cn", 443),
        }
        self._supports_stream_usage = self._official_openai or provider_origin(base_url) == (
            "https",
            "api.deepseek.com",
            443,
        )
        self._api_key = api_key
        self._timeout = timeout
        self._client = client or httpx.AsyncClient(trust_env=not is_loopback_endpoint(base_url))
        self._owns_client = client is None
        self._responses = OpenAIResponsesAdapter(base_url, api_key, self._client, timeout)

    @property
    def id(self) -> str:
        return self._id

    @property
    def reasoning_protocol(self) -> str | None:
        return REASONING_PROTOCOL if self._official_openai else None

    def default_output_tokens(self, model: str, reasoning_effort: str | None = None) -> int:
        effort = reasoning_effort
        if effort is None:
            effort = os.environ.get("AGENT_WORKSPACE_REASONING_EFFORT")
        native_efforts = supported_reasoning_efforts("openai-compatible", self._base_url, model)
        if (
            provider_origin(self._base_url) == ("https", "api.deepseek.com", 443)
            and "none" in native_efforts
            and effort in {None, "auto", "medium", "high", "xhigh", "max"}
        ):
            # This output window also contains reasoning tokens. An 8K limit
            # exhausted five successive thinking-only requests in a real task.
            # 32K is within the documented 384K maximum for these native models.
            return 32_768
        return 8192

    def encode_request(self, request: ProviderRequest) -> bytes:
        return encode_json_request(cast(dict[str, object], self._request_body(request)))

    async def __aenter__(self) -> OpenAICompatibleProvider:
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
        if self._official_openai and is_gpt6_model(request.model):
            async for response_delta in self._responses.stream_once(request):
                yield response_delta
            return
        headers = {"Accept": "text/event-stream", "Accept-Encoding": "identity"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        tool_calls: dict[tuple[int, int], _ToolCallParts] = {}
        usage: Usage | None = None
        finish_reason: str | None = None
        saw_done = False
        emitted_content = False
        status_code: int | None = None

        try:
            body = self._request_body(request)
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

                async for data in _iter_sse_data(response):
                    if data.strip() == "[DONE]":
                        saw_done = True
                        break

                    chunk = _decode_object(data, status_code=status_code, label="SSE event")
                    if chunk.get("error") is not None:
                        raw_error = chunk.get("error")
                        detail = (
                            raw_error
                            if isinstance(raw_error, str)
                            else raw_error.get("message")
                            if isinstance(raw_error, dict)
                            else None
                        )
                        raise provider_stream_error(detail, status_code=status_code)
                    chunk_usage = chunk.get("usage")
                    if chunk_usage is not None:
                        usage = _parse_usage(chunk_usage, status_code=status_code)

                    choices = chunk.get("choices", [])
                    if not isinstance(choices, list):
                        raise ProviderError(
                            "provider sent invalid choices",
                            status_code=status_code,
                        )

                    chunk_choice_indexes: set[int] = set()
                    for choice_position, raw_choice in enumerate(choices):
                        choice = _require_object(
                            raw_choice,
                            status_code=status_code,
                            label="choice",
                        )
                        raw_delta = choice.get("delta")
                        delta = (
                            {}
                            if raw_delta is None
                            else _require_object(
                                raw_delta,
                                status_code=status_code,
                                label="choice delta",
                            )
                        )
                        choice_index = choice.get("index", choice_position)
                        if (
                            not isinstance(choice_index, int)
                            or isinstance(choice_index, bool)
                            or choice_index < 0
                        ):
                            raise ProviderError(
                                "provider sent an invalid choice index",
                                status_code=status_code,
                            )
                        if choice_index != 0:
                            raise ProviderError(
                                "provider returned multiple choices, which are unsupported",
                                status_code=status_code,
                            )
                        if choice_index in chunk_choice_indexes:
                            raise ProviderError(
                                "provider returned duplicate choices, which are unsupported",
                                status_code=status_code,
                            )
                        chunk_choice_indexes.add(choice_index)

                        content = delta.get("content")
                        if content is not None:
                            if not isinstance(content, str):
                                raise ProviderError(
                                    "provider sent invalid text content",
                                    status_code=status_code,
                                )
                            if content:
                                emitted_content = True
                                yield ProviderDelta(kind=DeltaKind.TEXT, text=content)

                        reasoning = delta.get("reasoning_content")
                        if reasoning is not None:
                            if not isinstance(reasoning, str):
                                raise ProviderError(
                                    "provider sent invalid reasoning content",
                                    status_code=status_code,
                                )
                            if reasoning:
                                emitted_content = True
                                yield ProviderDelta(kind=DeltaKind.REASONING, text=reasoning)

                        raw_tool_calls = delta.get("tool_calls", [])
                        if not isinstance(raw_tool_calls, list):
                            raise ProviderError(
                                "provider sent invalid tool calls",
                                status_code=status_code,
                            )
                        for raw_tool_call in raw_tool_calls:
                            _merge_tool_call(
                                tool_calls,
                                raw_tool_call,
                                choice_index=choice_index,
                                status_code=status_code,
                            )

                        raw_finish_reason = choice.get("finish_reason")
                        if raw_finish_reason is not None:
                            if (
                                not isinstance(raw_finish_reason, str)
                                or not raw_finish_reason.strip()
                            ):
                                raise ProviderError(
                                    "provider sent an invalid finish reason",
                                    status_code=status_code,
                                )
                            finish_reason = raw_finish_reason

                if finish_reason is None:
                    raise ProviderError(
                        (
                            "provider completed without a finish reason"
                            if saw_done
                            else "provider stream ended before completion"
                        ),
                        status_code=status_code,
                        # Once the stream has yielded a text/reasoning prefix or
                        # tool-call fragments, the caller can safely persist that
                        # prefix and ask the model to continue.  Treating this
                        # boundary as permanently fatal is what surfaced as a
                        # mysterious truncated turn for long DeepSeek streams.
                        # An empty stream remains fail-closed: there is no
                        # confirmed work from which to resume.
                        retryable=bool(emitted_content or tool_calls),
                    )
                for tool_call in _finish_tool_calls(
                    tool_calls,
                    finish_reason=finish_reason,
                    status_code=status_code,
                ):
                    yield ProviderDelta(kind=DeltaKind.TOOL_CALL, tool_call=tool_call)
                if usage is not None:
                    yield ProviderDelta(kind=DeltaKind.USAGE, usage=usage)
                if finish_reason is not None:
                    yield ProviderDelta(
                        kind=DeltaKind.FINISH,
                        finish_reason=finish_reason,
                    )
        except ProviderError:
            raise
        except httpx.RequestError as exc:
            raise provider_request_error(exc, status_code=status_code) from None

    def _request_body(self, request: ProviderRequest) -> dict[str, Any]:
        if self._official_openai and is_gpt6_model(request.model):
            return self._responses.request_body(request)
        body: dict[str, Any] = {
            "model": request.model,
            "messages": [_message_to_openai(message) for message in request.messages],
            "stream": True,
        }
        if self._supports_stream_usage:
            body["stream_options"] = {"include_usage": True}
        if request.tools:
            body["tools"] = [tool.to_openai() for tool in request.tools]
        fixed_temperature = (
            self._official_openai and request.model.startswith(("o1", "o3", "o4"))
        ) or (self._official_moonshot and request.model.startswith(("kimi-k3", "kimi-k2.7")))
        if request.temperature is not None and not fixed_temperature:
            body["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            token_field = "max_completion_tokens" if self._official_openai else "max_tokens"
            body[token_field] = request.max_output_tokens
        reasoning_effort = request.metadata.get("reasoning_effort")
        if reasoning_effort is None:
            reasoning_effort = os.environ.get("AGENT_WORKSPACE_REASONING_EFFORT")
        if reasoning_effort == "auto":
            return body
        supported = supported_reasoning_efforts("openai-compatible", self._base_url, request.model)
        if self._official_openai and len(supported) > 1:
            if reasoning_effort == "off":
                reasoning_effort = "none"
            if reasoning_effort is not None:
                if not isinstance(reasoning_effort, str) or reasoning_effort not in supported:
                    raise ProviderError(
                        "unsupported reasoning effort for this model", status_code=None
                    )
                body["reasoning_effort"] = reasoning_effort
        elif "none" in supported:
            if reasoning_effort == "off":
                reasoning_effort = "none"
            if reasoning_effort in {"medium", "xhigh"}:
                reasoning_effort = "high"
            if reasoning_effort is not None and reasoning_effort not in supported:
                raise ProviderError("unsupported reasoning effort for this model", status_code=None)
            if reasoning_effort == "none":
                body["thinking"] = {"type": "disabled"}
            elif reasoning_effort is not None:
                body["thinking"] = {"type": "enabled"}
                body["reasoning_effort"] = reasoning_effort
        elif reasoning_effort in {"low", "medium", "high", "off", "max"}:
            # DeepSeek-compatible endpoints accept reasoning_effort to steer
            # thinking effort; other servers ignore or reject it, so it is
            # opt-in through a profile or the environment.
            body["reasoning_effort"] = reasoning_effort
        return body


def _message_to_openai(message: ChatMessage) -> dict[str, Any]:
    result: dict[str, Any] = {
        "role": message.role.value,
        "content": openai_message_content(message),
    }
    if message.tool_call_id:
        result["tool_call_id"] = message.tool_call_id
    if message.tool_calls:
        calls: list[dict[str, Any]] = []
        for call in message.tool_calls:
            try:
                arguments = json.dumps(
                    call.arguments,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                )
            except (TypeError, ValueError):
                raise ProviderError(
                    "tool call arguments are not JSON serializable",
                    status_code=None,
                ) from None
            calls.append(
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": arguments},
                }
            )
        result["tool_calls"] = calls
    return result


async def _iter_sse_data(response: httpx.Response) -> AsyncIterator[str]:
    data_lines: list[str] = []
    event_bytes = 0
    async for line in iter_bounded_lines(response, status_code=response.status_code):
        if line == "":
            if data_lines:
                yield "\n".join(data_lines)
                data_lines.clear()
                event_bytes = 0
            continue
        if line.startswith(":") or not line.startswith("data:"):
            continue
        value = line[5:]
        if value.startswith(" "):
            value = value[1:]
        event_bytes = append_event_data(
            data_lines,
            value,
            event_bytes,
            status_code=response.status_code,
        )
    if data_lines:
        yield "\n".join(data_lines)


def _decode_object(data: str, *, status_code: int, label: str) -> dict[str, object]:
    try:
        value = cast(object, json.loads(data))
    except (json.JSONDecodeError, ValueError):
        raise ProviderError(
            f"provider sent invalid JSON in {label}",
            status_code=status_code,
        ) from None
    return _require_object(value, status_code=status_code, label=label)


def _require_object(value: object, *, status_code: int, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProviderError(
            f"provider sent invalid {label}",
            status_code=status_code,
        )
    return cast(dict[str, object], value)


def _merge_tool_call(
    accumulated: dict[tuple[int, int], _ToolCallParts],
    raw_tool_call: object,
    *,
    choice_index: int,
    status_code: int,
) -> None:
    tool_call = _require_object(
        raw_tool_call,
        status_code=status_code,
        label="tool call",
    )
    index = tool_call.get("index")
    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        raise ProviderError(
            "provider sent a tool call without a valid index",
            status_code=status_code,
        )
    parts = accumulated.setdefault((choice_index, index), _ToolCallParts())

    call_id = tool_call.get("id")
    if call_id is not None:
        if not isinstance(call_id, str):
            raise ProviderError(
                "provider sent an invalid tool call id",
                status_code=status_code,
            )
        parts.call_id = _merge_stream_text(parts.call_id, call_id)

    raw_function = tool_call.get("function")
    if raw_function is None:
        return
    function = _require_object(
        raw_function,
        status_code=status_code,
        label="tool call function",
    )
    name = function.get("name")
    if name is not None:
        if not isinstance(name, str):
            raise ProviderError(
                "provider sent an invalid tool name",
                status_code=status_code,
            )
        parts.name = _merge_stream_text(parts.name, name)
    arguments = function.get("arguments")
    if arguments is not None:
        if isinstance(arguments, str):
            parts.argument_fragments.append(arguments)
        elif isinstance(arguments, dict):
            parts.argument_objects.append(cast(dict[str, object], arguments))
        else:
            parts.invalid_argument_type = True


def _finish_tool_calls(
    accumulated: dict[tuple[int, int], _ToolCallParts],
    *,
    finish_reason: str | None,
    status_code: int,
) -> list[ToolCall]:
    result: list[ToolCall] = []
    seen_ids: set[str] = set()
    for key in sorted(accumulated):
        parts = accumulated[key]
        if not parts.call_id or not parts.name:
            raise ProviderError(
                "provider sent an incomplete tool call",
                status_code=status_code,
            )
        arguments, argument_error = _finish_tool_arguments(
            parts,
            finish_reason=finish_reason,
        )
        if parts.call_id in seen_ids:
            raise ProviderError(
                "provider returned duplicate tool call ids",
                status_code=status_code,
            )
        seen_ids.add(parts.call_id)
        result.append(
            ToolCall(
                id=parts.call_id,
                name=parts.name,
                arguments=arguments,
                argument_error=argument_error,
            )
        )
    return result


def _merge_stream_text(current: str, fragment: str) -> str:
    if not fragment or fragment == current:
        return current
    if fragment.startswith(current):
        return fragment
    # Some compatible servers split name/id fragments into complementary
    # pieces ("get_" + "_weather"). Merge on the longest suffix/prefix overlap
    # so the shared part is not duplicated.
    overlap = 0
    maximum = min(len(current), len(fragment))
    while overlap < maximum and current[-overlap - 1 :] == fragment[: overlap + 1]:
        overlap += 1
    return f"{current}{fragment[overlap:]}"


def _finish_tool_arguments(
    parts: _ToolCallParts,
    *,
    finish_reason: str | None,
) -> tuple[dict[str, object], str | None]:
    if finish_reason not in {None, "stop", "tool_calls"}:
        return {}, (
            f"Provider ended the tool call with {finish_reason!r} before its arguments were "
            "complete. Retry the tool call with one complete JSON object."
        )
    if parts.invalid_argument_type:
        return {}, "Provider returned tool arguments with an unsupported type. Retry with JSON."
    if parts.argument_objects and parts.argument_fragments:
        return {}, (
            "Provider mixed structured and streamed tool arguments. Retry with one JSON object."
        )
    if parts.argument_objects:
        return parts.argument_objects[-1], None
    fragments = parts.argument_fragments
    if not fragments or not any(fragment.strip() for fragment in fragments):
        return {}, None

    joined = "".join(fragments)
    folded = ""
    for fragment in fragments:
        if fragment == folded:
            continue
        if fragment.startswith(folded):
            folded = fragment
        else:
            folded += fragment

    deduplicated = [
        fragment
        for index, fragment in enumerate(fragments)
        if index == 0 or fragment != fragments[index - 1]
    ]
    candidates = [joined, folded, "".join(deduplicated)]
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            value = cast(object, json.loads(candidate))
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(value, dict):
            return cast(dict[str, object], value), None
    return {}, (
        "Provider returned invalid JSON tool arguments. Retry the tool call with exactly one "
        "complete JSON object and no prose."
    )


def _parse_usage(value: object, *, status_code: int) -> Usage:
    usage = _require_object(value, status_code=status_code, label="usage")
    input_tokens = _token_count(usage, "prompt_tokens", status_code=status_code)
    output_tokens = _token_count(usage, "completion_tokens", status_code=status_code)

    cached_tokens = 0
    details_value = usage.get("prompt_tokens_details")
    if details_value is not None:
        details = _require_object(
            details_value,
            status_code=status_code,
            label="prompt token details",
        )
        cached_tokens = _token_count(details, "cached_tokens", status_code=status_code)
    elif "prompt_cache_hit_tokens" in usage:
        cached_tokens = _token_count(usage, "prompt_cache_hit_tokens", status_code=status_code)
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
    )


def _token_count(values: dict[str, object], key: str, *, status_code: int) -> int:
    value = values.get(key, 0)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProviderError(
            "provider sent invalid token usage",
            status_code=status_code,
        )
    return value
