from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from types import TracebackType
from typing import Any, cast
from urllib.parse import quote

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
)
from agent_workspace.providers.base import (
    ProviderError,
    encode_json_request,
    provider_request_error,
    response_http_error,
    stream_request_timeout,
    stream_with_retries,
)
from agent_workspace.providers.streaming import append_event_data, iter_bounded_lines

_THOUGHT_SIGNATURE_KEY = "gemini.thought_signature"
_PROVIDER_ID_PRESENT_KEY = "gemini.provider_id_present"
_CONTENT_ORDER_KEY = "gemini.content_order"
_REASONING_PROTOCOL_KEY = "agent_workspace.reasoning_protocol"


class GeminiProvider:
    """Google Gemini streamGenerateContent SSE adapter."""

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
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client = client or httpx.AsyncClient(trust_env=not is_loopback_endpoint(base_url))
        self._owns_client = client is None

    @property
    def id(self) -> str:
        return self._id

    @property
    def reasoning_protocol(self) -> str:
        return "gemini"

    def encode_request(self, request: ProviderRequest) -> bytes:
        body = _request_body(request)
        _validate_json_body(body)
        return encode_json_request(cast(dict[str, object], body))

    async def __aenter__(self) -> GeminiProvider:
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
        headers = {"Accept": "text/event-stream", "Accept-Encoding": "identity"}
        if self._api_key:
            headers["x-goog-api-key"] = self._api_key

        encoded_model = quote(request.model, safe="")
        endpoint = f"{self._base_url}/models/{encoded_model}:streamGenerateContent?alt=sse"
        usage: Usage | None = None
        finish_reason: str | None = None
        tool_call_index = 0
        tool_call_ids: set[str] = set()
        content_order: list[dict[str, Any]] = []
        visible_text_characters = 0
        reasoning_characters = 0
        status_code: int | None = None

        try:
            body = _request_body(request)
            _validate_json_body(body)
            async with self._client.stream(
                "POST",
                endpoint,
                headers=headers,
                json=body,
                timeout=stream_request_timeout(self._timeout),
            ) as response:
                status_code = response.status_code
                if not response.is_success:
                    raise await response_http_error(response, api_key=self._api_key)

                async for data in _iter_sse_data(response):
                    if data.strip() == "[DONE]":
                        break

                    chunk = _decode_object(data, status_code=status_code, label="SSE event")
                    if chunk.get("error") is not None:
                        raise ProviderError(
                            "provider returned an error",
                            status_code=status_code,
                        )

                    raw_usage = chunk.get("usageMetadata")
                    if raw_usage is not None:
                        usage = _parse_usage(raw_usage, status_code=status_code)

                    raw_prompt_feedback = chunk.get("promptFeedback")
                    if raw_prompt_feedback is not None:
                        prompt_feedback = _require_object(
                            raw_prompt_feedback,
                            status_code=status_code,
                            label="prompt feedback",
                        )
                        block_reason = prompt_feedback.get("blockReason")
                        if block_reason is not None:
                            if not isinstance(block_reason, str) or not block_reason.strip():
                                raise ProviderError(
                                    "provider sent an invalid prompt block reason",
                                    status_code=status_code,
                                )
                            finish_reason = "blocked"

                    raw_candidates = chunk.get("candidates", [])
                    if not isinstance(raw_candidates, list):
                        raise ProviderError(
                            "provider sent invalid candidates",
                            status_code=status_code,
                        )
                    if len(raw_candidates) > 1:
                        raise ProviderError(
                            "provider returned multiple candidates, which are unsupported",
                            status_code=status_code,
                        )

                    for raw_candidate in raw_candidates:
                        candidate = _require_object(
                            raw_candidate,
                            status_code=status_code,
                            label="candidate",
                        )
                        candidate_index = candidate.get("index", 0)
                        if (
                            not isinstance(candidate_index, int)
                            or isinstance(candidate_index, bool)
                            or candidate_index != 0
                        ):
                            raise ProviderError(
                                "provider returned a non-primary candidate",
                                status_code=status_code,
                            )
                        raw_content = candidate.get("content")
                        if raw_content is not None:
                            content = _require_object(
                                raw_content,
                                status_code=status_code,
                                label="candidate content",
                            )
                            raw_parts = content.get("parts", [])
                            if not isinstance(raw_parts, list):
                                raise ProviderError(
                                    "provider sent invalid content parts",
                                    status_code=status_code,
                                )
                            for raw_part in raw_parts:
                                part = _require_object(
                                    raw_part,
                                    status_code=status_code,
                                    label="content part",
                                )
                                text = part.get("text")
                                thought = part.get("thought", False)
                                thought_signature = part.get("thoughtSignature")
                                if not isinstance(thought, bool):
                                    raise ProviderError(
                                        "provider sent an invalid thought marker",
                                        status_code=status_code,
                                    )
                                if thought_signature is not None and (
                                    not isinstance(thought_signature, str) or not thought_signature
                                ):
                                    raise ProviderError(
                                        "provider sent an invalid thought signature",
                                        status_code=status_code,
                                    )
                                handled = False
                                if text is not None:
                                    if not isinstance(text, str):
                                        raise ProviderError(
                                            "provider sent invalid text content",
                                            status_code=status_code,
                                        )
                                    handled = True
                                    if thought:
                                        start = reasoning_characters
                                        reasoning_characters += len(text)
                                        descriptor: dict[str, Any] = {
                                            "type": "reasoning",
                                            "start": start,
                                            "end": reasoning_characters,
                                        }
                                    else:
                                        start = visible_text_characters
                                        visible_text_characters += len(text)
                                        descriptor = {
                                            "type": "text",
                                            "start": start,
                                            "end": visible_text_characters,
                                        }
                                    if thought_signature is not None:
                                        descriptor["thought_signature"] = thought_signature
                                    content_order.append(descriptor)
                                    if text:
                                        kind = DeltaKind.REASONING if thought else DeltaKind.TEXT
                                        yield ProviderDelta(kind=kind, text=text)

                                raw_function_call = part.get("functionCall")
                                if raw_function_call is not None:
                                    if handled:
                                        raise ProviderError(
                                            "provider sent multiple payloads in one content part",
                                            status_code=status_code,
                                        )
                                    handled = True
                                    function_call = _parse_function_call(
                                        raw_function_call,
                                        thought_signature=thought_signature,
                                        generated_id=f"gemini-call-{tool_call_index}",
                                        status_code=status_code,
                                    )
                                    if function_call.id in tool_call_ids:
                                        raise ProviderError(
                                            "provider returned duplicate tool call ids",
                                            status_code=status_code,
                                        )
                                    tool_call_ids.add(function_call.id)
                                    tool_call_index += 1
                                    content_order.append(
                                        {"type": "tool_call", "id": function_call.id}
                                    )
                                    yield ProviderDelta(
                                        kind=DeltaKind.TOOL_CALL,
                                        tool_call=function_call,
                                    )
                                if not handled:
                                    content_order.append({"type": "opaque", "part": part})

                        raw_finish_reason = candidate.get("finishReason")
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
                        "provider stream ended before completion",
                        status_code=status_code,
                        retryable=bool(content_order),
                    )
                if usage is not None:
                    yield ProviderDelta(kind=DeltaKind.USAGE, usage=usage)
                provider_metadata: dict[str, Any] = (
                    {_CONTENT_ORDER_KEY: content_order} if content_order else {}
                )
                if any(part.get("type") == "reasoning" for part in content_order):
                    provider_metadata[_REASONING_PROTOCOL_KEY] = "gemini"
                yield ProviderDelta(
                    kind=DeltaKind.FINISH,
                    finish_reason=finish_reason,
                    provider_metadata=provider_metadata,
                )
        except ProviderError:
            raise
        except httpx.RequestError as exc:
            raise provider_request_error(exc, status_code=status_code) from None


