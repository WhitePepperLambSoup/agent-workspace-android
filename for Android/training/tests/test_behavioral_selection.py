"""Behavior gates keep all paired dev denominators and never select by loss."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


def helper():
    path = Path(__file__).resolve().parents[1] / "behavioral_dev_selection.py"
    assert path.is_file(), "behavioral dev selection must be implemented"
    spec = importlib.util.spec_from_file_location("agent_behavioral_selection", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report(*, math=True, conversation=True, copy_success=False, edit_success=False):
    values = [
        ("math", "ordinary_arithmetic", True, math),
        ("conversation", "ordinary_conversation", True, conversation),
        ("copy", "copy_observed_write", False, copy_success),
        ("edit", "edit_observed_write", False, edit_success),
    ]
    return {
        "split": "dev",
        "dataset_sha256": "a" * 64,
        "generation_config": {"decoding": "greedy", "max_new_tokens": 512},
        "model_identity": {"base_weight_sha256": {"weights": "b" * 64}},
        "samples": [
            {
                "id": name,
                "family": family,
                "ordinary_retention": ordinary,
                "ordinary_semantics_supported": ordinary,
                "visible_prompt_sha256": str(index) * 64,
                "protocol_valid": True,
                "prediction_generation_success": True,
                "behavior_success": None if ordinary else success,
                "ordinary_correct": success if ordinary else None,
            }
            for index, (name, family, ordinary, success) in enumerate(values)
        ],
    }


def checkpoint(step, metrics, ids=None):
    ids = ids or [f"train-{(i // 2) % 10 + (10 if i % 2 else 0)}" for i in range(step * 4)]
    return {
        "step": step,
        "report": metrics,
        "sampling": {
            "available_record_ids": [f"train-{i}" for i in range(20)],
            "available_ordinary_record_ids": [f"train-{i}" for i in range(10)],
            "sampled_record_ids": ids,
            "ordinary_examples_consumed": sum(
                int(identifier.split("-")[1]) < 10 for identifier in ids
            ),
        },
    }


def select(base, candidates):
    return helper().select_behavioral_checkpoint(
        base, candidates, gradient_accumulation=4, minimum_ordinary_fraction=0.4
    )


def test_lower_loss_cannot_select_a_model_with_arithmetic_regression():
    base = report()
    bad = checkpoint(5, report(math=False, copy_success=True, edit_success=True))
    bad["macro_loss"] = 0.01
    good = checkpoint(6, report(copy_success=True))
    good["macro_loss"] = 9.0
    selection = select(base, [bad, good])
    assert selection["accepted"] is True
    assert selection["selected_step"] == 6
    assert "ordinary_arithmetic" in selection["candidates"][0]["rejection_reasons"][0]
    assert selection["selection_metric"] == "paired_dev_behavior_success"


def test_no_passing_candidate_refuses_recommendation_instead_of_selecting_lowest_loss():
    bad = checkpoint(5, report(conversation=False, copy_success=True))
    selection = select(report(), [bad])
    assert selection["accepted"] is False
    assert selection["selected_step"] is None
    assert selection["selected_score"] is None


def test_selected_prefix_must_cover_the_complete_training_set_and_ordinary_floor():
    short = checkpoint(4, report(copy_success=True))
    repeated = checkpoint(5, report(copy_success=True), [f"train-{i % 10}" for i in range(20)])
    low_retention = checkpoint(5, report(copy_success=True))
    low_retention["sampling"]["ordinary_examples_consumed"] = 7
    low_retention["sampling"]["available_ordinary_record_ids"] = [f"train-{i}" for i in range(7)]
    selections = [select(report(), [item]) for item in (short, repeated, low_retention)]
    assert all(selection["selected_step"] is None for selection in selections)
    reasons = [selection["candidates"][0]["rejection_reasons"] for selection in selections]
    assert any("complete epoch" in reason for reason in reasons[0])
    assert any("complete epoch" in reason for reason in reasons[1])
    assert any("ordinary fraction" in reason for reason in reasons[2])


def test_dev_pairing_rejects_missing_duplicated_reclassified_or_final_records():
    module = helper()
    base = report()
    changes = []
    missing = report(copy_success=True)
    missing["samples"].pop()
    changes.append(missing)
    duplicated = report(copy_success=True)
    duplicated["samples"].append(copy.deepcopy(duplicated["samples"][0]))
    changes.append(duplicated)
    reclassified = report(copy_success=True)
    reclassified["samples"][0]["family"] = "different-math"
    changes.append(reclassified)
    final = report(copy_success=True)
    final["split"] = "eval"
    changes.append(final)
    config = report(copy_success=True)
    config["generation_config"]["max_new_tokens"] = 1024
    changes.append(config)
    prompt = report(copy_success=True)
    prompt["samples"][0]["visible_prompt_sha256"] = "b" * 64
    changes.append(prompt)
    repeated_input = report(copy_success=True)
    repeated_input["samples"][1]["visible_prompt_sha256"] = repeated_input["samples"][0][
        "visible_prompt_sha256"
    ]
    changes.append(repeated_input)
    wrong_base = report(copy_success=True)
    wrong_base["model_identity"]["base_weight_sha256"] = {"weights": "c" * 64}
    changes.append(wrong_base)
    for changed in changes:
        with pytest.raises(ValueError):
            module.summarize_paired_behavior(base, changed)


def test_failed_generation_stays_in_denominator_and_unscored_behavior_is_rejected():
    trained = report(copy_success=True, edit_success=True)
    trained["samples"][2].update(
        prediction_generation_success=False, protocol_valid=False, behavior_success=False
    )
    paired = helper().summarize_paired_behavior(report(), trained)
    assert paired["candidate"]["tool"]["total"] == 2
    assert paired["candidate"]["tool"]["correct"] == 1
    assert paired["candidate"]["generation_failures"] == 1
    trained["samples"][2]["behavior_success"] = None
    with pytest.raises(ValueError, match="unscored"):
        helper().summarize_paired_behavior(report(), trained)


def test_false_failure_claims_and_budget_overruns_are_rejected():
    contradictory = report(copy_success=True)
    contradictory["samples"][2]["prediction_generation_success"] = False
    with pytest.raises(ValueError, match="failed generation"):
        select(report(), [checkpoint(5, contradictory)])
    with pytest.raises(ValueError, match="budget"):
        select(report(), [checkpoint(11, report(copy_success=True))])


def test_ties_choose_earlier_complete_epoch_and_tool_family_regression_is_blocked():
    base = report(copy_success=True)
    regression = checkpoint(5, report(edit_success=True))
    first = checkpoint(6, report(copy_success=True, edit_success=True))
    later = checkpoint(7, report(copy_success=True, edit_success=True))
    selection = select(base, [later, regression, first])
    assert selection["selected_step"] == 6
    assert any(
        "copy_observed_write" in reason
        for reason in selection["candidates"][1]["rejection_reasons"]
    )


def test_keyword_or_unscored_conversation_cannot_claim_preservation():
    metrics = report(copy_success=True)
    metrics["samples"][1]["ordinary_semantics_supported"] = False
    with pytest.raises(ValueError, match="unscored"):
        select(report(), [checkpoint(5, metrics)])


def test_truncated_answer_cannot_get_substring_credit():
    metrics = report(copy_success=True)
    metrics["samples"][0]["output_truncated"] = True
    with pytest.raises(ValueError, match="truncated"):
        select(report(), [checkpoint(5, metrics)])


def test_write_gate_is_fixed_before_generations_and_two_case_family_needs_two_successes():
    base = report()
    extra = {**base["samples"][2], "id": "copy-2", "visible_prompt_sha256": "4" * 64}
    base["samples"].append(extra)
    partial = copy.deepcopy(base)
    partial["samples"][2]["behavior_success"] = True
    complete = copy.deepcopy(partial)
    complete["samples"][4]["behavior_success"] = True
    selection = helper().select_behavioral_checkpoint(
        base,
        [checkpoint(5, partial), checkpoint(6, complete)],
        gradient_accumulation=4,
        critical_family_minima={"copy_observed_write": 0.75},
    )
    assert selection["selected_step"] == 6
    gate = selection["critical_family_gate_counts"]["copy_observed_write"]
    assert gate == {"minimum_rate": 0.75, "total": 2, "required_correct": 2}
    assert selection["maximum_epochs"] == 2
    assert selection["maximum_steps"] == 300


def test_canonical_dev_input_repetition_is_rejected_even_if_both_reports_repeat_it():
    repeated = report()
    repeated["samples"][1]["visible_prompt_sha256"] = repeated["samples"][0][
        "visible_prompt_sha256"
    ]
    with pytest.raises(ValueError, match="input"):
        helper().summarize_paired_behavior(repeated, repeated)


def test_absolute_ordinary_and_tool_gates_reject_improvement_over_a_zero_base():
    base = report(math=False, conversation=False)
    improved = checkpoint(5, report(math=False, conversation=True, copy_success=True))
    decision = helper().select_behavioral_checkpoint(
        base,
        [improved],
        gradient_accumulation=4,
        minimum_ordinary_overall_rate=0.9,
        minimum_ordinary_family_rate=0.8,
        minimum_tool_overall_rate=0.8,
    )
    assert decision["accepted"] is False
    reasons = decision["candidates"][0]["rejection_reasons"]
    assert any("ordinary overall" in reason for reason in reasons)
    assert any("ordinary_arithmetic" in reason and "absolute" in reason for reason in reasons)
    assert any("tool overall" in reason for reason in reasons)
    good = checkpoint(5, report(copy_success=True, edit_success=True))
    assert (
        helper().select_behavioral_checkpoint(
            base,
            [good],
            gradient_accumulation=4,
            minimum_ordinary_overall_rate=0.9,
            minimum_ordinary_family_rate=0.8,
            minimum_tool_overall_rate=0.8,
        )["accepted"]
        is True
    )


def autonomous_report(*, successes=None):
    successes = set() if successes is None else set(successes)
    cases = [
        (group, index)
        for group, count in (("file", 10), ("format", 6), ("search", 4))
        for index in range(count)
    ]
    return {
        "split": "dev",
        "dataset_sha256": "c" * 64,
        "generation_config": {"decoding": "greedy", "max_new_tokens": 1024, "max_turns": 16},
        "model_identity": {
            "base_weight_sha256": {"weights": "b" * 64},
            "generation_source": "model_free_generation",
        },
        "samples": [
            {
                "id": f"{group}-{index}",
                "group": group,
                "initial_visible_prompt_sha256": f"{position:064x}",
                "behavior_success": (group, index) in successes,
                "autonomous_success": (group, index) in successes,
                "prediction_generation_success": True,
                "output_truncated": False,
            }
            for position, (group, index) in enumerate(cases)
        ],
    }


def autonomous_select(base, candidate):
    item = checkpoint(5, report(copy_success=True, edit_success=True))
    item["autonomous_report"] = candidate
    return helper().select_behavioral_checkpoint(
        report(),
        [item],
        gradient_accumulation=4,
        autonomous_baseline=base,
        minimum_autonomous_overall_rate=0.8,
        minimum_autonomous_group_rate=0.5,
    )


def test_stage_success_does_not_hide_a_failed_autonomous_search_group():
    base = autonomous_report()
    files_and_formats = {
        (group, index) for group, count in (("file", 10), ("format", 6)) for index in range(count)
    }
    rejected = autonomous_select(base, autonomous_report(successes=files_and_formats))
    assert rejected["accepted"] is False
    assert any("search" in reason for reason in rejected["candidates"][0]["rejection_reasons"])
    passing = files_and_formats - {("file", 0), ("file", 1)} | {("search", 0), ("search", 1)}
    accepted = autonomous_select(base, autonomous_report(successes=passing))
    assert accepted["accepted"] is True
    assert accepted["candidates"][0]["autonomous_candidate"]["correct"] == 16
    assert accepted["autonomous_gate_counts"] == {
        "overall": {"total": 20, "required_correct": 16},
        "groups": {
            "file": {"total": 10, "required_correct": 5},
            "format": {"total": 6, "required_correct": 3},
            "search": {"total": 4, "required_correct": 2},
        },
    }


def test_autonomous_preserves_base_groups_without_requiring_improvement_over_a_perfect_base():
    all_cases = {
        (group, index)
        for group, count in (("file", 10), ("format", 6), ("search", 4))
        for index in range(count)
    }
    perfect = autonomous_report(successes=all_cases)
    assert autonomous_select(perfect, perfect)["accepted"] is True
    regressed = autonomous_report(successes=all_cases - {("search", 0)})
    decision = autonomous_select(perfect, regressed)
    assert decision["accepted"] is False
    assert any("regressed" in reason for reason in decision["candidates"][0]["rejection_reasons"])


def test_autonomous_rejects_partial_final_or_scripted_outputs_and_changed_initial_input():
    base = autonomous_report()
    variants = []
    partial = copy.deepcopy(base)
    partial["samples"].pop()
    variants.append(partial)
    final = copy.deepcopy(base)
    final["split"] = "final"
    variants.append(final)
    scripted = copy.deepcopy(base)
    scripted["model_identity"]["generation_source"] = "synthetic_control"
    variants.append(scripted)
    changed_prompt = copy.deepcopy(base)
    changed_prompt["samples"][0]["initial_visible_prompt_sha256"] = "f" * 64
    variants.append(changed_prompt)
    for changed in variants:
        with pytest.raises(ValueError):
            autonomous_select(base, changed)
    item = checkpoint(5, report(copy_success=True, edit_success=True))
    with pytest.raises(ValueError, match="autonomous"):
        helper().select_behavioral_checkpoint(
            report(),
            [item],
            gradient_accumulation=4,
            minimum_autonomous_overall_rate=0.8,
            minimum_autonomous_group_rate=0.5,
        )


def test_new_six_hundred_step_budget_consumes_two_complete_epochs_with_every_prefix_preserved():
    epoch = []
    for index in range(240):
        epoch.extend(
            [
                f"ordinary-{2 * index}",
                f"tool-{3 * index}",
                f"ordinary-{2 * index + 1}",
                f"tool-{3 * index + 1}",
                f"tool-{3 * index + 2}",
            ]
        )
    candidate = {
        "step": 600,
        "report": report(copy_success=True, edit_success=True),
        "sampling": {
            "available_record_ids": epoch,
            "available_ordinary_record_ids": [
                identifier for identifier in epoch if identifier.startswith("ordinary-")
            ],
            "sampled_record_ids": epoch * 2,
            "ordinary_examples_consumed": 960,
        },
    }
    selected = helper().select_behavioral_checkpoint(
        report(),
        [candidate],
        gradient_accumulation=4,
        maximum_steps=600,
        maximum_epochs=2,
        minimum_ordinary_fraction=0.4,
    )
    assert selected["selected_step"] == 600
    assert selected["maximum_steps"] == 600


def test_adequate_final_ordinary_fraction_cannot_hide_an_early_consumed_prefix_violation():
    ids = [f"train-{i}" for i in range(10, 20)] + [f"train-{i}" for i in range(10)]
    bad = checkpoint(5, report(copy_success=True, edit_success=True), ids)
    result = select(report(), [bad])
    assert result["accepted"] is False
    assert any(
        "consumed prefix" in reason for reason in result["candidates"][0]["rejection_reasons"]
    )


def test_final_workflow_summary_cannot_enter_checkpoint_selection():
    final = autonomous_report(successes={("file", 0)})
    final["split"] = "final"
    summary = helper().validate_final_autonomous_report(final)
    assert summary["total"] == 20 and summary["correct"] == 1
    with pytest.raises(ValueError, match="original dev"):
        autonomous_select(autonomous_report(), final)
    with pytest.raises(ValueError, match="original final"):
        helper().validate_final_autonomous_report(autonomous_report())
