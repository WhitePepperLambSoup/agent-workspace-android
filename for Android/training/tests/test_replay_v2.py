from __future__ import annotations

import copy
import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

ANDROID_ROOT = Path(__file__).resolve().parents[2]
for source in (ANDROID_ROOT, ANDROID_ROOT.parent / "src"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))


def evaluator():
    assert importlib.util.find_spec("training.evaluate_replay_v2") is not None
    return importlib.import_module("training.evaluate_replay_v2")


@pytest.fixture(scope="module")
def data():
    from training.build_dataset_v2 import generate_dataset

    return generate_dataset(seed=5119, train_count=48, dev_count=48, eval_count=48)


def example(data, family):
    return next(row for row in data["eval"] if row["metadata"]["family"] == family)


def render(item):
    from training.build_dataset import render_call

    return render_call(item)


def test_real_todo_update_completed_is_semantic_success_without_strict_match(data):
    row = example(data, "todo_complete")
    target = copy.deepcopy(row["expected"]["calls"][0])
    target["arguments"].update(action="update", status="completed")
    result = evaluator().score_record(row, render(target), data["catalog"])
    assert result["protocol_valid"] is True
    assert result["strict_correct"] is False
    assert result["execution_success"] is True
    assert result["step_success"] is True
    assert result["task_finished"] is True


def test_read_defaults_and_reversed_read_order_are_allowed_semantically(data):
    row = example(data, "copy_verify")
    target = copy.deepcopy(row["expected"]["calls"][0])
    target["arguments"].update(offset=0, max_bytes=262144)
    result = evaluator().score_record(row, render(target), data["catalog"])
    assert result["strict_correct"] is False
    assert result["step_success"] is True
    pair = example(data, "two_reads")
    reversed_calls = "\n".join(render(item) for item in reversed(pair["expected"]["calls"]))
    result = evaluator().score_record(pair, reversed_calls, data["catalog"])
    assert result["strict_correct"] is False
    assert result["step_success"] is True


def test_correct_tool_execution_does_not_excuse_wrong_file_content(data):
    row = example(data, "copy_from_read")
    target = copy.deepcopy(row["expected"]["calls"][0])
    target["arguments"]["content"] = "this is a guess instead of the observed content"
    result = evaluator().score_record(row, render(target), data["catalog"])
    assert result["protocol_valid"] is True
    assert result["execution_success"] is True
    assert result["step_success"] is False
    assert result["artifact_checks"]["requested_file_bytes"] is False


def test_semantic_success_is_separate_from_finished_multistep_task(data):
    row = example(data, "mkdir_select")
    target = copy.deepcopy(row["expected"]["calls"][0])
    target["arguments"]["names"] = ["make_directory"]
    result = evaluator().score_record(row, render(target), data["catalog"])
    assert result["strict_correct"] is False
    assert result["step_success"] is True
    assert result["task_finished"] is False


def test_failure_and_calls_after_verified_done_cannot_claim_completion(data):
    row = example(data, "edit_cas")
    target = copy.deepcopy(row["expected"]["calls"][0])
    target["arguments"]["expected_sha256"] = None
    result = evaluator().score_record(row, render(target), data["catalog"])
    assert result["protocol_valid"] is True
    assert result["execution_success"] is False
    assert result["step_success"] is False
    done = example(data, "file_done")
    source = next(iter(done["metadata"]["fixture_files"]))
    result = evaluator().score_record(
        done, render({"name": "read_file", "arguments": {"path": source}}), data["catalog"]
    )
    assert result["protocol_valid"] is True
    assert result["execution_success"] is True
    assert result["step_success"] is False
    assert result["task_finished"] is False


def test_invalid_protocol_has_no_effect_and_android_semantics_remain_unscored(data):
    row = example(data, "copy_from_read")
    result = evaluator().score_record(
        row, row["target_response"].replace("</tool_call>", ""), data["catalog"]
    )
    assert result["protocol_valid"] is False
    assert result["executed_calls"] == []
    android = example(data, "android_type")
    result = evaluator().score_record(android, android["target_response"], data["catalog"])
    assert result["protocol_valid"] is True
    assert result["strict_correct"] is True
    assert result["semantic_scoring_supported"] is False
    assert result["execution_success"] is None
    assert result["step_success"] is None


def test_replay_scores_all_frozen_file_targets_without_mutating_records(data):
    frozen = copy.deepcopy(data)
    for row in data["eval"]:
        if row["metadata"]["ordinary_retention"] or row["metadata"]["family"].startswith(
            "android_"
        ):
            continue
        result = evaluator().score_record(row, row["target_response"], data["catalog"])
        assert result["strict_correct"] is True, row["id"]
        assert result["step_success"] is True, (row["id"], result)
    assert data == frozen
