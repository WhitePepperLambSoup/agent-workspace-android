"""Server websocket keepalive policy.

Computes when to send the next ping and when a connection must be closed for
missing pongs. Pure policy math so both the server loop and tests can use the
same deadlines without timers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class WebsocketKeepaliveError(ValueError):
    pass


class KeepaliveAction(StrEnum):
    WAIT = "wait"
    PING = "ping"
    CLOSE = "close"


@dataclass(frozen=True, slots=True)
class WebsocketKeepalivePolicy:
    ping_interval_seconds: float = 30.0
    pong_timeout_seconds: float = 10.0
    max_missed_pongs: int = 2
    close_after_timeouts: bool = True

    def __post_init__(self) -> None:
        if self.ping_interval_seconds <= 0 or self.pong_timeout_seconds <= 0:
            raise WebsocketKeepaliveError("websocket keepalive intervals must be positive")
        if self.max_missed_pongs < 1:
            raise WebsocketKeepaliveError("max missed pongs must be positive")

    def to_document(self) -> dict[str, Any]:
        return {
            "ping_interval_seconds": self.ping_interval_seconds,
            "pong_timeout_seconds": self.pong_timeout_seconds,
            "max_missed_pongs": self.max_missed_pongs,
            "close_after_timeouts": self.close_after_timeouts,
        }


@dataclass(frozen=True, slots=True)
class KeepaliveDecision:
    action: KeepaliveAction
    seconds_until_next: float
    missed_pongs: int
    reason: str

    def to_document(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "seconds_until_next": round(self.seconds_until_next, 3),
            "missed_pongs": self.missed_pongs,
            "reason": self.reason,
        }


def validate_keepalive_config(config: dict[str, Any]) -> WebsocketKeepalivePolicy:
    if not isinstance(config, dict):
        raise WebsocketKeepaliveError("websocket keepalive config must be an object")
    raw_interval = config.get("ping_interval_seconds", 30.0)
    raw_timeout = config.get("pong_timeout_seconds", 10.0)
    raw_missed = config.get("max_missed_pongs", 2)
    raw_close = config.get("close_after_timeouts", True)
    if isinstance(raw_interval, bool) or not isinstance(raw_interval, (int, float)):
        raise WebsocketKeepaliveError("ping_interval_seconds must be numeric")
    if isinstance(raw_timeout, bool) or not isinstance(raw_timeout, (int, float)):
        raise WebsocketKeepaliveError("pong_timeout_seconds must be numeric")
    if isinstance(raw_missed, bool) or not isinstance(raw_missed, int):
        raise WebsocketKeepaliveError("max_missed_pongs must be an integer")
    if not isinstance(raw_close, bool):
        raise WebsocketKeepaliveError("close_after_timeouts must be a boolean")
    return WebsocketKeepalivePolicy(
        ping_interval_seconds=float(raw_interval),
        pong_timeout_seconds=float(raw_timeout),
        max_missed_pongs=raw_missed,
        close_after_timeouts=raw_close,
    )


def keepalive_decision(
    *,
    now: float,
    last_ping_at: float | None,
    last_pong_at: float | None,
    missed_pongs: int = 0,
    policy: WebsocketKeepalivePolicy | None = None,
) -> KeepaliveDecision:
    """Decide the next keepalive action for one connection.

    A missing first pong is only counted after ``pong_timeout_seconds`` have
    elapsed since the ping; earlier timestamps are a scheduling bug and raise
    so callers fix their clocks.
    """
    active = policy or WebsocketKeepalivePolicy()
    if missed_pongs < 0:
        raise WebsocketKeepaliveError("missed pongs may not be negative")
    if last_ping_at is None:
        if last_pong_at is not None and last_pong_at > now:
            raise WebsocketKeepaliveError("last pong timestamp is in the future")
        return KeepaliveDecision(
            KeepaliveAction.PING,
            active.ping_interval_seconds,
            missed_pongs,
            "connection has not been pinged yet",
        )
    if last_ping_at > now or (last_pong_at is not None and last_pong_at > now):
        raise WebsocketKeepaliveError("keepalive timestamps are in the future")
    if last_pong_at is not None and last_pong_at >= last_ping_at:
        # Healthy: the latest ping was answered.
        return KeepaliveDecision(
            KeepaliveAction.WAIT,
            max(0.0, last_ping_at + active.ping_interval_seconds - now),
            0,
            "latest ping was answered",
        )
    elapsed_since_ping = now - last_ping_at
    timed_out = elapsed_since_ping >= active.pong_timeout_seconds
    if timed_out and active.close_after_timeouts and missed_pongs + 1 >= active.max_missed_pongs:
        return KeepaliveDecision(
            KeepaliveAction.CLOSE,
            0.0,
            missed_pongs + 1,
            f"connection missed {missed_pongs + 1} pongs",
        )
    if timed_out:
        return KeepaliveDecision(
            KeepaliveAction.PING,
            active.ping_interval_seconds,
            missed_pongs + 1,
            f"pong timeout after {active.pong_timeout_seconds}s",
        )
    return KeepaliveDecision(
        KeepaliveAction.WAIT,
        max(0.0, last_ping_at + active.pong_timeout_seconds - now),
        missed_pongs,
        "waiting for outstanding pong",
    )


__all__ = [
    "KeepaliveAction",
    "KeepaliveDecision",
    "WebsocketKeepaliveError",
    "WebsocketKeepalivePolicy",
    "keepalive_decision",
    "validate_keepalive_config",
]
