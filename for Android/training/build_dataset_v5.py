"""New synthetic daily programs captured by the current mobile runner, without models."""

# Chinese punctuation in bilingual user requirements is intentional.
# ruff: noqa: RUF001
from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import json
import operator
import random
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

ANDROID_ROOT = Path(__file__).resolve().parents[1]
for source in (ANDROID_ROOT, ANDROID_ROOT.parent / "src"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from android_adapter.local_provider import parse_qwen_output  # noqa: E402

from agent_workspace.core.models import DeltaKind  # noqa: E402
from training.build_dataset import compact  # noqa: E402
from training.controlled_http_v5 import synthetic_web_config  # noqa: E402
from training.evaluate_tools import build_evaluation_prompt  # noqa: E402
from training.formats_v5 import EXTENSIONS, KINDS, render_artifact, validate_artifact  # noqa: E402
from training.runtime_fixture_v5 import (  # noqa: E402
    DEFAULT_CATALOG,
    DEFAULT_SYSTEM,
    capture_program,
    digest,
    load_catalog,
    load_system_source,
    observed_document_urls,
    transform_content,
)

SPLITS = ("train", "dev", "eval")
ORDINARY_GROUPS = (
    "arithmetic_add",
    "arithmetic_subtract",
    "arithmetic_multiply",
    "arithmetic_mixed",
    "arithmetic_parentheses",
    "arithmetic_units",
    "language_extract",
    "language_sort",
)
FILE_FAMILIES = (
    "copy_new_read",
    "copy_new_write",
    "copy_new_readback",
    "copy_new_done",
    "copy_existing_read_source",
    "copy_existing_read_target",
    "copy_existing_write",
    "copy_existing_readback",
    "copy_existing_done",
    "cas_recover_read",
    "cas_recover_write",
    "cas_recover_readback",
    "cas_recover_done",
    "missing_recover_write",
    "edit_replace_read",
    "edit_replace_write",
    "edit_replace_readback",
    "edit_replace_done",
    "edit_append_read",
    "edit_append_write",
    "edit_append_readback",
    "edit_append_done",
    "edit_remove_read",
    "edit_remove_write",
    "edit_remove_readback",
    "edit_remove_done",
    "mkdir_only_select",
    "mkdir_only_create",
    "mkdir_only_list",
    "mkdir_only_done",
    "mkdir_write_select",
    "mkdir_write_create",
    "mkdir_write_write",
    "mkdir_write_readback",
    "mkdir_write_done",
)
GENERATION_FAMILIES = tuple(
    f"generation_{kind}_{stage}" for kind in KINDS for stage in ("write", "readback", "done")
)
SEARCH_FAMILIES = tuple(
    f"search_{stage}"
    for stage in ("brief", "select", "query", "fetch", "write", "readback", "done")
)
FAMILIES = (*FILE_FAMILIES, *GENERATION_FAMILIES, *SEARCH_FAMILIES)
CRITICAL_WRITE_FAMILIES = (
    "copy_new_write",
    "copy_existing_write",
    "cas_recover_write",
    "missing_recover_write",
    "edit_replace_write",
    "edit_append_write",
    "edit_remove_write",
    "mkdir_write_write",
    *(f"generation_{kind}_write" for kind in KINDS),
    "search_write",
)
TOPICS = {
    "train": ("社区园艺", "Community workshop", "图书整理", "Museum volunteers"),
    "dev": ("河湾露营", "Field survey", "校园排练", "Repair meetup"),
    "eval": ("山间观测", "Coastal walk", "手工展览", "Archive visit"),
    "final": ("湖畔摄影", "Hilltop picnic", "博物馆讲解", "Science club"),
}
SYSTEM_SOURCE = "actual_current_mobile_agent_runner_provider_request"


def step(family, name, arguments, *, kind, **extras):
    return {
        "family": family,
        "kind": kind,
        "calls": [{"name": name, "arguments": arguments, **extras}],
    }


def done(family):
    return {"family": family, "kind": "terminal", "text": "已完成并核验所需结果。"}


def required_directories(files, directories=()):
    names = set(directories)
    for filename in [*files, *directories]:
        for parent in PurePosixPath(filename).parents:
            if parent.as_posix() != ".":
                names.add(parent.as_posix())
    return sorted(names)


def _base_program(split, index, seed, cycle):
    identifier = f"synthetic-v5-{split}-{index:05d}"
    return {
        "id": identifier,
        "fixture_name": f"v5-{seed}-{split}-{index:05d}",
        "mode": "task" if cycle % 2 == 0 else "coding",
        "initial_files": {},
        "initial_directories": ["notes", "archive"],
        "steps": [],
        "artifact_contracts": [],
        "goal_directory": None,
    }


def _file_program(split, index, seed, family, cycle):
    program = _base_program(split, index, seed, cycle)
    entity = f"case-{split}-{index:05d}"
    subject = TOPICS[split][(index + cycle) % 4]
    shape = (FILE_FAMILIES.index(family) + cycle) % 5
    newline = "\r\n" if shape == 1 else "\n"
    quotation = f"  引用[{subject}] \t{newline}"
    content = f"{subject} · {entity}{newline}阶段=计划{newline}{quotation}后记=原文{newline}"
    if shape == 0:
        content = "\n\n" + content + "\n"
    elif shape == 2:
        content = " \t" + content + "  \t"
    elif shape == 3:
        content = "κ · 🪴 · café\n" + content
    elif shape == 4:
        content = content.rstrip("\n")
    source, target = f"notes/{entity}.txt", f"archive/{entity}.txt"
    initial = {source: content, "notes/preserve.txt": f"Independent preserve {split}-{index}\n"}
    extra = {"content_shape": shape, "source_path": source, "target_path": target}
    steps = []
    if family.startswith(("copy_", "cas_", "missing_")):
        existing = family.startswith(("copy_existing", "cas_"))
        if existing:
            initial[target] = f"Previous archive {subject}\r\n\t{entity}  "
        prompt = (
            f"把 {source} 的完整原文复制到{'已有' if existing else '尚不存在'}的 {target}，"
            "保留源文件及其他文件；如果写入冲突就读取目标后重试，最后回读并核对。"
        )
        if cycle % 2:
            prompt = (
                f"Copy every character from {source} to the "
                f"{'existing' if existing else 'new'} {target}. Preserve the source and "
                "other files. Recover from any write conflict, then read back and verify."
            )
        prefix = "copy_existing" if existing else "copy_new"
        steps.append(
            step(
                prefix + ("_read_source" if existing else "_read"),
                "read_file",
                {"path": source},
                kind="read",
            )
        )
        if family.startswith(("cas_", "missing_")):
            steps.append(
                step(
                    "intentional_conflict",
                    "write_file",
                    {"path": target},
                    kind="failed_write",
                    content_from_read=source,
                    sha_from_read=source,
                    expected_failure=True,
                )
            )
            steps.append(
                step(
                    "cas_recover_read" if existing else "missing_observation",
                    "read_file",
                    {"path": target},
                    kind="read" if existing else "missing_read",
                    expected_failure=not existing,
                )
            )
        elif existing:
            steps.append(
                step("copy_existing_read_target", "read_file", {"path": target}, kind="read")
            )
        write_family = (
            "cas_recover_write"
            if family.startswith("cas_")
            else "missing_recover_write"
            if family.startswith("missing_")
            else prefix + "_write"
        )
        extras = {"content_from_read": source}
        if existing:
            extras["sha_from_read"] = target
        steps.append(
            step(
                write_family,
                "write_file",
                {"path": target, "expected_sha256": None},
                kind="write",
                **extras,
            )
        )
        prefix = "cas_recover" if family.startswith("cas_") else prefix
        steps.extend(
            [
                step(prefix + "_readback", "read_file", {"path": target}, kind="readback"),
                done(prefix + "_done"),
            ]
        )
        goal = {**initial, target: content}
    elif family.startswith("edit_"):
        operation = family.split("_")[1]
        edit = {"operation": operation, "old": "阶段=计划", "new": "阶段=确认"}
        if operation == "append":
            edit["new"] = f"{newline}确认记录：{subject}/{entity}{newline}"
        elif operation == "remove":
            edit["old"] = quotation
        prompt = {
            "replace": f"在 {source} 中只替换 {compact(edit['old'])} 为 {compact(edit['new'])}",
            "append": f"在 {source} 原文结尾追加准确文本 {compact(edit['new'])}",
            "remove": f"从 {source} 删除准确片段 {compact(edit['old'])}",
        }[operation] + "；保留其他全部字符和文件，保存后回读核对。"
        prefix = "edit_" + operation
        steps = [
            step(prefix + "_read", "read_file", {"path": source}, kind="read"),
            step(
                prefix + "_write",
                "write_file",
                {"path": source},
                kind="write",
                content_from_read=source,
                sha_from_read=source,
                edit=edit,
            ),
            step(prefix + "_readback", "read_file", {"path": source}, kind="readback"),
            done(prefix + "_done"),
        ]
        goal = {**initial, source: transform_content(content, edit)}
        extra.update(
            target_path=source,
            edit_operation=operation,
            edit_delta=edit["new"] if operation != "remove" else "",
        )
    else:
        only = family.startswith("mkdir_only")
        prefix = "mkdir_only" if only else "mkdir_write"
        folder, nested = f"archive/{entity}/plans", f"archive/{entity}/plans/record.txt"
        prompt = (
            f"Create the new directory {folder}. "
            + (
                "Verify that it exists and is empty."
                if only
                else f"Save exactly {compact(content)} as {nested}, then read it back."
            )
            + " Preserve all existing files and finish after verification."
        )
        names = (
            ["make_directory", "list_files"]
            if only
            else ["make_directory", "write_file", "read_file"]
        )
        steps = [
            step(prefix + "_select", "select_local_tools", {"names": names}, kind="select"),
            step(
                prefix + "_parent",
                "make_directory",
                {"path": str(PurePosixPath(folder).parent)},
                kind="directory",
            ),
            step(prefix + "_create", "make_directory", {"path": folder}, kind="directory"),
        ]
        if only:
            steps.append(
                step(prefix + "_list", "list_files", {"path": folder}, kind="directory_readback")
            )
            goal = initial.copy()
        else:
            steps.extend(
                [
                    step(
                        prefix + "_write",
                        "write_file",
                        {"path": nested, "content": content, "expected_sha256": None},
                        kind="write",
                    ),
                    step(prefix + "_readback", "read_file", {"path": nested}, kind="readback"),
                ]
            )
            goal = {**initial, nested: content}
        steps.append(done(prefix + "_done"))
        program["goal_directory"] = folder
        extra.update(target_path=folder if only else nested, directory_path=folder)
    program.update(
        prompt=prompt,
        initial_files=initial,
        steps=steps,
        goal_files=goal,
        goal_directories=required_directories(
            goal,
            [
                *program["initial_directories"],
                *([program["goal_directory"]] if program["goal_directory"] else []),
            ],
        ),
    )
    extra["target_step"] = next(i for i, entry in enumerate(steps) if entry["family"] == family)
    return program, extra


def _daily_task(kind, split, index, cycle):
    language = "zh" if cycle % 2 == 0 else "en"
    topic = TOPICS[split][(index + cycle) % 4]
    title = f"{topic} / {split}-{index:05d}"
    if cycle % 3 == 2:
        return {
            "title": title,
            "function_name": "sum_quantities",
            "require_citations": False,
            "items": [
                {"name": title + " A", "quantity": index % 37 + 2},
                {"name": topic + ' B,"note"', "quantity": cycle + 7},
            ],
        }
    if kind == "markdown":
        return {
            "subtype": "agenda",
            "language": language,
            "title": title,
            "date": f"2026-10-{index % 28 + 1:02d}",
            "sections": [
                {
                    "heading": "准备" if language == "zh" else "Preparation",
                    "bullets": [
                        f"09:00 {topic}",
                        "确认地点与材料" if language == "zh" else "Confirm location and materials",
                    ],
                },
                {
                    "heading": "纪要" if language == "zh" else "Minutes",
                    "bullets": [
                        f"负责人: team-{index % 19}",
                        "下一次跟进: 周五" if language == "zh" else "Next follow-up: Friday",
                    ],
                },
            ],
        }
    if kind == "json":
        return {
            "subtype": "settings",
            "language": language,
            "data": {
                "project": title,
                "appearance": {"theme": "system", "font_scale": 1.2},
                "notifications": {"on_complete": True, "sound": False},
                "labels": [topic, "local"],
                "retry_count": index % 4 + 1,
            },
        }
    if kind == "csv":
        return {
            "subtype": "records",
            "language": language,
            "columns": [
                {"name": "活动" if language == "zh" else "activity", "type": "str"},
                {"name": "数量" if language == "zh" else "count", "type": "int"},
                {"name": "确认" if language == "zh" else "confirmed", "type": "bool"},
            ],
            "rows": [
                [title + ',"first"', index % 31 + 2, True],
                [topic + "\nnext line", cycle + 4, False],
            ],
        }
    if kind == "html":
        return {
            "subtype": "guide",
            "language": language,
            "title": title,
            "paragraphs": [
                "先阅读简短说明，再按顺序操作。"
                if language == "zh"
                else "Read this guide, then follow the steps in order."
            ],
            "steps": [
                f"准备 {topic}" if language == "zh" else f"Prepare {topic}",
                "检查材料并记录结果"
                if language == "zh"
                else "Check materials and record the result",
            ],
            "animation": "pulse" if cycle % 2 else None,
        }
    return {
        "subtype": "text_cleanup",
        "language": language,
        "title": title,
        "function_name": "clean_lines",
        "operation": "strip_nonempty",
        "samples": [f"  {topic}\t", "", " \n ", f"item-{index} "],
    }


def _generation_program(split, index, seed, family, cycle):
    program = _base_program(split, index, seed, cycle)
    kind = family.split("_")[1]
    task = _daily_task(kind, split, index, cycle)
    contract = {
        "kind": kind,
        "task": task,
        "path": f"archive/report-{split}-{index:05d}.{EXTENSIONS[kind]}",
    }
    brief_path = f"notes/requirements-{split}-{index:05d}.json"
    program["initial_files"] = {
        brief_path: compact({"kind": kind, "task": task}),
        "notes/preserve.txt": f"Synthetic preserve {split}-{index}\n",
    }
    subtype = task.get("subtype", "inventory report")
    prompt = (
        f"读取 {brief_path}，按其中的完整数据和要求生成 {kind} {subtype} 文件 "
        f"{contract['path']}，然后回读核验，保留其他文件。Python/JavaScript 只定义数据和纯函数，"
        "不要执行代码；数据处理函数必须适用于任意同类输入。"
    )
    if cycle % 2:
        prompt = (
            f"Read {brief_path}. Generate the requested {kind} {subtype} at {contract['path']}, "
            "preserving its complete data. Read it back and verify. Preserve other files. "
            "For code, define data and a pure function that accepts arbitrary similar input; "
            "do not execute code."
        )
    steps = [
        step("generation_brief", "read_file", {"path": brief_path}, kind="read"),
        step(
            f"generation_{kind}_write",
            "write_file",
            {"path": contract["path"], "content": "", "expected_sha256": None},
            kind="artifact_write",
            artifact_from_brief=brief_path,
        ),
        step(
            f"generation_{kind}_readback", "read_file", {"path": contract["path"]}, kind="readback"
        ),
        done(f"generation_{kind}_done"),
    ]
    goal = {**program["initial_files"], contract["path"]: render_artifact(kind, task)}
    program.update(
        prompt=prompt,
        steps=steps,
        goal_files=goal,
        artifact_contracts=[contract],
        goal_directories=required_directories(goal, program["initial_directories"]),
    )
    return program, {
        "target_path": contract["path"],
        "artifact_contract": contract,
        "target_step": next(i for i, entry in enumerate(steps) if entry["family"] == family),
    }


def _search_program(split, index, seed, family, cycle):
    program = _base_program(split, index, seed, cycle)
    topic = TOPICS[split][index % 4]
    query = f"synthetic {split} {topic} records {index:05d}"
    variant = ("normal", "fetch_retry", "search_retry", "empty_retry")[cycle % 4]
    facts = [{"name": f"{topic} record A {index:05d}", "quantity": index % 41 + 3}]
    if cycle % 2 == 0:
        facts.append({"name": f"{topic} record B {index:05d}", "quantity": cycle + 9})
    config = synthetic_web_config(
        f"source-{split}-{index:05d}.example.test", query, facts, variant=variant
    )
    kind = ("markdown", "json", "html", "csv")[cycle % 4]
    target = f"archive/search-{split}-{index:05d}.{EXTENSIONS[kind]}"
    brief_path = f"notes/search-{split}-{index:05d}.json"
    title = f"{topic} synthetic source report {split}-{index}"
    brief = {
        "kind": kind,
        "title": title,
        "function_name": "sum_quantities",
        "query": query,
        "retry_query": query + " quantity",
        "target_path": target,
        "instructions": "Fetch all relevant named source documents in search rank order. "
        "Write their names and quantities, computed total and each fetched document URL.",
    }
    initial = {
        brief_path: compact(brief),
        "notes/preserve.txt": f"Search preserve {split}-{index}\n",
    }
    prompt = (
        f"Read {brief_path}, search for its query, fetch the relevant source documents, and "
        f"create {target} with facts, total and each source URL. If lookup is empty or fails, "
        "use retry_query; retry a temporary fetch failure. Read the report back and verify. "
        "Keep other files unchanged. These are synthetic controlled test documents."
    )
    steps = [
        step("search_brief", "read_file", {"path": brief_path}, kind="read"),
        step(
            "search_select",
            "select_local_tools",
            {"names": ["web_search", "web_fetch"]},
            kind="select",
        ),
    ]
    if variant in {"empty_retry", "search_retry"}:
        steps.append(
            step(
                "search_failed_observation",
                "web_search",
                {"query": query},
                kind="empty_search" if variant == "empty_retry" else "failed_search",
                expected_failure=variant == "search_retry",
            )
        )
    steps.append(
        step(
            "search_query",
            "web_search",
            {"query": query + " quantity" if variant in {"empty_retry", "search_retry"} else query},
            kind="search",
        )
    )
    for source_index in range(len(facts)):
        if variant == "fetch_retry" and source_index == 0:
            steps.append(
                step(
                    "fetch_failed_observation",
                    "web_fetch",
                    {"url": ""},
                    kind="failed_fetch",
                    url_from_search=source_index,
                    expected_failure=True,
                )
            )
        steps.append(
            step(
                "search_fetch" if source_index == 0 else "search_extra_fetch",
                "web_fetch",
                {"url": ""},
                kind="fetch",
                url_from_search=source_index,
            )
        )
    steps.extend(
        [
            step(
                "search_file_select",
                "select_local_tools",
                {"names": ["read_file", "write_file"]},
                kind="select",
            ),
            step(
                "search_write",
                "write_file",
                {"path": target, "content": "", "expected_sha256": None},
                kind="artifact_write",
                artifact_from_web=brief_path,
            ),
            step("search_readback", "read_file", {"path": target}, kind="readback"),
            done("search_done"),
        ]
    )
    contract = {
        "kind": kind,
        "path": target,
        "task": {
            "title": title,
            "function_name": "sum_quantities",
            "require_citations": True,
            "items": [
                {**fact, "source": document["url"]}
                for fact, document in zip(facts, config["documents"], strict=True)
            ],
        },
    }
    goal = {**initial, target: render_artifact(kind, contract["task"])}
    program.update(
        prompt=prompt,
        initial_files=initial,
        steps=steps,
        http_fixture=config,
        goal_files=goal,
        artifact_contracts=[contract],
        goal_directories=required_directories(goal, program["initial_directories"]),
    )
    return program, {
        "target_path": target,
        "artifact_contract": contract,
        "search_variant": variant,
        "target_step": next(i for i, entry in enumerate(steps) if entry["family"] == family),
    }


def evaluate_expression(expression):
    operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul}

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](visit(node.left), visit(node.right))
        raise ValueError("Unsupported ordinary arithmetic expression")

    return visit(ast.parse(expression, mode="eval").body)


