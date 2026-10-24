"""Semantic search for knowledge bases: passages and questions as sentence vectors from the
on-device embedding model (EmbeddingGemma, mobile_model_catalog), so a question also finds passages
that say the same thing in other words. BM25 (mobile_knowledge) still finds the exact words; the
search merges both.

Vectors are int8 unit vectors of DIMENSIONS values (LocalModelBridge.embed, KnowledgeVectors.kt):
a passage costs DIMENSIONS bytes, and the similarity of two is their dot product / 127².
"""

from __future__ import annotations

import json
import os
from typing import Any

MODEL_ID = "embeddinggemma-300m-q8-0"
# EmbeddingGemma's first 256 of 768 values (it is trained so that a prefix works on its own).
DIMENSIONS = 256
# Passages per call into the engine (one llama.cpp batch holds up to 16).
BATCH = 16


class _Engine:
    """The app's llama.cpp bridge (Android only)."""

    def __init__(self) -> None:
        self._bridge: Any = None

    def bridge(self) -> Any:
        if self._bridge is None and os.getenv("AGENT_WORKSPACE_EMBEDDED_PYTHON") == "chaquopy":
            from java import jclass

            self._bridge = jclass("com.agentworkspace.mobile.localmodels.LocalModelBridge")
        return self._bridge

    def available(self) -> bool:
        return self.bridge() is not None

    def embed(self, texts: list[str]) -> list[bytes]:
        data = bytes(self.bridge().embed(MODEL_ID, json.dumps(texts, ensure_ascii=False), DIMENSIONS))
        return [data[index:index + DIMENSIONS] for index in range(0, len(data), DIMENSIONS)]

    def similarities(self, query: bytes, matrix: bytes) -> list[float]:
        return list(self.bridge().similarities(query, matrix, DIMENSIONS))


# Replaced in tests by a stand-in with the same three methods.
engine: Any = _Engine()


def installed() -> bool:
    """Whether the embedding model is downloaded and verified."""
    from mobile_model_manager import get_model_manager

    try:
        get_model_manager().installed_path(MODEL_ID)
        return True
    except ValueError:
        return False


def download_state() -> dict[str, Any] | None:
    """The model's download as the local-models page shows it (state, progress, size, error)."""
    from mobile_model_manager import get_model_manager

    try:
        records = get_model_manager().snapshot().get("embedding_models", [])
    except ValueError:
        return None
    record = next((item for item in records if item.get("model_id") == MODEL_ID), None)
    if record is None:
        return None
    return {key: record.get(key) for key in ("state", "progress", "size_bytes", "error")}


def ready() -> bool:
    return engine.available() and installed()


def document_text(title: str, heading: str, text: str) -> str:
    """A passage as EmbeddingGemma expects a document."""
    body = f"{heading}\n{text}" if heading else text
    return f"title: {title or 'none'} | text: {body}"


def query_text(query: str) -> str:
    """A question as EmbeddingGemma expects a search query."""
    return f"task: search result | query: {query}"


def embed(texts: list[str]) -> list[bytes]:
    vectors = engine.embed(texts)
    if len(vectors) != len(texts) or any(len(vector) != DIMENSIONS for vector in vectors):
        raise ValueError("the embedding model returned vectors of the wrong size")
    return vectors


def similarities(query: bytes, matrix: bytes) -> list[float]:
    return engine.similarities(query, matrix) if matrix else []
