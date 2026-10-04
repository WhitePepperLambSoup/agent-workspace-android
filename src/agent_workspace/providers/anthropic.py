from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, cast

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
    anthropic_image_block,
    anthropic_message_content,
)
from agent_workspace.providers.base import (
    ProviderError,
    encode_json_request,
    provider_request_error,
    response_http_error,
    stream_request_timeout,
    stream_with_retries,
)
from agent_workspace.providers.reasoning import supported_reasoning_efforts
from agent_workspace.providers.streaming import append_event_data, iter_bounded_lines

_ANTHROPIC_VERSION = "2023-06-01"
_DEFAULT_MAX_TOKENS = 4096
_CONTENT_ORDER_KEY = "anthropic.content_order"
_REASONING_PROTOCOL_KEY = "agent_workspace.reasoning_protocol"


@dataclass(slots=True)
class _ContentBlockParts:
    block_type: str
    call_id: str = ""
    name: str = ""
    initial_input: dict[str, Any] = field(default_factory=dict)
    input_fragments: list[str] = field(default_factory=list)
    text_fragments: list[str] = field(default_factory=list)
    thinking_fragments: list[str] = field(default_factory=list)
    signature_fragments: list[str] = field(default_factory=list)
    redacted_data: str = ""
    stopped: bool = False


@dataclass(slots=True)
class _UsageParts:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cache_creation_tokens: int = 0
    seen: bool = False