def _ordinary_program(split, index, seed, group, cycle):
    program = _base_program(split, index, seed, cycle)
    rng = random.Random(seed + SPLITS.index(split) * 100000 + index)
    a = {"train": 2, "dev": 67, "eval": 103}[split] + cycle
    b, c = rng.randint(2, 18), rng.randint(3, 24)
    expression, answer = None, None
    if group.startswith("arithmetic_"):
        expression = {
            "arithmetic_add": f"{a} + {b} + {c}",
            "arithmetic_subtract": f"{a} - {b} - {c}",
            "arithmetic_multiply": f"{a} * {b}",
            "arithmetic_mixed": f"{a} + {b} * {c}",
            "arithmetic_parentheses": f"({a} + {b}) * {c}",
            "arithmetic_units": f"{a} * {b} + {c}",
        }[group]
        answer = evaluate_expression(expression)
        prompt = (
            f"计算 {expression}，直接给出最终答案。"
            if cycle % 2 == 0
            else f"Calculate {expression} and give the final answer directly."
        )
        if group == "arithmetic_units":
            prompt = f"每箱有 {a} 件物品，有 {b} 箱，另外 {c} 件。一共有多少件？直接回答。"
        text = f"{expression.replace('*', '×')} = {answer}。\n最终答案：{answer}"
        if group == "arithmetic_units":
            text += " 件"
    elif group == "language_extract":
        value = {"name": f"{TOPICS[split][cycle % 4]} entry-{split}-{index}", "status": "draft"}
        prompt = f"只输出这段 JSON 中 name 的原文，不加解释：{compact(value)}"
        text = value["name"]
    else:
        value = [f"{split}-{index}-{suffix}" for suffix in ("gamma", "alpha", "beta")]
        rng.shuffle(value)
        prompt = f"按字典序排序字符串，返回 JSON 数组：{compact(value)}"
        text = compact(sorted(value))
    program.update(
        prompt=prompt,
        initial_directories=[],
        steps=[{"family": group, "kind": "ordinary", "text": text}],
        goal_files={},
        goal_directories=[],
    )
    return program, {
        "ordinary_group": group,
        "arithmetic_expression": expression,
        "answer": answer,
        "target_step": 0,
    }


