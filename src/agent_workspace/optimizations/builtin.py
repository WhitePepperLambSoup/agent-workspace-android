"""Built-in, user-selectable model optimization presets.

These presets encode conservative defaults for current model families. They
are loaded by applications that call :func:`default_model_optimization_registry`
explicitly; workspace ``.agent/optimizations.json`` remains the primary user
configuration and always takes precedence when present.
"""

from __future__ import annotations

from .profiles import ModelOptimizationRegistry, OptimizationProfile


def default_model_optimization_registry() -> ModelOptimizationRegistry:
    registry = ModelOptimizationRegistry()
    registry.register(
        OptimizationProfile(
            id="deepseek-v4-anchored-standard",
            name="DeepSeek V4.1 Flash anchored bootstrap",
            version=1,
            models=("deepseek-flash*", "deepseek-v4*"),
            type="anchored_tool_bootstrap",
            enabled=True,
            parameters={
                "bootstrap_tools": ("read_file", "write_file"),
                "promote_on": "either",
                "suppress_context_sources": ("agent-instructions", "skill-catalog"),
            },
            description=(
                "First request uses a minimal tool catalog and no auto-injected "
                "context; the full catalog is restored after promotion."
            ),
        )
    )
    registry.register(
        OptimizationProfile(
            id="deepseek-v4-zero-anchored",
            name="DeepSeek V4.1 Flash zero-tool anchor",
            version=1,
            models=("deepseek-flash*", "deepseek-v4-pro*"),
            type="zero_tool_bootstrap",
            enabled=False,
            parameters={"anchor_prompt": "This round is a test. Tools are not open yet."},
            description=(
                "Anchor the first model request with zero tools before opening the catalog."
            ),
        )
    )
    registry.register(
        OptimizationProfile(
            id="deepseek-v4-whoami",
            name="DeepSeek V4.1 Flash whoami warm-up",
            version=1,
            models=("deepseek-flash*", "deepseek-v4-pro*"),
            type="whoami_bootstrap",
            enabled=False,
            description="Warm the session with a natural self-introduction turn.",
        )
    )
    registry.register(
        OptimizationProfile(
            id="gpt56-luna-fast-cap",
            name="GPT-5.6 Luna output cap",
            version=1,
            models=("gpt-5.6-luna*", "luna-max"),
            type="request_cap",
            enabled=False,
            parameters={"max_output_tokens": 4096},
            description="Bound cheap Luna worker turns to keep latency predictable.",
        )
    )
    registry.register(
        OptimizationProfile(
            id="gpt56-sol-max-effort",
            name="GPT-5.6 Sol reasoning effort",
            version=1,
            models=("gpt-5.6-sol*", "gpt-5.6"),
            type="reasoning_effort",
            enabled=False,
            parameters={"effort": "max"},
            description="Ask Sol to use maximum reasoning effort for hard orchestrator turns.",
        )
    )
    registry.register(
        OptimizationProfile(
            id="claude-opus5-conservative-cap",
            name="Claude Opus 5 conservative output cap",
            version=1,
            models=("claude-opus-5*", "opus-5"),
            type="request_cap",
            enabled=False,
            parameters={"max_output_tokens": 8192},
            description="Keep execution-tier Opus 5 turns bounded and cheap.",
        )
    )
    registry.register(
        OptimizationProfile(
            id="claude-fable5-thinking",
            name="Claude Fable 5 extended thinking",
            version=1,
            models=("claude-fable-5*", "fable-5"),
            type="anthropic_thinking",
            enabled=False,
            parameters={"thinking_budget_tokens": 16384, "temperature": 1.0},
            description="Enable Anthropic extended thinking with a bounded budget.",
        )
    )
    registry.register(
        OptimizationProfile(
            id="gemini37-flash-fast-cap",
            name="Gemini 3.7 Flash output cap",
            version=1,
            models=("gemini-3.7-flash*", "gemini-3.7"),
            type="request_cap",
            enabled=False,
            parameters={"max_output_tokens": 8192},
            description="Bound Gemini Flash fast-execution turns.",
        )
    )
    registry.register(
        OptimizationProfile(
            id="grok46-fast-cap",
            name="Grok 4.6 output cap",
            version=1,
            models=("grok-4.6*",),
            type="request_cap",
            enabled=False,
            parameters={"max_output_tokens": 8192},
            description="Bound Grok fast-execution turns.",
        )
    )
    registry.register(
        OptimizationProfile(
            id="qwen38-max-effort",
            name="Qwen3.8-Max reasoning effort",
            version=1,
            models=("qwen3.8-max*", "qwen3.8"),
            type="reasoning_effort",
            enabled=False,
            parameters={"effort": "high"},
            description="Request high reasoning effort on OpenAI-compatible Qwen routes.",
        )
    )
    registry.register(
        OptimizationProfile(
            id="kimi-k3-fast-cap",
            name="Kimi K3 output cap",
            version=1,
            models=("kimi-k3*",),
            type="request_cap",
            enabled=False,
            parameters={"max_output_tokens": 8192},
            description="Bound Kimi K3 execution turns.",
        )
    )
    return registry


__all__ = ["default_model_optimization_registry"]
