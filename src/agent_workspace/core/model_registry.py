"""Latest-model registry with alias resolution and legacy warnings.

The registry is data, not policy. It helps profiles and UI know which model a
user configured without ever automatically changing that configuration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

_SCHEMA_VERSION = 1


class ModelRegistryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ModelSnapshot:
    id: str
    family: str
    status: str = "current"
    released_on: str = ""
    aliases: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.id or not self.family:
            raise ModelRegistryError("model snapshot id and family may not be empty")
        if self.status not in {"current", "legacy", "preview", "deprecated"}:
            raise ModelRegistryError(f"model snapshot status is invalid: {self.status}")
        if self.released_on:
            try:
                date.fromisoformat(self.released_on)
            except ValueError:
                raise ModelRegistryError("model snapshot release date must be ISO-8601") from None

    def matches(self, model: str) -> bool:
        lowered = model.casefold()
        return lowered == self.id.casefold() or any(
            lowered == alias.casefold() for alias in self.aliases
        )

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "family": self.family,
            "status": self.status,
            "released_on": self.released_on,
            "aliases": list(self.aliases),
            "notes": self.notes,
        }

    @classmethod
    def from_document(cls, value: object) -> ModelSnapshot:
        if not isinstance(value, dict):
            raise ModelRegistryError("model snapshot document must be an object")
        try:
            return cls(
                id=str(value["id"]),
                family=str(value["family"]),
                status=str(value.get("status", "current")),
                released_on=str(value.get("released_on", "")),
                aliases=tuple(str(item) for item in value.get("aliases", ())),
                notes=str(value.get("notes", "")),
            )
        except ModelRegistryError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ModelRegistryError("model snapshot document is invalid") from exc


@dataclass(frozen=True, slots=True)
class ResolvedModel:
    requested: str
    snapshot: ModelSnapshot
    alias_of: str | None = None

    @property
    def legacy(self) -> bool:
        return self.snapshot.status in {"legacy", "deprecated"}


class LatestModelRegistry:
    def __init__(self, snapshots: tuple[ModelSnapshot, ...] = ()) -> None:
        self._snapshots: dict[str, ModelSnapshot] = {}
        for snapshot in snapshots:
            self.register(snapshot)

    def register(self, snapshot: ModelSnapshot) -> None:
        if snapshot.id in self._snapshots:
            raise ModelRegistryError(f"duplicate model snapshot: {snapshot.id}")
        self._snapshots[snapshot.id] = snapshot

    def resolve(self, model: str) -> ResolvedModel | None:
        if not isinstance(model, str) or not model:
            raise ModelRegistryError("model id may not be empty")
        for snapshot in self._snapshots.values():
            if snapshot.matches(model):
                alias_of = None if snapshot.id.casefold() == model.casefold() else snapshot.id
                return ResolvedModel(model, snapshot, alias_of)
        return None

    def current(self, family: str) -> tuple[ModelSnapshot, ...]:
        return tuple(
            snapshot
            for snapshot in self._snapshots.values()
            if snapshot.family == family and snapshot.status in {"current", "preview"}
        )

    def snapshots(self) -> tuple[ModelSnapshot, ...]:
        return tuple(self._snapshots.values())

    def to_document(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "snapshots": [snapshot.to_document() for snapshot in self._snapshots.values()],
        }

    def save(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_document(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> LatestModelRegistry:
        source = Path(path)
        try:
            document = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRegistryError(f"cannot read model registry {source}: {exc}") from exc
        if not isinstance(document, dict) or document.get("schema_version") != _SCHEMA_VERSION:
            raise ModelRegistryError("model registry schema is unsupported")
        raw = document.get("snapshots")
        if not isinstance(raw, list):
            raise ModelRegistryError("model registry snapshots must be a list")
        return cls(tuple(ModelSnapshot.from_document(item) for item in raw))


def builtin_latest_models() -> LatestModelRegistry:
    return LatestModelRegistry(
        (
            ModelSnapshot(
                id="gpt-6-astra",
                family="openai-gpt",
                released_on="2026-09-03",
                notes=(
                    "On the official OpenAI endpoint, tool calling requires the Responses API. "
                    "https://platform.openai.com/docs/changelog "
                    "https://platform.openai.com/docs/models/gpt-6-astra"
                ),
            ),
            ModelSnapshot(
                id="gpt-6-sol",
                family="openai-gpt",
                released_on="2026-09-22",
                notes=(
                    'Chat Completions tool calling requires reasoning_effort="none"; '
                    "use Responses for reasoning with tools. "
                    "https://platform.openai.com/docs/changelog "
                    "https://platform.openai.com/docs/models/gpt-6-sol"
                ),
            ),
            ModelSnapshot(
                id="gpt-6-luna",
                family="openai-gpt",
                released_on="2026-09-22",
                notes=(
                    'Chat Completions tool calling requires reasoning_effort="none"; '
                    "use Responses for reasoning with tools. "
                    "https://platform.openai.com/docs/changelog "
                    "https://platform.openai.com/docs/models/gpt-6-luna"
                ),
            ),
            ModelSnapshot(
                id="gpt-5.6-sol",
                family="openai-gpt",
                released_on="2026-07-09",
                aliases=("gpt-5.6",),
            ),
            ModelSnapshot(
                id="gpt-5.6-terra",
                family="openai-gpt",
                released_on="2026-07-09",
            ),
            ModelSnapshot(
                id="gpt-5.6-luna",
                family="openai-gpt",
                released_on="2026-07-09",
                aliases=("luna-max",),
            ),
            ModelSnapshot(
                id="claude-fable-5-1",
                family="anthropic-claude",
                released_on="2026-09-01",
                notes="https://platform.claude.com/docs/en/models/fable-5-1/overview",
            ),
            ModelSnapshot(
                id="claude-opus-5-5",
                family="anthropic-claude",
                released_on="2026-09-22",
                notes="https://platform.claude.com/docs/en/models/opus-5-5/overview",
            ),
            ModelSnapshot(
                id="claude-sonnet-5-5",
                family="anthropic-claude",
                released_on="2026-09-28",
                notes="https://platform.claude.com/docs/en/models/sonnet-5-5/overview",
            ),
            ModelSnapshot(
                id="claude-opus-5",
                family="anthropic-claude",
                released_on="2026-07-24",
                aliases=("opus-5",),
                notes="https://platform.claude.com/docs/en/models/opus-5/overview",
            ),
            ModelSnapshot(
                id="claude-fable-5",
                family="anthropic-claude",
                released_on="2026-07-01",
                aliases=("fable-5",),
            ),
            ModelSnapshot(
                id="deepseek-v4-pro-0813",
                family="deepseek-v4",
                released_on="2026-08-13",
                aliases=("deepseek-v4-pro",),
                notes=(
                    "Snapshot ID used by hosted providers; "
                    "official DeepSeek API uses deepseek-v4-pro. "
                    "The official API may route that name to V4.1 Flash. "
                    "https://api-docs.deepseek.com/news/news260813 "
                    "https://api-docs.deepseek.com/news/news260910"
                ),
            ),
            ModelSnapshot(
                id="deepseek-flash",
                family="deepseek-v4.1",
                released_on="2026-09-10",
                aliases=("deepseek-v4-flash", "deepseek-v4.1-flash"),
                notes=(
                    "Current DeepSeek V4.1 Flash API model name. "
                    "https://api-docs.deepseek.com/news/news260910"
                ),
            ),
            ModelSnapshot(
                id="gemini-3.8-flash",
                family="google-gemini",
                released_on="2026-09-02",
                notes="https://ai.google.dev/gemini-api/docs/changelog",
            ),
            ModelSnapshot(
                id="gemini-3.7-flash",
                family="google-gemini",
                released_on="2026-08-13",
                aliases=("gemini-3.7",),
                notes="https://ai.google.dev/gemini-api/docs/changelog",
            ),
            ModelSnapshot(
                id="grok-4.7",
                family="xai-grok",
                released_on="2026-09-21",
                notes="https://docs.x.ai/docs/release-notes",
            ),
            ModelSnapshot(
                id="grok-4.6",
                family="xai-grok",
                released_on="2026-08-12",
                notes="https://docs.x.ai/docs/release-notes",
            ),
            ModelSnapshot(
                id="qwen3.8-max",
                family="alibaba-qwen",
                aliases=("qwen3.8",),
                notes=(
                    "Official model ID; initial release date not independently confirmed. "
                    "https://www.alibabacloud.com/help/en/model-studio/text-generation-model"
                ),
            ),
            ModelSnapshot(
                id="qwen3.8-max-0902",
                family="alibaba-qwen",
                notes=(
                    "Documented September snapshot ID. "
                    "https://www.alibabacloud.com/help/en/model-studio/text-generation-model"
                ),
            ),
            ModelSnapshot(
                id="qwen3.8-flash",
                family="alibaba-qwen",
                notes="https://www.alibabacloud.com/help/en/model-studio/text-generation-model",
            ),
            ModelSnapshot(
                id="qwen3.7-plus",
                family="alibaba-qwen",
                notes="https://www.alibabacloud.com/help/en/model-studio/text-generation-model",
            ),
            ModelSnapshot(
                id="kimi-k3",
                family="moonshot-kimi",
                released_on="2026-07-16",
                notes=(
                    "1M context; always reasons. Preserve complete assistant messages, including "
                    "reasoning_content, for multi-turn tool calls. Sampling parameters are fixed. "
                    "https://www.kimi.com/blog/kimi-k3 "
                    "https://platform.kimi.ai/docs/guide/kimi-k3-quickstart"
                ),
            ),
            ModelSnapshot(
                id="kimi-k2.7-code",
                family="moonshot-kimi",
                notes=(
                    "256K context; always reasons. Preserve reasoning_content and omit fixed "
                    "sampling parameters. The official product page was published on 2026-06-13; "
                    "the model's initial release date is not independently confirmed. "
                    "https://www.kimi.com/resources/kimi-k2-7-code "
                    "https://platform.kimi.ai/docs/guide/kimi-k2-7-code-quickstart"
                ),
            ),
            ModelSnapshot(
                id="kimi-k2.7-code-highspeed",
                family="moonshot-kimi",
                notes=(
                    "High-speed K2.7 Code variant with the same reasoning and tool-call behavior; "
                    "its initial release date is not independently confirmed. "
                    "https://platform.kimi.ai/docs/guide/kimi-k2-7-code-quickstart"
                ),
            ),
            ModelSnapshot(
                id="kimi-k2.6",
                family="moonshot-kimi",
                released_on="2026-04-20",
                notes=(
                    "256K context with text, image, and video input; thinking can be disabled. "
                    "Sampling parameters are fixed; thinking tool_choice supports auto or none. "
                    "https://www.kimi.com/blog/kimi-k2-6 "
                    "https://platform.kimi.ai/docs/guide/kimi-k2-6-quickstart"
                ),
            ),
            ModelSnapshot(
                id="glm-5.3",
                family="zai-glm",
                released_on="2026-08-18",
                notes=(
                    "Text-only, 1M context, and 128K output; thinking cannot be disabled. "
                    "Function calling supports tool_choice=auto. Available on Z.AI and BigModel. "
                    "https://docs.z.ai/release-notes/new-released "
                    "https://docs.z.ai/guides/llm/glm-5.3 "
                    "https://docs.bigmodel.cn/cn/guide/models/text/glm-5.3"
                ),
            ),
            ModelSnapshot(
                id="glm-5.3-flash",
                family="zai-glm",
                released_on="2026-08-26",
                notes=(
                    "Multimodal, 1M context, and 128K output; thinking cannot be disabled. "
                    "Available on Z.AI and BigModel; tool_stream enables streaming tool calls. "
                    "https://docs.z.ai/release-notes/new-released "
                    "https://docs.z.ai/guides/vlm/glm-5.3-flash "
                    "https://docs.bigmodel.cn/cn/guide/models/vlm/glm-5.3-flash"
                ),
            ),
            ModelSnapshot(
                id="glm-5.3-flashx",
                family="zai-glm",
                notes=(
                    "Faster GLM-5.3-Flash variant, available through the Z.AI and BigModel APIs. "
                    "Not available on the Coding Plan; its release date is not independently "
                    "confirmed. https://docs.z.ai/guides/vlm/glm-5.3-flash "
                    "https://docs.bigmodel.cn/cn/guide/models/vlm/glm-5.3-flash"
                ),
            ),
            ModelSnapshot(
                id="glm-5.2",
                family="zai-glm",
                released_on="2026-06-16",
                notes=(
                    "1M context for coding and long-horizon agent tasks. "
                    "https://docs.z.ai/release-notes/new-released "
                    "https://docs.z.ai/guides/llm/glm-5.2"
                ),
            ),
            ModelSnapshot(
                id="zai-glm-5-3",
                family="mistral",
                released_on="2026-09-15",
                aliases=("zai-glm-5", "zai-glm-latest"),
                notes=(
                    "GLM-5.3 hosted by Mistral; this date is the Mistral API release, "
                    "not the original Z.AI model release. "
                    "https://docs.mistral.ai/models/zai-glm-5-3"
                ),
            ),
            ModelSnapshot(
                id="zai-glm-5-2",
                family="mistral",
                released_on="2026-08-06",
                notes=(
                    "GLM-5.2 hosted by Mistral; this date is the Mistral API release, "
                    "not the original Z.AI model release. "
                    "https://docs.mistral.ai/models/zai-glm-5-2"
                ),
            ),
            ModelSnapshot(
                id="mistral-medium-3-5",
                family="mistral",
                released_on="2026-04-28",
                aliases=("mistral-medium-3", "mistral-medium-latest"),
                notes=(
                    "Supports function calling and adjustable reasoning_effort. "
                    "https://docs.mistral.ai/models/mistral-medium-3-5-26-04 "
                    "https://docs.mistral.ai/studio/conversations/reasoning"
                ),
            ),
            ModelSnapshot(
                id="mistral-small-2603",
                family="mistral",
                released_on="2026-03-16",
                aliases=("mistral-small-latest",),
                notes=(
                    "Mistral Small 4; supports adjustable reasoning_effort. "
                    "https://docs.mistral.ai/models/mistral-small-4-0-26-03 "
                    "https://docs.mistral.ai/studio/conversations/reasoning"
                ),
            ),
            ModelSnapshot(
                id="mistral-large-2512",
                family="mistral",
                released_on="2025-12-02",
                aliases=("mistral-large-latest",),
                notes=(
                    "Mistral Large 3; supports function calling. "
                    "https://docs.mistral.ai/models/mistral-large-3-25-12 "
                    "https://docs.mistral.ai/studio/conversations/function-calling"
                ),
            ),
            ModelSnapshot(
                id="MiniMax-M3",
                family="minimax",
                released_on="2026-06-01",
                notes=(
                    "Multimodal, 1M context, and tool calling through OpenAI-compatible "
                    "Chat Completions. Preserve complete assistant messages for tool calls. "
                    "https://platform.minimax.io/docs/release-notes/models "
                    "https://platform.minimax.io/docs/api-reference/text-openai-api"
                ),
            ),
            ModelSnapshot(
                id="MiniMax-M2.7",
                family="minimax",
                released_on="2026-03-18",
                notes=(
                    "204800-token context and tool calling through OpenAI-compatible "
                    "Chat Completions; preserve thinking content in assistant messages. "
                    "https://platform.minimax.io/docs/release-notes/models "
                    "https://platform.minimax.io/docs/api-reference/text-openai-api"
                ),
            ),
            ModelSnapshot(
                id="MiniMax-M2.7-highspeed",
                family="minimax",
                released_on="2026-03-18",
                notes=(
                    "Faster M2.7 variant with the same capabilities, "
                    "released with the M2.7 series. "
                    "https://platform.minimax.io/docs/release-notes/models "
                    "https://platform.minimax.io/docs/api-reference/text-openai-api"
                ),
            ),
            ModelSnapshot(
                id="MiniMax-M2.5",
                family="minimax",
                released_on="2026-02-12",
                notes=(
                    "204800-token context and tool calling through OpenAI-compatible Chat "
                    "Completions. https://www.minimax.io/news/minimax-m25 "
                    "https://platform.minimax.io/docs/api-reference/text-openai-api"
                ),
            ),
            ModelSnapshot(
                id="MiniMax-M2.5-highspeed",
                family="minimax",
                notes=(
                    "Faster M2.5 variant with the same capabilities; its initial release date "
                    "is not independently confirmed. "
                    "https://platform.minimax.io/docs/api-reference/text-openai-api"
                ),
            ),
            ModelSnapshot(
                id="command-a-plus-05-2026",
                family="cohere-command",
                released_on="2026-05-20",
                notes=(
                    "128K context, 64K output, vision, reasoning, and agentic tool use. "
                    "OpenAI-compatible API at https://api.cohere.ai/compatibility/v1. "
                    "https://docs.cohere.com/docs/command-a-plus "
                    "https://docs.cohere.com/docs/compatibility-api"
                ),
            ),
        )
    )


__all__ = [
    "LatestModelRegistry",
    "ModelRegistryError",
    "ModelSnapshot",
    "ResolvedModel",
    "builtin_latest_models",
]
