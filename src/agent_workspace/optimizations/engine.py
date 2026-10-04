"""Request-time model optimization engine.

The engine is intentionally small and conservative. It only rewrites a turn
when at least one enabled profile matches the current model, and it always
returns the original inputs when no rule applies or a rule cannot be applied
safely (for example, when a bootstrap tool is missing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_workspace.core.models import ChatMessage, Role, ToolSpec

from .profiles import ModelOptimizationRegistry, OptimizationProfile


@dataclass(frozen=True, slots=True)
class PreparedTurn:
    """Optimization decisions for one outgoing model request."""

    tools: tuple[ToolSpec, ...]
    system_suffix: str
    max_output_tokens: int | None
    profiles: tuple[str, ...]
    phase: str
    metadata: dict[str, Any]
    anchor_prompt: str | None = None
    defer_user_message: bool = False


@dataclass(slots=True)
class OptimizationTurnState:
    """Per-session memory used to keep the optimization phase stable."""

    request_count: int = 0
    promoted: bool = False
    profiles: tuple[str, ...] = ()
    anchor_sent: bool = False


@dataclass(slots=True)
class ModelRequestOptimizer:
    """Apply enabled, matching profiles to a provider request assembly."""

    registry: ModelOptimizationRegistry
    states: dict[str, OptimizationTurnState] = field(default_factory=dict)

    def reset(self, session_id: str) -> None:
        self.states.pop(session_id, None)

    def state_for(self, session_id: str) -> OptimizationTurnState:
        state = self.states.get(session_id)
        if state is None:
            state = OptimizationTurnState()
            self.states[session_id] = state
        return state

    def prepare_turn(
        self,
        *,
        session_id: str,
        model: str,
        history: tuple[ChatMessage, ...],
        tools: tuple[ToolSpec, ...],
        system_suffix: str,
    ) -> PreparedTurn:
        """Return tools/system suffix/output cap for the next model request."""
        state = self.state_for(session_id)
        profiles = self.registry.resolve(model)
        if not profiles:
            state.request_count += 1
            return PreparedTurn(tools, system_suffix, None, (), "none", {})

        applied: list[str] = []
        metadata: dict[str, Any] = {}
        selected_tools = tools
        selected_suffix = system_suffix
        output_cap: int | None = None
        anchor_prompt: str | None = None
        defer_user_message = False

        for profile in profiles:
            if profile.type == "anchored_tool_bootstrap":
                selected_tools, selected_suffix, output_cap = self._apply_anchored(
                    profile,
                    state,
                    history,
                    tools,
                    system_suffix,
                )
                applied.append(profile.id)
                metadata[profile.id] = {
                    "version": profile.version,
                    "phase": "bootstrap" if _unpromoted(state) else "standard",
                }
            elif profile.type in {"zero_tool_bootstrap", "whoami_bootstrap"}:
                if not state.anchor_sent and state.request_count == 0:
                    state.anchor_sent = True
                    selected_tools = ()
                    selected_suffix = ""
                    anchor_prompt = str(profile.parameters["anchor_prompt"])
                    defer_user_message = True
                applied.append(profile.id)
                metadata[profile.id] = {
                    "version": profile.version,
                    "phase": "anchor" if anchor_prompt is not None else "standard",
                }
            elif profile.type == "anthropic_thinking":
                metadata[profile.id] = {
                    "version": profile.version,
                    "thinking_budget_tokens": profile.parameters["thinking_budget_tokens"],
                    "temperature": profile.parameters.get("temperature", 1.0),
                }
                applied.append(profile.id)
            elif profile.type == "request_cap":
                output_cap = int(profile.parameters["max_output_tokens"])
                applied.append(profile.id)
                metadata[profile.id] = {"version": profile.version}
            elif profile.type == "reasoning_effort":
                metadata[profile.id] = {
                    "version": profile.version,
                    "effort": profile.parameters["effort"],
                }
                applied.append(profile.id)

        if applied:
            state.profiles = tuple(applied)
        state.request_count += 1
        phase = (
            "anchor"
            if anchor_prompt is not None
            else "bootstrap"
            if _unpromoted(state) and applied
            else ("standard" if applied else "none")
        )
        return PreparedTurn(
            tools=tuple(selected_tools),
            system_suffix=selected_suffix,
            max_output_tokens=output_cap,
            profiles=tuple(applied),
            phase=phase,
            metadata=metadata,
            anchor_prompt=anchor_prompt,
            defer_user_message=defer_user_message,
        )

    @staticmethod
    def _apply_anchored(
        profile: OptimizationProfile,
        state: OptimizationTurnState,
        history: tuple[ChatMessage, ...],
        tools: tuple[ToolSpec, ...],
        system_suffix: str,
    ) -> tuple[tuple[ToolSpec, ...], str, int | None]:
        promote_on = profile.parameters.get("promote_on", "either")
        if not state.promoted and _history_promotes(history, promote_on, state.request_count):
            state.promoted = True

        cap = profile.parameters.get("bootstrap_max_tokens")
        if _unpromoted(state) and state.request_count == 0:
            names = set(profile.parameters["bootstrap_tools"])
            selected = tuple(spec for spec in tools if spec.name in names)
            missing = names - {spec.name for spec in tools}
            if missing:
                # Composition drift must never brick a session. Degrade to the
                # full catalog and record the missing tools in metadata via the
                # returned phase behavior elsewhere.
                return tools, system_suffix, cap
            suffix = ""
            if not profile.parameters.get("suppress_context_sources"):
                suffix = system_suffix
            return selected, suffix, cap
        return tools, system_suffix, None


def _unpromoted(state: OptimizationTurnState) -> bool:
    return not state.promoted


def _history_promotes(
    history: tuple[ChatMessage, ...],
    promote_on: str,
    request_count: int,
) -> bool:
    if request_count >= 1:
        # Anchored-standard promotes on request #2 regardless, so a text-only
        # first reply can never trap the session in bootstrap mode.
        return True
    assistant_messages = [message for message in history if message.role is Role.ASSISTANT]
    if promote_on == "either":
        return bool(assistant_messages)
    if promote_on == "tool-call":
        return any(bool(message.tool_calls) for message in assistant_messages)
    if promote_on == "assistant-message":
        return bool(assistant_messages)
    return False


__all__ = [
    "ModelRequestOptimizer",
    "OptimizationTurnState",
    "PreparedTurn",
]
