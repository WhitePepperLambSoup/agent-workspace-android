from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ANDROID_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ANDROID_ROOT), str(ANDROID_ROOT.parent / "src")]


def captured_row(family="generation_json_write"):
    from training.build_dataset_v5 import assert_program_completion, build_program, make_row
    from training.runtime_fixture_v5 import capture_program, load_catalog

    catalog = load_catalog()["catalog"]
    program, extra = build_program("dev", 600, 20261001, family, 0)
    captured = asyncio.run(capture_program(program, catalog))
    assert_program_completion(program, captured)
    return make_row("dev", 600, family, program, extra, captured), catalog


def test_v5_scorer_exists():
    assert importlib.util.find_spec("training.evaluate_replay_v5") is not None


def test_stage_executes_alternative_valid_json_and_rejects_wrong_data_and_side_effects():
    from training.build_dataset import render_call
    from training.evaluate_replay_v5 import score_prediction

    row, catalog = captured_row()
    call = copy.deepcopy(row["expected"]["calls"][0])
    call["arguments"]["content"] = json.dumps(
        json.loads(call["arguments"]["content"]), ensure_ascii=True, separators=(",", ":")
    )
    raw = render_call(call)
    result = score_prediction(row, {"raw_output": raw, "output_truncated": False}, catalog)
    assert result["behavior_success"] and result["actual_prediction_executed"]
    assert result["artifact_semantics"][row["metadata"]["target_path"]]["valid"]
    assert result["scripted_prefix_counted_as_model_progress"] is False
    call["arguments"]["content"] = "{}"
    result = score_prediction(row, {"raw_output": render_call(call)}, catalog)
    assert not result["behavior_success"]
    call["arguments"]["path"] = "notes/unrequested.json"
    assert not score_prediction(row, {"raw_output": render_call(call)}, catalog)["behavior_success"]


@pytest.mark.parametrize("status", ["output_truncated", "timed_out"])
def test_failed_generation_stays_in_denominator_and_never_executes(status):
    from training.evaluate_replay_v5 import score_report

    row, catalog = captured_row("copy_new_write")
    report = score_report(
        [row], [{"id": row["id"], "raw_output": row["target_response"], status: True}], catalog
    )
    assert len(report["samples"]) == 1
    assert not report["samples"][0]["behavior_success"]
    assert not report["samples"][0]["actual_prediction_executed"]


def test_stage_event_slicing_handles_proposed_and_settled_without_double_counting():
    from training.evaluate_replay_v5 import score_prediction

    row, catalog = captured_row("cas_recover_write")
    result = score_prediction(row, {"raw_output": row["target_response"]}, catalog)
    assert result["behavior_success"], result
    assert len(result["executed_events"]) == 1
    assert result["executed_events"][0]["type"] == "tool.settled"


def test_fetch_stage_wrong_search_function_executes_and_stays_a_failed_sample():
    from training.build_dataset import render_call
    from training.evaluate_replay_v5 import score_report

    row, catalog = captured_row("search_fetch")
    query = next(iter(row["metadata"]["program"]["http_fixture"]["queries"]))
    raw = render_call({"name": "web_search", "arguments": {"query": query}})
    report = score_report([row], [{"id": row["id"], "raw_output": raw}], catalog)
    assert report["summary"]["samples"] == report["summary"]["tool_step_total"] == 1
    result = report["samples"][0]
    assert result["actual_prediction_executed"] and result["execution_success"]
    assert result["executed_events"][0]["type"] == "tool.settled"
    assert not result["behavior_success"]


@pytest.mark.parametrize("family", ["copy_new_read", "copy_new_readback"])
def test_read_stage_wrong_selector_result_is_not_parsed_as_file_contents(family):
    from training.build_dataset import render_call
    from training.evaluate_replay_v5 import score_report

    row, catalog = captured_row(family)
    raw = render_call({"name": "select_local_tools", "arguments": {"names": ["read_file"]}})
    report = score_report([row], [{"id": row["id"], "raw_output": raw}], catalog)
    assert report["summary"]["samples"] == report["summary"]["tool_step_total"] == 1
    result = report["samples"][0]
    assert result["actual_prediction_executed"] and result["execution_success"]
    assert result["executed_events"][0]["type"] == "tool.settled"
    assert not result["behavior_success"]


@pytest.mark.parametrize(
    "family",
    ["copy_new_read", "copy_new_readback", "mkdir_only_list", "search_query", "search_fetch"],
)
def test_nonterminal_empty_calls_stay_in_complete_scoring_denominator(family):
    from training.evaluate_replay_v5 import score_report

    row, catalog = captured_row(family)
    raw = "Completed and verified everything."
    report = score_report([row], [{"id": row["id"], "raw_output": raw}], catalog)
    assert report["summary"]["samples"] == report["summary"]["tool_step_total"] == 1
    result = report["samples"][0]
    assert result["actual_prediction_executed"] and result["calls"] == []
    assert result["executed_events"] == [] and not result["behavior_success"]


def test_fetch_unknown_document_url_is_executed_and_failed_without_crashing():
    from training.build_dataset import render_call
    from training.evaluate_replay_v5 import score_report

    row, catalog = captured_row("search_fetch")
    url = row["expected"]["calls"][0]["arguments"]["url"] + "?unrequested=1"
    raw = render_call({"name": "web_fetch", "arguments": {"url": url}})
    report = score_report([row], [{"id": row["id"], "raw_output": raw}], catalog)
    assert report["summary"]["samples"] == report["summary"]["tool_step_total"] == 1
    result = report["samples"][0]
    assert result["actual_prediction_executed"]
    assert result["executed_events"][0]["type"] == "tool.settled"
    assert not result["behavior_success"]


