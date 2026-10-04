"""Reproducible phone task catalog and evidence-backed outcome records."""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
from pathlib import Path
from uuid import uuid4

from mobile_connections import connection_database
from mobile_protocol import parse_mobile_task_request
from mobile_workflows import DeviceExecutionChecks, observation_matches

_CASES = (
    (
        "settings-open",
        "打开系统设置",
        "settings",
        "打开系统设置并验证当前应用包",
        {"package": "com.android.settings"},
    ),
    (
        "settings-version",
        "显示系统版本",
        "settings",
        "在系统设置中显示 Android 系统版本数值, 不修改配置",
        {"text_contains": "Android"},
    ),
    (
        "settings-battery",
        "显示电量信息",
        "settings",
        "在系统设置中显示电池用量页面与当前电量数值, 不修改配置",
        {"text_contains": "电池"},
    ),
    (
        "settings-storage",
        "显示存储数值",
        "settings",
        "在系统设置中显示存储页面与空间数值, 不修改配置",
        {"text_contains": "存储"},
    ),
    (
        "settings-search",
        "系统设置搜索",
        "settings",
        "使用设置搜索找到显示设置, 不修改配置",
        {"text_contains": "显示"},
    ),
    (
        "settings-wifi",
        "显示网络连接状态",
        "settings",
        "打开 WLAN 设置并显示网络连接状态, 不切换开关",
        {"text_contains": "WLAN"},
    ),
    (
        "settings-display",
        "查看显示设置",
        "settings",
        "找到显示设置页面, 不修改配置",
        {"text_contains": "显示"},
    ),
    (
        "settings-font",
        "查看文字大小",
        "settings",
        "找到字体大小设置页面, 不修改配置",
        {"text_contains": "字体"},
    ),
    (
        "settings-accessibility",
        "查看无障碍服务",
        "settings",
        "打开无障碍设置并查找 Agent Workspace 服务",
        {"text_contains": "Agent Workspace"},
    ),
    (
        "app-return",
        "返回工作台",
        "workspace",
        "返回 Agent Workspace 工作台",
        {"package": "com.agentworkspace.mobile"},
    ),
    (
        "workspace-menu",
        "打开二级菜单",
        "workspace",
        "打开 Agent Workspace 的菜单",
        {"text_contains": "菜单"},
    ),
    (
        "workspace-model",
        "查看模型设置",
        "workspace",
        "打开模型与思考设置页面, 不保存改动",
        {"text_contains": "模型与思考"},
    ),
    (
        "workspace-usage",
        "查看费用统计",
        "workspace",
        "打开 Token 与费用页面",
        {"text_contains": "Token 与费用"},
    ),
    (
        "workspace-files",
        "打开工作区文件",
        "workspace",
        "打开工作区文件页面",
        {"text_contains": "工作区文件"},
    ),
    (
        "workspace-search",
        "打开会话搜索",
        "workspace",
        "打开会话搜索页面, 不输入或提交搜索",
        {"text_contains": "搜索关键词"},
    ),
    (
        "workspace-notification",
        "查看通知设置",
        "workspace",
        "打开通知设置, 不切换开关",
        {"text_contains": "任务完成通知"},
    ),
    (
        "workspace-doctor",
        "检查设备能力",
        "workspace",
        "打开设备与工具诊断页面",
        {"text_contains": "设备与工具"},
    ),
    (
        "workspace-schedules",
        "查看定时任务",
        "workspace",
        "打开定时任务列表, 不创建任务",
        {"text_contains": "定时任务"},
    ),
    (
        "workspace-workflows",
        "查看可复用流程",
        "workspace",
        "打开可复用流程列表",
        {"text_contains": "可复用流程"},
    ),
    (
        "workspace-connections",
        "查看连接设备",
        "workspace",
        "打开设备连接列表, 不发送数据",
        {"text_contains": "设备连接"},
    ),
    (
        "back-navigation",
        "菜单返回",
        "workspace",
        "从模型设置返回菜单首页",
        {"text_contains": "执行权限"},
    ),
    (
        "home-return",
        "Home 与恢复",
        "workspace",
        "返回桌面后重新打开 Agent Workspace, 验证前台应用",
        {"package": "com.agentworkspace.mobile"},
    ),
    (
        "snapshot-refresh",
        "显示菜单",
        "workspace",
        "打开菜单并验证菜单可见",
        {"text_contains": "菜单"},
    ),
    (
        "form-draft",
        "定位任务输入框",
        "workspace",
        "返回 Agent Workspace 工作台并找到任务输入框, 不输入或发送任务",
        {"text_contains": "任务指令"},
    ),
)

