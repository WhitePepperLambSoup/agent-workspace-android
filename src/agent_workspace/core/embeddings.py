from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

_MAX_EMBEDDING_TEXT_BYTES = 32 * 1024
_MAX_EMBEDDING_BATCH = 64
_TIMEOUT_SECONDS = 30.0
_INDEX_VERSION = 1


class EmbeddingsUnavailableError(RuntimeError):
    pass


class EmbeddingIndexError(ValueError):
    """Raised when a persisted embedding index is malformed or unusable."""


@dataclass(frozen=True, slots=True)
class EmbeddingRecord:
    item_id: str
    text_sha256: str
    vector: tuple[float, ...]
    updated_at: float

    def to_document(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "text_sha256": self.text_sha256,
            "vector": list(self.vector),
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class EmbeddingHit:
    item_id: str
    score: float


def _text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddingIndex:
    """Dependency-free durable vector index for local semantic projections."""

    def __init__(self, path: str | Path, *, clock: Any = time.time) -> None:
        self.path = Path(path)
        self._clock = clock
        self._records: dict[str, EmbeddingRecord] = {}
        self._dimension: int | None = None
        self._load()

    @property
    def dimension(self) -> int | None:
        return self._dimension

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EmbeddingIndexError(f"cannot read embedding index: {exc}") from exc
        if not isinstance(document, dict) or document.get("version") != _INDEX_VERSION:
            raise EmbeddingIndexError("embedding index version is unsupported")
        raw_records = document.get("records")
        if not isinstance(raw_records, list):
            raise EmbeddingIndexError("embedding index must declare a records array")
        for raw in raw_records:
            record = self._parse_record(raw)
            if record.item_id in self._records:
                raise EmbeddingIndexError(f"duplicate embedding index item: {record.item_id}")
            self._set_dimension(record.vector)
            self._records[record.item_id] = record

    @staticmethod
    def _parse_record(raw: object) -> EmbeddingRecord:
        if not isinstance(raw, dict):
            raise EmbeddingIndexError("embedding index record is invalid")
        item_id = raw.get("item_id")
        digest = raw.get("text_sha256")
        vector = raw.get("vector")
        updated = raw.get("updated_at")
        if (
            not isinstance(item_id, str)
            or not item_id
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not isinstance(vector, list)
            or not vector
            or not isinstance(updated, (int, float))
        ):
            raise EmbeddingIndexError("embedding index record is invalid")
        try:
            values = tuple(float(value) for value in vector)
            timestamp = float(updated)
        except (TypeError, ValueError) as exc:
            raise EmbeddingIndexError("embedding index record is invalid") from exc
        if any(not math.isfinite(value) for value in values) or timestamp < 0:
            raise EmbeddingIndexError("embedding index record is invalid")
        return EmbeddingRecord(item_id, digest, values, timestamp)

    def _set_dimension(self, vector: tuple[float, ...] | list[float]) -> None:
        dimension = len(vector)
        if dimension == 0:
            raise EmbeddingIndexError("embedding vector may not be empty")
        if self._dimension is None:
            self._dimension = dimension
        elif self._dimension != dimension:
            raise EmbeddingIndexError("embedding vectors must use one dimension")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(
                    {
                        "version": _INDEX_VERSION,
                        "dimension": self._dimension,
                        "records": [
                            self._records[item_id].to_document()
                            for item_id in sorted(self._records)
                        ],
                    },
                    stream,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                stream.write("\n")
            temporary.replace(self.path)
        except OSError as exc:
            raise EmbeddingIndexError(f"cannot save embedding index: {exc}") from exc
        finally:
            if temporary is not None and temporary.exists():
                with suppress(OSError):
                    temporary.unlink()

    def upsert(
        self,
        item_id: str,
        text: str,
        vector: list[float] | tuple[float, ...],
    ) -> EmbeddingRecord:
        if not isinstance(item_id, str) or not item_id.strip() or len(item_id) > 256:
            raise EmbeddingIndexError("embedding item id must be a non-empty string")
        if not isinstance(text, str) or not text:
            raise EmbeddingIndexError("embedding text may not be empty")
        try:
            values = tuple(float(value) for value in vector)
        except (TypeError, ValueError) as exc:
            raise EmbeddingIndexError("embedding vector is invalid") from exc
        if not values or any(not math.isfinite(value) for value in values):
            raise EmbeddingIndexError("embedding vector is invalid")
        self._set_dimension(values)
        record = EmbeddingRecord(item_id, _text_digest(text), values, float(self._clock()))
        self._records[item_id] = record
        self.save()
        return record

    def get(self, item_id: str) -> EmbeddingRecord | None:
        return self._records.get(item_id)

    def is_current(self, item_id: str, text: str) -> bool:
        record = self.get(item_id)
        return record is not None and record.text_sha256 == _text_digest(text)

    def delete(self, item_id: str) -> bool:
        if item_id not in self._records:
            return False
        del self._records[item_id]
        self._dimension = len(next(iter(self._records.values())).vector) if self._records else None
        self.save()
        return True

    def search(
        self,
        vector: list[float] | tuple[float, ...],
        *,
        limit: int = 20,
    ) -> tuple[EmbeddingHit, ...]:
        if limit < 1:
            raise EmbeddingIndexError("embedding result limit must be positive")
        try:
            query = tuple(float(value) for value in vector)
        except (TypeError, ValueError) as exc:
            raise EmbeddingIndexError("embedding query is invalid") from exc
        if not query or any(not math.isfinite(value) for value in query):
            raise EmbeddingIndexError("embedding query is invalid")
        self._set_dimension(query)
        query_norm = math.sqrt(sum(value * value for value in query))
        if query_norm == 0:
            return ()
        hits: list[EmbeddingHit] = []
        for item_id, record in self._records.items():
            record_norm = math.sqrt(sum(value * value for value in record.vector))
            if record_norm == 0:
                continue
            score = sum(a * b for a, b in zip(query, record.vector, strict=True)) / (
                query_norm * record_norm
            )
            hits.append(EmbeddingHit(item_id, score))
        hits.sort(key=lambda hit: (-hit.score, hit.item_id))
        return tuple(hits[:limit])


def embeddings_endpoint() -> str | None:
    base_url = os.getenv("AGENT_WORKSPACE_EMBEDDINGS_BASE_URL")
    if not base_url:
        return None
    return base_url.rstrip("/")


class EmbeddingClient:
    """Minimal OpenAI-compatible /v1/embeddings client for optional semantic search."""

    def __init__(self, base_url: str, api_key: str | None = None, model: str | None = None) -> None:
        self._endpoint = f"{base_url}/embeddings"
        self._api_key = api_key
        self._model = (
            model or os.getenv("AGENT_WORKSPACE_EMBEDDINGS_MODEL") or "text-embedding-3-small"
        )
        self._client = httpx.AsyncClient(trust_env=False)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts or len(texts) > _MAX_EMBEDDING_BATCH:
            raise ValueError("embedding batch size is invalid")
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = await self._client.post(
                self._endpoint,
                headers=headers,
                json={"model": self._model, "input": texts},
                timeout=_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            raise EmbeddingsUnavailableError(f"embedding request failed: {exc}") from None
        if not response.is_success:
            raise EmbeddingsUnavailableError(
                f"embedding endpoint returned HTTP {response.status_code}"
            )
        try:
            payload: Any = response.json()
        except json.JSONDecodeError:
            raise EmbeddingsUnavailableError("embedding endpoint returned invalid JSON") from None
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or len(data) != len(texts):
            raise EmbeddingsUnavailableError("embedding endpoint returned an invalid payload")
        vectors: list[list[float]] = []
        for entry in data:
            if not isinstance(entry, dict) or not isinstance(entry.get("embedding"), list):
                raise EmbeddingsUnavailableError("embedding endpoint returned an invalid vector")
            raw_vector = entry["embedding"]
            if any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in raw_vector
            ):
                raise EmbeddingsUnavailableError("embedding endpoint returned an invalid vector")
            vector = [float(value) for value in raw_vector]
            if not vector or any(not math.isfinite(value) for value in vector):
                raise EmbeddingsUnavailableError("embedding endpoint returned an empty vector")
            vectors.append(vector)
        return vectors

    async def aclose(self) -> None:
        await self._client.aclose()


async def semantic_rank(
    client: EmbeddingClient,
    query: str,
    documents: list[str],
    *,
    index: EmbeddingIndex | None = None,
    item_ids: list[str] | None = None,
) -> list[int]:
    """Rank documents by embedding cosine similarity against the query."""
    from agent_workspace.core.ranking import rank_by_embeddings

    keys = (
        item_ids if item_ids is not None else [str(position) for position in range(len(documents))]
    )
    if len(keys) != len(documents):
        raise ValueError("embedding item id count must match documents")
    cached: list[list[float] | None] = []
    if index is not None:
        for key, document in zip(keys, documents, strict=True):
            record = index.get(key)
            cached.append(
                list(record.vector)
                if record is not None and index.is_current(key, document)
                else None
            )
    missing = any(vector is None for vector in cached)
    if index is not None and not missing:
        query_vectors = await client.embed([query])
        vectors = [query_vectors[0], *[vector for vector in cached if vector is not None]]
    else:
        vectors = await client.embed([query, *documents])
        if index is not None:
            for key, (document, vector) in zip(
                keys, zip(documents, vectors[1:], strict=True), strict=True
            ):
                index.upsert(key, document, vector)
    return rank_by_embeddings(vectors[0], vectors[1:])


def parse_embeddings_key() -> str | None:
    return os.getenv("AGENT_WORKSPACE_EMBEDDINGS_API_KEY") or None


async def configured_embedding_client() -> EmbeddingClient | None:
    endpoint = embeddings_endpoint()
    if endpoint is None:
        return None
    return EmbeddingClient(endpoint, parse_embeddings_key())
