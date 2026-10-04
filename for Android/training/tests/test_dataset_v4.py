from __future__ import annotations

import copy
import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.timeout(600)

ANDROID_ROOT = Path(__file__).resolve().parents[2]
for source in (ANDROID_ROOT, ANDROID_ROOT.parent / "src"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))


def builder():
    assert importlib.util.find_spec("training.build_dataset_v4") is not None, (
        "V4 independent live-program builder is missing"
    )
    return importlib.import_module("training.build_dataset_v4")


@pytest.fixture(scope="module")
def data():
    return builder().generate_dataset(seed=20261005, train_count=120, dev_count=120, eval_count=120)


def test_builder_is_independent_and_uses_actual_runtime_capture():
    module = builder()
    assert module.SYSTEM_SOURCE == "actual_agent_runner_provider_request"
    assert len(module.FAMILIES) == 36


def test_complete_runtime_system_suffix_menu_and_prompt_capture(data):
    from mobile_runtime_controller import _ANDROID_SYSTEM_SUFFIX
    from training.evaluate_tools import build_evaluation_prompt

    for split in ("train", "dev", "eval"):
        for row in data[split]:
            system = row["messages"][0]["content"]
            if row["metadata"]["runtime_mode"] == "coding":
                assert _ANDROID_SYSTEM_SUFFIX in system
            else:
                assert _ANDROID_SYSTEM_SUFFIX not in system
            assert (
                system
                == data["live_system_source"]["entries"][row["metadata"]["runtime_mode"]][
                    "live_system_suffix"
                ]
            )
            assert "Complete the user's request" in system
            assert "Use the observed SHA-256" not in system
            metadata = row["metadata"]
            assert len(metadata["runtime_available_tools"]) > 20
            assert metadata["allowed_tools_override"] is None
            assert (
                "Available tools for this task: " + ", ".join(metadata["runtime_available_tools"])
                in system
            )
            assert {tool["function"]["name"] for tool in row["tools"]} == {
                *metadata["runtime_selected_tools"],
                "select_local_tools",
            }
            assert metadata["live_prompt_byte_equal"] is True
            assert (
                builder().digest(build_evaluation_prompt(row)[1])
                == metadata["captured_runtime_prompt_sha256"]
            )


def test_every_split_covers_all_operations_text_shapes_and_preservation(data):
    for split in ("train", "dev", "eval"):
        rows = data[split]
        ordinary = [row for row in rows if row["metadata"]["ordinary_retention"]]
        assert len(ordinary) * 5 == len(rows) * 2
        assert {
            row["metadata"]["family"] for row in rows if not row["metadata"]["ordinary_retention"]
        } == set(builder().FAMILIES)
        assert {
            row["metadata"]["edit_operation"]
            for row in rows
            if row["metadata"].get("edit_operation")
        } == {"replace", "append", "remove"}
        assert {
            row["metadata"]["content_shape"] for row in rows if row["metadata"].get("content_shape")
        } == set(builder().CONTENT_SHAPES)
        assert {row["metadata"]["runtime_mode"] for row in rows} == {"coding", "task"}
        assert {row["metadata"]["ordinary_group"] for row in ordinary} == set(
            builder().ORDINARY_GROUPS
        )
        for row in ordinary:
            assert len(row["tools"]) >= 4
            if row["metadata"]["ordinary_group"].startswith("arithmetic_"):
                assert "=" in row["target_response"]
                assert "最终答案" in row["target_response"]
                assert builder().independent_arithmetic_answer(row) == row["expected"]["answer"]


def test_existing_destination_uses_its_observed_hash_new_destination_uses_null(data):
    for row in data["train"]:
        family = row["metadata"]["family"]
        if family not in {
            "copy_new_write",
            "copy_existing_write",
            "cas_recover_write",
            "missing_recover_write",
        }:
            continue
        write = row["expected"]["calls"][0]
        args = write["arguments"]
        if family in {"copy_new_write", "missing_recover_write"}:
            assert args["expected_sha256"] is None
        else:
            reads = builder().historical_read_results(row)
            assert args["expected_sha256"] == reads[args["path"]]["sha256"]
            assert args["expected_sha256"] != reads[row["metadata"]["source_path"]]["sha256"]


def test_recovery_histories_have_real_error_messages_and_valid_continuations(data):
    for family in (
        "cas_recover_read",
        "cas_recover_write",
        "missing_recover_read",
        "missing_recover_write",
    ):
        row = next(row for row in data["train"] if row["metadata"]["family"] == family)
        failures = [
            message["content"]
            for message in row["messages"]
            if message["role"] == "tool" and "Tool failed (" in message["content"]
        ]
        assert failures and any("ConcurrentModificationError" in failure for failure in failures)
        if family == "missing_recover_write":
            assert any("file does not exist" in failure for failure in failures)
        assert builder().audit_replay(row, data["catalog"])["actual_targets_executed"] is True