class AnthropicProvider:
    """Anthropic Messages streaming adapter."""

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
        self._endpoint = f"{base_url.rstrip('/')}/messages"
        self._api_key = api_key
        self._timeout = timeout
        self._client = client or httpx.AsyncClient(trust_env=not is_loopback_endpoint(base_url))
        self._owns_client = client is None

    @property
    def id(self) -> str:
        return self._id

    @property
    def reasoning_protocol(self) -> str:
        return "anthropic"

    def encode_request(self, request: ProviderRequest) -> bytes:
        return encode_json_request(cast(dict[str, object], self._request_body(request)))

    async def __aenter__(self) -> AnthropicProvider:
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
        headers = {
            "Accept": "text/event-stream",
            "Accept-Encoding": "identity",
            "anthropic-version": _ANTHROPIC_VERSION,
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key

        blocks: dict[int, _ContentBlockParts] = {}
        usage = _UsageParts()
        finish_reason: str | None = None
        message_started = False
        message_stopped = False
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

                async for sse_type, data in _iter_sse_events(response):
                    event = _decode_object(data, status_code=status_code, label="SSE event")
                    raw_type = event.get("type")
                    if sse_type == "error" or raw_type == "error" or event.get("error") is not None:
                        raise ProviderError(
                            "provider returned an error",
                            status_code=status_code,
                        )
                    if not isinstance(raw_type, str) or not raw_type:
                        raise ProviderError(
                            "provider sent an invalid SSE event type",
                            status_code=status_code,
                        )
                    if sse_type is not None and sse_type != raw_type:
                        raise ProviderError(
                            "provider sent mismatched SSE event types",
                            status_code=status_code,
                        )

                    if raw_type == "ping":
                        continue
                    if raw_type == "message_start":
                        if message_started:
                            raise ProviderError(
                                "provider sent a duplicate message start",
                                status_code=status_code,
                            )
                        message = _require_object(
                            event.get("message"),
                            status_code=status_code,
                            label="message start",
                        )
                        raw_usage = message.get("usage")
                        if raw_usage is not None:
                            _update_usage(usage, raw_usage, status_code=status_code)
                        message_started = True
                        continue

                    if not message_started:
                        raise ProviderError(
                            "provider sent content before message start",
                            status_code=status_code,
                        )

                    if raw_type == "content_block_start":
                        index, block, initial_delta = _start_content_block(
                            event,
                            status_code=status_code,
                        )
                        if index in blocks:
                            raise ProviderError(
                                "provider sent a duplicate content block index",
                                status_code=status_code,
                            )
                        blocks[index] = block
                        if initial_delta is not None:
                            yield initial_delta
                        continue

                    if raw_type == "content_block_delta":
                        delta = _apply_content_block_delta(
                            blocks,
                            event,
                            status_code=status_code,
                        )
                        if delta is not None:
                            yield delta
                        continue

                    if raw_type == "content_block_stop":
                        index = _event_index(event, status_code=status_code)
                        stopped_block = blocks.get(index)
                        if stopped_block is None or stopped_block.stopped:
                            raise ProviderError(
                                "provider stopped an unknown content block",
                                status_code=status_code,
                            )
                        if stopped_block.block_type == "thinking" and (
                            len(stopped_block.signature_fragments) != 1
                            or not stopped_block.signature_fragments[0]
                        ):
                            raise ProviderError(
                                "provider completed thinking without exactly one signature",
                                status_code=status_code,
                            )
                        stopped_block.stopped = True
                        continue

                    if raw_type == "message_delta":
                        finish_reason = _parse_message_delta(
                            event,
                            usage,
                            current_finish_reason=finish_reason,
                            status_code=status_code,
                        )
                        continue

                    if raw_type == "message_stop":
                        if any(not block.stopped for block in blocks.values()):
                            raise ProviderError(
                                "provider stopped a message with incomplete content blocks",
                                status_code=status_code,
                            )
                        message_stopped = True
                        break

                    raise ProviderError(
                        "provider sent an unsupported SSE event",
                        status_code=status_code,
                    )

                if not message_stopped:
                    raise ProviderError(
                        "provider stream ended before message stop",
                        status_code=status_code,
                        retryable=bool(blocks),
                    )
                if finish_reason is None:
                    raise ProviderError(
                        "provider completed without a finish reason",
                        status_code=status_code,
                    )

                for tool_call in _finish_tool_calls(blocks, status_code=status_code):
                    yield ProviderDelta(kind=DeltaKind.TOOL_CALL, tool_call=tool_call)
                if usage.seen:
                    yield ProviderDelta(
                        kind=DeltaKind.USAGE,
                        usage=Usage(
                            input_tokens=(
                                usage.input_tokens
                                + usage.cache_creation_tokens
                                + usage.cached_tokens
                            ),
                            output_tokens=usage.output_tokens,
                            cached_tokens=usage.cached_tokens,
                        ),
                    )
                content_order = _content_order(blocks)
                provider_metadata: dict[str, Any] = {_CONTENT_ORDER_KEY: content_order}
                if any(
                    block.get("type") in {"thinking", "redacted_thinking"}
                    for block in content_order
                ):
                    provider_metadata[_REASONING_PROTOCOL_KEY] = "anthropic"
                yield ProviderDelta(
                    kind=DeltaKind.FINISH,
                    finish_reason=finish_reason,
                    provider_metadata=provider_metadata,
                )
        except ProviderError:
            raise
        except httpx.RequestError as exc:
            raise provider_request_error(exc, status_code=status_code) from None

    @staticmethod
    def _request_body(request: ProviderRequest) -> dict[str, Any]:
        system_messages = [
            message.content for message in request.messages if message.role is Role.SYSTEM
        ]
        body: dict[str, Any] = {
            "model": request.model,
            "messages": [
                _message_to_anthropic(message, target_model=request.model)
                for message in request.messages
                if message.role is not Role.SYSTEM
            ],
            "max_tokens": (
                request.max_output_tokens
                if request.max_output_tokens is not None
                else _DEFAULT_MAX_TOKENS
            ),
            "stream": True,
        }
        if system_messages:
            body["system"] = "\n\n".join(system_messages)
        if request.tools:
            body["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.advertised_input_schema,
                }
                for tool in request.tools
            ]
        if request.temperature is not None:
            body["temperature"] = request.temperature
        effort = request.metadata.get("reasoning_effort")
        if effort is not None and effort != "auto":
            supported = supported_reasoning_efforts(
                "anthropic", "https://api.anthropic.com/v1", request.model
            )
            if not isinstance(effort, str) or effort not in supported:
                raise ProviderError("unsupported reasoning effort for this model", status_code=None)
            body["output_config"] = {"effort": effort}
            body["thinking"] = {"type": "adaptive"}
            body.pop("temperature", None)
        thinking = request.metadata.get("anthropic_thinking") if effort is None else None
        if isinstance(thinking, dict):
            budget = thinking.get("thinking_budget_tokens")
            if type(budget) is int and 1024 <= budget <= 64000:
                # Native thinking consumes the same output allowance as the
                # answer. Keep the caller's limit and leave room for output.
                budget = min(budget, body["max_tokens"] - 1)
                if budget < 1024:
                    body["thinking"] = {"type": "disabled"}
                else:
                    body["thinking"] = {"type": "enabled", "budget_tokens": budget}
                    temperature = thinking.get("temperature", 1.0)
                    if isinstance(temperature, (int, float)) and 0 <= temperature <= 1:
                        body["temperature"] = temperature

        try:
            json.dumps(body, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError):
            raise ProviderError(
                "provider request is not JSON serializable",
                status_code=None,
            ) from None
        return body


