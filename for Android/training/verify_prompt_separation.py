"""Check frozen train/eval separation after the actual official tokenizer template."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--eval", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from train_lora import read_records, sha256_file
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        args.model, local_files_only=True, trust_remote_code=False
    )

    def encoded_prompts(path):
        result = {}
        for record in read_records(path):
            prompt = tokenizer.apply_chat_template(
                record["messages"],
                tools=record.get("tools") or None,
                add_generation_prompt=True,
                enable_thinking=False,
                tokenize=False,
            )
            tokens = tokenizer(prompt, add_special_tokens=False)["input_ids"]
            signature = hashlib.sha256(json.dumps(tokens).encode("utf-8")).hexdigest()
            result.setdefault(signature, []).append(record["id"])
        return result

    train = encoded_prompts(args.train)
    evaluation = encoded_prompts(args.eval)
    overlaps = [
        {"train_ids": train[signature], "eval_ids": evaluation[signature]}
        for signature in sorted(set(train) & set(evaluation))
    ]
    report = {
        "passed": not overlaps,
        "canonical_tokenized_prompt_overlaps": overlaps,
        "unique_train_prompts": len(train),
        "unique_eval_prompts": len(evaluation),
        "train_sha256": sha256_file(args.train),
        "eval_sha256": sha256_file(args.eval),
        "template": "original Qwen3.5 enable_thinking=False",
        "expected_answers_or_targets_used_in_prompt": False,
        "cuda_used": False,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)
    if not report["passed"]:
        raise SystemExit("Train/eval overlap exists after canonical prompt tokenization")


if __name__ == "__main__":
    main()