def _request_body(request: ProviderRequest) -> dict[str, Any]:
    body: dict[str, Any] = {}
    system_parts: list[dict[str, str]] = []
    contents: list[dict[str, Any]] = []
    call_names: dict[str, str] = {}
    call_remote_ids: dict[str, str | None] = {}

    for message in request.messages:
        if message.role is Role.SYSTEM:
            system_parts.append({"text": message.content})
            continue

        if message.role is Role.TOOL:
            call_id = message.tool_call_id
            if not call_id or call_id not in call_names:
                raise ProviderError(
                    "tool response does not match a function call",
                    status_code=None,
                )
            response: dict[str, Any] = {
                "name": call_names[call_id],
                "response": _tool_response(message.provider_content()),
            }
            remote_id = call_remote_ids.get(call_id, call_id)
            if remote_id is not None:
                response["id"] = remote_id
            response_part = {"functionResponse": response}
            if (
                contents
                and contents[-1].get("role") == "user"
                and all(
                    isinstance(part, dict) and "functionResponse" in part
                    for part in contents[-1].get("parts", [])
                )
            ):
                contents[-1]["parts"].append(response_part)
            else:
                contents.append({"role": "user", "parts": [response_part]})
            continue

        role = "model" if message.role is Role.ASSISTANT else "user"
        parts = _message_parts(
            message,
            call_names,
            call_remote_ids,
            target_model=request.model,
        )
        contents.append({"role": role, "parts": parts})

    if system_parts:
        body["systemInstruction"] = {"parts": system_parts}
    body["contents"] = contents
    if request.tools:
        body["tools"] = [
            {
                "functionDeclarations": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.advertised_input_schema,
                    }
                    for tool in request.tools
                ]
            }
        ]
    generation_config: dict[str, Any] = {}
    if request.temperature is not None:
        generation_config["temperature"] = request.temperature
    if request.max_output_tokens is not None:
        generation_config["maxOutputTokens"] = request.max_output_tokens
    if generation_config:
        body["generationConfig"] = generation_config
    return body


