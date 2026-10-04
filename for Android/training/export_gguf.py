"""Convert a measured real LoRA training run into a separate Android GGUF."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

ENGINE_REVISION = "7fe450e19305b828c199d602c23a8337aaa1f03b"
ENGINE_ARCHIVE_SHA256 = "a6861d549427f814dc591c439e08206f67ffaba0248344d421589abf18199e67"
TRAINED_MODEL_ID = "qwen3.5-0.8b-agent-v1-q4-k-m"


def export_identity(model_id: str) -> tuple[str, str]:
    if not re.fullmatch(r"qwen3\.5-0\.8b-agent-v[1-9][0-9]*-q4-k-m", model_id):
        raise ValueError("Export identity must identify a trained Qwen3.5 0.8B version")
    return model_id.removesuffix("-q4-k-m") + "-f16.gguf", f"Agent Workspace {model_id}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def verify_converter_source(source: Path, archive: Path) -> dict:
    if sha256(archive) != ENGINE_ARCHIVE_SHA256:
        raise ValueError("llama.cpp archive does not match the pinned engine")
    checked = 0
    with tarfile.open(archive, "r:gz") as stream:
        for member in stream.getmembers():
            relative = member.name.partition("/")[2]
            if not member.isfile() or not (
                relative == "convert_hf_to_gguf.py"
                or (relative.startswith("gguf-py/") and relative.endswith(".py"))
            ):
                continue
            local = source / relative
            if local.is_symlink() or not local.resolve().is_relative_to(source.resolve()):
                raise ValueError("Unsafe converter source path")
            if local.read_bytes() != stream.extractfile(member).read():
                raise ValueError("Converter source differs from the pinned engine archive")
            checked += 1
    if checked < 2:
        raise ValueError("Pinned archive does not contain the complete converter")
    return {
        "source_archive_sha256": ENGINE_ARCHIVE_SHA256,
        "converter_sha256": sha256(source / "convert_hf_to_gguf.py"),
        "converter_python_files_verified": checked,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--llama-source", type=Path, required=True)
    parser.add_argument("--quantizer", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--model-id", default=TRAINED_MODEL_ID)
    args = parser.parse_args()
    f16_name, model_title = export_identity(args.model_id)
    report_path = args.run / "training_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not (
        report.get("genuine_weight_training")
        and report.get("adapter_nonzero_update")
        and report.get("vision_weights_preserved")
        and report.get("steps", 0) > 2
    ):
        raise ValueError("Require completed real training with nonzero updates and frozen vision")
    adapter = args.run / "adapter/adapter_model.safetensors"
    if sha256(adapter) != report["adapter_sha256"]:
        raise ValueError("Adapter does not match the measured training run")
    merged = args.run / "merged"
    if not (merged / "config.json").is_file():
        raise ValueError("The complete merged Hugging Face model has not been exported")
    verification_path = args.run / "merged-weight-verification.json"
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if not (
        verification.get("passed") is True
        and verification.get("vision_tensors_preserved") is True
        and verification.get("tokenizer_bytes_preserved") is True
        and verification.get("changed_language_projection_tensors", 0) > 0
    ):
        raise ValueError(
            "Merged language and frozen vision weights require independent verification"
        )
    for name, digest in verification["merged_weight_sha256"].items():
        path = merged / name
        if path.is_symlink() or not path.resolve().is_relative_to(merged.resolve()):
            raise ValueError("Unsafe merged weight path")
        if sha256(path) != digest:
            raise ValueError("Merged weights changed after independent verification")
    converter = verify_converter_source(args.llama_source, args.source_archive)
    cache = args.quantizer.parent.parent / "CMakeCache.txt"
    source_line = next(
        (
            line.partition("=")[2]
            for line in cache.read_text().splitlines()
            if line.startswith("CMAKE_HOME_DIRECTORY:INTERNAL=")
        ),
        None,
    )
    if source_line is None or Path(source_line).resolve() != args.llama_source.resolve():
        raise ValueError("Quantizer build does not record this verified engine source")
    if args.output.exists():
        raise ValueError("Choose a fresh output directory to preserve previous exports")
    args.output.mkdir(parents=True)
    f16 = args.output / f16_name
    q4 = args.output / "model.gguf"
    subprocess.run(
        [
            sys.executable,
            str(args.llama_source / "convert_hf_to_gguf.py"),
            str(merged),
            "--outtype",
            "f16",
            "--outfile",
            str(f16),
            "--model-name",
            model_title,
        ],
        check=True,
    )
    subprocess.run([str(args.quantizer), str(f16), str(q4), "Q4_K_M"], check=True)
    with q4.open("rb") as stream:
        if stream.read(4) != b"GGUF":
            raise ValueError("Quantization did not produce a GGUF model")
    manifest = {
        "model_id": args.model_id,
        "sha256": sha256(q4),
        "size_bytes": q4.stat().st_size,
        "quantization": "Q4_K_M",
        "base_model": report["base_model"],
        "base_revision": report["base_revision"],
        "training_report_sha256": sha256(report_path),
        "adapter_sha256": report["adapter_sha256"],
        "train_sha256": report["train_sha256"],
        "eval_sha256": report["eval_sha256"],
        "eval_role": "development_checkpoint_selection",
        "development_eval_sha256": report["eval_sha256"],
        "training_steps": report["steps"],
        "selected_checkpoint_step": report.get("selected_checkpoint_step", report["steps"]),
        "selected_checkpoint_training_sampling": report.get(
            "selected_checkpoint_training_sampling"
        ),
        "prompt_source": report.get("prompt_source", "official"),
        "engine_revision": ENGINE_REVISION,
        **converter,
        "quantizer_sha256": sha256(args.quantizer),
        "quantizer_build_cache_sha256": sha256(cache),
        "merged_weight_verification_sha256": sha256(verification_path),
        "vision_weights_preserved": True,
        "local_artifact": True,
        "evaluation_required": True,
        "license": "Apache-2.0",
    }
    (args.output / "artifact.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