def _message_to_anthropic(
    message: ChatMessage,
    *,
    target_model: str | None = None,
) -> dict[str, Any]:
    if message.role is Role.TOOL:
        if not message.tool_call_id:
            raise ProviderError(
                "tool result is missing its tool call id",
                status_code=None,
            )
        tool_result_blocks: list[dict[str, Any]] = [
            {
                "type": "tool_result",
                "tool_use_id": message.tool_call_id,
                "content": message.provider_content(),
            }
        ]
        tool_result_blocks.extend(anthropic_image_block(image) for image in message.images)
        return {
            "role": Role.USER.value,
            "content": tool_result_blocks,
        }

    raw_order = message.provider_metadata.get(_CONTENT_ORDER_KEY)
    source_model = message.provider_metadata.get("agent_workspace.model")
    model_changed = (
        target_model is not None and isinstance(source_model, str) and source_model != target_model
    )
    if raw_order is not None and not model_changed:
        if message.role is not Role.ASSISTANT:
            raise ProviderError(
                "Anthropic content order is only valid for assistant messages",
                status_code=None,
            )
        return {
            "role": Role.ASSISTANT.value,
            "content": _ordered_assistant_content(message, raw_order),
        }
    if (
        message.role is Role.ASSISTANT
        and message.reasoning
        and not model_changed
        and message.provider_metadata.get(_REASONING_PROTOCOL_KEY) == "anthropic"
    ):
        raise ProviderError(
            "Anthropic assistant reasoning is missing signed content metadata",
            status_code=None,
        )

    if message.role is Role.ASSISTANT and message.tool_calls:
        content: list[dict[str, Any]] = []
        if message.content:
            content.append({"type": "text", "text": message.content})
        content.extend(
            {
                "type": "tool_use",
                "id": call.id,
                "name": call.name,
                "input": call.arguments,
            }
            for call in message.tool_calls
        )
        return {"role": Role.ASSISTANT.value, "content": content}

    return {"role": message.role.value, "content": anthropic_message_content(message)}


def _content_order(blocks: dict[int, _ContentBlockParts]) -> list[dict[str, Any]]:
    order: list[dict[str, Any]] = []
    text_offset = 0
    reasoning_offset = 0
    for index in sorted(blocks):
        block = blocks[index]
        if block.block_type == "text":
            end = text_offset + len("".join(block.text_fragments))
            order.append({"type": "text", "start": text_offset, "end": end})
            text_offset = end
        elif block.block_type == "thinking":
            end = reasoning_offset + len("".join(block.thinking_fragments))
            order.append(
                {
                    "type": "thinking",
                    "start": reasoning_offset,
                    "end": end,
                    "signature": block.signature_fragments[0],
                }
            )
            reasoning_offset = end
        elif block.block_type == "redacted_thinking":
            order.append({"type": "redacted_thinking", "data": block.redacted_data})
        elif block.block_type == "tool_use":
            order.append({"type": "tool_call", "id": block.call_id})
    return order


def _ordered_assistant_content(message: ChatMessage, raw_order: object) -> list[dict[str, Any]]:
    if not isinstance(raw_order, list):
        raise ProviderError("Anthropic content order metadata is invalid", status_code=None)
    calls = {call.id: call for call in message.tool_calls}
    if len(calls) != len(message.tool_calls):
        raise ProviderError("Anthropic tool call ids are not unique", status_code=None)
    text_offset = 0
    reasoning_offset = 0
    seen_calls: set[str] = set()
    content: list[dict[str, Any]] = []
    for raw_block in raw_order:
        if not isinstance(raw_block, dict):
            raise ProviderError("Anthropic content order metadata is invalid", status_code=None)
        block_type = raw_block.get("type")
        if block_type in {"text", "thinking"}:
            expected_keys = (
                {"type", "start", "end"}
                if block_type == "text"
                else {"type", "start", "end", "signature"}
            )
            if set(raw_block) != expected_keys:
                raise ProviderError("Anthropic content order metadata is invalid", status_code=None)
            start = raw_block.get("start")
            end = raw_block.get("end")
            source = message.content if block_type == "text" else message.reasoning
            expected_offset = text_offset if block_type == "text" else reasoning_offset
            if (
                not isinstance(start, int)
                or isinstance(start, bool)
                or not isinstance(end, int)
                or isinstance(end, bool)
                or start != expected_offset
                or end < start
                or end > len(source)
            ):
                raise ProviderError("Anthropic content order metadata is invalid", status_code=None)
            block: dict[str, Any] = {"type": block_type}
            if block_type == "text":
                block["text"] = source[start:end]
                text_offset = end
            else:
                signature = raw_block.get("signature")
                if not isinstance(signature, str) or not signature:
                    raise ProviderError(
                        "Anthropic content order metadata is invalid",
                        status_code=None,
                    )
                block["thinking"] = source[start:end]
                block["signature"] = signature
                reasoning_offset = end
            content.append(block)
            continue
        if block_type == "redacted_thinking" and set(raw_block) == {"type", "data"}:
            data = raw_block.get("data")
            if not isinstance(data, str) or not data:
                raise ProviderError("Anthropic content order metadata is invalid", status_code=None)
            content.append({"type": "redacted_thinking", "data": data})
            continue
        if block_type == "tool_call" and set(raw_block) == {"type", "id"}:
            call_id = raw_block.get("id")
            if not isinstance(call_id, str) or call_id in seen_calls or call_id not in calls:
                raise ProviderError("Anthropic content order metadata is invalid", status_code=None)
            call = calls[call_id]
            seen_calls.add(call_id)
            content.append(
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.name,
                    "input": call.arguments,
                }
            )
            continue
        raise ProviderError("Anthropic content order metadata is invalid", status_code=None)
    if (
        text_offset != len(message.content)
        or reasoning_offset != len(message.reasoning)
        or seen_calls != set(calls)
    ):
        raise ProviderError("Anthropic content order does not match the message", status_code=None)
    return content


