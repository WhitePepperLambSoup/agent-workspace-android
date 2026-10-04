"""Verify merged SFT language weights changed and frozen weights stayed equal."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--merged", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import torch
    from safetensors import safe_open
    from train_lora import TARGET_MODULES, sha256_file

    def files(directory):
        index = directory / "model.safetensors.index.json"
        if index.exists():
            entries = json.loads(index.read_text(encoding="utf-8"))["weight_map"]
            return {name: directory / file for name, file in entries.items()}
        file = directory / "model.safetensors"
        with safe_open(file, framework="pt", device="cpu") as stream:
            keys = list(stream.keys())
            return {name: file for name in keys}

    base_files = files(args.base)
    merged_files = files(args.merged)
    changed = []
    unexpected_changes = []
    maximum_deltas = {}
    checked_visual = 0
    checked_mtp = 0
    checked_frozen = 0
    checked = 0
    # Open each shard once. All tensor access is on CPU and no model is loaded.
    from contextlib import ExitStack

    with ExitStack() as stack:
        opened = {
            path: stack.enter_context(safe_open(path, framework="pt", device="cpu"))
            for path in set(base_files.values()) | set(merged_files.values())
        }
        for name in sorted(merged_files):
            if name not in base_files:
                unexpected_changes.append({"name": name, "reason": "new unexpected base tensor"})
                continue
            original = opened[base_files[name]].get_tensor(name)
            final = opened[merged_files[name]].get_tensor(name)
            checked += 1
            if not bool(torch.isfinite(final).all()):
                unexpected_changes.append({"name": name, "reason": "non-finite exported tensor"})
                continue
            if name.startswith("model.visual."):
                checked_visual += 1
            if name.startswith("mtp."):
                checked_mtp += 1
            module_name = name.removesuffix(".weight")
            targeted = (
                name.endswith(".weight") and re.fullmatch(TARGET_MODULES, module_name) is not None
            )
            if not targeted:
                checked_frozen += 1
                if original.dtype != final.dtype or not torch.equal(original, final):
                    unexpected_changes.append(
                        {"name": name, "reason": "frozen/non-target tensor dtype or value changed"}
                    )
                continue
            if torch.equal(original, final):
                continue
            changed.append(name)
            maximum_deltas[name] = float((original.float() - final.float()).abs().max())
    missing = sorted(set(base_files) - set(merged_files))
    # HF does not load the MTP head, but native inference still requires it.
    # No source tensor, including frozen MTP weights, may be silently omitted.
    unexplained_missing = missing
    report = {
        "passed": bool(changed)
        and checked_visual > 0
        and not unexpected_changes
        and not unexplained_missing,
        "checked_tensors": checked,
        "changed_language_projection_tensors": len(changed),
        "changed_names": changed,
        "maximum_absolute_deltas": maximum_deltas,
        "checked_vision_tensors": checked_visual,
        "checked_mtp_tensors": checked_mtp,
        "checked_frozen_tensors": checked_frozen,
        "frozen_tensors_preserved_exactly": not unexpected_changes
        and not missing
        and checked_frozen > 0,
        "vision_tensors_preserved": not any(
            entry["name"].startswith("model.visual.") for entry in unexpected_changes
        )
        and not any(name.startswith("model.visual.") for name in missing)
        and checked_visual > 0,
        "mtp_tensors_preserved_exactly": not any(
            entry["name"].startswith("mtp.") for entry in unexpected_changes
        )
        and not any(name.startswith("mtp.") for name in missing)
        and checked_mtp > 0,
        "source_tensor_names_complete": not missing and set(merged_files) == set(base_files),
        "unexpected_changes": unexpected_changes,
        "unused_mtp_tensors_omitted": [name for name in missing if name.startswith("mtp.")],
        "unexplained_missing_tensors": unexplained_missing,
        "tokenizer_bytes_preserved": all(
            sha256_file(args.base / name) == sha256_file(args.merged / name)
            for name in ("tokenizer.json", "tokenizer_config.json", "chat_template.jinja")
        ),
        "base_weight_sha256": {path.name: sha256_file(path) for path in set(base_files.values())},
        "merged_weight_sha256": {
            path.name: sha256_file(path) for path in set(merged_files.values())
        },
        "private_user_data_used": False,
        "cuda_used": False,
    }
    report["passed"] = report["passed"] and report["tokenizer_bytes_preserved"]
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: value
                for key, value in report.items()
                if key
                not in {"changed_names", "maximum_absolute_deltas", "unused_mtp_tensors_omitted"}
            }
        ),
        flush=True,
    )
    if not report["passed"]:
        raise SystemExit("Merged weight verification failed; see the saved report")


if __name__ == "__main__":
    main()