def independent_ordinary_answer(row):
    group = row["metadata"]["ordinary_group"]
    prompt = next(message["content"] for message in row["messages"] if message["role"] == "user")
    if group.startswith("arithmetic_"):
        if group == "arithmetic_units":
            a, b, c = map(int, re.findall(r"\d+", prompt))
            return a * b + c
        expression = re.search(r"(?<!\w)[\d(][\d\s()+*\-]*\d", prompt)
        if expression is None:
            raise ValueError("Visible ordinary input has no arithmetic expression")
        return evaluate_expression(expression[0])
    delimiter = "{" if group == "language_extract" else "["
    value, _ = json.JSONDecoder().raw_decode(prompt[prompt.index(delimiter) :])
    return value["name"] if group == "language_extract" else sorted(value)


def build_program(split, index, seed, family, cycle):
    if split not in {*SPLITS, "final"}:
        raise ValueError("Use a fixed train/dev/eval stage split or final workflow split")
    if family in FILE_FAMILIES:
        return _file_program(split, index, seed, family, cycle)
    if family in GENERATION_FAMILIES:
        return _generation_program(split, index, seed, family, cycle)
    if family in SEARCH_FAMILIES:
        return _search_program(split, index, seed, family, cycle)
    if family in ORDINARY_GROUPS:
        return _ordinary_program(split, index, seed, family, cycle)
    raise ValueError("Unknown V5 family")


