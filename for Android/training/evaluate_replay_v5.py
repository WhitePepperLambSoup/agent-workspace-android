"""Actual current-stage execution and initial-state callbacks; no gold autonomous history."""

# Chinese completion/negation vocabulary is intentionally literal.
# ruff: noqa: RUF001
from __future__ import annotations

import asyncio
import copy
import inspect
import json
import re
import sys
from collections import Counter
from pathlib import Path

ANDROID_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ANDROID_ROOT.parent
for source in (ANDROID_ROOT, REPOSITORY / "src"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from android_adapter.local_provider import parse_qwen_output  # noqa: E402

from agent_workspace.core.models import DeltaKind  # noqa: E402
from training.build_dataset_v5 import artifact_goal, independent_ordinary_answer  # noqa: E402
from training.evaluate_tools import build_evaluation_prompt  # noqa: E402
from training.formats_v5 import validate_artifact  # noqa: E402
from training.runtime_fixture_v5 import (  # noqa: E402
    _unwrap,
    capture_program,
    digest,
    generation_success,
    historical_tool_results,
    observed_document_urls,
    strip_end_marker,
)

# The complete project runtime/adapter superset is pinned, together with every shared
# training helper actually imported by this scorer. This includes V4 pure helpers, not
# its historical capture path or any labels. External Python packages are separately locked.
SOURCE_DEPENDENCIES = tuple(
    sorted(
        {
            "for Android/training/evaluate_replay_v5.py",
            "for Android/training/build_dataset_v5.py",
            "for Android/training/runtime_fixture_v5.py",
            "for Android/training/runtime_fixture_v4.py",
            "for Android/training/controlled_http_v5.py",
            "for Android/training/formats_v5.py",
            "for Android/training/daily_formats_v5.py",
            "for Android/training/build_dataset.py",
            "for Android/training/evaluate_tools.py",
            *(
                path.relative_to(REPOSITORY).as_posix()
                for path in (REPOSITORY / "src/agent_workspace").rglob("*.py")
            ),
            *(
                path.relative_to(REPOSITORY).as_posix()
                for path in (ANDROID_ROOT / "android_adapter").rglob("*.py")
            ),
            *(path.relative_to(REPOSITORY).as_posix() for path in ANDROID_ROOT.glob("*.py")),
        }
    )
)


def terminal_statement(text):
    if re.search(
        r"未|没有|无法|不能|失败|尚|将|准备|计划|请|需要|应该|[?？]|\b(?:not|cannot|can't|failed|unable|will|plan|should|must)\b",
        text,
        re.IGNORECASE,
    ):
        return False
    return bool(
        re.search(
            r"已(?:经)?(?:完成|复制|创建|保存|核对|核验)|\b(?:completed|done|copied|created|saved|verified)\b",
            text,
            re.IGNORECASE,
        )
    )


def ordinary_correct(row, text):
    expected = independent_ordinary_answer(row)
    group = row["metadata"]["ordinary_group"]
    if group.startswith("arithmetic_"):
        if re.search(r"不确定|无法|不是|未完成|\b(?:not|cannot|unknown)\b", text, re.IGNORECASE):
            return False
        tail = r"([+-]?\d+)(?:\s*(件|枚|个))?\s*[。.!]?\s*$"
        match = re.search(
            r"(?:最终答案|答案|结果|final answer|answer)\s*[:：=]?\s*" + tail, text, re.IGNORECASE
        )
        match = match or re.fullmatch(r"\s*" + tail, text) or re.search(r"=\s*" + tail, text)
        return bool(
            match
            and int(match[1]) == expected
            and (group != "arithmetic_units" or match[2] in {None, "件"})
        )
    if group == "language_extract":
        return text.strip() == expected
    try:
        return json.loads(text) == expected
    except (TypeError, ValueError):
        return False


def parsed_response(row, raw):
    request, _ = build_evaluation_prompt(row)
    deltas = parse_qwen_output(strip_end_marker(raw), request, row["id"])
    return (
        [
            {"name": delta.tool_call.name, "arguments": delta.tool_call.arguments}
            for delta in deltas
            if delta.kind is DeltaKind.TOOL_CALL
        ],
        "".join(delta.text for delta in deltas if delta.kind is DeltaKind.TEXT),
    )


def equivalent_calls(actual, expected, kind):
    if len(actual) != len(expected):
        return False
    for received, wanted in zip(actual, expected, strict=True):
        if received["name"] != wanted["name"]:
            return False
        args, wanted_args = received["arguments"], wanted["arguments"]
        if kind == "select":
            if not set(wanted_args["names"]) <= set(args.get("names", [])):
                return False
        elif kind in {"read", "readback", "directory_readback"}:
            if args.get("path", ".") != wanted_args.get("path", ".") or args.get("offset", 0) != 0:
                return False
        elif kind == "artifact_write":
            if (
                args.get("path") != wanted_args["path"]
                or args.get("expected_sha256", "absent") != wanted_args["expected_sha256"]
            ):
                return False
        elif kind == "search":
            if args.get("query") != wanted_args["query"]:
                return False
        elif kind == "fetch":
            if args.get("url") != wanted_args["url"]:
                return False
        elif args != wanted_args:
            return False
    return True


def stage_state_matches(metadata, state):
    after = metadata["after_files"]
    actual, checks = state["after_files"], {}
    if set(actual) != set(after) or state["after_directories"] != metadata["after_directories"]:
        return False, checks
    contract = (
        metadata.get("artifact_contract") if metadata["stage_kind"] == "artifact_write" else None
    )
    for path, wanted in after.items():
        if contract and path == contract["path"]:
            checks[path] = validate_artifact(
                contract["kind"],
                actual[path],
                contract["task"],
                observed_urls=observed_document_urls(state["messages"]),
            )
            if not checks[path]["valid"]:
                return False, checks
        elif actual[path] != wanted:
            return False, checks
    # Every unrelated byte matched the independent post-state above. The requested edit
    # of an existing file is intentionally allowed to differ from its observed pre-state.
    return True, checks


def score_prediction(row, prediction, catalog):
    metadata = row["metadata"]
    ordinary = bool(metadata["ordinary_retention"])
    raw = prediction.get("raw_output", "")
    result = {
        "id": row["id"],
        "split": row["split"],
        "family": metadata["family"],
        "group": metadata.get("ordinary_group", metadata["stage_kind"]),
        "ordinary_retention": ordinary,
        "ordinary_semantics_supported": ordinary,
        "protocol_valid": False,
        "prediction_generation_success": generation_success(prediction),
        "output_truncated": bool(
            prediction.get("output_truncated") or prediction.get("output_limit_reached")
        ),
        "behavior_success": False,
        "ordinary_correct": False if ordinary else None,
        "visible_prompt_sha256": digest(build_evaluation_prompt(row)[1]),
        "raw_output": raw,
        "completion_text": strip_end_marker(raw),
        "known_precondition": None,
        "actual_prediction_executed": False,
        "autonomous_task_success": None,
        "scripted_prefix_counted_as_model_progress": False,
    }
    if not result["prediction_generation_success"]:
        return result
    try:
        calls, text = parsed_response(row, raw)
    except Exception as error:
        result["protocol_error"] = f"{type(error).__name__}: {error}"
        return result
    result.update(calls=calls, text=text, protocol_valid=bool(calls or text.strip()))
    if not result["protocol_valid"]:
        return result
    if ordinary:
        result["ordinary_correct"] = not calls and ordinary_correct(row, text)
        result["behavior_success"] = result["ordinary_correct"]
        return result
    captured = asyncio.run(
        capture_program(
            metadata["program"],
            catalog,
            prediction=strip_end_marker(raw),
            stop_at=metadata["target_step"],
        )
    )
    if len(captured["records"]) <= metadata["target_step"]:
        raise ValueError(f"V5 known precondition failed before prediction: {captured['error']}")
    state = captured["records"][metadata["target_step"]]
    if (
        state["messages"] != row["messages"]
        or state["tools"] != row["tools"]
        or state["before_files"] != metadata["before_files"]
        or state["before_directories"] != metadata["before_directories"]
        or state["captured_runtime_prompt_sha256"] != result["visible_prompt_sha256"]
    ):
        raise ValueError("V5 current mobile precondition, menu or system changed")
    result.update(known_precondition=True, actual_prediction_executed=True)
    prefix_calls = sum(
        len(step.get("calls", []))
        for step in metadata["program"]["steps"][: metadata["target_step"]]
    )
    outcomes = [event for event in captured["tool_events"] if event["type"] != "tool.proposed"]
    events = outcomes[prefix_calls:]
    succeeded = (
        captured["error"] is None
        and len(events) == len(calls)
        and all(event["type"] == "tool.settled" for event in events)
    )
    kind = metadata["stage_kind"]
    correct_calls = equivalent_calls(calls, row["expected"].get("calls", []), kind)
    if kind in {"read", "readback"} and succeeded and correct_calls:
        for event, call in zip(events, calls, strict=True):
            output = json.loads(event["result"])
            succeeded &= (
                output.get("truncated") is False
                and output.get("offset") == 0
                and output.get("content") == metadata["before_files"].get(call["arguments"]["path"])
            )
    elif kind == "directory_readback" and succeeded and correct_calls:
        output = json.loads(events[0]["result"])
        succeeded &= output.get("truncated") is False and output.get("entries") == []
    elif kind == "search" and succeeded and correct_calls:
        output = json.loads(events[0]["result"])
        expected_urls = {item["source"] for item in metadata["artifact_contract"]["task"]["items"]}
        succeeded &= output.get("status") == "ok" and expected_urls <= {
            item["url"] for item in output.get("results", [])
        }
    elif kind == "fetch" and succeeded and correct_calls:
        output = json.loads(events[0]["result"])
        wanted = next(
            (
                document
                for document in metadata["program"]["http_fixture"]["documents"]
                if document["url"] == calls[0]["arguments"]["url"]
            ),
            None,
        )
        succeeded &= (
            wanted is not None
            and output.get("truncated") is False
            and output.get("content") == wanted["content"]
            and output.get("source", {}).get("url") == wanted["url"]
        )
    state_ok, checks = stage_state_matches(metadata, state)
    if kind == "terminal":
        urls = observed_document_urls(state["messages"])
        goal_ok, checks = artifact_goal(metadata["program"], state["before_files"], urls)
        succeeded &= not calls and terminal_statement(text) and goal_ok
    result.update(
        executed_events=events,
        artifact_semantics=checks,
        execution_success=bool(succeeded),
        artifact_state_matches=state_ok,
        behavior_success=bool(succeeded and correct_calls and state_ok),
    )
    result["filebytes_readback"] = bool(result["behavior_success"] and kind == "readback")
    result["terminal_continuation"] = bool(result["behavior_success"] and kind == "terminal")
    return result


def score_report(rows, predictions, catalog):
    splits = {row["split"] for row in rows}
    if len(splits) != 1 or not splits <= {"train", "dev", "eval"}:
        raise ValueError("V5 stage scoring requires one original train/dev/eval split")
    if any(row["metadata"]["split"] != row["split"] for row in rows):
        raise ValueError("V5 row provenance changed its original split")
    samples = predictions["samples"] if isinstance(predictions, dict) else predictions
    by_id = {prediction["id"]: prediction for prediction in samples}
    if (
        len(by_id) != len(samples)
        or len({row["id"] for row in rows}) != len(rows)
        or set(by_id) != {row["id"] for row in rows}
    ):
        raise ValueError("V5 predictions must preserve every unique original input ID")
    scored = [score_prediction(row, by_id[row["id"]], catalog) for row in rows]
    return {
        "split": next(iter(splits)),
        "samples": scored,
        "summary": {
            "samples": len(scored),
            "protocol_valid_count": sum(sample["protocol_valid"] for sample in scored),
            "behavior_success_count": sum(sample["behavior_success"] for sample in scored),
            "tool_step_success_count": sum(
                sample["behavior_success"] for sample in scored if not sample["ordinary_retention"]
            ),
            "tool_step_total": sum(not sample["ordinary_retention"] for sample in scored),
            "ordinary_correct_count": sum(bool(sample["ordinary_correct"]) for sample in scored),
            "ordinary_total": sum(sample["ordinary_retention"] for sample in scored),
            "family_counts": dict(Counter(sample["family"] for sample in scored)),
            "all_failed_generation_samples_remain_in_denominator": True,
            "autonomous_task_success_rate": None,
        },
        "scope": "Actual single current-stage execution from scripted known state; "
        "ordinary arithmetic/literal semantics; scripted prefix earns no model progress",
        "model_inference_performed": False,
    }


def history_operations(messages):
    calls, operations = {}, []
    for message in messages:
        for call in message.get("tool_calls", []):
            function = call["function"]
            args = function["arguments"]
            calls[call["id"]] = (
                function["name"],
                json.loads(args) if isinstance(args, str) else args,
            )
        if message["role"] == "tool":
            name, args = calls[message["tool_call_id"]]
            content = _unwrap(message["content"])
            if not content.startswith(("Tool failed (", "Tool rejected (", "Tool argument error")):
                try:
                    value = json.loads(content)
                except ValueError:
                    value = {"unparsed_result": content}
                operations.append((name, args, value))
    return operations


def workflow_evidence(case, captured):
    final = captured["records"][-1] if captured["records"] else {"messages": []}
    messages = final["messages"]
    urls = observed_document_urls(messages)
    goal_ok, checks = artifact_goal(case, captured["final_files"], urls)
    changed = {
        path
        for path, content in case["goal_files"].items()
        if case["initial_files"].get(path) != content
    }
    changed |= {contract["path"] for contract in case.get("artifact_contracts", [])}
    current_files, reads, first_read, first_write, last_write, last_read = (
        dict(case["initial_files"]),
        {},
        {},
        {},
        {},
        {},
    )
    writes_cas, intended_writes = True, True
    folder = case.get("goal_directory")
    empty_directory_required = bool(
        folder and not any(path.startswith(folder + "/") for path in case["goal_files"])
    )
    observed_directory = folder is None
    operations = history_operations(messages)
    for ordinal, (name, args, output) in enumerate(operations):
        path = args.get("path")
        if name == "read_file" and not output.get("truncated") and output.get("offset") == 0:
            reads[path] = {**output, "observation_index": ordinal}
            if output.get("content") == current_files.get(path):
                first_read.setdefault(path, ordinal)
                last_read[path] = ordinal
        elif name == "write_file":
            intended_writes &= path in changed
            if path in current_files:
                observed = reads.get(path)
                writes_cas &= bool(
                    observed
                    and observed["observation_index"] > last_write.get(path, -1)
                    and observed.get("content") == current_files[path]
                    and args.get("expected_sha256")
                    == observed["sha256"]
                    == digest(current_files[path])
                )
            else:
                writes_cas &= "expected_sha256" in args and args["expected_sha256"] is None
            current_files[path] = args["content"]
            first_write.setdefault(path, ordinal)
            last_write[path] = ordinal
        elif name == "make_directory" and path == folder and not empty_directory_required:
            observed_directory = True
        elif name == "list_files" and path == folder and empty_directory_required:
            observed_directory = output.get("truncated") is False and output.get("entries") == []
    readback = all(
        path in last_write and last_read.get(path, -1) > last_write[path] for path in changed
    )
    required_reads = all(
        path in first_read and first_read[path] < min(first_write.values(), default=10**9)
        for path in case.get("required_read_paths", [])
    )
    sources_read, sources_prior_write = True, True
    if case["group"] == "search":
        searches = historical_tool_results(messages, "web_search")
        sources_read = bool(
            searches and any(item["result"].get("status") == "ok" for item in searches) and urls
        )
        expected_sources = {
            item["source"]
            for contract in case["artifact_contracts"]
            for item in contract["task"]["items"]
        }
        searched_urls, fetched = set(), {}
        for ordinal, (name, _args, output) in enumerate(operations):
            if name == "web_search" and output.get("status") == "ok":
                searched_urls.update(item["url"] for item in output["results"])
            elif name == "web_fetch" and not output.get("truncated"):
                url = output["source"]["url"]
                if url in searched_urls:
                    fetched.setdefault(url, ordinal)
        first_artifact_write = min(first_write.values(), default=-1)
        sources_prior_write = bool(
            expected_sources
            and expected_sources <= set(fetched)
            and all(fetched[url] < first_artifact_write for url in expected_sources)
        )
    terminal_raw = final.get("target_response", "")
    terminal_ok = False
    try:
        calls, text = parsed_response({**final, "id": case["id"]}, terminal_raw)
        terminal_ok = not calls and terminal_statement(text)
    except Exception:
        pass
    return {
        "artifact_goal_matches": goal_ok,
        "artifact_semantics": checks,
        "directories_match": captured["final_directories"] == case["goal_directories"],
        "filebytes_readback": bool(readback),
        "required_initial_files_read": bool(required_reads),
        "writes_use_observed_cas": bool(writes_cas),
        "only_requested_files_written": bool(intended_writes),
        "requested_directory_observed": bool(observed_directory),
        "search_and_sources_observed": bool(sources_read),
        "required_sources_fetched_before_write": bool(sources_prior_write),
        "terminal_continuation": terminal_ok,
    }


async def evaluate_workflow_report(
    cases,
    catalog,
    generate_visible,
    *,
    generation_config,
    model_identity,
    max_turns=16,
    on_prediction=None,
):
    splits = {case["split"] for case in cases}
    if len(splits) != 1 or not splits <= {"dev", "final"}:
        raise ValueError("V5 autonomous workflows preserve one original dev/final split")
    if (
        type(max_turns) is not int
        or max_turns < 1
        or generation_config.get("max_turns", max_turns) != max_turns
    ):
        raise ValueError("Fixed autonomous generation configuration must match the turn budget")
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("V5 autonomous IDs must be unique and complete")
    if any(case["group"] not in {"file", "format", "search"} or "steps" in case for case in cases):
        raise ValueError(
            "Autonomous V5 cases contain only initial state, never gold assistant steps"
        )
    samples = []
    for case in cases:
        captured = await capture_program(
            case, catalog, generate_visible=generate_visible, max_turns=max_turns
        )
        turns = captured["records"]
        successful = bool(turns) and all(
            isinstance(turn.get("generation"), dict) and generation_success(turn["generation"])
            for turn in turns
        )
        truncated = any(
            bool(
                (turn.get("generation") or {}).get("output_truncated")
                or (turn.get("generation") or {}).get("output_limit_reached")
            )
            for turn in turns
        )
        evidence_error = None
        try:
            evidence = workflow_evidence(case, captured)
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
            evidence_error = f"{type(error).__name__}: {error}"
            evidence = {
                "artifact_goal_matches": False,
                "artifact_semantics": {},
                "directories_match": False,
                "filebytes_readback": False,
                "writes_use_observed_cas": False,
                "only_requested_files_written": False,
                "requested_directory_observed": False,
                "search_and_sources_observed": False,
                "required_sources_fetched_before_write": False,
                "terminal_continuation": False,
            }
        achieved = (
            captured["error"] is None
            and captured["turn_completed"]
            and successful
            and not truncated
            and all(value for name, value in evidence.items() if name != "artifact_semantics")
        )
        sample = {
            "id": case["id"],
            "split": case["split"],
            "group": case["group"],
            "initial_visible_prompt_sha256": turns[0]["captured_runtime_prompt_sha256"]
            if turns
            else None,
            "prediction_generation_success": bool(successful),
            "output_truncated": truncated,
            "behavior_success": bool(achieved),
            "autonomous_success": bool(achieved)
            if model_identity.get("generation_source") == "model_free_generation"
            else None,
            "model_performance_claim": model_identity.get("generation_source")
            == "model_free_generation",
            "scripted_prefix_counted_as_model_progress": False,
            "gold_history_injected": False,
            "turns": copy.deepcopy(turns),
            "tool_events": captured["tool_events"],
            "turn_events": captured["turn_events"],
            "run_result": captured["run_result"],
            "turn_completed": captured["turn_completed"],
            "error": captured["error"],
            "evidence_error": evidence_error,
            "final_files": captured["final_files"],
            "final_directories": captured["final_directories"],
            "transport": captured["transport"],
            "context_compacted": captured["compacted"],
            **evidence,
        }
        samples.append(sample)
        if on_prediction:
            completed = on_prediction(copy.deepcopy(sample))
            if inspect.isawaitable(completed):
                await completed
    return {
        "split": next(iter(splits)),
        "samples": samples,
        "generation_config": copy.deepcopy(generation_config),
        "model_identity": copy.deepcopy(model_identity),
        "summary": {
            "samples": len(samples),
            "successes": sum(sample["behavior_success"] for sample in samples),
            "group_counts": dict(Counter(sample["group"] for sample in samples)),
            "all_failed_generation_samples_remain_in_denominator": True,
        },
        "scope": "Initial-state actual mobile runner; callback receives visible prompt and ID "
        "strings only; all assistant decisions come from callback; controlled TLS transport "
        "uses synthetic fixture routing",
        "expected_answers_given_to_model": False,
        "private_user_data_used": False,
    }
