"""Check source precision restoration using tiny CPU tensors, never a GPU model."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
_SAFETENSORS = pytest.importorskip("safetensors.torch")
_SPEC = importlib.util.spec_from_file_location(
    "agent_qwen_train_lora_precision", Path(__file__).resolve().parents[1] / "train_lora.py"
)
assert _SPEC and _SPEC.loader
_TRAINING = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TRAINING)


def tiny_checkpoint(tmp_path):
    model = torch.nn.Module()
    model.model = torch.nn.Module()
    model.model.language_model = torch.nn.Module()
    layer = torch.nn.Module()
    layer.linear_attn = torch.nn.Module()
    layer.linear_attn.norm = torch.nn.LayerNorm(2)
    layer.linear_attn.in_proj_qkv = torch.nn.Linear(2, 2, bias=False)
    model.model.language_model.layers = torch.nn.ModuleList([layer])
    model.model.visual = torch.nn.LayerNorm(2)
    layer.linear_attn.norm.weight.data = torch.tensor([1.00390625, 0.12345678])
    model.model.visual.weight.data = torch.tensor([0.23456789, 1.00390625])
    layer.linear_attn.in_proj_qkv.weight.data = torch.tensor(
        [[0.125, 0.25], [0.375, 0.5]], dtype=torch.bfloat16
    )
    originals = {name: tensor.detach().clone() for name, tensor in model.state_dict().items()}
    filename = "model.safetensors"
    _SAFETENSORS.save_file(originals, tmp_path / filename)
    (tmp_path / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": {name: filename for name in originals}}), encoding="utf-8"
    )
    model.to(dtype=torch.bfloat16)
    return model, originals


def test_fp32_frozen_source_precision_is_kept_before_training(tmp_path):
    model, originals = tiny_checkpoint(tmp_path)
    name = "model.language_model.layers.0.linear_attn.norm.weight"
    assert not torch.equal(model.get_parameter(name), originals[name])
    restored = _TRAINING.restore_source_fp32_parameters(model, tmp_path)
    assert restored
    for name, parameter in model.named_parameters():
        if originals[name].dtype == torch.float32:
            assert parameter.dtype == torch.float32
            assert torch.equal(parameter, originals[name])


def test_export_restores_frozen_source_values_and_preserves_learned_projection(tmp_path):
    model, originals = tiny_checkpoint(tmp_path)
    target_name = "model.language_model.layers.0.linear_attn.in_proj_qkv.weight"
    model.get_parameter(target_name).data.add_(torch.tensor(0.0625, dtype=torch.bfloat16))
    learned = model.get_parameter(target_name).detach().clone()
    restored = _TRAINING.restore_frozen_source_parameters(model, tmp_path)
    assert restored
    assert torch.equal(model.get_parameter(target_name), learned)
    assert not torch.equal(model.get_parameter(target_name), originals[target_name])
    for name, parameter in model.named_parameters():
        if name != target_name:
            assert parameter.dtype == originals[name].dtype
            assert torch.equal(parameter, originals[name])
