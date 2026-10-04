from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ANDROID_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ANDROID_ROOT), str(ANDROID_ROOT.parent / "src")]


def test_controlled_server_executes_actual_fetch_and_transport_error_recovery(tmp_path):
    from training.controlled_http_v5 import controlled_http, synthetic_web_config
    from training.runtime_fixture_v4 import _thread_worker

    from agent_workspace.tools import web
    from agent_workspace.tools.base import ToolError

    config = synthetic_web_config(
        "fixture.example.test",
        "synthetic quantity",
        [{"name": "specimen", "quantity": 7}],
        variant="fetch_retry",
    )
    url = config["documents"][0]["url"]
    with (
        controlled_http(config, tmp_path / "http") as evidence,
        patch.object(web, "run_in_process", _thread_worker),
    ):
        with pytest.raises(ToolError, match="HTTP status 503"):
            asyncio.run(web.WebFetchTool().execute({"url": url, "max_bytes": 1024}))
        result = json.loads(
            asyncio.run(web.WebFetchTool().execute({"url": url, "max_bytes": 1024}))
        )
    assert json.loads(result["content"])["quantity"] == 7
    assert result["source"]["url"] == url
    assert result["truncated"] is False
    assert [request["status"] for request in evidence["requests"]] == [503, 200]
    assert evidence["real_tls_server"] and evidence["certificate_hostname_validation"]
    assert evidence["transport_routing_is_fixture_only"]
    assert evidence["external_network_used"] is False


def test_production_search_parses_real_primary_and_empty_requery(tmp_path):
    from training.controlled_http_v5 import controlled_http, synthetic_web_config
    from training.runtime_fixture_v4 import _thread_worker

    from agent_workspace.tools import web, web_search

    query = "specimen detail"
    config = synthetic_web_config(
        "fixture.example.test", query, [{"name": "fresh", "quantity": 11}], variant="empty_retry"
    )
    with (
        controlled_http(config, tmp_path / "http") as evidence,
        patch.object(web, "run_in_process", _thread_worker),
        patch.object(web_search, "run_in_process", _thread_worker),
    ):
        empty = json.loads(asyncio.run(web_search.WebSearchTool().execute({"query": query})))
        found = json.loads(
            asyncio.run(web_search.WebSearchTool().execute({"query": query + " quantity"}))
        )
    assert empty["status"] == "no_results" and empty["results"] == []
    assert found["status"] == "ok" and found["results"][0]["url"] == config["documents"][0]["url"]
    assert found["engine"] == "duckduckgo_lite"
    assert len(evidence["requests"]) == 2


def test_runtime_v5_exposes_real_capture_and_free_generation_without_old_catalog_fallback():
    import importlib.util

    assert importlib.util.find_spec("training.runtime_fixture_v5") is not None, (
        "V5 real runner fixture and free-generation driver are missing"
    )


def test_runtime_v5_short_file_program_uses_exact_new_mobile_capture_and_real_tools():
    from training.runtime_fixture_v5 import capture_program, load_catalog, load_system_source

    catalog, systems = load_catalog(), load_system_source()
    program = {
        "fixture_name": "v5-http-tests-real-file-01",
        "mode": "task",
        "prompt": "Copy input.txt into new.txt, preserving the source and checking the result.",
        "initial_directories": [],
        "initial_files": {"input.txt": "\nSynthetic original\r\n\n"},
        "steps": [
            {"kind": "read", "calls": [{"name": "read_file", "arguments": {"path": "input.txt"}}]},
            {
                "kind": "write",
                "calls": [
                    {
                        "name": "write_file",
                        "arguments": {"path": "new.txt", "content": "", "expected_sha256": None},
                        "content_from_read": "input.txt",
                    }
                ],
            },
            {
                "kind": "readback",
                "calls": [{"name": "read_file", "arguments": {"path": "new.txt"}}],
            },
            {"kind": "terminal", "text": "Copied and verified the new file."},
        ],
    }
    captured = asyncio.run(capture_program(program, catalog["catalog"]))
    assert captured["error"] is None, captured["error"]
    assert captured["final_files"] == {
        "input.txt": "\nSynthetic original\r\n\n",
        "new.txt": "\nSynthetic original\r\n\n",
    }
    assert (
        captured["records"][0]["messages"][0]["content"]
        == systems["entries"]["task"]["live_system_suffix"]
    )
    assert captured["compacted"] is False


