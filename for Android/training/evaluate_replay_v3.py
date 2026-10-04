"""Score V3 synthetic continuations using real isolated tools, without inference."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
from training.build_dataset_v2 import Fixture, compact  # noqa: E402
from training.build_dataset_v3 import FAMILIES, _active  # noqa: E402
from training.evaluate_replay_v2 import _history, _normalized_result, _restore  # noqa: E402
from training.evaluate_tools import build_evaluation_prompt  # noqa: E402

READ_FAMILIES = {"copy_initial_read", "edit_initial_read", "copy_selected_read"}
READBACK_FAMILIES = {"copy_read_back", "edit_read_back"}
WRITE_FAMILIES = {"copy_observed_write", "edit_observed_write", "mkdir_after_directory"}
DONE_FAMILIES = {"copy_verified_done", "edit_verified_done"}
EXECUTABLE_TOOLS = {
    "read_file",
    "write_file",
    "list_files",
    "search_files",
    "make_directory",
    "select_local_tools",
}


def _bytes_match(fixture, path, content):
    file = fixture.root / path
    return file.is_file() and file.read_bytes() == content.encode("utf-8")


def _files(fixture):
    return {
        str(path.relative_to(fixture.root)).replace("\\", "/"): path.read_bytes()
        for path in fixture.root.rglob("*")
        if path.is_file()
    }


def _full_read(fixture, calls, outputs, path, content):
    return any(
        item["name"] == "read_file"
        and item["arguments"]["path"] == path
        and "error" not in output
        and output.get("offset") == 0
        and output.get("truncated") is False
        and output.get("content") == content
        and _bytes_match(fixture, path, content)
        for item, output in zip(calls[: len(outputs)], outputs, strict=True)
    )


def _last_write(history, path=None):
    return next(
        (
            item["arguments"]
            for _, item, output in reversed(history)
            if item["name"] == "write_file"
            and "error" not in output
            and (path is None or item["arguments"]["path"] == path)
        ),
        None,
    )


def _preconditions(row, fixture, history):
    family = row["metadata"]["family"]
    target = row["expected"].get("calls", [{}])[0].get("arguments", {})
    checks, path, desired = {}, target.get("path"), None
    if family in READ_FAMILIES:
        desired = row["metadata"]["fixture_files"][path]
        checks["requested_source_bytes_present"] = _bytes_match(fixture, path, desired)
    elif family in WRITE_FAMILIES:
        desired = target["content"]
        if target["expected_sha256"] is None:
            checks["new_file_absent"] = not (fixture.root / path).exists()
        else:
            observed = {
                item["arguments"]["path"]: output["sha256"]
                for _, item, output in history
                if item["name"] == "read_file" and "sha256" in output
            }
            file = fixture.root / path
            checks["observed_existing_preimage_matches_file"] = (
                file.is_file()
                and observed.get(path) == target["expected_sha256"]
                and hashlib.sha256(file.read_bytes()).hexdigest() == target["expected_sha256"]
            )
        if family == "mkdir_after_directory":
            checks["parent_directory_already_exists"] = (fixture.root / path).parent.is_dir()
    elif family in READBACK_FAMILIES or family in DONE_FAMILIES:
        written = _last_write(history, path)
        if written is None:
            raise ValueError("Readback/terminal fixture has no preceding successful write")
        path, desired = written["path"], written["content"]
        checks["requested_file_bytes_already_present"] = _bytes_match(fixture, path, desired)
        if family in DONE_FAMILIES:
            write_position = max(
                position
                for position, item, output in history
                if item["name"] == "write_file"
                and item["arguments"]["path"] == path
                and "error" not in output
            )
            checks["historical_full_readback_verified"] = any(
                position > write_position
                and item["name"] == "read_file"
                and item["arguments"]["path"] == path
                and output.get("offset") == 0
                and output.get("truncated") is False
                and output.get("content") == desired
                for position, item, output in history
            )
            if family == "copy_verified_done" and row["split"] == "eval":
                checks["historical_requested_archive_listing_verified"] = any(
                    item["name"] == "list_files"
                    and item["arguments"].get("path") == "archive"
                    and "error" not in output
                    for _, item, output in history
                )
            elif family == "copy_verified_done" and row["split"] == "dev":
                source = next(iter(row["metadata"]["fixture_files"]))
                checks["historical_source_comparison_verified"] = any(
                    position > write_position
                    and item["name"] == "read_file"
                    and item["arguments"]["path"] == source
                    and output.get("offset") == 0
                    and output.get("truncated") is False
                    and output.get("content") == desired
                    for position, item, output in history
                )
    elif family == "mkdir_after_select":
        checks["requested_directory_absent"] = not (fixture.root / path).exists()
        checks["directory_and_write_tools_selected"] = set(
            fixture.selector_state.turns[fixture.entity].selected
        ) == {"make_directory", "write_file"}
    elif family != "mkdir_initial_select":
        raise ValueError(f"Unsupported V3 stage {family}")
    return checks, path, desired


def _completion_statement(text):
    """Conservative completion wording; this is not general natural-language grading."""
    negative = re.search(
        r"未|还没|没有|失败|无法|不确定|待完成"
        r"|\b(?:not|never|cannot|can['\u2019]t|haven['\u2019]t|hasn['\u2019]t"
        r"|hadn['\u2019]t|didn['\u2019]t|isn['\u2019]t|wasn['\u2019]t|aren['\u2019]t"
        r"|weren['\u2019]t|won['\u2019]t|unfinished|failed|pending|will|might|would)\b",
        text,
        re.IGNORECASE,
    )
    question = re.search(
        r"[?\uFF1F]|是否|(?:完成|核验|编辑|复制)了?吗"
        r"|^\s*(?:has|have|is|are|was|were|did|does|do|can|could|would|should|will)\b",
        text,
        re.IGNORECASE,
    )
    affirmative = re.search(
        r"已(?:经)?完成|完成了|已(?:经)?(?:复制|编辑|归档|备份|核验|验证|检查)"
        r"|\b(?:completed|done|copied|edited|archived|verified|checked)\b",
        text,
        re.IGNORECASE,
    )
    return bool(text.strip() and affirmative and not negative and not question)


def score_record(row: dict[str, Any], raw_output: str, catalog: dict[str, Any]):
    """Replay only this predicted continuation. History establishes preconditions.

    Historical writes/readback never count as predicted actions. All end-to-end
    task-success fields remain unmeasured. Ordinary answers need a separate
    preservation audit; exact target matching here never uses substring credit.
    """
    family = row["metadata"]["family"]
    supported = family in FAMILIES and not row["metadata"].get("ordinary_retention")
    result = {
        "id": row["id"],
        "family": family,
        "protocol_valid": False,
        "strict_correct": False,
        "semantic_scoring_supported": supported,
        "preservation_audit_required": bool(row["metadata"].get("ordinary_retention")),
        "prediction_generation_success": True,
        "history_replayed": False,
        "known_precondition": None,
        "precondition_checks": {},
        "execution_success": None,
        "step_success": False if supported else None,
        "filebytes_readback": False if family in READBACK_FAMILIES else None,
        "terminal_continuation": False if supported else None,
        "autonomous_task_success": None,
        "executed_calls": [],
        "artifact_checks": {},
    }
    try:
        request, _ = build_evaluation_prompt(row)
        text = raw_output.split("<|im_end|>", 1)[0].split("<|endoftext|>", 1)[0]
        deltas = parse_qwen_output(text, request, f"replay-v3-{row['id']}")
        calls = [
            {"name": delta.tool_call.name, "arguments": delta.tool_call.arguments}
            for delta in deltas
            if delta.kind is DeltaKind.TOOL_CALL
        ]
        text = "".join(delta.text or "" for delta in deltas if delta.kind is DeltaKind.TEXT)
        expected = row["expected"]
        result.update(protocol_valid=True, calls=calls, text=text)
        result["strict_correct"] = (
            calls == expected["calls"]
            if expected["kind"] == "tool_call"
            else not calls and text.strip() == row["target_response"].strip()
        )
        if not supported:
            result["semantic_limit"] = (
                "Ordinary text semantics require a separate preservation audit"
            )
            return result
        if row["metadata"].get("data_source") != "procedural_synthetic_v3_candidate":
            raise ValueError("V3 replay requires its frozen fixture metadata")
        if any(item["name"] not in EXECUTABLE_TOOLS for item in calls):
            raise ValueError("Prediction needs an executor outside the isolated file replay")
        history = list(_history(row))
        allowed = {*row["metadata"]["runtime_available_tools"], "select_local_tools"}
        task_catalog = {name: entry for name, entry in catalog.items() if name in allowed}
        with tempfile.TemporaryDirectory(prefix="agent-v3-continuation-") as temporary:
            fixture = Fixture(Path(temporary) / "workspace", row["metadata"]["entity"], catalog)
            try:
                _active(fixture, task_catalog)
                _restore(row, fixture)
                active, selected = _active(fixture, task_catalog)
                menu_exact = (
                    active == row["tools"] and selected == row["metadata"]["runtime_selected_tools"]
                )
                preconditions, path, desired = _preconditions(row, fixture, history)
                preconditions.update(history_replayed=True, runtime_menu_exact=menu_exact)
                result.update(
                    history_replayed=True,
                    precondition_checks=preconditions,
                    known_precondition=all(preconditions.values()),
                )
                if not result["known_precondition"]:
                    result["fixture_error"] = (
                        "Frozen history/menu/stage preconditions did not validate"
                    )
                    result["step_success"] = None
                    return result
                before = _files(fixture)
                targets = expected.get("calls", [])
                write_paths = {
                    item["arguments"]["path"] for item in targets if item["name"] == "write_file"
                }
                dir_paths = {
                    item["arguments"]["path"]
                    for item in targets
                    if item["name"] == "make_directory"
                }
                no_unrequested = all(
                    item["arguments"]["path"] in write_paths
                    if item["name"] == "write_file"
                    else item["arguments"]["path"] in dir_paths
                    if item["name"] == "make_directory"
                    else family == "mkdir_initial_select"
                    if item["name"] == "select_local_tools"
                    else True
                    for item in calls
                )
                observed = {
                    item["arguments"]["path"]: output["sha256"]
                    for _, item, output in history
                    if item["name"] == "read_file" and "sha256" in output
                }
                outputs, write_known = [], []
                for item in calls:
                    args = item["arguments"]
                    if item["name"] == "write_file":
                        file = fixture.root / args["path"]
                        write_known.append(
                            args["expected_sha256"] is None
                            if not file.exists()
                            else file.is_file()
                            and args["expected_sha256"] is not None
                            and args["expected_sha256"] == observed.get(args["path"])
                            and hashlib.sha256(file.read_bytes()).hexdigest()
                            == args["expected_sha256"]
                        )
                    try:
                        output = _normalized_result(fixture.run(item))
                    except Exception as failure:
                        output = {"error": f"{type(failure).__name__}: {failure}"}
                    outputs.append(output)
                    result["executed_calls"].append({"call": item, "result": output})
                    if "error" in output:
                        break
                    if item["name"] == "read_file":
                        observed[args["path"]] = output["sha256"]
                executed = len(outputs) == len(calls) and all(
                    "error" not in output for output in outputs
                )
                checks = {
                    "no_unrequested_side_effects": no_unrequested,
                    "other_files_unchanged": all(
                        name in write_paths
                        or (
                            (fixture.root / name).is_file()
                            and (fixture.root / name).read_bytes() == content
                        )
                        for name, content in before.items()
                    ),
                }
                if family in READ_FAMILIES or family in READBACK_FAMILIES:
                    checks["full_requested_content_read"] = _full_read(
                        fixture, calls, outputs, path, desired
                    )
                    if family in READBACK_FAMILIES:
                        result["filebytes_readback"] = bool(
                            executed and checks["full_requested_content_read"]
                        )
                elif family in WRITE_FAMILIES:
                    checks["requested_file_bytes"] = _bytes_match(fixture, path, desired)
                    checks["requested_write_executed"] = any(
                        item["name"] == "write_file" and item["arguments"]["path"] == path
                        for item in calls[: len(outputs)]
                    )
                    checks["write_uses_known_precondition"] = bool(write_known and all(write_known))
                elif family == "mkdir_after_select":
                    checks["requested_directory_exists"] = (fixture.root / path).is_dir()
                    checks["requested_directory_created"] = any(
                        item["name"] == "make_directory" and item["arguments"]["path"] == path
                        for item in calls
                    )
                elif family == "mkdir_initial_select":
                    active, selected = _active(fixture, task_catalog)
                    result["next_advertised_tools"] = [tool["function"]["name"] for tool in active]
                    checks["next_menu_has_exact_needed_tools"] = set(selected) == {
                        "make_directory",
                        "write_file",
                    }
                    checks["selection_executed"] = any(
                        item["name"] == "select_local_tools" for item in calls
                    )
                elif family in DONE_FAMILIES:
                    checks["stopped_without_another_tool"] = not calls
                    checks["response_is_completion_statement"] = _completion_statement(text)
                    result["terminal_continuation"] = bool(
                        executed
                        and checks["stopped_without_another_tool"]
                        and checks["response_is_completion_statement"]
                    )
                result.update(
                    execution_success=executed,
                    artifact_checks=checks,
                    step_success=bool(executed and all(checks.values())),
                )
            finally:
                fixture.close()
    except Exception as failure:
        result["error"] = f"{type(failure).__name__}: {failure}"
        if result["protocol_valid"] and supported and not result["executed_calls"]:
            result.update(known_precondition=False, step_success=None)
            result["fixture_error"] = result["error"]
    return result


def score_report(records, prediction_report, catalog):
    by_id = {row["id"]: row for row in records}
    if len(by_id) != len(records):
        raise ValueError("Frozen dataset contains duplicate record IDs")
    scored, seen = [], set()
    for sample in prediction_report["samples"]:
        if sample["id"] in seen:
            raise ValueError("Prediction report contains duplicate IDs")
        seen.add(sample["id"])
        if sample["id"] not in by_id:
            raise ValueError("Prediction ID is absent from the frozen dataset")
        failed = bool(sample.get("completion_process_timed_out")) or sample.get(
            "completion_process_returncode"
        ) not in {None, 0}
        result = score_record(by_id[sample["id"]], "" if failed else sample["raw_output"], catalog)
        if failed:
            result.update(
                prediction_generation_success=False,
                protocol_valid=False,
                strict_correct=False,
                execution_success=None,
                executed_calls=[],
            )
            if result["semantic_scoring_supported"]:
                result["step_success"] = False
            result["generation_error"] = (
                sample.get("error") or "Completion process failed or timed out"
            )
        result["frozen_evaluator_correct"] = sample.get("correct")
        scored.append(result)
    eligible = [row for row in scored if row["step_success"] is not None]
    family_results = {}
    for family in sorted({row["family"] for row in scored}):
        rows = [row for row in scored if row["family"] == family]
        family_results[family] = {
            "samples": len(rows),
            "step_scored": sum(row["step_success"] is not None for row in rows),
            "step_success": sum(row["step_success"] is True for row in rows),
        }
    return {
        "summary": {
            "samples": len(scored),
            "synthetic_continuation_scored_samples": len(eligible),
            "protocol_valid_count": sum(row["protocol_valid"] for row in scored),
            "exact_target_match_count": sum(row["strict_correct"] for row in scored),
            "known_precondition_count": sum(row["known_precondition"] is True for row in scored),
            "step_success_count": sum(row["step_success"] is True for row in scored),
            "filebytes_readback_eligible": sum(
                row["family"] in READBACK_FAMILIES for row in scored
            ),
            "filebytes_readback_count": sum(row["filebytes_readback"] is True for row in scored),
            "terminal_continuation_eligible": sum(row["family"] in DONE_FAMILIES for row in scored),
            "terminal_continuation_count": sum(
                row["terminal_continuation"] is True for row in scored
            ),
            "fixture_error_count": sum("fixture_error" in row for row in scored),
            "ordinary_preservation_audit_required": sum(
                row.get("preservation_audit_required", False) for row in scored
            ),
            "autonomous_task_success_rate": None,
            "family_counts": dict(Counter(row["family"] for row in scored)),
            "family_results": family_results,
        },
        "samples": scored,
        "prediction_control_only": prediction_report.get("oracle_control_only", False),
        "model_inference_performed": False,
        "expected_answers_given_to_model": False,
        "executor_scope": (
            "Real filesystem, CAS and local-tool selection "
            "in disposable synthetic single-step fixtures"
        ),
        "strict_text_criteria": (
            "Exact target response; frozen evaluator substring results are preserved separately"
        ),
        "limits": [
            "Stage continuation replay does not measure autonomous end-to-end task success "
            "or mainstream Android-agent performance.",
            "Known preconditions are restored synthetic history, "
            "not progress achieved by this prediction.",
            "Readback counts only a prediction that reads the complete correct file "
            "in a readback stage.",
            "Terminal continuations use a conservative completion-wording check "
            "after verified historical state.",
            "Ordinary arithmetic and conversation require the independent preservation audit.",
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
    raw = args.eval.read_bytes()
    records = [json.loads(line) for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
    if any(
        row.get("metadata", {}).get("data_source") != "procedural_synthetic_v3_candidate"
        for row in records
    ):
        parser.error("V3 replay requires the frozen V3 fixture dataset")
    predictions_raw, catalog_raw = args.predictions.read_bytes(), args.catalog.read_bytes()
    predictions, catalog = json.loads(predictions_raw), json.loads(catalog_raw)
    expected_hash = hashlib.sha256(raw).hexdigest()
    if predictions.get("eval_sha256") != expected_hash:
        parser.error("Prediction report must identify the same frozen evaluation SHA256")
    report = score_report(records, predictions, catalog)
    report["provenance"] = {
        "eval_sha256": expected_hash,
        "catalog_sha256": hashlib.sha256(catalog_raw).hexdigest(),
        "predictions_sha256": hashlib.sha256(predictions_raw).hexdigest(),
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture_builder_sha256": hashlib.sha256(
            Path(__file__).with_name("build_dataset_v2.py").read_bytes()
        ).hexdigest(),
        "runtime_menu_builder_sha256": hashlib.sha256(
            Path(__file__).with_name("build_dataset_v3.py").read_bytes()
        ).hexdigest(),
        "history_replay_helper_sha256": hashlib.sha256(
            Path(__file__).with_name("evaluate_replay_v2.py").read_bytes()
        ).hexdigest(),
        "prediction_input_builder_sha256": hashlib.sha256(
            Path(__file__).with_name("evaluate_tools.py").read_bytes()
        ).hexdigest(),
        "atomic_parser_sha256": hashlib.sha256(
            (ANDROID_ROOT / "android_adapter/local_provider.py").read_bytes()
        ).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(compact(report["summary"]), flush=True)


if __name__ == "__main__":
    main()
