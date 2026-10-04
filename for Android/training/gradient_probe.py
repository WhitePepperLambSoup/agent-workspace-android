"""Measure Qwen3.5 LoRA backward support and memory without saving any weights.

This is an environment smoke probe over artificial token IDs. It is not a tool
training dataset or a trained model and is never used for evaluation claims.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tokens", type=int, default=768)
    args = parser.parse_args()

    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from train_lora import TARGET_MODULES
    from transformers import Qwen3_5ForConditionalGeneration

    torch.manual_seed(20261001)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        args.model,
        local_files_only=True,
        trust_remote_code=False,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    model.config.text_config.use_cache = False
    model = get_peft_model(
        model,
        LoraConfig(task_type=TaskType.CAUSAL_LM, r=8, lora_alpha=16, target_modules=TARGET_MODULES),
    )
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.to("cuda")
    model.get_base_model().model.visual.to("cpu")
    model.train()
    torch.cuda.reset_peak_memory_stats()
    inputs = torch.randint(100, 20000, (1, args.tokens), device="cuda")
    trainable = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=0.0002)
    torch.cuda.synchronize()
    started = time.monotonic()
    output = model(input_ids=inputs, use_cache=False, logits_to_keep=32)
    loss = torch.nn.functional.cross_entropy(
        output.logits[:, :-1].reshape(-1, output.logits.shape[-1]).float(),
        inputs[:, -31:].reshape(-1),
    )
    loss.backward()
    norm = float(torch.nn.utils.clip_grad_norm_(trainable, 1.0))
    optimizer.step()
    torch.cuda.synchronize()
    report = {
        "purpose": "artificial-token gradient/environment smoke probe only",
        "saved_weights": False,
        "tool_training_claim": False,
        "tokens": args.tokens,
        "loss": float(loss.detach()),
        "gradient_norm": norm,
        "elapsed_seconds": time.monotonic() - started,
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(),
        "peak_cuda_reserved_bytes": torch.cuda.max_memory_reserved(),
        "nonzero_lora_b": any(
            bool(p.detach().count_nonzero())
            for name, p in model.named_parameters()
            if ".lora_B." in name
        ),
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
