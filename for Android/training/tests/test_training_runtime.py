"""Train with the same visible input and loss boundary used by the phone."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
for source in (_ROOT / "src", _ROOT / "for Android"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

_SPEC = importlib.util.spec_from_file_location(
    "agent_training_runtime", Path(__file__).resolve().parents[1] / "train_lora.py"
)
assert _SPEC and _SPEC.loader
_TRAINING = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TRAINING)


class CharacterTokenizer:
    def __call__(self, text, **kwargs):
        assert kwargs["add_special_tokens"] is False
        return {"input_ids": [ord(character) for character in text]}

    def decode(self, tokens):
        return "".join(chr(token) for token in tokens)


def record():
    return {
        "id": "runtime-boundary-fixture",
        "messages": [
            {"role": "system", "content": "Use only advertised tools."},
            {"role": "user", "content": "Copy the note without altering its bytes."},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "read-note",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"path": "notes/测试.txt"}),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "read-note",
                "content": json.dumps(
                    {"content": "\n原文字\n\n", "sha256": "a" * 64}, ensure_ascii=False
                ),
            },
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Create or replace a UTF-8 file using SHA-256 CAS.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                            "expected_sha256": {"type": ["string", "null"]},
                        },
                        "required": ["path", "content", "expected_sha256"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
        "target_response": (
            "<tool_call>\n<function=write_file>\n<parameter=path>\narchive/测试.txt\n"
            "</parameter>\n<parameter=content>\n\n原文字\n\n\n</parameter>\n"
            "<parameter=expected_sha256>\nnull\n</parameter>\n</function>\n</tool_call>"
        ),
        "expected": {"private_label": "MUST_NOT_ENTER_PROMPT"},
        "metadata": {"private_label": "ALSO_NOT_VISIBLE"},
    }


def test_runtime_training_prompt_matches_deployment_and_ignores_labels():
    from training.evaluate_tools import build_evaluation_prompt

    example = record()
    _, actual = build_evaluation_prompt(example, prompt_source="runtime")
    rendered = _TRAINING.render_prompt(example, None, prompt_source="runtime")
    assert rendered == actual
    changed = copy.deepcopy(example)
    changed["target_response"] = "Completely different supervision."
    changed["expected"] = {"another": "SECRET_TARGET"}
    changed["metadata"] = {"another": "SECRET_METADATA"}
    assert _TRAINING.render_prompt(changed, None, prompt_source="runtime") == actual
    assert "MUST_NOT_ENTER_PROMPT" not in actual
    assert "ALSO_NOT_VISIBLE" not in actual


def test_runtime_loss_masks_history_and_preserves_target_whitespace():
    example = record()
    tokenizer = CharacterTokenizer()
    prompt = _TRAINING.render_prompt(example, None, prompt_source="runtime")
    features, stats = _TRAINING.tokenize_records(
        [example], tokenizer, 10000, prompt_source="runtime"
    )
    feature = features[0]
    assert tokenizer.decode(feature["input_ids"][: len(prompt)]) == prompt
    assert feature["labels"][: len(prompt)] == [-100] * len(prompt)
    labels = [value for value in feature["labels"] if value != -100]
    assert tokenizer.decode(labels) == example["target_response"] + "<|im_end|>"
    assert stats["truncated_records"] == 0


def test_runtime_split_gate_rejects_the_same_visible_input_with_changed_labels():
    example = record()
    changed = copy.deepcopy(example)
    changed["expected"] = {"different": True}
    changed["target_response"] = "Different final answer."
    with pytest.raises(ValueError, match=r"canonical.*overlap"):
        _TRAINING.ensure_disjoint_prompts(
            [example], [changed], CharacterTokenizer(), prompt_source="runtime"
        )


def test_unknown_training_prompt_source_is_rejected():
    with pytest.raises(ValueError, match=r"prompt.source"):
        _TRAINING.render_prompt(record(), None, prompt_source="unrecognized")


def test_actual_base_tokenizer_maps_critical_cas_without_masking_its_target():
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        Path(__file__).resolve().parents[1] / "models" / "qwen3.5-0.8b", local_files_only=True
    )
    features, stats = _TRAINING.tokenize_records(
        [record()], tokenizer, 10000, prompt_source="runtime", critical_parameter_loss=True
    )
    feature = features[0]
    cas = next(group for group in feature["critical_groups"] if group["kind"] == "cas")
    assert (
        tokenizer.decode([feature["input_ids"][index] for index in cas["indices"]]).strip()
        == "null"
    )
    assert all(
        feature["labels"][index] != -100
        for group in feature["critical_groups"]
        for index in group["indices"]
    )
    assert stats["truncated_records"] == 0
