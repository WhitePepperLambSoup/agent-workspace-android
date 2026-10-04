"""Choose adapters by paired dev behavior, with explicit preservation gates.

This helper consumes semantic results from an independent scorer. It never
loads targets, fresh final data, or teacher-forced loss. Unscored ordinary
semantics cannot silently become passing preservation evidence.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from fractions import Fraction


def _indexed_report(report: dict) -> dict[str, dict]:
    if report.get("split") != "dev":
        raise ValueError("Behavioral checkpoint selection requires dev data only")
    if not re.fullmatch(r"[0-9a-f]{64}", report.get("dataset_sha256", "")):
        raise ValueError("Dev dataset requires its frozen SHA-256")
    if not report.get("generation_config"):
        raise ValueError("Dev generations require an explicit paired configuration")
    identity = report.get("model_identity", {}).get("base_weight_sha256")
    if (
        not isinstance(identity, dict)
        or not identity
        or any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in identity.values())
    ):
        raise ValueError("Dev predictions require their pinned original base weight identity")
    indexed = {}
    for sample in report.get("samples", []):
        identifier = sample.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in indexed:
            raise ValueError("Every dev ID must occur exactly once")
        if not isinstance(sample.get("family"), str) or not sample["family"]:
            raise ValueError("Every dev sample requires its fixed family")
        for key in ("ordinary_retention", "protocol_valid", "prediction_generation_success"):
            if type(sample.get(key)) is not bool:
                raise ValueError(f"Dev sample requires Boolean {key}")
        ordinary = sample["ordinary_retention"]
        key = "ordinary_correct" if ordinary else "behavior_success"
        if type(sample.get(key)) is not bool:
            raise ValueError(f"Dev behavior is unscored for {identifier}: {key}")
        if ordinary and sample.get("ordinary_semantics_supported") is not True:
            raise ValueError(f"Ordinary semantics are unscored for {identifier}")
        if not re.fullmatch(r"[0-9a-f]{64}", sample.get("visible_prompt_sha256", "")):
            raise ValueError("Dev predictions require their visible prompt SHA-256")
        if (not sample["prediction_generation_success"] or not sample["protocol_valid"]) and sample[
            key
        ]:
            raise ValueError(
                "A failed generation or invalid protocol cannot claim behavior success"
            )
        if sample.get("output_truncated", False) and sample[key]:
            raise ValueError("A truncated generation cannot claim behavior success")
        indexed[identifier] = sample
    if not indexed or not any(row["ordinary_retention"] for row in indexed.values()):
        raise ValueError("Behavioral dev requires ordinary preservation records")
    if not any(not row["ordinary_retention"] for row in indexed.values()):
        raise ValueError("Behavioral dev requires tool behavior records")
    if len({row["visible_prompt_sha256"] for row in indexed.values()}) != len(indexed):
        raise ValueError("Behavioral dev contains repeated canonical visible input")
    return indexed


def _summary(samples: dict[str, dict]) -> dict:
    groups: dict[str, dict] = {}
    ordinary = {"total": 0, "correct": 0}
    tool = {"total": 0, "correct": 0}
    for sample in samples.values():
        is_ordinary = sample["ordinary_retention"]
        correct = sample["ordinary_correct"] if is_ordinary else sample["behavior_success"]
        target = ordinary if is_ordinary else tool
        target["total"] += 1
        target["correct"] += correct
        group = groups.setdefault(
            sample["family"], {"ordinary_retention": is_ordinary, "total": 0, "correct": 0}
        )
        if group["ordinary_retention"] != is_ordinary:
            raise ValueError("A dev family mixes ordinary and tool semantics")
        group["total"] += 1
        group["correct"] += correct
    for counts in (ordinary, tool, *groups.values()):
        counts["rate"] = counts["correct"] / counts["total"]
    return {
        "total": len(samples),
        "ordinary": ordinary,
        "tool": tool,
        "families": dict(sorted(groups.items())),
        "protocol_correct": sum(row["protocol_valid"] for row in samples.values()),
        "generation_failures": sum(
            not row["prediction_generation_success"] for row in samples.values()
        ),
        "truncated_generations": sum(
            row.get("output_truncated", False) for row in samples.values()
        ),
        "tool_macro_rate": sum(
            row["rate"] for row in groups.values() if not row["ordinary_retention"]
        )
        / sum(not row["ordinary_retention"] for row in groups.values()),
    }


def summarize_paired_behavior(baseline: dict, candidate: dict) -> dict:
    """Keep failures in the complete, identical dev denominator."""
    base = _indexed_report(baseline)
    trained = _indexed_report(candidate)
    for key in ("dataset_sha256", "generation_config"):
        if baseline[key] != candidate[key]:
            raise ValueError(f"Paired dev {key} differs")
    if (
        baseline["model_identity"]["base_weight_sha256"]
        != candidate["model_identity"]["base_weight_sha256"]
    ):
        raise ValueError("Paired dev uses different original base weight identities")
    if set(base) != set(trained):
        raise ValueError("Paired dev IDs differ; failures must not be dropped")
    for identifier in base:
        for key in ("family", "ordinary_retention", "group", "visible_prompt_sha256"):
            if base[identifier].get(key) != trained[identifier].get(key):
                raise ValueError(f"Paired dev classification/input differs: {identifier}/{key}")
    return {"baseline": _summary(base), "candidate": _summary(trained)}


def _indexed_workflow_report(report: dict, *, split: str) -> dict[str, dict]:
    if report.get("split") != split:
        raise ValueError(f"Autonomous evaluation requires original {split} workflows")
    if not re.fullmatch(r"[0-9a-f]{64}", report.get("dataset_sha256", "")):
        raise ValueError("Autonomous dev requires its frozen dataset hash")
    if not report.get("generation_config"):
        raise ValueError("Autonomous dev requires an explicit paired generation configuration")
    identity = report.get("model_identity", {})
    if identity.get("generation_source") != "model_free_generation":
        raise ValueError("Scripted controls cannot claim autonomous model performance")
    weights = identity.get("base_weight_sha256")
    if (
        not isinstance(weights, dict)
        or not weights
        or any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in weights.values())
    ):
        raise ValueError("Autonomous dev must pin the original base weight identity")
    indexed = {}
    for sample in report.get("samples", []):
        identifier = sample.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in indexed:
            raise ValueError("Every autonomous dev ID must occur exactly once")
        for name in (
            "behavior_success",
            "autonomous_success",
            "prediction_generation_success",
            "output_truncated",
        ):
            if type(sample.get(name)) is not bool:
                raise ValueError(f"Autonomous dev requires explicitly scored Boolean {name}")
        if sample["behavior_success"] != sample["autonomous_success"]:
            raise ValueError("Autonomous success differs from actual behavioral success")
        if (not sample["prediction_generation_success"] or sample["output_truncated"]) and sample[
            "behavior_success"
        ]:
            raise ValueError("Failed or truncated autonomous generation cannot claim success")
        if not re.fullmatch(r"[0-9a-f]{64}", sample.get("initial_visible_prompt_sha256", "")):
            raise ValueError("Every autonomous case must pin its actual initial visible input")
        indexed[identifier] = sample
    if Counter(row.get("group") for row in indexed.values()) != {
        "file": 10,
        "format": 6,
        "search": 4,
    }:
        raise ValueError("Autonomous dev must preserve all twenty fixed workflow cases and groups")
    if len({row["initial_visible_prompt_sha256"] for row in indexed.values()}) != len(indexed):
        raise ValueError("Autonomous dev repeats a canonical initial visible input")
    return indexed


def _indexed_autonomous_report(report: dict) -> dict[str, dict]:
    return _indexed_workflow_report(report, split="dev")


def validate_final_autonomous_report(report: dict) -> dict:
    """Final scores have no checkpoint-selection entry point."""
    return _autonomous_summary(_indexed_workflow_report(report, split="final"))


def _autonomous_summary(samples: dict[str, dict]) -> dict:
    groups = {}
    for sample in samples.values():
        group = groups.setdefault(sample["group"], {"total": 0, "correct": 0})
        group["total"] += 1
        group["correct"] += sample["behavior_success"]
    for counts in groups.values():
        counts["rate"] = counts["correct"] / counts["total"]
    correct = sum(row["behavior_success"] for row in samples.values())
    return {
        "total": len(samples),
        "correct": correct,
        "rate": correct / len(samples),
        "groups": dict(sorted(groups.items())),
        "generation_failures": sum(
            not row["prediction_generation_success"] for row in samples.values()
        ),
        "truncated_generations": sum(row["output_truncated"] for row in samples.values()),
    }


def summarize_paired_autonomous(baseline: dict, candidate: dict) -> dict:
    base = _indexed_autonomous_report(baseline)
    trained = _indexed_autonomous_report(candidate)
    for key in ("dataset_sha256", "generation_config"):
        if baseline[key] != candidate[key]:
            raise ValueError(f"Paired autonomous dev {key} differs")
    if (
        baseline["model_identity"]["base_weight_sha256"]
        != candidate["model_identity"]["base_weight_sha256"]
    ):
        raise ValueError("Paired autonomous dev uses different original base weights")
    if set(base) != set(trained):
        raise ValueError("Paired autonomous dev IDs differ")
    for identifier in base:
        for key in ("group", "initial_visible_prompt_sha256"):
            if base[identifier][key] != trained[identifier][key]:
                raise ValueError(
                    f"Paired autonomous dev classification/input differs: {identifier}"
                )
    return {"baseline": _autonomous_summary(base), "candidate": _autonomous_summary(trained)}


def _sampling_gate(
    checkpoint: dict,
    *,
    gradient_accumulation: int,
    minimum_ordinary_fraction: float,
    maximum_epochs: int,
    maximum_steps: int,
) -> list[str]:
    step = checkpoint["step"]
    if type(step) is not int or not 1 <= step <= maximum_steps:
        raise ValueError("Candidate exceeds the fixed optimizer-step budget")
    sampling = checkpoint["sampling"]
    available = sampling["available_record_ids"]
    ordinary = sampling["available_ordinary_record_ids"]
    consumed = sampling["sampled_record_ids"]
    if not available or len(set(available)) != len(available):
        raise ValueError("Training IDs must be a unique, complete frozen set")
    if len(set(ordinary)) != len(ordinary) or not set(ordinary) <= set(available):
        raise ValueError("Ordinary IDs must belong to the frozen training set")
    if not set(consumed) <= set(available) or len(consumed) != step * gradient_accumulation:
        raise ValueError("Candidate sampling does not match its actual optimizer prefix")
    if len(consumed) > maximum_epochs * len(available):
        raise ValueError("Candidate exceeds the fixed complete-epoch budget")
    ordinary_set = set(ordinary)
    ordinary_count = sum(identifier in ordinary_set for identifier in consumed)
    if sampling["ordinary_examples_consumed"] != ordinary_count:
        raise ValueError("Ordinary sampling count differs from the actual consumed IDs")
    reasons = []
    counts = Counter(consumed)
    if not set(available) <= set(consumed):
        reasons.append("selected prefix has not seen one complete epoch")
    if any(count > maximum_epochs for count in counts.values()):
        raise ValueError("Candidate sampling repeats examples beyond its fixed epoch budget")
    if ordinary_count / len(consumed) < minimum_ordinary_fraction:
        reasons.append("selected prefix ordinary fraction is below the preservation floor")
    seen_ordinary = 0
    exact_fraction = Fraction(str(minimum_ordinary_fraction))
    for count, identifier in enumerate(consumed, 1):
        seen_ordinary += identifier in ordinary_set
        if seen_ordinary < math.ceil(count * exact_fraction):
            reasons.append(
                "an actual consumed prefix ordinary fraction is below the preservation floor"
            )
            break
    return reasons


def select_behavioral_checkpoint(
    baseline: dict,
    checkpoints: list[dict],
    *,
    gradient_accumulation: int,
    minimum_ordinary_fraction: float = 0.4,
    maximum_epochs: int = 2,
    maximum_steps: int = 300,
    critical_family_minima: dict[str, float] | None = None,
    minimum_ordinary_overall_rate: float = 0.0,
    minimum_ordinary_family_rate: float = 0.0,
    minimum_tool_overall_rate: float = 0.0,
    autonomous_baseline: dict | None = None,
    minimum_autonomous_overall_rate: float = 0.0,
    minimum_autonomous_group_rate: float = 0.0,
) -> dict:
    """Refuse all adapters when preservation or actual tool behavior regresses."""
    if gradient_accumulation < 1 or maximum_epochs < 1 or maximum_steps < 1:
        raise ValueError("Selection budgets must be positive")
    if not math.isfinite(minimum_ordinary_fraction) or not 0 < minimum_ordinary_fraction <= 1:
        raise ValueError("Ordinary fraction must be in (0, 1]")
    minima = critical_family_minima or {}
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in minima.values()):
        raise ValueError("Critical behavior minima must be rates in [0, 1]")
    absolute_minima = {
        "ordinary_overall": minimum_ordinary_overall_rate,
        "ordinary_family": minimum_ordinary_family_rate,
        "tool_overall": minimum_tool_overall_rate,
    }
    autonomous_minima = {
        "overall": minimum_autonomous_overall_rate,
        "group": minimum_autonomous_group_rate,
    }
    if any(
        type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1
        for value in (*absolute_minima.values(), *autonomous_minima.values())
    ):
        raise ValueError("Absolute behavior minima must be finite rates in [0, 1]")
    if any(autonomous_minima.values()) and autonomous_baseline is None:
        raise ValueError("Fixed autonomous gates require the complete paired autonomous baseline")
    autonomous_summary = (
        _autonomous_summary(_indexed_autonomous_report(autonomous_baseline))
        if autonomous_baseline is not None
        else None
    )
    autonomous_gate_counts = None
    if autonomous_summary:
        autonomous_gate_counts = {
            "overall": {
                "total": autonomous_summary["total"],
                "required_correct": math.ceil(
                    minimum_autonomous_overall_rate * autonomous_summary["total"]
                ),
            },
            "groups": {
                name: {
                    "total": counts["total"],
                    "required_correct": math.ceil(minimum_autonomous_group_rate * counts["total"]),
                }
                for name, counts in autonomous_summary["groups"].items()
            },
        }
    baseline_summary = _summary(_indexed_report(baseline))
    gate_counts = {}
    for family, minimum in minima.items():
        if family not in baseline_summary["families"]:
            raise ValueError(
                f"Critical behavior family is absent from the fixed baseline: {family}"
            )
        if baseline_summary["families"][family]["ordinary_retention"]:
            raise ValueError(
                f"A critical tool behavior gate refers to ordinary semantics: {family}"
            )
        count = baseline_summary["families"][family]["total"]
        gate_counts[family] = {
            "minimum_rate": minimum,
            "total": count,
            "required_correct": math.ceil(minimum * count),
        }
    decisions = []
    seen_steps = set()
    eligible = []
    for checkpoint in checkpoints:
        step = checkpoint["step"]
        if step in seen_steps:
            raise ValueError("Every candidate optimizer step must be unique")
        seen_steps.add(step)
        reasons = _sampling_gate(
            checkpoint,
            gradient_accumulation=gradient_accumulation,
            minimum_ordinary_fraction=minimum_ordinary_fraction,
            maximum_epochs=maximum_epochs,
            maximum_steps=maximum_steps,
        )
        paired = summarize_paired_behavior(baseline, checkpoint["report"])
        base, trained = paired["baseline"], paired["candidate"]
        if trained["ordinary"]["rate"] < minimum_ordinary_overall_rate:
            reasons.append("ordinary overall behavior is below its fixed absolute gate")
        if trained["tool"]["rate"] < minimum_tool_overall_rate:
            reasons.append("tool overall behavior is below its fixed absolute gate")
        for family, counts in base["families"].items():
            if trained["families"][family]["correct"] < counts["correct"]:
                reasons.append(f"behavior preservation regressed in {family}")
            if (
                counts["ordinary_retention"]
                and trained["families"][family]["rate"] < minimum_ordinary_family_rate
            ):
                reasons.append(f"ordinary behavior is below its fixed absolute gate in {family}")
        for family, minimum in minima.items():
            if family not in trained["families"]:
                raise ValueError(f"Critical behavior family is absent: {family}")
            if trained["families"][family]["rate"] < minimum:
                reasons.append(f"critical tool behavior is below its fixed gate in {family}")
        if trained["protocol_correct"] < base["protocol_correct"]:
            reasons.append("protocol validity regressed against the paired base")
        if trained["generation_failures"] > base["generation_failures"]:
            reasons.append("generation failures increased against the paired base")
        if trained["truncated_generations"] > base["truncated_generations"]:
            reasons.append("truncated generations increased against the paired base")
        if trained["tool"]["correct"] <= base["tool"]["correct"]:
            reasons.append("tool behavior did not strictly improve against the paired base")
        autonomous = {}
        if autonomous_baseline is not None:
            if not isinstance(checkpoint.get("autonomous_report"), dict):
                raise ValueError("Every candidate requires its complete autonomous dev report")
            values = summarize_paired_autonomous(
                autonomous_baseline, checkpoint["autonomous_report"]
            )
            before_autonomous, after_autonomous = values["baseline"], values["candidate"]
            if after_autonomous["rate"] < minimum_autonomous_overall_rate:
                reasons.append("autonomous overall behavior is below its fixed absolute gate")
            if after_autonomous["correct"] < before_autonomous["correct"]:
                reasons.append("autonomous total behavior regressed against the paired base")
            for group, counts in before_autonomous["groups"].items():
                measured = after_autonomous["groups"][group]
                if measured["rate"] < minimum_autonomous_group_rate:
                    reasons.append(f"autonomous {group} behavior is below its fixed absolute gate")
                if measured["correct"] < counts["correct"]:
                    reasons.append(f"autonomous {group} behavior regressed against the paired base")
            if after_autonomous["generation_failures"] > before_autonomous["generation_failures"]:
                reasons.append("autonomous generation failures increased against the paired base")
            if (
                after_autonomous["truncated_generations"]
                > before_autonomous["truncated_generations"]
            ):
                reasons.append("autonomous truncated generations increased against the paired base")
            autonomous = {
                "autonomous_baseline": before_autonomous,
                "autonomous_candidate": after_autonomous,
            }
        decision = {
            "step": step,
            "eligible": not reasons,
            "rejection_reasons": reasons,
            **paired,
            **autonomous,
        }
        decisions.append(decision)
        if not reasons:
            score = (
                trained["tool"]["correct"],
                trained["tool_macro_rate"],
                trained["protocol_correct"],
                -step,
            )
            eligible.append((score, decision))
    chosen = max(eligible, key=lambda item: item[0])[1] if eligible else None
    return {
        "accepted": chosen is not None,
        "selected_step": chosen["step"] if chosen else None,
        "selected_score": chosen["candidate"] if chosen else None,
        "selection_metric": "paired_dev_behavior_success",
        "teacher_forced_loss_used_for_selection": False,
        "fresh_final_used_for_selection": False,
        "minimum_ordinary_fraction": minimum_ordinary_fraction,
        "critical_family_minima": minima,
        "critical_family_gate_counts": gate_counts,
        "absolute_minima": absolute_minima,
        "autonomous_minima": autonomous_minima,
        "autonomous_gate_counts": autonomous_gate_counts,
        "gradient_accumulation": gradient_accumulation,
        "maximum_epochs": maximum_epochs,
        "maximum_steps": maximum_steps,
        "candidates": decisions,
    }
