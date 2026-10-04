"""Model and provider routing primitives.

Routing rules are declarative and never construct providers themselves, so
callers can keep provider construction behind their existing factory and
credential boundaries.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from time import monotonic
from typing import Any


class ModelRoutingError(ValueError):
    pass


def _matches(pattern: str, model: str) -> bool:
    pattern = pattern.casefold()
    model = model.casefold()
    if pattern.endswith("*"):
        return model.startswith(pattern[:-1])
    if pattern.startswith("*"):
        return model.endswith(pattern[1:])
    return pattern == model


@dataclass(frozen=True, slots=True)
class ModelRoute:
    """A declarative route from model patterns to a provider/model pair."""

    id: str
    patterns: tuple[str, ...]
    provider_id: str
    model_id: str
    priority: int = 100
    enabled: bool = True
    task_kinds: tuple[str, ...] = ("default",)
    fallback_route_ids: tuple[str, ...] = ()
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ModelRoutingError("model route id may not be empty")
        if not self.patterns or any(not pattern for pattern in self.patterns):
            raise ModelRoutingError(f"model route {self.id!r} needs non-empty patterns")
        if not self.provider_id or not self.model_id:
            raise ModelRoutingError(f"model route {self.id!r} needs provider_id and model_id")
        if not self.task_kinds or any(not kind for kind in self.task_kinds):
            raise ModelRoutingError(f"model route {self.id!r} needs task kinds")

    def matches(self, model: str, task_kind: str = "default") -> bool:
        return (
            self.enabled
            and task_kind in self.task_kinds
            and any(_matches(pattern, model) for pattern in self.patterns)
        )

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "patterns": list(self.patterns),
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "priority": self.priority,
            "enabled": self.enabled,
            "task_kinds": list(self.task_kinds),
            "fallback_route_ids": list(self.fallback_route_ids),
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_document(cls, value: object) -> ModelRoute:
        if not isinstance(value, dict):
            raise ModelRoutingError("model route document must be an object")
        try:
            return cls(
                id=str(value["id"]),
                patterns=tuple(str(item) for item in value["patterns"]),
                provider_id=str(value["provider_id"]),
                model_id=str(value["model_id"]),
                priority=int(value.get("priority", 100)),
                enabled=bool(value.get("enabled", True)),
                task_kinds=tuple(str(item) for item in value.get("task_kinds", ("default",))),
                fallback_route_ids=tuple(str(item) for item in value.get("fallback_route_ids", ())),
                parameters=dict(value.get("parameters", {})),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ModelRoutingError("model route document is invalid") from exc


@dataclass(slots=True)
class ModelRouter:
    """Select enabled routes for a model and task kind."""

    routes: dict[str, ModelRoute] = field(default_factory=dict)

    def register(self, route: ModelRoute) -> None:
        if route.id in self.routes:
            raise ModelRoutingError(f"duplicate model route id: {route.id}")
        unknown = [route_id for route_id in route.fallback_route_ids if route_id not in self.routes]
        if unknown:
            raise ModelRoutingError(
                f"model route {route.id!r} references unknown fallbacks: {', '.join(unknown)}"
            )
        self.routes[route.id] = route

    def resolve(
        self,
        model: str,
        *,
        task_kind: str = "default",
        excluded: frozenset[str] = frozenset(),
        health: Mapping[str, ProviderHealth] | None = None,
        now: float | None = None,
    ) -> ModelRoute | None:
        matches = [
            route
            for route in self.routes.values()
            if route.id not in excluded
            and route.matches(model, task_kind)
            and (
                health is None
                or health.get(route.provider_id) is None
                or health[route.provider_id].can_route(now=now)
            )
        ]
        matches.sort(key=lambda route: (route.priority, route.id))
        return matches[0] if matches else None

    def fallback_chain(
        self,
        route: ModelRoute,
        model: str,
        *,
        task_kind: str = "default",
        max_hops: int = 8,
        health: Mapping[str, ProviderHealth] | None = None,
        now: float | None = None,
    ) -> tuple[ModelRoute, ...]:
        chain = [route]
        seen = {route.id}
        for _ in range(max_hops):
            next_route: ModelRoute | None = None
            for route_id in chain[-1].fallback_route_ids:
                candidate = self.routes.get(route_id)
                if (
                    candidate is not None
                    and candidate.id not in seen
                    and candidate.enabled
                    and task_kind in candidate.task_kinds
                    and (
                        health is None
                        or health.get(candidate.provider_id) is None
                        or health[candidate.provider_id].can_route(now=now)
                    )
                ):
                    next_route = candidate
                    break
            if next_route is None:
                break
            seen.add(next_route.id)
            chain.append(next_route)
        return tuple(chain)

    def explain(
        self,
        model: str,
        *,
        task_kind: str = "default",
        excluded: frozenset[str] = frozenset(),
        health: Mapping[str, ProviderHealth] | None = None,
        now: float | None = None,
        provider_snapshots: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Return a secret-free explanation for one routing decision."""
        candidates: list[dict[str, Any]] = []
        selected: ModelRoute | None = None
        ordered = sorted(self.routes.values(), key=lambda item: (item.priority, item.id))
        for route in ordered:
            reason = "eligible"
            if route.id in excluded:
                reason = "excluded"
            elif not route.enabled:
                reason = "disabled"
            elif task_kind not in route.task_kinds:
                reason = "task_kind_mismatch"
            elif not any(_matches(pattern, model) for pattern in route.patterns):
                reason = "model_mismatch"
            elif health is not None:
                provider_health = health.get(route.provider_id)
                if provider_health is not None and not provider_health.can_route(now=now):
                    reason = "provider_circuit_open"
            eligible = reason == "eligible"
            if eligible and selected is None:
                selected = route
                reason = "selected"
            candidate: dict[str, Any] = {
                "route_id": route.id,
                "provider_id": route.provider_id,
                "model_id": route.model_id,
                "priority": route.priority,
                "reason": reason,
                "selected": eligible and selected is route,
            }
            if provider_snapshots is not None:
                snapshot = provider_snapshots.get(route.provider_id)
                if snapshot is not None:
                    candidate["provider_snapshot"] = _safe_snapshot(snapshot)
            candidates.append(candidate)

        chain = (
            self.fallback_chain(
                selected,
                model,
                task_kind=task_kind,
                health=health,
                now=now,
            )
            if selected is not None
            else ()
        )
        selected_provider = selected.provider_id if selected is not None else None
        selected_model = selected.model_id if selected is not None else None
        return {
            "requested_model": model,
            "task_kind": task_kind,
            "selected_route_id": selected.id if selected is not None else None,
            "selected_provider_id": selected_provider,
            "selected_model_id": selected_model,
            "fallback_chain": [item.id for item in chain],
            "candidates": candidates,
            # Stable camelCase aliases make this DTO convenient for wire callers
            # while retaining Python-friendly keys for backend consumers.
            "requestedModel": model,
            "taskKind": task_kind,
            "selectedRouteId": selected.id if selected is not None else None,
            "selectedProviderId": selected_provider,
            "selectedModelId": selected_model,
        }

    explain_route = explain


