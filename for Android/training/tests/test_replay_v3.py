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
    assert importlib.util.find_spec("training.evaluate_replay_v3") is not None
    return importlib.import_module("training.evaluate_replay_v3")


@pytest.fixture(scope="module")
def data():
    from training.build_dataset_v3 import generate_dataset

    return generate_dataset(seed=5119, train_count=48, dev_count=48, eval_count=48)


def example(data, family):
    return next(row for row in data["eval"] if row["metadata"]["family"] == family)


def render(item):
    from training.build_dataset import render_call

    return render_call(item)


def score(data, family, calls):
    return evaluator().score_record(example(data, family), calls, data["catalog"])


def test_read_defaults_succeed_but_truncated_content_is_not_a_full_read(data):
    row = example(data, "copy_initial_read")
    target = copy.deepcopy(row["expected"]["calls"][0])
    target["arguments"].update(offset=0, max_bytes=262144)
    result = score(data, "copy_initial_read", render(target))
    assert result["strict_correct"] is False
    assert result["step_success"] is True
    assert result["known_precondition"] is True
    assert result["autonomous_task_success"] is None
    target["arguments"]["max_bytes"] = 1
    result = score(data, "copy_initial_read", render(target))
    assert result["execution_success"] is True
    assert result["step_success"] is False
    assert result["artifact_checks"]["full_requested_content_read"] is False


def test_copy_requires_null_precondition_and_exact_leading_and_trailing_bytes(data):
    row = example(data, "copy_observed_write")
    target = copy.deepcopy(row["expected"]["calls"][0])
    assert target["arguments"]["content"].startswith("\n")
    assert target["arguments"]["content"].endswith("\n\n")
    target["arguments"]["content"] = target["arguments"]["content"].strip()
    result = score(data, "copy_observed_write", render(target))
    assert result["execution_success"] is True
    assert result["step_success"] is False
    assert result["artifact_checks"]["requested_file_bytes"] is False
    target = copy.deepcopy(row["expected"]["calls"][0])
    target["arguments"]["expected_sha256"] = "a" * 64
    result = score(data, "copy_observed_write", render(target))
    assert result["execution_success"] is False
    assert result["artifact_checks"]["write_uses_known_precondition"] is False


@pytest.mark.parametrize("preimage", [None, "0" * 64])
def test_existing_edit_cannot_replace_the_observed_cas_with_null_or_guess(data, preimage):
    row = example(data, "edit_observed_write")
    target = copy.deepcopy(row["expected"]["calls"][0])
    assert len(target["arguments"]["expected_sha256"]) == 64
    target["arguments"]["expected_sha256"] = preimage
    result = score(data, "edit_observed_write", render(target))
    assert result["known_precondition"] is True
    assert result["execution_success"] is False
    assert result["step_success"] is False
    assert result["artifact_checks"]["write_uses_known_precondition"] is False


def test_a_file_written_in_history_is_not_counted_as_a_model_readback(data):
    result = score(data, "copy_read_back", "The file is probably ready.")
    assert result["known_precondition"] is True
    assert result["precondition_checks"]["requested_file_bytes_already_present"] is True
    assert result["filebytes_readback"] is False
    assert result["step_success"] is False
    row = example(data, "copy_read_back")
    target = copy.deepcopy(row["expected"]["calls"][0])
    target["arguments"].update(offset=0, max_bytes=262144)
    result = score(data, "copy_read_back", render(target))
    assert result["strict_correct"] is False
    assert result["filebytes_readback"] is True
    assert result["step_success"] is True
    assert result["autonomous_task_success"] is None


def test_selection_uses_the_real_next_menu_and_keeps_both_needed_tools(data):
    row = example(data, "mkdir_initial_select")
    target = copy.deepcopy(row["expected"]["calls"][0])
    target["arguments"]["names"].reverse()
    result = score(data, "mkdir_initial_select", render(target))
    assert result["strict_correct"] is False
    assert result["step_success"] is True
    assert set(result["next_advertised_tools"]) == {
        "make_directory",
        "write_file",
        "select_local_tools",
    }
    target["arguments"]["names"] = ["make_directory"]
    result = score(data, "mkdir_initial_select", render(target))
    assert result["execution_success"] is True
    assert result["step_success"] is False
    assert result["artifact_checks"]["next_menu_has_exact_needed_tools"] is False


def test_mkdir_checks_the_requested_path_and_nested_write_bytes(data):
    row = example(data, "mkdir_after_select")
    target = copy.deepcopy(row["expected"]["calls"][0])
    target["arguments"]["path"] = "archive/unrequested"
    result = score(data, "mkdir_after_select", render(target))
    assert result["execution_success"] is True
    assert result["step_success"] is False
    assert result["artifact_checks"]["no_unrequested_side_effects"] is False
    row = example(data, "mkdir_after_directory")
    result = score(data, "mkdir_after_directory", row["target_response"])
    assert result["known_precondition"] is True
    assert result["precondition_checks"]["parent_directory_already_exists"] is True
    assert result["artifact_checks"]["requested_file_bytes"] is True
    assert result["step_success"] is True
    assert result["autonomous_task_success"] is None