def artifact_goal(program, files, observed_urls=()):
    contracts = {contract["path"]: contract for contract in program.get("artifact_contracts", [])}
    if set(files) != set(program["goal_files"]):
        return False, {"error": "Final file set differs from the independent task"}
    checks = {}
    for path, expected in program["goal_files"].items():
        if path in contracts:
            contract = contracts[path]
            checks[path] = validate_artifact(
                contract["kind"], files[path], contract["task"], observed_urls=observed_urls
            )
        elif files[path] != expected:
            return False, {"error": f"Unintended or incorrect exact file bytes at {path}"}
    return all(check["valid"] for check in checks.values()), checks


def assert_program_completion(program, captured):
    if (
        captured["error"]
        or captured["compacted"]
        or len(captured["records"]) != len(program["steps"])
    ):
        raise ValueError(f"Actual V5 canonical program failed: {captured['error']}")
    urls = observed_document_urls(captured["records"][-1]["messages"])
    success, checks = artifact_goal(program, captured["final_files"], urls)
    if not success or captured["final_directories"] != program["goal_directories"]:
        raise ValueError(f"Independent V5 goal/format/preservation failed: {checks}")
    expected = sum(
        bool(call.get("expected_failure"))
        for entry in program["steps"]
        for call in entry.get("calls", [])
    )
    failures = sum(
        event["type"] in {"tool.failed", "tool.rejected"} for event in captured["tool_events"]
    )
    if expected != failures:
        raise ValueError(f"Observed full failure history differs: {failures} != {expected}")


