from __future__ import annotations

import copy
import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ANDROID_ROOT = Path(__file__).resolve().parents[2]
for source in (ANDROID_ROOT, ANDROID_ROOT.parent / "src"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))


def modules():
    assert importlib.util.find_spec("training.build_dataset") is not None, (
        "the synthetic dataset builder is missing"
    )
    assert importlib.util.find_spec("training.validate_dataset") is not None, (
        "the independent dataset validator is missing"
    )
    return (
        importlib.import_module("training.build_dataset"),
        importlib.import_module("training.validate_dataset"),
    )


@pytest.fixture(autouse=True)
def frozen_v1_schema(monkeypatch):
    # V1 training and evidence stay reproducible against their historical
    # contracts. Current Android action requirements are covered by v2 tests.
    catalog = json.loads(
        (ANDROID_ROOT / "training" / "data" / "catalog.json").read_text(encoding="utf-8")
    )
    builder, _ = modules()
    monkeypatch.setattr(builder, "schema_catalog", lambda: copy.deepcopy(catalog))


def test_synthetic_examples_pass_historical_advertised_and_execution_schemas(tmp_path):
    builder, validator = modules()
    data = builder.generate_dataset(seed=1703, train_count=64, eval_count=32)
    summary = validator.validate_splits(data["train"], data["eval"], data["catalog"])
    assert summary["examples"] == 96
    assert summary["tool_calls"] > 64
    assert {"write_file", "select_local_tools", "android_action", "todo", "memory_write"} <= set(
        summary["tool_names"]
    )
    assert all(item["metadata"]["synthetic"] is True for item in data["train"] + data["eval"])
    builder.write_dataset(data, tmp_path)
    assert len((tmp_path / "train.jsonl").read_text(encoding="utf-8").splitlines()) == 64


def test_splits_use_disjoint_entities_compositions_and_example_ids():
    builder, _ = modules()
    data = builder.generate_dataset(seed=17, train_count=64, eval_count=32)
    for key in ("entity", "scenario_group"):
        assert {row["metadata"][key] for row in data["train"]}.isdisjoint(
            {row["metadata"][key] for row in data["eval"]}
        )
    assert {row["id"] for row in data["train"]}.isdisjoint({row["id"] for row in data["eval"]})
    assert data == builder.generate_dataset(seed=17, train_count=64, eval_count=32)


@pytest.mark.parametrize("mutation", ["required", "unknown_tool", "truncated", "unsafe_path"])
def test_independent_validator_rejects_bad_tool_proposals(mutation):
    builder, validator = modules()
    data = builder.generate_dataset(seed=71, train_count=64, eval_count=16)
    original = next(row for row in data["train"] if row["metadata"]["family"] == "create_file")
    row = copy.deepcopy(original)
    if mutation == "required":
        start = row["target_response"].index("<parameter=expected_sha256>")
        end = row["target_response"].index("</parameter>", start) + len("</parameter>")
        row["target_response"] = row["target_response"][:start] + row["target_response"][end:]
    elif mutation == "unknown_tool":
        row["target_response"] = row["target_response"].replace(
            "function=write_file", "function=html"
        )
    elif mutation == "truncated":
        row["target_response"] = row["target_response"].replace("</tool_call>", "")
    else:
        path = row["expected"]["calls"][0]["arguments"]["path"]
        row["target_response"] = row["target_response"].replace(path, "../outside.txt")
    with pytest.raises(ValueError):
        validator.validate_example(row, data["catalog"])


def test_nullable_file_hash_is_none_and_every_earlier_tool_has_a_result():
    builder, validator = modules()
    data = builder.generate_dataset(seed=27, train_count=64, eval_count=16)
    row = next(row for row in data["train"] if row["metadata"]["family"] == "create_file")
    calls = validator.parse_tool_response(row["target_response"], data["catalog"])
    assert calls[0]["arguments"]["expected_sha256"] is None
    validator.validate_splits(data["train"], data["eval"], data["catalog"])


def test_generated_targets_are_accepted_atomically_by_the_actual_qwen_adapter():
    from android_adapter.local_provider import parse_qwen_output

    from agent_workspace.core.models import ChatMessage, DeltaKind, ProviderRequest, Role, ToolSpec

    builder, _ = modules()
    data = builder.generate_dataset(seed=15, train_count=32, eval_count=16)
    for row in data["train"] + data["eval"]:
        tools = tuple(
            ToolSpec(
                name=tool["function"]["name"],
                description=tool["function"]["description"],
                input_schema=data["catalog"][tool["function"]["name"]]["execution_schema"],
                provider_input_schema=tool["function"]["parameters"],
                side_effect=data["catalog"][tool["function"]["name"]]["side_effect"],
            )
            for tool in row["tools"]
        )
        request = ProviderRequest(
            "qwen3.5-0.8b-q4-k-m", (ChatMessage(Role.USER, "Synthetic validation"),), tools=tools
        )
        deltas = parse_qwen_output(row["target_response"], request, row["id"])
        calls = [
            {"name": delta.tool_call.name, "arguments": delta.tool_call.arguments}
            for delta in deltas
            if delta.kind is DeltaKind.TOOL_CALL
        ]
        assert calls == row["expected"].get("calls", [])


def test_generation_never_uses_unrelated_local_file_content(tmp_path, monkeypatch):
    builder, _ = modules()
    private_marker = "private_fixture_must_not_enter_synthetic_examples_7392"
    (tmp_path / "user-conversation.txt").write_text(private_marker, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    data = builder.generate_dataset(seed=21, train_count=64, eval_count=16)
    serialized = json.dumps(data, ensure_ascii=False)
    assert private_marker not in serialized
    assert "鹈鹕" not in serialized
