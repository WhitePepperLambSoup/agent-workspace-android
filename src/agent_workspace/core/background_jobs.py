from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BackgroundJobLimits:
    max_seconds: int = 110
    max_output_bytes: int = 128 * 1024

    def __post_init__(self) -> None:
        if type(self.max_seconds) is not int or not 1 <= self.max_seconds <= 110:
            raise ValueError("background job max_seconds must be from 1 to 110")
        if (
            type(self.max_output_bytes) is not int
            or not 1024 <= self.max_output_bytes <= 1024 * 1024
        ):
            raise ValueError("background job max_output_bytes must be from 1024 to 1048576")


@dataclass(frozen=True, slots=True)
class BackgroundJobStatus:
    job_id: str
    session_id: str
    label: str
    state: str
    created_at: str
    updated_at: str
    result: str | None = None
    terminal_reason: str | None = None


def validate_background_job_event(event_type: str, data: dict[str, Any]) -> bool:
    if not event_type.startswith("background.job."):
        return False
    job_id = data.get("job_id")
    if not isinstance(job_id, str) or not job_id or len(job_id) > 128:
        raise ValueError("background job event has an invalid job id")
    if event_type == "background.job.created":
        if (
            set(data)
            != {
                "job_id",
                "label",
                "arguments_sha256",
                "max_seconds",
                "max_output_bytes",
            }
            or not isinstance(data.get("label"), str)
            or not data["label"]
            or len(data["label"]) > 200
            or not _is_sha256(data.get("arguments_sha256"))
            or type(data.get("max_seconds")) is not int
            or not 1 <= data["max_seconds"] <= 110
            or type(data.get("max_output_bytes")) is not int
            or not 1024 <= data["max_output_bytes"] <= 1024 * 1024
        ):
            raise ValueError("background job creation event is invalid")
        return True
    if event_type == "background.job.started":
        if set(data) != {"job_id"}:
            raise ValueError("background job started event is invalid")
        return True
    if event_type == "background.job.interrupted":
        reason = data.get("reason")
        if (
            set(data) != {"job_id", "reason"}
            or not isinstance(reason, str)
            or not reason
            or len(reason.encode()) > 1000
        ):
            raise ValueError("background job interrupted event is invalid")
        return True
    if event_type in {
        "background.job.succeeded",
        "background.job.failed",
        "background.job.stopped",
    }:
        if (
            set(data) != {"job_id", "result", "reason"}
            or (data.get("result") is not None and not isinstance(data.get("result"), str))
            or (data.get("reason") is not None and not isinstance(data.get("reason"), str))
            or (isinstance(data.get("result"), str) and len(data["result"].encode()) > 1024 * 1024)
            or (isinstance(data.get("reason"), str) and len(data["reason"].encode()) > 1000)
        ):
            raise ValueError("background job terminal event is invalid")
        return True
    raise ValueError("background job event type is unsupported")


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
