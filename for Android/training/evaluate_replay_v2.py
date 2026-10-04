"""Score frozen v2 predictions by real, isolated tool execution without inference."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ANDROID_ROOT = Path(__file__).resolve().parents[1]
for source in (ANDROID_ROOT, ANDROID_ROOT.parent / "src"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from android_adapter.local_provider import parse_qwen_output  # noqa: E402

from agent_workspace.core.models import DeltaKind  # noqa: E402
from training.build_dataset_v2 import Fixture, _result, compact  # noqa: E402
from training.evaluate_tools import build_evaluation_prompt  # noqa: E402

EXECUTABLE_TOOLS = {
    "read_file",
    "write_file",
    "list_files",
    "search_files",
    "make_directory",
    "select_local_tools",
    "todo",
}
STOP_FAMILIES = {"file_done", "todo_done", "clarify_destination", "reject_tool_instruction"}


def _history(row: dict[str, Any]):
    pending, position = {}, 0
    for message in row["messages"]:
        for previous in message.get("tool_calls", []):
            item = copy.deepcopy(previous["function"])
            if isinstance(item["arguments"], str):
                item["arguments"] = json.loads(item["arguments"])
            pending[previous["id"]] = item
        if message["role"] == "tool":
            yield position, pending.pop(message["tool_call_id"]), _result(message["content"])
            position += 1
    if pending:
        raise ValueError("Unfinished frozen history")


def _normalized_result(result):
    return {"error": result} if isinstance(result, str) else result


def _restore(row, fixture):
    metadata = row["metadata"]
    for directory in metadata["fixture_directories"]:
        if directory not in fixture.initial_dirs:
            fixture.run({"name": "make_directory", "arguments": {"path": directory}})
    for path, content in metadata["fixture_files"].items():
        fixture.seed_file(path, content)
    for position, previous, recorded in _history(row):
        if previous["name"] not in EXECUTABLE_TOOLS:
            raise ValueError("Unsupported frozen historical tool")
        result = _normalized_result(fixture.run(previous))
        if result != recorded:
            raise ValueError(f"Frozen history did not replay: {previous['name']} at {position}")
        for mutation in metadata.get("external_mutations", []):
            if mutation["after_history_step"] == position:
                path, content = mutation["path"], mutation["content"]
                observed = fixture.run({"name": "read_file", "arguments": {"path": path}})
                fixture.run(
                    {
                        "name": "write_file",
                        "arguments": {
                            "path": path,
                            "content": content,
                            "expected_sha256": observed["sha256"],
                        },
                    }
                )


def _bytes_match(fixture, path, desired):
    target = fixture.root / path
    return target.is_file() and target.read_bytes() == desired.encode("utf-8")


def _read_checks(fixture, calls, results, desired_paths):
    full = set()
    for item, result in zip(calls, results, strict=True):
        if item["name"] != "read_file" or "error" in result:
            continue
        path = item["arguments"]["path"]
        if (
            result.get("offset") == 0
            and result.get("truncated") is False
            and _bytes_match(fixture, path, result["content"])
        ):
            full.add(path)
    return {"all_requested_files_read_completely": set(desired_paths) <= full}


def _assess(row, fixture, calls, results, text):
    family, expected = row["metadata"]["family"], row["expected"]
    if family in STOP_FAMILIES:
        checks = {
            "stopped_without_another_tool": not calls,
            "response_meets_frozen_text_criteria": all(
                value in text for value in expected.get("must_contain", [])
            ),
        }
        return checks, all(checks.values()), family != "clarify_destination"
    targets = expected["calls"]
    if family in {
        "copy_from_read",
        "edit_cas",
        "cas_recover_write",
        "create_file",
        "mkdir_selected_write",
    }:
        args = targets[0]["arguments"]
        checks = {
            "requested_file_bytes": _bytes_match(fixture, args["path"], args["content"]),
            "requested_write_executed": any(
                item["name"] == "write_file" and item["arguments"]["path"] == args["path"]
                for item in calls
            ),
        }
        read_back = _read_checks(fixture, calls, results, [args["path"]])[
            "all_requested_files_read_completely"
        ]
        finished = family in {"create_file", "mkdir_selected_write"} or read_back
        return checks, all(checks.values()), finished
    if family in {"copy_verify", "cas_recover_read", "two_reads", "selected_read"}:
        paths = [item["arguments"]["path"] for item in targets]
        checks = _read_checks(fixture, calls, results, paths)
        return checks, all(checks.values()), family in {"copy_verify", "two_reads"}
    if family in {"select_tools", "mkdir_select"}:
        selected = fixture.selector_state.turns[fixture.entity].selected
        required = {"make_directory"} if family == "mkdir_select" else {"read_file", "write_file"}
        checks = {
            "needed_tools_selected": required <= set(selected),
            "selection_executed": any(item["name"] == "select_local_tools" for item in calls),
        }
        return checks, all(checks.values()), False
    if family == "mkdir_recover":
        path = targets[0]["arguments"]["path"]
        checks = {
            "requested_directory_exists": (fixture.root / path).is_dir(),
            "requested_directory_created": any(
                item["name"] == "make_directory" and item["arguments"]["path"] == path
                for item in calls
            ),
        }
        return checks, all(checks.values()), False
    if family == "todo_complete":
        stable_id = targets[0]["arguments"]["id"]
        actual_id = fixture.ids.get(stable_id)
        todos = fixture.store.list_todos(fixture.entity) if fixture.store else ()
        checks = {
            "requested_todo_completed": any(
                todo.id == actual_id
                and todo.status.value == "completed"
                and todo.content == f"检查{fixture.entity}"
                for todo in todos
            )
        }
        return checks, all(checks.values()), True
    raise ValueError(f"No execution outcome criteria for family {family}")


def score_record(row: dict[str, Any], raw_output: str, catalog: dict[str, Any]):
    """No model loads. Parse first, then restore and execute only temporary fixtures.

    Strict comparison is retained as an independent field. Semantic criteria are
    applied only after inference has finished; labels never enter the prompt.
    step_success describes this requested continuation, not autonomous end-to-end
    task success. task_finished is false while more user-requested work remains.
    """
    result = {
        "id": row["id"],
        "family": row["metadata"]["family"],
        "protocol_valid": False,
        "strict_correct": False,
        "semantic_scoring_supported": False,
        "history_replayed": False,
        "execution_success": None,
        "step_success": None,
        "task_finished": None,
        "executed_calls": [],
        "artifact_checks": {},
    }
    try:
        request, _ = build_evaluation_prompt(row)
        text = raw_output.split("<|im_end|>", 1)[0].split("<|endoftext|>", 1)[0]
        deltas = parse_qwen_output(text, request, f"replay-{row['id']}")
        calls = [
            {"name": delta.tool_call.name, "arguments": delta.tool_call.arguments}
            for delta in deltas
            if delta.kind is DeltaKind.TOOL_CALL
        ]
        text = "".join(delta.text or "" for delta in deltas if delta.kind is DeltaKind.TEXT)
        result.update(protocol_valid=True, calls=calls, text=text)
        expected = row["expected"]
        result["strict_correct"] = (
            calls == expected["calls"]
            if expected["kind"] == "tool_call"
            else not calls
            and all(value in text for value in expected.get("must_contain", []))
            and all(value not in text for value in expected.get("forbidden", []))
        )
        if row["metadata"].get("ordinary_retention") or result["family"].startswith("android_"):
            result["semantic_limit"] = (
                "Ordinary text retains frozen substring criteria; Android synthetic bridge "
                "does not establish real UI action, reference, or stale-snapshot success."
            )
            return result
        if any(item["name"] not in EXECUTABLE_TOOLS for item in calls):
            result["semantic_limit"] = (
                "Prediction requires an executor outside this isolated replay."
            )
            return result
        result["semantic_scoring_supported"] = True
        with tempfile.TemporaryDirectory(prefix="agent-v2-outcome-") as temporary:
            fixture = Fixture(Path(temporary) / "workspace", row["metadata"]["entity"], catalog)
            try:
                _restore(row, fixture)
                result["history_replayed"] = True
                original_files = {
                    path: (fixture.root / path).read_bytes()
                    for path in row["metadata"]["fixture_files"]
                }
                target_calls = row["expected"].get("calls", [])
                write_paths = {
                    item["arguments"]["path"]
                    for item in target_calls
                    if item["name"] == "write_file"
                }
                directory_paths = {
                    item["arguments"]["path"]
                    for item in target_calls
                    if item["name"] == "make_directory"
                }
                todo_ids = {
                    item["arguments"]["id"]
                    for item in target_calls
                    if item["name"] == "todo" and "id" in item["arguments"]
                }
                no_unrequested_effects = all(
                    item["arguments"].get("path") in write_paths
                    if item["name"] == "write_file"
                    else item["arguments"].get("path") in directory_paths
                    if item["name"] == "make_directory"
                    else item["arguments"].get("id") in todo_ids
                    and item["arguments"].get("action") in {"complete", "update"}
                    if item["name"] == "todo"
                    else True
                    for item in calls
                )
                outputs = []
                for item in calls:
                    try:
                        output = _normalized_result(fixture.run(item))
                    except Exception as failure:
                        output = {"error": f"{type(failure).__name__}: {failure}"}
                    outputs.append(output)
                    result["executed_calls"].append({"call": item, "result": output})
                    if "error" in output:
                        break
                execution_success = len(outputs) == len(calls) and all(
                    "error" not in output for output in outputs
                )
                result["execution_success"] = execution_success
                if not execution_success:
                    result.update(step_success=False, task_finished=False)
                else:
                    checks, succeeded, finished = _assess(row, fixture, calls, outputs, text)
                    checks["no_unrequested_side_effects"] = no_unrequested_effects
                    checks["other_initial_files_unchanged"] = all(
                        path in write_paths or (fixture.root / path).read_bytes() == content
                        for path, content in original_files.items()
                    )
                    succeeded = succeeded and all(checks.values())
                    result.update(
                        artifact_checks=checks,
                        step_success=succeeded,
                        task_finished=bool(succeeded and finished),
                    )
            finally:
                fixture.close()
    except Exception as failure:
        result["error"] = f"{type(failure).__name__}: {failure}"
        if result["semantic_scoring_supported"]:
            result.update(step_success=None, task_finished=None, execution_success=None)
    return result


def score_report(records, prediction_report, catalog):
    by_id = {row["id"]: row for row in records}
    scored = []
    for sample in prediction_report["samples"]:
        if sample["id"] not in by_id:
            raise ValueError("Prediction ID is absent from the frozen dataset")
        scored.append(score_record(by_id[sample["id"]], sample["raw_output"], catalog))
    eligible = [row for row in scored if row["step_success"] is not None]
    summary = {
        "samples": len(scored),
        "execution_scored_samples": len(eligible),
        "protocol_valid_count": sum(row["protocol_valid"] for row in scored),
        "strict_correct_count": sum(row["strict_correct"] for row in scored),
        "step_success_count": sum(row["step_success"] for row in eligible),
        "task_finished_count": sum(row["task_finished"] for row in eligible),
        "strict_mismatches_with_execution_success": [
            row["id"] for row in eligible if row["step_success"] and not row["strict_correct"]
        ],
        "family_counts": dict(Counter(row["family"] for row in scored)),
    }
    return {
        "summary": summary,
        "samples": scored,
        "prediction_control_only": prediction_report.get("oracle_control_only", False),
        "expected_answers_given_to_model": False,
        "model_inference_performed": False,
        "executor_scope": "real filesystem/Todo/tool selection in disposable synthetic workspaces",
        "limits": [
            "Continuation replay is not an autonomous end-to-end episode.",
            "Android and ordinary answer semantics are unscored; strict criteria remain visible.",
            "Execution success alone does not establish correct content or task completion.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh output path to preserve prior evaluation evidence")
    records = [
        json.loads(line)
        for line in args.eval.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if any(
        row.get("metadata", {}).get("data_source") != "procedural_synthetic_v2" for row in records
    ):
        parser.error(
            "Isolated execution replay requires v2 fixture metadata; v1 remains historical"
        )
    catalog = json.loads(args.catalog.read_text(encoding="utf-8-sig"))
    predictions = json.loads(args.predictions.read_text(encoding="utf-8-sig"))
    expected_hash = hashlib.sha256(args.eval.read_bytes()).hexdigest()
    if predictions.get("eval_sha256") not in {None, expected_hash}:
        parser.error("Prediction report refers to a different frozen evaluation dataset")
    report = score_report(records, predictions, catalog)
    report["provenance"] = {
        "eval_sha256": expected_hash,
        "catalog_sha256": hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
        "predictions_sha256": hashlib.sha256(args.predictions.read_bytes()).hexdigest(),
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(compact(report["summary"]), flush=True)


if __name__ == "__main__":
    main()
