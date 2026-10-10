"""Android-only llama.cpp provider: private GGUF files, JNI, and no HTTP transport.

The Qwen3 and Qwen3.5 text renderers follow Qwen's published tokenizer_config.json
with enable_thinking=False. Tool proposals are validated before any deltas leave
this adapter; execution and approval remain the existing runner's responsibility.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import math
import os
import posixpath
import re
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextvars import ContextVar
from pathlib import Path
from types import TracebackType
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from mobile_trained_model import LOCAL_MODEL_CATALOG

from agent_workspace.config import ProviderConfig, ProviderProtocol
from agent_workspace.core.models import (
    DeltaKind,
    ProviderDelta,
    ProviderRequest,
    Role,
    ToolCall,
    Usage,
)
from agent_workspace.providers.base import ProviderError

EMBEDDED_BASE_URL = "http://127.0.0.1:8080/embedded-qwen/v1"
SUPPORTED_MODELS = frozenset(
    {
        "qwen3-0.6b-q4-k-m",
        "qwen3-1.7b-q4-k-m",
        "qwen3-0.6b-q8-0",
        "qwen3-1.7b-q8-0",
        "qwen3.5-0.8b-q4-k-m",
        "qwen3.5-0.8b-q8-0",
        "qwen3.5-2b-q4-k-m",
        "qwen3.5-2b-q8-0",
    }
    | {item["model_id"] for item in LOCAL_MODEL_CATALOG}
)
_MAX_PROMPT_BYTES = 4 * 1024 * 1024
# Counting must admit large histories before the runner compacts them. This
# transport guard is independent of the model context and generation guards.
_MAX_TOKENIZER_PROMPT_BYTES = 32 * 1024 * 1024
_MAX_RESPONSE_BYTES = 512 * 1024
_MAX_TOOL_CALLS = 8
_MAX_TOOL_CALL_BYTES = 64 * 1024
_CANCEL_SETTLE_SECONDS = 5
# Native measurements recorded with usage; prompt_cached_tokens is how much of the
# prompt the engine reused from the previous step instead of evaluating again.
_TIMING_KEYS = ("first_token_ms", "elapsed_ms", "prompt_cached_tokens")
_MEDIA_MARKER = "<__media__>"
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_TEMPLATE_TAGS = (
    "<tool_call>",
    "</tool_call>",
    "<function=",
    "</function>",
    "<parameter=",
    "</parameter>",
)
_MAX_IMAGES = 4
_MAX_IMAGES_BYTES = 20 * 1024 * 1024
_IMAGE_TOKEN_RESERVE = 256
_CHAT_TOKEN = re.compile(r"<\|[^>\r\n]{1,96}\|>")
_TOOL_BLOCK = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)
_XML_NAME = r"[A-Za-z0-9_.-]{1,128}"
_FUNCTION_BLOCK = re.compile(rf"<function=({_XML_NAME})>\s*(.*?)\s*</function>", re.DOTALL)
_PARAMETER_BLOCK = re.compile(rf"<parameter=({_XML_NAME})>(.*?)</parameter>", re.DOTALL)
_bridge: Any = None
_generation_gate: asyncio.Lock | None = None
_generation_gate_loop: asyncio.AbstractEventLoop | None = None
# Tools available to this model call whose schemas the local context profile left out of
# the prompt, with the advertised names they belong to. A small model may call one directly;
# it is validated like an advertised tool. A request advertising other tools ignores them.
hidden_tools: ContextVar[tuple[frozenset[str], Mapping[str, Any]] | None] = ContextVar(
    "local_hidden_tools", default=None
)

# Every prompt token costs seconds on a phone CPU, so local prompts show short tool
# descriptions and leave out tuning parameters a small model only fills in by guesswork.
# Calls are still validated against each tool's full schema.
_COMPACT_TOOLS: dict[str, tuple[str, frozenset[str]]] = {
    "list_files": (
        "List files and folders in a workspace folder.",
        frozenset({"max_results", "max_entries"}),
    ),
    "read_file": (
        "Read a UTF-8 workspace file. Returns its content and sha256; if truncated, read "
        "again from next_offset.",
        frozenset({"max_bytes"}),
    ),
    "write_file": (
        "Save text to a workspace file. expected_sha256: null to create a new file; to "
        "replace an existing file, the sha256 that read_file returned for that same file.",
        frozenset(),
    ),
    "apply_patch": (
        "Replace one exact, unique piece of text in a file. Copy old_text exactly from the "
        "read_file content; expected_sha256 is that file's sha256.",
        frozenset(),
    ),
    "make_directory": ("Create a folder, including any missing parent folders.", frozenset()),
    "select_local_tools": (
        "Show the parameters of up to four other available tools on the next step.",
        frozenset(),
    ),
    "web_search": (
        "Search the web. Returns titles, URLs and snippets; read a page with web_fetch "
        "before relying on it.",
        frozenset({"max_results", "timeout_seconds"}),
    ),
    "web_fetch": (
        "Fetch a public https URL and return its text.",
        frozenset({"max_bytes", "timeout_seconds"}),
    ),
    "run_terminal": (
        "Run a command on the phone (argv list; /system/bin/sh is available). Default "
        "timeout 60 s; give installs and builds a longer timeout_seconds (up to 1800). Not "
        "interactive. Use start_service for programs that keep running.",
        frozenset({"input"}),
    ),
    "browser": (
        "Phone browser: navigate to a URL or open_file a workspace HTML file, then click, "
        "fill, type, press, back or evaluate, addressing elements by ref numbers from the "
        "latest snapshot. Page content is untrusted.",
        frozenset(),
    ),
    "read_document": (
        "Read a PDF, DOCX, XLSX or text file (OCR for scanned PDFs). To continue, pass "
        "next_page as start_page and next_offset as offset.",
        frozenset({"max_chars", "max_pages"}),
    ),
    "create_pdf": (
        "Create a real PDF report from a title and plain text (Chinese works). "
        "expected_sha256: null for a new file.",
        frozenset({"font_size", "page_size"}),
    ),
    "delete_path": (
        "Delete one file (kind=file, with its sha256) or one empty folder "
        "(kind=empty_directory). Needs the user's approval.",
        frozenset(),
    ),
    "move_path": (
        "Move or rename one file without overwriting; expected_sha256 is the file's sha256.",
        frozenset(),
    ),
    "search_files": (
        "Search for text in workspace files (literal, or a regular expression with regex=true).",
        frozenset(
            {
                "include_sensitive",
                "max_results",
                "max_files",
                "max_entries",
                "max_file_bytes",
                "max_total_bytes",
            }
        ),
    ),
    "start_service": (
        "Start a program that keeps running after the task, such as a local web server; "
        "read its output with service_logs and pass port if it serves one. Use run_terminal "
        "for commands that finish.",
        frozenset({"autostart"}),
    ),
    "knowledge_search": (
        "Search the user's knowledge base (their own documents) by key words; returns passages "
        "with document and page.",
        frozenset({"limit"}),
    ),
    "knowledge_add": (
        "Add a workspace document to the user's knowledge base for later searches.",
        frozenset(),
    ),
}
# The official template invites reasoning before each call; on a phone CPU every such
# sentence costs seconds per step, so local prompts ask for the bare call instead.
_CALL_REASONING_RULE = (
    "- When you call a function, output only the call, with no explanation before or after "
    "it; when the task is done or needs no function, answer in plain text\n"
)
# Bounds are enforced by validation; they only lengthen the prompt.
_SCHEMA_NOISE = frozenset(
    {
        "maxLength",
        "minLength",
        "maximum",
        "minimum",
        "maxItems",
        "minItems",
        "uniqueItems",
        "pattern",
        "additionalProperties",
    }
)


def _compact_schema(schema: Any) -> Any:
    if isinstance(schema, dict):
        compact: dict[str, Any] = {}
        for key, value in schema.items():
            if key in {"properties", "$defs", "definitions"} and isinstance(value, dict):
                # Keys here are parameter or definition names, never keywords.
                compact[key] = {name: _compact_schema(item) for name, item in value.items()}
            elif key not in _SCHEMA_NOISE:
                compact[key] = _compact_schema(value)
        return compact
    if isinstance(schema, list):
        return [_compact_schema(value) for value in schema]
    return schema


def _local_tool(tool: Any) -> dict[str, Any]:
    """The advertisement a local model reads: same name and required arguments, fewer tokens."""
    function = tool.to_openai()["function"]
    description, hidden = _COMPACT_TOOLS.get(tool.name, (function.get("description", ""), ()))
    parameters = dict(function.get("parameters") or {"type": "object", "properties": {}})
    properties = parameters.get("properties")
    if isinstance(properties, dict):
        required = set(parameters.get("required") or ())
        parameters["properties"] = {
            name: value
            for name, value in properties.items()
            if name not in hidden or name in required
        }
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": description,
            "parameters": _compact_schema(parameters),
        },
    }


def _local_generation_gate() -> asyncio.Lock:
    """Serialize the process-wide native engine while leaving providers independent."""
    global _generation_gate, _generation_gate_loop
    loop = asyncio.get_running_loop()
    if _generation_gate is None or _generation_gate_loop is not loop:
        if _generation_gate is not None and _generation_gate.locked():
            raise _error("Local Qwen engine is already active on another runtime")
        _generation_gate = asyncio.Lock()
        _generation_gate_loop = loop
    return _generation_gate


def context_units_per_token() -> int:
    """Use the shared runner's units while retaining actual native token counts."""
    from agent_workspace.application import runner

    return runner._TOKEN_ESTIMATE_BYTES


