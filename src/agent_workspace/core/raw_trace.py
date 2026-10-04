"""Developer-only raw conversation tracing."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DEFAULT_MAX_FILE_BYTES = 8 * 1024 * 1024
_DEFAULT_MAX_FILES = 4
_SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "api_secret",
        "authorization",
        "cookie",
        "credential",
        "password",
        "passphrase",
        "private_key",
        "secret",
        "token",
    }
)
_TRACE_API_KEY_PATTERN = re.compile(
    r"(?i)\b(sk-[A-Za-z0-9_\-]{16,}|AIza[0-9A-Za-z_\-]{30,}|"
    r"Bearer\s+[A-Za-z0-9._\-]{20,})\b"
)
_TRACE_PASSWORD_PATTERN = re.compile(
    r"(?i)\b(password|passwd|api[_-]?key|secret|token)\b(\s*[=:]\s*)([^\s,;]{6,})"
)
_TRACE_AWS_KEY_PATTERN = re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")
_TRACE_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END "
    r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    re.DOTALL,
)


class TraceRedactor:
    """Small core-local redactor so diagnostics do not depend on policy code."""

    def redact(self, text: str) -> str:
        text = _TRACE_API_KEY_PATTERN.sub("[REDACTED]", text)
        text = _TRACE_PASSWORD_PATTERN.sub(
            lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text
        )
        text = _TRACE_AWS_KEY_PATTERN.sub("[REDACTED]", text)
        return _TRACE_PRIVATE_KEY_PATTERN.sub("[REDACTED]", text)


def _positive_env(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _safe_session_component(session_id: str) -> str:
    if _SAFE_SESSION_ID.fullmatch(session_id):
        return session_id
    digest = hashlib.sha256(session_id.encode("utf-8", errors="replace")).hexdigest()[:20]
    return f"session-{digest}"


def _normalized_key(value: object) -> str:
    normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", str(value))
    normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", normalized)
    return re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()


def _redact_paths(value: str) -> str:
    """Replace user-home prefixes before a trace leaves the process."""
    result = value
    home_candidates = {str(Path.home())}
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        home_candidates.add(user_profile)
    home_drive = os.environ.get("HOMEDRIVE")
    home_path = os.environ.get("HOMEPATH")
    if home_drive and home_path:
        home_candidates.add(f"{home_drive}{home_path}")
    for home in sorted((item for item in home_candidates if item), key=len, reverse=True):
        result = result.replace(home, "<home>").replace(home.replace("\\", "/"), "<home>")
    return result


def _redact_trace_value(value: object, redactor: TraceRedactor, *, key: str = "") -> object:
    normalized = _normalized_key(key)
    if normalized in _SENSITIVE_KEYS or normalized.endswith(
        ("_token", "_secret", "_password", "_api_key", "_authorization")
    ):
        return "<redacted>"
    if isinstance(value, str):
        return _redact_paths(redactor.redact(value))
    if isinstance(value, dict):
        return {
            str(item_key): _redact_trace_value(item, redactor, key=str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_trace_value(item, redactor) for item in value]
    if isinstance(value, Path):
        return _redact_paths(str(value))
    return value


class RawConversationTrace:
    def __init__(
        self,
        directory: str | Path,
        *,
        enabled: bool = True,
        max_file_bytes: int = _DEFAULT_MAX_FILE_BYTES,
        max_files: int = _DEFAULT_MAX_FILES,
        redactor: TraceRedactor | None = None,
    ) -> None:
        self.directory = Path(directory).expanduser().resolve()
        self.enabled = enabled
        self.max_file_bytes = max(1, int(max_file_bytes))
        self.max_files = max(1, int(max_files))
        self.redactor = redactor or TraceRedactor()
        self._lock = threading.Lock()

    @classmethod
    def for_database(cls, database: str | Path) -> RawConversationTrace:
        raw = os.environ.get("AGENT_WORKSPACE_RAW_TRACE", "1").strip().lower()
        enabled = raw not in {"0", "false", "off", "no"}
        directory = os.environ.get("AGENT_WORKSPACE_RAW_TRACE_DIR")
        return cls(
            directory or (Path(database).expanduser().resolve().parent / "raw-traces"),
            enabled=enabled,
            max_file_bytes=_positive_env(
                "AGENT_WORKSPACE_RAW_TRACE_MAX_BYTES", _DEFAULT_MAX_FILE_BYTES
            ),
            max_files=_positive_env("AGENT_WORKSPACE_RAW_TRACE_MAX_FILES", _DEFAULT_MAX_FILES),
        )

    def record(
        self,
        *,
        session_id: str,
        correlation_id: str,
        phase: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return
        document = {
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": session_id,
            "correlation_id": correlation_id,
            "phase": phase,
            "payload": _redact_trace_value(dict(payload or {}), self.redactor),
        }
        try:
            line = (
                json.dumps(
                    document,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                    default=lambda value: repr(value),
                )
                + "\n"
            )
            encoded_size = len(line.encode("utf-8"))
        except (TypeError, ValueError, OverflowError):
            return
        path = self.directory / f"session-{_safe_session_component(session_id)}.jsonl"
        try:
            with self._lock:
                self.directory.mkdir(parents=True, exist_ok=True)
                if path.is_file() and path.stat().st_size + encoded_size > self.max_file_bytes:
                    self._rotate_locked(path)
                with path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(line)
        except OSError:
            # Diagnostics must never abort the user's turn.
            return

    def query(
        self,
        *,
        session_id: str | None = None,
        correlation_id: str | None = None,
        phase: str | None = None,
        offset: int = 0,
        limit: int = 500,
    ) -> tuple[dict[str, Any], ...]:
        """Read a bounded, best-effort view of persisted trace records.

        Rotated files are traversed from oldest to newest. Malformed lines are
        ignored so a damaged diagnostic record never prevents the remaining
        trace from being inspected.
        """
        if offset < 0 or limit < 0:
            raise ValueError("trace offset and limit must be non-negative")
        if limit == 0 or (not self.enabled and not self.directory.exists()):
            return ()
        records: list[dict[str, Any]] = []
        for path in self._trace_paths(session_id):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                continue
            for line in lines:
                try:
                    raw = json.loads(line)
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
                if not isinstance(raw, dict):
                    continue
                if session_id is not None and raw.get("session_id") != session_id:
                    continue
                if correlation_id is not None and raw.get("correlation_id") != correlation_id:
                    continue
                if phase is not None and raw.get("phase") != phase:
                    continue
                records.append(raw)
        return tuple(records[offset : offset + limit])

    def query_by_correlation(
        self,
        correlation_id: str,
        *,
        session_id: str | None = None,
        offset: int = 0,
        limit: int = 500,
    ) -> tuple[dict[str, Any], ...]:
        return self.query(
            session_id=session_id,
            correlation_id=correlation_id,
            offset=offset,
            limit=limit,
        )

    def export_debug(
        self,
        destination: str | Path,
        *,
        session_ids: tuple[str, ...] | list[str] = (),
        correlation_id: str | None = None,
        phase: str | None = None,
        max_records: int = 5_000,
    ) -> int:
        """Export a bounded NDJSON trace with a second redaction pass."""
        if max_records < 0:
            raise ValueError("max_records must be non-negative")
        ids = tuple(session_ids)
        records: list[dict[str, Any]] = []
        if ids:
            for session_id in ids:
                remaining = max_records - len(records)
                if remaining <= 0:
                    break
                records.extend(
                    self.query(
                        session_id=session_id,
                        correlation_id=correlation_id,
                        phase=phase,
                        limit=remaining,
                    )
                )
        else:
            records.extend(
                self.query(
                    correlation_id=correlation_id,
                    phase=phase,
                    limit=max_records,
                )
            )
        target = Path(destination).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as stream:
            for record in records[:max_records]:
                safe = _redact_trace_value(record, self.redactor)
                stream.write(
                    json.dumps(safe, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
                    + "\n"
                )
        return min(len(records), max_records)

    export_debug_trace = export_debug

    def _trace_paths(self, session_id: str | None) -> tuple[Path, ...]:
        if not self.directory.is_dir():
            return ()
        if session_id is not None:
            base = self.directory / f"session-{_safe_session_component(session_id)}.jsonl"
            candidates = list(self.directory.glob(f"{base.name}.*"))
            if base.exists():
                candidates.append(base)
        else:
            candidates = list(self.directory.glob("session-*.jsonl*"))

        def rotation(path: Path) -> tuple[str, int]:
            name = path.name
            if ".jsonl." not in name:
                return name, 0
            stem, suffix = name.split(".jsonl.", 1)
            try:
                return f"{stem}.jsonl", int(suffix)
            except ValueError:
                return name, 0

        grouped: dict[str, list[Path]] = {}
        for path in candidates:
            key = path.name.split(".jsonl", 1)[0]
            grouped.setdefault(key, []).append(path)
        ordered: list[Path] = []
        for key in sorted(grouped):
            ordered.extend(sorted(grouped[key], key=lambda item: rotation(item)[1], reverse=True))
        return tuple(ordered)

    def _rotate_locked(self, path: Path) -> None:
        if self.max_files <= 1:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                return
            return
        oldest = path.with_name(f"{path.name}.{self.max_files - 1}")
        try:
            oldest.unlink(missing_ok=True)
            for index in range(self.max_files - 2, 0, -1):
                source = path.with_name(f"{path.name}.{index}")
                target = path.with_name(f"{path.name}.{index + 1}")
                if source.exists():
                    source.replace(target)
            if path.exists():
                path.replace(path.with_name(f"{path.name}.1"))
        except OSError:
            # Keep the current log usable when rotation is blocked by an external lock.
            return
