"""Evaluate complete independent V5 cases without checkpoint selection.

HF and GGUF share the reviewed greedy output/turn budgets and runtime prompts.
Every generation is archived before semantic scoring, including process errors.
Final labels are available only to the scorer, never to the inference callback.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import importlib.metadata
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path


class GenerationFailure(RuntimeError):
    """A failed inference still carries its untouched raw/backend evidence."""

    def __init__(self, message: str, prediction: dict):
        super().__init__(message)
        self.prediction = prediction


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("model", "eval", "final-workflows", "catalog", "plan", "final-manifest", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--final-manifest-sha256", required=True)
    parser.add_argument("--context-tokens", type=int, required=True)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--gguf", type=Path)
    parser.add_argument("--completion-executable", type=Path)
    parser.add_argument("--completion-receipt-patch", type=Path)
    parser.add_argument("--completion-build", type=Path)
    parser.add_argument("--paired-with", type=Path)
    parser.add_argument("--threads", type=int, default=6)
    parser.add_argument("--gpu-layers", type=int, default=0)
    parser.add_argument("--process-timeout", type=int, default=240)
    return parser


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_records(raw: bytes) -> list[dict]:
    return [json.loads(line) for line in raw.decode("utf-8-sig").splitlines() if line.strip()]


def validate_final_manifest(
    raw: bytes,
    *,
    expected_sha256: str,
    plan: dict,
    eval_sha256: str,
    final_workflows_sha256: str,
    catalog_sha256: str,
) -> dict:
    """The separately approved manifest hash pins final data outside the trainer."""
    if (
        not isinstance(expected_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        or hashlib.sha256(raw).hexdigest() != expected_sha256
    ):
        raise ValueError("Final manifest differs from the independently approved SHA-256")
    manifest = json.loads(raw)
    hashes = manifest.get("dataset_hashes", {})
    for name, actual in (
        ("eval.jsonl", eval_sha256),
        ("final-workflows.jsonl", final_workflows_sha256),
        ("catalog.json", catalog_sha256),
    ):
        if hashes.get(name) != actual:
            raise ValueError(f"Frozen final input differs from its manifest: {name}")
    for name, expected in (
        ("train.jsonl", plan["train_sha256"]),
        ("dev.jsonl", plan["dev_sha256"]),
        ("dev-workflows.jsonl", plan["dev_workflows_sha256"]),
        ("catalog.json", plan["catalog_sha256"]),
    ):
        if hashes.get(name) != expected:
            raise ValueError(f"Final manifest differs from the reviewed training plan: {name}")
    return manifest


def backend_environment(root: Path) -> dict:
    versions, metadata_hashes = {}, {}
    for name in (
        "torch",
        "transformers",
        "tokenizers",
        "peft",
        "safetensors",
        "accelerate",
        "huggingface_hub",
        "pydantic",
        "httpx",
        "cryptography",
    ):
        distribution = importlib.metadata.distribution(name)
        versions[name] = distribution.version
        metadata_hashes[name] = {
            filename: hashlib.sha256(content.encode("utf-8")).hexdigest() if content else None
            for filename in ("METADATA", "RECORD")
            for content in (distribution.read_text(filename),)
        }
    return {
        "versions": versions,
        "distribution_metadata_sha256": metadata_hashes,
        "python_version": sys.version,
        "python_implementation": sys.implementation.name,
        "python_executable_sha256": sha256_file(Path(sys.executable)),
        "uv_lock_sha256": sha256_file(root / "uv.lock"),
    }


def validate_completion_patch(path: Path) -> tuple[dict, list[Path]]:
    from training import patch_completion_receipt as patch

    evidence = json.loads(path.read_bytes())
    source = Path(evidence.get("source", "")) / patch.RELATIVE
    if evidence.get("archive_sha256") != patch.ARCHIVE_SHA256:
        raise ValueError("Completion source archive differs from the pinned backend")
    if evidence.get("patch_helper_sha256") != sha256_file(Path(patch.__file__)):
        raise ValueError("Completion receipt patch helper differs from the reviewed source")
    if not source.is_file() or evidence.get("patched_source_sha256") != sha256_file(source):
        raise ValueError("Actual patched completion source differs from its receipt provenance")
    if (
        evidence.get("android_jni_modified") is not False
        or evidence.get("model_weights_modified") is not False
    ):
        raise ValueError(
            "Completion receipt patch must preserve the Android engine and model weights"
        )
    return evidence, [Path(patch.__file__), source]


def validate_completion_build(path: Path, executable: Path, patch: dict) -> tuple[dict, list[Path]]:
    evidence = json.loads(path.read_bytes())
    if (
        evidence.get("build_passed") is not True
        or evidence.get("source_patch") != patch
        or evidence.get("android_engine_modified") is not False
    ):
        raise ValueError("Completion build differs from its reviewed receipt source patch")
    if Path(
        evidence.get("completion_executable", "")
    ).resolve() != executable.resolve() or evidence.get("completion_sha256") != sha256_file(
        executable
    ):
        raise ValueError("Actual completion binary differs from the pinned build result")
    cache = executable.parent.parent / "CMakeCache.txt"
    if not cache.is_file() or evidence.get("build_cache_sha256") != sha256_file(cache):
        raise ValueError("Completion build cache differs from the pinned compilation settings")
    return evidence, [cache]


def _unique_ids(rows, name):
    identifiers = [row.get("id") for row in rows]
    if any(not isinstance(value, str) or not value for value in identifiers) or len(
        set(identifiers)
    ) != len(identifiers):
        raise ValueError(f"Every {name} record requires a unique nonempty ID")
    return identifiers


def validate_final_records(plan: dict, stage: list[dict], workflows: list[dict]) -> None:
    """Require the original 200 stages and 20 workflows, with fixed coverage."""
    if len(stage) != 200 or len(workflows) != 20:
        raise ValueError("Final evaluation requires all 200 stage and 20 workflow cases")
    _unique_ids(stage, "final stage")
    _unique_ids(workflows, "final workflow")
    ordinary, tools = set(plan["ordinary_families"]), set(plan["tool_families"])
    counts = Counter()
    for row in stage:
        metadata = row.get("metadata", {})
        family = metadata.get("family")
        if row.get("split") != "eval" or metadata.get("split") != "eval":
            raise ValueError("Final stages must preserve their original eval split")
        if (
            family not in ordinary | tools
            or type(metadata.get("ordinary_retention")) is not bool
            or metadata["ordinary_retention"] != (family in ordinary)
        ):
            raise ValueError("Final family classifications differ from the fixed plan")
        if not isinstance(row.get("messages"), list) or not row["messages"]:
            raise ValueError("Final stages require preceding visible messages")
        if row["messages"][-1].get("role") == "assistant":
            raise ValueError("Final supervision cannot be part of the visible preceding input")
        counts[family] += 1
    if set(counts) != ordinary | tools or any(
        count != (10 if family in ordinary else 2) for family, count in counts.items()
    ):
        raise ValueError("Final evaluation requires every fixed family's complete count")
    if any(row.get("split") != "final" for row in workflows):
        raise ValueError("Final workflows must preserve their original final split")
    if Counter(row.get("group") for row in workflows) != {"file": 10, "format": 6, "search": 4}:
        raise ValueError("Final workflow groups differ from the fixed twenty-case coverage")


def audit_context_budget(
    input_tokens: int, *, max_new_tokens: int, context_tokens: int, bos_margin: int
) -> dict:
    for name, value in (
        ("input tokens", input_tokens),
        ("output budget", max_new_tokens),
        ("context tokens", context_tokens),
    ):
        if type(value) is not int or value < 1:
            raise ValueError(f"The explicit {name} must be a positive integer")
    if type(bos_margin) is not int or bos_margin < 0:
        raise ValueError("The context BOS margin must be a nonnegative integer")
    required = input_tokens + max_new_tokens + bos_margin
    evidence = {
        "requested_context_tokens": context_tokens,
        "input_tokens": input_tokens,
        "reserved_output_tokens": max_new_tokens,
        "reserved_bos_tokens": bos_margin,
        "required_context_tokens": required,
        "fits": required <= context_tokens,
        "input_truncated": False,
        "context_shift": False,
        "automatic_memory_fitting": False,
    }
    if required > context_tokens:
        raise ValueError(
            f"Full prompt and output budget exceed context: {required} > {context_tokens}"
        )
    return evidence


def strip_terminal_footer_bytes(stdout: bytes) -> tuple[bytes, bool]:
    for newline in (b"\r\n", b"\n"):
        for count in (3, 2, 1):
            footer = b" [end of text]" + newline * count
            if stdout.endswith(footer):
                return stdout[: -len(footer)], True
    return stdout, False


def effective_completion_context(stderr: str, *, requested: int) -> int:
    values = [int(value) for value in re.findall(r"\bn_ctx(?:_per_seq)?\s*=\s*(\d+)\b", stderr)]
    if not values or set(values) != {requested}:
        raise ValueError("Completion backend context evidence is missing or differs from request")
    return requested


def parse_completion_receipt(
    stderr: str, *, requested_context: int, official_input_tokens: int, max_new_tokens: int
) -> dict:
    """Accept the pinned backend's measurement, never a literal model footer."""
    prefix = "AGENT_EVALUATION_STATUS "
    matches = [line[len(prefix) :] for line in stderr.splitlines() if line.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError("Completion requires exactly one measured backend status receipt")
    result = json.loads(matches[0])
    keys = {
        "schema_version",
        "input_tokens",
        "context_tokens",
        "generated_tokens",
        "eog",
        "input_truncated",
        "context_shifted",
        "context_full",
    }
    if not isinstance(result, dict) or set(result) != keys:
        raise ValueError("Completion status receipt has missing or unknown fields")
    for name in ("schema_version", "input_tokens", "context_tokens", "generated_tokens"):
        if type(result[name]) is not int or result[name] < 1:
            raise ValueError(f"Measured completion receipt {name} must be a positive integer")
    for name in ("eog", "input_truncated", "context_shifted", "context_full"):
        if type(result[name]) is not bool:
            raise ValueError(f"Measured completion receipt {name} must be explicitly Boolean")
    if result["schema_version"] != 1 or result["context_tokens"] != requested_context:
        raise ValueError("Measured completion context/schema differs from the fixed request")
    if result["input_tokens"] not in {official_input_tokens, official_input_tokens + 1}:
        raise ValueError("Measured complete prompt length differs beyond the reserved BOS margin")
    if result["generated_tokens"] > max_new_tokens:
        raise ValueError("Measured completion exceeds the fixed generation token budget")
    if any(result[name] for name in ("input_truncated", "context_shifted", "context_full")):
        raise ValueError("Completion changed the complete prompt or exhausted its fixed context")
    audit_context_budget(
        result["input_tokens"],
        max_new_tokens=max_new_tokens,
        context_tokens=requested_context,
        bos_margin=0,
    )
    return result


def completion_command(
    *,
    executable: Path,
    gguf: Path,
    prompt: Path,
    context_tokens: int,
    max_new_tokens: int,
    seed: int,
    threads: int,
    gpu_layers: int,
) -> list[str]:
    if type(threads) is not int or threads < 1 or type(gpu_layers) is not int or gpu_layers < 0:
        raise ValueError("Completion threads and GPU-layer settings are invalid")
    return [
        str(executable),
        "-m",
        str(gguf),
        "-f",
        str(prompt),
        "--no-conversation",
        "--temp",
        "0",
        "--no-display-prompt",
        "--no-escape",
        "--simple-io",
        "--no-context-shift",
        "--fit",
        "off",
        "--log-verbosity",
        "1",
        "--seed",
        str(seed),
        "-c",
        str(context_tokens),
        "-n",
        str(max_new_tokens),
        "-t",
        str(threads),
        "-tb",
        str(threads),
        "-ngl",
        str(gpu_layers),
    ]


def run_completion_bytes(command: list[str], folder: Path, *, timeout: int) -> dict:
    stdout_path, stderr_path = folder / "stdout.bin", folder / "stderr.bin"
    error, timed_out, returncode = None, False, None
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        try:
            process = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout,
                check=True,
            )
            returncode = process.returncode
        except subprocess.TimeoutExpired as failure:
            timed_out = True
            error = f"{type(failure).__name__}: completion timed out after {timeout} seconds"
        except subprocess.CalledProcessError as failure:
            returncode = failure.returncode
            error = f"{type(failure).__name__}: completion exited with code {returncode}"
        except OSError as failure:
            error = f"{type(failure).__name__}: {failure}"
    stdout_raw, stderr_raw = stdout_path.read_bytes(), stderr_path.read_bytes()
    try:
        stdout = stdout_raw.decode("utf-8")
    except UnicodeDecodeError:
        stdout = stdout_raw.decode("utf-8", errors="replace")
        error = error or "Completion stdout is not valid UTF-8; original bytes were preserved"
    return {
        "stdout": stdout,
        "stderr": stderr_raw.decode("utf-8", errors="replace"),
        "stdout_path": str(stdout_path.resolve()),
        "stderr_path": str(stderr_path.resolve()),
        "stdout_sha256": hashlib.sha256(stdout_raw).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr_raw).hexdigest(),
        "error": error,
        "timed_out": timed_out,
        "returncode": returncode,
    }


