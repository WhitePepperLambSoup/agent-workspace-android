from __future__ import annotations

from agent_workspace.config import provider_origin

_LEVELS = ("low", "medium", "high", "xhigh", "max")


def _model_matches(model: str, names: tuple[str, ...]) -> bool:
    return any(model == name or model.startswith(f"{name}-") for name in names)


def supported_reasoning_efforts(protocol: str, base_url: str, model: str) -> tuple[str, ...]:
    """Documented native effort options; unknown routes retain provider defaults."""
    origin = provider_origin(base_url)
    if protocol == "openai-compatible" and origin == ("https", "api.openai.com", 443):
        if _model_matches(model, ("gpt-6-astra",)):
            return ("auto", *_LEVELS)
        if _model_matches(
            model, ("gpt-6-sol", "gpt-6-luna", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")
        ):
            return ("auto", "none", *_LEVELS)
    if (
        protocol == "openai-compatible"
        and origin == ("https", "api.deepseek.com", 443)
        and _model_matches(model, ("deepseek-flash", "deepseek-v4-pro"))
    ):
        return ("auto", "none", "low", "high", "max")
    if protocol == "anthropic" and _model_matches(
        model, ("claude-fable-5", "claude-opus-5", "claude-sonnet-5-5")
    ):
        return ("auto", *_LEVELS)
    return ("auto",)