async def _iter_sse_events(
    response: httpx.Response,
) -> AsyncIterator[tuple[str | None, str]]:
    event_type: str | None = None
    data_lines: list[str] = []
    event_bytes = 0
    async for line in iter_bounded_lines(response, status_code=response.status_code):
        if line == "":
            if data_lines:
                yield event_type, "\n".join(data_lines)
            event_type = None
            data_lines.clear()
            event_bytes = 0
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            value = line[6:]
            event_type = value[1:] if value.startswith(" ") else value
            continue
        if line.startswith("data:"):
            value = line[5:]
            event_bytes = append_event_data(
                data_lines,
                value[1:] if value.startswith(" ") else value,
                event_bytes,
                status_code=response.status_code,
            )
    if data_lines:
        yield event_type, "\n".join(data_lines)


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


def _event_index(event: dict[str, object], *, status_code: int) -> int:
    index = event.get("index")
    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        raise ProviderError(
            "provider sent an invalid content block index",
            status_code=status_code,
        )
    return index


def _start_content_block(
    event: dict[str, object],
    *,
    status_code: int,
) -> tuple[int, _ContentBlockParts, ProviderDelta | None]:
    index = _event_index(event, status_code=status_code)
    value = _require_object(
        event.get("content_block"),
        status_code=status_code,
        label="content block",
    )
    block_type = value.get("type")
    if not isinstance(block_type, str):
        raise ProviderError(
            "provider sent an invalid content block type",
            status_code=status_code,
        )

    if block_type == "text":
        text = _optional_string(value, "text", status_code=status_code)
        delta = ProviderDelta(kind=DeltaKind.TEXT, text=text) if text else None
        return (
            index,
            _ContentBlockParts(block_type=block_type, text_fragments=[text] if text else []),
            delta,
        )
    if block_type == "thinking":
        thinking = _optional_string(value, "thinking", status_code=status_code)
        delta = ProviderDelta(kind=DeltaKind.REASONING, text=thinking) if thinking else None
        return (
            index,
            _ContentBlockParts(
                block_type=block_type,
                thinking_fragments=[thinking] if thinking else [],
            ),
            delta,
        )
    if block_type == "redacted_thinking":
        data = _required_string(value, "data", status_code=status_code)
        if not data:
            raise ProviderError(
                "provider sent invalid redacted thinking content",
                status_code=status_code,
            )
        return (
            index,
            _ContentBlockParts(block_type=block_type, redacted_data=data),
            None,
        )
    if block_type == "tool_use":
        call_id = value.get("id")
        name = value.get("name")
        if not isinstance(call_id, str) or not call_id or not isinstance(name, str) or not name:
            raise ProviderError(
                "provider sent an invalid tool use block",
                status_code=status_code,
            )
        raw_input = value.get("input", {})
        initial_input = _require_object(
            raw_input,
            status_code=status_code,
            label="tool input",
        )
        return (
            index,
            _ContentBlockParts(
                block_type=block_type,
                call_id=call_id,
                name=name,
                initial_input=cast(dict[str, Any], initial_input),
            ),
            None,
        )
    raise ProviderError(
        "provider sent an unsupported content block",
        status_code=status_code,
    )


