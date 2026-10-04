"""Benchmark warmup policy.

Benchmark samples need enough warmup that JIT/cache effects stop dominating
the mean. This policy drops the first sample (typical cold start), then keeps
requesting runs while the coefficient of variation stays above a target and
the sample cap has not been reached.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class BenchmarkWarmupError(ValueError):
    pass


class WarmupState(StrEnum):
    WARMING_UP = "warming_up"
    STABILIZED = "stabilized"
    SAMPLE_CAP_REACHED = "sample_cap_reached"


@dataclass(frozen=True, slots=True)
class WarmupPolicy:
    minimum_samples: int = 5
    maximum_samples: int = 20
    target_cv: float = 0.05
    drop_first_sample: bool = True

    def __post_init__(self) -> None:
        if self.minimum_samples < 1 or self.maximum_samples < self.minimum_samples:
            raise BenchmarkWarmupError("warmup sample counts are invalid")
        if self.target_cv <= 0:
            raise BenchmarkWarmupError("warmup target cv must be positive")

    def to_document(self) -> dict[str, Any]:
        return {
            "minimum_samples": self.minimum_samples,
            "maximum_samples": self.maximum_samples,
            "target_cv": self.target_cv,
            "drop_first_sample": self.drop_first_sample,
        }


@dataclass(frozen=True, slots=True)
class WarmupDecision:
    state: WarmupState
    samples: int
    analyzed_samples: int
    mean_seconds: float | None
    cv: float | None
    keep_warming: bool
    reason: str

    def to_document(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "samples": self.samples,
            "analyzed_samples": self.analyzed_samples,
            "mean_seconds": round(self.mean_seconds, 6) if self.mean_seconds is not None else None,
            "cv": round(self.cv, 6) if self.cv is not None else None,
            "keep_warming": self.keep_warming,
            "reason": self.reason,
        }


def warmup_decision(
    durations_seconds: list[float] | tuple[float, ...],
    *,
    policy: WarmupPolicy | None = None,
) -> WarmupDecision:
    """Decide whether benchmark warmup should continue for one more sample."""
    active = policy or WarmupPolicy()
    if any(
        not isinstance(duration, (int, float)) or duration < 0 for duration in durations_seconds
    ):
        raise BenchmarkWarmupError("benchmark durations must be non-negative numbers")
    samples = tuple(float(duration) for duration in durations_seconds)
    if len(samples) < active.minimum_samples:
        return WarmupDecision(
            WarmupState.WARMING_UP,
            len(samples),
            0,
            None,
            None,
            True,
            f"need at least {active.minimum_samples} samples, have {len(samples)}",
        )
    if len(samples) >= active.maximum_samples:
        analyzed = samples[1:] if active.drop_first_sample and len(samples) > 1 else samples
        mean = statistics.fmean(analyzed) if analyzed else 0.0
        cv = _coefficient_of_variation(analyzed)
        return WarmupDecision(
            WarmupState.SAMPLE_CAP_REACHED,
            len(samples),
            len(analyzed),
            mean,
            cv,
            False,
            f"sample cap of {active.maximum_samples} reached",
        )
    analyzed = samples[1:] if active.drop_first_sample and len(samples) > 1 else samples
    if not analyzed:
        return WarmupDecision(
            WarmupState.WARMING_UP,
            len(samples),
            0,
            None,
            None,
            True,
            "first sample is dropped as cold-start warmup",
        )
    mean = statistics.fmean(analyzed)
    cv = _coefficient_of_variation(analyzed)
    if cv <= active.target_cv:
        return WarmupDecision(
            WarmupState.STABILIZED,
            len(samples),
            len(analyzed),
            mean,
            cv,
            False,
            f"coefficient of variation {cv:.4f} is within target {active.target_cv}",
        )
    return WarmupDecision(
        WarmupState.WARMING_UP,
        len(samples),
        len(analyzed),
        mean,
        cv,
        True,
        f"coefficient of variation {cv:.4f} exceeds target {active.target_cv}",
    )


def _coefficient_of_variation(values: tuple[float, ...]) -> float:
    mean = statistics.fmean(values)
    if mean <= 0:
        return 0.0
    return statistics.pstdev(values) / mean


__all__ = [
    "BenchmarkWarmupError",
    "WarmupDecision",
    "WarmupPolicy",
    "WarmupState",
    "warmup_decision",
]
