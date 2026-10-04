from __future__ import annotations

import hashlib
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


def builder():
    assert importlib.util.find_spec("training.build_dataset_v2") is not None, (
        "the independent v2 builder is missing"
    )
    return importlib.import_module("training.build_dataset_v2")


@pytest.fixture(scope="module")
def data():
    return builder().generate_dataset(seed=6197, train_count=80, dev_count=48, eval_count=48)


def results(row):
    return [
        builder()._result(message["content"])
        for message in row["messages"]
        if message["role"] == "tool"
    ]


def test_three_splits_have_disjoint_entities_templates_and_real_task_graphs(data):
    assert set(data) >= {"train", "dev", "eval", "catalog", "seed"}
    for first, second in (("train", "dev"), ("train", "eval"), ("dev", "eval")):
        for attribute in ("entity", "scenario_group", "request_template", "task_graph"):
            assert {row["metadata"][attribute] for row in data[first]}.isdisjoint(
                {row["metadata"][attribute] for row in data[second]}
            ), attribute
    builder().validate_dataset(data)
    assert {row["metadata"]["family"] for row in data["train"]} <= {
        row["metadata"]["family"] for row in data["dev"]
    }
    for split in ("train", "dev", "eval"):
        assert len({row["id"] for row in data[split]}) == len(data[split])
        ordinary = sum(row["metadata"]["ordinary_retention"] for row in data[split])
        assert 0.25 <= ordinary / len(data[split]) <= 0.35
        assert all(row["metadata"]["user_data_used"] is False for row in data[split])


def test_read_result_copy_targets_preserve_exact_content_and_actual_null(data):
    rows = [row for row in data["train"] if row["metadata"]["family"] == "copy_from_read"]
    assert rows
    for row in rows:
        target = row["expected"]["calls"][0]
        source = next(result for result in results(row) if "content" in result)
        assert row["metadata"]["real_tools_executed"] is True
        assert target["name"] == "write_file"
        assert target["arguments"]["content"] == source["content"]
        assert target["arguments"]["expected_sha256"] is None
        assert source["sha256"] == hashlib.sha256(source["content"].encode()).hexdigest()


def test_real_file_and_todo_result_fields_are_not_handmade_aliases(data):
    saw_write = saw_todo = False
    for row in data["train"]:
        pending = {}
        for message in row["messages"]:
            for call in message.get("tool_calls", []):
                pending[call["id"]] = call["function"]["name"]
            if message["role"] != "tool":
                continue
            result = builder()._result(message["content"])
            name = pending.pop(message["tool_call_id"])
            if name == "write_file" and "error" not in result:
                saw_write = True
                assert {"path", "bytes_written", "sha256"} == result.keys()
            if name == "todo" and "todo_id" in result:
                saw_todo = True
                assert set(result) == {"todo_id", "status"}
                assert result["status"] in {"pending", "completed"}
    assert saw_write and saw_todo


def test_verified_success_ends_with_text_and_failures_have_a_recovery_step(data):
    verified = [row for row in data["train"] if row["metadata"]["family"] == "android_done"]
    recovered = [row for row in data["train"] if "recover" in row["metadata"]["family"]]
    assert verified and recovered
    for row in verified:
        assert results(row)[-1]["verified"] is True
        assert row["expected"]["kind"] == "text"
        assert "<tool_call>" not in row["target_response"]
    for row in recovered:
        assert any("error" in result for result in results(row))
        assert row["expected"]["kind"] == "tool_call"


def test_android_text_action_contains_observed_ref_snapshot_and_text(data):
    rows = [row for row in data["train"] if row["metadata"]["family"] == "android_type"]
    assert rows
    for row in rows:
        call = row["expected"]["calls"][0]
        args = call["arguments"]
        assert call["name"] == "android_action"
        assert args["action"] == "type_text"
        assert {"ref", "snapshot_version", "text"} <= args.keys()
        observation = [result["observation"] for result in results(row) if "observation" in result][
            -1
        ]
        assert args["snapshot_version"] == observation["snapshot_version"]
        assert any(node["ref"] == args["ref"] for node in observation["nodes"])


