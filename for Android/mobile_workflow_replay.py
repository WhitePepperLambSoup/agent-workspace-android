"""Bounded declarative Android replay with durable, fail-closed action checkpoints."""

from __future__ import annotations

import asyncio
import json
import re
import time
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

from mobile_connections import connection_database

FORMAT = "agent-workspace.android-workflow"
MAX_DOCUMENT_BYTES = 256 * 1024
MAX_STEPS = 100
_SELECTOR_FIELDS = {"resource_id", "text", "content_description", "class_name", "package"}
_ACTIONS = {"tap", "type_text", "launch_app", "back", "home"}
_PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+")


def bounded_json(value):
    if isinstance(value, str):
        if len(value.encode("utf-8")) > MAX_DOCUMENT_BYTES:
            raise ValueError("workflow JSON exceeds the 256 KiB size limit")
        try:
            value = json.loads(
                value,
                parse_constant=lambda _value: (_ for _ in ()).throw(
                    ValueError("invalid JSON number")
                ),
            )
        except (ValueError, RecursionError):
            raise ValueError("invalid workflow JSON") from None
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise ValueError("workflow must be finite JSON") from None
    if len(encoded.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise ValueError("workflow JSON exceeds the 256 KiB size limit")
    return deepcopy(value)


def validate_selector(value):
    if not isinstance(value, dict) or not value or not set(value) <= _SELECTOR_FIELDS:
        raise ValueError(
            "selector requires semantic fields; saved refs and coordinates are forbidden"
        )
    if not set(value) & {"resource_id", "text", "content_description"}:
        raise ValueError("selector requires resource_id, text or content_description")
    for key, item in value.items():
        if not isinstance(item, str) or not item.strip() or len(item) > 500 or "[redacted]" in item:
            raise ValueError(f"invalid selector {key}")
    return dict(value)


def validate_steps(value):
    from mobile_workflows import validate_assertions

    if not isinstance(value, list) or not 1 <= len(value) <= MAX_STEPS:
        raise ValueError("workflow requires 1 to 100 action steps")
    result, identifiers = [], set()
    allowed = {
        "step_id",
        "action",
        "selector",
        "text",
        "package_name",
        "preconditions",
        "postconditions",
        "timeout_ms",
        "max_retries",
    }
    for index, raw in enumerate(value):
        if not isinstance(raw, dict) or set(raw) - allowed:
            raise ValueError(
                "invalid workflow step fields; saved refs and coordinates are forbidden"
            )
        action = raw.get("action")
        if action not in _ACTIONS:
            raise ValueError("unsupported workflow action")
        identifier = raw.get("step_id", f"step-{index + 1}")
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", identifier)
            or identifier in identifiers
        ):
            raise ValueError("step_id must be unique and bounded")
        identifiers.add(identifier)
        timeout, retries = raw.get("timeout_ms", 5000), raw.get("max_retries", 0)
        if type(timeout) is not int or not 100 <= timeout <= 5000:
            raise ValueError("step timeout_ms must be from 100 to 5000")
        if type(retries) is not int or not 0 <= retries <= 2:
            raise ValueError("step max_retries must be from 0 to 2")
        step = {
            "step_id": identifier,
            "action": action,
            "preconditions": validate_assertions(raw.get("preconditions")),
            "postconditions": validate_assertions(raw.get("postconditions")),
            "timeout_ms": timeout,
            "max_retries": retries,
        }
        if action in {"tap", "type_text"}:
            step["selector"] = validate_selector(raw.get("selector"))
        elif "selector" in raw:
            raise ValueError("this workflow action does not accept a selector")
        if action == "type_text":
            text = raw.get("text")
            if not isinstance(text, str) or not text or len(text) > 4096 or "[redacted]" in text:
                raise ValueError(
                    "type_text requires reviewed non-protected text (max 4096 characters)"
                )
            step["text"] = text
        elif "text" in raw:
            raise ValueError("text is only supported for type_text")
        if action == "launch_app":
            package = raw.get("package_name")
            if (
                not isinstance(package, str)
                or len(package) > 255
                or not _PACKAGE.fullmatch(package)
            ):
                raise ValueError("launch_app requires a valid package_name")
            step["package_name"] = package
        elif "package_name" in raw:
            raise ValueError("package_name is only supported for launch_app")
        result.append(step)
    return result


