"""Privacy routing: one message answered by the on-device model while the conversation keeps its
cloud model (a message holding ID or bank card numbers, or one sent with no network). The runtime
uses the on-device model for that task only (mobile_runtime_controller._on_device_provider).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Most capable first; the first installed one that fits in free memory answers.
_PREFERENCE = (
    "qwen3.5-2b-q4-k-m",
    "qwen3.5-2b-q8-0",
    "qwen3.5-0.8b-q8-0",
    "qwen3.5-0.8b-q4-k-m",
    "qwen3-1.7b-q8-0",
    "qwen3-1.7b-q4-k-m",
    "qwen3-0.6b-q8-0",
    "qwen3-0.6b-q4-k-m",
)


def _available_memory() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def choose(models: list[dict[str, Any]], available: int | None) -> dict[str, Any] | None:
    """The model to answer with among installed [models]: the most capable that fits in
    [available] bytes (any, when unknown), else the smallest (loading checks memory again and says
    if it is short)."""
    rank = {model_id: index for index, model_id in enumerate(_PREFERENCE)}
    ranked = sorted(
        (model for model in models if model.get("installed") and model.get("kind", "model") == "model"),
        key=lambda model: rank.get(model["model_id"], len(rank)),
    )
    if not ranked:
        return None
    if available is None:
        return ranked[0]
    for model in ranked:
        if int(model.get("minimum_available_ram_bytes") or 0) <= available:
            return model
    return ranked[-1]


def local_model(manager: Any = None) -> dict[str, Any] | None:
    """The installed on-device model to answer with, or None when there is none."""
    if manager is None:
        from mobile_model_manager import get_model_manager

        try:
            manager = get_model_manager()
        except ValueError:
            return None
    return choose(manager.snapshot().get("models", []), _available_memory())


def status(manager: Any = None) -> dict[str, Any]:
    """For the composer: whether a message can be answered on the phone, and by which model."""
    model = local_model(manager)
    return {
        "local_model": model["model_id"] if model else None,
        "title": model.get("title") if model else None,
    }
