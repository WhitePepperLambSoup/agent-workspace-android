"""Mobile usage reports and persistent per-model price overrides."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from mobile_workspace import runtime_workspace

from agent_workspace.core.cost import UNKNOWN_PRICING, resolve_pricing
from agent_workspace.storage.sqlite import SQLiteEventStore
from agent_workspace.tools.base import ToolError
from agent_workspace.tools.filesystem import _scan_file, atomic_write
from agent_workspace.tools.paths import WorkspacePaths

_MAX_PRICING_BYTES = 256 * 1024
_RATE_FIELDS = (
    "input_usd_per_million",
    "output_usd_per_million",
    "cached_usd_per_million",
)


def _model_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError("model must be a nonempty model ID of at most 256 characters")
    return value.strip()


def _rates(payload: Mapping[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    for field in _RATE_FIELDS:
        value = payload.get(field)
        if type(value) not in (int, float):
            raise ValueError(f"{field} must be a finite non-negative number")
        try:
            rate = float(value)
        except OverflowError as exc:
            raise ValueError(f"{field} is too large") from exc
        if not math.isfinite(rate) or rate < 0:
            raise ValueError(f"{field} must be a finite non-negative number")
        result[field] = rate
    return result


def _read_pricing(runtime: Any) -> tuple[Path, dict[str, Any], str | None]:
    database = Path(runtime.database)
    path = database.with_name(f"{database.stem}.mobile-pricing-v1.json")
    try:
        path = WorkspacePaths(path.parent).resolve(path)
        digest, raw = _scan_file(
            path, max_scan_bytes=_MAX_PRICING_BYTES, retain_limit=_MAX_PRICING_BYTES
        )
        if raw is None:
            return path, {"version": 1, "models": {}}, None
        document = json.loads(raw.decode("utf-8"))
        if (
            not isinstance(document, dict)
            or type(document.get("version")) is not int
            or document["version"] != 1
            or not isinstance(document.get("models"), dict)
        ):
            raise ValueError("invalid pricing document")
        for model, rates in document["models"].items():
            if _model_id(model) != model or not isinstance(rates, dict):
                raise ValueError("invalid model pricing")
            _rates(rates)
        return path, document, digest
    except (OSError, ToolError, ValueError) as exc:
        raise OSError("mobile pricing cannot be read") from exc


def save_pricing(runtime: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    model = _model_id(payload.get("model"))
    rates = _rates(payload)
    path, document, digest = _read_pricing(runtime)
    document["models"][model] = rates
    encoded = json.dumps(
        document, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    if len(encoded) > _MAX_PRICING_BYTES:
        raise OSError("mobile pricing exceeds its storage limit")
    try:
        atomic_write(WorkspacePaths(path.parent), path, encoded, digest)
    except ToolError as exc:
        raise OSError("mobile pricing could not be saved; reload and retry") from exc
    return {"ok": True, "model": model, "pricing": {**rates, "source": "custom"}}


def _pricing(model: str, custom: Mapping[str, Any]) -> dict[str, Any] | None:
    if model in custom:
        return {**_rates(custom[model]), "source": "custom"}
    from mobile_model_catalog import MODEL_CATALOG

    if model in {item["model_id"] for item in MODEL_CATALOG}:
        return {**dict.fromkeys(_RATE_FIELDS, 0.0), "source": "on_device"}
    reference = resolve_pricing(model)
    if reference is UNKNOWN_PRICING:
        return None
    return {
        "input_usd_per_million": reference.input_usd_per_million,
        "output_usd_per_million": reference.output_usd_per_million,
        "cached_usd_per_million": (
            reference.input_usd_per_million
            if reference.cached_usd_per_million is None
            else reference.cached_usd_per_million
        ),
        "source": "reference",
    }


def _usage_rows(
    runtime: Any,
    workspace: Path,
    session_id: str | None,
    cutoff: datetime | None,
    end: datetime,
) -> Iterator[sqlite3.Row]:
    connection: sqlite3.Connection | None = None
    try:
        connection = SQLiteEventStore._open_read_only(Path(runtime.database))
        connection.execute("BEGIN")
        # Read only usage fields; request attribution stays in the database snapshot.
        rows = connection.execute(
            """
            SELECT
                json_extract(u.data_json, '$.input_tokens') AS input_tokens,
                json_extract(u.data_json, '$.output_tokens') AS output_tokens,
                COALESCE(json_extract(u.data_json, '$.cached_tokens'), 0) AS cached_tokens,
                COALESCE(json_extract(u.data_json, '$.estimated'), 0) AS estimated,
                COALESCE(NULLIF(json_extract(request.data_json, '$.model'), ''), (
                    SELECT json_extract(previous.data_json, '$.model')
                    FROM events AS previous
                    WHERE previous.session_id = u.session_id
                      AND previous.type = 'model.requested' AND previous.sequence < u.sequence
                      AND json_type(previous.data_json, '$.model') = 'text'
                      AND json_extract(previous.data_json, '$.model') <> ''
                    ORDER BY previous.sequence DESC LIMIT 1
                ), 'unknown') AS model
            FROM events AS u
            JOIN sessions AS session ON session.id = u.session_id
            LEFT JOIN events AS request
              ON request.id = u.causation_id AND request.session_id = u.session_id
             AND request.type = 'model.requested' AND request.sequence < u.sequence
             AND json_type(request.data_json, '$.model') = 'text'
            WHERE u.type = 'usage.updated' AND session.workspace = ?
              AND (? IS NULL OR u.session_id = ?)
              AND (? IS NULL OR julianday(u.created_at) BETWEEN julianday(?) AND julianday(?))
              AND json_type(u.data_json, '$.input_tokens') = 'integer'
              AND json_type(u.data_json, '$.output_tokens') = 'integer'
              AND (json_type(u.data_json, '$.cached_tokens') IS NULL
                   OR json_type(u.data_json, '$.cached_tokens') = 'integer')
              AND (json_type(u.data_json, '$.estimated') IS NULL
                   OR json_type(u.data_json, '$.estimated') IN ('true', 'false'))
            ORDER BY u.session_id, u.sequence
            """,
            (
                str(workspace), session_id, session_id,
                cutoff.isoformat() if cutoff else None,
                cutoff.isoformat() if cutoff else None, end.isoformat(),
            ),
        )
        yield from rows
    except sqlite3.Error as exc:
        raise OSError("usage database could not be read") from exc
    finally:
        if connection is not None:
            connection.close()


def _empty_totals() -> dict[str, Any]:
    return {
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 0,
        "estimated_calls": 0,
        "known_cost_usd": 0.0,
        "unpriced_calls": 0,
    }


def usage_summary(
    runtime: Any,
    *,
    session_id: str | None = None,
    days: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if days is not None and (type(days) is not int or not 1 <= days <= 3660):
        raise ValueError("days must be an integer from 1 to 3660")
    workspace = runtime_workspace(runtime)
    if session_id is not None:
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id must be a nonempty string")
        session = runtime.store.get_session(session_id)
        if session is None or Path(session.workspace).resolve() != workspace:
            raise KeyError("session not found in this workspace")
    _, document, _ = _read_pricing(runtime)
    end = now or datetime.now(UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    cutoff = end - timedelta(days=days) if days is not None else None
    buckets: dict[str, dict[str, Any]] = {}
    for usage in _usage_rows(runtime, workspace, session_id, cutoff, end):
        inputs, outputs, cached = (usage[field] for field in (
            "input_tokens", "output_tokens", "cached_tokens"
        ))
        if any(type(value) is not int or value < 0 for value in (inputs, outputs, cached)):
            continue
        model = usage["model"]
        if model not in buckets:
            buckets[model] = {
                "model": model,
                "pricing": _pricing(model, document["models"]),
                **_empty_totals(),
            }
        row = buckets[model]
        cached = min(cached, inputs)
        row["model_calls"] += 1
        row["input_tokens"] += inputs
        row["output_tokens"] += outputs
        row["cached_tokens"] += cached
        row["total_tokens"] += inputs + outputs
        row["estimated_calls"] += usage["estimated"]
        pricing = row["pricing"]
        if pricing is None:
            row["unpriced_calls"] += 1
        else:
            # Convert token units before multiplying to avoid intermediate overflow.
            row["known_cost_usd"] += (
                (inputs - cached) / 1_000_000 * pricing["input_usd_per_million"]
                + outputs / 1_000_000 * pricing["output_usd_per_million"]
                + cached / 1_000_000 * pricing["cached_usd_per_million"]
            )
    totals = _empty_totals()
    for row in buckets.values():
        if not math.isfinite(row["known_cost_usd"]):
            raise ValueError("cost exceeds the supported numeric range; lower model rates")
        for field in totals:
            totals[field] += row[field]
        row["cost_usd"] = None if row["unpriced_calls"] else row["known_cost_usd"]
    if not math.isfinite(totals["known_cost_usd"]):
        raise ValueError("cost exceeds the supported numeric range; lower model rates")
    totals["cost_usd"] = None if totals["unpriced_calls"] else totals["known_cost_usd"]
    return {
        "scope": "session" if session_id is not None else "workspace",
        "currency": "USD",
        "days": days,
        "totals": totals,
        "models": sorted(buckets.values(), key=lambda row: (-row["total_tokens"], row["model"])),
    }
