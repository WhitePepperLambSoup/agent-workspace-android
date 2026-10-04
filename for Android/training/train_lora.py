"""Train genuine assistant-only tool-call LoRA weights on Qwen3.5 0.8B.

Input records contain preceding ``messages``, advertised ``tools``, and a
``target_response``. Prompts come from the checkpoint's own chat template. Only
the target assistant turn contributes to the loss. No user conversation data is
collected, no cloud inference is used, and nothing is pushed to the Hub.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import math
import random
import re
import subprocess
import sys
import time
from contextlib import ExitStack
from fractions import Fraction
from pathlib import Path

TARGET_MODULES = (
    r"model\.language_model\.layers\.\d+\.(?:"
    r"self_attn\.(?:q_proj|k_proj|v_proj|o_proj)|"
    r"linear_attn\.(?:in_proj_qkv|in_proj_z|out_proj)|"
    r"mlp\.(?:gate_proj|up_proj|down_proj))"
)
EXPECTED_BASE_WEIGHTS_SHA256 = "04b1c301231dd422b8860db31311ab2721511346a32cb1e079c4c4e5f1fe4696"
TARGET_MODULE_PROFILES = {
    "full_v4": TARGET_MODULES,
    "attention_only": (
        r"model\.language_model\.layers\.\d+\.(?:"
        r"self_attn\.(?:q_proj|k_proj|v_proj|o_proj)|"
        r"linear_attn\.(?:in_proj_qkv|in_proj_z|out_proj))"
    ),
}


def behavioral_profile_sources(
    profile: str, script_path: Path, scorer_dependencies: tuple[str, ...] = ()
) -> list[Path]:
    """Pin the selected scorer and every explicitly declared runtime dependency."""
    if profile not in {"v4_files", "v5_general"}:
        raise ValueError("Unknown behavioral profile")
    root = script_path.parents[2].resolve()
    files = [script_path, script_path.with_name("critical_parameter_loss.py")]
    common = ("behavioral_dev_selection.py", "behavioral_dev_generation.py", "evaluate_tools.py")
    selected = (
        (
            "evaluate_replay_v4.py",
            "evaluate_replay_v3.py",
            "build_dataset.py",
            "build_dataset_v4.py",
            "runtime_fixture_v4.py",
        )
        if profile == "v4_files"
        else ("evaluate_replay_v5.py", "behavioral_plan.py", "autonomous_dev_generation.py")
    )
    files.extend(script_path.with_name(name) for name in (*common, *selected))
    files.extend(
        script_path.parents[1] / "android_adapter" / name
        for name in ("local_provider.py", "local_context.py")
    )
    files.extend(
        root / name
        for name in (
            "src/agent_workspace/application/runner.py",
            "src/agent_workspace/tools/filesystem.py",
        )
    )
    if profile == "v5_general":
        for name in scorer_dependencies:
            if not isinstance(name, str):
                raise ValueError("Behavioral source dependency paths must be strings")
            relative = Path(name)
            path = (root / relative).resolve()
            if relative.is_absolute() or not path.is_relative_to(root) or path.suffix != ".py":
                raise ValueError("Behavioral source dependencies must be repository Python files")
            files.append(path)
    return list(dict.fromkeys(files))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_records(path: Path, *, raw: bytes | None = None) -> list[dict]:
    result = []
    data = path.read_bytes() if raw is None else raw
    for number, line in enumerate(data.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record.get("messages"), list) or not record["messages"]:
            raise ValueError(f"{path.name}:{number}: messages must contain preceding turns")
        if not isinstance(record.get("target_response"), str) or not record["target_response"]:
            raise ValueError(f"{path.name}:{number}: target_response must be a non-empty string")
        if record["messages"][-1].get("role") == "assistant":
            raise ValueError(
                f"{path.name}:{number}: final assistant response must be a separate target"
            )
        result.append(record)
    if not result:
        raise ValueError(f"Empty dataset: {path}")
    return result


def validate_behavioral_training_inputs(train_records: list[dict], dev_records: list[dict]) -> None:
    """Preserve actual dataset roles before any behavioral generation or training."""
    split_ids = []
    for split, records in (("train", train_records), ("dev", dev_records)):
        if not records or any(row.get("split") != split for row in records):
            raise ValueError(
                f"Strict behavioral {split} input contains a different or unspecified split"
            )
        identifiers = [row.get("id") for row in records]
        if any(not isinstance(identifier, str) or not identifier for identifier in identifiers):
            raise ValueError(f"Strict behavioral {split} requires nonempty record IDs")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError(f"Strict behavioral {split} IDs must be unique")
        split_ids.append(set(identifiers))
    if split_ids[0] & split_ids[1]:
        raise ValueError("Strict train/dev IDs overlap")


def render_prompt(record: dict, tokenizer, *, prompt_source: str = "official") -> str:
    if prompt_source == "runtime":
        root = Path(__file__).resolve().parents[2]
        for source in (root / "src", root / "for Android"):
            if str(source) not in sys.path:
                sys.path.insert(0, str(source))
        from training.evaluate_tools import build_evaluation_prompt

        _, prompt = build_evaluation_prompt(record, prompt_source="runtime")
        return prompt
    if prompt_source != "official":
        raise ValueError("Unknown training prompt-source")
    return tokenizer.apply_chat_template(
        record["messages"],
        tools=record.get("tools") or None,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )


def ensure_disjoint_prompts(
    train_records: list[dict],
    eval_records: list[dict],
    tokenizer,
    *,
    prompt_source: str = "official",
) -> None:
    def signatures(records):
        return {
            tuple(
                tokenizer(
                    render_prompt(record, tokenizer, prompt_source=prompt_source),
                    add_special_tokens=False,
                )["input_ids"]
            )
            for record in records
        }

    if signatures(train_records) & signatures(eval_records):
        raise ValueError("Train/eval canonical tokenized prompts overlap")


def verify_source_checkpoint(directory: Path) -> dict[str, str]:
    weights = directory / "model.safetensors-00001-of-00001.safetensors"
    if not weights.is_file():
        raise ValueError("This trainer requires the pinned original Qwen3.5 0.8B checkpoint")
    actual = sha256_file(weights)
    if actual != EXPECTED_BASE_WEIGHTS_SHA256:
        raise ValueError("Source weights do not match the pinned public Qwen3.5 0.8B checkpoint")
    return {weights.name: actual}


def _restore_source_parameters(model, directory: Path, *, only_fp32: bool) -> list[str]:
    import torch
    from safetensors import safe_open

    index = json.loads((directory / "model.safetensors.index.json").read_text(encoding="utf-8"))
    mapping = {name: directory / filename for name, filename in index["weight_map"].items()}
    restored = []
    with ExitStack() as stack:
        streams = {
            filename: stack.enter_context(safe_open(filename, framework="pt", device="cpu"))
            for filename in set(mapping.values())
        }
        for name, parameter in model.named_parameters():
            module = name.removesuffix(".weight")
            targeted = name.endswith(".weight") and re.fullmatch(TARGET_MODULES, module) is not None
            if not only_fp32 and targeted:
                continue
            if name not in mapping:
                raise ValueError(f"Model parameter is absent from the pinned source: {name}")
            original = streams[mapping[name]].get_tensor(name)
            if only_fp32 and original.dtype != torch.float32:
                continue
            if parameter.shape != original.shape:
                raise ValueError(f"Model/source shape mismatch: {name}")
            if parameter.dtype != original.dtype or not torch.equal(
                parameter.detach().cpu(), original
            ):
                parameter.data = original.clone()
                restored.append(name)
    return restored


def restore_source_fp32_parameters(model, directory: Path) -> list[str]:
    """Preserve original FP32 normalization/gate values before mixed-precision SFT."""
    return _restore_source_parameters(model, directory, only_fp32=True)


def restore_frozen_source_parameters(model, directory: Path) -> list[str]:
    """Keep all frozen export weights at their original source dtype and values."""
    return _restore_source_parameters(model, directory, only_fp32=False)


def complete_source_mtp_export(source: Path, destination: Path) -> dict:
    """Retain the original MTP head that the HF inference class does not load.

    The native model loader still requires those tensors when the official
    configuration advertises MTP layers. Only that unloaded frozen head may be
    added; missing language or vision tensors remain an export error.
    """
    import gc

    import torch
    from safetensors import safe_open
    from safetensors.torch import save_file

    index = json.loads((source / "model.safetensors.index.json").read_text(encoding="utf-8"))
    source_files = {name: source / filename for name, filename in index["weight_map"].items()}
    final_file = destination / "model.safetensors"
    temporary = destination / "model.safetensors.mtp-completion.tmp"
    tensors = {}
    added = []
    restored = []
    current = original = None
    with ExitStack() as stack:
        streams = {
            filename: stack.enter_context(safe_open(filename, framework="pt", device="cpu"))
            for filename in set(source_files.values())
        }
        exported = stack.enter_context(safe_open(final_file, framework="pt", device="cpu"))
        exported_names = set(exported.keys())
        unknown = exported_names - set(source_files)
        missing_non_mtp = [
            name for name in set(source_files) - exported_names if not name.startswith("mtp.")
        ]
        if unknown or missing_non_mtp:
            raise ValueError(
                f"Export has unexpected or missing non-MTP tensors: "
                f"{sorted(unknown | set(missing_non_mtp))}"
            )
        for name in sorted(source_files):
            if not name.startswith("mtp."):
                tensors[name] = exported.get_tensor(name)
                continue
            original = streams[source_files[name]].get_tensor(name)
            if not bool(torch.isfinite(original).all()):
                raise ValueError(f"Non-finite original MTP tensor: {name}")
            if name not in exported_names:
                added.append(name)
            else:
                current = exported.get_tensor(name)
                if original.dtype != current.dtype or not torch.equal(original, current):
                    restored.append(name)
            tensors[name] = original
        if added or restored:
            save_file(tensors, temporary, metadata={"format": "pt"})
        tensors.clear()
        current = original = None
    gc.collect()
    if added or restored:
        temporary.replace(final_file)
    return {
        "added_source_mtp_tensors": added,
        "restored_source_mtp_tensors": restored,
        "source_mtp_tensors": sum(name.startswith("mtp.") for name in source_files),
        "learned_language_tensors_modified": False,
        "cuda_used": False,
    }


def tokenize_records(
    records: list[dict],
    tokenizer,
    max_length: int,
    *,
    prompt_source: str = "official",
    critical_parameter_loss: bool = False,
) -> tuple[list[dict], dict]:
    features = []
    lengths = []
    for record in records:
        prompt = render_prompt(record, tokenizer, prompt_source=prompt_source)
        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        input_ids = tokenizer(
            prompt + record["target_response"] + "<|im_end|>", add_special_tokens=False
        )["input_ids"]
        # BPE can merge the final prompt newline with the first answer token.
        # Preserve the actual canonical full encoding and mask its common prefix.
        boundary = 0
        for left, right in zip(prompt_ids, input_ids, strict=False):
            if left != right:
                break
            boundary += 1
        if tokenizer.decode(prompt_ids[boundary:]).strip():
            raise ValueError(
                "Tokenizer changed non-whitespace prompt tokens at the target boundary"
            )
        if len(input_ids) > max_length:
            raise ValueError(
                f"Record {record.get('id', '?')} needs {len(input_ids)} tokens, over {max_length}; "
                "increase max-length instead of truncating a tool call"
            )
        labels = [-100] * boundary + input_ids[boundary:]
        if not any(value != -100 for value in labels):
            raise ValueError("A training record contains no supervised assistant tokens")
        feature = {"input_ids": input_ids, "attention_mask": [1] * len(input_ids), "labels": labels}
        if critical_parameter_loss:
            android_root = str(Path(__file__).resolve().parents[1])
            if android_root not in sys.path:
                sys.path.insert(0, android_root)
            from training.critical_parameter_loss import (
                critical_target_spans,
                map_critical_token_groups,
            )

            encoded = tokenizer(
                prompt + record["target_response"] + "<|im_end|>",
                add_special_tokens=False,
                return_offsets_mapping=True,
            )
            if encoded["input_ids"] != input_ids:
                raise ValueError("Offset encoding differs from canonical training input")
            spans = critical_target_spans(
                record["target_response"], extra_spans=record.get("metadata", {}).get("loss_spans")
            )
            feature["critical_groups"] = map_critical_token_groups(
                spans, encoded["offset_mapping"], len(prompt), labels
            )
        features.append(feature)
        lengths.append(len(input_ids))
    return features, {
        "records": len(features),
        "maximum_tokens": max(lengths),
        "mean_tokens": sum(lengths) / len(lengths),
        "supervised_tokens": sum(sum(value != -100 for value in row["labels"]) for row in features),
        "truncated_records": 0,
        "loss_mask": "all prompt tokens masked except final whitespace merged with target by BPE",
        "critical_parameter_loss": critical_parameter_loss,
        "critical_group_counts": {
            kind: sum(
                group["kind"] == kind
                for feature in features
                for group in feature.get("critical_groups", [])
            )
            for kind in sorted(
                {
                    group["kind"]
                    for feature in features
                    for group in feature.get("critical_groups", [])
                }
            )
        },
    }


def assistant_forward_loss(model, feature: dict, *, torch, device, critical: bool = False):
    """Use the complete sequence while allocating logits only for assistant tokens."""
    batch = {
        key: torch.tensor([feature[key]], dtype=torch.long, device=device)
        for key in ("input_ids", "attention_mask", "labels")
    }
    first = next(i for i, value in enumerate(feature["labels"]) if value != -100)
    logits_indices = torch.arange(max(0, first - 1), len(feature["input_ids"]) - 1, device=device)
    output = model(
        input_ids=batch["input_ids"],
        attention_mask=batch["attention_mask"],
        use_cache=False,
        logits_to_keep=logits_indices,
    )
    target = batch["labels"][:, logits_indices + 1]
    if critical:
        from training.critical_parameter_loss import grouped_cross_entropy

        offset = int(logits_indices[0]) + 1
        groups = [
            {"kind": group["kind"], "indices": [index - offset for index in group["indices"]]}
            for group in feature["critical_groups"]
        ]
        loss, _ = grouped_cross_entropy(output.logits, target, groups)
        return loss
    return torch.nn.functional.cross_entropy(
        output.logits.reshape(-1, output.logits.shape[-1]).float(),
        target.reshape(-1),
        ignore_index=-100,
    )


def vision_hash(model) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.model.visual.state_dict().items()):
        digest.update(name.encode("utf-8"))
        # view(uint8) preserves BF16 bytes without a NumPy BF16 conversion.
        digest.update(
            value.detach().cpu().contiguous().view(__import__("torch").uint8).numpy().tobytes()
        )
    return digest.hexdigest()


def gpu_memory_snapshot() -> list[dict]:
    """Read physical GPU memory without inspecting other processes or stopping them."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return [
            {
                "name": cells[0].strip(),
                "total_mib": int(cells[1]),
                "used_mib": int(cells[2]),
                "free_mib": int(cells[3]),
            }
            for line in result.stdout.splitlines()
            if len(cells := line.split(",")) == 4
        ]
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def preserve_base_tokenizer(source: Path, destination: Path) -> None:
    """Keep the unchanged original vocabulary and template byte-for-byte."""
    for name in (
        "tokenizer.json",
        "tokenizer_config.json",
        "chat_template.jinja",
        "vocab.json",
        "merges.txt",
        "added_tokens.json",
        "special_tokens_map.json",
        "LICENSE",
    ):
        original = source / name
        if original.is_file():
            (destination / name).write_bytes(original.read_bytes())


