"""Model-specific optimization profiles.

Model behavior changes frequently. Every optimization in this package is an
optional, versioned profile that users can enable per workspace. Profiles are
selected by model id patterns and are validated against a manifest before use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SCHEMA_VERSION = 1
_PROFILE_KEYS = {
    "id",
    "name",
    "version",
    "models",
    "type",
    "enabled",
    "parameters",
    "requires",
    "conflicts",
    "description",
}
_TYPES = {
    "anchored_tool_bootstrap",
    "request_cap",
    "reasoning_effort",
    "zero_tool_bootstrap",
    "whoami_bootstrap",
    "anthropic_thinking",
}
_BOOTSTRAP_KEYS = {
    "bootstrap_tools",
    "promote_on",
    "suppress_context_sources",
    "bootstrap_max_tokens",
}
_ANCHOR_KEYS = {"anchor_prompt", "include_subagents"}


class OptimizationProfileError(ValueError):
    """Raised when an optimization profile or manifest is invalid."""


def _require_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OptimizationProfileError(f"{label} must be a mapping")
    return value


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise OptimizationProfileError(f"{label} must be a list of non-empty strings")
    return tuple(value)


@dataclass(frozen=True, slots=True)
class OptimizationProfile:
    """One optional model behavior module."""

    id: str
    name: str
    version: int
    models: tuple[str, ...]
    type: str
    enabled: bool = True
    parameters: dict[str, Any] = field(default_factory=dict)
    requires: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    description: str = ""

    @classmethod
    def from_mapping(cls, document: dict[str, Any]) -> OptimizationProfile:
        unknown = set(document) - _PROFILE_KEYS
        if unknown:
            raise OptimizationProfileError(
                f"optimization profile {document.get('id')!r} has unknown keys: "
                f"{', '.join(sorted(unknown))}"
            )
        profile_id = document.get("id")
        name = document.get("name")
        if not isinstance(profile_id, str) or not profile_id:
            raise OptimizationProfileError("optimization profile id may not be empty")
        if not isinstance(name, str) or not name.strip():
            raise OptimizationProfileError(f"optimization profile {profile_id!r} needs a name")
        version = document.get("version")
        if type(version) is not int or version < 1:
            raise OptimizationProfileError(
                f"optimization profile {profile_id!r} version must be a positive integer"
            )
        models = _string_list(document.get("models"), f"optimization profile {profile_id!r} models")
        if not models:
            raise OptimizationProfileError(
                f"optimization profile {profile_id!r} must target at least one model"
            )
        profile_type = document.get("type")
        if profile_type not in _TYPES:
            raise OptimizationProfileError(
                f"optimization profile {profile_id!r} has unsupported type {profile_type!r}"
            )
        parameters = _require_mapping(
            document.get("parameters", {}),
            f"optimization profile {profile_id!r} parameters",
        )
        profile = cls(
            id=profile_id,
            name=name,
            version=version,
            models=models,
            type=str(profile_type),
            enabled=bool(document.get("enabled", True)),
            parameters=dict(parameters),
            requires=_string_list(
                document.get("requires"), f"optimization profile {profile_id!r} requires"
            ),
            conflicts=_string_list(
                document.get("conflicts"), f"optimization profile {profile_id!r} conflicts"
            ),
            description=str(document.get("description") or ""),
        )
        profile.validate()
        return profile

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.type == "anchored_tool_bootstrap":
            unknown = set(self.parameters) - _BOOTSTRAP_KEYS
            if unknown:
                raise OptimizationProfileError(
                    f"optimization profile {self.id!r} has unknown parameters: "
                    f"{', '.join(sorted(unknown))}"
                )
            tools = _string_list(
                self.parameters.get("bootstrap_tools"),
                f"optimization profile {self.id!r} bootstrap_tools",
            )
            if not tools:
                raise OptimizationProfileError(
                    f"optimization profile {self.id!r} bootstrap_tools may not be empty"
                )
            promote_on = self.parameters.get("promote_on", "either")
            if promote_on not in {"either", "tool-call", "assistant-message"}:
                raise OptimizationProfileError(
                    f"optimization profile {self.id!r} promote_on must be one of "
                    "'either', 'tool-call', or 'assistant-message'"
                )
            suppressed = _string_list(
                self.parameters.get("suppress_context_sources"),
                f"optimization profile {self.id!r} suppress_context_sources",
            )
            self.parameters["bootstrap_tools"] = tools
            self.parameters["promote_on"] = promote_on
            if "suppress_context_sources" not in self.parameters:
                # Anchored-standard suppresses the two automatic context
                # injections by default; an explicit empty list opts back in.
                self.parameters["suppress_context_sources"] = (
                    "agent-instructions",
                    "skill-catalog",
                )
            else:
                self.parameters["suppress_context_sources"] = suppressed
            cap = self.parameters.get("bootstrap_max_tokens")
            if cap is not None and (type(cap) is not int or isinstance(cap, bool) or cap < 1):
                raise OptimizationProfileError(
                    f"optimization profile {self.id!r} bootstrap_max_tokens must be "
                    "a positive integer"
                )
        elif self.type in {"zero_tool_bootstrap", "whoami_bootstrap"}:
            unknown = set(self.parameters) - _ANCHOR_KEYS
            if unknown:
                raise OptimizationProfileError(
                    f"optimization profile {self.id!r} has unknown parameters: "
                    f"{', '.join(sorted(unknown))}"
                )
            anchor_prompt = self.parameters.get(
                "anchor_prompt",
                "This round is a test. Tools are not open yet; all tools will open next round."
                if self.type == "zero_tool_bootstrap"
                else "你是谁",
            )
            if not isinstance(anchor_prompt, str) or not anchor_prompt.strip():
                raise OptimizationProfileError(
                    f"optimization profile {self.id!r} anchor_prompt must be non-empty"
                )
            if not isinstance(self.parameters.get("include_subagents", False), bool):
                raise OptimizationProfileError(
                    f"optimization profile {self.id!r} include_subagents must be a bool"
                )
            self.parameters["anchor_prompt"] = anchor_prompt.strip()
        elif self.type == "anthropic_thinking":
            unknown = set(self.parameters) - {"thinking_budget_tokens", "temperature"}
            if unknown:
                raise OptimizationProfileError(
                    f"optimization profile {self.id!r} has unknown parameters: "
                    f"{', '.join(sorted(unknown))}"
                )
            budget = self.parameters.get("thinking_budget_tokens")
            if (
                budget is None
                or type(budget) is not int
                or isinstance(budget, bool)
                or not 1024 <= budget <= 64000
            ):
                raise OptimizationProfileError(
                    f"optimization profile {self.id!r} thinking_budget_tokens must be "
                    "from 1024 to 64000"
                )
            temperature = self.parameters.get("temperature", 1.0)
            if (
                isinstance(temperature, bool)
                or not isinstance(temperature, (int, float))
                or not 0 <= temperature <= 1
            ):
                raise OptimizationProfileError(
                    f"optimization profile {self.id!r} temperature must be from 0 to 1"
                )
        elif self.type == "request_cap":
            cap = self.parameters.get("max_output_tokens")
            if cap is None or type(cap) is not int or isinstance(cap, bool) or cap < 1:
                raise OptimizationProfileError(
                    f"optimization profile {self.id!r} requires a positive "
                    "max_output_tokens parameter"
                )
        elif self.type == "reasoning_effort":
            effort = self.parameters.get("effort")
            if effort not in {"off", "low", "medium", "high", "max"}:
                raise OptimizationProfileError(
                    f"optimization profile {self.id!r} effort must be one of "
                    "'off', 'low', 'medium', 'high', or 'max'"
                )

    def matches(self, model: str) -> bool:
        lowered = model.casefold()
        return any(_pattern_matches(pattern, lowered) for pattern in self.models)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "models": list(self.models),
            "type": self.type,
            "enabled": self.enabled,
            "parameters": dict(self.parameters),
            "requires": list(self.requires),
            "conflicts": list(self.conflicts),
            "description": self.description,
        }


def _pattern_matches(pattern: str, model: str) -> bool:
    pattern = pattern.casefold()
    if pattern.endswith("*"):
        return model.startswith(pattern[:-1])
    if pattern.startswith("*"):
        return model.endswith(pattern[1:])
    return model == pattern


@dataclass(slots=True)
class ModelOptimizationRegistry:
    """Validated, conflict-checked collection of optimization profiles."""

    profiles: dict[str, OptimizationProfile] = field(default_factory=dict)

    def register(self, profile: OptimizationProfile) -> None:
        profile.validate()
        existing = self.profiles.get(profile.id)
        if existing is not None and existing.version > profile.version:
            raise OptimizationProfileError(
                f"optimization profile {profile.id!r} would downgrade version "
                f"{existing.version} to {profile.version}"
            )
        for required in profile.requires:
            if required not in self.profiles:
                raise OptimizationProfileError(
                    f"optimization profile {profile.id!r} requires missing profile {required!r}"
                )
        for conflict in profile.conflicts:
            if conflict in self.profiles:
                raise OptimizationProfileError(
                    f"optimization profile {profile.id!r} conflicts with {conflict!r}"
                )
        self.profiles[profile.id] = profile

    def remove(self, profile_id: str) -> None:
        dependents = [
            profile.id for profile in self.profiles.values() if profile_id in profile.requires
        ]
        if dependents:
            raise OptimizationProfileError(
                f"cannot remove optimization profile {profile_id!r}; required by "
                f"{', '.join(dependents)}"
            )
        self.profiles.pop(profile_id, None)

    def resolve(self, model: str, *, enabled_only: bool = True) -> tuple[OptimizationProfile, ...]:
        matching = [
            profile
            for profile in self.profiles.values()
            if profile.matches(model) and (not enabled_only or profile.enabled)
        ]
        matching.sort(key=lambda profile: (profile.version, profile.id))
        return tuple(matching)

    def to_document(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "profiles": [profile.to_mapping() for profile in self.profiles.values()],
        }

    def save(self, path: str | Path) -> None:
        import json

        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_document(), indent=2, sort_keys=True) + "\n"
        temporary = destination.with_suffix(f"{destination.suffix}.tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(destination)


def load_optimization_registry(path: str | Path) -> ModelOptimizationRegistry:
    """Load profiles from a JSON document created by ``save``."""
    import json

    source = Path(path)
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OptimizationProfileError(
            f"cannot read optimization profiles {source}: {exc}"
        ) from exc
    document = _require_mapping(document, "optimization profile document")
    if document.get("schema_version") != _SCHEMA_VERSION:
        raise OptimizationProfileError(
            f"optimization profile schema {document.get('schema_version')!r} is unsupported"
        )
    raw_profiles = document.get("profiles")
    if not isinstance(raw_profiles, list):
        raise OptimizationProfileError("optimization profile document 'profiles' must be a list")
    registry = ModelOptimizationRegistry()
    for raw in raw_profiles:
        profile = OptimizationProfile.from_mapping(_require_mapping(raw, "profile entry"))
        registry.register(profile)
    return registry


def update_optimization_registry(
    current: ModelOptimizationRegistry,
    incoming: ModelOptimizationRegistry,
) -> ModelOptimizationRegistry:
    """Return a registry that merges incoming profiles into ``current``.

    Incoming versions equal to the current version are accepted as identical
    refreshes; older versions are rejected by ``register``.
    """
    updated = ModelOptimizationRegistry(dict(current.profiles))
    for profile in incoming.profiles.values():
        updated.register(profile)
    return updated


__all__ = [
    "ModelOptimizationRegistry",
    "OptimizationProfile",
    "OptimizationProfileError",
    "load_optimization_registry",
    "update_optimization_registry",
]
