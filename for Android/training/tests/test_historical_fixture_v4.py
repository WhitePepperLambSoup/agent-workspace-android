"""Current tool help can evolve without rewriting the frozen V4 experiment."""
from __future__ import annotations

import asyncio
import copy
import sys
from pathlib import Path

import pytest

ANDROID_ROOT = Path(__file__).resolve().parents[2]
for source in (ANDROID_ROOT, ANDROID_ROOT.parent / "src"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))


def test_historical_replay_preserves_captured_text_and_declares_its_scope(tmp_path, monkeypatch):
    from training import runtime_fixture_v4 as fixture
    from training.build_dataset_v4 import _file_program

    monkeypatch.setattr(fixture, "SCRATCH", tmp_path / "owned-scratch")
    program, _metadata = _file_program("dev", 6010, 20261004, "copy_new_write", 72)
    catalog = fixture.load_catalog()["catalog"]
    result = asyncio.run(fixture.capture_program(program, catalog))
    assert result["error"] is None
    assert result["historical_request_profile_restored"] is True
    assert result["current_android_prompt_capture"] is False
    historical = fixture.load_system_source()["entries"][program["mode"]]["live_system_suffix"]
    assert all(record["messages"][0]["content"] == historical for record in result["records"])
    assert not any((tmp_path / "owned-scratch").iterdir())


def test_historical_metadata_does_not_relax_execution_contract_and_cleans_setup_error(
    tmp_path, monkeypatch
):
    from training import runtime_fixture_v4 as fixture
    from training.build_dataset_v4 import _file_program

    monkeypatch.setattr(fixture, "SCRATCH", tmp_path / "owned-scratch")
    program, _metadata = _file_program("dev", 6011, 20261004, "copy_new_write", 72)
    catalog = copy.deepcopy(fixture.load_catalog()["catalog"])
    catalog["write_file"]["execution_schema"]["required"].remove("expected_sha256")
    with pytest.raises(ValueError, match="Historical V4 execution contract changed"):
        asyncio.run(fixture.capture_program(program, catalog))
    assert not any((tmp_path / "owned-scratch").iterdir())
