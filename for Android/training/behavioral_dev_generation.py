"""Generate complete dev continuations before allowing an independent scorer."""

from __future__ import annotations

import hashlib
import time


def runtime_turn_eos_ids(tokenizer) -> list[int]:
    """Use the same Qwen turn boundary as the production runtime evaluator."""
    ids = [tokenizer.convert_tokens_to_ids(token) for token in ("<|im_end|>", "<|endoftext|>")]
    if (
        any(type(value) is not int or value < 0 for value in ids)
        or getattr(tokenizer, "unk_token_id", None) in ids
        or len(set(ids)) != len(ids)
    ):
        raise ValueError("Runtime EOS markers must be present and distinct special tokens")
    return ids


def continuation_is_truncated(tokens, *, max_new_tokens: int, eos_ids: list[int]) -> bool:
    """An EOS on the exact output limit still completes the assistant turn."""
    return len(tokens) >= max_new_tokens and (not len(tokens) or int(tokens[-1]) not in eos_ids)


def generate_and_score_dev(
    records: list[dict],
    *,
    dataset_sha256: str,
    generation_config: dict,
    generate_visible,
    build_visible_prompt,
    score_report,
    catalog: dict,
    model_identity: dict | None = None,
    on_prediction=None,
) -> tuple[dict, dict]:
    """Never provide supervision to inference or drop an unsuccessful prediction."""
    identifiers = [row["id"] for row in records]
    if any(row.get("split") != "dev" for row in records):
        raise ValueError("Behavioral generation accepts original dev records only")
    if not identifiers or len(set(identifiers)) != len(identifiers):
        raise ValueError("Dev records must have unique complete IDs")
    raw_report = {
        "split": "dev",
        "dataset_sha256": dataset_sha256,
        "eval_sha256": dataset_sha256,
        "generation_config": generation_config,
        "model_identity": model_identity or {},
        "expected_answers_given_to_model": False,
        "private_user_data_used": False,
        "samples": [],
    }
    for record in records:
        prompt = build_visible_prompt(record)
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("The visible dev prompt must be a nonempty string")
        prediction = {
            "id": record["id"],
            "visible_prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prediction_generation_success": False,
            "generation_error": None,
            "raw_output": "",
            "output_truncated": False,
        }
        started = time.monotonic()
        try:
            generated = generate_visible(prompt, record["id"])
            if not isinstance(generated.get("raw_output"), str):
                raise ValueError("The generator must preserve a raw string continuation")
            if type(generated.get("output_truncated")) is not bool:
                raise ValueError("The generator must report an explicit truncation Boolean")
            prediction.update(
                raw_output=generated["raw_output"],
                input_tokens=generated.get("input_tokens"),
                output_tokens=generated.get("output_tokens"),
                output_truncated=generated["output_truncated"],
                prediction_generation_success=True,
            )
        except Exception as error:
            prediction["generation_error"] = f"{type(error).__name__}: {error}"
        prediction["elapsed_seconds"] = time.monotonic() - started
        raw_report["samples"].append(prediction)
        if on_prediction:
            on_prediction(raw_report)
    semantic = score_report(records, raw_report, catalog)
    if semantic.get("split") != "dev":
        raise ValueError("The semantic scorer must preserve the original dev split")
    semantic_samples = semantic.get("samples", [])
    scored_ids = [row["id"] for row in semantic_samples]
    if len(set(scored_ids)) != len(scored_ids) or set(scored_ids) != set(identifiers):
        raise ValueError("The semantic scorer changed the complete dev IDs/denominator")
    raw_by_id = {row["id"]: row for row in raw_report["samples"]}
    scored = []
    for sample in semantic_samples:
        generated = raw_by_id[sample["id"]]
        scored.append(
            {
                **sample,
                "visible_prompt_sha256": generated["visible_prompt_sha256"],
                "prediction_generation_success": generated["prediction_generation_success"],
                "output_truncated": generated["output_truncated"],
            }
        )
    semantic.update(
        split="dev",
        dataset_sha256=dataset_sha256,
        generation_config=generation_config,
        model_identity=model_identity or {},
        samples=scored,
        raw_generation_denominator=len(raw_report["samples"]),
    )
    return semantic, raw_report
