"""Prepare independent first-step and exact-menu candidate data; never alter v2."""

# Chinese punctuation is intentional in the synthetic requests.
# ruff: noqa: RUF001
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import sys
import tempfile
from collections import Counter
from pathlib import Path

ANDROID_ROOT = Path(__file__).resolve().parents[1]
for source in (ANDROID_ROOT, ANDROID_ROOT.parent / "src"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from android_adapter.local_context import SELECTION_TOOL  # noqa: E402

from training.build_dataset import call, compact, schema_catalog  # noqa: E402
from training.build_dataset_v2 import (  # noqa: E402
    SPLITS,
    SYSTEM,
    Fixture,
    _build_example,
    _result,
    _spec,
    parse_target,
    token_lengths,
)
from training.validate_dataset import validate_example  # noqa: E402

NOUNS = {
    "train": ("绒雪", "墨泉", "细竹", "远汀"),
    "dev": ("碧石", "清樱", "丹桂", "辰岛"),
    "eval": ("苔灯", "霜坡", "橘舟", "夏砾"),
}
FAMILIES = (
    "copy_initial_read",
    "edit_initial_read",
    "copy_observed_write",
    "edit_observed_write",
    "edit_read_back",
    "edit_verified_done",
    "copy_selected_read",
    "mkdir_initial_select",
    "mkdir_after_select",
    "mkdir_after_directory",
    "copy_read_back",
    "copy_verified_done",
)
TEMPLATES = {
    "train": {
        "copy": "请将 {source} 逐字复制到新文件 {destination}，保留所有空行，并核对保存的文字。",
        "edit": "把 {source} 中的阶段“初步”改为“确认”，保留其余文字和空行，完成后核验。",
        "mkdir": "创建目录 {folder}，把 {encoded} 解码得到的全文存入 {nested}，文件是新建的。",
    },
    "dev": {
        "copy": (
            "帮我将 {source} 完整备份为 {destination}。输出是新文件，之后分别核对原文件和备份。"
        ),
        "edit": (
            "在 {source} 的末尾追加 {append_encoded} 解码后的确认行，"
            "原有字节不改变，然后检查新文件。"
        ),
        "mkdir": "请先建立 {folder}，再新建 {nested}，内容需要与 {encoded} 解码后的原文完全一致。",
    },
    "eval": {
        "copy": (
            "归档 {source} 到尚不存在的 {destination}，逐字保留原文；"
            "检查归档文字后列出 archive 清单。"
        ),
        "edit": (
            "删除 {source} 中整行 {remove_encoded} 表示的引文，"
            "其余内容和空行保持原样，最后检查结果。"
        ),
        "mkdir": (
            "将 {encoded} 所代表的文本放在 {nested}，当前 {folder} 尚未创建，请完成整个保存任务。"
        ),
    },
}


def _active(fixture, task_catalog):
    specs = tuple(_spec(entry) for entry in task_catalog.values())
    turn = fixture.selector_state.prepare(fixture.entity, specs)
    active = {*turn.selected, SELECTION_TOOL}
    return [task_catalog[name]["advertisement"] for name in task_catalog if name in active], list(
        turn.selected
    )


def _instruction(task_catalog):
    available = sorted(set(task_catalog) - {SELECTION_TOOL})
    return (
        "\n# Local tools\nThe listed schemas are active. To use another available tool, first call "
        "select_local_tools with its name(s). This replaces the active list on the next call; "
        "the selector always remains available. Select only tools needed for the next action.\n"
        "Available tools for this task: " + ", ".join(available)
    )


def _row(
    catalog,
    task_catalog,
    split,
    index,
    entity,
    family,
    fixture,
    history,
    prompt,
    template,
    target,
    *,
    ordinary=False,
    criteria=None,
):
    tools, selected = _active(fixture, task_catalog)
    row = _build_example(
        catalog,
        split,
        index,
        entity,
        family,
        template,
        prompt,
        [tool["function"]["name"] for tool in tools],
        target,
        history,
        fixture,
        ordinary=ordinary,
        must_contain=criteria,
    )
    row["id"] = f"synthetic-v3-{split}-{index:05d}"
    row["tools"] = copy.deepcopy(tools)
    row["messages"][0]["content"] = SYSTEM + _instruction(task_catalog)
    row["metadata"].update(
        data_source="procedural_synthetic_v3_candidate",
        runtime_selected_tools=selected,
        runtime_available_tools=sorted(set(task_catalog) - {SELECTION_TOOL}),
        advertisement_scope="actual_file_task_profile",
        advertised_tool_count=len(tools),
        runtime_history_replayed=True,
    )
    if isinstance(target, list):
        for proposal in target:
            actual = fixture.run(proposal)
            if isinstance(actual, str) or "error" in actual:
                raise ValueError("Candidate target failed its actual tool executor")
    return row


def _tool_row(catalog, task_catalog, split, index, entity, family, fixture):
    source, destination = f"notes/{entity}.txt", f"archive/{entity}-backup.txt"
    folder, nested = f"archive/{entity}", f"archive/{entity}/record.txt"
    content = f"\n记录：{entity}\n阶段：初步\n引用：“保留空行” 🧪\n\n"
    appended, removed = f"确认：已阅读{entity}\n", "引用：“保留空行” 🧪\n"
    fixture.seed_file(source, content)
    history = []

    def step(item):
        actual = fixture.run(item)
        history.append((item, actual))
        return actual

    key = (
        "mkdir" if family.startswith("mkdir_") else "edit" if family.startswith("edit_") else "copy"
    )
    template = TEMPLATES[split][key]
    prompt = template.format(
        source=source,
        destination=destination,
        folder=folder,
        nested=nested,
        encoded=compact(content),
        append_encoded=compact(appended),
        remove_encoded=compact(removed),
    )
    read = call("read_file", path=source)
    if family == "copy_selected_read":
        step(call("select_local_tools", names=["read_file", "write_file"]))
    target, criteria = [read], None
    if family in {
        "copy_observed_write",
        "copy_read_back",
        "copy_verified_done",
        "edit_observed_write",
        "edit_read_back",
        "edit_verified_done",
    }:
        observed = step(read)
        path, modified, preimage = destination, observed["content"], None
        if family.startswith("edit_"):
            modified = (
                observed["content"].replace("阶段：初步", "阶段：确认")
                if split == "train"
                else observed["content"] + appended
                if split == "dev"
                else observed["content"].replace(removed, "")
            )
            path, preimage = source, observed["sha256"]
        write = call("write_file", path=path, content=modified, expected_sha256=preimage)
        target = [write]
        if family in {
            "copy_read_back",
            "copy_verified_done",
            "edit_read_back",
            "edit_verified_done",
        }:
            step(write)
            target = [call("read_file", path=path)]
        if family in {"copy_verified_done", "edit_verified_done"}:
            checked = step(target[0])
            assert checked["content"] == modified
            if split == "dev" and family == "copy_verified_done":
                assert step(read)["content"] == checked["content"]
            elif split == "eval" and family == "copy_verified_done":
                step(call("list_files", path="archive"))
            operation = "编辑" if family.startswith("edit_") else "复制"
            target, criteria = f"{entity}的{operation}与核验已完成。", [entity, "完成"]
    elif family.startswith("mkdir_"):
        select = call("select_local_tools", names=["make_directory", "write_file"])
        target = [select]
        if family != "mkdir_initial_select":
            step(select)
            target = [call("make_directory", path=folder)]
            if family == "mkdir_after_directory":
                step(target[0])
                target = [call("write_file", path=nested, content=content, expected_sha256=None)]
    return _row(
        catalog,
        task_catalog,
        split,
        index,
        entity,
        family,
        fixture,
        history,
        prompt,
        template,
        target,
        criteria=criteria,
    )


def _ordinary(catalog, task_catalog, split, index, entity, category, fixture, rng):
    if category < 5:
        a, b, c = rng.randrange(20, 100), rng.randrange(2, 17), rng.randrange(1, 8)
        variants = {
            "train": (a + b, a - b, a * b, a + b + c, a * b + c),
            "dev": (a + b - c, a - b + c, a * b - c, a + b + c + 2, (a + b) * c),
            "eval": ((a + b) * c, (a - b) * c, a * b + c + 1, a + b - c + 3, a * (b + c)),
        }
        expressions = {
            "train": (f"{a}+{b}", f"{a}-{b}", f"{a}*{b}", f"{a}+{b}+{c}", f"{a}*{b}+{c}"),
            "dev": (
                f"{a}+{b}-{c}",
                f"{a}-{b}+{c}",
                f"{a}*{b}-{c}",
                f"{a}+{b}+{c}+2",
                f"({a}+{b})*{c}",
            ),
            "eval": (
                f"({a}+{b})*{c}",
                f"({a}-{b})*{c}",
                f"{a}*{b}+{c}+1",
                f"{a}+{b}-{c}+3",
                f"{a}*({b}+{c})",
            ),
        }
        template = {
            "train": "计算 {expression}，直接报结果。",
            "dev": "请算一下 {expression} 的值。",
            "eval": "这道算式 {expression} 等于多少？",
        }[split]
        prompt = template.format(expression=expressions[split][category])
        value = variants[split][category]
        target, criteria, family = f"结果是 {value}。", [str(value)], f"retention_math_{category}"
    else:
        template = {
            "train": "用一句话祝贺 {entity} 活动完成。",
            "dev": "为 {entity} 的组织者写一句感谢。",
            "eval": "给准备参加 {entity} 的朋友一句祝福。",
        }[split]
        prompt = template.format(entity=entity)
        target = {
            "train": f"祝贺{entity}活动顺利完成！",
            "dev": f"感谢你为{entity}活动付出的努力！",
            "eval": f"祝你参加{entity}一切顺利！",
        }[split]
        criteria, family = [entity], "retention_conversation"
    return _row(
        catalog,
        task_catalog,
        split,
        index,
        entity,
        family,
        fixture,
        [],
        prompt,
        template + f":{category}",
        target,
        ordinary=True,
        criteria=criteria,
    )


def generate_dataset(seed=20261003, train_count=400, dev_count=96, eval_count=96):
    if any(
        type(count) is not int or not 48 <= count <= 10000
        for count in (train_count, dev_count, eval_count)
    ):
        raise ValueError("Each candidate split needs at least 48 bounded records")
    catalog = schema_catalog()
    task_catalog = {
        name: entry for name, entry in catalog.items() if not name.startswith("android_")
    }
    data = {"seed": seed, "catalog": catalog}
    with tempfile.TemporaryDirectory(prefix="agent-v3-candidate-") as temporary:
        for split, count in zip(SPLITS, (train_count, dev_count, eval_count), strict=True):
            rows, ordinary_index, tool_index = [], 0, 0
            for index in range(count):
                rng = random.Random(seed + SPLITS.index(split) * 100000 + index)
                entity = f"{rng.choice(NOUNS[split])}-v3{split[0]}-{index:04d}"
                fixture = Fixture(Path(temporary) / f"{split}-{index}", entity, catalog)
                try:
                    _active(fixture, task_catalog)
                    if index % 10 < 3:
                        row = _ordinary(
                            catalog,
                            task_catalog,
                            split,
                            index,
                            entity,
                            ordinary_index % 6,
                            fixture,
                            rng,
                        )
                        ordinary_index += 1
                    else:
                        row = _tool_row(
                            catalog,
                            task_catalog,
                            split,
                            index,
                            entity,
                            FAMILIES[tool_index % len(FAMILIES)],
                            fixture,
                        )
                        tool_index += 1
                    rows.append(row)
                finally:
                    fixture.close()
            data[split] = rows
    validate_dataset(data)
    return data


def validate_dataset(data):
    all_ids, counts = set(), {}
    for split in SPLITS:
        counts[split] = Counter(row["metadata"]["family"] for row in data[split])
        for row in data[split]:
            if row["id"] in all_ids:
                raise ValueError("Duplicate candidate ID")
            all_ids.add(row["id"])
            candidate = copy.deepcopy(row)
            for message in candidate["messages"]:
                if message["role"] == "tool":
                    message["content"] = "[UNTRUSTED TOOL DATA: fixture]\n" + compact(
                        _result(message["content"])
                    )
            if row["expected"]["kind"] == "tool_call":
                calls = parse_target(row["target_response"], data["catalog"])
                if calls != row["expected"]["calls"]:
                    raise ValueError("Candidate target and label differ")
                active = {tool["function"]["name"] for tool in row["tools"]}
                if any(item["name"] not in active for item in calls):
                    raise ValueError("Candidate calls an inactive tool")
                candidate["expected"] = {"kind": "text", "must_contain": [], "forbidden": []}
                candidate["target_response"] = (
                    "Target validated independently under exact newline contract."
                )
            validate_example(candidate, data["catalog"])
            if {tool["function"]["name"] for tool in row["tools"]} != {
                *row["metadata"]["runtime_selected_tools"],
                SELECTION_TOOL,
            }:
                raise ValueError("Candidate menu differs from actual runtime selection")
    for first, second in (("train", "dev"), ("train", "eval"), ("dev", "eval")):
        for key in ("entity", "request_template"):
            if not {row["metadata"][key] for row in data[first]}.isdisjoint(
                {row["metadata"][key] for row in data[second]}
            ):
                raise ValueError(f"Candidate {key} overlap")
    if not counts["train"].keys() <= counts["dev"].keys():
        raise ValueError("Candidate development lacks training families")
    return {
        "counts": {split: len(data[split]) for split in SPLITS},
        "families": {split: dict(counter) for split, counter in counts.items()},
        "menus_match_runtime": True,
        "dev_covers_all_train_families": True,
        "entities_templates_disjoint": True,
        "shared_first_read_tool_prefixes_are_intentional": True,
    }


def audit_replay(row, catalog):
    """Reconstruct a finished record and check its real tools and menu independently."""
    from android_adapter.local_provider import parse_qwen_output

    from agent_workspace.core.models import DeltaKind
    from training.evaluate_replay_v2 import _history, _normalized_result, _restore
    from training.evaluate_tools import build_evaluation_prompt

    allowed = {*row["metadata"]["runtime_available_tools"], SELECTION_TOOL}
    task_catalog = {name: entry for name, entry in catalog.items() if name in allowed}
    request, _ = build_evaluation_prompt(row)
    deltas = parse_qwen_output(row["target_response"], request, row["id"])
    calls = [
        {"name": delta.tool_call.name, "arguments": delta.tool_call.arguments}
        for delta in deltas
        if delta.kind is DeltaKind.TOOL_CALL
    ]
    observed = {
        (item["arguments"]["path"], result["sha256"])
        for _, item, result in _history(row)
        if item["name"] == "read_file" and "sha256" in result
    }
    with tempfile.TemporaryDirectory(prefix="agent-v3-independent-replay-") as temporary:
        fixture = Fixture(Path(temporary) / "workspace", row["metadata"]["entity"], catalog)
        try:
            _active(fixture, task_catalog)
            _restore(row, fixture)
            active, selected = _active(fixture, task_catalog)
            if active != row["tools"] or selected != row["metadata"]["runtime_selected_tools"]:
                raise ValueError("Replayed runtime menu differs from candidate advertisements")
            for item in calls:
                arguments = item["arguments"]
                if (
                    item["name"] == "write_file"
                    and arguments["expected_sha256"] is not None
                    and (arguments["path"], arguments["expected_sha256"]) not in observed
                ):
                    raise ValueError("Candidate existing-file write has no observed preimage")
                result = _normalized_result(fixture.run(item))
                if "error" in result:
                    raise ValueError("Candidate proposal failed real executor replay")
                if item["name"] == "read_file":
                    observed.add((arguments["path"], result["sha256"]))
                elif (
                    item["name"] == "write_file"
                    and (fixture.root / arguments["path"]).read_bytes()
                    != arguments["content"].encode()
                ):
                    raise ValueError("Candidate wrote different file bytes")
            return {
                "history_calls": sum(1 for _ in _history(row)),
                "target_calls": len(calls),
                "runtime_menu_exact": True,
                "actual_targets_executed": True,
            }
        finally:
            fixture.close()


def write_candidate(data, output, lengths):
    if any((output / f"{split}.jsonl").exists() for split in SPLITS):
        raise ValueError("Preserve existing candidate evidence; choose a new directory")
    output.mkdir(parents=True, exist_ok=True)
    files = {}
    for split in SPLITS:
        raw = "".join(compact(row) + "\n" for row in data[split]).encode("utf-8")
        (output / f"{split}.jsonl").write_bytes(raw)
        files[f"{split}.jsonl"] = {
            "records": len(data[split]),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    raw = (json.dumps(data["catalog"], ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (output / "catalog.json").write_bytes(raw)
    files["catalog.json"] = {"sha256": hashlib.sha256(raw).hexdigest()}
    manifest = {
        "format_version": 3,
        "candidate_only": True,
        "seed": data["seed"],
        "synthetic_only": True,
        "private_user_data_used": False,
        "model_inference_performed": False,
        "weights_trained": False,
        "samples_truncated": 0,
        "samples_excluded": 0,
        "max_sequence_tokens": 2048,
        "token_lengths": lengths,
        "validated": validate_dataset(data),
        "files": files,
        "limits": [
            "File task profile only; no Android UI perception or actions.",
            "Independent entities and templates; first-read tool prefixes "
            "are intentionally shared.",
            "Prepared as a candidate; separate weight training depends on "
            "the current round's measured result.",
        ],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "data-v3-candidate")
    parser.add_argument("--tokenizer", type=Path, required=True)
    args = parser.parse_args()
    from transformers import AutoTokenizer

    data = generate_dataset()
    tokenizer = AutoTokenizer.from_pretrained(
        args.tokenizer, local_files_only=True, trust_remote_code=False
    )
    lengths = token_lengths(data, tokenizer, 2048)
    print(compact(write_candidate(data, args.output, lengths)), flush=True)


if __name__ == "__main__":
    main()
