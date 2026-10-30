"""The code editor's model calls: rewriting the selected code as the user asks (Ctrl+K), and
completing at the cursor from the code around it (DeepSeek's fill-in-the-middle endpoint)."""

from __future__ import annotations

import asyncio
import contextlib
import re
from urllib.parse import urlparse

import httpx

from agent_workspace.config import ProviderConfig
from agent_workspace.core.models import ChatMessage, DeltaKind, ProviderRequest, Role
from agent_workspace.providers import create_provider

MAX_SELECTION = 20_000
MAX_BEFORE = 6_000
MAX_AFTER = 3_000
MAX_INSTRUCTION = 2_000
REWRITE_SECONDS = 120
COMPLETE_SECONDS = 8.0
_COMPLETE_LINES = 8

_REWRITE_SYSTEM = (
    "You edit one part of a source file. You get the code before the selection, the selected "
    "code, the code after it, and the user's instruction. Return only the code that replaces "
    "the selection: in the file's language and style, indented as it sits in the file, "
    "complete and working with the code around it. No explanation and no Markdown fences. "
    "When the selection is empty, return the code to insert at that point."
)


class EditorAiError(RuntimeError):
    pass


def _strip_fences(text: str) -> str:
    stripped = text.strip("\n")
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[0].lstrip().startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1])
    stripped = re.sub(r"^\s*<selection>\n?", "", stripped)
    return re.sub(r"\n?</selection>\s*$", "", stripped)


def rewrite_selection(
    config: ProviderConfig,
    *,
    path: str,
    language: str,
    before: str,
    selection: str,
    after: str,
    instruction: str,
) -> str:
    request = ProviderRequest(
        model=config.model,
        messages=(
            ChatMessage(role=Role.SYSTEM, content=_REWRITE_SYSTEM),
            ChatMessage(
                role=Role.USER,
                content=(
                    f"File: {path} ({language or 'plain text'})\n\n"
                    f"<before>\n{before[-MAX_BEFORE:]}</before>\n"
                    f"<selection>\n{selection[:MAX_SELECTION]}</selection>\n"
                    f"<after>\n{after[:MAX_AFTER]}</after>\n\n"
                    f"Instruction: {instruction[:MAX_INSTRUCTION]}"
                ),
            ),
        ),
        max_output_tokens=8192,
        temperature=0.2,
    )

    async def stream() -> str:
        provider = create_provider(config)
        chunks: list[str] = []
        try:
            async for delta in provider.stream(request):
                if delta.kind is DeltaKind.TEXT and delta.text:
                    chunks.append(delta.text)
        finally:
            if hasattr(provider, "aclose"):
                with contextlib.suppress(Exception):
                    await provider.aclose()
        return "".join(chunks)

    try:
        answer = asyncio.run(asyncio.wait_for(stream(), REWRITE_SECONDS))
    except TimeoutError:
        raise EditorAiError("editor_timeout") from None
    except Exception:
        raise EditorAiError("editor_failed") from None
    answer = _strip_fences(answer)
    if not answer.strip() and selection.strip():
        raise EditorAiError("editor_empty")
    return answer


def completion_available(config: ProviderConfig | None) -> bool:
    """Fill-in-the-middle needs DeepSeek's own API (its beta completions endpoint)."""
    if config is None or not config.api_key:
        return False
    host = urlparse(config.base_url).hostname or ""
    return host == "api.deepseek.com" or host.endswith(".deepseek.com")


def _trim_completion(text: str, suffix: str) -> str:
    lines = text.split("\n")
    text = "\n".join(lines[:_COMPLETE_LINES])
    # The model sometimes writes on into what already follows the cursor.
    head = suffix.lstrip()[:40]
    if head and head in text:
        text = text[: text.index(head)]
    return text.rstrip() if "\n" in text else text


def complete_at_cursor(
    config: ProviderConfig,
    prefix: str,
    suffix: str,
    *,
    client: httpx.Client | None = None,
) -> str:
    if not completion_available(config):
        raise EditorAiError("completion_unavailable")
    parsed = urlparse(config.base_url)
    url = f"{parsed.scheme}://{parsed.netloc}/beta/completions"
    body = {
        "model": config.model or "deepseek-chat",
        "prompt": prefix[-MAX_BEFORE:],
        "suffix": suffix[:MAX_AFTER],
        "max_tokens": 160,
        "temperature": 0.0,
        "stop": ["\n\n\n"],
    }
    owned = client is None
    http = client or httpx.Client(timeout=COMPLETE_SECONDS)
    try:
        response = http.post(url, json=body, headers={"Authorization": f"Bearer {config.api_key}"})
        if response.status_code in {400, 404, 422} and body["model"] != "deepseek-chat":
            # A model of the chat API that the completions endpoint does not know.
            response = http.post(
                url,
                json={**body, "model": "deepseek-chat"},
                headers={"Authorization": f"Bearer {config.api_key}"},
            )
        response.raise_for_status()
        document = response.json()
    except (httpx.HTTPError, ValueError):
        raise EditorAiError("completion_failed") from None
    finally:
        if owned:
            http.close()
    choices = document.get("choices") if isinstance(document, dict) else None
    text = choices[0].get("text") if isinstance(choices, list) and choices else None
    return _trim_completion(text, suffix) if isinstance(text, str) else ""


__all__ = [
    "EditorAiError",
    "complete_at_cursor",
    "completion_available",
    "rewrite_selection",
]
