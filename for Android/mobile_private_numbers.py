"""Personal numbers in text that leaves the phone: Chinese ID card numbers and bank card numbers,
only ones whose check digit is right. The engine's copy of the page's privateParts (app/65-privacy.js):
what the phone hands to a computer is checked here too, for text the page never sees (a whole
conversation continued on the computer, a task the agent writes for it).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID = re.compile(r"(?<![\dXx])\d{17}[\dXx](?![\dXx])")
_CARD = re.compile(r"(?<!\d)\d(?:[ -]?\d){15,18}(?!\d)")


def _valid_id(value: str) -> bool:
    if not re.fullmatch(r"\d{17}[\dXx]", value):
        return False
    total = sum(weight * int(value[index]) for index, weight in enumerate(_ID_WEIGHTS))
    return "10X98765432"[total % 11] == value[17].upper()


def _valid_card(digits: str) -> bool:
    if not re.fullmatch(r"\d{16,19}", digits):
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        value = int(digit) * (2 if index % 2 else 1)
        total += value - 9 if value > 9 else value
    return total % 10 == 0


def _masked(value: str) -> str:
    return "*" * len(value) if len(value) <= 8 else f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


def find(text: str) -> list[dict[str, str]]:
    """The personal numbers in [text]: [{kind: "id_card" | "bank_card", value, masked}]."""
    found: list[dict[str, str]] = []
    for match in _ID.finditer(text):
        if _valid_id(match.group()):
            found.append({"kind": "id_card", "value": match.group(), "masked": _masked(match.group())})
    for match in _CARD.finditer(text):
        digits = re.sub(r"[ -]", "", match.group())
        if any(item["value"] == digits for item in found) or _valid_id(digits):
            continue
        if _valid_card(digits):
            found.append({"kind": "bank_card", "value": match.group(), "masked": _masked(digits)})
    return found


def find_all(texts: Iterable[str]) -> list[dict[str, str]]:
    """The personal numbers in several texts, each once."""
    seen: dict[str, dict[str, str]] = {}
    for text in texts:
        for item in find(text):
            seen.setdefault(item["value"], item)
    return list(seen.values())


def mask(text: str) -> str:
    """[text] with each personal number masked (the first and last four digits kept)."""
    for item in find(text):
        text = text.replace(item["value"], item["masked"])
    return text


__all__ = ["find", "find_all", "mask"]