def stratified_dev_indices(records: list[dict], limit: int) -> list[int]:
    """Cover each task family rather than aliasing periodically ordered records."""
    if limit <= 0 or limit >= len(records):
        return list(range(len(records)))
    groups: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        family = str(record.get("metadata", {}).get("family", "unknown"))
        groups.setdefault(family, []).append(index)
    if limit < len(groups):
        raise ValueError("dev limit must cover all families, or be zero for the complete dev set")
    selected = []
    cursor = 0
    while len(selected) < limit:
        for family in sorted(groups):
            if cursor < len(groups[family]) and len(selected) < limit:
                selected.append(groups[family][cursor])
        cursor += 1
    return sorted(selected)


def balanced_training_order(records: list[dict], *, seed: int) -> list[int]:
    """Randomize within families, then interleave them for a short step budget."""
    rng = random.Random(seed)
    groups: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        family = str(record.get("metadata", {}).get("family", "unknown"))
        groups.setdefault(family, []).append(index)
    for indices in groups.values():
        rng.shuffle(indices)
    families = sorted(groups)
    rng.shuffle(families)
    order = []
    for cursor in range(max(map(len, groups.values()))):
        for family in families:
            if cursor < len(groups[family]):
                order.append(groups[family][cursor])
    return order


def retention_balanced_training_order(
    records: list[dict], *, seed: int, minimum_ordinary_fraction: float
) -> list[int]:
    """Cover a complete epoch while meeting the ordinary floor at every prefix."""
    if not records or not math.isfinite(minimum_ordinary_fraction):
        raise ValueError("A retention sampler requires records and a finite ordinary fraction")
    if not 0 < minimum_ordinary_fraction <= 1:
        raise ValueError("Ordinary retention fraction must be in (0, 1]")
    floor = Fraction(str(minimum_ordinary_fraction))
    ordinary_indices = [
        index
        for index, row in enumerate(records)
        if row.get("metadata", {}).get("ordinary_retention")
    ]
    if Fraction(len(ordinary_indices), len(records)) < floor:
        raise ValueError(
            "Frozen data has too few ordinary examples for the requested retention floor"
        )
    ordinary_set = set(ordinary_indices)
    tool_indices = [index for index in range(len(records)) if index not in ordinary_set]

    def category_order(indices: list[int], category_seed: int) -> list[int]:
        if not indices:
            return []
        local = balanced_training_order([records[index] for index in indices], seed=category_seed)
        return [indices[index] for index in local]

    ordinary_order = category_order(ordinary_indices, seed)
    tool_order = category_order(tool_indices, seed + 1000003)
    ordinary_cursor = tool_cursor = 0
    order = []
    for length in range(1, len(records) + 1):
        need_ordinary = Fraction(ordinary_cursor, length) < floor
        if need_ordinary or tool_cursor == len(tool_order):
            if ordinary_cursor == len(ordinary_order):
                raise ValueError("Ordinary source data cannot satisfy the prefix retention floor")
            order.append(ordinary_order[ordinary_cursor])
            ordinary_cursor += 1
        else:
            order.append(tool_order[tool_cursor])
            tool_cursor += 1
    return order