def _tool_response(content: str) -> dict[str, Any]:
    try:
        value = cast(object, json.loads(content))
    except (json.JSONDecodeError, ValueError):
        return {"result": content}
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {"result": value}


def _message_parts(
    message: ChatMessage,
    call_names: dict[str, str],
    call_remote_ids: dict[str, str | None],
    *,
    target_model: str,
) -> list[dict[str, Any]]:
    raw_order = message.provider_metadata.get(_CONTENT_ORDER_KEY)
    source_model = message.provider_metadata.get("agent_workspace.model")
    source_protocol = message.provider_metadata.get(_REASONING_PROTOCOL_KEY)
    model_changed = isinstance(source_model, str) and source_model != target_model
    signatures_compatible = not model_changed and source_protocol in {None, "gemini"}
    if raw_order is not None and message.role is not Role.ASSISTANT:
        raise ProviderError(
            "Gemini content order is only valid for assistant messages",
            status_code=None,
        )
    if raw_order is None:
        default_parts: list[dict[str, Any]] = (
            [{"text": message.content}] if message.content or not message.tool_calls else []
        )
        default_parts.extend(
            _function_call_part(
                call,
                call_names,
                call_remote_ids,
                include_thought_signature=signatures_compatible,
            )
            for call in message.tool_calls
        )
        default_parts.extend(
            {
                "inline_data": {
                    "mime_type": image.media_type,
                    "data": image.base64,
                }
            }
            for image in message.images
        )
        return default_parts
    if not isinstance(raw_order, list):
        raise ProviderError("Gemini content order metadata is invalid", status_code=None)

    calls = {call.id: call for call in message.tool_calls}
    if len(calls) != len(message.tool_calls):
        raise ProviderError("Gemini tool call ids are not unique", status_code=None)
    seen_calls: set[str] = set()
    text_offset = 0
    reasoning_offset = 0
    has_reasoning_blocks = False
    ordered_parts: list[dict[str, Any]] = []
    for raw_block in raw_order:
        if not isinstance(raw_block, dict):
            raise ProviderError("Gemini content order metadata is invalid", status_code=None)
        block_type = raw_block.get("type")
        if block_type in {"text", "reasoning"}:
            allowed_keys = {"type", "start", "end", "thought_signature"}
            if not {"type", "start", "end"}.issubset(raw_block) or not set(raw_block).issubset(
                allowed_keys
            ):
                raise ProviderError("Gemini content order metadata is invalid", status_code=None)
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
                raise ProviderError("Gemini content order metadata is invalid", status_code=None)
            part: dict[str, Any] = {"text": source[start:end]}
            if block_type == "reasoning":
                has_reasoning_blocks = True
                part["thought"] = True
                reasoning_offset = end
            else:
                text_offset = end
            thought_signature = raw_block.get("thought_signature")
            if thought_signature is not None:
                if not isinstance(thought_signature, str) or not thought_signature:
                    raise ProviderError(
                        "Gemini content order metadata is invalid", status_code=None
                    )
                if signatures_compatible:
                    part["thoughtSignature"] = thought_signature
            if block_type != "reasoning" or signatures_compatible:
                ordered_parts.append(part)
            continue
        if block_type == "tool_call" and set(raw_block) == {"type", "id"}:
            call_id = raw_block.get("id")
            if not isinstance(call_id, str) or call_id in seen_calls or call_id not in calls:
                raise ProviderError("Gemini content order metadata is invalid", status_code=None)
            seen_calls.add(call_id)
            ordered_parts.append(
                _function_call_part(
                    calls[call_id],
                    call_names,
                    call_remote_ids,
                    include_thought_signature=signatures_compatible,
                )
            )
            continue
        if block_type == "opaque" and set(raw_block) == {"type", "part"}:
            raw_part = raw_block.get("part")
            if not isinstance(raw_part, dict):
                raise ProviderError("Gemini content order metadata is invalid", status_code=None)
            part = cast(dict[str, Any], raw_part)
            if signatures_compatible:
                ordered_parts.append(part)
            elif part.get("thought") is not True:
                retained = dict(part)
                retained.pop("thoughtSignature", None)
                if retained:
                    ordered_parts.append(retained)
            continue
        raise ProviderError("Gemini content order metadata is invalid", status_code=None)
    if (
        text_offset != len(message.content)
        or (
            (has_reasoning_blocks or source_protocol == "gemini")
            and reasoning_offset != len(message.reasoning)
        )
        or seen_calls != set(calls)
    ):
        raise ProviderError(
            "Gemini content order does not match the assistant message",
            status_code=None,
        )
    return ordered_parts