@dataclass(slots=True)
class ProviderHealth:
    """Small failure/latency tracker used by routing pools."""

    provider_id: str
    failure_count: int = 0
    success_count: int = 0
    total_latency_seconds: float = 0.0
    cooldown_seconds: float = 30.0
    failure_threshold: int = 5
    _opened_at: float | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.provider_id:
            raise ValueError("provider id may not be empty")
        if self.cooldown_seconds < 0:
            raise ValueError("provider cooldown must be non-negative")
        if self.failure_threshold < 1:
            raise ValueError("provider failure threshold must be positive")

    def record_success(self, latency_seconds: float = 0.0) -> None:
        if latency_seconds < 0:
            raise ValueError("latency must be non-negative")
        self.success_count += 1
        self.total_latency_seconds += latency_seconds
        self.failure_count = 0
        self._opened_at = None

    def record_failure(self, *, now: float | None = None) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            current = monotonic() if now is None else now
            if self._opened_at is None or current - self._opened_at >= self.cooldown_seconds:
                self._opened_at = current

    def can_route(self, *, now: float | None = None) -> bool:
        if self.failure_count < self.failure_threshold:
            return True
        if self._opened_at is None:
            return False
        current = monotonic() if now is None else now
        return current - self._opened_at >= self.cooldown_seconds

    @property
    def circuit_open(self) -> bool:
        return not self.can_route()

    @property
    def healthy(self) -> bool:
        return self.can_route()

    @property
    def average_latency(self) -> float | None:
        return self.total_latency_seconds / self.success_count if self.success_count else None

    def snapshot(self, *, now: float | None = None) -> dict[str, Any]:
        """Return routing-safe health data suitable for audit events."""
        if self.failure_count < self.failure_threshold:
            status = "closed"
        elif self.can_route(now=now):
            status = "half_open"
        else:
            status = "open"
        return {
            "provider_id": self.provider_id,
            "status": status,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "average_latency_seconds": self.average_latency,
            "cooldown_seconds": self.cooldown_seconds,
        }


