"""Evaluation flaky test detector.

Aggregates repeated test-run outcomes and flags tests whose pass/fail pattern
is mixed across runs. Confidence is the probability of observing at least one
pass and one fail under the estimated per-run failure rate, which grows when
the evidence for intermittent behavior accumulates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class FlakyDetectorError(ValueError):
    pass


class FlakyStability(StrEnum):
    INSUFFICIENT_DATA = "insufficient_data"
    STABLE_PASSING = "stable_passing"
    STABLE_FAILING = "stable_failing"
    FLAKY = "flaky"


@dataclass(frozen=True, slots=True)
class FlakyDetectionPolicy:
    minimum_runs: int = 2
    minimum_failures: int = 1
    minimum_failure_rate: float = 0.02
    maximum_failure_rate: float = 0.98

    def __post_init__(self) -> None:
        if self.minimum_runs < 1 or self.minimum_failures < 1:
            raise FlakyDetectorError("flaky detection counts must be positive")
        if not 0.0 < self.minimum_failure_rate <= self.maximum_failure_rate < 1.0:
            raise FlakyDetectorError("flaky detection failure-rate bounds are invalid")

    def to_document(self) -> dict[str, Any]:
        return {
            "minimum_runs": self.minimum_runs,
            "minimum_failures": self.minimum_failures,
            "minimum_failure_rate": self.minimum_failure_rate,
            "maximum_failure_rate": self.maximum_failure_rate,
        }


@dataclass(frozen=True, slots=True)
class FlakyRunOutcome:
    test_id: str
    passed: bool
    duration_seconds: float | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "passed": self.passed,
            "duration_seconds": self.duration_seconds,
        }


@dataclass(frozen=True, slots=True)
class FlakyVerdict:
    test_id: str
    stability: FlakyStability
    runs: int
    passed: int
    failed: int
    failure_rate: float
    confidence: float
    severity: str

    def to_document(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "stability": self.stability.value,
            "runs": self.runs,
            "passed": self.passed,
            "failed": self.failed,
            "failure_rate": round(self.failure_rate, 4),
            "confidence": round(self.confidence, 4),
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class FlakyDetectionReport:
    verdicts: tuple[FlakyVerdict, ...]

    @property
    def flaky_tests(self) -> tuple[FlakyVerdict, ...]:
        return tuple(
            verdict for verdict in self.verdicts if verdict.stability is FlakyStability.FLAKY
        )

    def to_document(self) -> dict[str, Any]:
        return {"verdicts": [verdict.to_document() for verdict in self.verdicts]}


def _severity(failure_rate: float) -> str:
    if failure_rate >= 0.3:
        return "high"
    if failure_rate >= 0.1:
        return "medium"
    return "low"


def detect_flaky_tests(
    outcomes: list[FlakyRunOutcome] | tuple[FlakyRunOutcome, ...],
    *,
    policy: FlakyDetectionPolicy | None = None,
) -> FlakyDetectionReport:
    active = policy or FlakyDetectionPolicy()
    grouped: dict[str, list[bool]] = {}
    for outcome in outcomes:
        grouped.setdefault(outcome.test_id, []).append(outcome.passed)
    verdicts: list[FlakyVerdict] = []
    for test_id in sorted(grouped):
        runs = grouped[test_id]
        failed = sum(1 for passed in runs if not passed)
        passed = len(runs) - failed
        failure_rate = failed / len(runs)
        if len(runs) < active.minimum_runs:
            verdicts.append(
                FlakyVerdict(
                    test_id,
                    FlakyStability.INSUFFICIENT_DATA,
                    len(runs),
                    passed,
                    failed,
                    failure_rate,
                    0.0,
                    "low",
                )
            )
            continue
        mixed = passed > 0 and failed > 0
        in_failure_band = active.minimum_failure_rate <= failure_rate <= active.maximum_failure_rate
        if mixed and failed >= active.minimum_failures and in_failure_band:
            confidence = 1.0 - failure_rate ** len(runs) - (1.0 - failure_rate) ** len(runs)
            verdicts.append(
                FlakyVerdict(
                    test_id,
                    FlakyStability.FLAKY,
                    len(runs),
                    passed,
                    failed,
                    failure_rate,
                    max(0.0, confidence),
                    _severity(failure_rate),
                )
            )
        elif passed == 0 or (mixed and failure_rate > active.maximum_failure_rate):
            verdicts.append(
                FlakyVerdict(
                    test_id,
                    FlakyStability.STABLE_FAILING,
                    len(runs),
                    passed,
                    failed,
                    failure_rate,
                    1.0,
                    _severity(failure_rate),
                )
            )
        else:
            # All passed, or the observed failures stay inside the tolerated
            # noise band (below minimum_failure_rate).
            verdicts.append(
                FlakyVerdict(
                    test_id,
                    FlakyStability.STABLE_PASSING,
                    len(runs),
                    passed,
                    failed,
                    failure_rate,
                    1.0 - failure_rate ** len(runs) - (1.0 - failure_rate) ** len(runs),
                    _severity(failure_rate),
                )
            )
    return FlakyDetectionReport(tuple(verdicts))


__all__ = [
    "FlakyDetectionPolicy",
    "FlakyDetectionReport",
    "FlakyDetectorError",
    "FlakyRunOutcome",
    "FlakyStability",
    "FlakyVerdict",
    "detect_flaky_tests",
]