def test_complete_targets_are_accepted_by_the_actual_atomic_adapter(data):
    from android_adapter.local_provider import parse_qwen_output
    from training.evaluate_tools import build_evaluation_prompt

    from agent_workspace.core.models import DeltaKind

    for split in ("train", "dev", "eval"):
        for row in data[split]:
            request, prompt = build_evaluation_prompt(row)
            assert row["metadata"]["data_source"] == "procedural_synthetic_v2"
            assert "鹈鹕" not in prompt + row["target_response"]
            actual = parse_qwen_output(row["target_response"], request, row["id"])
            calls = [
                {"name": delta.tool_call.name, "arguments": delta.tool_call.arguments}
                for delta in actual
                if delta.kind is DeltaKind.TOOL_CALL
            ]
            assert calls == row["expected"].get("calls", [])


def test_generation_is_deterministic_and_does_not_read_unrelated_user_files(tmp_path, monkeypatch):
    module = builder()
    sentinel = "private_v2_fixture_must_stay_outside_training_47318"
    (tmp_path / "private-chat.txt").write_text(sentinel)
    monkeypatch.chdir(tmp_path)
    first = module.generate_dataset(seed=719, train_count=24, dev_count=24, eval_count=24)
    assert first == module.generate_dataset(seed=719, train_count=24, dev_count=24, eval_count=24)
    assert sentinel not in json.dumps(first, ensure_ascii=False)


def test_filesystem_histories_and_targets_replay_with_real_tools(data, tmp_path):
    from agent_workspace.tools.base import ToolError
    from agent_workspace.tools.filesystem import ListFilesTool, ReadFileTool, WriteFileTool
    from agent_workspace.tools.manage import _make_directory_sync

    families = {
        "copy_from_read",
        "copy_verify",
        "file_done",
        "edit_cas",
        "cas_recover_read",
        "cas_recover_write",
        "mkdir_recover",
        "mkdir_selected_write",
        "create_file",
        "two_reads",
        "reject_tool_instruction",
    }
    for split in ("train", "dev", "eval"):
        replayed = set()
        for row in data[split]:
            family = row["metadata"]["family"]
            if family not in families or family in replayed:
                continue
            replayed.add(family)
            root = tmp_path / row["id"]
            root.mkdir()
            for directory in row["metadata"]["fixture_directories"]:
                _make_directory_sync(str(root), directory)
            tools = {
                "read_file": ReadFileTool(root),
                "write_file": WriteFileTool(root),
                "list_files": ListFilesTool(root),
            }
            for path, content in row["metadata"]["fixture_files"].items():
                tools["write_file"]._execute_sync(
                    {"path": path, "content": content, "expected_sha256": None}
                )

            def execute(item, root=root, tools=tools):
                try:
                    if item["name"] == "make_directory":
                        return json.loads(
                            _make_directory_sync(str(root), item["arguments"]["path"])
                        )
                    return json.loads(tools[item["name"]]._execute_sync(item["arguments"]))
                except ToolError as failure:
                    return {
                        "error": f"Tool failed ({type(failure).__name__}): "
                        + str(failure).replace(str(root), "<workspace>")
                    }

            pending, step = {}, 0
            for message in row["messages"]:
                for item in message.get("tool_calls", []):
                    pending[item["id"]] = item["function"]
                if message["role"] != "tool":
                    continue
                item = pending.pop(message["tool_call_id"])
                if item["name"] in tools or item["name"] == "make_directory":
                    assert execute(item) == builder()._result(message["content"])
                for mutation in row["metadata"]["external_mutations"]:
                    if mutation["after_history_step"] == step:
                        (root / mutation["path"]).write_text(
                            mutation["content"], encoding="utf-8", newline=""
                        )
                step += 1
            for item in row["expected"].get("calls", []):
                result = execute(item)
                assert "error" not in result
                if item["name"] == "write_file":
                    assert (root / item["arguments"]["path"]).read_bytes() == item["arguments"][
                        "content"
                    ].encode()
            if family == "file_done":
                original = row["metadata"]["fixture_files"]
                assert (
                    root / f"archive/{row['metadata']['entity']}-copy.txt"
                ).read_bytes() == next(iter(original.values())).encode()
        assert replayed == families