def test_labels_and_hidden_loss_fields_never_enter_inputs(data):
    from training.evaluate_tools import build_evaluation_prompt

    for row in data["train"]:
        before = build_evaluation_prompt(row)[1]
        modified = copy.deepcopy(row)
        modified["expected"] = {"hidden_canary": "V4_LABEL_CANARY"}
        modified["target_response"] = "V4_TARGET_CANARY"
        modified["metadata"] = {"loss_spans": [{"expected_text": "V4_METADATA_CANARY"}]}
        assert build_evaluation_prompt(modified)[1] == before
        assert "V4_LABEL_CANARY" not in before
        for span in row["metadata"].get("loss_spans", []):
            assert row["target_response"][span["start"] : span["end"]] == span["expected_text"]


def test_split_entities_templates_and_numbers_are_independent(data):
    assert builder().validate_dataset(data)["split_isolation"] is True
    for first, second in (("train", "dev"), ("train", "eval"), ("dev", "eval")):
        for key in ("entity", "request_template"):
            assert {row["metadata"][key] for row in data[first]}.isdisjoint(
                {row["metadata"][key] for row in data[second]}
            )
        first_values = {
            value for row in data[first] for value in row["metadata"].get("generated_numbers", [])
        }
        second_values = {
            value for row in data[second] for value in row["metadata"].get("generated_numbers", [])
        }
        assert first_values.isdisjoint(second_values)


def test_replay_detects_target_content_or_hidden_state_corruption(data):
    row = next(row for row in data["train"] if row["metadata"]["family"] == "copy_new_write")
    corrupted = copy.deepcopy(row)
    corrupted["expected"]["calls"][0]["arguments"]["content"] += "unexpected"
    with pytest.raises(ValueError, match=r"target|prompt|state"):
        builder().audit_replay(corrupted, data["catalog"])
    corrupted = copy.deepcopy(row)
    corrupted["metadata"]["program"]["initial_files"][row["metadata"]["source_path"]] += (
        "unexpected"
    )
    with pytest.raises(ValueError, match=r"target|prompt|state"):
        builder().audit_replay(corrupted, data["catalog"])


def test_candidate_is_deterministic_and_not_v3_redistribution(data):
    rebuilt = builder().generate_dataset(
        seed=20261005, train_count=120, dev_count=120, eval_count=120
    )
    assert data == rebuilt
    for split in ("train", "dev", "eval"):
        assert all(
            row["metadata"]["data_source"] == "independent_synthetic_live_program_v4"
            for row in data[split]
        )
        assert all(row["id"].startswith("synthetic-v4-") for row in data[split])
        assert all(row["metadata"]["user_data_used"] is False for row in data[split])
        assert "PHONE-HOLDOUT" not in json.dumps(data[split], ensure_ascii=False)


@pytest.mark.parametrize(("split", "unit"), (("train", "件"), ("dev", "枚"), ("eval", "个")))
def test_arithmetic_units_preserve_the_visible_task_unit(split, unit):
    program, _metadata = builder()._ordinary_program(split, 9500, 20261005, 5)
    assert program["steps"][0]["text"].endswith(unit + "。")


def test_ordinary_language_targets_can_be_recomputed_without_open_semantic_guessing():
    program, metadata = builder()._ordinary_program("dev", 9501, 20261005, 6)
    assert metadata["ordinary_group"] == "language_extract"
    row = {"messages": [{"role": "user", "content": program["prompt"]}], "metadata": metadata}
    assert builder().independent_language_answer(row) == program["steps"][0]["text"]


def test_candidate_packages_exact_sanitized_runtime_sources_for_reproduction(tmp_path):
    from training.runtime_fixture_v4 import (
        DEFAULT_CATALOG,
        DEFAULT_SYSTEM,
        load_catalog,
        load_system_source,
    )

    module = builder()
    data = {"seed": 20261005, **load_catalog(), "live_system_source": load_system_source()}
    for split in ("train", "dev", "eval"):
        data[split] = [{"metadata": {"ordinary_retention": True}}]
    from unittest.mock import patch

    with patch.object(module, "validate_dataset", return_value={"synthetic_export_control": True}):
        module.write_dataset(data, tmp_path / "candidate")
    assert (
        tmp_path / "candidate/android-catalog-source.json"
    ).read_bytes() == DEFAULT_CATALOG.read_bytes()
    assert (
        tmp_path / "candidate/android-system-source.json"
    ).read_bytes() == DEFAULT_SYSTEM.read_bytes()
