from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace
from typing import Any, cast

import httpx

from agent_workspace.core.models import (
    ChatMessage,
    ContentTrust,
    DeltaKind,
    ProviderDelta,
    ProviderRequest,
    Role,
    ToolCall,
    Usage,
)
from agent_workspace.providers.base import (
    ProviderError,
    provider_request_error,
    provider_stream_error,
    response_http_error,
    stream_request_timeout,
)
from agent_workspace.providers.streaming import append_event_data, iter_bounded_lines

REASONING_PROTOCOL = "openai-responses"
_PROTOCOL_KEY = "agent_workspace.reasoning_protocol"
_OUTPUT_KEY = "openai.responses_output"
_SOURCE_KEY = "agent_workspace.provider_content"
_OVERRIDE_KEY = "agent_workspace.provider_content_override"
_PREFIX_KEY = "agent_workspace.provider_prefix"
_EFFORTS = {"none", "low", "medium", "high", "xhigh", "max"}
_GPT6_MODELS = ("gpt-6-astra", "gpt-6-sol", "gpt-6-luna")


def is_gpt6_model(model: str) -> bool:
    return any(model == name or model.startswith(f"{name}-") for name in _GPT6_MODELS)


@dataclass(slots=True)
class _StreamState:
    items: dict[int, dict[str, Any]] = field(default_factory=dict)
    arguments: dict[int, list[str]] = field(default_factory=dict)
    text: list[str] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _Output:
    text: str
    reasoning: str
    calls: tuple[ToolCall, ...]
    order: list[dict[str, Any]]
    refused: bool = False


