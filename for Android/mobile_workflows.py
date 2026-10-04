"""Reusable Android goals with checked preconditions and independent final assertions."""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from uuid import uuid4

from mobile_connections import connection_database
from mobile_protocol import parse_mobile_task_request
from mobile_workflow_replay import FORMAT, MobileWorkflowReplay, bounded_json, validate_steps


def validate_assertions(value, *, required=True):
    if (
        not isinstance(value, dict)
        or (required and not value)
        or not set(value) <= {"package", "text_contains", "resource_id"}
    ):
        raise ValueError("assertions require package, text_contains or resource_id")
    for key, item in value.items():
        if not isinstance(item, str) or not item.strip() or len(item) > 500:
            raise ValueError(f"invalid assertion {key}")
    return value


def observation_matches(observation, assertions):
    validate_assertions(assertions, required=False)
    if not isinstance(observation, dict) or observation.get("stable", True) is not True:
        return False
    package = observation.get("package") or observation.get("package_name")
    nodes = observation.get("nodes", [])
    if not isinstance(nodes, list):
        nodes = []
    nodes = [
        node
        for node in nodes
        if isinstance(node, dict)
        and node.get("visible", True)
        and not any(node.get(field) for field in ("password", "is_password", "sensitive"))
    ]
    windows = observation.get("windows")
    if isinstance(windows, list) and windows:
        application_ids = {
            window.get("id")
            for window in windows
            if isinstance(window, dict)
            and window.get("type") == 1
            and window.get("package_name") == package
        }
        nodes = [
            node
            for node in nodes
            if node.get("window_id") in application_ids or node.get("window_id") == -1
        ]
    texts = "\n".join(
        str(node.get("text", ""))
        + " "
        + str(node.get("content_description", node.get("description", "")))
        for node in nodes
    )
    resource_ids = {node.get("resource_id", node.get("view_id")) for node in nodes}
    return all(
        {
            "package": package == value,
            "text_contains": value in texts,
            "resource_id": value in resource_ids,
        }[key]
        for key, value in assertions.items()
    )


class DeviceExecutionChecks:
    """Capture observations while the controller still owns the execution lock."""

    def __init__(self, execute, preconditions=None):
        self.execute = execute
        self.preconditions = preconditions or {}
        self.final = {}

    async def before(self):
        observation = await self.execute({"action": "observe"})
        if not observation.get("ok") or not observation_matches(
            observation.get("observation", observation), self.preconditions
        ):
            raise ValueError("device precondition failed; open the expected app first")

    async def after(self):
        try:
            self.final = await self.execute({"action": "observe"})
        except Exception:
            self.final = {"ok": False}


