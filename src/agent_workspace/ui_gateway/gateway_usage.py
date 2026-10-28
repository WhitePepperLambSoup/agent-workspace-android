"""Spending (task limits, the monthly bill and cap, cost estimates), skills and file batches."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from agent_workspace.application.cost_estimate import project, recent_calls
from agent_workspace.application.usage_bill import current_month, month_bill
from agent_workspace.core.budgets import (
    MAX_TASK_COST_LIMIT_USD,
    MAX_TASK_TOKEN_LIMIT,
    TaskBudget,
    TaskLimits,
)
from agent_workspace.core.cost import UNKNOWN_PRICING, resolve_pricing, session_cost
from agent_workspace.storage import (
    SQLiteEventStore,
)
from agent_workspace.tools.file_batches import (
    UNDOABLE_STATES,
    FileBatch,
    FileBatchError,
    undo_batch,
)
from agent_workspace.ui_gateway.fork import fork_marker
from agent_workspace.ui_gateway.gateway_common import (
    _COST_ESTIMATE_DAYS,
    _MAX_MONTHLY_CAP_USD,
    _MAX_PROMPT_CHARS,
    _MONTH_COST_SECONDS,
    _TYPICAL_REQUEST_TOKENS,
    GatewayError,
    GatewayReply,
)
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import (
    CommandEnvelope,
)
from agent_workspace.ui_gateway.skills import SkillError as SkillLibraryError


class UsageCommands(GatewayState):
    """Spending: task limits, the monthly bill and cap, cost estimates; skills; undoable file
    batches.
    """

    def _estimate_cost(self, command: CommandEnvelope) -> GatewayReply:
        """A rough range for what the next task costs, for the composer while the user types."""
        self._require_payload(command, {"messageChars"}, optional={"sessionId"})
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        chars = command.payload.get("messageChars")
        if type(chars) is not int or not 0 <= chars <= _MAX_PROMPT_CHARS:
            raise GatewayError("invalid_payload")
        session_id = command.payload.get("sessionId")
        if session_id is not None and (
            not isinstance(session_id, str) or not session_id or len(session_id) > 128
        ):
            raise GatewayError("invalid_session")
        with self._lock:
            provider = self._provider
            workspace = self._workspace
        if provider is None or workspace is None:
            raise GatewayError("runtime_unconfigured")
        payload: dict[str, object] = {"epoch": self.epoch, "model": provider.model}
        pricing = resolve_pricing(provider.model)
        if pricing is UNKNOWN_PRICING:
            return self._reply(
                "cost.estimate.result", {**payload, "priced": False}, session_id=None
            )
        if not (pricing.input_usd_per_million or pricing.output_usd_per_million):
            return self._reply(
                "cost.estimate.result", {**payload, "priced": True, "free": True}, session_id=None
            )
        try:
            calls = (
                recent_calls(
                    self._database,
                    str(workspace),
                    datetime.now(UTC) - timedelta(days=_COST_ESTIMATE_DAYS),
                )
                if self._database.is_file()
                else []
            )
        except OSError:
            raise GatewayError("storage_unavailable") from None
        estimate = project(
            calls,
            session_id,
            pricing,
            chars,
            default_context=_TYPICAL_REQUEST_TOKENS,
        )
        return self._reply(
            "cost.estimate.result",
            {**payload, "priced": True, "free": False, **estimate},
            session_id=None,
        )

    def _task_limits_path(self) -> Path:
        return self._database.with_name("task-limits.json")

    def _task_limits(self) -> TaskLimits | None:
        """The user's per-task spending limits, or None when none is set. Never raises."""
        try:
            document = json.loads(self._task_limits_path().read_text(encoding="utf-8"))
            limits = TaskLimits(
                max_cost_usd=document.get("maxCostUsd"),
                max_total_tokens=document.get("maxTokens"),
            )
        except (OSError, ValueError, TypeError, AttributeError):
            return None
        if limits.max_cost_usd is None and limits.max_total_tokens is None:
            return None
        return limits

    @staticmethod
    def _task_limits_document(limits: TaskLimits | None) -> dict[str, object]:
        return {
            "maxCostUsd": limits.max_cost_usd if limits is not None else None,
            "maxTokens": limits.max_total_tokens if limits is not None else None,
            "maxCostLimitUsd": MAX_TASK_COST_LIMIT_USD,
            "maxTokenLimit": MAX_TASK_TOKEN_LIMIT,
            "defaultCostUsd": TaskBudget().max_cost_usd,
        }

    def _skills_command(self, command: CommandEnvelope) -> GatewayReply:
        """The skills the agent can use in every folder, and turning one on or off."""
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        try:
            if command.type == "skills.set":
                self._require_payload(command, {"key", "enabled"})
                key = command.payload.get("key")
                enabled = command.payload.get("enabled")
                if (
                    not isinstance(key, str)
                    or not key
                    or len(key) > 140
                    or type(enabled) is not bool
                ):
                    raise GatewayError("invalid_payload")
                self._skills.set_enabled(key, enabled)
            elif command.type == "skills.folder.open":
                self._require_payload(command, set())
                self._skills.open_user_folder()
            else:
                self._require_payload(command, set())
            document = self._skills.document()
        except SkillLibraryError as error:
            code = str(error)
            raise GatewayError(
                code if code in {"unknown_skill", "unsupported"} else "invalid_skill"
            ) from None
        except OSError:
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            f"{command.type}.result", {"epoch": self.epoch, **document}, session_id=None
        )

    def _task_limits_command(self, command: CommandEnvelope) -> GatewayReply:
        """Read or replace the spending limit every new task runs under (null clears one)."""
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        if command.type == "limits.get":
            self._require_payload(command, set())
            return self._reply(
                "limits.get.result",
                {"epoch": self.epoch, **self._task_limits_document(self._task_limits())},
                session_id=None,
            )
        self._require_payload(command, {"maxCostUsd", "maxTokens"})
        cost = command.payload.get("maxCostUsd")
        tokens = command.payload.get("maxTokens")
        if (
            isinstance(cost, bool)
            or isinstance(tokens, bool)
            or not (cost is None or isinstance(cost, int | float))
            or not (tokens is None or isinstance(tokens, int))
        ):
            raise GatewayError("invalid_limits")
        try:
            limits = TaskLimits(
                max_cost_usd=None if cost is None else float(cost),
                max_total_tokens=tokens,
            )
        except ValueError:
            raise GatewayError("invalid_limits") from None
        path = self._task_limits_path()
        staging = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            staging.write_text(
                json.dumps(
                    {"maxCostUsd": limits.max_cost_usd, "maxTokens": limits.max_total_tokens}
                ),
                encoding="utf-8",
            )
            os.replace(staging, path)
        except OSError:
            raise GatewayError("storage_unavailable") from None
        finally:
            staging.unlink(missing_ok=True)
        return self._reply(
            "limits.set.result",
            {"epoch": self.epoch, **self._task_limits_document(self._task_limits())},
            session_id=None,
        )

    def _session_usage(self, command: CommandEnvelope) -> GatewayReply:
        """Summarize recorded token usage and its estimated price for a session."""
        self._require_payload(command, {"sessionId"})
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        session = self._workspace_session(command.payload.get("sessionId"))
        try:
            events = SQLiteEventStore.list_session_events_of_types_read_only(
                self._database,
                session.id,
                frozenset({"model.requested", "usage.updated", "session.forked"}),
            )
        except (OSError, ValueError, sqlite3.DatabaseError):
            raise GatewayError("storage_unavailable") from None
        # A fork carries a copy of the original's history; its spending was the original's.
        marker = fork_marker(events)
        if marker is not None:
            events = events[marker[0] + 1 :]
        cost = session_cost(events)
        priced = any(resolve_pricing(model) is not UNKNOWN_PRICING for model in cost.models)
        return self._reply(
            "session.usage.result",
            {
                "epoch": self.epoch,
                "sessionId": session.id,
                "modelCalls": cost.model_calls,
                "inputTokens": cost.input_tokens,
                "outputTokens": cost.output_tokens,
                "cachedTokens": cost.cached_tokens,
                "estimated": cost.estimated,
                "costUsd": round(cost.cost_usd, 6),
                # Unpriced models count as free; the UI must not present $0 as a price.
                "priced": priced,
                "models": list(cost.models)[:16],
            },
            session_id=None,
        )

    def _file_batch_document(self, batch: FileBatch) -> dict[str, object]:
        return {
            "id": batch.id,
            "summary": batch.summary,
            "createdAt": batch.created_at,
            "updatedAt": batch.updated_at or batch.created_at,
            "state": batch.state,
            # A batch still marked running belongs to a process that ended mid-way.
            "undoable": batch.state in UNDOABLE_STATES or batch.state == "running",
            "steps": [
                {
                    "action": step.action,
                    "path": step.path,
                    "to": step.to,
                    "auto": step.auto,
                    "undone": step.undone,
                }
                for step in batch.steps
            ],
            "problems": batch.problems,
        }

    def _file_batches_command(self, command: CommandEnvelope) -> GatewayReply:
        """The agent's file batches in this workspace, and undoing one."""
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        try:
            if command.type == "files.batches.list":
                self._require_payload(command, set(), optional={"limit"})
                limit = command.payload.get("limit", 50)
                if type(limit) is not int or not 1 <= limit <= 200:
                    raise GatewayError("invalid_limit")
                with self._lock:
                    workspace = self._workspace
                batches = [] if workspace is None else self._file_batches.list(workspace, limit)
                return self._reply(
                    "files.batches.list.result",
                    {
                        "epoch": self.epoch,
                        "batches": [self._file_batch_document(batch) for batch in batches],
                    },
                    session_id=None,
                )
            self._require_payload(command, {"batchId"})
            batch_id = command.payload.get("batchId")
            if not isinstance(batch_id, str):
                raise GatewayError("invalid_batch")
            report = undo_batch(self._file_batches, batch_id)
        except FileBatchError:
            raise GatewayError("unknown_batch") from None
        except OSError:
            raise GatewayError("storage_unavailable") from None
        return self._reply(
            "files.batches.undo.result",
            {
                "epoch": self.epoch,
                "batch": self._file_batch_document(report.batch),
                "undone": report.undone,
                "skipped": report.skipped,
            },
            session_id=None,
        )

    def _usage_databases(self) -> list[Path]:
        """The main database and every agent run's, whose model calls the bill counts."""
        runs = self._database.parent / (self._database.stem + "-runs")
        try:
            extra = sorted(runs.glob("*.db")) if runs.is_dir() else []
        except OSError:
            extra = []
        return [self._database, *extra]

    def _monthly_cap_path(self) -> Path:
        return self._database.with_name("monthly-cap.json")

    def _monthly_cap(self) -> float | None:
        try:
            value = json.loads(self._monthly_cap_path().read_text("utf-8")).get("capUsd")
        except (OSError, ValueError, AttributeError):
            return None
        if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
            return None
        return float(value)

    def _month_to_date(self, *, fresh: bool = False) -> float:
        month = current_month()
        cached = self._month_cost
        if (
            not fresh
            and cached is not None
            and cached[0] == month
            and self._clock() - cached[1] < _MONTH_COST_SECONDS
        ):
            return cached[2]
        cost = month_bill(self._usage_databases(), month).cost_usd
        self._month_cost = (month, self._clock(), cost)
        return cost

    def _check_monthly_cap(self) -> None:
        """Refuse new work once this month's estimated cost reaches the user's cap."""
        cap = self._monthly_cap()
        if cap is None:
            return
        try:
            spent = self._month_to_date()
        except OSError:
            return  # unreadable usage never stops work
        if spent >= cap:
            raise GatewayError("monthly_cap_reached")

    def _usage_command(self, command: CommandEnvelope) -> GatewayReply:
        """A month's estimated model cost, and the monthly cap."""
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        if command.type == "usage.bill":
            self._require_payload(command, set(), optional={"month"})
            this_month = current_month()
            month = command.payload.get("month") or this_month
            if not isinstance(month, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
                raise GatewayError("invalid_month")
            try:
                bill = month_bill(self._usage_databases(), month)
                if month == this_month:
                    self._month_cost = (month, self._clock(), bill.cost_usd)
                spent = bill.cost_usd if month == this_month else self._month_to_date()
            except OSError:
                raise GatewayError("storage_unavailable") from None
            return self._reply(
                "usage.bill.result",
                {
                    "epoch": self.epoch,
                    "month": bill.month,
                    "costUsd": bill.cost_usd,
                    "calls": bill.calls,
                    "inputTokens": bill.input_tokens,
                    "outputTokens": bill.output_tokens,
                    "cachedTokens": bill.cached_tokens,
                    "cacheRatio": round(bill.cache_ratio, 4),
                    "models": [
                        {
                            "model": line.model,
                            "calls": line.calls,
                            "inputTokens": line.input_tokens,
                            "outputTokens": line.output_tokens,
                            "cachedTokens": line.cached_tokens,
                            "costUsd": line.cost_usd,
                            "priced": line.priced,
                        }
                        for line in bill.models
                    ],
                    "days": [{"day": day, "costUsd": cost} for day, cost in bill.days],
                    "unpricedCalls": bill.unpriced_calls,
                    "capUsd": self._monthly_cap(),
                    "monthToDateUsd": spent,
                },
                session_id=None,
            )
        self._require_payload(command, {"capUsd"})
        cap = command.payload.get("capUsd")
        if cap is not None and (
            isinstance(cap, bool)
            or not isinstance(cap, int | float)
            or not 0 < cap <= _MAX_MONTHLY_CAP_USD
        ):
            raise GatewayError("invalid_cap")
        path = self._monthly_cap_path()
        staging = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            staging.write_text(json.dumps({"capUsd": cap}), encoding="utf-8")
            os.replace(staging, path)
        except OSError:
            raise GatewayError("storage_unavailable") from None
        finally:
            staging.unlink(missing_ok=True)
        return self._reply(
            "usage.cap.set.result",
            {"epoch": self.epoch, "capUsd": self._monthly_cap()},
            session_id=None,
        )