def select_target(observation, selector, *, editable=False):
    """Choose one visible, enabled, unprotected app node from a fresh complete tree."""
    validate_selector(selector)
    if observation.get("stable") is not True or observation.get("truncated"):
        raise ValueError("selector requires a stable, complete fresh tree")
    nodes = observation.get("nodes")
    if not isinstance(nodes, list) or len(nodes) > 400:
        raise ValueError("selector requires a bounded node tree")
    package = observation.get("package") or observation.get("package_name")
    fields = {
        "resource_id": ("resource_id", "view_id"),
        "content_description": ("content_description", "description"),
    }
    matches = []
    by_ref = {node.get("ref"): node for node in nodes if isinstance(node, dict)}
    windows = observation.get("windows")
    application_ids = None
    if isinstance(windows, list) and windows:
        application_ids = {
            window.get("id")
            for window in windows
            if isinstance(window, dict)
            and window.get("type") == 1
            and window.get("package_name") == package
        }
    for node in nodes:
        if not isinstance(node, dict):
            continue

        def field(key, current_node=node):
            if key == "package":
                return current_node.get("package_name") or package
            aliases = fields.get(key, (key,))
            return next(
                (current_node[name] for name in aliases if current_node.get(name) is not None), None
            )

        if all(field(key) == value for key, value in selector.items()):
            matches.append(node)
    if len(matches) != 1:
        raise ValueError("selector is ambiguous" if matches else "selector target is missing")
    node = matches[0]
    if node.get("visible") is not True or node.get("enabled") is False:
        raise ValueError("selector target is offscreen or disabled")
    if application_ids is not None and node.get("window_id") not in application_ids:
        raise ValueError("selector target is outside the current application window")
    visited, parent = set(), node
    while isinstance(parent, dict):
        if any(parent.get(key) for key in ("password", "is_password", "sensitive")):
            raise ValueError("selector target contains protected content")
        parent_ref = parent.get("parent_ref")
        if not parent_ref or parent_ref in visited:
            break
        visited.add(parent_ref)
        parent = by_ref.get(parent_ref)
    if editable and node.get("editable") is not True:
        raise ValueError("selector target is not editable")
    ref = node.get("ref")
    if not isinstance(ref, str) or not re.fullmatch(r"n[0-9]{1,3}", ref):
        raise ValueError("selector target lacks a fresh Android reference")
    return ref


class ReplayInterrupted(RuntimeError):
    """Execution may have occurred; callers must not replay the action."""


class _ReplayStepBudget:
    """Charge device operations and verification polling, excluding approval and metadata."""

    def __init__(self, timeout_ms):
        self.remaining = timeout_ms / 1000

    async def call(self, operation, *arguments):
        if self.remaining <= 0:
            raise TimeoutError("workflow device budget exhausted")
        started = time.monotonic()
        try:
            async with asyncio.timeout(self.remaining):
                return await operation(*arguments)
        finally:
            self.remaining = max(0, self.remaining - (time.monotonic() - started))