def loss_spans(target, calls):
    if len(calls) != 1 or calls[0]["name"] != "write_file":
        return []
    content = calls[0]["arguments"]["content"]
    start = target.index("<parameter=content>\n") + len("<parameter=content>\n")
    if target[start : start + len(content)] != content:
        raise ValueError("Write loss span lost literal file bytes")
    widths = (
        (0, len(content) - len(content.lstrip("\r\n \t"))),
        (len(content.rstrip("\r\n \t")), len(content) - len(content.rstrip("\r\n \t"))),
    )
    return [
        {
            "kind": "content_boundary",
            "start": start + offset,
            "end": start + offset + width,
            "expected_text": content[offset : offset + width],
        }
        for offset, width in widths
        if width
    ]


def make_row(split, index, family, program, extra, captured):
    state = captured["records"][extra["target_step"]]
    ordinary = family in ORDINARY_GROUPS
    calls = state["expected_calls"]
    metadata = {
        "synthetic": True,
        "user_data_used": False,
        "split": split,
        "data_source": "independent_current_mobile_program_v5",
        "family": family,
        "scenario_group": program["fixture_name"],
        "ordinary_retention": ordinary,
        "runtime_mode": program["mode"],
        "runtime_autonomy": "full_access",
        "runtime_available_tools": state["runtime_available_tools"],
        "runtime_selected_tools": state["runtime_selected_tools"],
        "allowed_tools_override": None,
        "system_source": SYSTEM_SOURCE,
        "captured_runtime_prompt_sha256": state["captured_runtime_prompt_sha256"],
        "live_prompt_byte_equal": True,
        "runtime_history_replayed": True,
        "actual_full_program_completed": True,
        "native_actions_executed": False,
        "catalog_scope": captured["source_scope"],
        "stage_kind": program["steps"][extra["target_step"]]["kind"],
        "before_files": state["before_files"],
        "after_files": state["after_files"],
        "before_directories": state["before_directories"],
        "after_directories": state["after_directories"],
        "program": program,
        "controlled_http_real_tls": bool(captured["transport"]),
        **extra,
    }
    metadata["loss_spans"] = loss_spans(state["target_response"], calls)
    row = {
        "id": f"synthetic-v5-{split}-{index:05d}",
        "split": split,
        "messages": state["messages"],
        "tools": state["tools"],
        "target_response": state["target_response"],
        "expected": {"kind": "tool_call", "calls": calls}
        if calls
        else {"kind": "text", "answer": extra.get("answer")},
        "metadata": metadata,
    }
    request, prompt = build_evaluation_prompt(row)
    if digest(prompt) != state["captured_runtime_prompt_sha256"]:
        raise ValueError("Serialized V5 visible prompt differs from actual mobile request")
    actual_calls = [
        {"name": delta.tool_call.name, "arguments": delta.tool_call.arguments}
        for delta in parse_qwen_output(row["target_response"], request, row["id"])
        if delta.kind is DeltaKind.TOOL_CALL
    ]
    if actual_calls != calls:
        raise ValueError("Canonical V5 target failed the actual atomic protocol parser")
    return row