def test_ordinary_answer_is_derived_only_from_visible_input():
    from training.evaluate_replay_v5 import score_prediction

    row, catalog = captured_row("arithmetic_add")
    row["metadata"]["answer"] = -999
    row["expected"]["answer"] = -999
    assert score_prediction(row, {"raw_output": row["target_response"]}, catalog)[
        "ordinary_correct"
    ]
    assert not score_prediction(row, {"raw_output": "-999"}, catalog)["ordinary_correct"]


def test_initial_workflow_callback_gets_only_visible_state_and_failure_is_complete():
    from training.build_dataset_v5 import build_workflows
    from training.evaluate_replay_v5 import evaluate_workflow_report
    from training.runtime_fixture_v5 import load_catalog

    cases = build_workflows("final", 20261001)[:1]
    called, completed = [], []

    async def generate_visible(prompt, identifier):
        assert isinstance(prompt, str) and isinstance(identifier, str)
        assert "goal_files" not in prompt and "gold_history" not in prompt
        called.append(prompt)
        return {"raw_output": "I have completed everything.", "output_truncated": False}

    report = asyncio.run(
        evaluate_workflow_report(
            cases,
            load_catalog()["catalog"],
            generate_visible,
            generation_config={"max_turns": 16},
            model_identity={"generation_source": "model_free_generation"},
            on_prediction=lambda result: completed.append(copy.deepcopy(result)),
        )
    )
    assert report["split"] == "final" and len(report["samples"]) == 1
    assert len(called) == 1 and completed == report["samples"]
    sample = report["samples"][0]
    assert not sample["behavior_success"] and sample["prediction_generation_success"]
    assert sample["autonomous_success"] is False
    assert len(sample["initial_visible_prompt_sha256"]) == 64


def test_workflow_from_zero_uses_model_raw_calls_readback_and_observed_cas():
    from training.build_dataset import render_call
    from training.build_dataset_v5 import build_workflows
    from training.evaluate_replay_v5 import evaluate_workflow_report
    from training.runtime_fixture_v5 import load_catalog

    case = build_workflows("dev", 20261001)[0]
    source = next(path for path in case["initial_files"] if path != "notes/preserve.txt")
    target = next(path for path in case["goal_files"] if path not in case["initial_files"])
    raw_turns = [
        render_call({"name": "read_file", "arguments": {"path": source}}),
        render_call(
            {
                "name": "write_file",
                "arguments": {
                    "path": target,
                    "content": case["initial_files"][source],
                    "expected_sha256": None,
                },
            }
        ),
        render_call({"name": "read_file", "arguments": {"path": target}}),
        "Completed and verified the copy.",
    ]
    seen = []

    def generate_visible(prompt, identifier):
        seen.append((prompt, identifier))
        return {"raw_output": raw_turns[len(seen) - 1], "output_truncated": False}

    report = asyncio.run(
        evaluate_workflow_report(
            [case],
            load_catalog()["catalog"],
            generate_visible,
            generation_config={"max_turns": 16},
            model_identity={"generation_source": "synthetic_integration_control"},
        )
    )
    sample = report["samples"][0]
    assert sample["behavior_success"] and sample["autonomous_success"] is None
    assert sample["model_performance_claim"] is False
    assert len(sample["turns"]) == 4 and len(seen) == 4
    assert [turn["generation"]["raw_output"] for turn in sample["turns"]] == raw_turns
    assert sample["filebytes_readback"] and sample["writes_use_observed_cas"]


@pytest.mark.parametrize("rewrite_after_readback", [False, True])
def test_correct_final_bytes_without_last_write_readback_are_failed(rewrite_after_readback):
    from training.build_dataset import render_call
    from training.build_dataset_v5 import build_workflows
    from training.evaluate_replay_v5 import evaluate_workflow_report
    from training.runtime_fixture_v5 import digest, load_catalog

    case = build_workflows("dev", 20261001)[0]
    source = next(path for path in case["initial_files"] if path != "notes/preserve.txt")
    target = next(path for path in case["goal_files"] if path not in case["initial_files"])
    content = case["initial_files"][source]
    calls = [
        {"name": "read_file", "arguments": {"path": source}},
        {
            "name": "write_file",
            "arguments": {"path": target, "content": content, "expected_sha256": None},
        },
    ]
    if rewrite_after_readback:
        calls += [
            {"name": "read_file", "arguments": {"path": target}},
            {
                "name": "write_file",
                "arguments": {
                    "path": target,
                    "content": content,
                    "expected_sha256": digest(content),
                },
            },
        ]
    raws = [render_call(call) for call in calls] + ["Completed and verified the copy."]
    generated = iter(raws)
    report = asyncio.run(
        evaluate_workflow_report(
            [case],
            load_catalog()["catalog"],
            lambda _prompt, _id: {"raw_output": next(generated), "output_truncated": False},
            generation_config={"max_turns": 16},
            model_identity={"generation_source": "synthetic_integration_control"},
        )
    )
    result = report["samples"][0]
    assert result["artifact_goal_matches"] and result["turn_completed"]
    assert result["writes_use_observed_cas"]
    assert not result["filebytes_readback"] and not result["behavior_success"]


def test_multiple_artifact_workflow_requires_every_output_and_readback():
    from training.build_dataset_v5 import build_workflows

    case = build_workflows("dev", 20261001)[9]
    added = set(case["goal_files"]) - set(case["initial_files"])
    assert len(added) == 2
    assert all(path in case["prompt"] for path in added)
