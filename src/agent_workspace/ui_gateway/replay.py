"""A finished turn told again step by step, for the studio's replay: who did what, when.

The steps come from the recorded events of the conversation and of the sub-agents and experts it
delegated to (each run keeps its own store): tool calls from start to end, model calls (thinking),
waits for an approval, and the answer. Times are seconds from the turn's start.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from agent_workspace.core.events import Event
from agent_workspace.policy.redaction import Redactor

REPLAY_EVENT_TYPES = frozenset(
    {
        "turn.started",
        "turn.completed",
        "turn.failed",
        "turn.cancelled",
        "message.created",
        "model.requested",
        "model.completed",
        "model.failed",
        "tool.proposed",
        "tool.started",
        "tool.settled",
        "tool.failed",
        "tool.rejected",
        "tool.cancelled",
        "tool.approval_required",
        "tool.approved",
    }
)
_TURN_ENDS = {"turn.completed": "completed", "turn.failed": "failed", "turn.cancelled": "cancelled"}
_TOOL_ENDS = {"tool.settled", "tool.failed", "tool.rejected", "tool.cancelled"}
_DETAIL_ARGUMENTS = ("command", "path", "url", "query", "task", "title", "source")
_DETAIL_CHARS = 100
MAX_STEPS = 600


def _seconds(text: str) -> float:
    return datetime.fromisoformat(text).timestamp()


@dataclass(frozen=True, slots=True)
class ReplayTurn:
    turn_id: str
    start: float
    end: float | None
    outcome: str | None
    prompt: str


def turns_of(events: Sequence[Event]) -> list[ReplayTurn]:
    """The conversation's turns, oldest first, each with its start, its end and its request."""
    turns: dict[str, dict[str, Any]] = {}
    for event in events:
        turn_id = event.correlation_id
        if not turn_id:
            continue
        if event.type == "turn.started":
            turns.setdefault(turn_id, {"start": _seconds(event.created_at), "prompt": ""})
        elif turn_id in turns:
            if event.type in _TURN_ENDS:
                turns[turn_id]["end"] = _seconds(event.created_at)
                turns[turn_id]["outcome"] = _TURN_ENDS[event.type]
            elif (
                event.type == "message.created"
                and event.data.get("role") == "user"
                and not turns[turn_id]["prompt"]
            ):
                turns[turn_id]["prompt"] = str(event.data.get("content") or "")[:200]
    return [
        ReplayTurn(turn_id, item["start"], item.get("end"), item.get("outcome"), item["prompt"])
        for turn_id, item in sorted(turns.items(), key=lambda pair: pair[1]["start"])
    ]


def _detail(name: str, arguments: object) -> str:
    detail = ""
    if isinstance(arguments, Mapping):
        detail = next(
            (
                str(arguments[key])
                for key in _DETAIL_ARGUMENTS
                if isinstance(arguments.get(key), str) and str(arguments[key]).strip()
            ),
            "",
        )
        if not detail and isinstance(arguments.get("argv"), list):
            detail = " ".join(str(part) for part in arguments["argv"])
    text = " ".join(Redactor().redact(detail).split())
    return text[:_DETAIL_CHARS] if name else ""


def steps_of(
    events: Sequence[Event], actor: str, start: float, end: float | None
) -> list[dict[str, object]]:
    """One actor's steps within [start, end]: tools, thinking, approval waits, the answer."""
    steps: list[dict[str, object]] = []
    proposed: dict[str, tuple[str, object]] = {}
    open_tools: dict[str, dict[str, object]] = {}
    waits: dict[str, dict[str, object]] = {}
    thinking: dict[str, object] | None = None
    last = start
    for event in events:
        at = _seconds(event.created_at)
        if at < start or (end is not None and at > end + 1):
            continue
        last = max(last, at)
        offset = round(at - start, 3)
        data = event.data
        attempt = str(data.get("attempt_id") or data.get("tool_call_id") or "")
        if event.type == "tool.proposed":
            proposed[attempt] = (str(data.get("name") or ""), data.get("arguments"))
        elif event.type == "tool.approval_required":
            name = proposed.get(attempt, (str(data.get("name") or ""), None))[0]
            waits[attempt] = {"actor": actor, "kind": "wait", "tool": name, "start": offset}
        elif event.type == "tool.approved" and attempt in waits:
            steps.append({**waits.pop(attempt), "end": offset})
        elif event.type == "tool.started":
            name, arguments = proposed.get(attempt, (str(data.get("name") or ""), None))
            open_tools[attempt] = {
                "actor": actor,
                "kind": "tool",
                "tool": name,
                "detail": _detail(name, arguments),
                "start": offset,
                "item": f"tool-{attempt}",
            }
        elif event.type in _TOOL_ENDS:
            if attempt in waits:
                steps.append({**waits.pop(attempt), "end": offset})
            step = open_tools.pop(attempt, None)
            if step is not None:
                steps.append({**step, "end": offset, "failed": event.type != "tool.settled"})
        elif event.type == "model.requested":
            thinking = {"actor": actor, "kind": "think", "start": offset}
        elif event.type in {"model.completed", "model.failed"} and thinking is not None:
            steps.append({**thinking, "end": offset})
            thinking = None
        elif (
            event.type == "message.created"
            and data.get("role") == "assistant"
            and not data.get("tool_calls")
            and str(data.get("content") or "").strip()
        ):
            steps.append({"actor": actor, "kind": "answer", "start": offset, "end": offset})
    finish = round((end if end is not None else last) - start, 3)
    for step in [*open_tools.values(), *waits.values(), *([thinking] if thinking else [])]:
        steps.append({**step, "end": finish})
    return steps


def build_replay(
    turn: ReplayTurn,
    lead_events: Sequence[Event],
    runs: Sequence[tuple[str, str, str | None, Sequence[Event]]],
) -> dict[str, object]:
    """The turn's replay: its actors (the lead, then each run: id, title, expert) and the steps
    of all of them in time order. A run's steps outside the turn are left out."""
    actors: list[dict[str, object]] = [{"id": "lead"}]
    steps = steps_of(lead_events, "lead", turn.start, turn.end)
    for run_id, title, expert, events in runs:
        actor = f"run:{run_id}"
        actors.append({"id": actor, "runId": run_id, "title": title, "expert": expert})
        # A run's tool calls are rows of its own task, not of the conversation.
        steps.extend(
            {key: value for key, value in step.items() if key != "item"}
            for step in steps_of(events, actor, turn.start, turn.end)
        )
    steps.sort(key=lambda step: (float(step["start"]), str(step["actor"])))  # type: ignore[arg-type]
    duration = (
        turn.end - turn.start
        if turn.end is not None
        else max((float(step["end"]) for step in steps), default=0.0)  # type: ignore[arg-type]
    )
    return {
        "turnId": turn.turn_id,
        "prompt": turn.prompt,
        "outcome": turn.outcome,
        "duration": round(duration, 3),
        "actors": actors,
        "steps": steps[:MAX_STEPS],
        "truncated": len(steps) > MAX_STEPS,
    }