class MobileWorkflows:
    def __init__(self, path: Path):
        self.path = path
        self._jobs = set()
        self.replay = MobileWorkflowReplay(path)
        with connection_database(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS mobile_workflows "
                "(workflow_id TEXT PRIMARY KEY, document TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS mobile_workflow_runs "
                "(run_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, task_id TEXT NOT NULL, "
                "state TEXT NOT NULL, verified INTEGER NOT NULL, "
                "reason TEXT, created_at REAL NOT NULL)"
            )
            db.execute(
                "UPDATE mobile_workflow_runs SET state='interrupted', "
                "reason='runtime restarted; inspect current state' WHERE state='running'"
            )

    def list(self):
        with connection_database(self.path) as db:
            return [
                json.loads(row[0])
                for row in db.execute("SELECT document FROM mobile_workflows ORDER BY workflow_id")
            ]

    def get(self, workflow_id):
        with connection_database(self.path) as db:
            row = db.execute(
                "SELECT document FROM mobile_workflows WHERE workflow_id=?", (workflow_id,)
            ).fetchone()
        if row is None:
            raise KeyError("unknown workflow")
        return json.loads(row[0])

    def save(self, payload):
        payload = bounded_json(payload)
        if not isinstance(payload, dict):
            raise ValueError("workflow must be a JSON object")
        version = payload.get("schema_version", 1)
        if type(version) is not int or version not in {1, 2}:
            raise ValueError("unsupported workflow schema version")
        name, prompt = payload.get("name"), payload.get("prompt")
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError("workflow name is required (max 100 characters)")
        if version == 1 and (
            not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 16384
        ):
            raise ValueError("workflow prompt is required (max 16384 characters)")
        if version == 2:
            if set(payload) - {
                "workflow_id",
                "schema_version",
                "name",
                "prompt",
                "package",
                "preconditions",
                "assertions",
                "steps",
            }:
                raise ValueError("invalid workflow fields")
            if prompt is not None and (not isinstance(prompt, str) or len(prompt) > 16384):
                raise ValueError("workflow prompt must be bounded text")
            steps = validate_steps(payload.get("steps"))
        elif "steps" in payload:
            raise ValueError("action steps require workflow schema version 2")
        preconditions = validate_assertions(payload.get("preconditions", {}), required=False)
        assertions = validate_assertions(payload.get("assertions"))
        package = payload.get("package")
        if package is not None and (
            not isinstance(package, str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+", package)
        ):
            raise ValueError("invalid app package")
        workflow_id = payload.get("workflow_id") or str(uuid4())
        if payload.get("workflow_id"):
            self.get(workflow_id)
        document = {
            "workflow_id": workflow_id,
            "name": name.strip(),
            "prompt": prompt.strip() if prompt else "",
            "package": package,
            "preconditions": preconditions,
            "assertions": assertions,
        }
        if version == 2:
            document.update(schema_version=2, steps=steps)
        with connection_database(self.path) as db:
            db.execute(
                "INSERT OR REPLACE INTO mobile_workflows VALUES (?,?)",
                (workflow_id, json.dumps(document)),
            )
        return document

    def export(self, workflow_id):
        return {"format": FORMAT, "schema_version": 2, "workflow": self.get(workflow_id)}

    def import_document(self, document):
        document = bounded_json(document)
        if (
            not isinstance(document, dict)
            or set(document) != {"format", "schema_version", "workflow"}
            or document["format"] != FORMAT
            or type(document["schema_version"]) is not int
            or document["schema_version"] != 2
        ):
            raise ValueError("unsupported workflow export format or version")
        workflow = document["workflow"]
        if not isinstance(workflow, dict):
            raise ValueError("workflow import requires an object")
        workflow.pop("workflow_id", None)  # imports create a new reviewed copy
        return self.save(workflow)

    def record(self, payload):
        """Import a user-reviewed trace, excluding all unconfirmed or protected actions."""
        payload = bounded_json(payload)
        if not isinstance(payload, dict) or payload.get("reviewed") is not True:
            raise ValueError("workflow recording requires reviewed:true")
        actions = payload.get("actions")
        if not isinstance(actions, list) or not 1 <= len(actions) <= 100:
            raise ValueError("reviewed actions require 1 to 100 entries")
        steps, dropped = [], 0

        def protected(value):
            if isinstance(value, dict):
                return any(
                    value.get(field)
                    for field in ("password", "is_password", "sensitive", "protected")
                ) or any(protected(nested) for nested in value.values())
            if isinstance(value, list):
                return any(protected(nested) for nested in value)
            return isinstance(value, str) and "[redacted]" in value

        fields = {
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
        for raw in actions:
            if not isinstance(raw, dict) or raw.get("executed") is not True or protected(raw):
                dropped += 1
                continue
            step = {key: raw[key] for key in fields if key in raw}
            arguments = raw.get("arguments", {})
            if not isinstance(arguments, dict):
                raise ValueError("reviewed action arguments must be an object")
            action = arguments.get("action", step.get("action"))
            step["action"] = "tap" if action == "ref" else action
            for key in ("text", "package_name"):
                if key in arguments:
                    step[key] = arguments[key]
            steps.append(step)
        if not steps:
            raise ValueError("no confirmed, non-protected action is available to record")
        workflow = self.save(
            {
                "schema_version": 2,
                "name": payload.get("name"),
                "preconditions": payload.get("preconditions", {}),
                "assertions": payload.get("assertions"),
                "steps": steps,
            }
        )
        return {"workflow": workflow, "dropped_actions": dropped}

    def delete(self, workflow_id):
        with connection_database(self.path) as db:
            return (
                db.execute(
                    "DELETE FROM mobile_workflows WHERE workflow_id=?", (workflow_id,)
                ).rowcount
                == 1
            )

    def runs(self):
        with connection_database(self.path) as db:
            legacy = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM mobile_workflow_runs ORDER BY created_at DESC LIMIT 200"
                )
            ]
        return sorted(legacy + self.replay.list(), key=lambda run: run["created_at"], reverse=True)[
            :200
        ]

    def run(self, run_id):
        try:
            return self.replay.get(run_id)
        except KeyError:
            for run in self.runs():
                if run["run_id"] == run_id:
                    return run
            raise KeyError("unknown workflow run") from None

    async def start(self, workflow_id, payload, controller, execute):
        workflow = self.get(workflow_id)
        if workflow.get("schema_version") == 2:
            record = self.replay.create(workflow)
            request = parse_mobile_task_request(
                {**payload, "prompt": f"Replay reviewed workflow: {workflow['name']}"}
            )

            async def execution(task):
                return await self.replay.execute(record["run_id"], task, controller, execute)

            try:
                task = await controller.submit(
                    request,
                    execution=execution,
                    execution_kind="workflow_replay",
                    budget_steps=sum(step["max_retries"] + 1 for step in workflow["steps"]),
                )
            except BaseException:
                record.update(state="failed", reason="workflow task could not be submitted")
                self.replay.update(record)
                raise
            record["task_id"] = task.task_id
            self.replay.update(record)
            self._watch_replay(record["run_id"], task.task_id, controller)
            return {"run_id": record["run_id"], "task": task.to_dict()}
        observed = await execute({"action": "observe"})
        if not observed.get("ok") or not observation_matches(
            observed.get("observation", observed), workflow["preconditions"]
        ):
            raise ValueError("workflow precondition failed; open the expected app first")
        prompt = (
            workflow["prompt"]
            + "\nRequired terminal assertions: "
            + json.dumps(workflow["assertions"], ensure_ascii=False)
        )
        checks = DeviceExecutionChecks(execute, workflow["preconditions"])
        task = await controller.submit(
            parse_mobile_task_request({**payload, "prompt": prompt}),
            before_run=checks.before,
            after_run=checks.after,
        )
        run_id = str(uuid4())
        with connection_database(self.path) as db:
            db.execute(
                "INSERT INTO mobile_workflow_runs VALUES (?,?,?,'running',0,NULL,?)",
                (run_id, workflow_id, task.task_id, time.time()),
            )
        job = asyncio.create_task(self._verify(run_id, workflow, task.task_id, controller, checks))
        self._jobs.add(job)
        job.add_done_callback(self._jobs.discard)
        return {"run_id": run_id, "task": task.to_dict()}

    async def resume(self, run_id, payload, controller, execute):
        if not isinstance(payload, dict) or payload.get("confirm_resume") is not True:
            raise ValueError("workflow resume requires confirm_resume:true")
        record = self.replay.get(run_id)
        self.replay.resumable(record)
        if not record.get("task_id"):
            raise ValueError("workflow has no durable task to resume")

        async def execution(task):
            return await self.replay.execute(run_id, task, controller, execute, resume=True)

        task = await controller.resume(record["task_id"], execution=execution)
        record.update(state="queued", reason=None, resume_available=False)
        self.replay.update(record)
        self._watch_replay(run_id, task.task_id, controller)
        return {"run_id": run_id, "task": task.to_dict()}

    def _watch_replay(self, run_id, task_id, controller):
        job = asyncio.create_task(self._replay_complete(run_id, task_id, controller))
        self._jobs.add(job)
        job.add_done_callback(self._jobs.discard)

    async def _replay_complete(self, run_id, task_id, controller):
        try:
            task = await controller.wait(task_id)
            record = self.replay.get(run_id)
            if record["state"] in {"queued", "running", "waiting_approval"}:
                record.update(
                    state="interrupted"
                    if task.state.value == "interrupted"
                    else "cancelled"
                    if task.state.value == "cancelled"
                    else "failed",
                    reason=task.reason,
                    resume_available=task.resume_available,
                )
                self.replay.update(record)
        except asyncio.CancelledError:
            record = self.replay.get(run_id)
            if record["state"] in {"queued", "running", "waiting_approval"}:
                record.update(
                    state="interrupted",
                    reason="runtime stopped; inspect current state",
                    resume_available=not any(
                        step["action_outcome"] == "unknown" for step in record["steps"]
                    ),
                )
                self.replay.update(record)
            raise

    async def _verify(self, run_id, workflow, task_id, controller, checks):
        state, verified, reason = "failed", False, "task did not complete successfully"
        try:
            task = await controller.wait(task_id)
            if task.state.value == "succeeded":
                observation = checks.final
                verified = observation.get("ok", False) and observation_matches(
                    observation.get("observation", observation), workflow["assertions"]
                )
                state, reason = (
                    ("verified", None)
                    if verified
                    else ("unverified", "terminal assertions did not match")
                )
        except asyncio.CancelledError:
            state, reason = "interrupted", "verification interrupted; inspect the current state"
            raise
        except Exception:
            state, reason = "unverified", "could not observe the terminal state"
        finally:
            with connection_database(self.path) as db:
                db.execute(
                    "UPDATE mobile_workflow_runs SET state=?,verified=?,reason=? WHERE run_id=?",
                    (state, int(verified), reason, run_id),
                )

    async def aclose(self):
        for job in tuple(self._jobs):
            job.cancel()
        await asyncio.gather(*tuple(self._jobs), return_exceptions=True)