_VISIBLE_VALUES = {
    "settings-version": {"version": r"Android\s*(?:\u7248\u672c\s*)?\d+(?:\.\d+){0,2}\b"},
    "settings-battery": {
        "page": r"\u7535\u6c60\u7528\u91cf|\u7535\u91cf|\u8017\u7535",
        "charge": r"(?<!\d)(?:100|[1-9]?\d)\s*%",
    },
    "settings-storage": {"space": r"\d+(?:[.,]\d+)?\s*(?:GiB|MiB|GB|MB|TB)\b"},
    "settings-wifi": {
        "connection": (
            r"\u5df2\u8fde\u63a5|\u672a\u8fde\u63a5|\u5df2\u65ad\u5f00|"
            r"\u65e0\u4e92\u8054\u7f51"
        )
    },
}


def validate_metadata(metadata):
    fields = {"device", "app_version", "model", "budget_steps", "retry_policy"}
    if not isinstance(metadata, dict) or not fields <= set(metadata):
        raise ValueError(
            "evaluation requires fixed device, app, model, budget and retry policy metadata"
        )
    for key in fields - {"budget_steps"}:
        if (
            not isinstance(metadata[key], str)
            or not metadata[key].strip()
            or len(metadata[key]) > 500
        ):
            raise ValueError(f"invalid evaluation metadata: {key}")
    if type(metadata["budget_steps"]) is not int or not 1 <= metadata["budget_steps"] <= 1000:
        raise ValueError("invalid evaluation step budget")
    return {key: metadata[key] for key in fields}


def _application_observation(observation):
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
        package = observation.get("package") or observation.get("package_name")
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
    return {**observation, "nodes": nodes}