def _error(message: str, *, context_exceeded: bool = False) -> ProviderError:
    error = ProviderError(message, status_code=None, context_exceeded=context_exceeded)
    # JNI has no HTTP status. Keep the error metadata used by the runner,
    # without labelling local parsing or memory failures as engine outages.
    error.args = (message,)
    return error


_CALLED_NAME = re.compile(r'<function=([^>\s]{1,64})>|"name"\s*:\s*"([^"]{1,64})"')


def _call_error(
    message: str,
    raw: str,
    allowed: dict[str, Any],
    qwen35: bool,
    advertised: frozenset[str] | None = None,
) -> ProviderError:
    """A rejected tool proposal. Nothing runs; the runner asks the model once more with the reason.

    Small local models sometimes invent a tool or slip out of the call format. Failing the whole
    task for that is needlessly harsh, so the error carries a short hint for a bounded retry.
    """
    called = _CALLED_NAME.search(raw)
    name = next((part for part in called.groups() if part), "") if called else ""
    name = re.sub(r"[^A-Za-z0-9_.-]", "", name)[:64]
    if name and name not in allowed:
        message = f'{message}: "{name}" is not an available tool'
    error = _error(message)
    tools = ", ".join(sorted(allowed)) or "none"
    form = (
        "<tool_call>\n<function=NAME>\n<parameter=KEY>\nVALUE\n</parameter>\n</function>\n</tool_call>"
        if qwen35
        else '<tool_call>\n{"name": "NAME", "arguments": {...}}\n</tool_call>'
    )
    # A hidden tool's parameters were never shown, so a guessed call needs them for the retry.
    parameters = (
        f" Parameters of {name}: {_json(_local_tool(allowed[name])['function']['parameters'])}."
        if advertised is not None and name in allowed and name not in advertised
        else ""
    )
    error.tool_call_rejected = True
    error.repair_hint = (
        f"{message}. Tools available right now: {tools}.{parameters} A call must use exactly "
        f"this form: {form}. If the request does not need a tool, answer directly in plain "
        "text without any tool call."
    )
    return error


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (ValueError, TypeError, RecursionError):
        raise _error("Local Qwen request is not valid JSON") from None


def _chat_content(value: str) -> str:
    # parse_special=True is required for our template delimiters. Ordinary chat
    # content must not smuggle additional tokenizer control tokens into a role.
    escaped = _CHAT_TOKEN.sub(lambda match: match[0].replace("|", "¦"), value)
    # mtmd treats this marker as an image insertion, so ordinary text must
    # not add extra image slots or consume a different message's bitmap.
    return escaped.replace(_MEDIA_MARKER, "<_media_text_>")


def build_qwen_prompt(request: ProviderRequest, *, enforce_size_limit: bool = True) -> str:
    """Render Qwen3's tool format, grouped tool responses, and no-thinking suffix."""
    if not request.messages:
        raise _error("Local Qwen requires at least one chat message")
    images = [image for message in request.messages for image in message.images]
    if images:
        if not request.model.startswith("qwen3.5-"):
            raise _error("Choose Qwen3.5 with its installed vision projection to read images")
        if any(
            message.images and message.role not in {Role.USER, Role.TOOL}
            for message in request.messages
        ):
            raise _error("Local Qwen images must be attached to a user or tool-result message")
        if enforce_size_limit and (
            len(images) > _MAX_IMAGES
            or sum(len(image.data) for image in images) > _MAX_IMAGES_BYTES
        ):
            raise _error(
                "Local Qwen accepts at most four images totaling 20 MiB across this request, "
                "including history and tool screenshots; start a new session for more images"
            )
    if request.model.startswith("qwen3.5-"):
        return _build_qwen35_prompt(request, enforce_size_limit=enforce_size_limit)
    parts: list[str] = []
    first_system = request.messages[0].role is Role.SYSTEM
    if request.tools:
        system = _chat_content(request.messages[0].provider_content()) if first_system else ""
        parts.append("<|im_start|>system\n" + (system + "\n\n" if system else ""))
        parts.append(
            "# Tools\n\nYou may call one or more functions to assist with the user query.\n\n"
            "You are provided with function signatures within <tools></tools> XML tags:\n<tools>"
        )
        for tool in request.tools:
            parts.append("\n" + _chat_content(_json(_local_tool(tool))))
        parts.append(
            "\n</tools>\n\nFor each function call, return a json object with function name "
            "and arguments within <tool_call></tool_call> XML tags:\n<tool_call>\n"
            '{"name": <function-name>, "arguments": <args-json-object>}\n'
            "</tool_call><|im_end|>\n"
        )
    elif first_system:
        parts.append(
            "<|im_start|>system\n"
            + _chat_content(request.messages[0].provider_content())
            + "<|im_end|>\n"
        )

    tool_group = False
    for index, message in enumerate(request.messages):
        if index == 0 and first_system:
            continue
        content = _chat_content(message.provider_content())
        if message.role is Role.TOOL:
            if not tool_group:
                parts.append("<|im_start|>user")
                tool_group = True
            parts.append("\n<tool_response>\n" + content + "\n</tool_response>")
            continue
        if tool_group:
            parts.append("<|im_end|>\n")
            tool_group = False
        if message.role is Role.ASSISTANT:
            # Historic chain of thought is omitted, matching the template's
            # behavior before the last user query and limiting phone memory.
            if "</think>" in content:
                content = content.rsplit("</think>", 1)[1].lstrip("\n")
            parts.append("<|im_start|>assistant\n" + content)
            for call in message.tool_calls:
                parts.append(
                    "\n<tool_call>\n"
                    + _chat_content(
                        _json(
                            {
                                "name": call.name,
                                "arguments": call.arguments,
                            }
                        )
                    )
                    + "\n</tool_call>"
                )
            parts.append("<|im_end|>\n")
        else:
            parts.append(f"<|im_start|>{message.role.value}\n{content}<|im_end|>\n")
    if tool_group:
        parts.append("<|im_end|>\n")
    parts.append("<|im_start|>assistant\n<think>\n\n</think>\n\n")
    prompt = "".join(parts)
    if enforce_size_limit and len(prompt.encode("utf-8")) > _MAX_PROMPT_BYTES:
        raise _error("Local Qwen prompt is too long for the phone", context_exceeded=True)
    return prompt


