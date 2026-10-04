"""The memory probe measures complete backward passes without optimizer updates."""

from __future__ import annotations

import copy
import importlib
import sys
from pathlib import Path

import pytest

ANDROID = Path(__file__).resolve().parents[2]
for source in (ANDROID, ANDROID.parent / "src"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))


def probe():
    path = ANDROID / "training/probe_training_memory.py"
    assert path.is_file(), "Complete Qwen backward feasibility needs a no-update probe"
    return importlib.import_module("training.probe_training_memory")


def sample_features():
    records = [
        {"id": f"{split}-{index}", "split": split}
        for split in ("train", "dev")
        for index in range(2)
    ]
    features = [
        {"input_ids": [1] * length, "labels": [-100] * (length - target) + [1] * target}
        for length, target in ((8, 3), (12, 2), (10, 7), (9, 4))
    ]
    return records, features


def test_probe_selects_full_longest_sequence_and_longest_assistant_target():
    records, features = sample_features()
    selected = probe().select_memory_probe_cases(records, features)
    assert {row["record"]["id"] for row in selected} == {"train-1", "dev-0"}
    assert [row["sequence_tokens"] for row in selected] == [12, 10]
    assert [row["supervised_tokens"] for row in selected] == [2, 7]
    assert selected[0]["feature"] is features[1]
    assert selected[1]["feature"] is features[2]
    records[0]["split"] = "eval"
    with pytest.raises(ValueError, match=r"train|dev"):
        probe().select_memory_probe_cases(records, features)


def test_same_longest_case_still_probes_at_least_two_unique_complete_examples():
    records, features = sample_features()
    features[1]["labels"] = [1] * 12
    selected = probe().select_memory_probe_cases(records, features)
    assert len(selected) >= 2
    assert len({row["record"]["id"] for row in selected}) == len(selected)


@pytest.mark.parametrize("critical", [False, True])
def test_shared_assistant_forward_loss_matches_full_causal_gradient(critical):
    import torch

    trainer = importlib.import_module("training.train_lora")
    assert callable(getattr(trainer, "assistant_forward_loss", None))

    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.table = torch.nn.Parameter(torch.arange(5 * 7).float().reshape(5, 7) / 20)

        def forward(self, *, input_ids, attention_mask, use_cache, logits_to_keep):
            assert use_cache is False and input_ids.shape[1] == 5
            assert logits_to_keep.tolist() == [1, 2, 3]
            from types import SimpleNamespace

            return SimpleNamespace(logits=self.table[logits_to_keep].unsqueeze(0))

    feature = {
        "input_ids": [0, 1, 2, 3, 4],
        "attention_mask": [1] * 5,
        "labels": [-100, -100, 2, 3, 4],
        "critical_groups": [{"kind": "function", "indices": [2, 3]}],
    }
    actual_model, expected_model = Model(), Model()
    actual = trainer.assistant_forward_loss(
        actual_model, feature, torch=torch, device="cpu", critical=critical
    )
    logits = expected_model.table[:-1].unsqueeze(0)
    targets = torch.tensor([feature["labels"][1:]])
    if critical:
        from training.critical_parameter_loss import grouped_cross_entropy

        expected, _ = grouped_cross_entropy(
            logits, targets, [{"kind": "function", "indices": [1, 2]}]
        )
    else:
        expected = torch.nn.functional.cross_entropy(
            logits.reshape(-1, 7), targets.reshape(-1), ignore_index=-100
        )
    actual.backward()
    expected.backward()
    assert torch.allclose(actual, expected, atol=1e-6)
    assert torch.allclose(actual_model.table.grad, expected_model.table.grad, atol=1e-6)


def test_cpu_probe_accumulates_gradients_and_never_constructs_an_optimizer(monkeypatch):
    import torch

    module = probe()
    model = torch.nn.Linear(2, 2)
    before = copy.deepcopy(model.state_dict())
    records, features = sample_features()
    selected = module.select_memory_probe_cases(records, features)

    def forbidden(*args, **kwargs):
        pytest.fail("The feasibility probe must never construct or update an optimizer")

    monkeypatch.setattr(torch.optim, "AdamW", forbidden)
    calls = []

    def loss(feature):
        calls.append(len(feature["input_ids"]))
        return model(torch.ones(1, 2)).square().mean()

    report = module.run_backward_probe(
        model,
        selected,
        forward_loss=loss,
        torch=torch,
        device="cpu",
        gradient_accumulation=4,
    )
    assert calls == [12] * 4 + [10] * 4
    assert report["optimizer_updates"] == 0 and report["adapter_exported"] is False
    assert report["parameter_hash_before"] == report["parameter_hash_after"]
    assert report["passed"] is True and len(report["cases"]) == 2
    assert all(torch.equal(value, before[name]) for name, value in model.state_dict().items())
    assert all(value.grad is None for value in model.parameters())
