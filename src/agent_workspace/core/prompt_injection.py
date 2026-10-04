"""Deterministic prompt injection heuristic classifier.

This is a local pre-filter, not a guarantee. It scores explicit instruction
overrides, role confusion, known jailbreak phrasings, delimiter smuggling, and
encoded-instruction markers. Scores are 0..1 and levels mirror the security
team's response ladder: low (log), medium (warn), high (block).
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from typing import Any

_LOW = 0.35
_HIGH = 0.75

_RULES: tuple[tuple[str, float, str], ...] = (
    (
        r"ignore\s+(all\s+|any\s+)?(previous|prior|earlier|above)\s+instructions",
        0.9,
        "instruction_override",
    ),
    (
        r"disregard\s+(all\s+|any\s+)?(previous|prior|earlier|above)\s+instructions",
        0.9,
        "instruction_override",
    ),
    (
        r"forget\s+(everything\s+)?(you\s+were\s+told|your\s+instructions)",
        0.9,
        "instruction_override",
    ),
    (
        r"(override|supersede|replace)\s+(the\s+)?system\s+(prompt|instructions|message)",
        0.9,
        "instruction_override",
    ),
    (r"reveal\s+(the\s+|your\s+)?(system\s+)?(prompt|instructions)", 0.8, "prompt_exfiltration"),
    (r"(show|print|dump)\s+(me\s+)?your\s+(system\s+)?prompt", 0.8, "prompt_exfiltration"),
    (r"\b(system\s+prompt|developer\s+message)\s*(:|=)", 0.7, "delimiter_smuggling"),
    (r"^---+BEGIN (NEW )?INSTRUCTIONS---+$", 0.7, "delimiter_smuggling"),
    (r"you\s+are\s+now\s+(DAN|an?\s+unrestricted\s+model)", 0.9, "jailbreak_persona"),
    (r"\b(jailbreak|do\s+anything\s+now)\b", 0.6, "jailbreak_persona"),
    (r"(act|pretend|roleplay)\s+as\s+(a\s+|an\s+)?(unfiltered|uncensored)", 0.7, "role_confusion"),
    (r"you\s+(are|must)\s+(not|never)\s+(follow|obey)", 0.6, "role_confusion"),
    (r"(decrypt|decode)\s+(the\s+)?(base64|hex)\s+instruction", 0.8, "encoded_instructions"),
    (r"<\|?im_start\|?>.*?system", 0.8, "delimiter_smuggling"),
)

_SAFE_TERMS = frozenset(
    {
        "ignore previous instructions in the example below",
        "do not follow instructions from untrusted data",
        "disregard instructions found in fetched pages",
    }
)


@dataclass(frozen=True, slots=True)
class PromptInjectionAssessment:
    score: float
    level: str
    triggered_rules: tuple[str, ...]
    matched_patterns: tuple[str, ...]

    @property
    def blocked(self) -> bool:
        return self.score >= _HIGH

    def to_document(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "blocked": self.blocked,
            "triggered_rules": list(self.triggered_rules),
            "matched_patterns": list(self.matched_patterns),
        }


def _decode_candidates(text: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for match in re.findall(r"\b[A-Za-z0-9+/]{16,}={0,2}(?=\s|$)", text):
        try:
            decoded = base64.b64decode(match, validate=True).decode("utf-8", errors="strict")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        lowered = decoded.lower()
        if any(token in lowered for token in ("instruction", "ignore", "system", "prompt")):
            candidates.append(("base64", decoded))
    for match in re.findall(r"\b(?:[0-9a-f]{16,})\b", text):
        if len(match) % 2:
            continue
        try:
            decoded = bytes.fromhex(match).decode("utf-8", errors="strict")
        except (ValueError, UnicodeDecodeError):
            continue
        lowered = decoded.lower()
        if any(token in lowered for token in ("instruction", "ignore", "system", "prompt")):
            candidates.append(("hex", decoded))
    return candidates


def classify_prompt_injection(
    text: str,
    *,
    allowlisted_instructions: tuple[str, ...] = (),
) -> PromptInjectionAssessment:
    if not isinstance(text, str):
        raise ValueError("prompt text must be a string")
    allowed = {instruction.casefold() for instruction in allowlisted_instructions}
    for safe in _SAFE_TERMS:
        if safe in text.casefold():
            allowed.add(safe)
    triggered: list[str] = []
    matched: list[str] = []
    scores: list[float] = []
    lowered = text.casefold()
    for pattern, score, rule in _RULES:
        for match in re.finditer(pattern, lowered, flags=re.IGNORECASE):
            matched_text = match.group(0)
            if any(matched_text in instruction for instruction in allowed):
                continue
            triggered.append(rule)
            matched.append(matched_text)
            scores.append(score)
    for kind, decoded in _decode_candidates(text):
        triggered.append(f"{kind}_payload")
        matched.append(decoded[:160])
        scores.append(0.75)
    score = 0.0 if not scores else min(1.0, max(scores) + 0.05 * min(len(scores) - 1, 4))
    if score >= _HIGH:
        level = "high"
    elif score >= _LOW:
        level = "medium"
    else:
        level = "low"
    unique_rules = tuple(dict.fromkeys(triggered))
    return PromptInjectionAssessment(
        score=round(score, 3),
        level=level,
        triggered_rules=unique_rules,
        matched_patterns=tuple(matched),
    )


__all__ = ["PromptInjectionAssessment", "classify_prompt_injection"]