def _qwen35_tool_history(call: ToolCall) -> str:
    if not re.fullmatch(_XML_NAME, call.name):
        raise _error("Local Qwen3.5 tool call name cannot be encoded in its template")
    parts = [f"\n<tool_call>\n<function={call.name}>\n"]
    for name, value in call.arguments.items():
        if not re.fullmatch(_XML_NAME, name):
            raise _error("Local Qwen3.5 tool call parameter cannot be encoded in its template")
        if isinstance(value, (dict, list)):
            rendered = _json(value)
        elif isinstance(value, str):
            # Preserve the official raw-string format in ordinary histories. Only a
            # string holding the template's own tags needs JSON escapes to keep the
            # history well formed. Escaping every "<" taught a 2B model to write
            # "<" escapes into later HTML edits, so its patches never matched.
            rendered = (
                _json(value).replace("<", "\\u003c")
                if any(tag in value for tag in _TEMPLATE_TAGS)
                else value
            )
        elif value is None:
            rendered = "None"  # Qwen's Jinja string filter uses Python scalar spelling.
        elif type(value) is bool:
            rendered = str(value)
        else:
            rendered = _json(value)
        parts.append(f"<parameter={name}>\n{_chat_content(rendered)}\n</parameter>\n")
    parts.append("</function>\n</tool_call>")
    return "".join(parts)


def _build_qwen35_prompt(request: ProviderRequest, *, enforce_size_limit: bool = True) -> str:
    """Official Qwen3.5 text/tool template with mtmd media insertions."""
    if not any(message.role is Role.USER for message in request.messages):
        raise _error("Local Qwen3.5 requires a user query")
    # The official 3.5 template allows one initial system message. The shared
    # runner can supply several trusted system instructions, so combine them.
    system = "\n\n".join(
        _chat_content(message.provider_content()).strip()
        for message in request.messages
        if message.role is Role.SYSTEM
    )
    parts: list[str] = []
    if request.tools:
        parts.append(
            "<|im_start|>system\n# Tools\n\nYou have access to the following functions:\n\n<tools>"
        )
        for tool in request.tools:
            if not re.fullmatch(_XML_NAME, tool.name):
                raise _error("Local Qwen3.5 tool call name cannot be encoded in its template")
            parts.append("\n" + _chat_content(_json(_local_tool(tool))))
        parts.append(
            "\n</tools>\n\nIf you choose to call a function ONLY reply in the following format "
            "with NO suffix:\n\n<tool_call>\n<function=example_function_name>\n"
            "<parameter=example_parameter_1>\nvalue_1\n</parameter>\n"
            "<parameter=example_parameter_2>\nThis is the value for the second parameter\n"
            "that can span\nmultiple lines\n</parameter>\n</function>\n</tool_call>\n\n"
            "<IMPORTANT>\nReminder:\n"
            "- Function calls MUST follow the specified format: an inner <function=...></function> "
            "block must be nested within <tool_call></tool_call> XML tags\n"
            "- Required parameters MUST be specified\n"
            + _CALL_REASONING_RULE
            + "- If there is no function call available, answer the question like normal with "
            "your current knowledge and do not tell the user about function calls\n</IMPORTANT>"
        )
        parts.append(("\n\n" + system if system else "") + "<|im_end|>\n")
    elif system:
        parts.append("<|im_start|>system\n" + system + "<|im_end|>\n")
    last_user = max(
        index for index, message in enumerate(request.messages) if message.role is Role.USER
    )
    tool_group = False
    for index, message in enumerate(request.messages):
        if message.role is Role.SYSTEM:
            continue
        content = _chat_content(message.provider_content()).strip()
        if message.images:
            content += "\n" + "\n".join(_MEDIA_MARKER for _ in message.images)
        if message.role is Role.TOOL:
            if not tool_group:
                parts.append("<|im_start|>user")
                tool_group = True
            parts.append("\n<tool_response>\n" + content + "\n</tool_response>")
            continue
        if tool_group:
            parts.append("<|im_end|>\n")
            tool_group = False
        if message.role is Role.ASSISTANT:
            if "</think>" in content:
                content = content.rsplit("</think>", 1)[1].lstrip("\n")
            thought = "<think>\n\n</think>\n\n" if index > last_user else ""
            parts.append("<|im_start|>assistant\n" + thought + content)
            parts.extend(_qwen35_tool_history(call) for call in message.tool_calls)
            parts.append("<|im_end|>\n")
        else:
            parts.append(f"<|im_start|>user\n{content}<|im_end|>\n")
    if tool_group:
        parts.append("<|im_end|>\n")
    parts.append("<|im_start|>assistant\n<think>\n\n</think>\n\n")
    prompt = "".join(parts)
    if enforce_size_limit and len(prompt.encode("utf-8")) > _MAX_PROMPT_BYTES:
        raise _error("Local Qwen prompt is too long for the phone", context_exceeded=True)
    return prompt


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("non-finite JSON number")


