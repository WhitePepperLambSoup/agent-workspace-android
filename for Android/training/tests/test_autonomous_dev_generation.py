"""From-zero dev evaluation sees visible prompts and retains every failure."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest


def helper():
    path = Path(__file__).resolve().parents[1] / "autonomous_dev_generation.py"
    if str(path.parents[1]) not in sys.path:
        sys.path.insert(0, str(path.parents[1]))
    assert path.is_file(), "Actual autonomous dev generation must be implemented"
    spec = importlib.util.spec_from_file_location("agent_autonomous_generation", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cases():
    return [
        {
            "id": f"{group}-{index}",
            "group": group,
            "split": "dev",
            "prompt": f"Visible task {group}-{index}",
            "expected": "PRIVATE_LABEL",
            "metadata": {"target": "PRIVATE_METADATA"},
        }
        for group, count in (("file", 10), ("format", 6), ("search", 4))
        for index in range(count)
    ]


def identity():
    return {
        "base_weight_sha256": {"weights": "b" * 64},
        "generation_source": "model_free_generation",
        "optimizer_step": 0,
    }


def scorer(
    cases, catalog, generate_visible, *, generation_config, model_identity, max_turns, on_prediction
):
    assert catalog == {"fixture": "actual runner contract"}
    assert max_turns == generation_config["max_turns"] == 16
    rows = []
    for case in cases:
        result = {
            "id": case["id"],
            "group": case["group"],
            "initial_visible_prompt_sha256": hashlib.sha256(case["prompt"].encode()).hexdigest(),
            "behavior_success": False,
            "autonomous_success": False,
            "prediction_generation_success": True,
            "output_truncated": False,
            "raw_turns": [],
        }
        try:
            generated = generate_visible(case["prompt"], case["id"])
            result["raw_turns"].append(generated)
            result["output_truncated"] = generated["output_truncated"]
            result["behavior_success"] = result["autonomous_success"] = not generated[
                "output_truncated"
            ]
        except Exception as error:
            result["prediction_generation_success"] = False
            result["generation_error"] = f"{type(error).__name__}: {error}"
        rows.append(result)
        on_prediction(result)
    return {
        "split": "dev",
        "samples": rows,
        "generation_config": generation_config,
        "model_identity": model_identity,
    }


def run(*, data=None, generate=None, evaluator=scorer, on_prediction=None, final=False):
    module = helper()
    entry = (
        module.generate_and_score_final_workflows
        if final
        else module.generate_and_score_autonomous_dev
    )
    return entry(
        cases() if data is None else data,
        dataset_sha256="c" * 64,
        generation_config={"decoding": "greedy", "max_new_tokens": 1024, "max_turns": 16},
        model_identity=identity(),
        generate_visible=generate
        or (
            lambda prompt, identifier: {
                "raw_output": "answer<|im_end|>",
                "output_truncated": False,
            }
        ),
        evaluate_workflow_report=evaluator,
        catalog={"fixture": "actual runner contract"},
        max_turns=16,
        on_prediction=on_prediction,
    )


def test_autonomous_generation_keeps_exception_and_truncation_in_complete_denominator():
    visible = []
    persisted = []

    def generate(prompt, identifier):
        visible.append(prompt)
        assert "PRIVATE" not in prompt
        if identifier == "file-2":
            raise RuntimeError("bounded synthetic generation failure")
        return {
            "raw_output": "raw unchanged\n<|im_end|>",
            "output_truncated": identifier == "search-2",
        }

    result = run(
        generate=generate, on_prediction=lambda report: persisted.append(copy.deepcopy(report))
    )
    assert len(result["samples"]) == len(visible) == len(persisted) == 20
    assert result["dataset_sha256"] == "c" * 64
    assert result["expected_answers_given_to_model"] is False
    assert len(persisted[0]["samples"]) == 1
    assert len(persisted[-1]["samples"]) == 20
    failure = next(row for row in result["samples"] if row["id"] == "file-2")
    truncated = next(row for row in result["samples"] if row["id"] == "search-2")
    assert failure["behavior_success"] is failure["prediction_generation_success"] is False
    assert truncated["behavior_success"] is False and truncated["output_truncated"] is True
    assert result["samples"][0]["raw_turns"][0]["raw_output"] == "raw unchanged\n<|im_end|>"


def test_autonomous_generation_rejects_final_scripted_missing_or_reclassified_cases():
    final = cases()
    final[0]["split"] = "final"
    with pytest.raises(ValueError, match="dev"):
        run(data=final)
    for kind in ("missing", "reclassified", "scripted", "false_success"):

        def bad_scorer(*args, mutation=kind, **kwargs):
            report = scorer(*args, **kwargs)
            if mutation == "missing":
                report["samples"].pop()
            elif mutation == "reclassified":
                report["samples"][0]["group"] = "search"
            elif mutation == "scripted":
                report["model_identity"] = {
                    **report["model_identity"],
                    "generation_source": "synthetic_control",
                }
            else:
                report["samples"][0]["prediction_generation_success"] = False
            return report

        with pytest.raises(ValueError):
            run(evaluator=bad_scorer)


def test_async_workflow_scorer_is_awaited_without_changing_generation_contract():
    async def async_scorer(*args, **kwargs):
        return scorer(*args, **kwargs)

    assert len(run(evaluator=async_scorer)["samples"]) == 20


def test_scorer_cannot_claim_from_zero_success_without_calling_the_model():
    def scripted_without_model(data, catalog, generate_visible, **kwargs):
        del catalog, generate_visible
        sample = {
            "id": data[0]["id"],
            "group": data[0]["group"],
            "initial_visible_prompt_sha256": hashlib.sha256(data[0]["prompt"].encode()).hexdigest(),
            "behavior_success": True,
            "autonomous_success": True,
            "prediction_generation_success": True,
            "output_truncated": False,
        }
        kwargs["on_prediction"](sample)
        return {"split": "dev", "samples": [sample]}

    with pytest.raises(ValueError, match="attempt model generation"):
        run(evaluator=scripted_without_model)


def test_workflow_budget_rejects_extra_model_turns_and_initial_prompt_hash_changes():
    for kind in ("extra_turns", "changed_prompt"):

        def violating(data, catalog, generate_visible, mutation=kind, **kwargs):
            if mutation == "extra_turns":
                original = generate_visible

                def repeated(prompt, identifier):
                    for _ in range(kwargs["max_turns"] + 1):
                        value = original(prompt, identifier)
                    return value

                return scorer(data, catalog, repeated, **kwargs)

            original_callback = kwargs["on_prediction"]

            def rewrite_hash(sample):
                sample["initial_visible_prompt_sha256"] = "f" * 64
                original_callback(sample)

            return scorer(
                data, catalog, generate_visible, **{**kwargs, "on_prediction": rewrite_hash}
            )

        with pytest.raises(ValueError):
            run(evaluator=violating)


def test_independent_final_workflows_preserve_original_split_and_reject_dev_entry():
    final_cases = [{**row, "split": "final"} for row in cases()]

    def final_scorer(data, *args, **kwargs):
        assert {row["split"] for row in data} == {"final"}
        result = scorer(data, *args, **kwargs)
        result["split"] = "final"
        return result

    result = run(data=final_cases, evaluator=final_scorer, final=True)
    assert result["split"] == "final"
    assert len(result["samples"]) == 20
    assert result["actual_model_generation_calls"] == 20
    with pytest.raises(ValueError, match="original final"):
        run(final=True)
    with pytest.raises(ValueError, match="original dev"):
        run(data=final_cases, evaluator=final_scorer)


def test_final_workflow_evaluator_rejects_scorer_relabeling_final_as_dev():
    final_cases = [{**row, "split": "final"} for row in cases()]
    with pytest.raises(ValueError, match="original workflow split"):
        run(data=final_cases, final=True)
