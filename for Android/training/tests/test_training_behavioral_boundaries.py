"""Strict behavioral CLI cannot reuse final data or pick a short epoch prefix."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "agent_training_behavioral_boundaries", Path(__file__).resolve().parents[1] / "train_lora.py"
)
assert _SPEC and _SPEC.loader
_TRAINING = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TRAINING)


def test_behavioral_training_rejects_final_or_unspecified_split_and_duplicate_ids():
    check = getattr(_TRAINING, "validate_behavioral_training_inputs", None)
    assert callable(check), "Strict behavioral training must validate split roles"
    train = [{"id": "train-0", "split": "train"}]
    dev = [{"id": "dev-0", "split": "dev"}]
    check(train, dev)
    for wrong in ("eval", "train", None):
        with pytest.raises(ValueError, match="dev"):
            check(train, [{"id": "dev-0", "split": wrong}])
    with pytest.raises(ValueError, match="train"):
        check([{**train[0], "split": "dev"}], dev)
    with pytest.raises(ValueError, match="IDs"):
        check(train * 2, dev)


def test_attention_only_excludes_mlp_and_vision_and_preserves_linear_attention():
    profiles = getattr(_TRAINING, "TARGET_MODULE_PROFILES", None)
    assert profiles is not None, "Training needs explicit reviewed module profiles"
    assert profiles["full_v4"] == _TRAINING.TARGET_MODULES
    pattern = profiles["attention_only"]
    for suffix in (
        "self_attn.q_proj",
        "self_attn.k_proj",
        "self_attn.v_proj",
        "self_attn.o_proj",
        "linear_attn.in_proj_qkv",
        "linear_attn.in_proj_z",
        "linear_attn.out_proj",
    ):
        assert re.fullmatch(pattern, f"model.language_model.layers.0.{suffix}")
    for name in (
        "model.language_model.layers.0.mlp.gate_proj",
        "model.visual.blocks.0.attn.q_proj",
    ):
        assert re.fullmatch(pattern, name) is None


def test_profile_source_inventory_pins_the_actual_v5_scorer_closure_and_rejects_path_escape(
    tmp_path,
):
    inventory = getattr(_TRAINING, "behavioral_profile_sources", None)
    assert callable(inventory), "Training must pin the sources of its actual behavioral profile"
    script = tmp_path / "for Android/training/train_lora.py"
    root = tmp_path
    paths = inventory(
        "v5_general",
        script,
        ("for Android/training/formats_v5.py", "src/agent_workspace/tools/web_search.py"),
    )
    assert script in paths
    assert root / "for Android/training/evaluate_replay_v5.py" in paths
    assert root / "for Android/training/behavioral_plan.py" in paths
    assert root / "for Android/training/autonomous_dev_generation.py" in paths
    assert root / "for Android/training/formats_v5.py" in paths
    assert root / "src/agent_workspace/tools/web_search.py" in paths
    assert len(paths) == len(set(paths))
    with pytest.raises(ValueError, match="source"):
        inventory("v5_general", script, ("../private.py",))
    with pytest.raises(ValueError, match="profile"):
        inventory("unknown", script, ())


def test_v5_cli_refuses_missing_plan_before_importing_or_loading_model(tmp_path):
    script = Path(__file__).resolve().parents[1] / "train_lora.py"
    target = tmp_path / "never-created-run"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--model",
            str(tmp_path / "missing-model"),
            "--train",
            str(tmp_path / "missing-train"),
            "--eval",
            str(tmp_path / "missing-dev"),
            "--output",
            str(target),
            "--behavioral-profile",
            "v5_general",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 2
    assert "fixed plan" in result.stderr
    assert "Loading weights" not in result.stderr
    assert not target.exists()