class OpenAIResponsesAdapter:
    """Stateless Responses transport sharing its owner's HTTP client and retry policy."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        client: httpx.AsyncClient,
        timeout: float | httpx.Timeout,
    ) -> None:
        self._endpoint = f"{base_url.rstrip('/')}/responses"
        self._api_key = api_key
        self._client = client
        self._timeout = timeout

    @staticmethod
    def request_body(request: ProviderRequest) -> dict[str, Any]:
        effort = request.metadata.get("reasoning_effort")
        if effort is None:
            effort = os.environ.get("AGENT_WORKSPACE_REASONING_EFFORT")
        if effort == "auto":
            effort = None
        if effort == "off":
            effort = "none"
        reasoning: dict[str, str] = {"summary": "auto"}
        if effort is not None:
            if (
                not isinstance(effort, str)
                or effort not in _EFFORTS
                or (effort == "none" and request.model.startswith("gpt-6-astra"))
            ):
                raise ProviderError(
                    f"{request.model} does not support reasoning effort selected in settings",
                    status_code=None,
                )
            reasoning["effort"] = effort
        body: dict[str, Any] = {
            "model": request.model,
            "input": _request_input(request),
            "stream": True,
            "store": False,
            "include": ["reasoning.encrypted_content"],
            "reasoning": reasoning,
        }
        if request.tools:
            # Responses defaults to strict schemas, while existing tool schemas allow optional keys.
            body["tools"] = [
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.advertised_input_schema,
                    "strict": False,
                }
                for tool in request.tools
            ]
        if request.max_output_tokens is not None:
            body["max_output_tokens"] = request.max_output_tokens
        if request.temperature is not None and effort == "none":
            body["temperature"] = request.temperature
        return body

    async def stream_once(self, request: ProviderRequest) -> AsyncIterator[ProviderDelta]:
        headers = {"Accept": "text/event-stream", "Accept-Encoding": "identity"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        status_code: int | None = None
        state = _StreamState()
        terminal: dict[str, Any] | None = None
        event_type: str | None = None
        try:
            async with self._client.stream(
                "POST",
                self._endpoint,
                headers=headers,
                json=self.request_body(request),
                timeout=stream_request_timeout(self._timeout),
            ) as response:
                status_code = response.status_code
                if not response.is_success:
                    raise await response_http_error(response, api_key=self._api_key)
                async for data in _iter_sse_data(response):
                    if data == "[DONE]":
                        break
                    event = _decode(data, status_code=status_code)
                    event_type = event.get("type")
                    if not isinstance(event_type, str):
                        raise ProviderError(
                            "provider sent an invalid response event", status_code=status_code
                        )
                    if event_type == "error":
                        raise provider_stream_error(_error_detail(event), status_code=status_code)
                    if event_type == "response.failed":
                        failed = _object(event.get("response"), status_code=status_code)
                        raise provider_stream_error(_error_detail(failed), status_code=status_code)
                    if event_type in {"response.completed", "response.incomplete"}:
                        terminal = _object(event.get("response"), status_code=status_code)
                        break
                    if event_type in {"response.output_text.delta", "response.refusal.delta"}:
                        text = _string(event, "delta", status_code=status_code, allow_empty=True)
                        state.text.append(text)
                        if text:
                            yield ProviderDelta(kind=DeltaKind.TEXT, text=text)
                    elif event_type == "response.reasoning_summary_text.delta":
                        text = _string(event, "delta", status_code=status_code, allow_empty=True)
                        state.reasoning.append(text)
                        if text:
                            yield ProviderDelta(kind=DeltaKind.REASONING, text=text)
                    elif event_type in {"response.output_item.added", "response.output_item.done"}:
                        _record_item(state, event, status_code=status_code)
                    elif event_type in {
                        "response.function_call_arguments.delta",
                        "response.function_call_arguments.done",
                    }:
                        _record_arguments(state, event, status_code=status_code)
                if terminal is None:
                    raise ProviderError(
                        "provider stream ended before completion",
                        status_code=status_code,
                        retryable=bool(state.text or state.reasoning or state.items),
                    )
                finish_reason = _finish_reason(terminal, event_type, status_code=status_code)
                raw_output = terminal.get("output")
                if not isinstance(raw_output, list):
                    raise ProviderError(
                        "provider sent invalid response output", status_code=status_code
                    )
                _validate_stream_items(state, raw_output, status_code=status_code)
                output = _parse_output(
                    raw_output, finish_reason=finish_reason, status_code=status_code
                )
                for kind, final, fragments in (
                    (DeltaKind.TEXT, output.text, state.text),
                    (DeltaKind.REASONING, output.reasoning, state.reasoning),
                ):
                    streamed = "".join(fragments)
                    if not final.startswith(streamed):
                        raise ProviderError(
                            "provider returned conflicting response output", status_code=status_code
                        )
                    suffix = final[len(streamed) :]
                    if suffix:
                        yield ProviderDelta(kind=kind, text=suffix)
                for call in output.calls:
                    yield ProviderDelta(kind=DeltaKind.TOOL_CALL, tool_call=call)
                if terminal.get("usage") is not None:
                    yield ProviderDelta(
                        kind=DeltaKind.USAGE,
                        usage=_parse_usage(terminal["usage"], status_code=status_code),
                    )
                if finish_reason == "stop":
                    finish_reason = (
                        "content_filter"
                        if output.refused
                        else ("tool_calls" if output.calls else "stop")
                    )
                yield ProviderDelta(
                    kind=DeltaKind.FINISH,
                    finish_reason=finish_reason,
                    provider_metadata={
                        _PROTOCOL_KEY: REASONING_PROTOCOL,
                        "agent_workspace.model": request.model,
                        _OUTPUT_KEY: output.order,
                    },
                )
        except ProviderError:
            raise
        except httpx.RequestError as exc:
            raise provider_request_error(exc, status_code=status_code) from None


def _request_input(request: ProviderRequest) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    pending: set[str] = set()
    seen: set[str] = set()
    for message in request.messages:
        if message.role is Role.TOOL:
            if not message.tool_call_id or message.tool_call_id not in pending:
                raise ProviderError(
                    "tool response does not match a function call", status_code=None
                )
            pending.remove(message.tool_call_id)
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": message.tool_call_id,
                    "output": _message_content(message),
                }
            )
            continue
        for call in message.tool_calls:
            if not call.id or call.id in seen:
                raise ProviderError("tool call has an invalid or duplicate id", status_code=None)
            seen.add(call.id)
            pending.add(call.id)
        stored = _ordered_input(message, request.model)
        if stored is not None:
            items.extend(stored)
            continue
        items.extend(_plain_input(message))
    return items


def _plain_input(message: ChatMessage) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if message.content or message.images or not message.tool_calls:
        items.append({"role": message.role.value, "content": _message_content(message)})
    items.extend(_call_input(call) for call in message.tool_calls)
    return items


def _message_content(message: ChatMessage) -> str | list[dict[str, Any]]:
    if not message.images:
        return message.provider_content()
    return [
        {"type": "input_text", "text": message.provider_content()},
        *(
            {"type": "input_image", "image_url": image.data_uri, "detail": "high"}
            for image in message.images
        ),
    ]


def _call_input(call: ToolCall, *, item_id: str | None = None) -> dict[str, Any]:
    try:
        arguments = json.dumps(
            call.arguments, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError):
        raise ProviderError(
            "tool call arguments are not JSON serializable", status_code=None
        ) from None
    if call.argument_error is not None:
        raw_arguments = call.provider_metadata.get("openai.arguments")
        if isinstance(raw_arguments, str):
            arguments = raw_arguments
    result = {
        "type": "function_call",
        "call_id": call.id,
        "name": call.name,
        "arguments": arguments,
    }
    if item_id is not None:
        result["id"] = item_id
    return result


def _ordered_input(message: ChatMessage, target_model: str) -> list[dict[str, Any]] | None:
    prefixes = message.provider_metadata.get(_PREFIX_KEY, [])
    if not isinstance(prefixes, list):
        raise ProviderError("OpenAI response prefix metadata is invalid", status_code=None)
    result: list[dict[str, Any]] = []
    for raw_prefix in prefixes:
        prefix = _object(raw_prefix, status_code=None)
        content = _string(prefix, "content", status_code=None, allow_empty=True)
        metadata = _object(prefix.get("provider_metadata"), status_code=None)
        try:
            trust = ContentTrust(prefix.get("trust", ContentTrust.DERIVED.value))
        except ValueError:
            raise ProviderError(
                "OpenAI response prefix trust is invalid", status_code=None
            ) from None
        source = ChatMessage(
            role=Role.ASSISTANT,
            content=content,
            trust=trust,
            provider_metadata=metadata,
        )
        stored_prefix = _response_input(source, target_model)
        result.extend(_plain_input(source) if stored_prefix is None else stored_prefix)
    stored = _response_input(message, target_model)
    if stored is None and not prefixes and _SOURCE_KEY not in message.provider_metadata:
        return None
    if stored is None:
        original_content = (
            _string(message.provider_metadata, _SOURCE_KEY, status_code=None, allow_empty=True)
            if _SOURCE_KEY in message.provider_metadata
            else message.content
        )
        result.extend(_plain_input(replace(message, content=original_content)))
    else:
        result.extend(stored)
    override = message.provider_metadata.get(_OVERRIDE_KEY)
    if override is not None:
        if not isinstance(override, str):
            raise ProviderError("OpenAI response content override is invalid", status_code=None)
        # Request-local continuation markers shrink text without discarding signed reasoning.
        remaining = replace(message, content=override).provider_content()
        for item in result:
            if item.get("role") == "assistant" and item.get("type") != "message":
                item["content"], remaining = remaining, ""
                continue
            if item.get("type") != "message":
                continue
            content_parts = item["content"]
            if not content_parts:
                content_parts.append({"type": "output_text", "text": remaining, "annotations": []})
                remaining = ""
            for part in content_parts:
                key = "text" if part["type"] == "output_text" else "refusal"
                part[key], remaining = remaining, ""
        if remaining:
            result.append({"role": "assistant", "content": remaining})
    return result


def _response_input(message: ChatMessage, target_model: str) -> list[dict[str, Any]] | None:
    metadata = message.provider_metadata
    source_model = metadata.get("agent_workspace.model")
    compatible = metadata.get(_PROTOCOL_KEY) == REASONING_PROTOCOL and (
        source_model is None or source_model == target_model
    )
    if not compatible:
        return None
    raw_order = metadata.get(_OUTPUT_KEY)
    if raw_order is None:
        if message.reasoning:
            raise ProviderError(
                "OpenAI reasoning is missing encrypted output metadata", status_code=None
            )
        return None
    if message.role is not Role.ASSISTANT or not isinstance(raw_order, list):
        raise ProviderError("OpenAI response output metadata is invalid", status_code=None)
    source_content = metadata.get(_SOURCE_KEY, message.content)
    if not isinstance(source_content, str):
        raise ProviderError("OpenAI response original content is invalid", status_code=None)
    result: list[dict[str, Any]] = []
    calls = {call.id: call for call in message.tool_calls}
    used_calls: set[str] = set()
    text_offset = 0
    for raw in raw_order:
        item = _object(raw, status_code=None)
        kind = item.get("type")
        if kind == "reasoning":
            result.append(_reasoning_item(item, status_code=None))
        elif kind == "function_call":
            call_id = _string(item, "call_id", status_code=None)
            if call_id not in calls or call_id in used_calls:
                raise ProviderError("OpenAI response tool metadata is invalid", status_code=None)
            used_calls.add(call_id)
            result.append(
                _call_input(calls[call_id], item_id=_string(item, "id", status_code=None))
            )
        elif kind == "message":
            raw_content = item.get("content")
            if not isinstance(raw_content, list):
                raise ProviderError("OpenAI response content metadata is invalid", status_code=None)
            content: list[dict[str, Any]] = []
            for raw_part in raw_content:
                part = _object(raw_part, status_code=None)
                start, end = part.get("start"), part.get("end")
                if (
                    type(start) is not int
                    or type(end) is not int
                    or start != text_offset
                    or end < start
                    or end > len(source_content)
                ):
                    raise ProviderError(
                        "OpenAI response text offsets are invalid", status_code=None
                    )
                text_offset = end
                text = replace(message, content=source_content[start:end]).provider_content()
                if part.get("type") == "output_text":
                    content.append({"type": "output_text", "text": text, "annotations": []})
                elif part.get("type") == "refusal":
                    content.append({"type": "refusal", "refusal": text})
                else:
                    raise ProviderError(
                        "OpenAI response content metadata is invalid", status_code=None
                    )
            result.append(
                {
                    "type": "message",
                    "id": _string(item, "id", status_code=None),
                    "role": "assistant",
                    "content": content,
                    **_message_fields(item, status_code=None),
                }
            )
        else:
            raise ProviderError("OpenAI response output metadata is invalid", status_code=None)
    if used_calls != set(calls) or text_offset != len(source_content):
        raise ProviderError(
            "OpenAI response output metadata does not match its message", status_code=None
        )
    return result


def _record_item(state: _StreamState, event: dict[str, Any], *, status_code: int) -> None:
    index = _index(event, status_code=status_code)
    item = _object(event.get("item"), status_code=status_code)
    _string(item, "id", status_code=status_code)
    previous = state.items.get(index)
    if previous is not None:
        for key in ("id", "type", "call_id", "name"):
            if key in previous and previous.get(key) != item.get(key):
                raise ProviderError(
                    "provider changed a response output item", status_code=status_code
                )
        fragments = state.arguments.get(index)
        if fragments is not None and "".join(fragments) != item.get("arguments"):
            raise ProviderError(
                "provider returned conflicting tool arguments", status_code=status_code
            )
    state.items[index] = item


def _record_arguments(state: _StreamState, event: dict[str, Any], *, status_code: int) -> None:
    index = _index(event, status_code=status_code)
    item = state.items.get(index)
    if (
        item is None
        or item.get("type") != "function_call"
        or item.get("id") != event.get("item_id")
    ):
        raise ProviderError(
            "provider sent arguments for an unknown tool call", status_code=status_code
        )
    if event["type"] == "response.function_call_arguments.delta":
        text = _string(event, "delta", status_code=status_code, allow_empty=True)
        state.arguments.setdefault(index, []).append(text)
    else:
        text = _string(event, "arguments", status_code=status_code, allow_empty=True)
        fragments = state.arguments.get(index)
        if fragments is not None and "".join(fragments) != text:
            raise ProviderError(
                "provider returned conflicting tool arguments", status_code=status_code
            )
        state.arguments[index] = [text]


def _validate_stream_items(state: _StreamState, output: list[Any], *, status_code: int) -> None:
    for index, earlier in state.items.items():
        if index >= len(output):
            raise ProviderError("provider omitted a response output item", status_code=status_code)
        final = _object(output[index], status_code=status_code)
        for key in ("id", "type", "call_id", "name"):
            if key in earlier and final.get(key) != earlier[key]:
                raise ProviderError(
                    "provider changed a response output item", status_code=status_code
                )
        if index in state.arguments and final.get("arguments") != "".join(state.arguments[index]):
            raise ProviderError(
                "provider returned conflicting tool arguments", status_code=status_code
            )


def _parse_output(output: list[Any], *, finish_reason: str, status_code: int) -> _Output:
    texts: list[str] = []
    thoughts: list[str] = []
    calls: list[ToolCall] = []
    order: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_calls: set[str] = set()
    text_offset = 0
    refused = False
    for raw in output:
        item = _object(raw, status_code=status_code)
        item_id = _string(item, "id", status_code=status_code)
        if item_id in seen_ids:
            raise ProviderError(
                "provider returned duplicate response item ids", status_code=status_code
            )
        seen_ids.add(item_id)
        kind = item.get("type")
        if kind == "reasoning":
            reasoning = _reasoning_item(
                item, status_code=status_code, allow_missing_encrypted=finish_reason != "stop"
            )
            if reasoning.get("encrypted_content"):
                order.append(reasoning)
            thoughts.extend(part["text"] for part in reasoning["summary"])
        elif kind == "message":
            if item.get("role") != "assistant" or not isinstance(item.get("content"), list):
                raise ProviderError(
                    "provider sent invalid assistant output", status_code=status_code
                )
            parts: list[dict[str, Any]] = []
            for raw_part in item["content"]:
                part = _object(raw_part, status_code=status_code)
                part_type = part.get("type")
                if part_type == "output_text":
                    text = _string(part, "text", status_code=status_code, allow_empty=True)
                elif part_type == "refusal":
                    text = _string(part, "refusal", status_code=status_code, allow_empty=True)
                    refused = True
                else:
                    raise ProviderError(
                        "provider sent unsupported assistant content", status_code=status_code
                    )
                texts.append(text)
                end = text_offset + len(text)
                parts.append({"type": part_type, "start": text_offset, "end": end})
                text_offset = end
            order.append(
                {
                    "type": "message",
                    "id": item_id,
                    "content": parts,
                    **_message_fields(item, status_code=status_code),
                }
            )
        elif kind == "function_call":
            call_id = _string(item, "call_id", status_code=status_code)
            if call_id in seen_calls:
                raise ProviderError(
                    "provider returned duplicate tool call ids", status_code=status_code
                )
            seen_calls.add(call_id)
            name = _string(item, "name", status_code=status_code)
            raw_arguments = _string(item, "arguments", status_code=status_code, allow_empty=True)
            arguments, argument_error = _tool_arguments(raw_arguments, finish_reason)
            calls.append(
                ToolCall(
                    call_id,
                    name,
                    arguments,
                    provider_metadata={
                        "openai.item_id": item_id,
                        "openai.arguments": raw_arguments,
                    },
                    argument_error=argument_error,
                )
            )
            order.append({"type": "function_call", "id": item_id, "call_id": call_id})
        else:
            raise ProviderError(
                "provider returned unsupported response output", status_code=status_code
            )
    return _Output("".join(texts), "".join(thoughts), tuple(calls), order, refused)


def _message_fields(item: dict[str, Any], *, status_code: int | None) -> dict[str, Any]:
    status = item.get("status", "completed")
    if not isinstance(status, str) or status not in {"completed", "incomplete", "in_progress"}:
        raise ProviderError("provider sent invalid message status", status_code=status_code)
    result: dict[str, Any] = {"status": status}
    if "phase" in item:
        phase = item["phase"]
        if phase is not None and (
            not isinstance(phase, str) or phase not in {"commentary", "final_answer"}
        ):
            raise ProviderError("provider sent invalid message phase", status_code=status_code)
        result["phase"] = phase
    return result


def _reasoning_item(
    item: dict[str, Any], *, status_code: int | None, allow_missing_encrypted: bool = False
) -> dict[str, Any]:
    item_id = _string(item, "id", status_code=status_code)
    encrypted: str | None
    if allow_missing_encrypted and item.get("encrypted_content") in (None, ""):
        encrypted = None
    else:
        encrypted = _string(item, "encrypted_content", status_code=status_code)
    summary = item.get("summary")
    if not isinstance(summary, list):
        raise ProviderError("provider sent invalid reasoning summary", status_code=status_code)
    result: list[dict[str, str]] = []
    for raw in summary:
        part = _object(raw, status_code=status_code)
        if part.get("type") != "summary_text":
            raise ProviderError("provider sent invalid reasoning summary", status_code=status_code)
        result.append(
            {
                "type": "summary_text",
                "text": _string(part, "text", status_code=status_code, allow_empty=True),
            }
        )
    return {"type": "reasoning", "id": item_id, "encrypted_content": encrypted, "summary": result}


def _tool_arguments(raw: str, finish_reason: str) -> tuple[dict[str, Any], str | None]:
    if finish_reason != "stop":
        return (
            {},
            "Provider ended the tool call before its arguments were complete. Retry with JSON.",
        )
    try:
        value = json.loads(raw, parse_constant=_reject_constant)
    except (json.JSONDecodeError, ValueError):
        value = None
    if not isinstance(value, dict):
        return (
            {},
            "Provider returned invalid JSON tool arguments. Retry with one complete JSON object.",
        )
    return value, None


def _finish_reason(response: dict[str, Any], event_type: str | None, *, status_code: int) -> str:
    expected = "completed" if event_type == "response.completed" else "incomplete"
    if response.get("status") != expected:
        raise ProviderError("provider sent a conflicting response status", status_code=status_code)
    if response.get("error") is not None:
        raise provider_stream_error(_error_detail(response), status_code=status_code)
    if expected == "completed":
        return "stop"
    details = _object(response.get("incomplete_details"), status_code=status_code)
    if details.get("reason") == "max_output_tokens":
        return "length"
    if details.get("reason") == "content_filter":
        return "content_filter"
    raise ProviderError(
        "provider response was incomplete for an unknown reason", status_code=status_code
    )


def _parse_usage(value: object, *, status_code: int) -> Usage:
    usage = _object(value, status_code=status_code)
    input_tokens = _token_count(usage, "input_tokens", status_code=status_code)
    output_tokens = _token_count(usage, "output_tokens", status_code=status_code)
    cached = 0
    if usage.get("input_tokens_details") is not None:
        details = _object(usage["input_tokens_details"], status_code=status_code)
        cached = _token_count(details, "cached_tokens", status_code=status_code)
    if cached > input_tokens:
        raise ProviderError("provider sent invalid token usage", status_code=status_code)
    if usage.get("output_tokens_details") is not None:
        details = _object(usage["output_tokens_details"], status_code=status_code)
        if _token_count(details, "reasoning_tokens", status_code=status_code) > output_tokens:
            raise ProviderError("provider sent invalid token usage", status_code=status_code)
    return Usage(input_tokens, output_tokens, cached)


def _token_count(values: dict[str, Any], key: str, *, status_code: int) -> int:
    value = values.get(key, 0)
    if type(value) is not int or value < 0:
        raise ProviderError("provider sent invalid token usage", status_code=status_code)
    return value


def _index(event: dict[str, Any], *, status_code: int) -> int:
    index = event.get("output_index")
    if type(index) is not int or index < 0:
        raise ProviderError("provider sent an invalid output index", status_code=status_code)
    return index


def _object(value: object, *, status_code: int | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProviderError("provider sent an invalid response object", status_code=status_code)
    return value


def _string(
    item: dict[str, Any],
    key: str,
    *,
    status_code: int | None,
    allow_empty: bool = False,
) -> str:
    value = item.get(key)
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ProviderError(f"provider sent invalid response {key}", status_code=status_code)
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON constant {value}")


def _decode(data: str, *, status_code: int) -> dict[str, Any]:
    try:
        value = json.loads(data, parse_constant=_reject_constant)
    except (json.JSONDecodeError, ValueError):
        raise ProviderError(
            "provider sent invalid JSON in response event", status_code=status_code
        ) from None
    return _object(value, status_code=status_code)


def _error_detail(item: dict[str, Any]) -> str | None:
    error = item.get("error", item)
    if isinstance(error, str):
        return error
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return cast(str, error["message"])
    return None


async def _iter_sse_data(response: httpx.Response) -> AsyncIterator[str]:
    lines: list[str] = []
    event_bytes = 0
    async for line in iter_bounded_lines(response, status_code=response.status_code):
        if not line:
            if lines:
                yield "\n".join(lines)
                lines.clear()
                event_bytes = 0
        elif line.startswith("data:"):
            value = line[5:]
            if value.startswith(" "):
                value = value[1:]
            event_bytes = append_event_data(
                lines, value, event_bytes, status_code=response.status_code
            )
    if lines:
        yield "\n".join(lines)