def build_workflows(split, seed):
    if split not in {"dev", "final"}:
        raise ValueError("Autonomous workflows have independently fixed dev/final inputs")
    cases = []
    families = [
        "copy_new_write",
        "copy_existing_write",
        "edit_replace_write",
        "edit_append_write",
        "edit_remove_write",
        "mkdir_only_create",
        "mkdir_write_write",
        "cas_recover_write",
        "missing_recover_write",
        "mkdir_write_write",
        *(f"generation_{kind}_write" for kind in KINDS),
        *(["search_write"] * 4),
    ]
    for index, family in enumerate(families):
        # Case inputs are separate from every stage row, including dev stage inputs.
        program, _ = build_program(
            split,
            90000 + index,
            seed + 5000,
            family,
            index % 4 if family == "search_write" else index % 2,
        )
        group = "file" if index < 10 else "format" if index < 16 else "search"
        if index == 9:
            folder = program["goal_directory"]
            receipt = f"{folder}/receipt.txt"
            content = f"Verified synthetic plan receipt {split}-{index}\n"
            program["prompt"] += (
                f" Also create {receipt} containing exactly {compact(content)} and read back "
                "both newly written files before finishing."
            )
            program["goal_files"][receipt] = content
            program["goal_directories"] = required_directories(
                program["goal_files"], program["goal_directories"]
            )
        program["required_read_paths"] = sorted(
            {
                call["arguments"]["path"]
                for entry in program["steps"]
                for call in entry.get("calls", [])
                if call["name"] == "read_file"
                and call["arguments"]["path"] in program["initial_files"]
            }
        )
        program["id"] = f"synthetic-v5-{split}-workflow-{index:02d}"
        program.pop("steps")
        program.update(
            split=split,
            group=group,
            synthetic=True,
            user_data_used=False,
            gold_history_injected=False,
        )
        cases.append(program)
    return cases