def describe_training_sampling(
    records: list[dict], sampled_indices: list[int], *, minimum_ordinary_fraction: float = 0.0
) -> dict:
    """Describe the exact prefix consumed by a run or its selected checkpoint."""
    family_counts: dict[str, int] = {}
    ordinary = 0
    for index in sampled_indices:
        metadata = records[index].get("metadata", {})
        family = str(metadata.get("family", "unknown"))
        family_counts[family] = family_counts.get(family, 0) + 1
        ordinary += bool(metadata.get("ordinary_retention"))
    return {
        "method": (
            "ordinary_floor_at_every_prefix_with_seeded_family_interleaving"
            if minimum_ordinary_fraction
            else "seeded_shuffle_within_family_then_family_interleaving"
        ),
        "minimum_ordinary_fraction": minimum_ordinary_fraction,
        "examples_consumed": len(sampled_indices),
        "unique_examples_consumed": len(set(sampled_indices)),
        "available_examples": len(records),
        "available_record_ids": [row["id"] for row in records],
        "available_ordinary_record_ids": [
            row["id"] for row in records if row.get("metadata", {}).get("ordinary_retention")
        ],
        "sampled_family_counts": dict(sorted(family_counts.items())),
        "sampled_record_ids": [records[index]["id"] for index in sampled_indices],
        "complete_training_set_seen": len(set(sampled_indices)) == len(records),
        "ordinary_examples_consumed": ordinary,
        "ordinary_fraction": ordinary / len(sampled_indices) if sampled_indices else 0.0,
    }


def aggregate_dev_losses(rows: list[tuple[str, float, int]]) -> dict:
    """Report token-weighted family losses and a family-balanced macro loss."""
    groups: dict[str, dict] = {}
    for family, loss, count in rows:
        if not math.isfinite(loss) or count < 1:
            raise ValueError("dev losses must be finite with positive supervised token counts")
        group = groups.setdefault(
            family, {"weighted_loss": 0.0, "supervised_tokens": 0, "records": 0}
        )
        group["weighted_loss"] += loss * count
        group["supervised_tokens"] += count
        group["records"] += 1
    if not groups:
        raise ValueError("dev validation requires records from at least one family")
    families = {
        family: {
            "loss": group["weighted_loss"] / group["supervised_tokens"],
            "supervised_tokens": group["supervised_tokens"],
            "records": group["records"],
        }
        for family, group in sorted(groups.items())
    }
    token_count = sum(group["supervised_tokens"] for group in groups.values())
    return {
        "loss": sum(group["weighted_loss"] for group in groups.values()) / token_count,
        "macro_loss": sum(group["loss"] for group in families.values()) / len(families),
        "supervised_tokens": token_count,
        "records": len(rows),
        "families": families,
    }


def select_dev_checkpoint(
    baseline: dict, history: list[dict], *, patience: int, min_delta: float
) -> dict:
    """Select a trained checkpoint while retaining an honest base comparison."""
    best_for_stopping = baseline["macro_loss"]
    best_trained_score = math.inf
    best_trained_step = None
    bad_checks = 0
    for checkpoint in history:
        score = checkpoint["metrics"]["macro_loss"]
        if not math.isfinite(score):
            raise ValueError("checkpoint macro loss must be finite")
        if score < best_trained_score:
            best_trained_score = score
            best_trained_step = checkpoint["step"]
        if score < best_for_stopping - min_delta:
            best_for_stopping = score
            bad_checks = 0
        else:
            bad_checks += 1
    return {
        "selected_step": best_trained_step,
        "selected_macro_loss": best_trained_score if history else None,
        "improved_over_baseline": best_trained_score < baseline["macro_loss"] - min_delta,
        "non_improving_checks": bad_checks,
        "should_stop": patience > 0 and bad_checks >= patience,
        "selection_metric": "family_balanced_macro_loss",
    }


