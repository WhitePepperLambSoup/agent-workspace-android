"""Require actual visible-input generation for each complete dev workflow."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import re
from collections import Counter


def _generate_and_score_workflows(
    cases: list[dict],
    *,
    dataset_sha256: str,
    generation_config: dict,
    model_identity: dict,
    generate_visible,
    evaluate_workflow_report,
    catalog: dict,
    max_turns: int,
    on_prediction=None,
    expected_split="dev",
) -> dict:
    """The private scorer runs the runner; inference receives only its prompts."""
    from training.behavioral_dev_selection import (
        summarize_paired_autonomous,
        validate_final_autonomous_report,
    )

    identifiers = [row.get("id") for row in cases]
    if expected_split not in {"dev", "final"} or any(
        row.get("split") != expected_split for row in cases
    ):
        raise ValueError(f"Only original {expected_split} workflows may enter this evaluation")
    if (
        any(not isinstance(identifier, str) or not identifier for identifier in identifiers)
        or len(set(identifiers)) != len(identifiers)
        or Counter(row.get("group") for row in cases) != {"file": 10, "format": 6, "search": 4}
    ):
        raise ValueError("Autonomous dev must include every unique fixed workflow ID and group")
    if not re.fullmatch(r"[0-9a-f]{64}", dataset_sha256):
        raise ValueError("Autonomous dev requires the frozen workflow dataset hash")
    if model_identity.get("generation_source") != "model_free_generation":
        raise ValueError("Autonomous dev requires actual free model generation")
    if (
        type(max_turns) is not int
        or max_turns < 1
        or generation_config.get("max_turns") != max_turns
    ):
        raise ValueError("Autonomous turn budget differs from the paired generation configuration")
    identity = copy.deepcopy(model_identity)
    configuration = copy.deepcopy(generation_config)
    report = {
        "split": expected_split,
        "dataset_sha256": dataset_sha256,
        "generation_config": configuration,
        "model_identity": identity,
        "expected_answers_given_to_model": False,
        "private_user_data_used": False,
        "autonomous_evaluation": "real runner from initial state with model free generation",
        "samples": [],
    }
    expected_groups = {row["id"]: row["group"] for row in cases}
    completed = set()
    model_calls = 0
    case_calls = 0
    first_prompt_sha256 = None

    def checked_output(generated):
        if (
            not isinstance(generated, dict)
            or not isinstance(generated.get("raw_output"), str)
            or type(generated.get("output_truncated")) is not bool
        ):
            raise ValueError("The autonomous generator must preserve raw output and truncation")
        return generated

    def guarded_generate(prompt, identifier):
        nonlocal model_calls, case_calls, first_prompt_sha256
        if (
            not isinstance(prompt, str)
            or not prompt
            or not isinstance(identifier, str)
            or not identifier
        ):
            raise ValueError(
                "The autonomous generator accepts only visible prompt and identifier strings"
            )
        model_calls += 1
        case_calls += 1
        if first_prompt_sha256 is None:
            first_prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        generated = generate_visible(prompt, identifier)
        if inspect.isawaitable(generated):

            async def checked_async():
                return checked_output(await generated)

            return checked_async()
        return checked_output(generated)

    def completed_case(sample):
        nonlocal case_calls, first_prompt_sha256
        identifier = sample.get("id")
        if identifier not in expected_groups or identifier in completed:
            raise ValueError("The autonomous scorer changed or duplicated complete dev IDs")
        if sample.get("group") != expected_groups[identifier]:
            raise ValueError("The autonomous scorer reclassified a fixed dev workflow")
        if case_calls < 1 or case_calls > max_turns:
            raise ValueError(
                "Every autonomous case must attempt model generation within its turn budget"
            )
        if sample.get("initial_visible_prompt_sha256") != first_prompt_sha256:
            raise ValueError("The autonomous scorer changed the actual initial visible input")
        preserved = copy.deepcopy(sample)
        preserved["actual_model_generation_calls"] = case_calls
        report["samples"].append(preserved)
        completed.add(identifier)
        case_calls = 0
        first_prompt_sha256 = None
        if on_prediction:
            on_prediction(report)

    scored = evaluate_workflow_report(
        cases,
        catalog,
        guarded_generate,
        generation_config=copy.deepcopy(configuration),
        model_identity=copy.deepcopy(identity),
        max_turns=max_turns,
        on_prediction=completed_case,
    )
    if inspect.isawaitable(scored):
        scored = asyncio.run(scored)
    if not isinstance(scored, dict) or scored.get("split") != expected_split:
        raise ValueError("The autonomous scorer must preserve the original workflow split")
    for name, expected in (
        ("generation_config", configuration),
        ("model_identity", identity),
        ("dataset_sha256", dataset_sha256),
    ):
        if name in scored and scored[name] != expected:
            raise ValueError(f"The autonomous scorer changed pinned {name}")
    scored_ids = [row.get("id") for row in scored.get("samples", [])]
    if (
        len(set(scored_ids)) != len(scored_ids)
        or set(scored_ids) != set(identifiers)
        or completed != set(identifiers)
        or case_calls
    ):
        raise ValueError("The autonomous scorer changed the complete dev denominator")
    by_id = {row["id"]: row for row in report["samples"]}
    for row in scored["samples"]:
        if row != {
            key: value
            for key, value in by_id[row["id"]].items()
            if key != "actual_model_generation_calls"
        }:
            raise ValueError("The autonomous scorer changed a persisted case after generation")
    report["actual_model_generation_calls"] = model_calls
    report["scorer_scope"] = scored.get("scope")
    if expected_split == "dev":
        summarize_paired_autonomous(report, report)
    else:
        validate_final_autonomous_report(report)
    return report


def generate_and_score_autonomous_dev(cases: list[dict], **kwargs) -> dict:
    """Checkpoint selection accepts complete original dev workflows only."""
    return _generate_and_score_workflows(cases, expected_split="dev", **kwargs)


def generate_and_score_final_workflows(cases: list[dict], **kwargs) -> dict:
    """Preserve final labels for evaluation; never send them to dev selection."""
    return _generate_and_score_workflows(cases, expected_split="final", **kwargs)
