from __future__ import annotations

# Chinese punctuation in fixtures is intentional.
# ruff: noqa: RUF001
import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

ANDROID_ROOT = Path(__file__).resolve().parents[2]
for source in (ANDROID_ROOT, ANDROID_ROOT.parent / "src"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))


def scorer():
    assert importlib.util.find_spec("training.evaluate_replay_v4") is not None, (
        "V4 semantic replay scorer is missing"
    )
    return importlib.import_module("training.evaluate_replay_v4")


def example(family):
    import asyncio

    from training.build_dataset_v4 import _assert_program_completion, _file_program, _row
    from training.runtime_fixture_v4 import capture_program, load_catalog

    source = load_catalog()
    program, metadata = _file_program("dev", 6000, 20261004, family, 72)
    capture = asyncio.run(capture_program(program, source["catalog"]))
    _assert_program_completion(program, capture)
    return _row("dev", 6000, family, program, metadata, capture, source["catalog"]), source[
        "catalog"
    ]


def test_scorer_runs_actual_tools_instead_of_legacy_substrings():
    row, catalog = example("copy_new_write")
    result = scorer().score_prediction(row, {"raw_output": row["target_response"]}, catalog)
    assert result["behavior_success"] is True
    assert result["known_precondition"] is True
    assert result["actual_prediction_executed"] is True
    assert result["autonomous_task_success"] is None
    wrong = row["target_response"].replace(
        "<parameter=expected_sha256>\nNone\n", "<parameter=expected_sha256>\n" + "a" * 64 + "\n"
    )
    result = scorer().score_prediction(row, {"raw_output": wrong}, catalog)
    assert result["protocol_valid"] is True
    assert result["behavior_success"] is False


def test_newline_loss_and_extra_tool_side_effects_fail_even_when_reply_claims_success():
    row, catalog = example("edit_append_write")
    wrong = row["target_response"].replace("<parameter=content>\n", "<parameter=content>\nBAD", 1)
    assert (
        scorer().score_prediction(row, {"raw_output": wrong}, catalog)["behavior_success"] is False
    )
    assert (
        scorer().score_prediction(row, {"raw_output": "已完成。"}, catalog)["behavior_success"]
        is False
    )


def test_terminal_continuation_requires_completed_history_and_no_new_call():
    row, catalog = example("mkdir_write_done")
    assert (
        scorer().score_prediction(row, {"raw_output": "文件已保存并核对。"}, catalog)[
            "behavior_success"
        ]
        is True
    )
    for answer in ("尚未保存。", "文件已保存吗？", "The file has not been saved."):
        assert (
            scorer().score_prediction(row, {"raw_output": answer}, catalog)["behavior_success"]
            is False
        )


def test_arithmetic_uses_explicit_final_answer_and_independent_visible_prompt():
    import asyncio

    from training.build_dataset_v4 import _ordinary_program, _row
    from training.runtime_fixture_v4 import capture_program, load_catalog

    source = load_catalog()
    program, metadata = _ordinary_program("dev", 7000, 20261004, 0)
    capture = asyncio.run(capture_program(program, source["catalog"]))
    row = _row(
        "dev", 7000, metadata["ordinary_group"], program, metadata, capture, source["catalog"]
    )
    answer = row["expected"]["answer"]
    right = scorer().score_prediction(
        row, {"raw_output": f"最终答案：{answer}。"}, source["catalog"]
    )
    assert right["ordinary_correct"] is True
    assert right["ordinary_semantics_supported"] is True
    wrong = scorer().score_prediction(
        row, {"raw_output": f"中间结果={answer}；最终答案：{answer}0。"}, source["catalog"]
    )
    assert wrong["ordinary_correct"] is False


def test_generation_failure_does_not_execute_tool_and_stays_in_denominator():
    row, catalog = example("copy_new_write")
    result = scorer().score_prediction(
        row, {"raw_output": row["target_response"], "timed_out": True}, catalog
    )
    assert result["prediction_generation_success"] is False
    assert result["actual_prediction_executed"] is False
    assert result["behavior_success"] is False


def test_scorer_fails_on_hidden_fixture_corruption_instead_of_blame_model():
    row, catalog = example("copy_existing_write")
    row["metadata"]["before_files"][row["metadata"]["target_path"]] += "corrupted"
    with pytest.raises(ValueError, match=r"precondition|fixture|state"):
        scorer().score_prediction(row, {"raw_output": row["target_response"]}, catalog)


@pytest.mark.parametrize("marker", ("<|im_end|>", "<|endoftext|>"))
def test_hf_end_marker_is_framing_without_changing_file_content(marker):
    row, catalog = example("copy_new_write")
    raw = row["target_response"] + marker
    result = scorer().score_prediction(row, {"raw_output": raw}, catalog)
    assert result["behavior_success"] is True
    assert result["raw_output"] == raw
    assert result["completion_text"] == row["target_response"]


def test_report_preserves_explicit_dev_split_and_rejects_mixed_inputs():
    row, catalog = example("copy_new_write")
    report = scorer().score_report(
        [row], [{"id": row["id"], "raw_output": row["target_response"]}], catalog
    )
    assert report["split"] == "dev"
    changed = {**row, "id": "other-split", "split": "eval"}
    with pytest.raises(ValueError, match="split"):
        scorer().score_report([row, changed], [], catalog)


def test_selector_name_order_and_extra_needed_legal_schema_do_not_fail_behavior():
    from training.build_dataset import render_call

    row, catalog = example("mkdir_write_select")
    raw = render_call(
        {
            "name": "select_local_tools",
            "arguments": {"names": ["read_file", "write_file", "make_directory", "list_files"]},
        }
    )
    assert scorer().score_prediction(row, {"raw_output": raw}, catalog)["behavior_success"] is True