def reserve_output(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=False)


def write_report(path: Path, report: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    temporary.replace(path)


def snapshot_sources(files: list[Path], folder: Path) -> list[dict]:
    folder.mkdir(parents=True, exist_ok=False)
    rows = []
    for index, source in enumerate(dict.fromkeys(path.resolve() for path in files)):
        content = source.read_bytes()
        snapshot = folder / f"{index:03d}-{source.name}"
        snapshot.write_bytes(content)
        rows.append(
            {
                "source": str(source),
                "snapshot": str(snapshot.resolve()),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return rows


def verify_pinned_files(rows: list[dict]) -> None:
    for row in rows:
        if sha256_file(Path(row["source"])) != row["sha256"]:
            raise ValueError(f"Pinned evaluation input or source changed: {row['source']}")
        if row.get("snapshot") and sha256_file(Path(row["snapshot"])) != row["sha256"]:
            raise ValueError(f"Pinned source snapshot changed: {row['snapshot']}")


def generate_and_score_final_stages(
    records: list[dict],
    *,
    dataset_sha256: str,
    generation_config: dict,
    model_identity: dict,
    build_visible_prompt,
    generate_visible,
    score_report,
    catalog: dict,
    on_prediction=None,
) -> tuple[dict, dict]:
    """Inference receives only messages/tools; independent scoring retains all rows."""
    identifiers = _unique_ids(records, "final stage")
    if not identifiers or any(row.get("split") != "eval" for row in records):
        raise ValueError("Independent stage inference requires original eval records")
    raw = {
        "split": "eval",
        "dataset_sha256": dataset_sha256,
        "eval_sha256": dataset_sha256,
        "generation_config": copy.deepcopy(generation_config),
        "model_identity": copy.deepcopy(model_identity),
        "samples": [],
        "expected_answers_given_to_model": False,
        "private_user_data_used": False,
        "fresh_final_used_for_selection": False,
    }
    for row in records:
        visible = copy.deepcopy({"messages": row["messages"], "tools": row.get("tools", [])})
        prompt = build_visible_prompt(visible)
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("Visible final prompt must be a nonempty string")
        prediction = {
            "id": row["id"],
            "visible_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "prediction_generation_success": False,
            "generation_error": None,
            "raw_output": "",
            "output_truncated": False,
        }
        started = time.monotonic()
        try:
            generated = generate_visible(prompt, row["id"])
            if not isinstance(generated, dict) or not isinstance(generated.get("raw_output"), str):
                raise ValueError("Final inference must preserve a raw string continuation")
            if type(generated.get("output_truncated")) is not bool:
                raise ValueError("Final inference requires explicit truncation status")
            prediction.update(copy.deepcopy(generated))
            prediction["prediction_generation_success"] = generated.get(
                "prediction_generation_success", True
            )
            if type(prediction["prediction_generation_success"]) is not bool:
                raise ValueError("Final generation status must be Boolean")
        except Exception as failure:
            if isinstance(failure, GenerationFailure):
                prediction.update(copy.deepcopy(failure.prediction))
            prediction["prediction_generation_success"] = False
            prediction["generation_error"] = f"{type(failure).__name__}: {failure}"
        prediction["id"] = row["id"]
        prediction["visible_prompt_sha256"] = hashlib.sha256(prompt.encode()).hexdigest()
        prediction["elapsed_seconds"] = time.monotonic() - started
        raw["samples"].append(prediction)
        if on_prediction:
            on_prediction(raw)
    scored = score_report(records, copy.deepcopy(raw), catalog)
    if scored.get("split") != "eval":
        raise ValueError("Final scorer must preserve the original eval split")
    scored_ids = _unique_ids(scored.get("samples", []), "scored final stage")
    if set(scored_ids) != set(identifiers):
        raise ValueError("Final scorer changed the complete generation denominator")
    raw_by_id = {row["id"]: row for row in raw["samples"]}
    for sample in scored["samples"]:
        generated = raw_by_id[sample["id"]]
        for key in ("visible_prompt_sha256", "prediction_generation_success", "output_truncated"):
            sample[key] = generated[key]
        if (not generated["prediction_generation_success"] or generated["output_truncated"]) and (
            sample.get("behavior_success") is True or sample.get("ordinary_correct") is True
        ):
            raise ValueError("A failed or truncated final generation cannot claim success")
    scored.update(
        dataset_sha256=dataset_sha256,
        generation_config=copy.deepcopy(generation_config),
        model_identity=copy.deepcopy(model_identity),
        raw_generation_denominator=len(records),
        fresh_final_used_for_selection=False,
    )
    return scored, raw


def validate_final_stage_report(report: dict, records: list[dict]) -> dict:
    """Validate scored classifications/status without a dev-selection entry point."""
    if report.get("split") != "eval":
        raise ValueError("Final stage report must retain original eval split")
    indexed = {row["id"]: row for row in records}
    if set(_unique_ids(report.get("samples", []), "scored final")) != set(indexed):
        raise ValueError("Final stage report dropped or added generation cases")
    families = {}
    for sample in report["samples"]:
        metadata = indexed[sample["id"]]["metadata"]
        if any(sample.get(key) != metadata[key] for key in ("family", "ordinary_retention")):
            raise ValueError("Final scorer changed a fixed family classification")
        for key in ("protocol_valid", "prediction_generation_success", "output_truncated"):
            if type(sample.get(key)) is not bool:
                raise ValueError(f"Final stage requires explicitly scored Boolean {key}")
        key = "ordinary_correct" if sample["ordinary_retention"] else "behavior_success"
        if type(sample.get(key)) is not bool:
            raise ValueError(f"Final semantics are unscored for {sample['id']}")
        if sample["ordinary_retention"] and sample.get("ordinary_semantics_supported") is not True:
            raise ValueError("Ordinary final semantics require a supported independent validator")
        if sample[key] and (
            not sample["prediction_generation_success"]
            or sample["output_truncated"]
            or not sample["protocol_valid"]
        ):
            raise ValueError("Invalid or failed final inference cannot claim behavior success")
        if not re.fullmatch(r"[0-9a-f]{64}", sample.get("visible_prompt_sha256", "")):
            raise ValueError("Every final stage must pin its actual visible prompt")
        family = families.setdefault(
            sample["family"],
            {
                "ordinary_retention": sample["ordinary_retention"],
                "total": 0,
                "correct": 0,
            },
        )
        family["total"] += 1
        family["correct"] += sample[key]
    for family in families.values():
        family["rate"] = family["correct"] / family["total"]
    ordinary = [row for row in report["samples"] if row["ordinary_retention"]]
    tools = [row for row in report["samples"] if not row["ordinary_retention"]]
    return {
        "total": len(records),
        "ordinary_total": len(ordinary),
        "tool_total": len(tools),
        "ordinary_correct": sum(row["ordinary_correct"] for row in ordinary),
        "tool_correct": sum(row["behavior_success"] for row in tools),
        "families": families,
        "generation_failures": sum(
            not row["prediction_generation_success"] for row in report["samples"]
        ),
        "truncated_generations": sum(row["output_truncated"] for row in report["samples"]),
    }


def compare_final_reports(baseline: dict, candidate: dict) -> dict:
    """Report paired final changes; these results cannot choose a checkpoint."""
    for key in ("generation_config", "eval_sha256", "final_workflows_sha256"):
        if baseline.get(key) != candidate.get(key) or not baseline.get(key):
            raise ValueError(f"Paired final {key} differs or is missing")
    if (
        baseline["model_identity"]["base_weight_sha256"]
        != candidate["model_identity"]["base_weight_sha256"]
    ):
        raise ValueError("Paired final uses different original base weight identity")
    result = {"fresh_final_used_for_selection": False}
    for kind, keys in (
        ("stage", ("family", "ordinary_retention", "group", "visible_prompt_sha256")),
        ("workflow", ("group", "initial_visible_prompt_sha256")),
    ):
        left_rows, right_rows = (
            baseline[f"{kind}_scored"]["samples"],
            candidate[f"{kind}_scored"]["samples"],
        )
        if set(_unique_ids(left_rows, "paired baseline")) != set(
            _unique_ids(right_rows, "paired candidate")
        ):
            raise ValueError("Paired final complete IDs differ")
        left, right = ({row["id"]: row for row in rows} for rows in (left_rows, right_rows))
        for identifier in left:
            if any(left[identifier].get(key) != right[identifier].get(key) for key in keys):
                raise ValueError(
                    f"Paired final classification or visible input differs: {identifier}"
                )

        def correct(rows):
            return sum(
                row["ordinary_correct"]
                if row.get("ordinary_retention")
                else row["behavior_success"]
                for row in rows
            )

        result[kind] = {
            "total": len(left_rows),
            "baseline_correct": correct(left_rows),
            "candidate_correct": correct(right_rows),
        }
    return result


def source_closure(scorer, root: Path) -> list[Path]:
    from training.train_lora import behavioral_profile_sources

    declared = getattr(scorer, "SOURCE_DEPENDENCIES", ())
    required = {
        "for Android/training/daily_formats_v5.py",
        "for Android/training/controlled_http_v5.py",
    }
    if not isinstance(declared, (tuple, list)) or not declared or not required <= set(declared):
        raise ValueError("V5 scorer must declare its complete daily-format/HTTP source closure")
    files = behavioral_profile_sources(
        "v5_general", Path(__file__).with_name("train_lora.py"), declared
    )
    files.append(Path(__file__))
    if any(not path.resolve().is_relative_to(root) or not path.is_file() for path in files):
        raise ValueError("V5 source closure has missing or external repository files")
    return files


class ArchivedGenerator:
    """Bound inference to complete inputs and archive every call before returning."""

    def __init__(
        self, *, tokenizer, configuration: dict, output: Path, args, model=None, torch=None
    ):
        self.tokenizer, self.configuration, self.output = tokenizer, configuration, output
        self.args, self.model, self.torch = args, model, torch
        self.calls = []

    def __call__(self, prompt: str, identifier: str) -> dict:
        if (
            not isinstance(prompt, str)
            or not prompt
            or not isinstance(identifier, str)
            or not identifier
        ):
            raise ValueError("Inference accepts only visible prompt and identifier strings")
        folder = self.output / "generation-artifacts" / f"{len(self.calls) + 1:04d}"
        folder.mkdir(parents=True, exist_ok=False)
        prompt_path = folder / "prompt.txt"
        prompt_path.write_bytes(prompt.encode("utf-8"))
        prediction = {
            "id": identifier,
            "raw_output": "",
            "output_truncated": False,
            "prediction_generation_success": False,
            "generation_error": None,
            "prompt_path": str(prompt_path.resolve()),
            "prompt_sha256": sha256_file(prompt_path),
            "requested_context_tokens": self.configuration["context_tokens"],
            "effective_context_tokens": None,
        }
        started = time.monotonic()
        try:
            tokens = self.tokenizer(prompt, add_special_tokens=False, truncation=False)["input_ids"]
            count = len(tokens)
            prediction["input_tokens"] = count
            prediction["input_token_count_source"] = (
                "official tokenizer, complete prompt, no truncation"
            )
            prediction["context_audit"] = audit_context_budget(
                count,
                max_new_tokens=self.configuration["max_new_tokens"],
                context_tokens=self.configuration["context_tokens"],
                bos_margin=1 if self.args.gguf else 0,
            )
            if self.args.gguf:
                command = completion_command(
                    executable=self.args.completion_executable,
                    gguf=self.args.gguf,
                    prompt=prompt_path,
                    context_tokens=self.configuration["context_tokens"],
                    max_new_tokens=self.configuration["max_new_tokens"],
                    seed=self.configuration["seed"],
                    threads=self.args.threads,
                    gpu_layers=self.args.gpu_layers,
                )
                process = run_completion_bytes(command, folder, timeout=self.args.process_timeout)
                prediction["completion_command"] = command
                prediction["completion"] = process
                stdout_bytes = Path(process["stdout_path"]).read_bytes()
                prediction["raw_output"] = stdout_bytes.decode("utf-8", errors="replace")
                if process["error"]:
                    raise RuntimeError(process["error"])
                receipt = parse_completion_receipt(
                    process["stderr"],
                    requested_context=self.configuration["context_tokens"],
                    official_input_tokens=count,
                    max_new_tokens=self.configuration["max_new_tokens"],
                )
                prediction["backend_status_receipt"] = receipt
                if re.search(r"\bn_ctx(?:_per_seq)?\s*=", process["stderr"]):
                    effective_completion_context(
                        process["stderr"], requested=self.configuration["context_tokens"]
                    )
                prediction["effective_context_tokens"] = receipt["context_tokens"]
                prediction["backend_input_tokens"] = receipt["input_tokens"]
                prediction["output_tokens"] = receipt["generated_tokens"]
                prediction["token_counts_estimated"] = False
                prediction["output_truncated"] = not receipt["eog"]
                if not receipt["eog"]:
                    raise RuntimeError("Completion stopped without reliable assistant EOS evidence")
                raw, footer = strip_terminal_footer_bytes(stdout_bytes)
                prediction["completion_eog_footer"] = footer
                if not footer:
                    raise RuntimeError(
                        "Measured backend EOG lacks its pinned terminal stdout footer"
                    )
                prediction["raw_output"] = raw.decode("utf-8")
            else:
                from training.behavioral_dev_generation import continuation_is_truncated

                inputs = self.tokenizer(
                    prompt, add_special_tokens=False, truncation=False, return_tensors="pt"
                ).to(self.configuration["device"])
                if int(inputs["input_ids"].shape[-1]) != count:
                    raise ValueError("Tensor inference changed the complete audited prompt length")
                with self.torch.inference_mode():
                    generated = self.model.generate(
                        **inputs,
                        do_sample=False,
                        max_new_tokens=self.configuration["max_new_tokens"],
                        use_cache=True,
                        eos_token_id=self.configuration["eos_token_ids"],
                        pad_token_id=self.tokenizer.eos_token_id,
                    )
                generated_tokens = generated[0, count:]
                prediction["raw_output"] = self.tokenizer.decode(
                    generated_tokens, skip_special_tokens=False
                )
                prediction["output_tokens"] = int(generated_tokens.numel())
                prediction["output_truncated"] = continuation_is_truncated(
                    generated_tokens,
                    max_new_tokens=self.configuration["max_new_tokens"],
                    eos_ids=self.configuration["eos_token_ids"],
                )
                if prediction["output_tokens"] > self.configuration["max_new_tokens"]:
                    raise ValueError("HF inference exceeded the fixed output budget")
                ended = bool(
                    prediction["output_tokens"]
                    and int(generated_tokens[-1]) in self.configuration["eos_token_ids"]
                )
                prediction["assistant_eos_observed"] = ended
                if not ended and not prediction["output_truncated"]:
                    raise RuntimeError(
                        "HF inference stopped without reliable assistant EOS evidence"
                    )
                prediction["token_counts_estimated"] = False
                prediction["effective_context_tokens"] = self.configuration["context_tokens"]
            prediction["prediction_generation_success"] = True
        except Exception as failure:
            prediction["generation_error"] = f"{type(failure).__name__}: {failure}"
        prediction["elapsed_seconds"] = time.monotonic() - started
        write_report(folder / "generation.json", prediction)
        self.calls.append(copy.deepcopy(prediction))
        write_report(self.output / "generation-calls.json", {"calls": self.calls})
        # Scorers receive explicit failure status and must refuse tool execution.
        return prediction


def main() -> None:
    parser = argument_parser()
    args = parser.parse_args()
    if (
        args.context_tokens < 1
        or args.process_timeout < 1
        or args.threads < 1
        or args.gpu_layers < 0
    ):
        parser.error("Context, timeout, and thread budgets must be positive")
    if args.gguf and (
        args.adapter
        or not args.completion_executable
        or not args.completion_receipt_patch
        or not args.completion_build
    ):
        parser.error(
            "GGUF requires its completion executable, receipt patch evidence, and no HF adapter"
        )
    if not args.gguf and (
        args.completion_executable or args.completion_receipt_patch or args.completion_build
    ):
        parser.error("The completion executable is for GGUF inference only")
    root = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(root / "src"), str(root / "for Android")]
    from training.behavioral_plan import read_behavioral_plan
    from training.train_lora import verify_source_checkpoint

    plan, plan_sha = read_behavioral_plan(args.plan)
    stage_bytes, workflow_bytes, catalog_bytes = (
        path.read_bytes() for path in (args.eval, args.final_workflows, args.catalog)
    )
    stage, workflows, catalog = (
        read_records(stage_bytes),
        read_records(workflow_bytes),
        json.loads(catalog_bytes),
    )
    validate_final_records(plan, stage, workflows)
    manifest_bytes = args.final_manifest.read_bytes()
    manifest = validate_final_manifest(
        manifest_bytes,
        expected_sha256=args.final_manifest_sha256,
        plan=plan,
        eval_sha256=hashlib.sha256(stage_bytes).hexdigest(),
        final_workflows_sha256=hashlib.sha256(workflow_bytes).hexdigest(),
        catalog_sha256=hashlib.sha256(catalog_bytes).hexdigest(),
    )
    if hashlib.sha256(catalog_bytes).hexdigest() != plan["catalog_sha256"]:
        raise ValueError("Final catalog differs from the frozen training plan")
    if (
        hashlib.sha256(stage_bytes).hexdigest() == plan["dev_sha256"]
        or hashlib.sha256(workflow_bytes).hexdigest() == plan["dev_workflows_sha256"]
    ):
        raise ValueError("Final inputs cannot reuse checkpoint-selection dev datasets")
    source_identity = verify_source_checkpoint(args.model)
    scorer = importlib.import_module("training.evaluate_replay_v5")
    sources = source_closure(scorer, root)
    completion_patch = None
    completion_build = None
    build_files = []
    if args.gguf:
        completion_patch, backend_sources = validate_completion_patch(args.completion_receipt_patch)
        sources.extend(backend_sources)
        completion_build, build_files = validate_completion_build(
            args.completion_build, args.completion_executable, completion_patch
        )
    tokenizer_names = (
        "tokenizer.json",
        "tokenizer_config.json",
        "chat_template.jinja",
        "vocab.json",
        "merges.txt",
        "added_tokens.json",
        "special_tokens_map.json",
        "config.json",
        "model.safetensors.index.json",
    )
    tokenizer_files = [
        args.model / name for name in tokenizer_names if (args.model / name).is_file()
    ]
    if not {"tokenizer.json", "tokenizer_config.json", "chat_template.jinja", "config.json"} <= {
        path.name for path in tokenizer_files
    }:
        raise ValueError("Final inference requires the complete official tokenizer/template/config")
    input_files = [
        args.plan,
        args.final_manifest,
        args.eval,
        args.final_workflows,
        args.catalog,
        root / "uv.lock",
        Path(sys.executable),
        Path(__file__).with_name("requirements-local.txt"),
        *tokenizer_files,
    ]
    input_files.extend(args.model / name for name in source_identity)
    if args.adapter:
        for name in ("adapter_config.json", "adapter_model.safetensors"):
            input_files.append(args.adapter / name)
        for name in tokenizer_names:
            supplied = args.adapter / name
            if supplied.is_file() and sha256_file(supplied) != sha256_file(args.model / name):
                raise ValueError("Adapter tokenizer/config changed the official inference inputs")
    if args.gguf:
        input_files.extend(
            [
                args.gguf,
                args.completion_executable,
                args.completion_receipt_patch,
                args.completion_build,
                *build_files,
            ]
        )
        input_files.extend(args.completion_executable.parent.glob("*.dll"))
    paired = None
    if args.paired_with:
        paired = json.loads(args.paired_with.read_bytes())
        if (
            paired.get("complete") is not True
            or paired.get("fresh_final_used_for_selection") is not False
        ):
            raise ValueError("Paired final baseline must be a completed independent final report")
        input_files.append(args.paired_with)
    pinned = [
        {"source": str(path.resolve()), "sha256": sha256_file(path)}
        for path in dict.fromkeys(input_files)
    ]
    reserve_output(args.output)
    snapshots = snapshot_sources(sources, args.output / "source-snapshots")
    report = {
        "schema_version": 1,
        "profile": "v5_general",
        "complete": False,
        "fresh_final_used_for_selection": False,
        "expected_answers_given_to_model": False,
        "private_user_data_used": False,
        "fixed_plan_sha256": plan_sha,
        "frozen_final_manifest_sha256": args.final_manifest_sha256,
        "original_candidate_manifest_status": manifest.get("status"),
        "manifest_approved_by_sha256_after_independent_freeze_review": True,
        "eval_sha256": hashlib.sha256(stage_bytes).hexdigest(),
        "final_workflows_sha256": hashlib.sha256(workflow_bytes).hexdigest(),
        "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
        "source_snapshots": snapshots,
        "pinned_files": pinned,
        "expected_stage_cases": 200,
        "expected_workflow_cases": 20,
    }
    report_path = args.output / "evaluation-report.json"
    write_report(report_path, report)
    try:
        from transformers import AutoTokenizer

        from training.autonomous_dev_generation import generate_and_score_final_workflows
        from training.behavioral_dev_generation import runtime_turn_eos_ids
        from training.behavioral_dev_selection import validate_final_autonomous_report
        from training.evaluate_tools import build_evaluation_prompt, load_evaluation_model

        tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
        configuration = {
            "backend": "gguf_completion" if args.gguf else "huggingface",
            "decoding": plan["generation"]["decoding"],
            "max_new_tokens": plan["generation"]["max_new_tokens"],
            "max_turns": plan["generation"]["max_turns"],
            "eos_tokens": plan["generation"]["eos_tokens"],
            "eos_token_ids": runtime_turn_eos_ids(tokenizer),
            "pad_token_id": tokenizer.eos_token_id,
            "context_tokens": args.context_tokens,
            "seed": plan["training_seed"],
            "prompt_source": "runtime",
            "fixed_plan_sha256": plan_sha,
            "frozen_final_manifest_sha256": args.final_manifest_sha256,
            "environment": backend_environment(root),
            "catalog_sha256": report["catalog_sha256"],
            "tokenizer_sha256": {path.name: sha256_file(path) for path in tokenizer_files},
            "source_sha256": {
                str(Path(row["source"]).relative_to(root)): row["sha256"] for row in snapshots
            },
            "context_shift": False,
            "automatic_memory_fitting": False,
        }
        model, torch_module = None, None
        if args.gguf:
            configuration.update(
                dtype="GGUF",
                device="completion",
                threads=args.threads,
                gpu_layers=args.gpu_layers,
                process_timeout=args.process_timeout,
                backend_executable_sha256=sha256_file(args.completion_executable),
                backend_receipt_patch_sha256=sha256_file(args.completion_receipt_patch),
                backend_receipt_patch=completion_patch,
                backend_build_sha256=sha256_file(args.completion_build),
                backend_build=completion_build,
                backend_dll_sha256={
                    path.name: sha256_file(path)
                    for path in args.completion_executable.parent.glob("*.dll")
                },
                input_token_bos_margin=1,
            )
        else:
            import torch

            torch_module = torch
            model, restored = load_evaluation_model(
                args.model,
                dtype=torch.bfloat16,
                device=plan["generation"]["device"],
                adapter=args.adapter,
            )
            # This text-only evaluation keeps the unchanged vision tower on CPU.
            base_model = model.get_base_model() if args.adapter else model
            base_model.model.visual.to("cpu")
            base_model.config.text_config.use_cache = True
            configuration.update(
                dtype=plan["generation"]["dtype"],
                device=plan["generation"]["device"],
                source_fp32_restored=restored,
                input_token_bos_margin=0,
            )
        model_identity = {
            "base_weight_sha256": source_identity,
            "generation_source": "model_free_generation",
            "adapter_sha256": sha256_file(args.adapter / "adapter_model.safetensors")
            if args.adapter
            else None,
            "gguf_sha256": sha256_file(args.gguf) if args.gguf else None,
        }
        report.update(generation_config=configuration, model_identity=model_identity)
        if paired and paired.get("generation_config") != configuration:
            raise ValueError("Paired final configuration differs before inference")
        verify_pinned_files([*pinned, *snapshots])
        write_report(report_path, report)
        generator = ArchivedGenerator(
            tokenizer=tokenizer,
            configuration=configuration,
            output=args.output,
            args=args,
            model=model,
            torch=torch_module,
        )

        def persist(path, raw):
            write_report(args.output / path, raw)
            sample = raw["samples"][-1]
            print(
                json.dumps(
                    {
                        "event": "final_case",
                        "report": path,
                        "completed": len(raw["samples"]),
                        "id": sample["id"],
                        "generation_success": sample["prediction_generation_success"],
                    }
                ),
                flush=True,
            )

        stage_scored, _stage_raw = generate_and_score_final_stages(
            stage,
            dataset_sha256=report["eval_sha256"],
            generation_config=configuration,
            model_identity=model_identity,
            build_visible_prompt=lambda visible: build_evaluation_prompt(
                visible, prompt_source="runtime"
            )[1],
            generate_visible=generator,
            score_report=scorer.score_report,
            catalog=catalog,
            on_prediction=lambda raw: persist("final-stage-raw.json", raw),
        )
        write_report(args.output / "final-stage-scored.json", stage_scored)
        report["stage_scored"] = stage_scored
        report["stage_summary"] = validate_final_stage_report(stage_scored, stage)
        write_report(report_path, report)
        workflow_scored = generate_and_score_final_workflows(
            workflows,
            dataset_sha256=report["final_workflows_sha256"],
            generation_config=configuration,
            model_identity=model_identity,
            generate_visible=generator,
            evaluate_workflow_report=scorer.evaluate_workflow_report,
            catalog=catalog,
            max_turns=configuration["max_turns"],
            on_prediction=lambda raw: persist("final-workflow-raw.json", raw),
        )
        write_report(args.output / "final-workflow-scored.json", workflow_scored)
        report["workflow_scored"] = workflow_scored
        report["workflow_summary"] = validate_final_autonomous_report(workflow_scored)
        if paired:
            report["paired_final"] = compare_final_reports(paired, report)
        verify_pinned_files([*pinned, *snapshots])
        report["generation_calls"] = len(generator.calls)
        report["raw_report_sha256"] = {
            path.name: sha256_file(path)
            for path in (
                args.output / "final-stage-raw.json",
                args.output / "final-workflow-raw.json",
                args.output / "generation-calls.json",
            )
        }
        report["complete"] = True
        write_report(report_path, report)
    except Exception as failure:
        report["evaluation_error"] = f"{type(failure).__name__}: {failure}"
        write_report(report_path, report)
        raise


if __name__ == "__main__":
    main()
