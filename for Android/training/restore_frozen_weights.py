"""Restore exact non-LoRA source tensors after mixed-precision HF model loading.

The original exported checkpoint and failed verification report are preserved as
evidence. Learned language projection tensors are kept unchanged. This is a CPU
export correction, not a new training run or a relaxation of verification.
"""

from __future__ import annotations

import argparse
import gc
import json
import re
import shutil
from contextlib import ExitStack
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--merged", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--failed-verification", type=Path)
    args = parser.parse_args()

    import torch
    from safetensors import safe_open
    from safetensors.torch import save_file
    from train_lora import TARGET_MODULES, sha256_file

    index = json.loads((args.base / "model.safetensors.index.json").read_text(encoding="utf-8"))
    source_files = {name: args.base / file for name, file in index["weight_map"].items()}
    merged_file = args.merged / "model.safetensors"
    before_sha = sha256_file(merged_file)
    args.evidence.mkdir(parents=True, exist_ok=True)
    backup = args.evidence / "merged-before-frozen-restoration.safetensors"
    if backup.exists():
        parser.error("original export evidence already exists; refusing to overwrite it")
    shutil.copyfile(merged_file, backup)
    if args.failed_verification:
        shutil.copyfile(
            args.failed_verification,
            args.evidence / "merged-weight-verification-before-restoration.json",
        )
    restored = []
    changed_targets = 0
    target_count = 0
    frozen_count = 0
    temporary = args.merged / "model.safetensors.frozen-restoration.tmp"
    tensors = {}
    with ExitStack() as stack:
        source_streams = {
            path: stack.enter_context(safe_open(path, framework="pt", device="cpu"))
            for path in set(source_files.values())
        }
        final_stream = stack.enter_context(safe_open(merged_file, framework="pt", device="cpu"))
        names = list(final_stream.keys())
        for name in names:
            if name not in source_files:
                raise ValueError(f"Unrecognized exported tensor: {name}")
            original = source_streams[source_files[name]].get_tensor(name)
            current = final_stream.get_tensor(name)
            if not bool(torch.isfinite(current).all()):
                raise ValueError(f"Non-finite exported tensor: {name}")
            if current.shape != original.shape:
                raise ValueError(f"Exported tensor shape changed: {name}")
            module = name.removesuffix(".weight")
            targeted = name.endswith(".weight") and re.fullmatch(TARGET_MODULES, module) is not None
            if targeted:
                target_count += 1
                changed_targets += int(not torch.equal(original, current))
                tensors[name] = current
            else:
                frozen_count += 1
                if original.dtype != current.dtype or not torch.equal(original, current):
                    cast_only = torch.equal(original.to(current.dtype), current)
                    restored.append(
                        {
                            "name": name,
                            "source_dtype": str(original.dtype),
                            "exported_dtype_before": str(current.dtype),
                            "matches_source_cast_to_export_dtype": cast_only,
                            "reason": "mixed-precision source load rounding"
                            if cast_only
                            else "non-target drift",
                        }
                    )
                tensors[name] = original
        if changed_targets == 0:
            raise ValueError("No genuine learned projection updates remain")
        save_file(tensors, temporary, metadata={"format": "pt"})
        # Release all views before replacing a mapped file on Windows.
        tensors.clear()
        del original, current
    gc.collect()
    temporary.replace(merged_file)
    after_sha = sha256_file(merged_file)
    report = {
        "correction": "exact frozen source tensor restoration after mixed-precision loading",
        "original_training_report_modified": False,
        "original_export_preserved": str(backup.resolve()),
        "before_weight_sha256": before_sha,
        "after_weight_sha256": after_sha,
        "target_projection_count": target_count,
        "genuine_changed_target_projections_preserved": changed_targets,
        "all_non_target_tensors_copied_exactly_from_source": frozen_count,
        "restored_tensors": restored,
        "only_source_load_cast_drift_observed": all(
            item["matches_source_cast_to_export_dtype"] for item in restored
        ),
        "cuda_used": False,
        "verification_required_after_correction": True,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({key: value for key, value in report.items() if key != "restored_tensors"}),
        flush=True,
    )


if __name__ == "__main__":
    main()
