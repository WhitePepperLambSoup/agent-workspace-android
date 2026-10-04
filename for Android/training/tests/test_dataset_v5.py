from __future__ import annotations

import asyncio
import importlib.util
import sys
from collections import Counter
from pathlib import Path

import pytest

ANDROID_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ANDROID_ROOT), str(ANDROID_ROOT.parent / "src")]


def test_v5_builder_exists():
    assert importlib.util.find_spec("training.build_dataset_v5") is not None


def test_fixed_family_counts_and_daily_subjects_are_distinct():
    from training.build_dataset_v5 import FAMILIES, ORDINARY_GROUPS, build_program

    assert len(FAMILIES) == len(set(FAMILIES)) == 60
    assert len(ORDINARY_GROUPS) == 8
    for split in ("train", "dev", "eval"):
        tasks = []
        for i, family in enumerate(FAMILIES):
            program, extra = build_program(split, i, 20261001, family, i % 2)
            assert extra["target_step"] < len(program["steps"])
            assert program["steps"][extra["target_step"]]["family"] == family
            assert split in program["fixture_name"]
            if family.startswith("generation_"):
                tasks.append(extra["artifact_contract"]["task"].get("subtype"))
        assert {"agenda", "settings", "records", "guide", "text_cleanup"} <= set(tasks)


@pytest.mark.parametrize(
    "family",
    [
        "copy_existing_write",
        "missing_recover_write",
        "generation_json_write",
        "generation_html_write",
        "search_write",
    ],
)
def test_canonical_targets_from_actual_full_runner_semantically_finish(family):
    from training.build_dataset_v5 import assert_program_completion, build_program, make_row
    from training.runtime_fixture_v5 import capture_program, load_catalog

    catalog = load_catalog()["catalog"]
    program, extra = build_program("dev", 500, 20261001, family, 0)
    captured = asyncio.run(capture_program(program, catalog))
    assert_program_completion(program, captured)
    row = make_row("dev", 500, family, program, extra, captured)
    assert row["metadata"]["live_prompt_byte_equal"]
    assert row["metadata"]["actual_full_program_completed"]
    assert "Android" in row["messages"][0]["content"]


def test_workflows_are_initial_state_without_gold_assistant_history():
    from training.build_dataset_v5 import build_workflows

    dev, final = build_workflows("dev", 20261001), build_workflows("final", 20261001)
    for cases in (dev, final):
        assert Counter(case["group"] for case in cases) == {"file": 10, "format": 6, "search": 4}
        for case in cases:
            assert not ({"messages", "target_response", "expected_calls", "steps"} & set(case))
            assert case["initial_files"] is not None and case["prompt"]
    assert not ({case["id"] for case in dev} & {case["id"] for case in final})