class MobileEvaluations:
    def __init__(self, path: Path):
        self.path = path
        self._jobs = set()
        with connection_database(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS mobile_evaluations "
                "(run_id TEXT PRIMARY KEY, created_at REAL NOT NULL, document TEXT NOT NULL)"
            )
            for row in db.execute("SELECT run_id, document FROM mobile_evaluations"):
                document = json.loads(row[1])
                if document["outcome"] == "running":
                    document.update(
                        outcome="blocked", reason="runtime restarted; inspect current device state"
                    )
                    db.execute(
                        "UPDATE mobile_evaluations SET document=? WHERE run_id=?",
                        (json.dumps(document), row[0]),
                    )

    @staticmethod
    def scenarios():
        return [
            {
                "scenario_id": item[0],
                "name": item[1],
                "app": item[2],
                "prompt": item[3],
                "assertions": {
                    "package": "com.android.settings"
                    if item[2] == "settings"
                    else "com.agentworkspace.mobile",
                    **item[4],
                },
                "verification_scope": "visible_values"
                if item[0] in _VISIBLE_VALUES
                else "terminal_ui",
                "setup": (
                    "unlocked test device; Chinese system UI; fixed app version; "
                    "no pending task; benchmark-fixture session"
                ),
            }
            for item in _CASES
        ]

    def record(self, payload):
        scenario_id = payload.get("scenario_id")
        if scenario_id not in {item[0] for item in _CASES}:
            raise ValueError("unknown evaluation scenario")
        metadata = validate_metadata(payload.get("metadata"))
        outcome = payload.get("outcome")
        if outcome not in {"success", "failure", "blocked", "takeover", "unverified"}:
            raise ValueError("invalid evaluation outcome")
        evidence = payload.get("evidence", {})
        if not isinstance(evidence, dict):
            raise ValueError("evaluation evidence must be a JSON object")
        if outcome == "success" and (
            not isinstance(evidence, dict)
            or evidence.get("verified") is not True
            or evidence.get("kind")
            not in {"package", "ui_assertion", "file_digest", "instrumentation"}
            or not evidence.get("value")
        ):
            raise ValueError("success requires independent terminal evidence")
        metrics = payload.get("metrics", {})
        allowed = {
            "steps",
            "elapsed_seconds",
            "input_tokens",
            "output_tokens",
            "cached_tokens",
            "cost_usd",
            "retries",
            "takeovers",
            "provider_attempts",
        }
        if not isinstance(metrics, dict) or not set(metrics) <= allowed:
            raise ValueError("invalid evaluation metrics")
        for key, value in metrics.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"invalid metric {key}")
        document = {
            "run_id": str(uuid4()),
            "scenario_id": scenario_id,
            "metadata": metadata,
            "outcome": outcome,
            "evidence": evidence,
            "metrics": metrics,
            "measurement_source": "reviewed_record",
            "created_at": time.time(),
        }
        try:
            serialized = json.dumps(document, allow_nan=False)
        except (ValueError, TypeError, RecursionError):
            raise ValueError("evaluation evidence must be bounded finite JSON") from None
        if len(serialized.encode()) > 16384:
            raise ValueError("evaluation record exceeds 16 KiB")
        with connection_database(self.path) as db:
            db.execute(
                "INSERT INTO mobile_evaluations VALUES (?,?,?)",
                (document["run_id"], time.time(), serialized),
            )
        return document

    def export(self, *, limit=200):
        """Export actual recorded executions; scenario declarations never count as outcomes."""
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("evaluation export limit must be from 1 to 500")
        records = self.list()[:limit]
        # Older records remain reviewable but lack provenance for measured rates.
        measured = [
            record
            for record in records
            if record.get("measurement_source") == "controller_execution"
        ]
        reviewed = [
            record
            for record in records
            if record.get("measurement_source") != "controller_execution"
        ]
        finished = [record for record in measured if record["outcome"] != "running"]
        successes = sum(record["outcome"] == "success" for record in finished)
        with connection_database(self.path) as db:
            total = db.execute("SELECT COUNT(*) FROM mobile_evaluations").fetchone()[0]
        export = {
            "format": "agent-workspace.android-evaluations",
            "schema_version": 1,
            "exported_at": time.time(),
            "catalog_count": len(_CASES),
            "measured_runs": measured,
            "reviewed_records": reviewed,
            "summary": {
                "measured_runs": len(measured),
                "measured_finished": len(finished),
                "measured_successes": successes,
                "measured_success_rate": successes / len(finished) if finished else None,
                "reviewed_records": len(reviewed),
            },
            "total_records": total,
            "truncated": total > len(records),
            "scope": (
                "controller task executions on the recorded device/app/model; "
                "declarations and reviewed claims are excluded from measured rates"
            ),
        }
        if len(json.dumps(export, allow_nan=False).encode("utf-8")) > 4 * 1024 * 1024:
            raise ValueError("evaluation export exceeds 4 MiB; request a smaller limit")
        return export

    def export_plan(self, payload):
        """A reproducible run order with fixed task/model/provider attempt ceilings."""
        if not isinstance(payload, dict):
            raise ValueError("evaluation plan requires an object")
        metadata = validate_metadata(payload.get("metadata"))
        scenarios = payload.get("scenario_ids", [item[0] for item in _CASES])
        available = {item[0] for item in _CASES}
        if (
            not isinstance(scenarios, list)
            or not scenarios
            or any(not isinstance(item, str) or item not in available for item in scenarios)
            or len(set(scenarios)) != len(scenarios)
        ):
            raise ValueError("evaluation plan requires unique catalog scenario_ids")
        repetitions = payload.get("repetitions", 1)
        if (
            type(repetitions) is not int
            or not 1 <= repetitions <= 10
            or len(scenarios) * repetitions > 100
        ):
            raise ValueError("evaluation repetitions must be 1 to 10, with at most 100 total runs")
        if type(payload.get("task_retries", 0)) is not int or payload.get("task_retries", 0) != 0:
            raise ValueError(
                "evaluation task retry budget must be zero; "
                "interrupted actions cannot be automatically replayed"
            )
        return {
            "format": "agent-workspace.android-evaluation-plan",
            "schema_version": 1,
            "metadata": metadata,
            "task_retries": 0,
            "provider_attempt_budget": metadata["budget_steps"],
            "turn_timeout_seconds": 900,
            "runs": [
                {
                    "scenario_id": scenario,
                    "repetition": repetition + 1,
                    "model": metadata["model"],
                    "budget_steps": metadata["budget_steps"],
                }
                for repetition in range(repetitions)
                for scenario in scenarios
            ],
            "setup": (
                "Unlocked dedicated Chinese-UI fixture; fixed device, installed app and model; "
                "no pending task. Review approvals in the phone task UI; "
                "reset the declared fixture state between runs."
            ),
            "runner": (
                "python mobile_evaluation_runner.py --endpoint URL --plan plan.json "
                "--session-id FIXTURE_SESSION --output results.json --confirm-fixture-ready"
            ),
        }

    def list(self):
        with connection_database(self.path) as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT document FROM mobile_evaluations ORDER BY created_at DESC LIMIT 500"
                )
            ]

    async def start(self, payload, controller, execute, runtime, metadata):
        scenario = next(
            (
                item
                for item in self.scenarios()
                if item["scenario_id"] == payload.get("scenario_id")
            ),
            None,
        )
        if scenario is None:
            raise ValueError("unknown evaluation scenario")
        if any(
            task.state.value in {"queued", "running", "waiting_approval"}
            for task in controller.list()
        ):
            raise ValueError("wait for the current task before starting an evaluation")
        observation = await execute({"action": "observe"})
        if not observation.get("ok"):
            raise ValueError("evaluation requires a connected and unlocked accessibility device")
        prompt = (
            scenario["prompt"]
            + "\nRequired terminal assertions: "
            + json.dumps(scenario["assertions"], ensure_ascii=False)
        )
        request = parse_mobile_task_request({**payload, "prompt": prompt})
        metadata = {**metadata, "model": request.model or controller.default_model}
        document = self.record(
            {"scenario_id": scenario["scenario_id"], "metadata": metadata, "outcome": "unverified"}
        )
        document.update(
            outcome="running",
            session_id=request.session_id,
            reason=None,
            measurement_source="controller_execution",
            task_retries=0,
            provider_attempt_budget=metadata["budget_steps"],
            turn_timeout_seconds=900,
        )
        document["verification_scope"] = scenario["verification_scope"]
        self._update(document)
        checks = DeviceExecutionChecks(execute)
        try:
            task = await controller.submit(
                request,
                budget_steps=metadata["budget_steps"],
                before_run=checks.before,
                after_run=checks.after,
            )
        except BaseException:
            document.update(outcome="blocked", reason="task could not be submitted")
            self._update(document)
            raise
        document["task_id"] = task.task_id
        self._update(document)
        job = asyncio.create_task(
            self._complete(document, scenario, task.task_id, controller, checks, runtime)
        )
        self._jobs.add(job)
        job.add_done_callback(self._jobs.discard)
        return {"run_id": document["run_id"], "task": task.to_dict()}

    def _update(self, document):
        with connection_database(self.path) as db:
            db.execute(
                "UPDATE mobile_evaluations SET document=? WHERE run_id=?",
                (json.dumps(document), document["run_id"]),
            )

    async def _complete(self, document, scenario, task_id, controller, checks, runtime):
        started = time.monotonic()
        try:
            task = await controller.wait(task_id)
            events = controller.events(task_id)
            actions = [
                event
                for event in events
                if event.payload.get("source_type") == "android.action.result"
                and event.payload.get("data", {}).get("executed") is True
            ]
            document.update(outcome="failure", reason="task did not complete successfully")
            if task.state.value == "succeeded":
                response = checks.final
                observation = _application_observation(response.get("observation", response))
                texts = "\n".join(
                    str(node.get("text") or "")
                    + " "
                    + str(node.get("content_description", node.get("description")) or "")
                    for node in observation["nodes"]
                )
                values = {
                    field: match.group(0)
                    for field, pattern in _VISIBLE_VALUES.get(scenario["scenario_id"], {}).items()
                    if (match := re.search(pattern, texts)) is not None
                }
                verified = (
                    bool(actions)
                    and response.get("ok", False)
                    and observation_matches(observation, scenario["assertions"])
                    and len(values) == len(_VISIBLE_VALUES.get(scenario["scenario_id"], {}))
                )
                document.update(
                    outcome="success" if verified else "unverified",
                    reason=None
                    if verified
                    else (
                        "no confirmed Android action was recorded"
                        if not actions
                        else "terminal assertions or visible values did not match"
                    ),
                )
                if verified:
                    document["evidence"] = {
                        "verified": True,
                        "kind": "ui_assertion",
                        "value": scenario["assertions"],
                        "snapshot_version": observation.get("snapshot_version"),
                        "terminal_values": values,
                        "action_event_ids": [event.event_id for event in actions],
                        "verification_scope": scenario["verification_scope"],
                    }
            elif task.state.value == "cancelled":
                document.update(outcome="takeover", reason="task cancelled by the user")
            elif task.state.value == "interrupted":
                document.update(
                    outcome="blocked", reason="execution interrupted; inspect current device state"
                )
            sources = [event.payload.get("source_type") for event in events]
            metrics = {
                "steps": sources.count("tool.started"),
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "retries": sources.count("model.stream.interrupted"),
                "takeovers": int(document["outcome"] == "takeover"),
                "provider_attempts": sources.count("model.attempted"),
            }
            usage = [
                event.payload.get("data", {})
                for event in events
                if event.payload.get("source_type") == "usage.updated"
            ]
            for field in ("input_tokens", "output_tokens", "cached_tokens"):
                if usage:
                    metrics[field] = sum(
                        item.get(field, 0)
                        for item in usage
                        if type(item.get(field, 0)) is int and item.get(field, 0) >= 0
                    )
            if usage:
                from mobile_usage import _pricing, _read_pricing

                _, prices, _ = _read_pricing(runtime)
                rates = _pricing(task.model, prices["models"])
                if rates:
                    cached = min(metrics["cached_tokens"], metrics["input_tokens"])
                    metrics["cost_usd"] = (
                        (metrics["input_tokens"] - cached) * rates["input_usd_per_million"]
                        + metrics["output_tokens"] * rates["output_usd_per_million"]
                        + cached * rates["cached_usd_per_million"]
                    ) / 1_000_000
            document["metrics"] = metrics
        except asyncio.CancelledError:
            document.update(
                outcome="blocked", reason="verification interrupted; inspect current device state"
            )
            raise
        except Exception:
            document.update(
                outcome="unverified", reason="could not independently verify the device result"
            )
        finally:
            self._update(document)

    async def aclose(self):
        for job in tuple(self._jobs):
            job.cancel()
        await asyncio.gather(*tuple(self._jobs), return_exceptions=True)

    def summary(self):
        records = self.list()
        finished = [record for record in records if record["outcome"] != "running"]
        success = sum(record["outcome"] == "success" for record in finished)
        return {
            "runs": len(records),
            "running": len(records) - len(finished),
            "verified_successes": success,
            "success_rate": success / len(finished) if finished else None,
            "scope": "recorded tasks only; not a competitor benchmark",
        }
