"""Test balanced dev coverage and honest checkpoint selection without a model."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "agent_training_validation", Path(__file__).resolve().parents[1] / "train_lora.py"
)
assert _SPEC and _SPEC.loader
_TRAINING = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TRAINING)


def function(name):
    value = getattr(_TRAINING, name, None)
    assert callable(value), f"training needs {name}"
    return value


def test_periodically_ordered_dev_keeps_every_family_in_a_limited_probe():
    records = [{"metadata": {"family": f"family-{index % 12}"}} for index in range(96)]
    selected = function("stratified_dev_indices")(records, 32)
    assert len(selected) == len(set(selected)) == 32
    assert {records[index]["metadata"]["family"] for index in selected} == {
        f"family-{index}" for index in range(12)
    }


def test_full_dev_uses_every_record_and_a_probe_cannot_drop_families():
    records = [{"metadata": {"family": f"family-{index % 12}"}} for index in range(96)]
    select = function("stratified_dev_indices")
    assert select(records, 0) == list(range(96))
    with pytest.raises(ValueError, match="families"):
        select(records, 3)


def test_short_training_budget_covers_every_family_with_deterministic_sampling():
    records = [{"metadata": {"family": "many_tools"}} for _ in range(80)] + [
        {"metadata": {"family": family}}
        for family in ("arithmetic", "finish_task", "copy_exact_content")
        for _ in range(8)
    ]
    order = function("balanced_training_order")(records, seed=517)
    assert order == function("balanced_training_order")(records, seed=517)
    assert len(order) == len(set(order)) == len(records)
    assert set(order) == set(range(len(records)))
    for batch in (order[:4], order[4:8]):
        assert {records[index]["metadata"]["family"] for index in batch} == {
            "many_tools",
            "arithmetic",
            "finish_task",
            "copy_exact_content",
        }


def test_selected_checkpoint_sampling_reports_only_its_consumed_prefix():
    records = [
        {"id": "tool-a", "metadata": {"family": "copy", "ordinary_retention": False}},
        {"id": "math-a", "metadata": {"family": "math", "ordinary_retention": True}},
        {"id": "tool-b", "metadata": {"family": "copy", "ordinary_retention": False}},
        {"id": "math-b", "metadata": {"family": "math", "ordinary_retention": True}},
    ]
    describe = function("describe_training_sampling")
    selected = describe(records, [0, 1])
    full_run = describe(records, [0, 1, 2, 3])
    assert selected["examples_consumed"] == selected["unique_examples_consumed"] == 2
    assert selected["ordinary_examples_consumed"] == 1
    assert selected["ordinary_fraction"] == 0.5
    assert selected["sampled_record_ids"] == ["tool-a", "math-a"]
    assert selected["complete_training_set_seen"] is False
    assert full_run["complete_training_set_seen"] is True
    assert full_run["examples_consumed"] == full_run["unique_examples_consumed"] == 4
    assert full_run["ordinary_examples_consumed"] == 2


def test_sampling_provenance_keeps_repeated_examples_separate_from_unique_coverage():
    records = [
        {"id": "tool-a", "metadata": {"family": "copy", "ordinary_retention": False}},
        {"id": "math-a", "metadata": {"family": "math", "ordinary_retention": True}},
    ]
    sampled = function("describe_training_sampling")(records, [0, 1, 1])
    assert sampled["examples_consumed"] == 3
    assert sampled["unique_examples_consumed"] == 2
    assert sampled["ordinary_examples_consumed"] == 2
    assert sampled["ordinary_fraction"] == pytest.approx(2 / 3)
    assert sampled["sampled_family_counts"] == {"copy": 1, "math": 2}


def test_retention_sampler_covers_every_record_and_preserves_every_global_prefix():
    records = [
        {
            "id": f"record-{index}",
            "metadata": {"family": f"ordinary-{index % 3}", "ordinary_retention": True},
        }
        for index in range(24)
    ] + [
        {
            "id": f"record-{index + 24}",
            "metadata": {"family": f"tool-{index % 9}", "ordinary_retention": False},
        }
        for index in range(36)
    ]
    sampler = function("retention_balanced_training_order")
    first = sampler(records, seed=817, minimum_ordinary_fraction=0.4)
    second = sampler(records, seed=818, minimum_ordinary_fraction=0.4)
    assert first == sampler(records, seed=817, minimum_ordinary_fraction=0.4)
    assert first != second
    assert sorted(first) == sorted(second) == list(range(60))
    for length in range(1, 121):
        prefix = (first + second)[:length]
        assert (
            sum(records[index]["metadata"]["ordinary_retention"] for index in prefix) / length
            >= 0.4
        )
    assert {records[index]["metadata"]["family"] for index in first[:30]} == {
        records[index]["metadata"]["family"] for index in first
    }


def test_retention_sampler_cannot_relabel_or_oversample_to_fix_insufficient_source_data():
    records = [
        {"metadata": {"family": "ordinary", "ordinary_retention": index < 3}} for index in range(10)
    ]
    with pytest.raises(ValueError, match="ordinary"):
        function("retention_balanced_training_order")(
            records, seed=5, minimum_ordinary_fraction=0.4
        )


def test_family_macro_loss_does_not_hide_short_general_ability_targets():
    aggregate = function("aggregate_dev_losses")
    result = aggregate([("tool", 0.2, 100), ("tool", 0.4, 100), ("arithmetic", 2.0, 2)])
    assert result["loss"] == pytest.approx(64 / 202)
    assert result["macro_loss"] == pytest.approx(1.15)
    assert result["families"]["tool"] == {
        "loss": pytest.approx(0.3),
        "supervised_tokens": 200,
        "records": 2,
    }
    assert result["families"]["arithmetic"]["records"] == 1
    assert result["records"] == 3


def test_validation_rejects_non_finite_losses():
    with pytest.raises(ValueError, match="finite"):
        function("aggregate_dev_losses")([("arithmetic", float("nan"), 2)])


def test_early_stopping_preserves_the_best_checkpoint_instead_of_the_last():
    history = [
        {"step": 12, "metrics": {"macro_loss": 0.8}},
        {"step": 24, "metrics": {"macro_loss": 0.9}},
        {"step": 36, "metrics": {"macro_loss": 1.1}},
    ]
    selected = function("select_dev_checkpoint")(
        {"macro_loss": 1.0}, history, patience=2, min_delta=0.001
    )
    assert selected["selected_step"] == 12
    assert selected["should_stop"] is True
    assert selected["improved_over_baseline"] is True


def test_a_trained_checkpoint_cannot_claim_improvement_over_a_better_base():
    history = [
        {"step": 12, "metrics": {"macro_loss": 1.2}},
        {"step": 24, "metrics": {"macro_loss": 1.1}},
    ]
    selected = function("select_dev_checkpoint")(
        {"macro_loss": 1.0}, history, patience=2, min_delta=0.001
    )
    assert selected["selected_step"] == 24
    assert selected["should_stop"] is True
    assert selected["improved_over_baseline"] is False


def test_restoring_best_adapter_replaces_later_updates_exactly(tmp_path):
    torch = pytest.importorskip("torch")
    peft = pytest.importorskip("peft")

    class TinyModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.linear = torch.nn.Linear(2, 2, bias=False)

        def forward(self, value):
            return self.linear(value)

    model = peft.get_peft_model(TinyModel(), peft.LoraConfig(r=2, target_modules=["linear"]))
    with torch.no_grad():
        for name, parameter in model.named_parameters():
            if ".lora_B." in name:
                parameter.fill_(0.125)
    checkpoint = tmp_path / "checkpoint-12"
    model.save_pretrained(checkpoint, safe_serialization=True)
    expected = {
        name: value.detach().clone()
        for name, value in peft.get_peft_model_state_dict(model).items()
    }
    digest = _TRAINING.sha256_file(checkpoint / "adapter_model.safetensors")
    with torch.no_grad():
        for name, parameter in model.named_parameters():
            if ".lora_B." in name:
                parameter.fill_(0.5)
    restore = function("restore_saved_adapter")
    with pytest.raises(ValueError, match="hash"):
        restore(model, checkpoint, "bad-hash")
    restore(model, checkpoint, digest)
    actual = peft.get_peft_model_state_dict(model)
    assert set(actual) == set(expected)
    for name in actual:
        assert actual[name].dtype == expected[name].dtype
        assert torch.equal(actual[name], expected[name])
    final_adapter = tmp_path / "selected-adapter"
    model.save_pretrained(final_adapter, safe_serialization=True)
    assert _TRAINING.sha256_file(final_adapter / "adapter_model.safetensors") == digest
