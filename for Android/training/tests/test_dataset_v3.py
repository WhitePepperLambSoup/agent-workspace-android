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


def builder():
    assert importlib.util.find_spec("training.build_dataset_v3") is not None
    return importlib.import_module("training.build_dataset_v3")


@pytest.fixture(scope="module")
def data():
    return builder().generate_dataset(train_count=80, dev_count=48, eval_count=48)


def test_natural_initial_copy_and_edit_require_read_before_writing(data):
    for split in ("train", "dev", "eval"):
        for family in ("copy_initial_read", "edit_initial_read"):
            rows = [row for row in data[split] if row["metadata"]["family"] == family]
            assert rows
            for row in rows:
                assert not any(message["role"] == "tool" for message in row["messages"])
                assert row["expected"]["calls"][0]["name"] == "read_file"
                assert "read_file" not in row["messages"][1]["content"]
                assert {tool["function"]["name"] for tool in row["tools"]} == {
                    "list_files",
                    "read_file",
                    "write_file",
                    "select_local_tools",
                }


def test_every_advertised_menu_is_exactly_runtime_selected_plus_selector(data):
    for split in ("train", "dev", "eval"):
        for row in data[split]:
            metadata = row["metadata"]
            assert {tool["function"]["name"] for tool in row["tools"]} == {
                *metadata["runtime_selected_tools"],
                "select_local_tools",
            }
            assert metadata["advertisement_scope"] == "actual_file_task_profile"
            if row["metadata"]["family"] == "copy_selected_read":
                assert metadata["runtime_selected_tools"] == ["read_file", "write_file"]
            if row["metadata"]["family"].startswith("mkdir_after_"):
                assert metadata["runtime_selected_tools"] == ["make_directory", "write_file"]


def test_split_isolation_and_actual_atomic_parser_acceptance(data):
    from android_adapter.local_provider import parse_qwen_output
    from training.evaluate_tools import build_evaluation_prompt

    from agent_workspace.core.models import DeltaKind

    builder().validate_dataset(data)
    for split in ("train", "dev", "eval"):
        for row in data[split]:
            request, prompt = build_evaluation_prompt(row)
            assert row["metadata"]["user_data_used"] is False
            assert (
                row["metadata"]["ordinary_retention"] or row["metadata"]["runtime_history_replayed"]
            )
            assert "鹈鹕" not in prompt + row["target_response"]
            modified = copy.deepcopy(row)
            modified["expected"] = {"sentinel": "hidden_scoring_label"}
            modified["target_response"] = "hidden_target_answer"
            modified["metadata"] = {"sentinel": "hidden_metadata"}
            assert build_evaluation_prompt(modified)[1] == prompt
            deltas = parse_qwen_output(row["target_response"], request, row["id"])
            calls = [
                {"name": delta.tool_call.name, "arguments": delta.tool_call.arguments}
                for delta in deltas
                if delta.kind is DeltaKind.TOOL_CALL
            ]
            assert calls == row["expected"].get("calls", [])


def test_deterministic_candidate_preserves_copy_boundaries_and_cas(data):
    module = builder()
    first = module.generate_dataset(seed=10991, train_count=48, dev_count=48, eval_count=48)
    assert first == module.generate_dataset(seed=10991, train_count=48, dev_count=48, eval_count=48)
    for row in first["train"]:
        if row["metadata"]["family"] == "copy_observed_write":
            content = row["expected"]["calls"][0]["arguments"]["content"]
            assert content.startswith("\n") and content.endswith("\n\n")
            assert row["expected"]["calls"][0]["arguments"]["expected_sha256"] is None
        elif row["metadata"]["family"] == "edit_observed_write":
            assert len(row["expected"]["calls"][0]["arguments"]["expected_sha256"]) == 64


def test_finished_records_independently_replay_real_histories_targets_and_menus(data):
    for split in ("train", "dev", "eval"):
        for row in data[split]:
            replay = builder().audit_replay(row, data["catalog"])
            assert replay["runtime_menu_exact"] is True
            assert replay["actual_targets_executed"] is True