def _apply_content_block_delta(
    blocks: dict[int, _ContentBlockParts],
    event: dict[str, object],
    *,
    status_code: int,
) -> ProviderDelta | None:
    index = _event_index(event, status_code=status_code)
    block = blocks.get(index)
    if block is None or block.stopped:
        raise ProviderError(
            "provider sent a delta for an unknown content block",
            status_code=status_code,
        )
    delta = _require_object(
        event.get("delta"),
        status_code=status_code,
        label="content block delta",
    )
    delta_type = delta.get("type")

    if delta_type == "text_delta" and block.block_type == "text":
        text = _required_string(delta, "text", status_code=status_code)
        if text:
            block.text_fragments.append(text)
        return ProviderDelta(kind=DeltaKind.TEXT, text=text) if text else None
    if delta_type == "thinking_delta" and block.block_type == "thinking":
        thinking = _required_string(delta, "thinking", status_code=status_code)
        if thinking:
            block.thinking_fragments.append(thinking)
        return ProviderDelta(kind=DeltaKind.REASONING, text=thinking) if thinking else None
    if delta_type == "signature_delta" and block.block_type == "thinking":
        signature = _required_string(delta, "signature", status_code=status_code)
        if not signature:
            raise ProviderError(
                "provider sent an empty thinking signature",
                status_code=status_code,
            )
        block.signature_fragments.append(signature)
        return None
    if delta_type == "input_json_delta" and block.block_type == "tool_use":
        fragment = _required_string(delta, "partial_json", status_code=status_code)
        if fragment:
            block.input_fragments.append(fragment)
        return None
    raise ProviderError(
        "provider sent an invalid content block delta",
        status_code=status_code,
    )


def _optional_string(
    values: dict[str, object],
    key: str,
    *,
    status_code: int,
) -> str:
    value = values.get(key, "")
    if not isinstance(value, str):
        raise ProviderError(
            "provider sent invalid streamed content",
            status_code=status_code,
        )
    return value


def _required_string(
    values: dict[str, object],
    key: str,
    *,
    status_code: int,
) -> str:
    value = values.get(key)
    if not isinstance(value, str):
        raise ProviderError(
            "provider sent invalid streamed content",
            status_code=status_code,
        )
    return value


def _parse_message_delta(
    event: dict[str, object],
    usage: _UsageParts,
    *,
    current_finish_reason: str | None,
    status_code: int,
) -> str | None:
    delta = _require_object(
        event.get("delta"),
        status_code=status_code,
        label="message delta",
    )
    finish_reason = current_finish_reason
    raw_finish_reason = delta.get("stop_reason")
    if raw_finish_reason is not None:
        if not isinstance(raw_finish_reason, str) or not raw_finish_reason:
            raise ProviderError(
                "provider sent an invalid finish reason",
                status_code=status_code,
            )
        finish_reason = raw_finish_reason

    raw_usage = event.get("usage")
    if raw_usage is not None:
        _update_usage(usage, raw_usage, status_code=status_code)
    return finish_reason


def _update_usage(parts: _UsageParts, value: object, *, status_code: int) -> None:
    usage = _require_object(value, status_code=status_code, label="usage")
    mappings = (
        ("input_tokens", "input_tokens"),
        ("output_tokens", "output_tokens"),
        ("cache_read_input_tokens", "cached_tokens"),
        ("cache_creation_input_tokens", "cache_creation_tokens"),
    )
    for source, target in mappings:
        if source not in usage:
            continue
        count = usage[source]
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ProviderError(
                "provider sent invalid token usage",
                status_code=status_code,
            )
        setattr(parts, target, count)
    parts.seen = True


def _finish_tool_calls(
    blocks: dict[int, _ContentBlockParts],
    *,
    status_code: int,
) -> list[ToolCall]:
    result: list[ToolCall] = []
    seen_ids: set[str] = set()
    for index in sorted(blocks):
        block = blocks[index]
        if block.block_type != "tool_use":
            continue
        arguments = block.initial_input
        if block.input_fragments:
            if block.initial_input:
                raise ProviderError(
                    "provider sent conflicting tool input",
                    status_code=status_code,
                )
            arguments = cast(
                dict[str, Any],
                _decode_object(
                    "".join(block.input_fragments),
                    status_code=status_code,
                    label="tool input",
                ),
            )
        if block.call_id in seen_ids:
            raise ProviderError(
                "provider returned duplicate tool call ids",
                status_code=status_code,
            )
        seen_ids.add(block.call_id)
        result.append(ToolCall(id=block.call_id, name=block.name, arguments=arguments))
    return result