async def _generate(seed, counts, catalog_source, system_source):
    data = {**catalog_source, "seed": seed, "live_system_source": system_source}
    for split, count in zip(SPLITS, counts, strict=True):
        rows, ordinary_index, tool_index = [], 0, 0
        for index in range(count):
            if index % 5 < 2:
                family = ORDINARY_GROUPS[ordinary_index % len(ORDINARY_GROUPS)]
                cycle = ordinary_index // len(ORDINARY_GROUPS)
                ordinary_index += 1
            else:
                family = FAMILIES[tool_index % len(FAMILIES)]
                cycle = tool_index // len(FAMILIES)
                tool_index += 1
            program, extra = build_program(split, index, seed, family, cycle)
            captured = await capture_program(program, data["catalog"])
            assert_program_completion(program, captured)
            row = make_row(split, index, family, program, extra, captured)
            if (
                row["messages"][0]["content"]
                != system_source["entries"][program["mode"]]["live_system_suffix"]
            ):
                raise ValueError("Current mobile TASK/CODING system differs from the phone capture")
            rows.append(row)
            if (index + 1) % 100 == 0:
                print(f"Captured {split}: {index + 1}/{count} complete actual programs", flush=True)
        data[split] = rows
    data["dev_workflows"] = build_workflows("dev", seed)
    data["final_workflows"] = build_workflows("final", seed)
    return data


def generate_dataset(
    seed=20261001,
    counts=(1200, 200, 200),
    *,
    catalog_path=DEFAULT_CATALOG,
    system_path=DEFAULT_SYSTEM,
):
    if len(counts) != 3 or any(count < 200 or count % 200 for count in counts):
        raise ValueError("Balanced V5 splits require multiples of 200 with at least 200 rows")
    return asyncio.run(
        _generate(seed, counts, load_catalog(catalog_path), load_system_source(system_path))
    )


def validate_dataset(data):
    reports = {}
    hashes = {}
    for split in SPLITS:
        rows = data[split]
        counts = Counter(row["metadata"]["family"] for row in rows)
        tool_each, ordinary_each = len(rows) * 3 // 5 // 60, len(rows) * 2 // 5 // 8
        if any(counts[family] != tool_each for family in FAMILIES) or any(
            counts[group] != ordinary_each for group in ORDINARY_GROUPS
        ):
            raise ValueError("Every V5 family/group must have the prescribed balanced count")
        hashes[split] = set()
        for row in rows:
            metadata = row["metadata"]
            if row["split"] != split or metadata["split"] != split:
                raise ValueError("V5 split provenance is inconsistent")
            if (
                not metadata["live_prompt_byte_equal"]
                or not metadata["actual_full_program_completed"]
            ):
                raise ValueError("V5 samples require completed actual mobile captures")
            prompt_hash = digest(build_evaluation_prompt(row)[1])
            if (
                prompt_hash in hashes[split]
                or prompt_hash != metadata["captured_runtime_prompt_sha256"]
            ):
                raise ValueError("V5 canonical visible prompts repeated or changed")
            hashes[split].add(prompt_hash)
            if (
                row["messages"][0]["content"]
                != data["live_system_source"]["entries"][metadata["runtime_mode"]][
                    "live_system_suffix"
                ]
            ):
                raise ValueError("V5 mobile system no longer equals the current source capture")
            if any(
                set(message) - {"role", "content", "tool_calls", "tool_call_id"}
                for message in row["messages"]
            ):
                raise ValueError("V5 model messages contain unsupported hidden metadata")
            if metadata["ordinary_retention"]:
                independent_ordinary_answer(row)
        reports[split] = dict(counts)
    overlap = {
        f"{a}/{b}": len(hashes[a] & hashes[b])
        for a, b in (("train", "dev"), ("train", "eval"), ("dev", "eval"))
    }
    if any(overlap.values()):
        raise ValueError("V5 splits share canonical visible input")
    return {
        "family_counts": reports,
        "canonical_prompt_overlap": overlap,
        "split_isolation": True,
        "hidden_fields_passed_to_model": False,
        "current_mobile_system_verified": True,
        "canonical_targets_are_model_performance": False,
    }


def token_lengths(data, tokenizer, maximum=4096):
    records, summary, violations, sets = {}, {}, [], {kind: {} for kind in ("runtime", "official")}
    for split in SPLITS:
        records[split] = []
        for kind in sets:
            sets[kind][split] = set()
        for row in data[split]:
            measured = {"id": row["id"], "family": row["metadata"]["family"]}
            for kind in sets:
                prompt = build_evaluation_prompt(row, prompt_source=kind, tokenizer=tokenizer)[1]
                tokens = tokenizer(prompt, add_special_tokens=False)["input_ids"]
                sets[kind][split].add(digest(compact(tokens)))
                measured[kind + "_prompt"] = len(tokens)
                measured[kind] = len(
                    tokenizer(
                        prompt + row["target_response"] + "<|im_end|>", add_special_tokens=False
                    )["input_ids"]
                )
            records[split].append(measured)
            if max(measured["runtime"], measured["official"]) > maximum:
                violations.append(measured)
        summary[split] = {
            kind: {
                "min": min(item[kind] for item in records[split]),
                "max": max(item[kind] for item in records[split]),
                "total": sum(item[kind] for item in records[split]),
            }
            for kind in sets
        }
    overlap = {
        kind: {
            f"{a}/{b}": len(values[a] & values[b])
            for a, b in (("train", "dev"), ("train", "eval"), ("dev", "eval"))
        }
        for kind, values in sets.items()
    }
    return {
        "rows": records,
        "summary": summary,
        "budget": maximum,
        "violations": violations,
        "required_budget": max(
            row[kind] for rows in records.values() for row in rows for kind in sets
        ),
        "budget_passed": not violations,
        "truncation_performed": False,
        "canonical_prompt_overlap": overlap,
        "unique_inputs": {
            split: {kind: len(sets[kind][split]) for kind in sets} for split in SPLITS
        },
    }


