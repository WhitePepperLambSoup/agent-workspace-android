"""Deterministic offline evals for scripted agent scenarios.

Scenarios are declared in TOML files and replayed against the real
``ApplicationService``/``AgentRunner`` with a scripted provider, so no live
model or network access is required.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import AsyncIterator, Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from agent_workspace.application.event_bus import EventBus
from agent_workspace.application.ports import EventStore
from agent_workspace.application.service import ApplicationService
from agent_workspace.core.events import Event
from agent_workspace.core.models import (
    Autonomy,
    DeltaKind,
    ProviderDelta,
    ProviderRequest,
    ToolCall,
)
from agent_workspace.policy import ProviderEgressPolicy, WorkspacePolicy
from agent_workspace.tools import ToolRegistry
from agent_workspace.tools.paths import StrPath

_EVAL_MODEL = "eval-model"
_EGRESS_ENDPOINT = "http://127.0.0.1:1"


@dataclass(frozen=True, slots=True)
class EvalTurn:
    """One scripted exchange: provider deltas plus the expected behavior."""

    deltas: tuple[dict[str, Any], ...]
    expected_tool_calls: tuple[str, ...] = ()
    expected_final_text: str | None = None
    prompt: str | None = None


@dataclass(frozen=True, slots=True)
class EvalScenario:
    """A named scenario with one or more scripted turns."""

    id: str
    name: str
    prompt: str
    turns: tuple[EvalTurn, ...]
    allowed_tools: frozenset[str] | None = None


@dataclass(frozen=True, slots=True)
class EvalOutcome:
    """The result of replaying a single scenario."""

    scenario_id: str
    passed: bool
    failures: tuple[str, ...]
    final_text: str
    tool_calls: tuple[str, ...]
    # Event-level evidence is intentionally optional for backwards
    # compatibility with callers that construct EvalOutcome directly.
    terminal_events: tuple[str, ...] = ()
    incomplete: bool = False
    settled_tool_results: tuple[dict[str, Any], ...] = ()


def load_scenarios(directory: StrPath) -> tuple[EvalScenario, ...]:
    """Load and validate every scenario TOML in a directory, ordered by id."""
    root = Path(os.fspath(directory))
    scenarios: list[EvalScenario] = []
    seen_ids: set[str] = set()
    for path in sorted(root.glob("*.toml")):
        scenario = _scenario_from_document(_read_document(path), path.name)
        if scenario.id in seen_ids:
            raise ValueError(f"duplicate scenario id: {scenario.id}")
        seen_ids.add(scenario.id)
        scenarios.append(scenario)
    return tuple(sorted(scenarios, key=lambda scenario: scenario.id))


class ScriptedEvalProvider:
    """A ModelProvider that replays scripted delta sequences deterministically.

    Each ``stream()`` call consumes exactly one script (in the order given),
    so the runner's tool-execution loop naturally advances through the turn
    scripts. A FINISH delta without a finish reason is normalized to "stop";
    a script that omits FINISH gets a trailing "stop". Calling ``stream()``
    after the scripts run out raises RuntimeError.
    """

    def __init__(self, scripts: Iterable[Iterable[dict[str, Any]]] = ()) -> None:
        self._scripts: tuple[tuple[ProviderDelta, ...], ...] = tuple(
            tuple(_delta_from_mapping(delta, f"script {index + 1}") for delta in script)
            for index, script in enumerate(scripts)
        )
        self._position = 0
        self.requests: list[ProviderRequest] = []

    @property
    def id(self) -> str:
        return "scripted-eval"

    @property
    def reasoning_protocol(self) -> str | None:
        return None

    @property
    def consumed(self) -> int:
        """Number of scripts already yielded by ``stream()``."""
        return self._position

    @property
    def has_remaining(self) -> bool:
        return self._position < len(self._scripts)

    def encode_request(self, request: ProviderRequest) -> bytes:
        return b""

    async def stream(self, request: ProviderRequest) -> AsyncIterator[ProviderDelta]:
        self.requests.append(request)
        if self._position >= len(self._scripts):
            raise RuntimeError("scripted provider script exhausted")
        script = self._scripts[self._position]
        self._position += 1
        saw_finish = False
        for delta in script:
            if delta.kind is DeltaKind.FINISH:
                saw_finish = True
                if delta.finish_reason is None or not delta.finish_reason.strip():
                    yield replace(delta, finish_reason="stop")
                else:
                    yield delta
            else:
                yield delta
        if not saw_finish:
            yield ProviderDelta(kind=DeltaKind.FINISH, finish_reason="stop")


async def run_scenario(
    scenario: EvalScenario,
    provider: ScriptedEvalProvider,
    store: EventStore,
    workspace: StrPath,
    *,
    autonomy: Autonomy = Autonomy.WORKSPACE,
    approval_callback: Any | None = None,
) -> EvalOutcome:
    """Replay a scenario through the real application service and evaluate it.

    The scenario is run inside a single shared session: every turn issues one
    ``service.run`` call, and the runner's tool-execution loop advances the
    provider script queue as needed. A turn's expectations are checked against
    the state after the run that consumed that turn's script. Provider failures
    (for example a script that runs out mid-run) are captured as failures.
    """
    workspace_path = Path(os.fspath(workspace))
    events = EventBus()
    tools = ToolRegistry.for_workspace(workspace_path, store)
    policy = WorkspacePolicy(workspace_path, autonomy, approval_callback)
    egress_policy = ProviderEgressPolicy(_EGRESS_ENDPOINT, Autonomy.WORKSPACE)
    service = ApplicationService(
        store,
        provider,
        tools,
        policy,
        events,
        egress_policy=egress_policy,
    )
    started_tool_names: list[str] = []
    settled_tool_results: list[dict[str, Any]] = []
    observed_events: list[str] = []

    def collect_started_tools(event: Event) -> None:
        observed_events.append(event.type)
        if event.type == "tool.started":
            name = event.data.get("name")
            if isinstance(name, str):
                started_tool_names.append(name)
        elif event.type == "tool.settled":
            settled_tool_results.append(dict(event.data))

    events.subscribe(collect_started_tools)
    session = service.create_session(workspace_path)
    failures: list[str] = []
    final_text = ""
    evaluated_tools = 0
    try:
        for index, turn in enumerate(scenario.turns):
            if not provider.has_remaining:
                break
            prompt = scenario.prompt if index == 0 else (turn.prompt or scenario.prompt)
            result = await service.run(
                session,
                prompt,
                _EVAL_MODEL,
                allowed_tools=scenario.allowed_tools,
            )
            final_text = result.text
            # Attribute only the tools started during this turn's run; earlier
            # turns keep their own slice so expectations do not accumulate.
            turn_tools = tuple(started_tool_names[evaluated_tools:])
            evaluated_tools = len(started_tool_names)
            failures.extend(_evaluate_turn(turn, turn_tools, final_text))
    except RuntimeError as exc:
        failures.append(f"provider error: {exc}")
    finally:
        await service.aclose()
    incomplete_events = {
        "turn.failed",
        "turn.cancelled",
        "model.stream.interrupted",
        "model.output.limited",
        "runtime.display_truncated",
        "tool.unknown",
    }
    # A provider may hit its output limit and then be continued by the
    # runner.  The limit event is useful evidence, but it is not an
    # incomplete task when the same turn subsequently reaches a clean
    # ``turn.completed`` event.  Keep a small state machine instead of
    # treating the mere presence of a limit event as terminal failure.
    incomplete = False
    for event_type in observed_events:
        if event_type in incomplete_events:
            incomplete = True
        elif event_type == "turn.completed":
            incomplete = False
    if incomplete and not any("truncat" in failure.casefold() for failure in failures):
        if any(
            event_type
            in {"model.stream.interrupted", "model.output.limited", "runtime.display_truncated"}
            for event_type in observed_events
        ):
            failures.append("task output was truncated or interrupted")
        else:
            failures.append("task did not reach a clean terminal state")
    return EvalOutcome(
        scenario_id=scenario.id,
        passed=not failures,
        failures=tuple(failures),
        final_text=final_text,
        tool_calls=tuple(started_tool_names),
        terminal_events=tuple(observed_events),
        incomplete=incomplete,
        settled_tool_results=tuple(settled_tool_results),
    )


def render_outcomes(outcomes: Sequence[EvalOutcome]) -> str:
    """Render a human-readable report with one line per outcome."""
    lines: list[str] = []
    for outcome in outcomes:
        prefix = f"[{'PASS' if outcome.passed else 'FAIL'}] {outcome.scenario_id}"
        if outcome.failures:
            lines.append(f"{prefix}: {'; '.join(outcome.failures)}")
        else:
            lines.append(prefix)
    return "\n".join(lines)


def _evaluate_turn(
    turn: EvalTurn,
    tool_calls: tuple[str, ...],
    final_text: str,
) -> tuple[str, ...]:
    failures: list[str] = []
    if not _is_prefix(turn.expected_tool_calls, tool_calls):
        failures.append(
            "expected tool calls "
            f"{list(turn.expected_tool_calls)} are not a prefix of this turn's actual "
            f"{list(tool_calls)}"
        )
    if turn.expected_final_text is not None and turn.expected_final_text not in final_text:
        failures.append(f"expected final text {turn.expected_final_text!r} was not produced")
    return tuple(failures)


def _is_prefix(expected: tuple[str, ...], actual: tuple[str, ...]) -> bool:
    return actual[: len(expected)] == expected


def _read_document(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            raw: object = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid scenario TOML {path.name}: {exc}") from None
    if not isinstance(raw, dict):
        raise ValueError(f"scenario TOML {path.name} must contain a table")
    return raw


def _scenario_from_document(document: dict[str, Any], source: str) -> EvalScenario:
    scenario_id = document.get("id")
    name = document.get("name")
    prompt = document.get("prompt")
    raw_turns = document.get("turns")
    if not isinstance(scenario_id, str) or not scenario_id:
        raise ValueError(f"{source}: scenario id must be a non-empty string")
    if not isinstance(name, str) or not name:
        raise ValueError(f"{source}: scenario name must be a non-empty string")
    if not isinstance(prompt, str) or not prompt:
        raise ValueError(f"{source}: scenario prompt must be a non-empty string")
    if not isinstance(raw_turns, list) or not raw_turns:
        raise ValueError(f"{source}: scenario turns must be a non-empty list")
    turns = tuple(
        _turn_from_mapping(turn, f"{source} turn {index + 1}")
        for index, turn in enumerate(raw_turns)
    )
    allowed_tools: frozenset[str] | None = None
    raw_allowed = document.get("allowed_tools")
    if raw_allowed is not None:
        if not isinstance(raw_allowed, list) or not raw_allowed:
            raise ValueError(f"{source}: allowed_tools must be a non-empty list of tool names")
        if any(not isinstance(tool, str) or not tool for tool in raw_allowed):
            raise ValueError(f"{source}: allowed_tools must be a non-empty list of tool names")
        allowed_tools = frozenset(raw_allowed)
    return EvalScenario(
        id=scenario_id,
        name=name,
        prompt=prompt,
        turns=turns,
        allowed_tools=allowed_tools,
    )


def _turn_from_mapping(mapping: object, source: str) -> EvalTurn:
    if not isinstance(mapping, dict):
        raise ValueError(f"{source}: turn must be a table")
    raw_deltas = mapping.get("deltas")
    if not isinstance(raw_deltas, list) or not raw_deltas:
        raise ValueError(f"{source}: turn deltas must be a non-empty list")
    deltas: list[dict[str, Any]] = []
    for index, delta in enumerate(raw_deltas):
        _delta_from_mapping(delta, f"{source} delta {index + 1}")
        deltas.append(dict(delta))
    expected_tool_calls: tuple[str, ...] = ()
    raw_expected = mapping.get("expected_tool_calls")
    if raw_expected is not None:
        if not isinstance(raw_expected, list) or any(
            not isinstance(tool, str) or not tool for tool in raw_expected
        ):
            raise ValueError(f"{source}: expected_tool_calls must be a list of tool names")
        expected_tool_calls = tuple(raw_expected)
    expected_final_text = mapping.get("expected_final_text")
    if expected_final_text is not None and not isinstance(expected_final_text, str):
        raise ValueError(f"{source}: expected_final_text must be a string")
    prompt = mapping.get("prompt")
    if prompt is not None and not isinstance(prompt, str):
        raise ValueError(f"{source}: prompt must be a string")
    return EvalTurn(
        deltas=tuple(dict(delta) for delta in raw_deltas),
        expected_tool_calls=expected_tool_calls,
        expected_final_text=expected_final_text,
        prompt=prompt,
    )


def _delta_from_mapping(mapping: object, source: str) -> ProviderDelta:
    if not isinstance(mapping, dict):
        raise ValueError(f"{source}: delta must be a table")
    raw_kind = mapping.get("kind")
    if not isinstance(raw_kind, str):
        raise ValueError(f"{source}: delta kind must be 'text', 'tool_call', or 'finish'")
    try:
        kind = DeltaKind(raw_kind)
    except ValueError:
        raise ValueError(f"{source}: delta kind must be 'text', 'tool_call', or 'finish'") from None
    if kind is DeltaKind.TEXT:
        text = mapping.get("text")
        if not isinstance(text, str):
            raise ValueError(f"{source}: text delta requires a text string")
        return ProviderDelta(kind=kind, text=text)
    if kind is DeltaKind.TOOL_CALL:
        raw_call = mapping.get("tool_call")
        if not isinstance(raw_call, dict):
            raise ValueError(f"{source}: tool_call delta requires a tool_call table")
        call_id = raw_call.get("id")
        name = raw_call.get("name")
        arguments = raw_call.get("arguments")
        if not isinstance(call_id, str) or not call_id:
            raise ValueError(f"{source}: tool_call requires a non-empty id")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{source}: tool_call requires a non-empty name")
        if not isinstance(arguments, dict):
            raise ValueError(f"{source}: tool_call requires an arguments table")
        return ProviderDelta(
            kind=kind,
            tool_call=ToolCall(id=call_id, name=name, arguments=dict(arguments)),
        )
    if kind is DeltaKind.FINISH:
        finish_reason = mapping.get("finish_reason")
        if finish_reason is not None and not isinstance(finish_reason, str):
            raise ValueError(f"{source}: finish_reason must be a string")
        return ProviderDelta(kind=kind, finish_reason=finish_reason)
    raise ValueError(f"{source}: delta kind {raw_kind!r} is not supported")
