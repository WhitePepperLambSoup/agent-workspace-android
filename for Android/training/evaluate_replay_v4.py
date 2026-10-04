"""Execute only each V4 prediction; ordinary answers use visible-task computation."""

# Chinese punctuation in arithmetic answers is intentional.
# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ANDROID_ROOT = Path(__file__).resolve().parents[1]
for source in (ANDROID_ROOT, ANDROID_ROOT.parent / "src"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from android_adapter.local_provider import parse_qwen_output  # noqa: E402

from agent_workspace.core.models import DeltaKind  # noqa: E402
from training.build_dataset_v4 import (  # noqa: E402
    independent_arithmetic_answer,
    independent_language_answer,
)
from training.evaluate_replay_v3 import _completion_statement  # noqa: E402
from training.evaluate_tools import build_evaluation_prompt  # noqa: E402
from training.runtime_fixture_v4 import capture_program, digest  # noqa: E402


def generation_success(prediction):
    return not (
        prediction.get("prediction_generation_success") is False
        or prediction.get("generation_error")
        or prediction.get("error")
        or prediction.get("timed_out")
        or prediction.get("output_truncated")
        or prediction.get("output_limit_reached")
        or prediction.get("finish_reason") in {"length", "cancelled"}
        or (prediction.get("returncode") is not None and prediction["returncode"] != 0)
    )


def _terminal_statement(text):
    # Expand completion vocabulary while keeping V3's conservative negation,
    # question and future-tense rejection unchanged.
    normalized = re.sub(r"(已(?:经)?)(?:创建|保存|核对)", r"\1完成", text)
    normalized = re.sub(r"\b(?:created|saved)\b", "completed", normalized, flags=re.IGNORECASE)
    return _completion_statement(normalized)


def _final_integer(text):
    if re.search(r"不确定|无法|不是|未完成|\b(?:not|cannot|unknown)\b", text, re.IGNORECASE):
        return None
    pattern = r"([+-]?\d+)(?:\s*(件|枚|个))?\s*[。.!]?\s*$"
    labelled = re.search(
        r"(?:最终答案|答案|结果|final answer|answer)\s*[:：=]?\s*" + pattern, text, re.IGNORECASE
    )
    if labelled is None:
        labelled = re.fullmatch(r"\s*" + pattern, text)
    if labelled is None:
        labelled = re.search(r"=\s*" + pattern, text)
    return (int(labelled[1]), labelled[2]) if labelled is not None else None


def _ordinary_correct(row, text):
    group = row["metadata"]["ordinary_group"]
    if group.startswith("arithmetic_"):
        answer = _final_integer(text)
        if answer is None or answer[0] != independent_arithmetic_answer(row):
            return False
        if group == "arithmetic_units" and answer[1] is not None:
            prompt = next(
                message["content"] for message in row["messages"] if message["role"] == "user"
            )
            unit = re.search(r"\d+\s*(件|枚|个)", prompt)
            return unit is not None and answer[1] == unit[1]
        return True
    expected = independent_language_answer(row)
    if group == "language_extract":
        return text.strip() == expected
    try:
        return json.loads(text) == json.loads(expected)
    except (ValueError, TypeError):
        return False


def _equivalent_calls(actual, expected, kind):
    if len(actual) != len(expected):
        return False
    for received, wanted in zip(actual, expected, strict=True):
        if received["name"] != wanted["name"]:
            return False
        if kind == "select":
            if not set(wanted["arguments"]["names"]) <= set(received["arguments"].get("names", [])):
                return False
        elif kind in {"read", "readback", "missing_read", "directory_readback"}:
            args = received["arguments"]
            if (
                args.get("path", ".") != wanted["arguments"].get("path", ".")
                or args.get("offset", 0) != 0
            ):
                return False
        elif received["arguments"] != wanted["arguments"]:
            return False
    return True


def score_prediction(row, prediction, catalog):
    metadata = row["metadata"]
    ordinary = bool(metadata["ordinary_retention"])
    raw = prediction.get("raw_output", "")
    completion = re.sub(
        r"(?:<\|im_end\|>|<\|endoftext\|>)(?:\s*(?:<\|im_end\|>|<\|endoftext\|>))*\s*$",
        "",
        raw,
    )
    result = {
        "id": row["id"],
        "split": row["split"],
        "family": metadata["family"],
        "group": metadata.get("ordinary_group", metadata["stage_kind"]),
        "ordinary_retention": ordinary,
        "ordinary_semantics_supported": ordinary,
        "protocol_valid": False,
        "prediction_generation_success": generation_success(prediction),
        "behavior_success": False,
        "ordinary_correct": False if ordinary else None,
        "known_precondition": None,
        "actual_prediction_executed": False,
        "autonomous_task_success": None,
        "visible_prompt_sha256": digest(build_evaluation_prompt(row)[1]),
        "raw_output": raw,
        "completion_text": completion,
        "ordinary_scoring_scope": (
            "Visible arithmetic final answer or literal field extraction/string sorting; "
            "not general conversation"
        )
        if ordinary
        else None,
    }
    if not result["prediction_generation_success"]:
        return result
    request, _ = build_evaluation_prompt(row)
    try:
        deltas = parse_qwen_output(completion, request, row["id"])
    except Exception as error:
        result["protocol_error"] = f"{type(error).__name__}: {error}"
        return result
    calls = [
        {"name": delta.tool_call.name, "arguments": delta.tool_call.arguments}
        for delta in deltas
        if delta.kind is DeltaKind.TOOL_CALL
    ]
    text = "".join(delta.text for delta in deltas if delta.kind is DeltaKind.TEXT)
    result["protocol_valid"] = bool(calls or text.strip())
    result["calls"], result["text"] = calls, text
    if not result["protocol_valid"]:
        return result
    if ordinary:
        result["ordinary_correct"] = not calls and _ordinary_correct(row, text)
        result["behavior_success"] = result["ordinary_correct"]
        return result
    # The program prefix is executed through the same real runner. It supplies
    # known state, and never earns credit as a prediction or autonomous progress.
    captured = asyncio.run(
        capture_program(
            metadata["program"], catalog, prediction=completion, stop_at=metadata["target_step"]
        )
    )
    if len(captured["records"]) <= metadata["target_step"]:
        raise ValueError(
            f"Synthetic fixture failed before its known precondition: {captured['error']}"
        )
    state = captured["records"][metadata["target_step"]]
    if (
        state["messages"] != row["messages"]
        or state["tools"] != row["tools"]
        or state["before_files"] != metadata["before_files"]
        or state["before_directories"] != metadata["before_directories"]
    ):
        raise ValueError("Synthetic replay precondition or recorded fixture state changed")
    result["known_precondition"] = True
    result["actual_prediction_executed"] = True
    kind = metadata["stage_kind"]
    correct_calls = _equivalent_calls(calls, row["expected"].get("calls", []), kind)
    correct_state = (
        state["after_files"] == metadata["after_files"]
        and state["after_directories"] == metadata["after_directories"]
    )
    prefix_calls = sum(
        len(step.get("calls", []))
        for step in metadata["program"]["steps"][: metadata["target_step"]]
    )
    current_events = captured["tool_events"][prefix_calls:]
    result["executed_events"] = current_events
    succeeded = captured["error"] is None and len(current_events) == len(calls)
    if kind == "missing_read":
        succeeded = (
            succeeded
            and len(current_events) == 1
            and current_events[0]["type"] == "tool.failed"
            and "file does not exist" in (current_events[0]["error"] or "")
        )
    else:
        succeeded = succeeded and all(event["type"] == "tool.settled" for event in current_events)
    if kind in {"read", "readback"} and succeeded:
        for event, call in zip(current_events, calls, strict=True):
            output = json.loads(event["result"])
            path = call["arguments"]["path"]
            succeeded = (
                succeeded
                and output.get("truncated") is False
                and output.get("offset") == 0
                and output.get("content") == metadata["before_files"].get(path)
            )
    if kind == "directory_readback" and succeeded:
        output = json.loads(current_events[0]["result"])
        succeeded = output.get("truncated") is False and output.get("entries") == []
    if kind == "terminal":
        succeeded = (
            succeeded
            and not calls
            and _terminal_statement(text)
            and metadata["before_files"] == metadata["program"]["goal_files"]
        )
    result["behavior_success"] = bool(correct_calls and correct_state and succeeded)
    result["execution_success"] = bool(succeeded)
    result["artifact_state_matches"] = correct_state
    result["filebytes_readback"] = bool(result["behavior_success"] and kind == "readback")
    result["terminal_continuation"] = bool(result["behavior_success"] and kind == "terminal")
    return result


def score_report(rows, predictions, catalog):
    splits = {row["split"] for row in rows}
    if len(splits) != 1 or not splits <= {"train", "dev", "eval"}:
        raise ValueError("Replay requires one explicit dataset split")
    if any(row["metadata"]["split"] != row["split"] for row in rows):
        raise ValueError("Row split differs from its metadata split")
    samples = predictions["samples"] if isinstance(predictions, dict) else predictions
    by_id = {}
    for prediction in samples:
        if prediction["id"] in by_id:
            raise ValueError("Duplicate V4 prediction ID")
        by_id[prediction["id"]] = prediction
    if len({row["id"] for row in rows}) != len(rows) or set(by_id) != {row["id"] for row in rows}:
        raise ValueError("V4 prediction IDs must exactly match every supplied input")
    scored = []
    for row in rows:
        try:
            scored.append(score_prediction(row, by_id[row["id"]], catalog))
        except ValueError as error:
            raise ValueError(f"{row['id']}: independent fixture error: {error}") from error
    families = Counter(row["family"] for row in scored)
    return {
        "split": next(iter(splits)),
        "samples": scored,
        "summary": {
            "samples": len(scored),
            "protocol_valid_count": sum(row["protocol_valid"] for row in scored),
            "behavior_success_count": sum(row["behavior_success"] for row in scored),
            "tool_step_success_count": sum(
                row["behavior_success"] for row in scored if not row["ordinary_retention"]
            ),
            "tool_step_total": sum(not row["ordinary_retention"] for row in scored),
            "ordinary_correct_count": sum(bool(row["ordinary_correct"]) for row in scored),
            "ordinary_total": sum(row["ordinary_retention"] for row in scored),
            "family_counts": dict(families),
            "autonomous_task_success_rate": None,
            "all_failed_generation_samples_remain_in_denominator": True,
        },
        "scope": (
            "Single current prediction from restored synthetic state; "
            "ordinary arithmetic and deterministic language tasks only"
        ),
        "model_inference_performed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a fresh report output to preserve evidence")
    rows = [json.loads(line) for line in args.eval.read_text(encoding="utf-8").splitlines()]
    predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
    eval_hash = hashlib.sha256(args.eval.read_bytes()).hexdigest()
    if predictions.get("eval_sha256") is not None and predictions["eval_sha256"] != eval_hash:
        parser.error("Prediction report does not belong to the supplied dataset")
    report = score_report(rows, predictions, json.loads(args.catalog.read_text(encoding="utf-8")))
    report["provenance"] = {
        "eval_sha256": eval_hash,
        "predictions_sha256": hashlib.sha256(args.predictions.read_bytes()).hexdigest(),
        "catalog_sha256": hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
        "scorer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