def _search_program():
    from training.controlled_http_v5 import synthetic_web_config

    query = "synthetic bridge schedule"
    brief = {"kind": "markdown", "title": "Independent test report", "function_name": "total"}
    return {
        "id": "v5-search-fixture-test",
        "fixture_name": "v5-search-fixture-test",
        "mode": "task",
        "prompt": "Read brief.json, search for synthetic bridge schedule, fetch its source, "
        "write report.md with the observed quantities and source links, read it back and finish.",
        "initial_directories": [],
        "initial_files": {"brief.json": json.dumps(brief), "keep.txt": "unchanged\n"},
        "http_fixture": synthetic_web_config(
            "bridge.example.test",
            query,
            [{"name": "bridge forms", "quantity": 7}],
            variant="fetch_retry",
        ),
        "steps": [
            {"kind": "read", "calls": [{"name": "read_file", "arguments": {"path": "brief.json"}}]},
            {
                "kind": "select",
                "calls": [
                    {
                        "name": "select_local_tools",
                        "arguments": {"names": ["web_search", "web_fetch"]},
                    }
                ],
            },
            {"kind": "search", "calls": [{"name": "web_search", "arguments": {"query": query}}]},
            {
                "kind": "failed_fetch",
                "calls": [
                    {
                        "name": "web_fetch",
                        "arguments": {"url": ""},
                        "url_from_search": 0,
                        "expected_failure": True,
                    }
                ],
            },
            {
                "kind": "fetch",
                "calls": [{"name": "web_fetch", "arguments": {"url": ""}, "url_from_search": 0}],
            },
            {
                "kind": "select",
                "calls": [
                    {
                        "name": "select_local_tools",
                        "arguments": {"names": ["read_file", "write_file"]},
                    }
                ],
            },
            {
                "kind": "write",
                "calls": [
                    {
                        "name": "write_file",
                        "arguments": {"path": "report.md", "content": "", "expected_sha256": None},
                        "artifact_from_web": "brief.json",
                    }
                ],
            },
            {
                "kind": "readback",
                "calls": [{"name": "read_file", "arguments": {"path": "report.md"}}],
            },
            {"kind": "terminal", "text": "Completed and verified the report."},
        ],
    }


def test_search_program_executes_complete_real_tools_and_failure_history():
    from training.formats_v5 import validate_artifact
    from training.runtime_fixture_v5 import capture_program, load_catalog

    program = _search_program()
    result = asyncio.run(capture_program(program, load_catalog()["catalog"]))
    assert result["error"] is None, result["error"]
    assert result["final_files"]["keep.txt"] == "unchanged\n"
    assert len(result["records"]) == len(program["steps"])
    assert [receipt["status"] for receipt in result["transport"]["requests"]] == [200, 503, 200]
    task = {
        "title": "Independent test report",
        "function_name": "total",
        "require_citations": True,
        "items": [
            {
                "name": "bridge forms",
                "quantity": 7,
                "source": "https://bridge.example.test/source-1.json",
            }
        ],
    }
    assert validate_artifact(
        "markdown",
        result["final_files"]["report.md"],
        task,
        observed_urls=[task["items"][0]["source"]],
    )["valid"]
    assert "Tool failed (" in str(result["records"][-1]["messages"])


@pytest.mark.parametrize("failure", ["output_truncated", "timed_out", "generation_error"])
def test_free_callback_only_sees_visible_strings_and_failed_output_never_executes(failure):
    from training.build_dataset import render_call
    from training.runtime_fixture_v5 import capture_program, load_catalog

    prompts = []
    raw = render_call(
        {
            "name": "write_file",
            "arguments": {"path": "bad.txt", "content": "bad", "expected_sha256": None},
        }
    )
    program = {
        "id": "v5-failed-generation-test",
        "fixture_name": "v5-failed-generation-test",
        "mode": "task",
        "prompt": "Copy keep.txt to good.txt and verify.",
        "initial_directories": [],
        "initial_files": {"keep.txt": "source"},
        "hidden_goal": "this must not be input",
    }

    async def generate_visible(prompt, identifier):
        assert isinstance(prompt, str) and isinstance(identifier, str)
        assert "hidden_goal" not in prompt and "this must not be input" not in prompt
        prompts.append(prompt)
        return {
            "raw_output": raw,
            "output_truncated": False,
            failure: True if failure != "generation_error" else "synthetic failure",
        }

    captured = asyncio.run(
        capture_program(program, load_catalog()["catalog"], generate_visible=generate_visible)
    )
    assert len(prompts) == 1
    assert captured["error"]
    assert captured["records"][0]["generation"]["raw_output"] == raw
    assert captured["final_files"] == {"keep.txt": "source"}
    assert captured["tool_events"] == []


def test_initial_visible_prompt_is_stable_for_repeated_fresh_model_callbacks():
    from training.runtime_fixture_v5 import capture_program, load_catalog

    program = {
        "id": "v5-paired-input-test",
        "fixture_name": "v5-paired-input-test",
        "mode": "coding",
        "prompt": "What is 6 + 7?",
        "initial_files": {},
        "initial_directories": [],
    }
    prompts = []

    def generate_visible(prompt, _identifier):
        prompts.append(prompt)
        return {"raw_output": "13<|im_end|>", "output_truncated": False}

    for _ in range(2):
        result = asyncio.run(
            capture_program(program, load_catalog()["catalog"], generate_visible=generate_visible)
        )
        assert result["error"] is None
    assert len(prompts) == 2 and prompts[0] == prompts[1]
