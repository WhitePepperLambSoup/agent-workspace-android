"""Run an exported Android evaluation plan sequentially without automatic task retries."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from urllib.parse import quote

import httpx
from mobile_connections import endpoint_url
from mobile_evaluation import _CASES, validate_metadata


def validate_plan(plan):
    try:
        size = len(json.dumps(plan, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError, RecursionError):
        raise ValueError("evaluation plan must be finite JSON") from None
    if size > 256 * 1024 or not isinstance(plan, dict):
        raise ValueError("evaluation plan exceeds the 256 KiB size limit")
    if (
        plan.get("format") != "agent-workspace.android-evaluation-plan"
        or type(plan.get("schema_version")) is not int
        or plan["schema_version"] != 1
    ):
        raise ValueError("unsupported evaluation plan format/version")
    metadata = validate_metadata(plan.get("metadata"))
    if type(plan.get("task_retries")) is not int or plan["task_retries"] != 0:
        raise ValueError("runner task retry budget must be zero")
    if (
        plan.get("provider_attempt_budget") != metadata["budget_steps"]
        or type(plan.get("turn_timeout_seconds")) is not int
        or plan["turn_timeout_seconds"] != 900
    ):
        raise ValueError("evaluation provider/time budgets differ from the supported fixed plan")
    runs = plan.get("runs")
    if not isinstance(runs, list) or not 1 <= len(runs) <= 100:
        raise ValueError("evaluation plan requires 1 to 100 runs")
    scenarios, seen = {case[0] for case in _CASES}, set()
    for run in runs:
        if not isinstance(run, dict) or set(run) != {
            "scenario_id",
            "repetition",
            "model",
            "budget_steps",
        }:
            raise ValueError("invalid evaluation run fields")
        scenario, repetition = run["scenario_id"], run["repetition"]
        if (
            not isinstance(scenario, str)
            or scenario not in scenarios
            or type(repetition) is not int
            or not 1 <= repetition <= 10
        ):
            raise ValueError("invalid evaluation scenario or repetition")
        if (scenario, repetition) in seen:
            raise ValueError("duplicate evaluation scenario repetition")
        seen.add((scenario, repetition))
        if (
            run["model"] != metadata["model"]
            or type(run["budget_steps"]) is not int
            or run["budget_steps"] != metadata["budget_steps"]
        ):
            raise ValueError("evaluation run differs from fixed model/step budget")
    return metadata, runs


async def _json(client, method, path, **options):
    response = await client.request(method, path, **options)
    response.raise_for_status()
    if len(response.content) > 4 * 1024 * 1024:
        raise ValueError("evaluation response exceeds 4 MiB")
    value = response.json()
    if not isinstance(value, dict):
        raise ValueError("evaluation response must be an object")
    return value


async def run_plan(client, plan, session_id, *, poll_interval=0.5):
    """Return a bounded report; lost submission responses never trigger resubmission."""
    metadata, runs = validate_plan(plan)
    if not isinstance(session_id, str) or not session_id or len(session_id) > 256:
        raise ValueError("fixture session_id is required")
    if (
        not isinstance(poll_interval, (int, float))
        or isinstance(poll_interval, bool)
        or not 0 <= poll_interval <= 60
    ):
        raise ValueError("poll interval must be from 0 to 60 seconds")
    report = {
        "format": "agent-workspace.android-evaluation-batch",
        "schema_version": 1,
        "plan": plan,
        "started_at": time.time(),
        "runner_state": "running",
        "completed_runs": [],
        "remaining_runs": len(runs),
    }
    for run in runs:
        device = await _json(client, "GET", "/mobile/android-system/status")
        for field in ("device", "app_version"):
            if device.get(field) != metadata[field]:
                raise ValueError(f"fixed evaluation {field} changed; no task was submitted")
        if (
            device.get("connected") is not True
            or device.get("paused")
            or device.get("takeover_requested")
        ):
            raise ValueError("evaluation device is disconnected or paused; inspect the fixture")
        tasks = await _json(client, "GET", "/mobile/tasks")
        if any(
            task.get("state") in {"queued", "running", "waiting_approval"}
            for task in tasks.get("tasks", [])
        ):
            raise ValueError("a task is still active; no evaluation was submitted")
        try:
            submitted = await _json(
                client,
                "POST",
                "/mobile/evaluations/run",
                json={
                    "scenario_id": run["scenario_id"],
                    "session_id": session_id,
                    "model": metadata["model"],
                    "metadata": metadata,
                },
            )
        except httpx.HTTPStatusError as exc:
            report.update(
                runner_state="blocked",
                reason=f"evaluation submission rejected with HTTP {exc.response.status_code}",
            )
            break
        except (httpx.HTTPError, ValueError):
            report.update(
                runner_state="interrupted",
                reason="submission outcome unknown; inspect phone tasks before continuing",
            )
            break
        run_id, task = submitted.get("run_id"), submitted.get("task")
        task_id = task.get("task_id") if isinstance(task, dict) else None
        if not isinstance(run_id, str) or not isinstance(task_id, str):
            report.update(
                runner_state="interrupted",
                reason="submission outcome unknown; inspect phone tasks before continuing",
            )
            break
        deadline = time.monotonic() + plan["turn_timeout_seconds"]
        while True:
            try:
                snapshot = await _json(client, "GET", "/mobile/evaluations")
                records = snapshot.get("runs")
                if not isinstance(records, list) or any(
                    not isinstance(item, dict) for item in records
                ):
                    raise ValueError("evaluation response has invalid run records")
            except (httpx.HTTPError, ValueError):
                report.update(
                    runner_state="interrupted",
                    reason=(
                        "evaluation connection lost; inspect the existing task before continuing"
                    ),
                    active_run_id=run_id,
                    active_task_id=task_id,
                )
                break
            record = next((item for item in records if item.get("run_id") == run_id), None)
            if record and record.get("outcome") != "running":
                if (
                    record.get("metadata") != metadata
                    or record.get("measurement_source") != "controller_execution"
                ):
                    raise ValueError(
                        "measured execution differs from the fixed evaluation manifest"
                    )
                report["completed_runs"].append({"repetition": run["repetition"], **record})
                report["remaining_runs"] -= 1
                if record.get("outcome") in {"blocked", "takeover"}:
                    report.update(
                        runner_state="blocked",
                        reason=(
                            "evaluation requires device inspection or user takeover; "
                            "no next task submitted"
                        ),
                    )
                break
            if time.monotonic() >= deadline:
                cancellation_outcome = "unknown"
                try:
                    await _json(
                        client, "POST", f"/mobile/tasks/{quote(task_id, safe='')}/cancel", json={}
                    )
                except (httpx.HTTPError, ValueError):
                    pass
                else:
                    cancellation_outcome = "requested"
                report.update(
                    runner_state="interrupted",
                    reason=(
                        f"evaluation timeout; cancellation {cancellation_outcome}, "
                        "inspect device state before continuing"
                    ),
                    active_run_id=run_id,
                    active_task_id=task_id,
                    cancellation_outcome=cancellation_outcome,
                )
                break
            await asyncio.sleep(poll_interval)
        if report["runner_state"] != "running":
            break
    if report["runner_state"] == "running":
        report["runner_state"] = "completed"
    report["finished_at"] = time.time()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--confirm-fixture-ready", action="store_true")
    arguments = parser.parse_args()
    if not arguments.confirm_fixture_ready:
        parser.error(
            "--confirm-fixture-ready is required after reviewing "
            "the fixed device/app/model and fixture setup"
        )
    token = os.getenv("AGENT_WORKSPACE_MOBILE_TOKEN")
    if not token:
        parser.error(
            "set AGENT_WORKSPACE_MOBILE_TOKEN to a paired gateway token; tokens are never exported"
        )
    if arguments.plan.stat().st_size > 256 * 1024:
        parser.error("plan exceeds 256 KiB")
    plan = json.loads(arguments.plan.read_text(encoding="utf-8"))
    validate_plan(plan)
    endpoint = endpoint_url(arguments.endpoint, allow_lan=True)

    async def run():
        async with httpx.AsyncClient(
            base_url=endpoint,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
            follow_redirects=False,
        ) as client:
            return await run_plan(client, plan, arguments.session_id)

    report = asyncio.run(run())
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = arguments.output.with_suffix(arguments.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    temporary.replace(arguments.output)
    print(
        f"{report['runner_state']}: {len(report['completed_runs'])} recorded executions; "
        f"{report['remaining_runs']} remaining"
    )
    return 0 if report["runner_state"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
