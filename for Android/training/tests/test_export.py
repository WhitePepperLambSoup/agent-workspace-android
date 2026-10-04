"""Reject stale or mismatched converter provenance before publishing weights."""

import hashlib
import importlib.util
import io
import tarfile
from pathlib import Path

import pytest


def helper():
    source = Path(__file__).resolve().parents[1] / "export_gguf.py"
    spec = importlib.util.spec_from_file_location("training_export", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(tmp_path):
    source = tmp_path / "source"
    archive = tmp_path / "pinned.tar.gz"
    files = {"convert_hf_to_gguf.py": b"# converter\n", "gguf-py/gguf/model.py": b"# writer\n"}
    with tarfile.open(archive, "w:gz") as output:
        for name, value in files.items():
            local = source / name
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(value)
            entry = tarfile.TarInfo("llama-fixture/" + name)
            entry.size = len(value)
            output.addfile(entry, io.BytesIO(value))
    return source, archive


def test_converter_and_python_dependencies_match_the_fixed_archive(tmp_path, monkeypatch):
    exporter = helper()
    source, archive = fixture(tmp_path)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    monkeypatch.setattr(exporter, "ENGINE_ARCHIVE_SHA256", digest)
    result = exporter.verify_converter_source(source, archive)
    assert result["converter_python_files_verified"] == 2
    assert result["source_archive_sha256"] == digest
    (source / "gguf-py/gguf/model.py").write_text("# modified writer\n")
    with pytest.raises(ValueError, match="differs"):
        exporter.verify_converter_source(source, archive)


def test_unpinned_archive_is_rejected_before_conversion(tmp_path):
    exporter = helper()
    source, archive = fixture(tmp_path)
    with pytest.raises(ValueError, match="pinned"):
        exporter.verify_converter_source(source, archive)


@pytest.mark.parametrize("version", [1, 2])
def test_each_training_version_has_an_independent_export_identity(version):
    exporter = helper()
    model_id = f"qwen3.5-0.8b-agent-v{version}-q4-k-m"
    name, title = exporter.export_identity(model_id)
    assert name == f"qwen3.5-0.8b-agent-v{version}-f16.gguf"
    assert model_id in title


@pytest.mark.parametrize(
    "model_id",
    [
        "../model",
        "qwen3.5-0.8b-agent-v2-q4-k-m/weights",
        "qwen3.5-0.8b-agent-v0-q4-k-m",
        "qwen3.5-2b-agent-v2-q4-k-m",
    ],
)
def test_export_identity_rejects_paths_and_untrained_architectures(model_id):
    with pytest.raises(ValueError, match="identity"):
        helper().export_identity(model_id)