def test_verified_history_only_establishes_a_terminal_continuation(data):
    row = example(data, "copy_verified_done")
    result = score(data, "copy_verified_done", row["target_response"])
    assert result["known_precondition"] is True
    assert result["precondition_checks"]["historical_full_readback_verified"] is True
    assert result["terminal_continuation"] is True
    assert result["step_success"] is True
    assert result["filebytes_readback"] is None
    assert result["autonomous_task_success"] is None
    result = score(data, "copy_verified_done", f"{row['metadata']['entity']}还未完成。")
    assert result["terminal_continuation"] is False
    assert result["step_success"] is False
    path = next(iter(row["metadata"]["fixture_files"]))
    result = score(
        data, "copy_verified_done", render({"name": "read_file", "arguments": {"path": path}})
    )
    assert result["execution_success"] is True
    assert result["terminal_continuation"] is False
    assert result["step_success"] is False


@pytest.mark.parametrize(
    "response",
    [
        "I haven't completed the copy.",
        "The copy has never been completed.",
        "Has the copy been completed?",
        "Has the copy been completed",
        "The copy hasn\u2019t been completed.",
        "已经完成了吗\uff1f",
        "I will consider it completed later.",
    ],
)
def test_denial_question_or_future_claim_is_not_a_terminal_completion(data, response):
    result = score(data, "copy_verified_done", response)
    assert result["known_precondition"] is True
    assert result["terminal_continuation"] is False
    assert result["step_success"] is False


def test_extra_existing_file_modification_is_rejected_despite_correct_copy(data):
    row = example(data, "copy_observed_write")
    path, original = next(iter(row["metadata"]["fixture_files"].items()))
    import hashlib

    extra = {
        "name": "write_file",
        "arguments": {
            "path": path,
            "content": "unrequested edit",
            "expected_sha256": hashlib.sha256(original.encode()).hexdigest(),
        },
    }
    result = score(data, "copy_observed_write", row["target_response"] + "\n" + render(extra))
    assert result["execution_success"] is True
    assert result["artifact_checks"]["requested_file_bytes"] is True
    assert result["artifact_checks"]["other_files_unchanged"] is False
    assert result["step_success"] is False


def test_atomic_parse_failure_has_no_effect_and_ordinary_answers_need_separate_audit(data):
    row = example(data, "copy_observed_write")
    result = score(data, "copy_observed_write", row["target_response"].replace("</tool_call>", ""))
    assert result["protocol_valid"] is False
    assert result["executed_calls"] == []
    assert result["step_success"] is False
    row = example(data, "retention_math_0")
    value = row["expected"]["must_contain"][0]
    result = evaluator().score_record(row, f"结果是 {value}0。", data["catalog"])
    assert result["strict_correct"] is False
    assert result["semantic_scoring_supported"] is False
    assert result["step_success"] is None
    assert result["preservation_audit_required"] is True


def test_all_oracle_stage_continuations_replay_without_claiming_end_to_end(data):
    original = copy.deepcopy(data)
    for row in data["eval"]:
        if row["metadata"]["ordinary_retention"]:
            continue
        result = evaluator().score_record(row, row["target_response"], data["catalog"])
        assert result["strict_correct"] is True, (row["id"], result)
        assert result["known_precondition"] is True, (row["id"], result)
        assert result["step_success"] is True, (row["id"], result)
        assert result["autonomous_task_success"] is None
    assert data == original


def test_report_rejects_duplicate_ids_and_generation_failure_cannot_execute(data):
    row = example(data, "copy_observed_write")
    sample = {"id": row["id"], "raw_output": row["target_response"]}
    with pytest.raises(ValueError, match="duplicate"):
        evaluator().score_report(data["eval"], {"samples": [sample, sample]}, data["catalog"])
    failed = {**sample, "completion_process_timed_out": True}
    report = evaluator().score_report(data["eval"], {"samples": [failed]}, data["catalog"])
    result = report["samples"][0]
    assert result["prediction_generation_success"] is False
    assert result["step_success"] is False
    assert result["executed_calls"] == []
    assert report["summary"]["autonomous_task_success_rate"] is None


def test_invalid_fixture_is_separate_from_a_failed_model_continuation(data):
    row = copy.deepcopy(example(data, "copy_observed_write"))
    tool_result = next(message for message in row["messages"] if message["role"] == "tool")
    # Change a real recorded read result without touching the fixture source bytes.
    import json

    prefix, recorded = tool_result["content"].split("\n", 1)
    value = json.loads(recorded)
    value["content"] = "history result does not match the seeded source"
    tool_result["content"] = prefix + "\n" + json.dumps(value)
    result = evaluator().score_record(row, row["target_response"], data["catalog"])
    assert result["protocol_valid"] is True
    assert result["known_precondition"] is False
    assert result["step_success"] is None
    assert "fixture_error" in result
    assert result["executed_calls"] == []


def test_ordinary_audit_denominator_survives_protocol_and_generation_failures(data):
    row = example(data, "retention_math_0")
    sample = {"id": row["id"], "raw_output": "<tool_call>incomplete"}
    for prediction in (sample, {**sample, "completion_process_timed_out": True}):
        report = evaluator().score_report(data["eval"], {"samples": [prediction]}, data["catalog"])
        result = report["samples"][0]
        assert result["protocol_valid"] is False
        assert result["step_success"] is None
        assert result["preservation_audit_required"] is True
        assert report["summary"]["ordinary_preservation_audit_required"] == 1
