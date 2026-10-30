"""A model's review of a frozen change (a review snapshot): findings anchored at lines of the
diff, which become review comments the user can hand to the agent to fix."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_workspace.config import ProviderConfig

from .model_call import ModelCallError, ask_model

MAX_DIFF_CHARS = 60_000
MAX_CONTEXT_CHARS = 40_000
MAX_FILE_CHARS = 12_000
MAX_FINDINGS = 12
REVIEW_SECONDS = 240
SEVERITIES = ("bug", "risk", "suggestion")

_LANGUAGES = {
    "zh-CN": "Simplified Chinese",
    "zh-TW": "Traditional Chinese",
    "ja-JP": "Japanese",
    "en-US": "English",
}


class ReviewAiError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Finding:
    path: str
    side: str
    line: int
    severity: str
    title: str
    body: str

    def comment(self) -> str:
        return f"[AI · {self.severity}] {self.title}\n\n{self.body}".strip()


# Kept here, not in the shared expert library, so the phone's expert list stays as it is.
REVIEWER_BRIEF = (
    "Code reviewer. Method: read the change and the code it touches (its callers, the data it "
    "handles) and look for what breaks: wrong logic and edge cases, error paths, concurrency, "
    "resources left open, security, compatibility with the code that calls it, tests that do "
    "not cover the change. Check: each finding against the code itself, not style "
    "preferences. Deliver: findings ranked by severity, each with the place, why it is wrong, "
    "and the fix."
)


def render_diff(files: Sequence[Mapping[str, Any]]) -> str:
    """The snapshot's hunks with the line numbers findings must use: new-side numbers on added
    and unchanged lines, old-side numbers on removed ones."""
    parts: list[str] = []
    for document in files:
        path = str(document.get("filePath", ""))
        parts.append(f"### {path} ({document.get('status', 'modified')})")
        for hunk in document.get("hunks", []) if isinstance(document.get("hunks"), list) else []:
            if not isinstance(hunk, Mapping):
                continue
            parts.append(str(hunk.get("header", "@@")))
            for line in hunk.get("lines", []) if isinstance(hunk.get("lines"), list) else []:
                if not isinstance(line, Mapping):
                    continue
                kind, content = line.get("kind"), str(line.get("content", ""))
                if kind == "add":
                    parts.append(f"+ new {line.get('newLineno')}: {content}")
                elif kind == "delete":
                    parts.append(f"- old {line.get('oldLineno')}: {content}")
                elif kind == "context":
                    parts.append(f"  new {line.get('newLineno')}: {content}")
        parts.append("")
    text = "\n".join(parts)
    return text if len(text) <= MAX_DIFF_CHARS else text[:MAX_DIFF_CHARS] + "\n… (cut)"


def file_context(checkout: Path, files: Sequence[Mapping[str, Any]]) -> str:
    """The whole of the changed files that are small enough, for what the diff does not show."""
    parts: list[str] = []
    used = 0
    for document in files:
        path = str(document.get("filePath", ""))
        if document.get("status") == "deleted" or document.get("isBinary"):
            continue
        try:
            text = (checkout / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if len(text) > MAX_FILE_CHARS or used + len(text) > MAX_CONTEXT_CHARS:
            continue
        used += len(text)
        numbered = "\n".join(f"{index + 1}: {line}" for index, line in enumerate(text.splitlines()))
        parts.append(f"### {path} (whole file)\n{numbered}")
    return "\n\n".join(parts)


def _anchors(files: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], list[int]]:
    found: dict[tuple[str, str], list[int]] = {}
    for document in files:
        path = str(document.get("filePath", ""))
        for hunk in document.get("hunks", []) if isinstance(document.get("hunks"), list) else []:
            for line in hunk.get("lines", []) if isinstance(hunk, Mapping) else []:
                if not isinstance(line, Mapping):
                    continue
                for side, key in (("new", "newLineno"), ("old", "oldLineno")):
                    number = line.get(key)
                    if isinstance(number, int) and number > 0:
                        found.setdefault((path, side), []).append(number)
    return found


def parse_findings(text: str, files: Sequence[Mapping[str, Any]]) -> tuple[list[Finding], int]:
    """The model's findings that can be placed on the diff (a line nearby when its own is not
    in it); returns them and how many could not be placed."""
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    start, end = cleaned.find("["), cleaned.rfind("]")
    try:
        document = json.loads(cleaned[start : end + 1]) if start >= 0 and end > start else []
    except json.JSONDecodeError:
        raise ReviewAiError("review_unreadable") from None
    anchors = _anchors(files)
    findings: list[Finding] = []
    skipped = 0
    for item in document if isinstance(document, list) else []:
        if not isinstance(item, dict):
            skipped += 1
            continue
        path, line = str(item.get("path", "")).strip().removeprefix("b/"), item.get("line")
        side = "old" if item.get("side") == "old" else "new"
        title = " ".join(str(item.get("title", "")).split())[:200]
        body = str(item.get("body", "")).strip()[:4000]
        severity = item.get("severity") if item.get("severity") in SEVERITIES else "risk"
        if (path, side) not in anchors:
            side = "new" if side == "old" else "old"
        lines = anchors.get((path, side))
        if not lines or type(line) is not int or not (title or body):
            skipped += 1
            continue
        if line not in lines:
            wanted = line
            line = min(lines, key=lambda number: abs(number - wanted))
        findings.append(Finding(path, side, line, str(severity), title or body[:80], body))
        if len(findings) >= MAX_FINDINGS:
            break
    return findings, skipped


def review_change(
    config: ProviderConfig,
    files: Sequence[Mapping[str, Any]],
    *,
    checkout: Path,
    language: str = "en-US",
) -> tuple[list[Finding], int]:
    system = (
        f"{REVIEWER_BRIEF}\n\n"
        "You review the change below. Report only real problems: wrong logic, unhandled "
        "errors and edge cases, crashes, security issues, data loss, concurrency, broken "
        "compatibility, tests that miss what changed. No style remarks unless they hide a bug. "
        f"At most {MAX_FINDINGS} findings, the most serious first. Each finding names a line "
        "shown in the diff: side 'new' with a 'new N' number, or side 'old' with an 'old N' "
        "number for a removed line. Write title and body in "
        f"{_LANGUAGES.get(language, 'English')}; the body says what is wrong, why, and the fix "
        "(code when it helps). Answer with a JSON array only, no prose: "
        '[{"path": "...", "side": "new", "line": 12, "severity": "bug|risk|suggestion", '
        '"title": "...", "body": "..."}]. An empty array when you find nothing.'
    )
    context = file_context(checkout, files)
    user = f"The change:\n\n{render_diff(files)}"
    if context:
        user += f"\n\nThe changed files as they are now:\n\n{context}"
    try:
        answer = ask_model(
            config,
            system,
            user,
            max_output_tokens=8192,
            seconds=REVIEW_SECONDS,
            error_prefix="review",
        )
    except ModelCallError as error:
        raise ReviewAiError(str(error)) from None
    return parse_findings(answer, files)


__all__ = ["Finding", "ReviewAiError", "parse_findings", "render_diff", "review_change"]