def _safe_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    """Keep provider capability/price/context metadata free of credentials."""
    allowed = {
        "provider_id",
        "model_id",
        "capabilities",
        "context_window",
        "price_input_usd_per_million",
        "price_output_usd_per_million",
        "currency",
        "updated_at",
    }
    return {str(key): item for key, item in value.items() if str(key) in allowed}


def builtin_model_routes() -> ModelRouter:
    """Conservative routes for current model families.

    All routes are declarative and disabled until the caller loads them; they
    never construct credentials or providers.
    """
    router = ModelRouter()
    router.register(
        ModelRoute(
            id="gpt56-luna",
            patterns=("gpt-5.6-luna*", "luna-max"),
            provider_id="openai",
            model_id="gpt-5.6-luna",
            priority=30,
            task_kinds=("default", "fast"),
        )
    )
    router.register(
        ModelRoute(
            id="gpt56-terra",
            patterns=("gpt-5.6-terra*",),
            provider_id="openai",
            model_id="gpt-5.6-terra",
            priority=20,
            fallback_route_ids=("gpt56-luna",),
        )
    )
    router.register(
        ModelRoute(
            id="gpt56-sol",
            patterns=("gpt-5.6-sol*", "gpt-5.6"),
            provider_id="openai",
            model_id="gpt-5.6-sol",
            priority=10,
            fallback_route_ids=("gpt56-terra",),
        )
    )
    router.register(
        ModelRoute(
            id="claude-opus5",
            patterns=("claude-opus-5*", "opus-5"),
            provider_id="anthropic",
            model_id="claude-opus-5",
            priority=20,
        )
    )
    router.register(
        ModelRoute(
            id="claude-fable5",
            patterns=("claude-fable-5*", "fable-5"),
            provider_id="anthropic",
            model_id="claude-fable-5",
            priority=10,
            fallback_route_ids=("claude-opus5",),
        )
    )
    router.register(
        ModelRoute(
            id="deepseek-flash",
            patterns=("deepseek-flash*", "deepseek-v4-flash*", "deepseek-v4.1-flash*"),
            provider_id="deepseek",
            model_id="deepseek-flash",
            priority=30,
        )
    )
    router.register(
        ModelRoute(
            id="deepseek-v4-pro",
            patterns=("deepseek-v4-pro*",),
            provider_id="deepseek",
            model_id="deepseek-v4-pro-0813",
            priority=10,
            fallback_route_ids=("deepseek-flash",),
        )
    )
    router.register(
        ModelRoute(
            id="gemini37-flash",
            patterns=("gemini-3.7-flash*", "gemini-3.7"),
            provider_id="google",
            model_id="gemini-3.7-flash",
            priority=20,
        )
    )
    router.register(
        ModelRoute(
            id="grok46",
            patterns=("grok-4.6*",),
            provider_id="xai",
            model_id="grok-4.6",
            priority=20,
        )
    )
    router.register(
        ModelRoute(
            id="qwen38-max",
            patterns=("qwen3.8-max*", "qwen3.8"),
            provider_id="dashscope",
            model_id="qwen3.8-max",
            priority=20,
        )
    )
    router.register(
        ModelRoute(
            id="kimi-k3",
            patterns=("kimi-k3*",),
            provider_id="moonshot",
            model_id="kimi-k3",
            priority=20,
        )
    )
    return router


__all__ = [
    "ModelRoute",
    "ModelRouter",
    "ModelRoutingError",
    "ProviderHealth",
    "builtin_model_routes",
]
