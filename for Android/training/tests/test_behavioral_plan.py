"""The broader V5 experiment cannot silently inherit or weaken V4 budgets."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def helper():
    path = Path(__file__).resolve().parents[1] / "behavioral_plan.py"
    assert path.is_file(), "The fixed V5 behavioral plan must be implemented"
    spec = importlib.util.spec_from_file_location("agent_behavioral_plan", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan():
    return {
        "schema_version": 1,
        "profile": "v5_general",
        "base_weights_sha256": "04b1c301231dd422b8860db31311ab2721511346a32cb1e079c4c4e5f1fe4696",
        "train_records": 1200,
        "dev_records": 200,
        "dev_workflows_records": 20,
        "train_sha256": "a" * 64,
        "dev_sha256": "b" * 64,
        "dev_workflows_sha256": "c" * 64,
        "catalog_sha256": "d" * 64,
        "critical_minima_sha256": "e" * 64,
        "maximum_steps": 600,
        "maximum_epochs": 2,
        "gradient_accumulation": 4,
        "checkpoint_steps": [300, 600],
        "rank": 16,
        "alpha": 32,
        "dropout": 0.05,
        "learning_rate": 0.00002,
        "target_modules_profile": "attention_only",
        "max_length": 3072,
        "training_seed": 20261001,
        "critical_parameter_loss": True,
        "minimum_ordinary_fraction": 0.4,
        "generation": {
            "decoding": "greedy",
            "max_new_tokens": 1024,
            "max_turns": 10,
            "eos_tokens": ["<|im_end|>", "<|endoftext|>"],
            "device": "cuda",
            "dtype": "torch.bfloat16",
            "source_fp32_restored": True,
        },
        "absolute_minima": {"ordinary_overall": 0.9, "ordinary_family": 0.8, "tool_overall": 0.8},
        "autonomous_minima": {"overall": 0.8, "group": 0.5},
        "critical_family_minima": {f"tool-{i}": 0.75 for i in range(15)},
        "tool_families": [f"tool-{i}" for i in range(60)],
        "ordinary_families": [f"ordinary-{i}" for i in range(8)],
        "paired_rules": {
            name: True
            for name in (
                "every_family_no_regression",
                "tool_total_strict_improvement",
                "protocol_no_regression",
                "generation_failures_no_increase",
                "truncation_no_increase",
                "identical_complete_dev",
                "complete_epoch_before_selection",
                "fresh_final_excluded",
                "teacher_loss_not_for_selection",
                "refuse_unqualified_export",
                "workflow_group_no_regression",
                "workflow_total_no_regression",
            )
        },
    }


def arguments():
    return SimpleNamespace(
        behavioral_profile="v5_general",
        steps=600,
        gradient_accumulation=4,
        checkpoint_every=300,
        rank=16,
        learning_rate=0.00002,
        max_length=3072,
        seed=20261001,
        target_modules_profile="attention_only",
        minimum_ordinary_fraction=0.4,
        critical_parameter_loss=True,
        behavioral_max_new_tokens=1024,
        behavioral_max_turns=10,
        prompt_source="runtime",
        eval_limit=0,
        early_stopping_patience=0,
        device="cuda",
    )


def test_fixed_v5_plan_and_cli_preserve_new_explicit_budget_and_structure():
    value = plan()
    assert helper().validate_behavioral_plan(value) == value
    helper().validate_behavioral_plan_cli(value, arguments())
    assert helper().selection_options(value)["maximum_steps"] == 600
    assert helper().selection_options(value)["minimum_ordinary_overall_rate"] == 0.9
    assert helper().selection_options(value)["minimum_ordinary_family_rate"] == 0.8
    assert helper().selection_options(value)["minimum_tool_overall_rate"] == 0.8


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("unknown", True),
        ("schema_version", True),
        ("maximum_steps", 300),
        ("maximum_epochs", 3),
        ("gradient_accumulation", 2),
        ("rank", 8),
        ("alpha", 16),
        ("dropout", 0.0),
        ("learning_rate", 0.00001),
        ("target_modules_profile", "full_v4"),
        ("max_length", 0),
        ("critical_parameter_loss", False),
        ("minimum_ordinary_fraction", 0.1),
        ("train_sha256", "not-pinned"),
        ("base_weights_sha256", "f" * 64),
        ("checkpoint_steps", [150, 600]),
        ("dev_workflows_records", 0),
    ],
)
def test_v5_plan_rejects_unknown_or_weakened_fields(key, value):
    changed = plan()
    changed[key] = value
    with pytest.raises(ValueError):
        helper().validate_behavioral_plan(changed)


def test_v5_nested_plan_cannot_change_metrics_decoding_groups_or_paired_rules():
    variants = []
    for section, key, value in (
        ("absolute_minima", "ordinary_overall", 0.0),
        ("absolute_minima", "ordinary_family", 0.0),
        ("absolute_minima", "tool_overall", 0.0),
        ("autonomous_minima", "overall", 0.0),
        ("autonomous_minima", "group", 0.0),
        ("generation", "decoding", "sample"),
        ("generation", "max_new_tokens", 0),
        ("generation", "max_turns", 0),
        ("generation", "eos_tokens", ["<|endoftext|>"]),
        ("generation", "source_fp32_restored", False),
        ("paired_rules", "fresh_final_excluded", False),
        ("paired_rules", "workflow_total_no_regression", False),
    ):
        changed = plan()
        changed[section][key] = value
        variants.append(changed)
    for changed in variants:
        with pytest.raises(ValueError):
            helper().validate_behavioral_plan(changed)
    changed = plan()
    changed["critical_family_minima"]["tool-0"] = 0
    with pytest.raises(ValueError):
        helper().validate_behavioral_plan(changed)
    for section in ("generation", "paired_rules", "absolute_minima", "autonomous_minima"):
        changed = plan()
        changed[section]["unknown"] = True
        with pytest.raises(ValueError):
            helper().validate_behavioral_plan(changed)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("steps", 300),
        ("rank", 8),
        ("max_length", 4096),
        ("learning_rate", 0.00001),
        ("behavioral_max_new_tokens", 512),
        ("behavioral_max_turns", 4),
        ("target_modules_profile", "full_v4"),
        ("seed", 42),
        ("device", "cpu"),
    ],
)
def test_v5_cli_must_match_the_exact_frozen_plan(key, value):
    args = arguments()
    setattr(args, key, value)
    with pytest.raises(ValueError, match="plan"):
        helper().validate_behavioral_plan_cli(plan(), args)


def test_fixed_input_identity_rejects_changed_data_catalog_minima_or_workflows():
    value = plan()
    hashes = {
        name: value[name]
        for name in (
            "train_sha256",
            "dev_sha256",
            "catalog_sha256",
            "critical_minima_sha256",
            "dev_workflows_sha256",
        )
    }
    helper().validate_behavioral_plan_hashes(value, hashes)
    for key in hashes:
        changed = {**hashes, key: "f" * 64}
        with pytest.raises(ValueError, match="hash"):
            helper().validate_behavioral_plan_hashes(value, changed)


def test_v5_family_and_workflow_counts_include_every_fixed_case_and_group():
    value = plan()
    train, dev = [], []
    for split, count, target in (("train", 12, train), ("dev", 2, dev)):
        for family in value["tool_families"]:
            target.extend(
                {
                    "id": f"{split}-{family}-{i}",
                    "metadata": {
                        "family": family,
                        "ordinary_retention": False,
                    },
                }
                for i in range(count)
            )
    for split, count, target in (("train", 60, train), ("dev", 10, dev)):
        for family in value["ordinary_families"]:
            target.extend(
                {
                    "id": f"{split}-{family}-{i}",
                    "metadata": {
                        "family": family,
                        "ordinary_retention": True,
                    },
                }
                for i in range(count)
            )
    workflows = [
        {"id": f"{group}-{i}", "split": "dev", "group": group}
        for group, count in (("file", 10), ("format", 6), ("search", 4))
        for i in range(count)
    ]
    helper().validate_behavioral_plan_records(value, train, dev, workflows)
    for new_train, new_dev, new_workflows in (
        (train[:-1], dev, workflows),
        (train, dev[:-1], workflows),
        (train, dev, workflows[:-1]),
        (train, dev, workflows * 2),
    ):
        with pytest.raises(ValueError):
            helper().validate_behavioral_plan_records(value, new_train, new_dev, new_workflows)
    wrong = copy.deepcopy(workflows)
    wrong[0]["split"] = "eval"
    with pytest.raises(ValueError):
        helper().validate_behavioral_plan_records(value, train, dev, wrong)
