"""Durable mobile schedules which submit through the existing task controller."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import tempfile
import threading
from collections.abc import Mapping
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from mobile_protocol import TaskState, parse_mobile_task_request
from mobile_runtime_controller import MobileRuntimeController

from agent_workspace.core.models import Autonomy
from agent_workspace.providers.reasoning import supported_reasoning_efforts

_MAX_SCHEDULES = 128
_RECOVERY_WINDOW = timedelta(hours=24)
_LIVE_STATES = {TaskState.QUEUED, TaskState.RUNNING, TaskState.WAITING_APPROVAL}
_CONFIG_FIELDS = {
    "title",
    "session_id",
    "prompt",
    "model",
    "reasoning_effort",
    "due_at",
    "repeat_seconds",
    "enabled",
}
_STATUSES = {
    "scheduled",
    "disabled",
    "dispatching",
    "submitted",
    "interrupted",
    "missed",
    "mode_required",
    "skipped_busy",
    "failed",
}


def _instant(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO datetime with a timezone")
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError
        return result.astimezone(UTC)
    except (ValueError, OverflowError):
        raise ValueError(f"{field} must be an ISO datetime with a timezone") from None


class MobileScheduleManager:
    """Checkpoint due occurrences before creating tasks; never replay unknown outcomes."""

    def __init__(self, controller: MobileRuntimeController, storage_path: str | Path) -> None:
        self.controller = controller
        self.path = Path(storage_path)
        self._lock = threading.RLock()
        self._dispatch_lock = asyncio.Lock()
        self._items = self._load()
        changed = False
        for item in self._items.values():
            if item["last_status"] == "dispatching":
                item["last_status"] = "interrupted"
                item["last_error"] = (
                    "Submission outcome was interrupted; inspect task history before retrying."
                )
                changed = True
        if changed:
            self._save()

    def list(self) -> list[dict[str, object]]:
        with self._lock:
            return copy.deepcopy(
                sorted(
                    self._items.values(),
                    key=lambda item: (item["next_due_at"], item["schedule_id"]),
                )
            )

    def snapshot(self) -> dict[str, object]:
        items = self.list()
        return {
            "schedules": items,
            "status": {
                "enabled": sum(item["enabled"] is True for item in items),
                "recovery_window_seconds": int(_RECOVERY_WINDOW.total_seconds()),
                "max_dispatch_per_wake": 4,
                "unattended_mode_required": "yolo or full_access",
            },
        }

    def create(self, payload: Mapping[str, object]) -> dict[str, object]:
        config = self._config(payload)
        self._require_unattended(config["session_id"])
        with self._lock:
            if len(self._items) >= _MAX_SCHEDULES:
                raise ValueError("too many mobile schedules")
            item = {
                **config,
                "schedule_id": str(uuid4()),
                "next_due_at": config["due_at"],
                "last_status": "scheduled" if config["enabled"] else "disabled",
                "last_task_id": None,
                "last_run": None,
                "last_occurrence": None,
                "last_error": None,
            }
            self._items[item["schedule_id"]] = item
            self._save()
            return copy.deepcopy(item)

    def update(self, schedule_id: str, payload: Mapping[str, object]) -> dict[str, object]:
        with self._lock:
            item = self._get(schedule_id)
            config = self._config(payload, existing=item)
            if config["enabled"]:
                self._require_unattended(config["session_id"])
                if item["last_occurrence"] == config["due_at"]:
                    raise ValueError(
                        "this occurrence was already handled; choose a new due_at "
                        "to schedule it again"
                    )
            item.update(config)
            if "due_at" in payload:
                item["next_due_at"] = config["due_at"]
            if "enabled" in payload or "due_at" in payload:
                item["last_status"] = "scheduled" if config["enabled"] else "disabled"
                item["last_error"] = None
            self._save()
            return copy.deepcopy(item)

    def delete(self, schedule_id: str) -> None:
        with self._lock:
            self._get(schedule_id)
            del self._items[schedule_id]
            self._save()

    async def dispatch_due(self, *, now: datetime | None = None) -> list[dict[str, object]]:
        current = now or datetime.now(UTC)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("now must have a timezone")
        current = current.astimezone(UTC)
        submitted: list[dict[str, object]] = []
        async with self._dispatch_lock:
            for visible in self.list():
                if len(submitted) >= 4:
                    break
                with self._lock:
                    item = self._items.get(visible["schedule_id"])
                    if item is None or not item["enabled"]:
                        continue
                    due = _instant(item["next_due_at"], "next_due_at")
                    if due > current:
                        continue
                    try:
                        self._require_unattended(item["session_id"])
                    except (KeyError, ValueError) as error:
                        item.update(
                            enabled=False, last_status="mode_required", last_error=str(error)
                        )
                        self._save()
                        continue
                    interval = item["repeat_seconds"]
                    if interval is not None:
                        # Coalesce a delayed repeat to its most recent due occurrence.
                        elapsed = int((current - due).total_seconds())
                        due += timedelta(seconds=(elapsed // interval) * interval)
                        item["next_due_at"] = (due + timedelta(seconds=interval)).isoformat()
                    else:
                        item["enabled"] = False
                    previous_id = item["last_task_id"]
                    previous_live = False
                    if previous_id:
                        with suppress(KeyError):
                            previous_live = self.controller.get(previous_id).state in _LIVE_STATES
                    if previous_live:
                        item["last_status"] = "skipped_busy"
                        self._save()
                        continue
                    if current - due > _RECOVERY_WINDOW:
                        item.update(
                            last_status="missed",
                            last_error="The due time is outside the recovery window.",
                        )
                        self._save()
                        continue
                    occurrence = due.isoformat()
                    if item["last_occurrence"] == occurrence:
                        self._save()
                        continue
                    item.update(
                        last_occurrence=occurrence,
                        last_run=current.isoformat(),
                        last_status="dispatching",
                        last_error=None,
                    )
                    self._save()
                    schedule_id = item["schedule_id"]
                    request = parse_mobile_task_request(item)
                try:
                    task = await self.controller.submit(request)
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    with self._lock:
                        if schedule_id in self._items:
                            self._items[schedule_id].update(
                                last_status="failed", last_error=str(error)[:512]
                            )
                            self._save()
                    continue
                with self._lock:
                    if schedule_id in self._items:
                        self._items[schedule_id].update(
                            last_status="submitted", last_task_id=task.task_id
                        )
                        self._save()
                        submitted.append(copy.deepcopy(self._items[schedule_id]))
        return submitted

    async def run(self) -> None:
        while True:
            await self.dispatch_due()
            await asyncio.sleep(15)

    def _get(self, schedule_id: str) -> dict[str, object]:
        if schedule_id not in self._items:
            raise KeyError(schedule_id)
        return self._items[schedule_id]

    def _require_unattended(self, session_id: str) -> None:
        session = self.controller.runtime.service.get_session(session_id)
        effective = (
            getattr(self.controller.runtime.service, "_execution_autonomy", None)
            or session.autonomy
        )
        allowed = {Autonomy.YOLO, Autonomy.FULL_ACCESS}
        if effective not in allowed or session.autonomy not in allowed:
            raise ValueError("Unattended schedules require yolo or full_access execution mode.")
        workspace = self.controller.tasks.workspace
        if workspace is not None and Path(session.workspace).resolve() != workspace:
            raise ValueError("schedule session is outside the mobile workspace")

    def _config(
        self, payload: Mapping[str, object], *, existing: Mapping[str, object] | None = None
    ) -> dict[str, object]:
        if not isinstance(payload, Mapping) or set(payload) - _CONFIG_FIELDS:
            raise ValueError("invalid schedule fields")
        config = (
            {field: existing[field] for field in _CONFIG_FIELDS}
            if existing
            else {
                "title": "Scheduled task",
                "model": self.controller.default_model,
                "reasoning_effort": self.controller.default_reasoning_effort,
                "repeat_seconds": None,
                "enabled": True,
            }
        )
        config.update(payload)
        request = parse_mobile_task_request(config)
        if not request.model:
            raise ValueError("no model configured for the scheduled task")
        if (
            self.controller.protocol is not None
            and self.controller.base_url is not None
            and request.reasoning_effort
            not in supported_reasoning_efforts(
                self.controller.protocol, self.controller.base_url, request.model
            )
        ):
            raise ValueError(f"{request.model} does not support the scheduled reasoning_effort")
        title = config.get("title")
        if not isinstance(title, str) or not title.strip() or len(title) > 160:
            raise ValueError("schedule title must contain 1 to 160 characters")
        enabled = config.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")
        repeat = config.get("repeat_seconds")
        if repeat is not None and (
            not isinstance(repeat, int)
            or isinstance(repeat, bool)
            or not 900 <= repeat <= 31_536_000
        ):
            raise ValueError("repeat_seconds must be an integer from 900 to 31536000")
        return {
            "title": title.strip(),
            "session_id": request.session_id,
            "prompt": request.prompt,
            "model": request.model,
            "reasoning_effort": request.reasoning_effort,
            "due_at": _instant(config.get("due_at"), "due_at").isoformat(),
            "repeat_seconds": repeat,
            "enabled": enabled,
        }

    def _load(self) -> dict[str, dict[str, object]]:
        if not self.path.exists():
            return {}
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(document, dict) or document.get("schema") != 1:
                raise ValueError
            items = document["schedules"]
            if not isinstance(items, list) or len(items) > _MAX_SCHEDULES:
                raise ValueError
            result = {}
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError
                required = {
                    "schedule_id",
                    "title",
                    "session_id",
                    "prompt",
                    "model",
                    "reasoning_effort",
                    "due_at",
                    "repeat_seconds",
                    "enabled",
                    "next_due_at",
                    "last_status",
                    "last_task_id",
                    "last_run",
                    "last_occurrence",
                    "last_error",
                }
                if set(item) != required:
                    raise ValueError
                identifier = item["schedule_id"]
                if not isinstance(identifier, str) or not identifier or identifier in result:
                    raise ValueError
                self._config({field: item[field] for field in _CONFIG_FIELDS})
                _instant(item["next_due_at"], "next_due_at")
                if item["last_status"] not in _STATUSES:
                    raise ValueError
                result[identifier] = item
            return result
        except (KeyError, ValueError, TypeError, OSError) as error:
            raise ValueError(
                "mobile schedule storage is invalid; preserve and repair it before saving schedules"
            ) from error

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as output:
                name = output.name
                json.dump(
                    {"schema": 1, "schedules": list(self._items.values())},
                    output,
                    ensure_ascii=False,
                )
                output.flush()
                os.fsync(output.fileno())
            with suppress(OSError):
                os.chmod(name, 0o600)
            os.replace(name, self.path)
        finally:
            if name is not None:
                with suppress(OSError):
                    Path(name).unlink(missing_ok=True)
