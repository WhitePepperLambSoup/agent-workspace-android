# ruff: noqa: RUF001 -- the instructions describe Chinese writing.
"""The quick actions on what the user copied anywhere: a one-shot model call that polishes,
translates, summarizes or rewrites text in the tone of an official document, and a table
screenshot turned into a workbook by Windows text recognition."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import tempfile
from pathlib import Path
from typing import Any

from agent_workspace.config import ProviderConfig
from agent_workspace.core.models import ChatMessage, DeltaKind, ProviderRequest, Role
from agent_workspace.office import pdf, xlsx
from agent_workspace.office.ooxml import OfficeError
from agent_workspace.providers import create_provider

MAX_TEXT = 20_000
MAX_IMAGE_BYTES = 6 * 1024 * 1024
TIMEOUT_SECONDS = 120

_INSTRUCTIONS = {
    "polish": (
        "Polish the text: fix errors, make it clear and fluent, keep its meaning, language, "
        "facts, names, numbers and length about the same."
    ),
    "translate": (
        "Translate the text. Chinese text goes into natural English; any other language into "
        "natural Simplified Chinese. Keep names, numbers, units and formatting; no translationese."
    ),
    "summarize": (
        "Summarize the text in its own language: one sentence with the main point, then at most "
        "five short points with the facts, numbers, decisions and deadlines it contains."
    ),
    "official": (
        "Rewrite the text in the register of a Chinese official document (公文): formal, "
        "accurate and concise, no colloquial words or exaggeration, numbered levels 一、（一）1. "
        "where the content has parts. Keep every fact; add none."
    ),
    "reply": (
        "Write a short, polite reply to this message in its language: answer what it asks, "
        "and leave [placeholders] for facts, dates or commitments the user must decide."
    ),
}
ACTIONS = frozenset(_INSTRUCTIONS)


class QuickActionError(RuntimeError):
    pass


def run_text_action(config: ProviderConfig, action: str, text: str) -> str:
    """The model's answer for one quick action on the text."""
    if action not in _INSTRUCTIONS:
        raise QuickActionError("invalid_action")
    request = ProviderRequest(
        model=config.model,
        messages=(
            ChatMessage(
                role=Role.SYSTEM,
                content=_INSTRUCTIONS[action]
                + " Return only the result, with no preface, explanation or quotation marks.",
            ),
            ChatMessage(role=Role.USER, content=text.strip()[:MAX_TEXT]),
        ),
        max_output_tokens=4096,
        temperature=0.3,
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
        return "".join(chunks).strip()

    try:
        answer = asyncio.run(asyncio.wait_for(stream(), TIMEOUT_SECONDS))
    except TimeoutError:
        raise QuickActionError("quick_action_timeout") from None
    except QuickActionError:
        raise
    except Exception:
        raise QuickActionError("quick_action_failed") from None
    if answer.startswith("```") and answer.endswith("```"):
        answer = "\n".join(answer.splitlines()[1:-1]).strip()
    if not answer:
        raise QuickActionError("quick_action_empty")
    return answer


def table_from_image(image: str) -> tuple[list[list[str]], bytes]:
    """The rows of a table screenshot (PNG, base64) and a workbook of them."""
    try:
        data = base64.b64decode(image, validate=True)
    except ValueError:
        raise QuickActionError("invalid_image") from None
    if not data.startswith(b"\x89PNG") or len(data) > MAX_IMAGE_BYTES:
        raise QuickActionError("invalid_image")
    with tempfile.TemporaryDirectory(prefix="aw-quick-") as folder:
        path = Path(folder) / "table.png"
        path.write_bytes(data)
        try:
            recognized = pdf.recognize(path, kind="image", timeout=120)
        except OfficeError:
            raise QuickActionError("recognition_failed") from None
    page: dict[str, Any] = next(iter(recognized.values()), {})
    rows = pdf.table_from_lines(pdf.recognized_lines(page))
    if not rows:
        raise QuickActionError("no_table")
    cells: list[list[Any]] = [[_cell(value) for value in row] for row in rows]
    workbook, _ = xlsx.build({"sheets": [{"name": "表格", "rows": cells}]})
    return rows, workbook


def _cell(value: str) -> Any:
    """Numbers as numbers (so the workbook can sum them), the rest as text."""
    cleaned = value.replace(",", "").replace("，", "").strip()
    if cleaned and len(cleaned) <= 15 and not (cleaned.startswith("0") and cleaned[1:2].isdigit()):
        try:
            number = float(cleaned)
        except ValueError:
            return value
        return int(number) if number.is_integer() and "." not in cleaned else number
    return value


__all__ = ["ACTIONS", "QuickActionError", "run_text_action", "table_from_image"]