def restore_saved_adapter(model, checkpoint: Path, expected_sha256: str) -> dict:
    """Reload and verify the selected saved adapter before exporting any weights."""
    import torch
    from peft import get_peft_model_state_dict, set_peft_model_state_dict
    from safetensors.torch import load_file

    adapter_file = checkpoint / "adapter_model.safetensors"
    if sha256_file(adapter_file) != expected_sha256:
        raise ValueError("selected checkpoint adapter hash changed")
    expected = load_file(adapter_file, device="cpu")
    incompatible = set_peft_model_state_dict(model, expected)
    if incompatible.unexpected_keys or any("lora_" in name for name in incompatible.missing_keys):
        raise ValueError("selected adapter weights could not be completely restored")
    actual = get_peft_model_state_dict(model)
    if set(actual) != set(expected):
        raise ValueError("restored adapter tensor names differ from the saved checkpoint")
    for name, value in actual.items():
        restored = value.detach().cpu()
        if restored.dtype != expected[name].dtype or not torch.equal(restored, expected[name]):
            raise ValueError(f"restored adapter differs from the selected checkpoint: {name}")
    return {
        "adapter_sha256": expected_sha256,
        "checked_adapter_tensors": len(expected),
        "restored_exactly": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--eval", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-length", type=int, default=1536)
    parser.add_argument("--prompt-source", choices=("official", "runtime"), default="official")
    parser.add_argument("--steps", type=int, default=96)
    parser.add_argument("--gradient-accumulation", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=0.0002)
    parser.add_argument("--rank", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261001)
    parser.add_argument("--eval-limit", type=int, default=32)
    parser.add_argument("--checkpoint-every", type=int, default=0)
    parser.add_argument("--early-stopping-patience", type=int, default=0)
    parser.add_argument("--early-stopping-min-delta", type=float, default=0.001)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--export-merged", action="store_true")
    parser.add_argument("--critical-parameter-loss", action="store_true")
    parser.add_argument("--minimum-ordinary-fraction", type=float, default=0.0)
    parser.add_argument("--behavioral-dev-catalog", type=Path)
    parser.add_argument("--behavioral-max-new-tokens", type=int, default=512)
    parser.add_argument("--behavioral-critical-minima", type=Path)
    parser.add_argument(
        "--behavioral-profile", choices=("v4_files", "v5_general"), default="v4_files"
    )
    parser.add_argument("--behavioral-plan", type=Path)
    parser.add_argument("--behavioral-dev-workflows", type=Path)
    parser.add_argument("--behavioral-max-turns", type=int, default=16)
    parser.add_argument(
        "--target-modules-profile", choices=tuple(TARGET_MODULE_PROFILES), default="full_v4"
    )
    args = parser.parse_args()
    if args.steps < 1 or args.gradient_accumulation < 1 or args.rank < 1:
        parser.error("steps, rank, and gradient-accumulation must be positive")
    if (
        args.checkpoint_every < 0
        or args.early_stopping_patience < 0
        or args.early_stopping_min_delta < 0
    ):
        parser.error("checkpoint and early stopping settings must be nonnegative")
    if args.early_stopping_patience and not args.checkpoint_every:
        parser.error("early stopping requires periodic checkpoints")
    if (
        not math.isfinite(args.minimum_ordinary_fraction)
        or not 0 <= args.minimum_ordinary_fraction <= 1
        or args.behavioral_max_new_tokens < 1
    ):
        parser.error("ordinary fraction must be in [0, 1] and generation budget positive")
    script_path = Path(__file__).resolve()
    root = script_path.parents[2]
    for source in (root / "src", root / "for Android"):
        if str(source) not in sys.path:
            sys.path.insert(0, str(source))
    fixed_plan = None
    fixed_plan_sha256 = None
    if args.behavioral_profile == "v5_general":
        if not all(
            (
                args.behavioral_plan,
                args.behavioral_dev_workflows,
                args.behavioral_dev_catalog,
                args.behavioral_critical_minima,
            )
        ):
            parser.error("v5_general requires its fixed plan, catalog, minima and dev workflows")
        from training.behavioral_plan import read_behavioral_plan, validate_behavioral_plan_cli

        try:
            fixed_plan, fixed_plan_sha256 = read_behavioral_plan(args.behavioral_plan)
            validate_behavioral_plan_cli(fixed_plan, args)
        except ValueError as error:
            parser.error(str(error))
    elif args.behavioral_plan or args.behavioral_dev_workflows:
        parser.error("fixed broader plans and workflows require the v5_general profile")
    if args.behavioral_profile == "v4_files" and args.target_modules_profile != "full_v4":
        parser.error("v4_files must preserve its original full_v4 module profile")
    behavioral_budget = (
        {
            "maximum_epochs": fixed_plan["maximum_epochs"],
            "maximum_steps": fixed_plan["maximum_steps"],
        }
        if fixed_plan
        else {"maximum_epochs": 2, "maximum_steps": 300}
    )
    if args.behavioral_dev_catalog and (
        not args.checkpoint_every
        or args.eval_limit != 0
        or args.early_stopping_patience
        or args.minimum_ordinary_fraction < 0.4
        or args.steps > behavioral_budget["maximum_steps"]
        or args.prompt_source != "runtime"
        or not args.behavioral_critical_minima
    ):
        parser.error(
            "behavioral dev requires runtime prompts, complete dev, checkpoints, no loss early "
            "stopping, fixed critical minima, ordinary fraction >=0.4, and its fixed step budget"
        )
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("output must be empty to keep completed training runs reproducible")
    args.output.mkdir(parents=True, exist_ok=True)

    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    source_identity = verify_source_checkpoint(args.model)
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; explicitly choose --device cpu to train on CPU")
    device = torch.device(args.device)
    dtype = (
        torch.bfloat16
        if args.device == "cuda" and torch.cuda.is_bf16_supported()
        else torch.float32
    )
    tokenizer = AutoTokenizer.from_pretrained(
        args.model, local_files_only=True, trust_remote_code=False
    )
    train_bytes = args.train.read_bytes()
    eval_bytes = args.eval.read_bytes()
    train_sha256 = hashlib.sha256(train_bytes).hexdigest()
    eval_sha256 = hashlib.sha256(eval_bytes).hexdigest()
    train_records = read_records(args.train, raw=train_bytes)
    eval_records = read_records(args.eval, raw=eval_bytes)
    if args.behavioral_dev_catalog:
        validate_behavioral_training_inputs(train_records, eval_records)
    if args.behavioral_dev_catalog and (
        args.steps * args.gradient_accumulation < len(train_records)
        or args.steps * args.gradient_accumulation
        > behavioral_budget["maximum_epochs"] * len(train_records)
        or (args.steps * args.gradient_accumulation) % len(train_records)
        or (args.checkpoint_every * args.gradient_accumulation) % len(train_records)
    ):
        parser.error(
            "behavioral training/checkpoints must consume one or two exact complete epochs"
        )
    catalog = None
    catalog_sha256 = None
    critical_minima = None
    critical_minima_sha256 = None
    workflow_records = None
    workflow_sha256 = None
    score_workflow_report = None
    scorer_dependencies = ()
    score_behavior_module = None
    if args.behavioral_dev_catalog:
        score_behavior_module = importlib.import_module(
            "training.evaluate_replay_v5" if fixed_plan else "training.evaluate_replay_v4"
        )
        score_behavior_report = score_behavior_module.score_report

        catalog_bytes = args.behavioral_dev_catalog.read_bytes()
        catalog_sha256 = hashlib.sha256(catalog_bytes).hexdigest()
        catalog = json.loads(catalog_bytes)
        if args.behavioral_critical_minima:
            minima_bytes = args.behavioral_critical_minima.read_bytes()
            critical_minima = json.loads(minima_bytes)
            critical_minima_sha256 = hashlib.sha256(minima_bytes).hexdigest()
        if fixed_plan:
            from training.behavioral_plan import (
                validate_behavioral_plan_hashes,
                validate_behavioral_plan_records,
            )

            workflow_bytes = args.behavioral_dev_workflows.read_bytes()
            workflow_sha256 = hashlib.sha256(workflow_bytes).hexdigest()
            workflow_records = [
                json.loads(line)
                for line in workflow_bytes.decode("utf-8-sig").splitlines()
                if line.strip()
            ]
            validate_behavioral_plan_hashes(
                fixed_plan,
                {
                    "train_sha256": train_sha256,
                    "dev_sha256": eval_sha256,
                    "catalog_sha256": catalog_sha256,
                    "critical_minima_sha256": critical_minima_sha256,
                    "dev_workflows_sha256": workflow_sha256,
                },
            )
            validate_behavioral_plan_records(
                fixed_plan, train_records, eval_records, workflow_records
            )
            if critical_minima != fixed_plan["critical_family_minima"]:
                raise ValueError("Critical family minima differ from the fixed behavioral plan")
            score_workflow_report = score_behavior_module.evaluate_workflow_report
            scorer_dependencies = getattr(score_behavior_module, "SOURCE_DEPENDENCIES", ())
            if not isinstance(scorer_dependencies, (tuple, list)) or not scorer_dependencies:
                raise ValueError(
                    "The broader scorer must declare its complete source dependency inventory"
                )
            if str(dtype) != fixed_plan["generation"]["dtype"]:
                raise ValueError("Actual generation dtype differs from the fixed behavioral plan")
    ensure_disjoint_prompts(
        train_records, eval_records, tokenizer, prompt_source=args.prompt_source
    )
    official_template_audit = None
    if args.prompt_source == "runtime":
        ensure_disjoint_prompts(train_records, eval_records, tokenizer)
        _, official_train_stats = tokenize_records(train_records, tokenizer, args.max_length)
        _, official_dev_stats = tokenize_records(eval_records, tokenizer, args.max_length)
        official_template_audit = {
            "train": official_train_stats,
            "dev": official_dev_stats,
            "canonical_train_dev_prompt_overlap": 0,
        }
    train_features, train_stats = tokenize_records(
        train_records,
        tokenizer,
        args.max_length,
        prompt_source=args.prompt_source,
        critical_parameter_loss=args.critical_parameter_loss,
    )
    eval_features, eval_stats = tokenize_records(
        eval_records, tokenizer, args.max_length, prompt_source=args.prompt_source
    )
    if fixed_plan:
        longest_target = max(
            sum(label != -100 for label in feature["labels"])
            for feature in (*train_features, *eval_features)
        )
        if longest_target > args.behavioral_max_new_tokens:
            raise ValueError("Fixed generation budget is shorter than a complete supervised target")
    selected = stratified_dev_indices(eval_records, args.eval_limit)
    eval_features = [eval_features[index] for index in selected]
    selected_eval_records = [eval_records[index] for index in selected]
    (args.output / "training_script.py").write_bytes(script_path.read_bytes())
    source_snapshots = []
    if args.critical_parameter_loss or args.behavioral_dev_catalog:
        source_files = [script_path, script_path.with_name("critical_parameter_loss.py")]
        if args.behavioral_dev_catalog:
            source_files = behavioral_profile_sources(
                args.behavioral_profile, script_path, scorer_dependencies
            )
        snapshot_dir = args.output / "source-snapshots"
        snapshot_dir.mkdir()
        for index, source_file in enumerate(source_files):
            contents = source_file.read_bytes()
            snapshot = snapshot_dir / f"{index:02d}-{source_file.name}"
            snapshot.write_bytes(contents)
            source_snapshots.append(
                {
                    "source": str(source_file.resolve()),
                    "snapshot": str(snapshot.resolve()),
                    "sha256": hashlib.sha256(contents).hexdigest(),
                }
            )
    provenance = {
        "training_script_sha256": sha256_file(script_path),
        "base_weight_sha256": source_identity,
        "train_sha256": train_sha256,
        "dev_sha256": eval_sha256,
        "train": train_stats,
        "dev": eval_stats,
        "prompt_source": args.prompt_source,
        "official_template_audit": official_template_audit,
        "behavioral_catalog_sha256": catalog_sha256,
        "behavioral_critical_minima": critical_minima,
        "behavioral_critical_minima_sha256": critical_minima_sha256,
        "behavioral_profile": args.behavioral_profile,
        "behavioral_budget": behavioral_budget,
        "behavioral_fixed_plan": fixed_plan,
        "behavioral_fixed_plan_sha256": fixed_plan_sha256,
        "behavioral_dev_workflows_sha256": workflow_sha256,
        "behavioral_dev_workflow_record_ids": (
            [row["id"] for row in workflow_records] if workflow_records else None
        ),
        "training_source_snapshots": source_snapshots,
        "loss_configuration": {
            "critical_parameter_loss": args.critical_parameter_loss,
            "critical_group_weights": (
                __import__(
                    "training.critical_parameter_loss", fromlist=["DEFAULT_WEIGHTS"]
                ).DEFAULT_WEIGHTS
                if args.critical_parameter_loss
                else None
            ),
            "private_metadata_used_only_for_verified_target_loss_spans": (
                args.critical_parameter_loss
            ),
        },
        "runtime_prompt_builder_sha256": (
            sha256_file(
                Path(__file__).resolve().parents[1] / "android_adapter" / "local_provider.py"
            )
            if args.prompt_source == "runtime"
            else None
        ),
        "visible_record_to_runtime_request_sha256": (
            sha256_file(Path(__file__).with_name("evaluate_tools.py"))
            if args.prompt_source == "runtime"
            else None
        ),
        "selected_dev_record_ids": [row["id"] for row in selected_eval_records],
        "parameters": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        },
    }
    (args.output / "input-provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"event": "input_provenance", **provenance}), flush=True)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        args.model,
        dtype=dtype,
        local_files_only=True,
        trust_remote_code=False,
        attn_implementation="sdpa",
    )
    source_fp32_restored = restore_source_fp32_parameters(model, args.model)
    initial_vision_hash = vision_hash(model)
    model.config.text_config.use_cache = False
    model = get_peft_model(
        model,
        LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=args.rank,
            lora_alpha=args.rank * 2,
            lora_dropout=0.05,
            bias="none",
            target_modules=TARGET_MODULE_PROFILES[args.target_modules_profile],
        ),
    )
    visual_trainable = [
        name for name, p in model.named_parameters() if ".visual." in name and p.requires_grad
    ]
    if visual_trainable:
        raise RuntimeError(f"Vision weights must remain frozen: {visual_trainable}")
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.to(device)
    if args.device == "cuda":
        # Text-only SFT never invokes the vision tower. Keep its frozen weights
        # on CPU, then include them unchanged when exporting the full checkpoint.
        model.get_base_model().model.visual.to("cpu")
    model.print_trainable_parameters()
    trainable = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=args.learning_rate, weight_decay=0.01)
    if args.device == "cuda":
        torch.cuda.reset_peak_memory_stats()

    def forward_loss(feature, *, critical=False):
        return assistant_forward_loss(model, feature, torch=torch, device=device, critical=critical)

    def evaluate():
        model.eval()
        rows = []
        with torch.no_grad():
            for feature, record in zip(eval_features, selected_eval_records, strict=True):
                count = sum(x != -100 for x in feature["labels"])
                family = str(record.get("metadata", {}).get("family", "unknown"))
                rows.append((family, float(forward_loss(feature)), count))
        return aggregate_dev_losses(rows)

    def verify_adapter_finite():
        for name, value in model.named_parameters():
            if value.requires_grad and not bool(torch.isfinite(value).all()):
                raise RuntimeError(f"Non-finite learned adapter tensor: {name}")

    def evaluate_behavior(step, adapter_sha256=None, *, autonomous=False):
        from training.behavioral_dev_generation import (
            continuation_is_truncated,
            generate_and_score_dev,
            runtime_turn_eos_ids,
        )

        model.eval()
        model.gradient_checkpointing_disable()
        text_config = model.get_base_model().config.text_config
        previous_cache = text_config.use_cache
        text_config.use_cache = True
        eos_ids = runtime_turn_eos_ids(tokenizer)
        generation_config = {
            "backend": "huggingface",
            "device": str(device),
            "dtype": str(dtype),
            "decoding": "greedy",
            "max_new_tokens": args.behavioral_max_new_tokens,
            "prompt_source": args.prompt_source,
            "tokenizer_sha256": sha256_file(args.model / "tokenizer.json"),
            "source_fp32_restored": source_fp32_restored,
            "scorer_sha256": sha256_file(Path(score_behavior_module.__file__)),
            "runtime_prompt_builder_sha256": provenance["runtime_prompt_builder_sha256"],
            "critical_minima_sha256": critical_minima_sha256,
            "eos_token_ids": eos_ids,
            "pad_token_id": tokenizer.eos_token_id,
            "behavioral_profile": args.behavioral_profile,
            "fixed_plan_sha256": fixed_plan_sha256,
            "max_turns": args.behavioral_max_turns,
        }
        model_identity = {
            "base_weight_sha256": source_identity,
            "optimizer_step": step,
            "adapter_sha256": adapter_sha256,
            "zero_initialized_adapter_equivalent_to_frozen_base": step == 0,
            "generation_source": "model_free_generation",
        }
        prefix = "dev-autonomous" if autonomous else "dev-behavior"
        raw_file = args.output / f"{prefix}-step-{step:04d}-raw.json"

        def generate_visible(prompt, identifier):
            del identifier
            inputs = tokenizer(prompt, add_special_tokens=False, return_tensors="pt").to(device)
            with torch.no_grad():
                generated = model.generate(
                    **inputs,
                    do_sample=False,
                    max_new_tokens=args.behavioral_max_new_tokens,
                    use_cache=True,
                    eos_token_id=eos_ids,
                    pad_token_id=tokenizer.eos_token_id,
                )
            count = int(inputs["input_ids"].shape[1])
            tokens = generated[0, count:]
            return {
                "raw_output": tokenizer.decode(tokens, skip_special_tokens=False),
                "input_tokens": count,
                "output_tokens": int(tokens.numel()),
                "output_truncated": continuation_is_truncated(
                    tokens, max_new_tokens=args.behavioral_max_new_tokens, eos_ids=eos_ids
                ),
            }

        def save_raw(raw):
            raw_file.write_text(
                json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            sample = raw["samples"][-1]
            print(
                json.dumps(
                    {
                        "event": "dev_autonomous_generation"
                        if autonomous
                        else "dev_behavior_generation",
                        "step": step,
                        "completed": len(raw["samples"]),
                        "total": len(workflow_records) if autonomous else len(eval_records),
                        "id": sample["id"],
                        "generation_success": sample["prediction_generation_success"],
                        "elapsed_seconds": sample.get("elapsed_seconds"),
                    }
                ),
                flush=True,
            )

        try:
            if autonomous:
                from training.autonomous_dev_generation import generate_and_score_autonomous_dev

                if not fixed_plan or not workflow_records or not score_workflow_report:
                    raise ValueError(
                        "Autonomous dev requires the complete fixed V5 workflow profile"
                    )
                scored = generate_and_score_autonomous_dev(
                    workflow_records,
                    dataset_sha256=workflow_sha256,
                    generation_config=generation_config,
                    model_identity=model_identity,
                    generate_visible=generate_visible,
                    evaluate_workflow_report=score_workflow_report,
                    catalog=catalog,
                    max_turns=args.behavioral_max_turns,
                    on_prediction=save_raw,
                )
            else:
                scored, _ = generate_and_score_dev(
                    eval_records,
                    dataset_sha256=eval_sha256,
                    generation_config=generation_config,
                    generate_visible=generate_visible,
                    build_visible_prompt=lambda row: render_prompt(
                        row, tokenizer, prompt_source=args.prompt_source
                    ),
                    score_report=score_behavior_report,
                    catalog=catalog,
                    model_identity=model_identity,
                    on_prediction=save_raw,
                )
            scored["raw_report"] = str(raw_file.resolve())
            scored["raw_report_sha256"] = sha256_file(raw_file)
            scored_file = args.output / f"{prefix}-step-{step:04d}-scored.json"
            scored_file.write_text(
                json.dumps(scored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            return scored
        finally:
            text_config.use_cache = previous_cache
            model.gradient_checkpointing_enable(
                gradient_checkpointing_kwargs={"use_reentrant": False}
            )

    def save_checkpoint(step):
        verify_adapter_finite()
        checkpoint_dir = args.output / "checkpoints" / f"step-{step:04d}"
        model.save_pretrained(checkpoint_dir, safe_serialization=True)
        tokenizer.save_pretrained(checkpoint_dir)
        preserve_base_tokenizer(args.model, checkpoint_dir)
        metrics = evaluate()
        record = {
            "step": step,
            "directory": str(checkpoint_dir.resolve()),
            "adapter_sha256": sha256_file(checkpoint_dir / "adapter_model.safetensors"),
            "metrics": metrics,
            "checkpoint_kind": "adapter_only_not_exact_training_resume",
            "train_sha256": train_sha256,
            "dev_sha256": eval_sha256,
            "sampling": describe_training_sampling(
                train_records,
                sampled_indices,
                minimum_ordinary_fraction=args.minimum_ordinary_fraction,
            ),
        }
        if args.behavioral_dev_catalog:
            record["report"] = evaluate_behavior(step, record["adapter_sha256"])
            if fixed_plan:
                record["autonomous_report"] = evaluate_behavior(
                    step, record["adapter_sha256"], autonomous=True
                )
        (checkpoint_dir / "dev_metrics.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        with (args.output / "dev_loss.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
        print(json.dumps({"event": "dev_checkpoint", **record}), flush=True)
        return record

    start = time.monotonic()
    gpu_before = gpu_memory_snapshot() if args.device == "cuda" else []
    before = evaluate()
    (args.output / "dev_baseline.json").write_text(
        json.dumps(before, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"event": "eval_before", **before}), flush=True)
    before_behavior = evaluate_behavior(0) if args.behavioral_dev_catalog else None
    before_autonomous = evaluate_behavior(0, autonomous=True) if fixed_plan else None
    if fixed_plan:
        from training.behavioral_plan import selection_options

        behavioral_selection_options = selection_options(fixed_plan)
        behavioral_selection_options["autonomous_baseline"] = before_autonomous
    else:
        behavioral_selection_options = {
            "gradient_accumulation": args.gradient_accumulation,
            "minimum_ordinary_fraction": args.minimum_ordinary_fraction,
            "critical_family_minima": critical_minima,
            **behavioral_budget,
        }
    if before_behavior:
        from training.behavioral_dev_selection import summarize_paired_behavior

        summarize_paired_behavior(before_behavior, before_behavior)
    epoch = 0

    def training_order(epoch_number):
        if args.minimum_ordinary_fraction:
            return retention_balanced_training_order(
                train_records,
                seed=args.seed + epoch_number,
                minimum_ordinary_fraction=args.minimum_ordinary_fraction,
            )
        return balanced_training_order(train_records, seed=args.seed + epoch_number)

    order = training_order(epoch)
    cursor = 0
    sampled_indices = []
    sampled_family_counts: dict[str, int] = {}
    losses = []
    checkpoints = []
    early_stopped = False
    optimizer.zero_grad(set_to_none=True)
    for step in range(1, args.steps + 1):
        step_started = time.monotonic()
        model.train()
        step_loss = 0.0
        step_samples = []
        warmup = max(1, min(10, args.steps // 10))
        progress = max(0, step - warmup) / max(1, args.steps - warmup)
        factor = step / warmup if step <= warmup else 0.5 * (1 + math.cos(math.pi * progress))
        for group in optimizer.param_groups:
            group["lr"] = args.learning_rate * factor
        for _ in range(args.gradient_accumulation):
            if cursor == len(order):
                epoch += 1
                order = training_order(epoch)
                cursor = 0
            sampled_index = order[cursor]
            feature = train_features[sampled_index]
            sampled_record = train_records[sampled_index]
            family = str(sampled_record.get("metadata", {}).get("family", "unknown"))
            sampled_indices.append(sampled_index)
            sampled_family_counts[family] = sampled_family_counts.get(family, 0) + 1
            step_samples.append({"id": sampled_record["id"], "family": family})
            cursor += 1
            loss = forward_loss(feature, critical=args.critical_parameter_loss)
            if not torch.isfinite(loss):
                raise RuntimeError("Non-finite training loss; refusing to save an invalid adapter")
            step_loss += float(loss.detach()) / args.gradient_accumulation
            (loss / args.gradient_accumulation).backward()
        grad_norm = float(torch.nn.utils.clip_grad_norm_(trainable, 1.0))
        if not math.isfinite(grad_norm):
            raise RuntimeError("Non-finite gradient norm; refusing to update model weights")
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        record = {
            "step": step,
            "loss": step_loss,
            "gradient_norm": grad_norm,
            "learning_rate": optimizer.param_groups[0]["lr"],
            "elapsed_seconds": time.monotonic() - start,
            "step_seconds": time.monotonic() - step_started,
            "samples": step_samples,
        }
        losses.append(record)
        with (args.output / "loss.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
        print(json.dumps(record), flush=True)
        if args.checkpoint_every and (step % args.checkpoint_every == 0 or step == args.steps):
            checkpoints.append(save_checkpoint(step))
            if args.behavioral_dev_catalog:
                from training.behavioral_dev_selection import select_behavioral_checkpoint

                decision = select_behavioral_checkpoint(
                    before_behavior,
                    checkpoints,
                    **behavioral_selection_options,
                )
            else:
                decision = select_dev_checkpoint(
                    before,
                    checkpoints,
                    patience=args.early_stopping_patience,
                    min_delta=args.early_stopping_min_delta,
                )
            print(json.dumps({"event": "checkpoint_selection", **decision}), flush=True)
            if decision.get("should_stop", False):
                early_stopped = step < args.steps
                break
    actual_steps = losses[-1]["step"]
    selection = None
    checkpoint_restoration = None
    if checkpoints:
        if args.behavioral_dev_catalog:
            selection = select_behavioral_checkpoint(
                before_behavior,
                checkpoints,
                **behavioral_selection_options,
            )
        else:
            selection = select_dev_checkpoint(
                before,
                checkpoints,
                patience=args.early_stopping_patience,
                min_delta=args.early_stopping_min_delta,
            )
        if selection["selected_step"] is None:
            report = {
                **provenance,
                "genuine_weight_training": True,
                "qualified_for_deployment": False,
                "training_type": "LoRA assistant-only supervised fine-tuning",
                "steps": actual_steps,
                "planned_steps": args.steps,
                "training_sampling": describe_training_sampling(
                    train_records,
                    sampled_indices,
                    minimum_ordinary_fraction=args.minimum_ordinary_fraction,
                ),
                "selected_checkpoint_training_sampling": None,
                "selected_checkpoint_step": None,
                "checkpoint_selection": selection,
                "dev_checkpoint_history": checkpoints,
                "eval_before": before,
                "dev_behavior_baseline": before_behavior,
                "dev_autonomous_baseline": before_autonomous,
                "adapter_directory": None,
                "merged_directory": None,
                "reason": (
                    "No dev candidate preserves ordinary abilities and improves tool behavior"
                ),
                "elapsed_seconds": time.monotonic() - start,
                "private_user_data_used": False,
                "cloud_training_used": False,
                "datasets_unchanged_during_training": (
                    sha256_file(args.train) == train_sha256
                    and sha256_file(args.eval) == eval_sha256
                ),
                "peak_cuda_allocated_bytes": (
                    torch.cuda.max_memory_allocated() if args.device == "cuda" else None
                ),
                "peak_cuda_reserved_bytes": (
                    torch.cuda.max_memory_reserved() if args.device == "cuda" else None
                ),
            }
            (args.output / "training_report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(
                json.dumps({"event": "completed_without_qualified_adapter", "steps": actual_steps}),
                flush=True,
            )
            return
        chosen = next(row for row in checkpoints if row["step"] == selection["selected_step"])
        checkpoint_restoration = restore_saved_adapter(
            model, Path(chosen["directory"]), chosen["adapter_sha256"]
        )
        after = chosen["metrics"]
    else:
        after = evaluate()
    verify_adapter_finite()
    gpu_after = gpu_memory_snapshot() if args.device == "cuda" else []
    lora_b_norms = {
        name: float(value.detach().float().norm())
        for name, value in model.named_parameters()
        if ".lora_B." in name and value.requires_grad
    }
    if not lora_b_norms or not all(math.isfinite(value) for value in lora_b_norms.values()):
        raise RuntimeError("Adapter updates are absent or non-finite")
    if not any(value > 0 for value in lora_b_norms.values()):
        raise RuntimeError("No LoRA B weights changed from their zero initialization")
    if any(sha256_file(Path(row["source"])) != row["sha256"] for row in source_snapshots):
        raise RuntimeError("Training dependency source changed during the frozen run")
    if args.behavioral_dev_catalog and sha256_file(args.behavioral_dev_catalog) != catalog_sha256:
        raise RuntimeError("Frozen behavioral catalog changed during the run")
    if args.behavioral_critical_minima and (
        sha256_file(args.behavioral_critical_minima) != critical_minima_sha256
    ):
        raise RuntimeError("Fixed critical behavior gate changed during the run")
    if fixed_plan and (
        sha256_file(args.behavioral_plan) != fixed_plan_sha256
        or sha256_file(args.behavioral_dev_workflows) != workflow_sha256
    ):
        raise RuntimeError("Fixed behavioral plan or dev workflows changed during the run")
    adapter_dir = args.output / "adapter"
    model.save_pretrained(adapter_dir, safe_serialization=True)
    tokenizer.save_pretrained(adapter_dir)
    preserve_base_tokenizer(args.model, adapter_dir)
    if (
        checkpoint_restoration
        and sha256_file(adapter_dir / "adapter_model.safetensors")
        != checkpoint_restoration["adapter_sha256"]
    ):
        raise RuntimeError("final adapter differs from the selected checkpoint")
    # The original multimodal class remains intact; merging modifies only the
    # trained language projection weights and keeps the original vision tower.
    model.to("cpu")
    if args.device == "cuda":
        torch.cuda.empty_cache()
    merged = model.merge_and_unload(safe_merge=True)
    export_frozen_restored = restore_frozen_source_parameters(merged, args.model)
    merged.config.text_config.use_cache = True
    merged.generation_config.use_cache = True
    final_vision_hash = vision_hash(merged)
    if initial_vision_hash != final_vision_hash:
        raise RuntimeError("Vision weights changed unexpectedly")
    merged_dir = None
    export_mtp_completion = None
    if args.export_merged:
        merged_dir = args.output / "merged"
        merged.save_pretrained(merged_dir, safe_serialization=True, max_shard_size="2GB")
        export_mtp_completion = complete_source_mtp_export(args.model, merged_dir)
        tokenizer.save_pretrained(merged_dir)
        preserve_base_tokenizer(args.model, merged_dir)
        # Keep the original image/video preprocessing metadata for future use.
        for source in args.model.glob("*preprocessor_config.json"):
            (merged_dir / source.name).write_bytes(source.read_bytes())
    adapter_file = adapter_dir / "adapter_model.safetensors"
    report = {
        "genuine_weight_training": True,
        "qualified_for_deployment": selection.get("accepted") if before_behavior else None,
        "training_type": "LoRA assistant-only supervised fine-tuning",
        "base_model": "Qwen/Qwen3.5-0.8B",
        "base_revision": "2fc06364715b967f1860aea9cf38778875588b17",
        "base_weight_sha256": source_identity,
        "source_fp32_restored_before_training": source_fp32_restored,
        "frozen_parameters_restored_on_export": export_frozen_restored,
        "frozen_mtp_export_completion": export_mtp_completion,
        "safe_merge_used": True,
        "train_sha256": train_sha256,
        "eval_sha256": eval_sha256,
        "datasets_unchanged_during_training": (
            sha256_file(args.train) == train_sha256 and sha256_file(args.eval) == eval_sha256
        ),
        "train": train_stats,
        "training_sampling": describe_training_sampling(
            train_records,
            sampled_indices,
            minimum_ordinary_fraction=args.minimum_ordinary_fraction,
        ),
        "selected_checkpoint_training_sampling": describe_training_sampling(
            train_records,
            sampled_indices[
                : (selection["selected_step"] if selection else actual_steps)
                * args.gradient_accumulation
            ],
            minimum_ordinary_fraction=args.minimum_ordinary_fraction,
        ),
        "prompt_source": args.prompt_source,
        "loss_configuration": provenance["loss_configuration"],
        "training_source_snapshots": source_snapshots,
        "behavioral_catalog_sha256": catalog_sha256,
        "behavioral_critical_minima_sha256": critical_minima_sha256,
        "behavioral_budget": provenance["behavioral_budget"],
        "dev_behavior_baseline": before_behavior,
        "dev_autonomous_baseline": before_autonomous,
        "behavioral_profile": args.behavioral_profile,
        "behavioral_fixed_plan": fixed_plan,
        "behavioral_fixed_plan_sha256": fixed_plan_sha256,
        "behavioral_dev_workflows_sha256": workflow_sha256,
        "official_template_audit": official_template_audit,
        "runtime_prompt_builder_sha256": provenance["runtime_prompt_builder_sha256"],
        "visible_record_to_runtime_request_sha256": provenance[
            "visible_record_to_runtime_request_sha256"
        ],
        "eval": eval_stats,
        "eval_before": before,
        "eval_after": after,
        "loss_probe_record_ids": [eval_records[index]["id"] for index in selected],
        "steps": actual_steps,
        "planned_steps": args.steps,
        "selected_checkpoint_step": selection["selected_step"] if selection else actual_steps,
        "checkpoint_restoration": checkpoint_restoration,
        "dev_checkpoint_history": checkpoints,
        "early_stopped": early_stopped,
        "checkpoint_selection": selection,
        "early_stopping_patience": args.early_stopping_patience,
        "early_stopping_min_delta": args.early_stopping_min_delta,
        "gradient_accumulation": args.gradient_accumulation,
        "rank": args.rank,
        "seed": args.seed,
        "learning_rate": args.learning_rate,
        "max_length": args.max_length,
        "dtype": str(dtype),
        "device": str(device),
        "trainable_parameters": sum(p.numel() for p in trainable),
        "target_modules": TARGET_MODULE_PROFILES[args.target_modules_profile],
        "target_modules_profile": args.target_modules_profile,
        "adapter_sha256": sha256_file(adapter_file),
        "adapter_nonzero_update": any(value > 0 for value in lora_b_norms.values()),
        "lora_b_weight_norms": lora_b_norms,
        "vision_weights_preserved": initial_vision_hash == final_vision_hash,
        "tokenizer_artifacts_preserved": all(
            sha256_file(args.model / name) == sha256_file(adapter_dir / name)
            for name in ("tokenizer.json", "tokenizer_config.json", "chat_template.jinja")
        ),
        "vision_tower_kept_on_cpu_during_text_training": args.device == "cuda",
        "vision_sha256": final_vision_hash,
        "merged_directory": str(merged_dir.resolve()) if merged_dir else None,
        "elapsed_seconds": time.monotonic() - start,
        "private_user_data_used": False,
        "cloud_training_used": False,
        "versions": {
            name: importlib.metadata.version(name) for name in ("torch", "transformers", "peft")
        },
        "gpu_memory_before_training": gpu_before,
        "gpu_memory_after_training": gpu_after,
        "mean_step_seconds": sum(record["step_seconds"] for record in losses) / len(losses),
    }
    if args.device == "cuda":
        report["peak_cuda_allocated_bytes"] = torch.cuda.max_memory_allocated()
        report["peak_cuda_reserved_bytes"] = torch.cuda.max_memory_reserved()
    (args.output / "training_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "event": "completed",
                "report": str((args.output / "training_report.json").resolve()),
                "steps": actual_steps,
                "selected_checkpoint_step": report["selected_checkpoint_step"],
                "eval_before": before,
                "eval_after": after,
                "adapter_sha256": report["adapter_sha256"],
                "vision_weights_preserved": report["vision_weights_preserved"],
                "elapsed_seconds": report["elapsed_seconds"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
