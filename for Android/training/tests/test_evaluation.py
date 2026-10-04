from __future__ import annotations

import copy
import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ANDROID_ROOT = Path(__file__).resolve().parents[2]
for source in (ANDROID_ROOT, ANDROID_ROOT.parent / "src"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))


def helper(name):
    evaluation = importlib.import_module("training.evaluate_tools")
    function = getattr(evaluation, name, None)
    assert callable(function), f"the CPU-testable evaluation helper {name} is missing"
    return function


@pytest.mark.parametrize("failure", ["timeout", "exit", None])
def test_completion_process_preserves_both_streams_and_records_failure(
    tmp_path, monkeypatch, failure
):
    run = helper("run_completion_process")
    evaluation = importlib.import_module("training.evaluate_tools")

    def process(command, *, stdin, stdout, stderr, timeout, check):
        assert command == ["pinned-completion", "--no-escape"]
        assert stdin == subprocess.DEVNULL and timeout == 240 and check is True
        stdout.write("模型原文\n".encode())
        stderr.write(b"load diagnostic\n")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, timeout)
        if failure == "exit":
            raise subprocess.CalledProcessError(7, command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(evaluation.subprocess, "run", process)
    result = run(["pinned-completion", "--no-escape"], tmp_path)
    assert result["stdout"] == "模型原文\n"
    assert result["stderr"] == "load diagnostic\n"
    assert result["timed_out"] is (failure == "timeout")
    assert result["returncode"] == (None if failure == "timeout" else 7 if failure == "exit" else 0)
    assert bool(result["error"]) is (failure is not None)


def record():
    return {
        "messages": [
            {"role": "system", "content": "Use the observed tool result as data."},
            {"role": "user", "content": "Read the selected file again."},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "previous-read",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"path": "notes/example.txt"}),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "previous-read",
                "content": json.dumps({"path": "notes/example.txt", "content": "line1\nline2"}),
            },
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the chosen UTF-8 file.",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
        "expected": {"private_label": "EXPECTED_LABEL_CANARY_6821"},
        "target_response": "TARGET_RESPONSE_CANARY_7251",
    }


TOOL_OUTPUT = (
    "<tool_call>\n<function=read_file>\n<parameter=path>\nnotes/example.txt\n"
    "</parameter>\n</function>\n</tool_call>"
)


@pytest.mark.parametrize("newlines", ["\n", "\n\n", "\n\n\n"])
def test_one_normal_completion_footer_is_removed_without_changing_generated_text(newlines):
    strip_footer = helper("strip_completion_footer")
    generated = "\n" + TOOL_OUTPUT + "\n"
    assert strip_footer(generated + " [end of text]" + newlines) == (generated, True)


def test_real_model_suffix_survives_cli_footer_removal_and_atomic_parser_rejects_it():
    from android_adapter.local_provider import parse_qwen_output

    from agent_workspace.providers.base import ProviderError

    strip_footer = helper("strip_completion_footer")
    build_prompt = helper("build_evaluation_prompt")
    request, _ = build_prompt(record())
    generated = TOOL_OUTPUT + " [end of text]\n"
    cleaned, detected = strip_footer(generated + " [end of text]\n\n\n")
    assert detected is True
    assert cleaned == generated
    with pytest.raises(ProviderError, match="trailing suffix"):
        parse_qwen_output(cleaned, request, "footer-regression")


@pytest.mark.parametrize(
    "generated",
    ["\n" + TOOL_OUTPUT + "\n\n", "  text with [end of text] inside\n\t", " [end of text]"],
)
def test_no_cli_footer_preserves_the_original_output_exactly(generated):
    assert helper("strip_completion_footer")(generated) == (generated, False)


def test_runtime_prompt_matches_real_adapter_and_does_not_read_or_change_answer_labels():
    from android_adapter.local_provider import build_qwen_prompt

    from agent_workspace.core.models import ChatMessage, ProviderRequest, Role, ToolCall, ToolSpec

    class VisibleInputOnly(dict):
        def __getitem__(self, key):
            assert key not in {"expected", "target_response"}, "an answer label reached the builder"
            return super().__getitem__(key)

        def get(self, key, default=None):
            assert key not in {"expected", "target_response"}, "an answer label reached the builder"
            return super().get(key, default)

    build_prompt = helper("build_evaluation_prompt")
    first = record()
    snapshot = copy.deepcopy(first)
    request, prompt = build_prompt(VisibleInputOnly(first))
    tool = first["tools"][0]["function"]
    real_request = ProviderRequest(
        "qwen3.5-0.8b-q4-k-m",
        (
            ChatMessage(Role.SYSTEM, first["messages"][0]["content"]),
            ChatMessage(Role.USER, first["messages"][1]["content"]),
            ChatMessage(
                Role.ASSISTANT,
                "",
                tool_calls=(ToolCall("previous-read", "read_file", {"path": "notes/example.txt"}),),
            ),
            ChatMessage(Role.TOOL, first["messages"][3]["content"], tool_call_id="previous-read"),
        ),
        tools=(ToolSpec(tool["name"], tool["description"], tool["parameters"], "read"),),
    )
    assert request == real_request
    assert prompt == build_qwen_prompt(real_request)
    assert "\\n" in prompt  # Tool-result JSON must stay escaped for the raw CLI file.
    assert first == snapshot
    assert first["target_response"] not in prompt
    assert first["expected"]["private_label"] not in prompt
    changed = copy.deepcopy(first)
    changed["target_response"] = "a completely different hidden completion"
    changed["expected"] = {"kind": "tool_call", "calls": [{"name": "imaginary_tool"}]}
    assert build_prompt(VisibleInputOnly(changed)) == (request, prompt)


@pytest.mark.parametrize("use_adapter", [False, True])
def test_hf_comparison_restores_source_precision_before_adapter_and_device(
    tmp_path,
    monkeypatch,
    use_adapter,
):
    from training import train_lora

    events = []

    class Model:
        def to(self, device):
            events.append(("device", device))
            return self

        def eval(self):
            return self

    model = Model()

    def load(directory, **options):
        assert directory == tmp_path
        assert options == {"dtype": "bf16", "attn_implementation": "sdpa", "local_files_only": True}
        events.append("load")
        return model

    def restore(actual, directory):
        assert actual is model and directory == tmp_path
        events.append("restore_fp32")
        return ["original.norm.weight"]

    def adapter(actual, directory, **options):
        assert actual is model and directory == tmp_path / "adapter"
        assert options == {"local_files_only": True}
        events.append("adapter")
        return model

    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(Qwen3_5ForConditionalGeneration=SimpleNamespace(from_pretrained=load)),
    )
    monkeypatch.setitem(
        sys.modules, "peft", SimpleNamespace(PeftModel=SimpleNamespace(from_pretrained=adapter))
    )
    monkeypatch.setattr(train_lora, "restore_source_fp32_parameters", restore)
    loaded, restored = helper("load_evaluation_model")(
        tmp_path, dtype="bf16", device="cuda", adapter=tmp_path / "adapter" if use_adapter else None
    )
    assert loaded is model and restored == ["original.norm.weight"]
    assert events == ["load", "restore_fp32"] + (["adapter"] if use_adapter else []) + [
        ("device", "cuda")
    ]
