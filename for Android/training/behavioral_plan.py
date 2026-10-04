"""Strict, byte-pinned settings for the separately reviewed V5 experiment."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

BASE_SHA256 = "04b1c301231dd422b8860db31311ab2721511346a32cb1e079c4c4e5f1fe4696"
PAIRED_RULES = {
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
}
INPUT_HASH_KEYS = {
    "train_sha256",
    "dev_sha256",
    "catalog_sha256",
    "critical_minima_sha256",
    "dev_workflows_sha256",
}
PLAN_KEYS = INPUT_HASH_KEYS | {
    "schema_version",
    "profile",
    "base_weights_sha256",
    "train_records",
    "dev_records",
    "dev_workflows_records",
    "maximum_steps",
    "maximum_epochs",
    "gradient_accumulation",
    "checkpoint_steps",
    "rank",
    "alpha",
    "dropout",
    "learning_rate",
    "target_modules_profile",
    "max_length",
    "training_seed",
    "critical_parameter_loss",
    "minimum_ordinary_fraction",
    "generation",
    "absolute_minima",
    "autonomous_minima",
    "critical_family_minima",
    "tool_families",
    "ordinary_families",
    "paired_rules",
}
WORKFLOW_GROUP_COUNTS = {"file": 10, "format": 6, "search": 4}


def _exact_keys(value, expected, name):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"The fixed plan {name} has missing or unknown keys")


def _positive_integer(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(f"The fixed plan {name} must be a positive integer")


def _fixed_number(value, expected, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value != expected:
        raise ValueError(f"The fixed plan {name} differs from the reviewed V5 setting")


def _families(value, count, name):
    if (
        not isinstance(value, list)
        or len(value) != count
        or any(not isinstance(item, str) or not item for item in value)
        or len(set(value)) != count
    ):
        raise ValueError(f"The fixed plan {name} must have {count} unique family names")


def validate_behavioral_plan(plan: dict) -> dict:
    """Reject omitted gates and settings altered after the experiment was fixed."""
    _exact_keys(plan, PLAN_KEYS, "root")
    fixed_integers = {
        "schema_version": 1,
        "train_records": 1200,
        "dev_records": 200,
        "dev_workflows_records": 20,
        "maximum_steps": 600,
        "maximum_epochs": 2,
        "gradient_accumulation": 4,
        "rank": 16,
        "alpha": 32,
    }
    for name, expected in fixed_integers.items():
        _positive_integer(plan[name], name)
        if plan[name] != expected:
            raise ValueError(f"The fixed plan {name} differs from the reviewed V5 setting")
    for name, expected in (
        ("profile", "v5_general"),
        ("base_weights_sha256", BASE_SHA256),
        ("target_modules_profile", "attention_only"),
    ):
        if plan[name] != expected:
            raise ValueError(f"The fixed plan {name} differs from the reviewed V5 setting")
    for name, expected in (
        ("dropout", 0.05),
        ("learning_rate", 0.00002),
        ("minimum_ordinary_fraction", 0.4),
    ):
        _fixed_number(plan[name], expected, name)
    for name in ("max_length", "training_seed"):
        _positive_integer(plan[name], name)
    if plan["critical_parameter_loss"] is not True:
        raise ValueError("The fixed plan requires verified critical parameter loss")
    if (
        plan["checkpoint_steps"] != [300, 600]
        or any(type(step) is not int for step in plan["checkpoint_steps"])
        or plan["maximum_steps"] * plan["gradient_accumulation"]
        != plan["train_records"] * plan["maximum_epochs"]
    ):
        raise ValueError("The fixed plan must checkpoint both complete training epochs")
    for name in INPUT_HASH_KEYS:
        if not isinstance(plan[name], str) or not re.fullmatch(r"[0-9a-f]{64}", plan[name]):
            raise ValueError(f"The fixed plan {name} must pin its exact input hash")
    _families(plan["tool_families"], 60, "tool_families")
    _families(plan["ordinary_families"], 8, "ordinary_families")
    if set(plan["tool_families"]) & set(plan["ordinary_families"]):
        raise ValueError("The fixed plan ordinary and tool families overlap")
    minima = plan["critical_family_minima"]
    if (
        not isinstance(minima, dict)
        or len(minima) != 15
        or not set(minima) <= set(plan["tool_families"])
    ):
        raise ValueError("The fixed plan requires fifteen actual critical tool families")
    for name, value in minima.items():
        _fixed_number(value, 0.75, f"critical_family_minima.{name}")
    _exact_keys(
        plan["absolute_minima"],
        {"ordinary_overall", "ordinary_family", "tool_overall"},
        "absolute_minima",
    )
    for name, minimum in (
        ("ordinary_overall", 0.9),
        ("ordinary_family", 0.8),
        ("tool_overall", 0.8),
    ):
        _fixed_number(plan["absolute_minima"][name], minimum, f"absolute_minima.{name}")
    _exact_keys(plan["autonomous_minima"], {"overall", "group"}, "autonomous_minima")
    for name, minimum in (("overall", 0.8), ("group", 0.5)):
        _fixed_number(plan["autonomous_minima"][name], minimum, f"autonomous_minima.{name}")
    _exact_keys(plan["paired_rules"], PAIRED_RULES, "paired_rules")
    if any(value is not True for value in plan["paired_rules"].values()):
        raise ValueError("The fixed plan cannot disable a paired preservation rule")
    generation = plan["generation"]
    _exact_keys(
        generation,
        {
            "decoding",
            "max_new_tokens",
            "max_turns",
            "eos_tokens",
            "device",
            "dtype",
            "source_fp32_restored",
        },
        "generation",
    )
    for name, expected in (
        ("decoding", "greedy"),
        ("device", "cuda"),
        ("dtype", "torch.bfloat16"),
        ("eos_tokens", ["<|im_end|>", "<|endoftext|>"]),
    ):
        if generation[name] != expected:
            raise ValueError(f"The fixed plan generation.{name} is unsupported")
    if generation["source_fp32_restored"] is not True:
        raise ValueError("The fixed plan must preserve original FP32 norms and gates")
    for name in ("max_new_tokens", "max_turns"):
        _positive_integer(generation[name], f"generation.{name}")
    return plan


def read_behavioral_plan(path: Path) -> tuple[dict, str]:
    contents = path.read_bytes()
    plan = validate_behavioral_plan(json.loads(contents))
    return plan, hashlib.sha256(contents).hexdigest()


def validate_behavioral_plan_cli(plan: dict, args) -> None:
    validate_behavioral_plan(plan)
    fields = {
        "behavioral_profile": plan["profile"],
        "steps": plan["maximum_steps"],
        "gradient_accumulation": plan["gradient_accumulation"],
        "checkpoint_every": plan["checkpoint_steps"][0],
        "rank": plan["rank"],
        "learning_rate": plan["learning_rate"],
        "max_length": plan["max_length"],
        "seed": plan["training_seed"],
        "target_modules_profile": plan["target_modules_profile"],
        "minimum_ordinary_fraction": plan["minimum_ordinary_fraction"],
        "critical_parameter_loss": True,
        "behavioral_max_new_tokens": plan["generation"]["max_new_tokens"],
        "behavioral_max_turns": plan["generation"]["max_turns"],
        "device": plan["generation"]["device"],
        "prompt_source": "runtime",
        "eval_limit": 0,
        "early_stopping_patience": 0,
    }
    for name, value in fields.items():
        actual = getattr(args, name, None)
        if type(actual) is not type(value) or actual != value:
            raise ValueError(f"CLI {name} differs from the fixed behavioral plan")


def validate_behavioral_plan_hashes(plan: dict, actual: dict) -> None:
    _exact_keys(actual, INPUT_HASH_KEYS, "input hashes")
    for name in INPUT_HASH_KEYS:
        if actual[name] != plan[name]:
            raise ValueError(f"Input {name} hash differs from the fixed behavioral plan")


def validate_behavioral_plan_records(
    plan: dict, train: list[dict], dev: list[dict], workflows: list[dict]
) -> None:
    tool = set(plan["tool_families"])
    ordinary = set(plan["ordinary_families"])
    for split, rows in (("train", train), ("dev", dev)):
        if len(rows) != plan[f"{split}_records"]:
            raise ValueError(f"The complete {split} count differs from the fixed plan")
        counts = Counter()
        ordinary_count = 0
        for row in rows:
            metadata = row.get("metadata", {})
            family = metadata.get("family")
            retained = metadata.get("ordinary_retention")
            if (
                type(retained) is not bool
                or family not in tool | ordinary
                or retained != (family in ordinary)
            ):
                raise ValueError("Record families differ from the fixed plan classifications")
            counts[family] += 1
            ordinary_count += retained
        if set(counts) != tool | ordinary or ordinary_count != round(len(rows) * 0.4):
            raise ValueError("The fixed plan requires every family and exact ordinary coverage")
        if split == "dev" and any(
            counts[family] != (10 if family in ordinary else 2) for family in counts
        ):
            raise ValueError("Every fixed dev family requires its complete reviewed count")
    if len(workflows) != plan["dev_workflows_records"]:
        raise ValueError("The complete workflow count differs from the fixed plan")
    ids = [row.get("id") for row in workflows]
    if any(not isinstance(identifier, str) or not identifier for identifier in ids) or len(
        set(ids)
    ) != len(ids):
        raise ValueError("Every fixed dev workflow requires a unique nonempty ID")
    if any(row.get("split") != "dev" for row in workflows):
        raise ValueError("Only original dev workflows may enter checkpoint selection")
    if Counter(row.get("group") for row in workflows) != WORKFLOW_GROUP_COUNTS:
        raise ValueError("Dev workflow groups differ from the fixed file/format/search counts")


def selection_options(plan: dict) -> dict:
    return {
        "gradient_accumulation": plan["gradient_accumulation"],
        "minimum_ordinary_fraction": plan["minimum_ordinary_fraction"],
        "maximum_steps": plan["maximum_steps"],
        "maximum_epochs": plan["maximum_epochs"],
        "critical_family_minima": plan["critical_family_minima"],
        "minimum_ordinary_overall_rate": plan["absolute_minima"]["ordinary_overall"],
        "minimum_ordinary_family_rate": plan["absolute_minima"]["ordinary_family"],
        "minimum_tool_overall_rate": plan["absolute_minima"]["tool_overall"],
        "minimum_autonomous_overall_rate": plan["autonomous_minima"]["overall"],
        "minimum_autonomous_group_rate": plan["autonomous_minima"]["group"],
    }