class MobileWorkflowReplay:
    def __init__(self, path):
        self.path = path
        with connection_database(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS mobile_workflow_replays "
                "(run_id TEXT PRIMARY KEY, created_at REAL NOT NULL, document TEXT NOT NULL)"
            )
            for row in db.execute("SELECT run_id,document FROM mobile_workflow_replays"):
                record = json.loads(row[1])
                if record["state"] in {"running", "queued", "waiting_approval"}:
                    record.update(
                        state="interrupted",
                        reason="runtime restarted; explicit resume and state inspection required",
                    )
                    for step in record["steps"]:
                        if step["state"] == "dispatching":
                            step.update(state="interrupted", action_outcome="unknown")
                    record["resume_available"] = not any(
                        step["action_outcome"] == "unknown" for step in record["steps"]
                    )
                    db.execute(
                        "UPDATE mobile_workflow_replays SET document=? WHERE run_id=?",
                        (json.dumps(record), row[0]),
                    )

    def create(self, workflow):
        record = {
            "run_id": str(uuid4()),
            "workflow_id": workflow["workflow_id"],
            "workflow": deepcopy(workflow),
            "task_id": None,
            "state": "queued",
            "verified": 0,
            "reason": None,
            "created_at": time.time(),
            "resume_available": False,
            "steps": [
                {
                    "step_id": step["step_id"],
                    "state": "pending",
                    "action_outcome": "not_executed",
                    "attempts": 0,
                    "verified": False,
                }
                for step in workflow["steps"]
            ],
        }
        with connection_database(self.path) as db:
            db.execute(
                "INSERT INTO mobile_workflow_replays VALUES (?,?,?)",
                (record["run_id"], record["created_at"], json.dumps(record)),
            )
        return record

    def get(self, run_id):
        with connection_database(self.path) as db:
            row = db.execute(
                "SELECT document FROM mobile_workflow_replays WHERE run_id=?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError("unknown workflow replay")
        return json.loads(row[0])

    def list(self):
        with connection_database(self.path) as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT document FROM mobile_workflow_replays "
                    "ORDER BY created_at DESC LIMIT 200"
                )
            ]

    def update(self, record):
        record["updated_at"] = time.time()
        with connection_database(self.path) as db:
            db.execute(
                "UPDATE mobile_workflow_replays SET document=? WHERE run_id=?",
                (json.dumps(record, allow_nan=False), record["run_id"]),
            )

    def resumable(self, record):
        if any(step["action_outcome"] == "unknown" for step in record["steps"]):
            raise ValueError(
                "unknown action outcome requires user inspection; replay resume is blocked"
            )
        if record["state"] != "interrupted" or not record.get("resume_available"):
            raise ValueError("workflow replay is not resumable")

    async def _observe(self, execute):
        response = await execute({"action": "observe"})
        observation = response.get("observation", response) if isinstance(response, dict) else {}
        if (
            not response.get("ok")
            or observation.get("stable") is not True
            or observation.get("truncated")
        ):
            raise ValueError("workflow requires a stable, complete device observation")
        version = observation.get("snapshot_version")
        if not isinstance(version, str) or not version or len(version) > 128:
            raise ValueError("workflow requires a fresh snapshot version")
        return observation

    @staticmethod
    def _request(step, observation):
        request = {
            "action": "ref" if step["action"] == "tap" else step["action"],
            "snapshot_version": observation["snapshot_version"],
            "timeout_ms": step["timeout_ms"],
        }
        if step["action"] in {"tap", "type_text"}:
            request["ref"] = select_target(
                observation, step["selector"], editable=step["action"] == "type_text"
            )
        for field in ("text", "package_name"):
            if field in step:
                request[field] = step[field]
        return request

    async def _event(self, controller, task, kind, data):
        from agent_workspace.core.events import Event

        event = controller.runtime.store.append(
            Event(session_id=task.session_id, type=kind, data=data)
        )
        await controller.handle_runtime_event(event)

    async def _verify(self, execute, assertions):
        from mobile_workflows import observation_matches

        while True:
            observation = await self._observe(execute)
            if observation_matches(observation, assertions):
                return observation
            await asyncio.sleep(0.05)

    async def execute(self, run_id, task, controller, execute, *, resume=False):
        from mobile_workflows import observation_matches

        record = self.get(run_id)
        record.update(task_id=task.task_id, state="running", reason=None, resume_available=False)
        self.update(record)
        try:
            async with asyncio.timeout(5):
                observation = await self._observe(execute)
            if resume:
                confirmed = [
                    index
                    for index, checkpoint in enumerate(record["steps"])
                    if checkpoint["action_outcome"] == "executed"
                ]
                if confirmed and not observation_matches(
                    observation, record["workflow"]["steps"][confirmed[-1]]["postconditions"]
                ):
                    raise ValueError("last confirmed workflow state changed; resume is blocked")
            elif not observation_matches(observation, record["workflow"]["preconditions"]):
                raise ValueError("workflow precondition failed; open the expected app first")
            for step, checkpoint in zip(record["workflow"]["steps"], record["steps"], strict=True):
                if checkpoint["state"] == "verified":
                    continue
                if checkpoint["action_outcome"] == "unknown":
                    raise ReplayInterrupted("unknown action outcome; inspect device state")
                budget = _ReplayStepBudget(step["timeout_ms"])

                async def execute_action(request, budget=budget):
                    return await budget.call(execute, request)

                if checkpoint["action_outcome"] != "executed":
                    while checkpoint["attempts"] <= step["max_retries"]:
                        observation = await budget.call(self._observe, execute)
                        if not observation_matches(observation, step["preconditions"]):
                            raise ValueError(f"step {step['step_id']} precondition failed")
                        request = self._request(step, observation)
                        checkpoint["state"] = "waiting_approval"
                        self.update(record)
                        await controller.authorize_replay_action(
                            request, selector=step.get("selector")
                        )
                        # Approval can take time. Never send the previously observed ref.
                        observation = await budget.call(self._observe, execute)
                        if not observation_matches(observation, step["preconditions"]):
                            raise ValueError("step state changed while awaiting approval")
                        request = self._request(step, observation)
                        await asyncio.sleep(0)  # cancellation before durable dispatch
                        checkpoint.update(
                            state="dispatching",
                            action_outcome="unknown",
                            attempts=checkpoint["attempts"] + 1,
                        )
                        self.update(record)  # commit before external side effects
                        response = await controller.dispatch_replay_action(request, execute_action)
                        executed = response.get("executed") if isinstance(response, dict) else None
                        checkpoint["action_outcome"] = (
                            "executed"
                            if executed is True
                            else "not_executed"
                            if executed is False
                            else "unknown"
                        )
                        checkpoint["state"] = (
                            "verifying"
                            if executed is True
                            else "rejected"
                            if executed is False
                            else "interrupted"
                        )
                        error = response.get("error", {}) if isinstance(response, dict) else {}
                        checkpoint["error_code"] = (
                            error.get("code") if isinstance(error, dict) else None
                        )
                        self.update(record)
                        if executed is True:
                            break
                        if executed is not False:
                            raise ReplayInterrupted(
                                "Android did not confirm execution; "
                                "unknown action must not be repeated"
                            )
                        if (
                            checkpoint["error_code"] != "stale_snapshot"
                            or checkpoint["attempts"] > step["max_retries"]
                        ):
                            raise ValueError(
                                "Android rejected the workflow action; no safe retry remains"
                            )
                        await self._event(
                            controller,
                            task,
                            "workflow.step.retry",
                            {
                                "run_id": run_id,
                                "step_id": step["step_id"],
                                "attempts": checkpoint["attempts"],
                                "reason": "stale_snapshot; confirmed unexecuted",
                            },
                        )
                    if checkpoint["action_outcome"] != "executed":
                        raise ValueError("workflow step retry budget exhausted")
                await budget.call(self._verify, execute, step["postconditions"])
                checkpoint.update(state="verified", verified=True, confirmed_at=time.time())
                self.update(record)
                await self._event(
                    controller,
                    task,
                    "workflow.step.verified",
                    {
                        "run_id": run_id,
                        "step_id": step["step_id"],
                        "executed": True,
                        "verified": True,
                    },
                )
            async with asyncio.timeout(5):
                observation = await self._observe(execute)
            if not observation_matches(observation, record["workflow"]["assertions"]):
                raise ValueError("workflow terminal assertions did not match")
            record.update(state="verified", verified=1, reason=None, resume_available=False)
            self.update(record)
            return SimpleNamespace(text=f"Workflow verified: {record['workflow']['name']}")
        except asyncio.CancelledError:
            unknown = any(step["action_outcome"] == "unknown" for step in record["steps"])
            stopped = getattr(controller, "_closing", False)
            record.update(
                state="interrupted" if stopped or unknown else "cancelled",
                reason="execution interrupted; inspect current device state"
                if stopped or unknown
                else "cancelled by client",
                resume_available=stopped and not unknown,
            )
            self.update(record)
            raise
        except (ReplayInterrupted, TimeoutError) as exc:
            unknown = any(step["action_outcome"] == "unknown" for step in record["steps"])
            record.update(
                state="interrupted" if unknown else "failed",
                reason="unknown action outcome; resume blocked"
                if unknown
                else "workflow step timed out",
                resume_available=False,
            )
            self.update(record)
            if unknown:
                raise ReplayInterrupted(record["reason"]) from exc
            raise ValueError(record["reason"]) from exc
        except Exception as exc:
            if any(step["action_outcome"] == "unknown" for step in record["steps"]):
                record.update(
                    state="interrupted",
                    reason="Android action result was lost; unknown outcome must not be repeated",
                    resume_available=False,
                )
                self.update(record)
                raise ReplayInterrupted(record["reason"]) from exc
            record.update(state="failed", reason=str(exc)[:500], resume_available=False)
            self.update(record)
            raise