def _function_call_part(
    call: ToolCall,
    call_names: dict[str, str],
    call_remote_ids: dict[str, str | None],
    *,
    include_thought_signature: bool = True,
) -> dict[str, Any]:
    function_call: dict[str, Any] = {
        "name": call.name,
        "args": call.arguments,
    }
    provider_id_present = call.provider_metadata.get(_PROVIDER_ID_PRESENT_KEY, True)
    if not isinstance(provider_id_present, bool):
        raise ProviderError("Gemini tool call has invalid id metadata", status_code=None)
    if call.id and provider_id_present:
        function_call["id"] = call.id
    if call.id:
        call_names[call.id] = call.name
        call_remote_ids[call.id] = call.id if provider_id_present else None
    call_part: dict[str, Any] = {"functionCall": function_call}
    thought_signature = call.provider_metadata.get(_THOUGHT_SIGNATURE_KEY)
    if thought_signature is not None and include_thought_signature:
        if not isinstance(thought_signature, str) or not thought_signature:
            raise ProviderError(
                "Gemini tool call has an invalid thought signature",
                status_code=None,
            )
        call_part["thoughtSignature"] = thought_signature
    return call_part


def _validate_json_body(body: dict[str, Any]) -> None:
    try:
        json.dumps(body, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise ProviderError(
            "provider request is not JSON serializable",
            status_code=None,
        ) from None


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


def _parse_function_call(
    value: object,
    *,
    thought_signature: object,
    generated_id: str,
    status_code: int,
) -> ToolCall:
    function_call = _require_object(
        value,
        status_code=status_code,
        label="function call",
    )
    name = function_call.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ProviderError(
            "provider sent an invalid function name",
            status_code=status_code,
        )
    raw_arguments = function_call.get("args", {})
    arguments = _require_object(
        raw_arguments,
        status_code=status_code,
        label="function arguments",
    )
    raw_id = function_call.get("id")
    if raw_id is not None and (not isinstance(raw_id, str) or not raw_id.strip()):
        raise ProviderError(
            "provider sent an invalid function call id",
            status_code=status_code,
        )
    call_id = raw_id if isinstance(raw_id, str) else generated_id
    provider_metadata: dict[str, Any] = {}
    provider_metadata[_PROVIDER_ID_PRESENT_KEY] = isinstance(raw_id, str)
    if thought_signature is not None:
        if not isinstance(thought_signature, str) or not thought_signature:
            raise ProviderError(
                "provider sent an invalid thought signature",
                status_code=status_code,
            )
        provider_metadata[_THOUGHT_SIGNATURE_KEY] = thought_signature
    return ToolCall(
        id=call_id,
        name=name,
        arguments=cast(dict[str, Any], arguments),
        provider_metadata=provider_metadata,
    )


def _parse_usage(value: object, *, status_code: int) -> Usage:
    usage = _require_object(value, status_code=status_code, label="usage metadata")
    input_tokens = _token_count(usage, "promptTokenCount", status_code=status_code)
    candidate_tokens = _token_count(usage, "candidatesTokenCount", status_code=status_code)
    thought_tokens = _token_count(usage, "thoughtsTokenCount", status_code=status_code)
    cached_tokens = _token_count(usage, "cachedContentTokenCount", status_code=status_code)
    return Usage(
        input_tokens=input_tokens,
        output_tokens=candidate_tokens + thought_tokens,
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
