"""A native Qwen checkpoint must include its frozen MTP head, even for text SFT."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
safetensors = pytest.importorskip("safetensors.torch")
_TRAINING_DIR = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "agent_export_train_lora", _TRAINING_DIR / "train_lora.py"
)
assert _SPEC and _SPEC.loader
_TRAINING = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TRAINING)


def tiny_export(tmp_path):
    base = tmp_path / "base"
    merged = tmp_path / "merged"
    base.mkdir()
    merged.mkdir()
    target = "model.language_model.layers.0.linear_attn.in_proj_qkv.weight"
    vision = "model.visual.norm.weight"
    mtp = "mtp.layers.0.input_layernorm.weight"
    originals = {
        target: torch.tensor([[0.125, 0.25]], dtype=torch.bfloat16),
        vision: torch.tensor([0.12345678], dtype=torch.float32),
        mtp: torch.tensor([1.00390625], dtype=torch.float32),
    }
    safetensors.save_file(originals, base / "model.safetensors")
    (base / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": {name: "model.safetensors" for name in originals}}),
        encoding="utf-8",
    )
    learned = originals[target] + torch.tensor(0.0625, dtype=torch.bfloat16)
    safetensors.save_file(
        {target: learned, vision: originals[vision]}, merged / "model.safetensors"
    )
    for name in ("tokenizer.json", "tokenizer_config.json", "chat_template.jinja"):
        (base / name).write_text("same frozen tokenizer", encoding="utf-8")
        (merged / name).write_bytes((base / name).read_bytes())
    return base, merged, originals, target, learned, mtp


def test_verifier_rejects_an_export_missing_the_frozen_mtp_head(tmp_path):
    base, merged, _, _, _, mtp = tiny_export(tmp_path)
    report_path = tmp_path / "verification.json"
    result = subprocess.run(
        [
            sys.executable,
            str(_TRAINING_DIR / "verify_merged_weights.py"),
            "--base",
            str(base),
            "--merged",
            str(merged),
            "--output",
            str(report_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert result.returncode != 0, "missing frozen MTP tensors must fail the export gate"
    assert report["passed"] is False
    assert mtp in report["unexplained_missing_tensors"]
    assert report["frozen_tensors_preserved_exactly"] is False


def test_export_completion_restores_original_mtp_without_changing_learned_tensors(tmp_path):
    base, merged, originals, target, learned, mtp = tiny_export(tmp_path)
    complete = getattr(_TRAINING, "complete_source_mtp_export", None)
    assert callable(complete), "the trainer needs a source MTP export completion step"
    report = complete(base, merged)
    final = safetensors.load_file(merged / "model.safetensors", device="cpu")
    assert set(final) == set(originals)
    assert torch.equal(final[target], learned)
    assert final[mtp].dtype == originals[mtp].dtype
    assert torch.equal(final[mtp], originals[mtp])
    assert report["added_source_mtp_tensors"] == [mtp]
    for name in originals:
        if name != target:
            assert final[name].dtype == originals[name].dtype
            assert torch.equal(final[name], originals[name])


def test_export_completion_refuses_a_missing_language_projection(tmp_path):
    base, merged, originals, target, _, _ = tiny_export(tmp_path)
    safetensors.save_file(
        {"model.visual.norm.weight": originals["model.visual.norm.weight"]},
        merged / "model.safetensors",
    )
    complete = getattr(_TRAINING, "complete_source_mtp_export", None)
    assert callable(complete), "the trainer needs a source MTP export completion step"
    with pytest.raises(ValueError, match="non-MTP"):
        complete(base, merged)
    final = safetensors.load_file(merged / "model.safetensors", device="cpu")
    assert target not in final
