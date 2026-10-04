"""Lightweight turn-latency profiling.

The profiler records stage durations without adding dependencies; callers feed
it monotonic timestamps and it renders a compact report. It is intentionally
side-effect free.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True)
class TurnStageTiming:
    stage: str
    started_at: float
    ended_at: float | None = None

    @property
    def elapsed_seconds(self) -> float | None:
        return None if self.ended_at is None else self.ended_at - self.started_at


@dataclass(slots=True)
class TurnProfiler:
    session_id: str
    turn: int = 0
    stages: dict[str, TurnStageTiming] = field(default_factory=dict)
    history: deque[dict[str, float]] = field(default_factory=lambda: deque(maxlen=50))

    def start(self, stage: str) -> None:
        if stage in self.stages:
            raise ValueError(f"profiler stage already started: {stage}")
        self.stages[stage] = TurnStageTiming(stage, _monotonic())

    def stop(self, stage: str) -> float:
        timing = self.stages.get(stage)
        if timing is None:
            raise ValueError(f"profiler stage is not running: {stage}")
        if timing.ended_at is not None:
            raise ValueError(f"profiler stage already stopped: {stage}")
        timing.ended_at = _monotonic()
        elapsed = timing.elapsed_seconds
        if elapsed is None:
            raise AssertionError("profiler stage failed to record a duration")
        self.history.append({stage: elapsed})
        return elapsed

    def snapshot(self) -> dict[str, float]:
        return {stage: timing.elapsed_seconds or 0.0 for stage, timing in self.stages.items()}

    def render(self) -> str:
        lines = [f"turn {self.turn} profile"]
        for stage, elapsed in sorted(self.snapshot().items()):
            lines.append(f"  {stage}: {elapsed:.3f}s")
        return "\n".join(lines)


def _monotonic() -> float:
    import time

    return time.monotonic()


__all__ = ["TurnProfiler", "TurnStageTiming"]
