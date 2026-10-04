"""Generate independent live-runner synthetic candidates; never read V3 labels."""

# Chinese punctuation is deliberate in synthetic user tasks and answers.
# ruff: noqa: RUF001
from __future__ import annotations

import argparse
import ast
import asyncio
import copy
import hashlib
import json
import operator
import random
import sys
from collections import Counter
from pathlib import Path

ANDROID_ROOT = Path(__file__).resolve().parents[1]
for source in (ANDROID_ROOT, ANDROID_ROOT.parent / "src"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from android_adapter.local_provider import parse_qwen_output  # noqa: E402

from agent_workspace.core.models import DeltaKind  # noqa: E402
from training.build_dataset import compact  # noqa: E402
from training.evaluate_tools import build_evaluation_prompt  # noqa: E402
from training.runtime_fixture_v4 import (  # noqa: E402
    DEFAULT_CATALOG,
    DEFAULT_SYSTEM,
    capture_program,
    digest,
    load_catalog,
    load_system_source,
    transform_content,
)
from training.runtime_fixture_v4 import (  # noqa: E402
    historical_read_results as historical_read_results,
)

SYSTEM_SOURCE = "actual_agent_runner_provider_request"
SPLITS = ("train", "dev", "eval")
CONTENT_SHAPES = ("lf_boundaries", "crlf", "spaces", "unicode", "no_final_lf")
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
FAMILIES = (
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
    "missing_recover_read",
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
NOUNS = {
    "train": ("青穗", "暖溪", "石弦"),
    "dev": ("鹭桥", "寒谷", "映杉"),
    "eval": ("虹岬", "晴柚", "雪畔"),
}
TEMPLATES = {
    "train": {
        "copy_new": "将 {source} 的原文完整复制到尚不存在的 {target}，保留全部字符并检查保存结果。",
        "copy_existing": "用 {source} 的全文替换已有的 {target}，源文件保持原样，完成后核对。",
        "replace": "请把 {source} 里的 {old} 改成 {new}，其余内容逐字保留并验证。",
        "append": "请在 {source} 原文之后接上 {new} 表示的文本，保留原有字符并核对。",
        "remove": "从 {source} 中移除 {old} 表示的完整文本，其余字符保持原样并检查结果。",
        "mkdir_only": "建立空目录 {folder}，确认它存在且保持为空，然后回复完成。",
        "mkdir_write": (
            "建立 {folder} 并新建 {nested}，内容是 {encoded} 解码后的原文，保存后读取核对。"
        ),
        "math": "计算表达式 {expression}，写出简短的等式过程和最终答案。",
        "units": "一组有 {a} 件，共有 {b} 组，再添 {c} 件。用算式求总件数并给出最终答案。",
        "definition": "用一个简短句子说明什么是 {term}。",
        "rewrite": "将“{sentence}”改写得礼貌一些，输出改写后的一个句子。",
        "extract": (
            "读取这段合成记录 {record}，只回复 name 字段的原始字符串值，不加引号或其他文字。"
        ),
        "sort": "将合成标签数组 {items} 按字符串的 Unicode 码点升序排列，只回复 JSON 数组。",
    },
    "dev": {
        "copy_new": "把 {source} 完整备份为新文件 {target}；请核验备份字符，勿改动源资料。",
        "copy_existing": (
            "归档 {source} 的全部内容到已存在的 {target}，覆盖旧文字后检查，保留源件。"
        ),
        "replace": "更新 {source}：仅将 {old} 替换为 {new}，核查所有其他文字都一致。",
        "append": "给 {source} 增补 {new} 所代表的字符，接在文件结尾，随后确认原文与新增部分。",
        "remove": "清理 {source}：删掉 {old} 解码出的那段文字，其他字节不变，完成后验证。",
        "mkdir_only": "请新建 {folder} 这个空文件夹，核实为空后结束任务。",
        "mkdir_write": (
            "把 {encoded} 所代表的文本写入新文件 {nested}，先创建尚无的 {folder}，并检查保存文字。"
        ),
        "math": "请求出 {expression} 的值，以简短等式说明计算，再写明最终答案。",
        "units": "每包 {a} 枚，备有 {b} 包，另有 {c} 枚。列式计算全部数量并写明最终答案。",
        "definition": "请用简短的一句话解释 {term} 的含义。",
        "rewrite": "请礼貌改写“{sentence}”，只写一句改写结果。",
        "extract": "合成记录为 {record}。请提取 name 的完整值，仅输出字段文字，不附加引号或说明。",
        "sort": "对这些合成字符串 {items} 按 Unicode 码点从小到大排序，结果仅用 JSON 数组表示。",
    },
    "eval": {
        "copy_new": "为 {source} 创建逐字一致的副本 {target}，副本路径目前不存在，保存后确认一致。",
        "copy_existing": (
            "将现存文件 {target} 的文字更新为 {source} 的原文；检查复制内容，原件不得变化。"
        ),
        "replace": "在 {source} 执行文字更新：{old} 换成 {new}，没有涉及的字符全部保留，最后核验。",
        "append": "向 {source} 的现有末尾原样加入 {new} 解码后的内容，然后检查追加后的全文。",
        "remove": "请删除 {source} 内 {old} 所代表的字符序列，保存和核查余下原文。",
        "mkdir_only": "创建名为 {folder} 的空目录，检查目录确为空并报告结果。",
        "mkdir_write": (
            "完成保存任务：先建 {folder}，将 {encoded} 解码得到的全文存到新文件 {nested} 并检查。"
        ),
        "math": "求算式 {expression} 的计算结果，提供简短等式以及明确的最终答案。",
        "units": "某批每箱 {a} 个，有 {b} 箱，再加入 {c} 个。列出算式与总数的最终答案。",
        "definition": "用一句简洁的话描述 {term} 是什么。",
        "rewrite": "把“{sentence}”换为礼貌说法，回复一个句子即可。",
        "extract": "从合成条目 {record} 找到 name 内容，逐字答出该值，回复不含引号或解释。",
        "sort": "请把 {items} 中的合成标签按 Unicode 码点升序整理，回答只包含排序后的 JSON 数组。",
    },
}


def _shape(entity, shape):
    newline = "\r\n" if shape == "crlf" else "\n"
    quotation = "引文「严格保留」🧬" + newline
    body = f"日志：{entity}{newline}状态=预备{newline}{quotation}尾部：{entity}"
    if shape == "lf_boundaries":
        text = "\n\n" + body + "\n\n"
    elif shape == "crlf":
        text = "\r\n" + body + "\r\n\r\n"
    elif shape == "spaces":
        text = "\t  " + body.replace("状态=预备", "状态=预备  ") + "  \t"
    elif shape == "unicode":
        text = "Unicode：e\u0301　𐍈 🚲\n" + body + "\n非断空格：\u00a0\n"
    else:
        text = body
    return text, newline, quotation


def _step(family, name=None, arguments=None, *, kind, **extras):
    return {
        "family": family,
        "kind": kind,
        "calls": [{"name": name, "arguments": arguments or {}, **extras}],
    }


def _done(family, text):
    return {"family": family, "kind": "terminal", "text": text}


def _file_program(split, index, seed, family, tool_index):
    rng = random.Random(seed + SPLITS.index(split) * 1_000_000 + index)
    entity = f"{rng.choice(NOUNS[split])}·v4{split}·{index:04d}"
    # Rotating across families gives every shape in every split. Repeated family
    # cycles cover both runtime modes and all shapes in training.
    family_cycle = tool_index // len(FAMILIES)
    shape = CONTENT_SHAPES[(FAMILIES.index(family) + family_cycle) % len(CONTENT_SHAPES)]
    source, target = f"notes/{entity}.txt", f"archive/{entity}.txt"
    folder, nested = f"archive/{entity}", f"archive/{entity}/record.txt"
    content, newline, quotation = _shape(entity, shape)
    mode = "task" if family_cycle % 2 == 0 else "coding"
    initial = {source: content, f"notes/keep-{entity}.txt": "这是独立合成的保留文件。\n"}
    metadata = {
        "entity": entity,
        "source_path": source,
        "target_path": target,
        "content_shape": shape,
        "edit_operation": None,
    }
    steps = []
    if family.startswith(("copy_", "cas_", "missing_")):
        existing = family.startswith(("copy_existing", "cas_"))
        if existing:
            initial[target] = f"旧目标：{entity}\r\n 旧记录 \t"
        key = "copy_existing" if existing else "copy_new"
        template = TEMPLATES[split][key]
        prompt = template.format(source=source, target=target)
        read_family = "copy_existing_read_source" if existing else "copy_new_read"
        steps.append(_step(read_family, "read_file", {"path": source}, kind="read"))
        if family.startswith(("cas_", "missing_")):
            steps.append(
                _step(
                    "intentional_failed_cas",
                    "write_file",
                    {"path": target},
                    kind="failed_write",
                    content_from_read=source,
                    sha_from_read=source,
                    expected_failure=True,
                )
            )
            steps.append(
                _step(
                    "cas_recover_read" if existing else "missing_recover_read",
                    "read_file",
                    {"path": target},
                    kind="read" if existing else "missing_read",
                    expected_failure=not existing,
                )
            )
        elif existing:
            steps.append(
                _step("copy_existing_read_target", "read_file", {"path": target}, kind="read")
            )
        write_family = (
            "cas_recover_write"
            if family.startswith("cas_")
            else "missing_recover_write"
            if family.startswith("missing_")
            else "copy_existing_write"
            if existing
            else "copy_new_write"
        )
        extras = {"content_from_read": source}
        if existing:
            extras["sha_from_read"] = target
        steps.append(
            _step(
                write_family,
                "write_file",
                {"path": target, "expected_sha256": None},
                kind="write",
                **extras,
            )
        )
        prefix = (
            "cas_recover"
            if family.startswith("cas_")
            else "copy_existing"
            if existing
            else "copy_new"
        )
        steps.append(_step(prefix + "_readback", "read_file", {"path": target}, kind="readback"))
        steps.append(_done(prefix + "_done", "已复制并核对全部内容。"))
        goal_files = {**initial, target: content}
        goal_directories = None
    elif family.startswith("edit_"):
        operation = family.split("_")[1]
        edit = {"operation": operation, "old": "状态=预备", "new": "状态=已定"}
        if operation == "append":
            edit["new"] = f"{newline}确认：{entity}{newline}"
        elif operation == "remove":
            edit["old"] = quotation
        template = TEMPLATES[split][operation]
        prompt = template.format(source=source, old=compact(edit["old"]), new=compact(edit["new"]))
        metadata["edit_operation"], metadata["target_path"] = operation, source
        metadata["edit_delta"] = edit["new"] if operation != "remove" else ""
        prefix = "edit_" + operation
        steps = [
            _step(prefix + "_read", "read_file", {"path": source}, kind="read"),
            _step(
                prefix + "_write",
                "write_file",
                {"path": source},
                kind="write",
                content_from_read=source,
                sha_from_read=source,
                edit=edit,
            ),
            _step(prefix + "_readback", "read_file", {"path": source}, kind="readback"),
            _done(prefix + "_done", "已完成指定修改并核对内容。"),
        ]
        goal_files = {**initial, source: transform_content(content, edit)}
        goal_directories = None
    else:
        only = family.startswith("mkdir_only")
        key = "mkdir_only" if only else "mkdir_write"
        template = TEMPLATES[split][key]
        prompt = template.format(folder=folder, nested=nested, encoded=compact(content))
        prefix = key
        names = (
            ["make_directory", "list_files"]
            if only
            else ["make_directory", "write_file", "read_file"]
        )
        steps = [
            _step(prefix + "_select", "select_local_tools", {"names": names}, kind="select"),
            _step(prefix + "_create", "make_directory", {"path": folder}, kind="directory"),
        ]
        if only:
            steps.append(
                _step(prefix + "_list", "list_files", {"path": folder}, kind="directory_readback")
            )
            goal_files = initial.copy()
        else:
            steps.extend(
                [
                    _step(
                        prefix + "_write",
                        "write_file",
                        {"path": nested, "content": content, "expected_sha256": None},
                        kind="write",
                    ),
                    _step(prefix + "_readback", "read_file", {"path": nested}, kind="readback"),
                ]
            )
            goal_files = {**initial, nested: content}
        steps.append(
            _done(
                prefix + "_done", "目录已创建并核验。" if only else "目录和文件已创建，文字已核对。"
            )
        )
        metadata["target_path"], metadata["directory_path"] = nested if not only else folder, folder
        goal_directories = folder
    program = {
        "fixture_name": f"v4-{seed}-{split}-{index:05d}",
        "mode": mode,
        "android_system_suffix": source_suffix(mode),
        "prompt": prompt,
        "initial_directories": ["notes", "archive"],
        "initial_files": initial,
        "steps": steps,
        "goal_files": goal_files,
        "goal_directory": goal_directories,
    }
    metadata.update(
        request_template=template,
        program=program,
        target_step=next(i for i, step in enumerate(steps) if step["family"] == family),
    )
    return program, metadata


def _ordinary_program(split, index, seed, ordinary_index):
    group = ORDINARY_GROUPS[ordinary_index % len(ORDINARY_GROUPS)]
    entity = f"{NOUNS[split][ordinary_index % 3]}·普通v4{split}·{index:04d}"
    mode = "task" if (ordinary_index // len(ORDINARY_GROUPS)) % 2 == 0 else "coding"
    rng = random.Random(seed + SPLITS.index(split) * 1_000_000 + index)
    bounds = ((3, 32), (43, 72), (83, 112))[SPLITS.index(split)]
    a, b, c = (rng.randint(*bounds) for _ in range(3))
    # Each arithmetic family uses a different first operand on every pass.
    # The supported 600-row training plan has thirty passes over each family.
    a = bounds[0] + (ordinary_index // len(ORDINARY_GROUPS)) % (bounds[1] - bounds[0] + 1)
    generated, expression, answer = [], None, None
    if group.startswith("arithmetic"):
        generated = [a, b, c]
        expression = {
            "arithmetic_add": f"{a} + {b} + {c}",
            "arithmetic_subtract": f"{a} - {b} - {c}",
            "arithmetic_multiply": f"{a} * {b}",
            "arithmetic_mixed": f"{a} + {b} * {c}",
            "arithmetic_parentheses": f"({a} + {b}) * {c}",
            "arithmetic_units": f"{a} * {b} + {c}",
        }[group]
        key = "units" if group == "arithmetic_units" else "math"
        template = TEMPLATES[split][key]
        prompt = template.format(expression=expression, a=a, b=b, c=c)
        answer = evaluate_expression(expression)
        if group == "arithmetic_mixed":
            equation = f"{b} × {c} = {b * c}；{a} + {b * c} = {answer}。"
        elif group == "arithmetic_parentheses":
            equation = f"{a} + {b} = {a + b}；{a + b} × {c} = {answer}。"
        elif group == "arithmetic_units":
            equation = f"{a} × {b} = {a * b}；{a * b} + {c} = {answer}。"
        else:
            equation = f"{expression.replace('*', '×')} = {answer}。"
        unit = {"train": "件", "dev": "枚", "eval": "个"}[split]
        response = (
            f"{equation}\n最终答案：{answer}{' ' + unit if group == 'arithmetic_units' else ''}。"
        )
    elif group == "language_extract":
        record = {"name": entity + "·清单", "status": ("草案", "等待", "归档")[ordinary_index % 3]}
        template = TEMPLATES[split]["extract"]
        prompt = template.format(record=compact(record))
        response = record["name"]
    else:
        items = [f"{entity}·{suffix}" for suffix in ("gamma", "alpha", "beta")]
        rng.shuffle(items)
        template = TEMPLATES[split]["sort"]
        prompt = template.format(items=compact(items))
        response = compact(sorted(items))
    program = {
        "fixture_name": f"v4-{seed}-{split}-{index:05d}",
        "mode": mode,
        "prompt": prompt,
        "android_system_suffix": source_suffix(mode),
        "initial_directories": ["notes", "archive"],
        "initial_files": {},
        "steps": [{"family": group, "kind": "ordinary", "text": response}],
        "goal_files": {},
        "goal_directory": None,
    }
    return program, {
        "entity": entity,
        "request_template": template + ":" + group,
        "ordinary_group": group,
        "generated_numbers": generated,
        "arithmetic_expression": expression,
        "answer": answer,
        "program": program,
        "target_step": 0,
    }


def evaluate_expression(expression):
    operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul}

    def compute(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](compute(node.left), compute(node.right))
        raise ValueError("Unsupported synthetic arithmetic expression")

    return compute(ast.parse(expression, mode="eval").body)


def source_suffix(mode):
    from mobile_runtime_controller import _ANDROID_SYSTEM_SUFFIX

    return _ANDROID_SYSTEM_SUFFIX if mode == "coding" else ""


def independent_arithmetic_answer(row):
    import re

    prompt = next(message["content"] for message in row["messages"] if message["role"] == "user")
    if row["metadata"]["ordinary_group"] == "arithmetic_units":
        a, b, c = map(int, re.findall(r"\d+", prompt))
        return a * b + c
    expression = re.search(r"(?<!\w)[\d(][\d\s()+*\-]*\d", prompt)
    if expression is None:
        raise ValueError("Arithmetic expression is absent from visible user input")
    return evaluate_expression(expression[0])


def independent_language_answer(row):
    prompt = next(message["content"] for message in row["messages"] if message["role"] == "user")
    group = row["metadata"]["ordinary_group"]
    delimiter = "{" if group == "language_extract" else "["
    value, _ = json.JSONDecoder().raw_decode(prompt[prompt.index(delimiter) :])
    if group == "language_extract":
        if not isinstance(value, dict) or not isinstance(value.get("name"), str):
            raise ValueError("Visible extraction record is malformed")
        return value["name"]
    if group == "language_sort":
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError("Visible language-sort task is malformed")
        return compact(sorted(value))
    raise ValueError("Unsupported independently scored language group")


def loss_spans(target, calls, metadata):
    spans = []
    if not calls or calls[0]["name"] != "write_file":
        return spans
    content = calls[0]["arguments"]["content"]
    start = target.index("<parameter=content>\n") + len("<parameter=content>\n")
    if target[start : start + len(content)] != content:
        raise ValueError("Content loss span does not match target bytes")
    leading = len(content) - len(content.lstrip("\r\n \t"))
    trailing = len(content) - len(content.rstrip("\r\n \t"))
    for offset, width in ((0, leading), (len(content) - trailing, trailing)):
        if width:
            spans.append(
                {
                    "kind": "content_boundary",
                    "start": start + offset,
                    "end": start + offset + width,
                    "expected_text": content[offset : offset + width],
                }
            )
    delta = metadata.get("edit_delta")
    if delta:
        offset = content.index(delta)
        spans.append(
            {
                "kind": "edit_delta",
                "start": start + offset,
                "end": start + offset + len(delta),
                "expected_text": delta,
            }
        )
    return spans


def _assert_program_completion(program, capture):
    if capture["error"] or capture["compacted"] or len(capture["records"]) != len(program["steps"]):
        raise ValueError(
            f"Actual synthetic program failed: {capture['error']} "
            f"(compacted={capture['compacted']})"
        )
    final = capture["records"][-1]
    if final["after_files"] != program["goal_files"]:
        raise ValueError("Actual full program goal state did not preserve independent file bytes")
    folder = program["goal_directory"]
    if folder is not None and folder not in final["after_directories"]:
        raise ValueError("Actual full program did not create its independent goal directory")
    expected_failures = sum(
        bool(call.get("expected_failure"))
        for step in program["steps"]
        for call in step.get("calls", [])
    )
    observed_failures = sum(event["type"] != "tool.settled" for event in capture["tool_events"])
    if expected_failures != observed_failures:
        raise ValueError(
            f"Synthetic recovery failure count changed: expected {expected_failures}, "
            f"observed {observed_failures}"
        )


def _row(split, index, family, program, extra, captured, catalog):
    target_step = extra["target_step"]
    state = captured["records"][target_step]
    ordinary = program["steps"][target_step]["kind"] == "ordinary"
    calls = state["expected_calls"]
    expected = (
        {"kind": "tool_call", "calls": calls}
        if calls
        else {
            "kind": "text",
            "must_contain": [],
            "forbidden": ["<tool_call>"],
            "answer": extra.get("answer"),
        }
    )
    metadata = {
        "synthetic": True,
        "user_data_used": False,
        "split": split,
        "data_source": "independent_synthetic_live_program_v4",
        "family": family,
        "scenario_group": f"v4-{split}-{index:05d}",
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
        "catalog_scope": (
            "Complete applicable catalog from one installed Android capability state; "
            "accessibility tools were unavailable"
        ),
        "stage_kind": program["steps"][target_step]["kind"],
        "before_files": state["before_files"],
        "after_files": state["after_files"],
        "before_directories": state["before_directories"],
        "after_directories": state["after_directories"],
        **extra,
    }
    metadata["loss_spans"] = loss_spans(state["target_response"], calls, metadata)
    row = {
        "id": f"synthetic-v4-{split}-{index:05d}",
        "split": split,
        "messages": state["messages"],
        "tools": state["tools"],
        "target_response": state["target_response"],
        "expected": expected,
        "metadata": metadata,
    }
    request, prompt = build_evaluation_prompt(row)
    if digest(prompt) != state["captured_runtime_prompt_sha256"]:
        raise ValueError("Serialized visible request differs from actual captured runtime prompt")
    actual_calls = [
        {"name": delta.tool_call.name, "arguments": delta.tool_call.arguments}
        for delta in parse_qwen_output(row["target_response"], request, row["id"])
        if delta.kind is DeltaKind.TOOL_CALL
    ]
    if calls != actual_calls:
        raise ValueError("Actual atomic parser changed a synthetic target")
    return row


async def _generate(seed, counts, source):
    data = {"seed": seed, **source}
    for split, count in zip(SPLITS, counts, strict=True):
        rows, ordinary_index, tool_index = [], 0, 0
        for index in range(count):
            if index % 5 < 2:
                program, extra = _ordinary_program(split, index, seed, ordinary_index)
                family = extra["ordinary_group"]
                ordinary_index += 1
            else:
                family = FAMILIES[tool_index % len(FAMILIES)]
                program, extra = _file_program(split, index, seed, family, tool_index)
                tool_index += 1
            captured = await capture_program(program, data["catalog"])
            _assert_program_completion(program, captured)
            system_evidence = data["live_system_source"]["entries"][program["mode"]]
            for record in captured["records"]:
                if record["messages"][0]["content"] != system_evidence["live_system_suffix"]:
                    raise ValueError(
                        "Actual generated runner system differs from the system-only phone capture"
                    )
            rows.append(_row(split, index, family, program, extra, captured, data["catalog"]))
        data[split] = rows
    validate_dataset(data)
    return data


def generate_dataset(
    seed=20261004,
    train_count=600,
    dev_count=120,
    eval_count=120,
    *,
    catalog_source=DEFAULT_CATALOG,
    system_source=DEFAULT_SYSTEM,
):
    counts = (train_count, dev_count, eval_count)
    if any(type(count) is not int or count < 120 or count > 10000 or count % 5 for count in counts):
        raise ValueError("Each split requires at least 120 records in a multiple of five")
    source = load_catalog(Path(catalog_source))
    source["live_system_source"] = load_system_source(Path(system_source))
    return asyncio.run(_generate(seed, counts, source))


def validate_dataset(data):
    ids, reports = set(), {}
    for split in SPLITS:
        counts = Counter(row["metadata"]["family"] for row in data[split])
        reports[split] = dict(counts)
        if set(FAMILIES) - set(counts):
            raise ValueError("A split lacks a real program continuation family")
        if (
            sum(row["metadata"]["ordinary_retention"] for row in data[split]) * 5
            != len(data[split]) * 2
        ):
            raise ValueError(
                "The ordinary mixture must remain exactly forty percent by sample count"
            )
        for row in data[split]:
            if row["id"] in ids:
                raise ValueError("Duplicate synthetic record ID")
            ids.add(row["id"])
            metadata = row["metadata"]
            if row["split"] != split or metadata["split"] != split:
                raise ValueError("Row split differs from its explicit dataset split")
            if metadata["user_data_used"] is not False or metadata["synthetic"] is not True:
                raise ValueError("Only new synthetic data is accepted")
            request, prompt = build_evaluation_prompt(row)
            if digest(prompt) != metadata["captured_runtime_prompt_sha256"]:
                raise ValueError("Visible prompt changed since real runtime capture")
            for tool in row["tools"]:
                if tool != data["catalog"][tool["function"]["name"]]["advertisement"]:
                    raise ValueError("Advertisement differs from the immutable real catalog")
            calls = [
                {"name": delta.tool_call.name, "arguments": delta.tool_call.arguments}
                for delta in parse_qwen_output(row["target_response"], request, row["id"])
                if delta.kind is DeltaKind.TOOL_CALL
            ]
            if calls != row["expected"].get("calls", []):
                raise ValueError("Parsed target differs from independently structured calls")
            if metadata["ordinary_retention"] and metadata["ordinary_group"].startswith(
                "arithmetic"
            ):
                if independent_arithmetic_answer(row) != row["expected"]["answer"]:
                    raise ValueError("Arithmetic label differs from visible task calculation")
            elif (
                metadata["ordinary_retention"]
                and independent_language_answer(row) != row["target_response"]
            ):
                raise ValueError("Language label differs from visible task calculation")
            for span in metadata["loss_spans"]:
                if row["target_response"][span["start"] : span["end"]] != span["expected_text"]:
                    raise ValueError("Hidden critical loss span does not match exact target text")
            changed = copy.deepcopy(row)
            changed["metadata"] = {"hidden_canary": "V4_METADATA_CANARY"}
            changed["expected"] = {"hidden_canary": "V4_LABEL_CANARY"}
            changed["target_response"] = "V4_TARGET_CANARY"
            if build_evaluation_prompt(changed)[1] != prompt:
                raise ValueError("Hidden scoring or loss fields leak into runtime inputs")
    for first, second in (("train", "dev"), ("train", "eval"), ("dev", "eval")):
        for field in ("entity", "request_template", "scenario_group"):
            if {row["metadata"][field] for row in data[first]} & {
                row["metadata"][field] for row in data[second]
            }:
                raise ValueError("Split entities or request templates overlap")
        first_values = {
            value for row in data[first] for value in row["metadata"].get("generated_numbers", [])
        }
        second_values = {
            value for row in data[second] for value in row["metadata"].get("generated_numbers", [])
        }
        if first_values & second_values:
            raise ValueError("Split generated arithmetic values overlap")
    return {
        "families": reports,
        "split_isolation": True,
        "hidden_field_guard_passed": True,
        "examples": len(ids),
    }


def audit_replay(row, catalog):
    metadata = row["metadata"]
    capture = asyncio.run(capture_program(metadata["program"], catalog))
    _assert_program_completion(metadata["program"], capture)
    state = capture["records"][metadata["target_step"]]
    for key in ("messages", "tools", "target_response"):
        if state[key] != row[key]:
            raise ValueError(f"Actual replay {key} changed from the recorded target/prompt")
    if state["expected_calls"] != row["expected"].get("calls", []):
        raise ValueError("Recorded target calls differ from actual resolved program")
    for key in ("before_files", "after_files", "before_directories", "after_directories"):
        if state[key] != metadata[key]:
            raise ValueError("Recorded state differs from actual replay")
    return {
        "runtime_menu_exact": True,
        "live_system_exact": True,
        "actual_histories_replayed": True,
        "actual_targets_executed": True,
        "complete_synthetic_program_verified": True,
        "autonomous_model_task_success": None,
    }


def token_lengths(data, tokenizer, maximum=2560):
    summaries, rows, violations, overlaps, unique_inputs = {}, {}, [], {}, {}
    prompt_ids = {kind: {} for kind in ("runtime", "official")}
    for split in SPLITS:
        rows[split] = []
        for kind in prompt_ids:
            prompt_ids[kind][split] = set()
        for row in data[split]:
            runtime = build_evaluation_prompt(row)[1]
            official = tokenizer.apply_chat_template(
                row["messages"],
                tools=row["tools"],
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            measured = {"id": row["id"], "family": row["metadata"]["family"]}
            for kind, prompt in (("runtime", runtime), ("official", official)):
                tokens = tokenizer(prompt, add_special_tokens=False)["input_ids"]
                prompt_ids[kind][split].add(digest(compact(tokens)))
                measured[kind] = len(
                    tokenizer(
                        prompt + row["target_response"] + "<|im_end|>", add_special_tokens=False
                    )["input_ids"]
                )
            rows[split].append(measured)
            if max(measured["runtime"], measured["official"]) > maximum:
                violations.append(measured)
        summaries[split] = {
            kind: {
                "min": min(row[kind] for row in rows[split]),
                "max": max(row[kind] for row in rows[split]),
                "total": sum(row[kind] for row in rows[split]),
            }
            for kind in prompt_ids
        }
        ordinary_inputs = [
            digest(build_evaluation_prompt(row)[1])
            for row in data[split]
            if row["metadata"]["ordinary_retention"]
        ]
        unique_inputs[split] = {
            "runtime_unique_prompts": len(prompt_ids["runtime"][split]),
            "ordinary_samples": len(ordinary_inputs),
            "ordinary_unique_visible_prompts": len(set(ordinary_inputs)),
            "ordinary_repeated_visible_prompts": len(ordinary_inputs) - len(set(ordinary_inputs)),
        }
    for kind, splits in prompt_ids.items():
        overlaps[kind] = {
            f"{first}/{second}": len(splits[first] & splits[second])
            for first, second in (("train", "dev"), ("train", "eval"), ("dev", "eval"))
        }
    return {
        "summary": summaries,
        "rows": rows,
        "budget": maximum,
        "violations": violations,
        "required_budget": max(
            row[kind] for split in rows.values() for row in split for kind in prompt_ids
        ),
        "truncation_performed": False,
        "canonical_prompt_overlap": overlaps,
        "unique_inputs": unique_inputs,
        "budget_passed": not violations,
    }


def write_dataset(data, output, *, lengths=None):
    output = Path(output)
    if output.exists():
        raise ValueError("Choose a fresh candidate directory; old evidence is immutable")
    output.mkdir(parents=True)
    hashes = {}
    for split in SPLITS:
        path = output / f"{split}.jsonl"
        path.write_text(
            "".join(compact(row) + "\n" for row in data[split]), encoding="utf-8", newline="\n"
        )
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / "catalog.json").write_text(
        json.dumps(data["catalog"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    hashes["catalog.json"] = hashlib.sha256((output / "catalog.json").read_bytes()).hexdigest()
    source_files = {
        "android-catalog-source.json": data["catalog_capture_text"],
        "android-system-source.json": data["live_system_source"]["capture_text"],
    }
    for name, text in source_files.items():
        (output / name).write_bytes(text.encode("utf-8"))
        hashes[name] = hashlib.sha256((output / name).read_bytes()).hexdigest()
    manifest = {
        "status": "unfrozen_candidate_pending_independent_review",
        "seed": data["seed"],
        "catalog_source_sha256": data["catalog_source_sha256"],
        "catalog_source": data["catalog_source"],
        "live_system_source": {
            key: value for key, value in data["live_system_source"].items() if key != "capture_text"
        },
        "applicable_catalogs": data["applicable_catalogs"],
        "system_source": SYSTEM_SOURCE,
        "source_hashes": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                Path(__file__),
                ANDROID_ROOT / "training/runtime_fixture_v4.py",
                ANDROID_ROOT / "android_adapter/local_context.py",
                ANDROID_ROOT / "android_adapter/local_provider.py",
                ANDROID_ROOT / "mobile_runtime_controller.py",
                ANDROID_ROOT.parent / "src/agent_workspace/application/runner.py",
            )
        },
        "dataset_hashes": hashes,
        "counts": {split: len(data[split]) for split in SPLITS},
        "ordinary_fraction": {
            split: sum(row["metadata"]["ordinary_retention"] for row in data[split])
            / len(data[split])
            for split in SPLITS
        },
        "validation": validate_dataset(data),
        "lengths": lengths,
        "fixture_policy": {
            "synthetic_entity_and_body_shortening_performed": False,
            "complete_live_system_and_applicable_menu_preserved": True,
            "complete_observed_success_and_failure_history_preserved": True,
            "complete_target_and_end_marker_preserved": True,
            "truncation_performed": False,
            "training_max_length_must_cover_complete_measured_sequences": True,
        },
        "provenance": {
            "v3_labels_read": False,
            "phone_user_or_file_content_read": False,
            "catalog_only_phone_capture": True,
            "model_inference_performed": False,
            "gpu_used": False,
            "actual_full_programs_replayed": sum(len(data[split]) for split in SPLITS),
            "sampled_row_histories_and_targets_independently_replayed": False,
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (output / "README.md").write_text(
        "# V4 independent synthetic candidate\n\n"
        "Unfrozen; independent review and Root acceptance are required before training. "
        "Each record captures the actual AgentRunner provider request and complete "
        "applicable catalog from one installed capability state. TASK uses the actual "
        "raw-service system without the Android suffix; CODING uses the mobile system "
        "including that suffix. Both systems equal system-only phone evidence byte for byte. "
        "Mobile TASK with suffix, custom workspace prompt assembly and connected native UI "
        "tools are not covered by this candidate. Only disposable real file/selector tools "
        "execute here; other full-catalog advertisements reject execution in the CPU fixture.\n\n"
        "All programs are newly synthesized; V3 final labels and phone text/files are excluded. "
        "Forty percent of samples are ordinary arithmetic, literal extraction and sorting. "
        "This does not establish general conversation preservation. Arithmetic targets "
        "contain short equations and explicit final answers. Every full program completes "
        "against independently specified goal bytes. Continuation replay does not measure "
        "autonomous model success. All recorded prompts and error results are untruncated.\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--catalog-source", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--system-source", type=Path, default=DEFAULT_SYSTEM)
    parser.add_argument("--tokenizer", type=Path)
    parser.add_argument("--train-count", type=int, default=600)
    parser.add_argument("--dev-count", type=int, default=120)
    parser.add_argument("--eval-count", type=int, default=120)
    parser.add_argument("--seed", type=int, default=20261004)
    parser.add_argument("--maximum-tokens", type=int, default=2560)
    args = parser.parse_args()
    data = generate_dataset(
        args.seed,
        args.train_count,
        args.dev_count,
        args.eval_count,
        catalog_source=args.catalog_source,
        system_source=args.system_source,
    )
    lengths = None
    if args.tokenizer:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, local_files_only=True)
        lengths = token_lengths(data, tokenizer, args.maximum_tokens)
    manifest = write_dataset(data, args.output, lengths=lengths)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "counts": manifest["counts"],
                "lengths": lengths["summary"] if lengths else None,
                "budget_passed": lengths["budget_passed"] if lengths else None,
            },
            ensure_ascii=False,
        )
    )
    if lengths is not None and not lengths["budget_passed"]:
        print(
            f"Untruncated candidate requires at least {lengths['required_budget']} tokens; "
            f"{len(lengths['violations'])} rows exceed {args.maximum_tokens}.",
            file=sys.stderr,
        )
        raise SystemExit(2)


if __name__ == "__main__":
    main()