def _decode(raw: str, label: str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (ValueError, TypeError, RecursionError):
        raise _error(f"Local Qwen returned an invalid {label}") from None


def _check_schema_refs(value: Any) -> None:
    if isinstance(value, dict):
        for name, child in value.items():
            if name in {"$ref", "$dynamicRef"} and (
                not isinstance(child, str) or not child.startswith("#")
            ):
                raise _error("Local Qwen tool call schema cannot resolve network references")
            _check_schema_refs(child)
    elif isinstance(value, list):
        for child in value:
            _check_schema_refs(child)


def _qwen35_parameter(raw: str, schema: dict[str, Any], property_schema: Any) -> Any:
    # Official XML parameters have one framing newline on each side. File
    # contents may contain further leading/trailing newlines of their own.
    # Choose the envelope's line ending before removing either boundary so an
    # LF envelope followed by content's trailing CR is never treated as CRLF.
    value = raw
    for newline in ("\r\n", "\n"):
        if raw.startswith(newline) and raw.endswith(newline) and len(raw) >= 2 * len(newline):
            value = raw[len(newline) : -len(newline)]
            break
    try:
        validator = Draft202012Validator(schema).evolve(schema=property_schema)
        # Nullable string parameters (such as a new-file preimage hash) also
        # accept literal strings. Decode the template's null spelling first,
        # while a string-only content/path parameter keeps the same text.
        if value.strip() in {"None", "null"} and validator.is_valid(None):
            return None
        # A quoted string with JSON escapes is how the history spells a string that
        # holds template tags, and small models copy that spelling for HTML. Decode it;
        # a plain quoted string without escapes keeps its quotes.
        literal = value.strip()
        if len(literal) >= 2 and literal[0] == literal[-1] == '"' and "\\" in literal:
            with contextlib.suppress(ValueError):
                decoded_text = json.loads(literal)
                if isinstance(decoded_text, str) and validator.is_valid(decoded_text):
                    return decoded_text
        if validator.is_valid(value):
            return value
        # Jinja renders Python bool/null scalars in prior calls; accept their
        # exact spellings alongside strict JSON when the schema requires them.
        scalar = {"True": True, "False": False, "None": None}
        decoded = scalar[value] if value in scalar else _decode(value, "tool call parameter")
        if not validator.is_valid(decoded):
            raise _error("Local Qwen3.5 tool call parameter has an invalid type")
        return decoded
    except ProviderError:
        raise
    except Exception:
        raise _error("Local Qwen3.5 tool call parameter schema is invalid") from None


def _parse_qwen35_call(raw: str, allowed: dict[str, Any]) -> dict[str, Any]:
    function = _FUNCTION_BLOCK.fullmatch(raw.strip())
    if function is None or function[1] not in allowed:
        raise _error("Local Qwen3.5 returned an invalid or unadvertised tool call")
    name, body = function[1], function[2]
    parameters = list(_PARAMETER_BLOCK.finditer(body))
    if _PARAMETER_BLOCK.sub("", body).strip():
        raise _error("Local Qwen3.5 returned malformed tool call parameters")
    schema = allowed[name].advertised_input_schema
    _check_schema_refs(schema)
    properties = schema.get("properties", {})
    arguments: dict[str, Any] = {}
    for parameter in parameters:
        key = parameter[1]
        if key in arguments:
            raise _error("Local Qwen3.5 returned duplicate tool call parameters")
        property_schema = properties.get(key, schema.get("additionalProperties", {}))
        if property_schema is False:
            raise _error("Local Qwen3.5 returned an unadvertised tool call parameter")
        if property_schema is True:
            property_schema = {}
        arguments[key] = _qwen35_parameter(parameter[2], schema, property_schema)
    return {"name": name, "arguments": arguments}


def _observed_digest(path: str, request: ProviderRequest) -> str | None:
    """The sha256 of `path` that the latest tool result in this conversation reported."""
    wanted = posixpath.normpath(path.replace("\\", "/"))
    for message in reversed(request.messages):
        if message.role is not Role.TOOL:
            continue
        try:
            result = json.loads(message.content)
        except ValueError:
            continue
        if not isinstance(result, dict):
            continue
        reported, digest = result.get("path"), result.get("sha256")
        if (
            isinstance(reported, str)
            and isinstance(digest, str)
            and _SHA256.fullmatch(digest)
            and posixpath.normpath(reported.replace("\\", "/")) == wanted
        ):
            return digest.lower()
    return None


def _repair_digest(
    arguments: dict[str, Any], schema: dict[str, Any], request: ProviderRequest
) -> dict[str, Any]:
    """Fix the preimage digest of a file write that small models get wrong.

    A 2B model loses whole generated files here: it invents a digest for a new file,
    or after reading a file it passes null or mis-copies the 64 hex digits. When this
    conversation read or wrote the same path, use the digest it observed then; the
    tool still rejects the write if the file changed since, so nothing is overwritten
    blind. Otherwise an invented digest for a nullable field means a new file, which
    the tool accepts only while no such file exists.
    """
    digest_schema = schema.get("properties", {}).get("expected_sha256")
    path = arguments.get("path")
    digest = arguments.get("expected_sha256")
    if (
        digest_schema is None
        or not isinstance(path, str)
        or not isinstance(digest, (str, type(None)))
    ):
        return arguments
    observed = _observed_digest(path, request)
    if observed is not None:
        return {**arguments, "expected_sha256": observed}
    if not isinstance(digest, str) or not Draft202012Validator(digest_schema).is_valid(None):
        return arguments
    # Copying a file, small models pass the source's digest for a destination this conversation
    # never observed. Read as a new file, which the tool refuses if the destination exists.
    if _digest_paths(digest, request) - {posixpath.normpath(path.replace("\\", "/"))}:
        return {**arguments, "expected_sha256": None}
    # A digest some successful tool result reported (not an error message quoting it) is real.
    if any(digest.lower() in message.content.lower() for message in _json_results(request)):
        return arguments
    return {**arguments, "expected_sha256": None}


def _digest_paths(digest: str, request: ProviderRequest) -> set[str]:
    """Paths whose sha256 a tool result reported as exactly this digest."""
    paths = set()
    for message in _json_results(request):
        result = json.loads(message.content)
        if (
            isinstance(result, dict)
            and isinstance(result.get("path"), str)
            and isinstance(result.get("sha256"), str)
            and result["sha256"].lower() == digest.lower()
        ):
            paths.add(posixpath.normpath(result["path"].replace("\\", "/")))
    return paths


def _json_results(request: ProviderRequest) -> list[Any]:
    results = []
    for message in request.messages:
        if message.role is not Role.TOOL:
            continue
        try:
            json.loads(message.content)
        except ValueError:
            continue
        results.append(message)
    return results


_PATH_ARGUMENTS = ("path", "source", "destination")
# Repeating one of these right after it succeeded can only give the same result.
_REPEAT_GUARDED_EFFECTS = frozenset({"read", "write", "mkdir"})
_FAILED_RESULT = (
    "Tool failed",
    "Tool rejected",
    "Tool call rejected",
    "Tool is unavailable",
    "Unknown tool",
    "Tool capability is unavailable",
    "Tool did not settle",
    "Tool execution was cancelled",
)


def _just_succeeded(name: str, arguments: dict[str, Any], request: ProviderRequest) -> bool:
    """Whether the model's previous step made this exact call and it succeeded.

    A 0.8B model created a folder, then proposed the same make_directory eleven more times
    until its step budget ran out, never writing the file it was asked for.
    """
    results: dict[str, str] = {}
    previous: tuple[ToolCall, ...] = ()
    for message in reversed(request.messages):
        if message.role is Role.TOOL:
            if message.tool_call_id is not None:
                results[message.tool_call_id] = message.content
            continue
        if message.role is Role.ASSISTANT:
            previous = tuple(message.tool_calls)
        break
    for call in previous:
        if call.name == name and call.arguments == arguments:
            content = results.get(call.id, "")
            if content.startswith("[UNTRUSTED TOOL DATA"):
                content = content.split("\n", 1)[-1]
            return bool(content) and not content.startswith(_FAILED_RESULT)
    return False


def _workspace_relative(arguments: dict[str, Any], root: Path | None) -> dict[str, Any]:
    """Map "/todo.md" or "/workspace/todo.md" to "todo.md".

    A 0.8B model treats the workspace as the file system root and lost whole tasks to
    "path is outside workspace". A real absolute path inside the workspace is left alone.
    """
    if root is None:
        return arguments
    fixed = dict(arguments)
    base = root.as_posix().rstrip("/")
    for key in _PATH_ARGUMENTS:
        value = arguments.get(key)
        if not isinstance(value, str) or not value.startswith(("/", "\\")):
            continue
        normalized = value.replace("\\", "/")
        if normalized == base or normalized.startswith(base + "/"):
            continue
        relative = normalized.lstrip("/")
        if relative == root.name or relative.startswith(root.name + "/"):
            relative = relative[len(root.name) :].lstrip("/")
        if ".." not in relative.split("/"):
            fixed[key] = relative or "."
    return fixed


def _callable_tools(request: ProviderRequest) -> dict[str, Any]:
    """The advertised tools plus the everyday ones that may be called without selection."""
    advertised = frozenset(tool.name for tool in request.tools)
    hidden = hidden_tools.get()
    return {
        **(hidden[1] if hidden is not None and hidden[0] == advertised else {}),
        **{tool.name: tool for tool in request.tools},
    }


def tool_grammar(request: ProviderRequest) -> str:
    """A lazy GBNF grammar for this request's tool calls, or "" when there are none."""
    from .local_grammar import enabled, tool_call_grammar

    if not request.tools or not enabled():
        return ""
    tools = [
        (name, _local_tool(tool)["function"]["parameters"])
        for name, tool in _callable_tools(request).items()
    ]
    return tool_call_grammar(tools, qwen35=request.model.startswith("qwen3.5-"))


def parse_qwen_output(
    text: str,
    request: ProviderRequest,
    request_id: str,
    *,
    workspace_root: Path | None = None,
) -> list[ProviderDelta]:
    """Validate every proposal before returning any text or executable tool delta."""
    if len(text.encode("utf-8")) > _MAX_RESPONSE_BYTES:
        raise _error("Local Qwen response exceeded the phone response limit")
    reasoning = ""
    if text.lstrip().startswith("<think>"):
        thought = text.lstrip()[len("<think>") :]
        if "</think>" not in thought:
            # A generation budget can end within thinking. This remains reasoning
            # only and cannot turn a partial tool block into an executable call.
            return [ProviderDelta(DeltaKind.REASONING, text=thought)] if thought else []
        reasoning, text = thought.split("</think>", 1)
        text = text.lstrip("\n")
    matches = list(_TOOL_BLOCK.finditer(text))
    remaining = _TOOL_BLOCK.sub("", text)
    if "<tool_call>" in remaining or "</tool_call>" in remaining:
        raise _error("Local Qwen returned an incomplete tool call")
    if len(matches) > _MAX_TOOL_CALLS:
        raise _error("Local Qwen returned too many tool calls")
    advertised = frozenset(tool.name for tool in request.tools)
    allowed = _callable_tools(request)
    qwen35 = request.model.startswith("qwen3.5-")
    if qwen35 and matches and text[matches[-1].end() :].strip():
        raise _call_error(
            "Local Qwen3.5 tool call must not contain a trailing suffix",
            matches[-1][1],
            allowed,
            qwen35,
            advertised,
        )
    calls: list[ToolCall] = []
    for index, match in enumerate(matches):
        raw = match[1]
        if len(raw.encode("utf-8")) > _MAX_TOOL_CALL_BYTES:
            raise _error("Local Qwen tool call arguments exceeded the phone limit")
        try:
            call = _parse_qwen35_call(raw, allowed) if qwen35 else _decode(raw, "tool call")
            if not isinstance(call, dict) or set(call) != {"name", "arguments"}:
                raise _error("Local Qwen returned an invalid tool call object")
            name, arguments = call["name"], call["arguments"]
            if not isinstance(name, str) or name not in allowed or not isinstance(arguments, dict):
                raise _error("Local Qwen returned an unadvertised or invalid tool call")
            schema = allowed[name].advertised_input_schema
            try:
                _check_schema_refs(schema)
                Draft202012Validator.check_schema(schema)
                Draft202012Validator(schema).validate(arguments)
            except (SchemaError, ValidationError, RecursionError):
                raise _error(
                    "Local Qwen tool call arguments do not match the advertised schema"
                ) from None
        except ProviderError as error:
            # Still never executed; the error now says what to fix for a bounded retry.
            raise _call_error(str(error), raw, allowed, qwen35, advertised) from None
        arguments = _repair_digest(_workspace_relative(arguments, workspace_root), schema, request)
        if allowed[name].side_effect in _REPEAT_GUARDED_EFFECTS and _just_succeeded(
            name, arguments, request
        ):
            raise _call_error(
                f'"{name}" just ran with these same arguments and succeeded; its result is '
                "above. Do not repeat it: do the next step of the task, or answer if it is done",
                raw,
                allowed,
                qwen35,
                advertised,
            )
        digest = hashlib.sha256((request_id + str(index) + _json(call)).encode()).hexdigest()[:24]
        calls.append(ToolCall("local_" + digest, name, arguments))
    deltas: list[ProviderDelta] = []
    if reasoning.strip():
        deltas.append(ProviderDelta(DeltaKind.REASONING, text=reasoning.strip()))
    if remaining.strip():
        deltas.append(ProviderDelta(DeltaKind.TEXT, text=remaining.strip()))
    deltas.extend(ProviderDelta(DeltaKind.TOOL_CALL, tool_call=call) for call in calls)
    return deltas


def android_bridge() -> Any:
    global _bridge
    if _bridge is None:
        try:
            from java import jclass

            _bridge = jclass("com.agentworkspace.mobile.localmodels.LocalModelBridge")
        except Exception:
            raise _error(
                "Local Qwen native engine is unavailable on this Android runtime"
            ) from None
    return _bridge


def _bounded_integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be an integer from {minimum} to {maximum}")
    return value


def _planned_context_size(plan: Any, model_id: str, configured_tokens: int) -> int | None:
    """Only a structured allocation shortage may defer provider initialization."""
    if not isinstance(plan, dict):
        raise _error("Local Qwen returned an invalid context plan")
    if "error" in plan:
        error = plan["error"]
        if (
            not isinstance(error, dict)
            or not isinstance(error.get("code"), str)
            or not error["code"]
            or not isinstance(error.get("message"), str)
            or not error["message"].strip()
        ):
            raise _error("Local Qwen returned an invalid context planning error")
        if error["code"] == "insufficient_memory":
            return None
        raise _error(error["message"][:500])
    context = plan.get("context_size")
    maximum = 262144 if model_id.startswith("qwen3.5-") else 32768
    installed_maximum = plan.get("model_max_context_tokens", maximum)
    if (
        type(installed_maximum) is not int
        or not 512 <= installed_maximum <= maximum
        or type(context) is not int
        or not 512 <= context <= installed_maximum
        or (configured_tokens > 0 and context != configured_tokens)
        or ("feasible" in plan and type(plan["feasible"]) is not bool)
        or (configured_tokens == 0 and plan.get("feasible") is False)
    ):
        raise _error("Local Qwen returned an invalid context plan")
    return context


class EmbeddedQwenProvider:
    def __init__(
        self,
        provider_id: str,
        *,
        bridge: Any = None,
        model_root: Path | None = None,
        model_resolver: Callable[[str], Path] | None = None,
        projection_resolver: Callable[[str], Path] | None = None,
        context_size: int = 4096,
        memory_mode: str = "balanced",
        threads: int | None = None,
        generation_timeout_seconds: int = 0,
    ) -> None:
        self._id = provider_id
        self._bridge = bridge
        self._model_root = model_root
        self._model_resolver = model_resolver
        self._projection_resolver = projection_resolver
        self._context_size = _bounded_integer(context_size, "context size", 512, 262144)
        if memory_mode not in {"balanced", "extended"}:
            raise ValueError("memory mode must be balanced or extended")
        self._memory_mode = memory_mode
        self._configured_context_tokens = context_size
        self._context_plan: dict[str, Any] | None = None
        self._context_plan_pending = False
        self._context_plan_model_id: str | None = None
        self._context_plan_failure: dict[str, str] | None = None
        self._threads = _bounded_integer(
            min(4, os.cpu_count() or 1) if threads is None else threads,
            "threads",
            1,
            64,
        )
        self._generation_timeout_seconds = _bounded_integer(
            generation_timeout_seconds, "generation timeout seconds", 0, 7200
        )
        self._token_measurement_cache: tuple[tuple[str, str, int, int], dict[str, Any]] | None = (
            None
        )
        self._closed = False
        # Set by the local context profile; lets the parser repair root-relative paths.
        self._workspace_root: Path | None = None
        self._inflight_id: str | None = None
        self._generation_acquired = False
        self._stream_task: asyncio.Task[Any] | None = None

    @property
    def id(self) -> str:
        return self._id

    @property
    def reasoning_protocol(self) -> None:
        return None

    @property
    def context_plan_ready(self) -> bool:
        return not self._context_plan_pending

    @property
    def context_plan_error(self) -> dict[str, str] | None:
        if self.context_plan_ready:
            return None
        if self._context_plan_failure is not None:
            return dict(self._context_plan_failure)
        error = (self._context_plan or {}).get("error", {})
        return {
            "code": error.get("code", "context_plan_failed"),
            "message": error.get("message", "Local Qwen context planning failed")[:500],
        }

    def ensure_context_plan_ready(
        self, model_id: str, *, retry: bool = True, raise_on_error: bool = True
    ) -> bool:
        """Retry a deferred plan before budgets, keeping healthy turn capacity stable."""
        if self.context_plan_ready:
            return True
        if retry:
            try:
                if model_id != self._context_plan_model_id:
                    raise _error("Local Qwen deferred context belongs to another model")
                bridge = self._bridge if self._bridge is not None else android_bridge()
                self._bridge = bridge
                plan = _decode(
                    str(
                        bridge.contextPlan(
                            model_id, self._configured_context_tokens, self._memory_mode
                        )
                    ),
                    "context plan",
                )
                context = _planned_context_size(plan, model_id, self._configured_context_tokens)
                self._context_plan = plan
                self._context_plan_failure = None
                if context is not None:
                    self._context_size = context
                    self._context_plan_pending = False
                    self._token_measurement_cache = None
            except ProviderError as failure:
                self._context_plan_failure = {
                    "code": "context_plan_failed",
                    "message": str(failure)[:500],
                }
            except Exception:
                self._context_plan_failure = {
                    "code": "context_plan_failed",
                    "message": "Local Qwen context planning failed",
                }
        if self._context_plan_pending and raise_on_error:
            error = self.context_plan_error
            raise _error(
                error["message"] if error is not None else "Local Qwen context is unavailable"
            )
        return self.context_plan_ready

    def _expected_model_path(self, model_id: str) -> Path:
        if model_id not in SUPPORTED_MODELS:
            raise _error("Select an installed, supported small Qwen model")
        root = self._model_root
        if root is None:
            data = os.environ.get("AGENT_WORKSPACE_DATA_DIR")
            if not data:
                raise _error("Local Qwen private model directory is not configured")
            root = Path(data) / "local-models"
        return root.resolve() / model_id / "model.gguf"

    def _installed_path(self, model_id: str) -> Path:
        expected = self._expected_model_path(model_id)
        root = expected.parent.parent
        try:
            if self._model_resolver is not None:
                path = Path(self._model_resolver(model_id))
            else:
                from mobile_model_manager import get_model_manager

                path = get_model_manager(root).installed_path(model_id)
            if path.is_symlink() or path.parent.is_symlink() or path.resolve() != expected:
                raise _error("Local Qwen model path escaped the private model directory")
            with path.open("rb") as stream:
                if stream.read(4) != b"GGUF":
                    raise _error("Local Qwen model file is not a valid GGUF")
            return path.resolve()
        except ProviderError:
            raise
        except (OSError, ValueError, KeyError):
            raise _error(
                "Local Qwen model is not installed or failed integrity validation"
            ) from None

    def _expected_projection_path(self, model_id: str) -> Path:
        if not model_id.startswith("qwen3.5-"):
            raise _error("Choose Qwen3.5 with its installed vision projection to read images")
        family = "2b" if model_id.startswith("qwen3.5-2b-") else "0.8b"
        root = self._expected_model_path(model_id).parent.parent
        return root / f"qwen3.5-{family}-vision-f16" / "model.gguf"

    def _installed_projection_path(self, model_id: str) -> Path:
        expected = self._expected_projection_path(model_id)
        try:
            if self._projection_resolver is not None:
                path = Path(self._projection_resolver(model_id))
            else:
                from mobile_model_manager import get_model_manager

                path = get_model_manager(expected.parent.parent).installed_projection_path(model_id)
            if path.is_symlink() or path.parent.is_symlink() or path.resolve() != expected:
                raise _error("Local Qwen vision projection path escaped private model storage")
            with path.open("rb") as stream:
                if stream.read(4) != b"GGUF":
                    raise _error("Local Qwen vision projection is not a valid GGUF")
            return path.resolve()
        except ProviderError:
            raise
        except (OSError, ValueError, KeyError):
            raise _error(
                "Install and verify the matching local Qwen vision projection to read images"
            ) from None

    def _request_body(
        self, request: ProviderRequest, request_id: str, *, verify_model: bool = True
    ) -> dict[str, Any]:
        maximum = (
            request.max_output_tokens
            if request.max_output_tokens is not None
            else min(4096, max(256, self._context_size // 4))
        )
        if type(maximum) is not int or maximum <= 0:
            raise _error("Local Qwen output budget must be a positive integer")
        model_limit = 262144 if request.model.startswith("qwen3.5-") else 32768
        if self._context_size > model_limit:
            raise _error("Selected local context exceeds this model's supported context")
        temperature = request.temperature if request.temperature is not None else 0.7
        if (
            type(temperature) not in {int, float}
            or not math.isfinite(temperature)
            or not 0 <= temperature <= 2
        ):
            raise _error("Local Qwen temperature must be a finite number from 0 to 2")
        body = {
            "version": 1,
            "request_id": request_id,
            "model_id": request.model,
            "model_path": str(
                self._installed_path(request.model)
                if verify_model
                else self._expected_model_path(request.model)
            ),
            # Budget encoding must measure large old histories before the
            # runner compacts them. Only generation crosses the JNI size gate.
            "prompt": build_qwen_prompt(request, enforce_size_limit=verify_model),
            "context_size": self._context_size,
            "max_output_tokens": min(maximum, 8192, self._context_size // 2),
            "memory_mode": self._memory_mode,
            "threads": self._threads,
            "temperature": temperature,
            "generation_timeout_ms": 180_000,
        }
        # Slow CPUs may need several minutes to emit a complete code tool call.
        # Include startup time and 150 ms per reserved output token, while
        # retaining a finite cap and the runner's caller-selected turn budget.
        body["generation_timeout_ms"] = (
            self._generation_timeout_seconds * 1000
            if self._generation_timeout_seconds
            else min(900_000, max(180_000, 60_000 + body["max_output_tokens"] * 150))
        )
        if verify_model:
            # Generation only: budgeting measures the prompt, which the grammar is not part of.
            grammar = tool_grammar(request)
            if grammar:
                body["tool_grammar"] = grammar
        images = [image for message in request.messages for image in message.images]
        if images:
            body["projection_path"] = str(
                self._installed_projection_path(request.model)
                if verify_model
                else self._expected_projection_path(request.model)
            )
            if verify_model:
                body["encoded_images"] = [
                    {"media_type": image.media_type, "base64": image.base64} for image in images
                ]
            else:
                # Wire-byte budgeting must reserve visual tokens without
                # counting encoded file bytes as text tokens. JNI counts the
                # actual text and image chunks before allocating the context.
                body["image_token_reserve"] = "x" * (
                    len(images) * _IMAGE_TOKEN_RESERVE * context_units_per_token()
                )
        return body

    def encode_request(self, request: ProviderRequest) -> bytes:
        # The runner uses this synchronously for repeated budget calculations.
        # Verify large weight files only in the generation worker.
        return _json(self._request_body(request, "trace", verify_model=False)).encode("utf-8")

    def measure_context_tokens(self, request: ProviderRequest) -> dict[str, Any]:
        """Measure the rendered prompt; image and JSON transport are not text tokens."""
        prompt = build_qwen_prompt(request, enforce_size_limit=False)
        prompt_utf8 = prompt.encode("utf-8")
        image_reserve = (
            sum(len(message.images) for message in request.messages) * _IMAGE_TOKEN_RESERVE
        )
        unit_size = context_units_per_token()
        key = (request.model, hashlib.sha256(prompt_utf8).hexdigest(), image_reserve, unit_size)
        if self._token_measurement_cache is not None and self._token_measurement_cache[0] == key:
            return dict(self._token_measurement_cache[1])
        measurement = {
            "text_tokens": (len(prompt_utf8) + unit_size - 1) // unit_size,
            "image_token_reserve": image_reserve,
            "native_counted": False,
            "count_source": "utf8_estimate_without_native_tokenizer",
        }
        if len(prompt_utf8) > _MAX_TOKENIZER_PROMPT_BYTES:
            measurement["count_source"] = "utf8_estimate_above_tokenizer_transport_guard"
        elif _generation_gate is not None and _generation_gate.locked():
            measurement["count_source"] = "utf8_estimate_native_engine_busy"
        else:
            try:
                bridge = self._bridge if self._bridge is not None else android_bridge()
                count = getattr(bridge, "countPromptTokens", None)
                if count is not None:
                    result = _decode(str(count(request.model, prompt)), "tokenizer response")
                    if (
                        isinstance(result, dict)
                        and not isinstance(result.get("error"), dict)
                        and type(result.get("prompt_tokens")) is int
                        and 0 <= result["prompt_tokens"] <= len(prompt_utf8) + 1
                        and result.get("includes_image_tokens") is False
                        and result.get("count_source") == "installed_gguf_vocabulary"
                    ):
                        measurement["text_tokens"] = result["prompt_tokens"]
                        measurement["native_counted"] = True
                        measurement["count_source"] = result["count_source"]
                    else:
                        measurement["count_source"] = "utf8_estimate_native_tokenizer_unavailable"
            except Exception:
                # The estimate is explicitly labelled. Native tokenization
                # still validates the final compacted request on generation.
                pass
        measurement["context_units"] = (measurement["text_tokens"] + image_reserve) * unit_size
        if measurement["native_counted"]:
            self._token_measurement_cache = (key, dict(measurement))
        return measurement

    async def __aenter__(self) -> EmbeddedQwenProvider:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    def _cancel(self, request_id: str) -> None:
        if self._bridge is not None:
            # A close/cancel must not interrupt another session using the engine.
            with contextlib.suppress(Exception):
                self._bridge.cancelRequest(request_id)

    async def aclose(self) -> None:
        self._closed = True
        if self._inflight_id is not None and self._generation_acquired:
            self._cancel(self._inflight_id)
        elif self._stream_task is not None and self._stream_task is not asyncio.current_task():
            # A queued stream has no native request to cancel yet. Cancel only
            # that provider's waiter so the active session keeps the engine.
            self._stream_task.cancel()

    async def stream_with_attempts(
        self,
        request: ProviderRequest,
        attempt_started: Callable[[int], Awaitable[None]],
    ) -> AsyncIterator[ProviderDelta]:
        await attempt_started(1)
        async for delta in self.stream(request):
            yield delta

    async def stream(self, request: ProviderRequest) -> AsyncIterator[ProviderDelta]:
        if self._closed:
            raise _error("Local Qwen provider is closed")
        if self._inflight_id is not None:
            raise _error("Local Qwen provider is already generating")
        self.ensure_context_plan_ready(request.model)
        request_id = uuid.uuid4().hex
        bridge = self._bridge if self._bridge is not None else android_bridge()
        self._bridge = bridge
        gate = _local_generation_gate()
        self._inflight_id = request_id
        self._stream_task = asyncio.current_task()
        gate_acquired = False
        native_task: asyncio.Task[tuple[Any, int]] | None = None
        loop = asyncio.get_running_loop()

        try:
            body = await asyncio.to_thread(self._request_body, request, request_id)
            budget_seconds = body["generation_timeout_ms"] / 1000
            recommendation = (self._context_plan or {}).get("recommended_timeout_seconds")
            if (
                not self._generation_timeout_seconds
                and type(recommendation) is int
                and 180 <= recommendation <= 7200
            ):
                budget_seconds = max(budget_seconds, recommendation)
            elif not self._generation_timeout_seconds:
                budget_seconds = max(
                    budget_seconds,
                    min(7200, math.ceil(60 + 1.5 * (max(4096, self._context_size) / 16 + 614.4))),
                )
            deadline = loop.time() + budget_seconds
            try:
                await asyncio.wait_for(gate.acquire(), timeout=max(0.001, deadline - loop.time()))
            except TimeoutError:
                raise _error(
                    f"Local Qwen generation queue timed out after {budget_seconds:g} seconds; "
                    "finish another local task or increase the local timeout setting"
                ) from None
            gate_acquired = True
            self._generation_acquired = True
            remaining_ms = max(1, int((deadline - loop.time()) * 1000))

            def generate_with_deadline() -> tuple[Any, int]:
                body["generation_timeout_ms"] = min(body["generation_timeout_ms"], remaining_ms)
                return bridge.generate(_json(body)), body["max_output_tokens"]

            native_task = asyncio.create_task(asyncio.to_thread(generate_with_deadline))
            try:
                # Kotlin also derives its native timeout. This outer budget
                # includes queue time even if JNI replaces the remaining limit.
                completion, output_allowance = await asyncio.wait_for(
                    asyncio.shield(native_task), max(0.001, deadline - loop.time())
                )
            except TimeoutError:
                self._cancel(request_id)
                with contextlib.suppress(Exception, asyncio.CancelledError):
                    await asyncio.wait_for(asyncio.shield(native_task), _CANCEL_SETTLE_SECONDS)
                raise _error(
                    f"Local Qwen generation timed out after {budget_seconds:g} seconds "
                    "including queue time; increase the local timeout setting"
                ) from None
            raw = str(completion)
        except asyncio.CancelledError:
            if gate_acquired:
                self._cancel(request_id)
                if native_task is not None:
                    with contextlib.suppress(Exception, asyncio.CancelledError):
                        await asyncio.wait_for(asyncio.shield(native_task), _CANCEL_SETTLE_SECONDS)
            raise
        except ProviderError:
            raise
        except Exception:
            raise _error("Local Qwen native generation failed") from None
        finally:
            if gate_acquired:

                def release_generation(completed: asyncio.Task[tuple[Any, int]] | None) -> None:
                    if completed is not None and not completed.cancelled():
                        completed.exception()
                    gate.release()

                # The native worker may need more time to abort. Its gate stays
                # owned until it actually exits so the next session cannot race it.
                if native_task is not None and not native_task.done():
                    native_task.add_done_callback(release_generation)
                else:
                    release_generation(native_task)
            self._generation_acquired = False
            self._inflight_id = None
            self._stream_task = None
        if len(raw.encode("utf-8")) > _MAX_RESPONSE_BYTES:
            raise _error("Local Qwen response exceeded the phone response limit")
        response = _decode(raw, "native response")
        if not isinstance(response, dict):
            raise _error("Local Qwen returned an invalid native response")
        error = response.get("error")
        if isinstance(error, dict):
            # Native timeouts may include measured work already performed.
            # Reject invented counts and never release unfinished text/tools.
            counts = [response.get("prompt_tokens"), response.get("generated_tokens")]
            if all(type(value) is int and value >= 0 for value in counts):
                if (
                    counts[0] > self._context_size
                    or counts[1] > output_allowance
                    or sum(counts) > self._context_size
                ):
                    raise _error("Local Qwen returned invalid token counts")
                yield ProviderDelta(
                    DeltaKind.USAGE,
                    usage=Usage(*counts),
                    provider_metadata={
                        key: response[key]
                        for key in _TIMING_KEYS
                        if type(response.get(key)) in {int, float} and math.isfinite(response[key])
                    },
                )
            message = error.get("message", "Local Qwen engine error")
            message = message[:500] if isinstance(message, str) else "Local Qwen engine error"
            raise _error(message, context_exceeded=error.get("code") == "context_exceeded")
        if response.get("cancelled") is True:
            raise asyncio.CancelledError
        text = response.get("text")
        finish = response.get("finish_reason")
        if not isinstance(text, str) or finish not in {"stop", "length"}:
            raise _error("Local Qwen returned an invalid completion")
        counts = [response.get("prompt_tokens"), response.get("generated_tokens")]
        if (
            any(type(value) is not int or value < 0 for value in counts)
            or counts[0] > self._context_size
            or counts[1] > output_allowance
            or sum(counts) > self._context_size
        ):
            raise _error("Local Qwen returned invalid token counts")
        metadata = {
            key: response[key]
            for key in _TIMING_KEYS
            if type(response.get(key)) in {int, float} and math.isfinite(response[key])
        }
        try:
            deltas = parse_qwen_output(
                text, request, request_id, workspace_root=self._workspace_root
            )
        except ProviderError as error:
            # Parsing is atomic: no partial text or executable proposal escapes.
            # The actual CPU generation still consumed tokens, including failures.
            yield ProviderDelta(DeltaKind.USAGE, usage=Usage(*counts), provider_metadata=metadata)
            if getattr(error, "tool_call_rejected", False):
                # An invented tool or a broken call format: ask the model again (bounded).
                error.retryable = True
                error.incomplete_tool_call = True
                raise error from None
            if "incomplete tool call" in str(error):
                if finish == "length":
                    error = _error(
                        f"Local Qwen tool call was truncated at the {counts[1]}-token "
                        "output limit; use a larger local context/output budget "
                        "or generate the file in smaller steps"
                    )
                error.retryable = True
                error.incomplete_tool_call = True
                raise error from None
            raise
        for delta in deltas:
            yield delta
        yield ProviderDelta(DeltaKind.USAGE, usage=Usage(*counts), provider_metadata=metadata)
        yield ProviderDelta(
            DeltaKind.FINISH,
            finish_reason="tool_calls"
            if any(d.kind is DeltaKind.TOOL_CALL for d in deltas)
            else finish,
        )


def install_local_provider_factory() -> None:
    """Patch the Android process only, including already-imported factory aliases."""
    from agent_workspace import providers
    from agent_workspace.providers import factory

    original = factory.create_provider
    if getattr(original, "_android_embedded_qwen", False):
        return

    def create(config: ProviderConfig, **kwargs: Any) -> Any:
        if config.base_url.rstrip("/") == EMBEDDED_BASE_URL:
            config.validate()
            if config.protocol is not ProviderProtocol.OPENAI_COMPATIBLE:
                raise _error("The embedded Qwen endpoint requires openai-compatible protocol")
            if config.model not in SUPPORTED_MODELS:
                raise _error("Select an installed, supported small Qwen model")
            configured = os.getenv("AGENT_WORKSPACE_LOCAL_CONTEXT_TOKENS", "0")
            if not configured.isdecimal():
                raise _error("Invalid local context setting")
            requested = int(configured)
            model_maximum = 262144 if config.model.startswith("qwen3.5-") else 32768
            if requested != 0 and not 512 <= requested <= model_maximum:
                raise _error("Unsupported local context setting")
            memory_mode = os.getenv("AGENT_WORKSPACE_LOCAL_MEMORY_MODE", "balanced")
            if memory_mode not in {"balanced", "extended"}:
                raise _error("Unsupported local memory mode")

            def performance_setting(name: str, maximum: int) -> int:
                raw = os.getenv(name, "0")
                if not raw.isdecimal() or not 0 <= int(raw) <= maximum:
                    raise _error("Invalid local performance setting")
                return int(raw)

            threads = performance_setting("AGENT_WORKSPACE_LOCAL_THREADS", 64)
            timeout = performance_setting("AGENT_WORKSPACE_LOCAL_TIMEOUT_SECONDS", 7200)
            bridge = None
            plan = None
            context = requested or 8192
            pending = False
            if os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") == "chaquopy":
                bridge = android_bridge()
                plan = _decode(
                    str(bridge.contextPlan(config.model, requested, memory_mode)), "context plan"
                )
                planned = _planned_context_size(plan, config.model, requested)
                pending = planned is None
                # This capacity is only an internal placeholder. Pending plans
                # cannot derive turn budgets, compact history, or generate.
                context = planned if planned is not None else requested or model_maximum
            provider = EmbeddedQwenProvider(
                config.id,
                bridge=bridge,
                context_size=context,
                memory_mode=memory_mode,
                threads=threads or None,
                generation_timeout_seconds=timeout,
            )
            provider._configured_context_tokens = requested
            provider._context_plan = plan
            provider._context_plan_pending = pending
            provider._context_plan_model_id = config.model
            return provider
        return original(config, **kwargs)

    create._android_embedded_qwen = True
    factory.create_provider = create
    providers.create_provider = create
    for name, module in tuple(sys.modules.items()):
        if (
            name.startswith("agent_workspace.")
            and module is not None
            and getattr(module, "create_provider", None) is original
        ):
            module.create_provider = create
