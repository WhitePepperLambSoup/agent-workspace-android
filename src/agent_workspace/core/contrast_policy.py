"""Desktop high-contrast policy.

Validates foreground/background pairs against WCAG-style contrast targets and
maps a user-facing accessibility setting to an enforceable policy. The module
is pure data/policy logic so the Qt theme layer can consume it without owning
widget code.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")


class HighContrastError(ValueError):
    pass


class ContrastProfile(StrEnum):
    STANDARD = "standard"
    HIGH_CONTRAST = "high_contrast"
    FORCED_COLORS = "forced_colors"
    OFF = "off"


@dataclass(frozen=True, slots=True)
class ContrastPolicy:
    profile: ContrastProfile = ContrastProfile.STANDARD
    minimum_ratio: float = 4.5
    large_text_minimum_ratio: float = 3.0

    def __post_init__(self) -> None:
        if self.minimum_ratio < 1.0 or self.large_text_minimum_ratio < 1.0:
            raise HighContrastError("contrast ratios must be at least 1.0")
        if self.profile is ContrastProfile.OFF:
            object.__setattr__(self, "minimum_ratio", 1.0)
            object.__setattr__(self, "large_text_minimum_ratio", 1.0)

    def threshold_for(self, *, large_text: bool) -> float:
        return self.large_text_minimum_ratio if large_text else self.minimum_ratio

    def to_document(self) -> dict[str, Any]:
        return {
            "profile": self.profile.value,
            "minimum_ratio": self.minimum_ratio,
            "large_text_minimum_ratio": self.large_text_minimum_ratio,
        }


@dataclass(frozen=True, slots=True)
class ContrastVerdict:
    foreground: str
    background: str
    ratio: float
    passes: bool
    large_text: bool

    def to_document(self) -> dict[str, Any]:
        return {
            "foreground": self.foreground,
            "background": self.background,
            "ratio": round(self.ratio, 3),
            "passes": self.passes,
            "large_text": self.large_text,
        }


def parse_hex_color(color: str) -> tuple[int, int, int]:
    if not _HEX_COLOR.fullmatch(color):
        raise HighContrastError(f"color {color!r} must use #RRGGBB hex notation")
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def _channel_luminance(value: int) -> float:
    normalized = value / 255.0
    if normalized <= 0.04045:
        return normalized / 12.92
    return math.pow((normalized + 0.055) / 1.055, 2.4)


def relative_luminance(color: str) -> float:
    red, green, blue = parse_hex_color(color)
    return (
        0.2126 * _channel_luminance(red)
        + 0.7152 * _channel_luminance(green)
        + 0.0722 * _channel_luminance(blue)
    )


def contrast_ratio(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def contrast_verdict(
    foreground: str,
    background: str,
    *,
    policy: ContrastPolicy | None = None,
    large_text: bool = False,
) -> ContrastVerdict:
    active = policy or effective_contrast_policy(ContrastProfile.STANDARD)
    ratio = contrast_ratio(foreground, background)
    threshold = active.threshold_for(large_text=large_text)
    return ContrastVerdict(
        foreground=foreground,
        background=background,
        ratio=ratio,
        passes=ratio >= threshold,
        large_text=large_text,
    )


def audit_palette(
    pairs: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    *,
    policy: ContrastPolicy | None = None,
) -> tuple[ContrastVerdict, ...]:
    if not pairs:
        raise HighContrastError("palette audit requires at least one color pair")
    return tuple(
        contrast_verdict(foreground, background, policy=policy) for foreground, background in pairs
    )


def effective_contrast_policy(setting: str) -> ContrastPolicy:
    try:
        profile = ContrastProfile(setting.casefold())
    except ValueError as exc:
        raise HighContrastError(f"unknown contrast setting {setting!r}") from exc
    if profile is ContrastProfile.OFF:
        return ContrastPolicy(profile=profile)
    if profile is ContrastProfile.HIGH_CONTRAST:
        return ContrastPolicy(profile=profile, minimum_ratio=7.0, large_text_minimum_ratio=4.5)
    if profile is ContrastProfile.FORCED_COLORS:
        return ContrastPolicy(profile=profile, minimum_ratio=21.0, large_text_minimum_ratio=21.0)
    return ContrastPolicy(profile=profile)


__all__ = [
    "ContrastPolicy",
    "ContrastProfile",
    "ContrastVerdict",
    "HighContrastError",
    "audit_palette",
    "contrast_ratio",
    "contrast_verdict",
    "effective_contrast_policy",
    "parse_hex_color",
    "relative_luminance",
]
