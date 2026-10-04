"""Dev generation sees only visible input and keeps every failure in its report."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def helper():
    path = Path(__file__).resolve().parents[1] / "behavioral_dev_generation.py"
    assert path.is_file(), "behavioral dev generation must be implemented"
    spec = importlib.util.spec_from_file_location("agent_behavioral_generation", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_turn_eos_stops_real_hf_generation_at_im_end_on_cpu():
    """A checkpoint defaulting to endoftext must not generate fictitious turns."""
    import torch
    from transformers import GPT2Config, GPT2LMHeadModel, LogitsProcessor, LogitsProcessorList

    class Tokens:
        unk_token_id = 1

        def convert_tokens_to_ids(self, token):
            return {"<|im_end|>": 4, "<|endoftext|>": 0}.get(token, self.unk_token_id)

    class ForceContinuation(LogitsProcessor):
        def __call__(self, input_ids, scores):
            token = [8, 4, 9, 0][input_ids.shape[1] - 1]
            scores.fill_(-float("inf"))
            scores[:, token] = 0
            return scores

    model = GPT2LMHeadModel(
        GPT2Config(vocab_size=12, n_layer=1, n_head=1, n_embd=8, eos_token_id=0, bos_token_id=2)
    ).eval()
    inputs = torch.tensor([[2]])
    controls = {
        "do_sample": False,
        "max_new_tokens": 4,
        "pad_token_id": 0,
        "attention_mask": torch.ones_like(inputs),
        "logits_processor": LogitsProcessorList([ForceContinuation()]),
    }
    with torch.no_grad():
        buggy = model.generate(inputs, **controls)[0, 1:].tolist()
        eos_ids = helper().runtime_turn_eos_ids(Tokens())
        repaired = model.generate(inputs, eos_token_id=eos_ids, **controls)[0, 1:].tolist()
    assert buggy == [8, 4, 9, 0]
    assert repaired == [8, 4]
    assert helper().continuation_is_truncated(repaired, max_new_tokens=2, eos_ids=eos_ids) is False
    assert helper().continuation_is_truncated([8, 9], max_new_tokens=2, eos_ids=eos_ids) is True
    assert helper().continuation_is_truncated([8], max_new_tokens=2, eos_ids=eos_ids) is False


def test_runtime_turn_eos_rejects_absent_or_ambiguous_special_tokens():
    class Tokens:
        unk_token_id = 1

        def __init__(self, im_end, endoftext):
            self.mapping = {"<|im_end|>": im_end, "<|endoftext|>": endoftext}

        def convert_tokens_to_ids(self, token):
            return self.mapping[token]

    for values in ((None, 0), (1, 0), (4, 4), (True, 0), (-1, 0)):
        with pytest.raises(ValueError, match="EOS"):
            helper().runtime_turn_eos_ids(Tokens(*values))


def records():
    return [
        {
            "id": name,
            "split": "dev",
            "messages": [{"role": "user", "content": name}],
            "tools": [],
            "target_response": "PRIVATE_TARGET",
            "metadata": {"private": "PRIVATE_METADATA"},
            "expected": {"private": "PRIVATE_EXPECTATION"},
        }
        for name in ("ordinary", "tool", "failure")
    ]


def test_generation_failures_do_not_drop_rows_and_no_label_enters_the_generator():
    data = records()
    visible = []
    scorer_input = []

    def generate(prompt, identifier):
        visible.append((prompt, identifier))
        if identifier == "failure":
            raise RuntimeError("synthetic bounded failure")
        return {
            "raw_output": "raw answer",
            "input_tokens": 9,
            "output_tokens": 2,
            "output_truncated": False,
        }

    def prompt_builder(record):
        return record["messages"][0]["content"]

    def score(rows, predictions, catalog):
        assert rows == data
        assert catalog == {"catalog": "fixture"}
        scorer_input.extend(predictions["samples"])
        return {
            "split": "dev",
            "samples": [
                {
                    "id": row["id"],
                    "behavior_success": False,
                    "ordinary_correct": False,
                    "ordinary_semantics_supported": True,
                    "ordinary_retention": row["id"] == "ordinary",
                    "family": row["id"],
                    "protocol_valid": row["id"] != "failure",
                }
                for row in rows
            ],
        }

    scored, raw = helper().generate_and_score_dev(
        data,
        dataset_sha256="a" * 64,
        generation_config={"backend": "test", "decoding": "greedy"},
        generate_visible=generate,
        build_visible_prompt=prompt_builder,
        score_report=score,
        catalog={"catalog": "fixture"},
    )
    assert len(scored["samples"]) == len(raw["samples"]) == len(data) == 3
    assert visible == [(row["id"], row["id"]) for row in data]
    assert not any("PRIVATE" in prompt for prompt, _ in visible)
    failed = next(row for row in raw["samples"] if row["id"] == "failure")
    assert failed["prediction_generation_success"] is False
    assert "RuntimeError" in failed["generation_error"]
    assert (
        next(row for row in scored["samples"] if row["id"] == "failure")[
            "prediction_generation_success"
        ]
        is False
    )
    assert len(scorer_input) == 3
    assert all(len(row["visible_prompt_sha256"]) == 64 for row in scored["samples"])


def test_scorer_cannot_omit_failures_or_duplicate_dev_ids():
    def generate(prompt, identifier):
        return {"raw_output": "x", "output_truncated": False}

    for predictions in ([{"id": "ordinary"}], [{"id": "ordinary"}] * 3):
        with pytest.raises(ValueError, match="IDs"):
            helper().generate_and_score_dev(
                records(),
                dataset_sha256="a" * 64,
                generation_config={"backend": "test"},
                generate_visible=generate,
                build_visible_prompt=lambda row: row["id"],
                score_report=lambda *args, expected=predictions: {
                    "split": "dev",
                    "samples": expected,
                },
                catalog={},
            )


def test_fresh_final_records_and_scorer_split_cannot_be_relabeled_as_dev():
    for data, scorer_split in (
        ([{**row, "split": "eval"} for row in records()], "dev"),
        (records(), "eval"),
    ):
        with pytest.raises(ValueError, match="dev"):
            helper().generate_and_score_dev(
                data,
                dataset_sha256="a" * 64,
                generation_config={"backend": "test"},
                generate_visible=lambda prompt, identifier: {
                    "raw_output": "x",
                    "output_truncated": False,
                },
                build_visible_prompt=lambda row: row["id"],
                score_report=lambda *args, split=scorer_split, rows=data: {
                    "split": split,
                    "samples": [{"id": row["id"]} for row in rows],
                },
                catalog={},
            )