def write_dataset(data, output, *, lengths=None):
    from training.evaluate_replay_v5 import SOURCE_DEPENDENCIES

    output = Path(output)
    if output.exists():
        raise ValueError("Use a fresh unfrozen candidate directory to preserve evidence")
    output.mkdir(parents=True)
    hashes = {}
    for name, value in [(f"{split}.jsonl", data[split]) for split in SPLITS] + [
        ("dev-workflows.jsonl", data["dev_workflows"]),
        ("final-workflows.jsonl", data["final_workflows"]),
    ]:
        path = output / name
        path.write_text(
            "".join(compact(row) + "\n" for row in value), encoding="utf-8", newline="\n"
        )
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    sources = {
        "catalog.json": json.dumps(data["catalog"], ensure_ascii=False, indent=2) + "\n",
        "android-catalog-source.json": data["catalog_capture_text"],
        "android-system-source.json": data["live_system_source"]["capture_text"],
    }
    for name, value in sources.items():
        (output / name).write_bytes(value.encode("utf-8"))
        hashes[name] = hashlib.sha256((output / name).read_bytes()).hexdigest()
    manifest = {
        "status": "unfrozen_candidate_pending_independent_review",
        "seed": data["seed"],
        "system_source": SYSTEM_SOURCE,
        "dataset_hashes": hashes,
        "counts": {split: len(data[split]) for split in SPLITS},
        "workflow_counts": {"dev": 20, "final": 20},
        "catalog_source_sha256": data["catalog_source_sha256"],
        "catalog_source": data["catalog_source"],
        "applicable_catalogs": data["applicable_catalogs"],
        "live_system_source": {
            key: value for key, value in data["live_system_source"].items() if key != "capture_text"
        },
        "source_hashes": {
            path: hashlib.sha256((ANDROID_ROOT.parent / path).read_bytes()).hexdigest()
            for path in SOURCE_DEPENDENCIES
        },
        "validation": validate_dataset(data),
        "lengths": lengths,
        "critical_write_families": list(CRITICAL_WRITE_FAMILIES),
        "fixture_policy": {
            "complete_live_system_and_applicable_menu_preserved": True,
            "complete_observed_success_and_failure_history_preserved": True,
            "complete_target_and_end_marker_preserved": True,
            "truncation_performed": False,
            "training_max_length_must_cover_complete_measured_sequences": True,
            "http_transport_routing_is_fixture_only": True,
        },
        "provenance": {
            "old_final_labels_read": False,
            "phone_user_or_file_content_read": False,
            "catalog_only_phone_capture": True,
            "model_inference_performed": False,
            "gpu_used": False,
            "actual_full_programs_replayed": sum(len(data[split]) for split in SPLITS),
            "canonical_targets_are_model_performance": False,
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (output / "README.md").write_text(
        "# V5 synthetic daily candidate\n\nUnfrozen. Current TASK and CODING both use the Android "
        "suffix and exact system-only phone captures. Stage labels are real runner continuations, "
        "not autonomous model results. File/selector/search/fetch tools execute; other complete "
        "applicable advertisements reject fixture execution.\n\n"
        "Daily formats include agendas/minutes, settings, typed records, HTML guides/animation, "
        "pure text cleanup functions and inventory reports. Search uses real controlled TLS "
        "requests "
        "through a fixture transport route, not public-network acceptance. All source bodies and "
        "histories are complete. The separate workflows contain initial state and private goals, "
        "with no gold assistant/tool history injected. Only prompt strings reach inference "
        "callbacks. Forty percent ordinary arithmetic/literal tasks do not prove open "
        "conversation retention.\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261001)
    parser.add_argument("--tokenizer", type=Path)
    parser.add_argument("--maximum", type=int, default=4096)
    parser.add_argument("--counts", type=int, nargs=3, default=(1200, 200, 200))
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a fresh candidate output; V5 remains unfrozen")
    tokenizer = None
    if args.tokenizer:
        from transformers import AutoTokenizer

        # Validate tokenizer availability before spending time on real full captures.
        tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, local_files_only=True)
    data = generate_dataset(args.seed, tuple(args.counts))
    lengths = None
    if tokenizer is not None:
        lengths = token_lengths(data, tokenizer, args.maximum)
    manifest = write_dataset(data, args.output, lengths=lengths)
    print(
        json.dumps(
            {
                "counts": manifest["counts"],
                "status": manifest["status"],
                "lengths": lengths["summary"] if lengths else None,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
