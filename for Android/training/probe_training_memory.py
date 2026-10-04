"""Measure full V5 backward feasibility without optimizer updates or saved adapters."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import sys
import time
from collections import Counter
from pathlib import Path


def select_memory_probe_cases(records: list[dict], features: list[dict]) -> list[dict]:
    if len(records) != len(features) or len(records) < 2:
        raise ValueError("The memory probe requires at least two aligned complete examples")
    if any(row.get("split") not in {"train", "dev"} for row in records):
        raise ValueError("Memory feasibility uses only train/dev, never fresh final records")
    ids = [row.get("id") for row in records]
    if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("Memory probe examples require unique original IDs")
    measured = [
        {
            "record": row,
            "feature": feature,
            "sequence_tokens": len(feature["input_ids"]),
            "supervised_tokens": sum(value != -100 for value in feature["labels"]),
        }
        for row, feature in zip(records, features, strict=True)
    ]
    indices = list(
        dict.fromkeys(
            [
                max(
                    range(len(measured)),
                    key=lambda index: (measured[index]["sequence_tokens"], -index),
                ),
                max(
                    range(len(measured)),
                    key=lambda index: (measured[index]["supervised_tokens"], -index),
                ),
            ]
        )
    )
    if len(indices) == 1:
        indices.append(
            max(
                (index for index in range(len(measured)) if index not in indices),
                key=lambda index: (
                    measured[index]["sequence_tokens"],
                    measured[index]["supervised_tokens"],
                    -index,
                ),
            )
        )
    return [measured[index] for index in indices]


def trainable_parameter_hash(model, *, torch) -> str:
    digest = hashlib.sha256()
    for name, parameter in sorted(model.named_parameters()):
        if parameter.requires_grad:
            digest.update(name.encode("utf-8"))
            digest.update(str(parameter.dtype).encode())
            digest.update(parameter.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def run_backward_probe(
    model,
    cases: list[dict],
    *,
    forward_loss,
    torch,
    device,
    gradient_accumulation: int,
    on_case=None,
) -> dict:
    if type(gradient_accumulation) is not int or gradient_accumulation < 1:
        raise ValueError("The memory probe requires positive gradient accumulation")
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    if not trainable:
        raise ValueError("The memory probe requires the actual trainable LoRA parameters")
    before = trainable_parameter_hash(model, torch=torch)
    report = {
        "passed": False,
        "optimizer_updates": 0,
        "optimizer_constructed": False,
        "optimizer_step_tested": False,
        "optimizer_intermediate_memory_reserved": False,
        "all_dataset_case_memory_tested": False,
        "feasibility_scope": "selected complete backward cases plus Adam moments; "
        "not full optimizer step or all dataset cases",
        "adapter_exported": False,
        "parameter_hash_before": before,
        "gradient_accumulation": gradient_accumulation,
        "cases": [],
    }
    # Reserve the Adam first/second-moment tensor memory without constructing an
    # optimizer. The gradients and complete model activations are actual tensors.
    state_reserve = [(torch.zeros_like(value), torch.zeros_like(value)) for value in trainable]
    report["optimizer_state_equivalent_reserved_bytes"] = sum(
        tensor.numel() * tensor.element_size() for pair in state_reserve for tensor in pair
    )
    model.train()
    try:
        for case in cases:
            model.zero_grad(set_to_none=True)
            if str(device).startswith("cuda"):
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats()
            started = time.monotonic()
            losses = []
            for _ in range(gradient_accumulation):
                loss = forward_loss(case["feature"])
                if not bool(torch.isfinite(loss)):
                    raise RuntimeError("Memory probe has a non-finite actual training loss")
                losses.append(float(loss.detach()))
                (loss / gradient_accumulation).backward()
                del loss
            norm = float(torch.nn.utils.clip_grad_norm_(trainable, 1.0))
            if not math.isfinite(norm):
                raise RuntimeError("Memory probe accumulated a non-finite actual gradient")
            evidence = {
                "id": case["record"]["id"],
                "split": case["record"]["split"],
                "sequence_tokens": case["sequence_tokens"],
                "supervised_tokens": case["supervised_tokens"],
                "complete_input_used": True,
                "truncated_records": 0,
                "micro_batch_backward_passes": gradient_accumulation,
                "losses": losses,
                "gradient_norm": norm,
                "elapsed_seconds": time.monotonic() - started,
            }
            if str(device).startswith("cuda"):
                torch.cuda.synchronize()
                evidence.update(
                    peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                    peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                    allocated_bytes=torch.cuda.memory_allocated(),
                    reserved_bytes=torch.cuda.memory_reserved(),
                    device_total_bytes=torch.cuda.get_device_properties(device).total_memory,
                )
            report["cases"].append(evidence)
            if on_case:
                on_case(copy.deepcopy(report))
            model.zero_grad(set_to_none=True)
        report["parameter_hash_after"] = trainable_parameter_hash(model, torch=torch)
        if report["parameter_hash_after"] != before:
            raise RuntimeError("A no-update memory probe changed the adapter parameters")
        report["passed"] = True
        return report
    finally:
        model.zero_grad(set_to_none=True)
        del state_reserve


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("model", "train", "dev", "plan", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(root / "src"), str(root / "for Android")]
    from training.behavioral_plan import read_behavioral_plan
    from training.evaluate_general_v5 import sha256_file, write_report
    from training.train_lora import (
        TARGET_MODULE_PROFILES,
        assistant_forward_loss,
        read_records,
        restore_source_fp32_parameters,
        tokenize_records,
        verify_source_checkpoint,
        vision_hash,
    )

    plan, plan_sha = read_behavioral_plan(args.plan)
    if (
        sha256_file(args.train) != plan["train_sha256"]
        or sha256_file(args.dev) != plan["dev_sha256"]
    ):
        raise ValueError("Memory probe inputs differ from the frozen V5 training plan")
    if args.output.exists():
        raise FileExistsError("Memory probe output must be fresh")
    records = [*read_records(args.train), *read_records(args.dev)]
    if Counter(row["split"] for row in records) != {"train": 1200, "dev": 200}:
        raise ValueError("Memory probe requires all complete frozen train/dev records")
    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("The reviewed V5 memory probe requires CUDA BF16")
    random.seed(plan["training_seed"])
    torch.manual_seed(plan["training_seed"])
    identity = verify_source_checkpoint(args.model)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model, local_files_only=True, trust_remote_code=False
    )
    features, stats = tokenize_records(
        records,
        tokenizer,
        plan["max_length"],
        prompt_source="runtime",
        critical_parameter_loss=True,
    )
    selected = select_memory_probe_cases(records, features)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {
        "passed": False,
        "optimizer_updates": 0,
        "adapter_exported": False,
        "fixed_plan_sha256": plan_sha,
        "base_weight_sha256": identity,
        "train_sha256": plan["train_sha256"],
        "dev_sha256": plan["dev_sha256"],
        "script_sha256": sha256_file(Path(__file__)),
        "shared_training_loss_sha256": sha256_file(Path(__file__).with_name("train_lora.py")),
        "tokenization": stats,
        "selected_cases": [
            {key: value for key, value in row.items() if key not in {"feature", "record"}}
            | {"id": row["record"]["id"], "split": row["record"]["split"]}
            for row in selected
        ],
    }
    path = args.output / "memory-probe.json"
    write_report(path, report)
    try:
        model = Qwen3_5ForConditionalGeneration.from_pretrained(
            args.model,
            dtype=torch.bfloat16,
            local_files_only=True,
            trust_remote_code=False,
            attn_implementation="sdpa",
        )
        restored = restore_source_fp32_parameters(model, args.model)
        initial_vision = vision_hash(model)
        model.config.text_config.use_cache = False
        model = get_peft_model(
            model,
            LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                r=plan["rank"],
                lora_alpha=plan["alpha"],
                lora_dropout=plan["dropout"],
                bias="none",
                target_modules=TARGET_MODULE_PROFILES[plan["target_modules_profile"]],
            ),
        )
        if any(
            ".visual." in name and value.requires_grad for name, value in model.named_parameters()
        ):
            raise RuntimeError("Vision parameters must remain frozen in the actual V5 memory probe")
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.to("cuda")
        model.get_base_model().model.visual.to("cpu")
        report["source_fp32_restored"] = restored
        report["vision_hash_before"] = initial_vision
        report["cuda_device"] = torch.cuda.get_device_name()

        def progress(partial):
            report["probe"] = partial
            write_report(path, report)
            print(json.dumps({"event": "memory_probe_case", **partial["cases"][-1]}), flush=True)

        report["probe"] = run_backward_probe(
            model,
            selected,
            forward_loss=lambda feature: assistant_forward_loss(
                model,
                feature,
                torch=torch,
                device="cuda",
                critical=True,
            ),
            torch=torch,
            device="cuda",
            gradient_accumulation=plan["gradient_accumulation"],
            on_case=progress,
        )
        report["vision_hash_after"] = vision_hash(model.get_base_model())
        if report["vision_hash_after"] != initial_vision:
            raise RuntimeError("No-update memory probe changed the frozen vision checkpoint")
        report["passed"] = True
        write_report(path, report)
    except Exception as failure:
        report["error"] = f"{type(failure).__name__}: {failure}"
        if torch.cuda.is_available():
            report["failure_peak_allocated_bytes"] = torch.cuda.max_memory_allocated()
            report["failure_peak_reserved_bytes"] = torch.cuda.max_memory_reserved()
        write_report(path, report)
        raise


if __name__ == "__main__":
    main()
