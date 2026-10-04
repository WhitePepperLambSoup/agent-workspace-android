"""CPU controls for the strict independent V5 evaluation CLI."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ANDROID = Path(__file__).resolve().parents[2]
for source in (ANDROID, ANDROID.parent / "src"):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))


def helper():
    path = ANDROID / "training/evaluate_general_v5.py"
    assert path.is_file(), "Independent V5 model evaluation must have its own strict CLI"
    return importlib.import_module("training.evaluate_general_v5")


def fixed_plan():
    spec = importlib.util.spec_from_file_location(
        "v5_evaluation_test_plan", ANDROID / "training/tests/test_behavioral_plan.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.plan()


def rows():
    return [
        {
            "id": f"final-{family}-{index}",
            "split": "eval",
            "messages": [{"role": "user", "content": f"visible {family} {index}"}],
            "tools": [],
            "metadata": {
                "family": family,
                "split": "eval",
                "ordinary_retention": ordinary,
                "hidden": "PRIVATE_METADATA_CANARY",
            },
            "expected": "PRIVATE_LABEL_CANARY",
            "target_response": "PRIVATE_SUPERVISION_CANARY",
        }
        for ordinary, prefix, count, each in ((True, "ordinary", 8, 10), (False, "tool", 60, 2))
        for family in (f"{prefix}-{number}" for number in range(count))
        for index in range(each)
    ]


def workflows():
    return [
        {"id": f"final-{group}-{number}", "split": "final", "group": group}
        for group, count in (("file", 10), ("format", 6), ("search", 4))
        for number in range(count)
    ]


def configuration():
    return {"decoding": "greedy", "max_new_tokens": 4, "max_turns": 10, "context_tokens": 100}


def identity():
    return {
        "generation_source": "model_free_generation",
        "base_weight_sha256": {"weights": "b" * 64},
    }


def test_cli_requires_an_explicit_context_and_has_no_subset_switches():
    parser = helper().argument_parser()
    required = [
        "--model",
        "source",
        "--eval",
        "eval.jsonl",
        "--final-workflows",
        "final.jsonl",
        "--catalog",
        "catalog.json",
        "--plan",
        "plan.json",
        "--final-manifest",
        "manifest.json",
        "--final-manifest-sha256",
        "a" * 64,
        "--output",
        "new-output",
    ]
    with pytest.raises(SystemExit):
        parser.parse_args(required)
    args = parser.parse_args([*required, "--context-tokens", "9000"])
    assert args.context_tokens == 9000
    for flag in ("--limit", "--start-index", "--max-new-tokens"):
        with pytest.raises(SystemExit):
            parser.parse_args([*required, "--context-tokens", "9000", flag, "1"])


def test_input_validation_preserves_complete_final_counts_and_original_splits():
    validate = helper().validate_final_records
    stage, final = rows(), workflows()
    validate(fixed_plan(), stage, final)
    assert {row["split"] for row in stage} == {"eval"}
    for mutation in ("partial", "dev", "duplicate", "changed_family", "group"):
        bad_stage, bad_final = copy.deepcopy(stage), copy.deepcopy(final)
        if mutation == "partial":
            bad_stage.pop()
        elif mutation == "dev":
            bad_stage[0]["split"] = "dev"
        elif mutation == "duplicate":
            bad_final[0]["id"] = bad_final[1]["id"]
        elif mutation == "changed_family":
            bad_stage[0]["metadata"]["family"] = "tool-0"
        else:
            bad_final[0]["group"] = "search"
        with pytest.raises(ValueError):
            validate(fixed_plan(), bad_stage, bad_final)


def test_context_audit_allows_exact_boundary_and_refuses_one_token_over():
    audit = helper().audit_context_budget
    assert audit(96, max_new_tokens=4, context_tokens=100, bos_margin=0)["fits"] is True
    assert audit(95, max_new_tokens=4, context_tokens=100, bos_margin=1)["fits"] is True
    with pytest.raises(ValueError, match="context"):
        audit(96, max_new_tokens=4, context_tokens=100, bos_margin=1)
    for invalid in (True, 0, -1, 1.5):
        with pytest.raises(ValueError):
            audit(1, max_new_tokens=4, context_tokens=invalid, bos_margin=0)


@pytest.mark.parametrize("ending", [b"\n", b"\n\n", b"\n\n\n", b"\r\n", b"\r\n\r\n\r\n"])
def test_completion_footer_removal_preserves_payload_bytes_and_prior_footer(ending):
    strip = helper().strip_terminal_footer_bytes
    payload = b"<parameter=content>\r\nA\r\n\r\n</parameter> [end of text]\n"
    assert strip(payload + b" [end of text]" + ending) == (payload, True)
    assert strip(payload + b"actual suffix") == (payload + b"actual suffix", False)


@pytest.mark.parametrize("failure", [None, "timeout", "exit"])
def test_completion_process_persists_exact_streams_for_success_and_failures(
    tmp_path, monkeypatch, failure
):
    module = helper()
    raw = "内容\r\n\r\n".encode() + b" [end of text]\r\n"

    def process(command, *, stdin, stdout, stderr, timeout, check):
        assert stdin == subprocess.DEVNULL and timeout == 3 and check is True
        stdout.write(raw)
        stderr.write(b"n_ctx = 100\r\nn_ctx_per_seq = 100\r\n")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, timeout)
        if failure == "exit":
            raise subprocess.CalledProcessError(7, command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(module.subprocess, "run", process)
    result = module.run_completion_bytes(["completion"], tmp_path, timeout=3)
    assert (tmp_path / "stdout.bin").read_bytes() == raw
    assert result["stdout"] == raw.decode()
    assert result["stdout_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["returncode"] == (None if failure == "timeout" else 7 if failure == "exit" else 0)
    assert result["timed_out"] is (failure == "timeout")


def test_effective_backend_context_requires_unambiguous_matching_evidence():
    parse = helper().effective_completion_context
    assert parse("n_ctx = 128\nn_ctx_per_seq = 128\n", requested=128) == 128
    for invalid in (
        "no context evidence",
        "n_ctx = 128\nn_ctx_per_seq = 64\n",
        "n_ctx = 64\n",
        "n_ctx_per_seq = 128\nn_ctx_per_seq = 64\n",
    ):
        with pytest.raises(ValueError, match="context"):
            parse(invalid, requested=128)


def receipt(**kwargs):
    return {
        "schema_version": 1,
        "input_tokens": 15,
        "context_tokens": 20,
        "generated_tokens": 4,
        "eog": True,
        "input_truncated": False,
        "context_shifted": False,
        "context_full": False,
        **kwargs,
    }


def test_completion_receipt_uses_actual_token_eog_and_refuses_marker_spoofs():
    parse = helper().parse_completion_receipt
    valid = "AGENT_EVALUATION_STATUS " + json.dumps(receipt()) + "\r\n"
    args = dict(requested_context=20, official_input_tokens=15, max_new_tokens=4)
    result = parse(valid, **args)
    assert result["eog"] is True and result["generated_tokens"] == 4
    assert (
        parse(valid.replace('"input_tokens": 15', '"input_tokens": 16'), **args)["input_tokens"]
        == 16
    )
    for changed in (
        receipt(context_tokens=19),
        receipt(input_tokens=14),
        receipt(input_tokens=17),
        receipt(generated_tokens=5),
        receipt(input_truncated=True),
        receipt(context_shifted=True),
        receipt(context_full=True),
        receipt(generated_tokens=True),
        receipt(extra=True),
    ):
        with pytest.raises(ValueError):
            parse("AGENT_EVALUATION_STATUS " + json.dumps(changed) + "\n", **args)
    for bad in (
        "found an EOG token\n",
        " [end of text]\n",
        valid + valid,
        'prompt: "AGENT_EVALUATION_STATUS ' + json.dumps(receipt()) + '"\n',
    ):
        with pytest.raises(ValueError):
            parse(bad, **args)
    assert (
        parse("AGENT_EVALUATION_STATUS " + json.dumps(receipt(eog=False)) + "\n", **args)["eog"]
        is False
    )


def test_gguf_command_pins_full_prompt_context_and_disables_fitting_and_shift():
    cmd = helper().completion_command(
        executable=Path("completion.exe"),
        gguf=Path("model.gguf"),
        prompt=Path("prompt.txt"),
        context_tokens=12345,
        max_new_tokens=1001,
        seed=20261001,
        threads=2,
        gpu_layers=0,
    )
    assert cmd[cmd.index("-c") + 1] == "12345"
    assert cmd[cmd.index("-n") + 1] == "1001"
    assert cmd[cmd.index("--fit") + 1] == "off" and "--no-context-shift" in cmd
    assert cmd[cmd.index("--temp") + 1] == "0"


def test_final_generation_receives_visible_messages_only_and_retains_all_failure_rows():
    module = helper()
    stage = rows()
    seen, saved = [], []

    def prompt(row):
        assert set(row) == {"messages", "tools"}
        return row["messages"][0]["content"]

    def generate(prompt, identifier):
        seen.append(prompt)
        assert "PRIVATE" not in prompt
        if identifier == stage[0]["id"]:
            raise RuntimeError("synthetic retained failure")
        return {
            "raw_output": "A\r\n\r\n<|im_end|>",
            "output_truncated": identifier == stage[1]["id"],
        }

    def scorer(data, raw, catalog):
        assert data is stage and catalog == {}
        return {
            "split": "eval",
            "samples": [
                {
                    "id": row["id"],
                    "family": row["metadata"]["family"],
                    "ordinary_retention": row["metadata"]["ordinary_retention"],
                    "ordinary_correct": False,
                    "ordinary_semantics_supported": True,
                    "behavior_success": False,
                    "protocol_valid": True,
                }
                for row in data
            ],
        }

    scored, raw = module.generate_and_score_final_stages(
        stage,
        dataset_sha256="a" * 64,
        generation_config=configuration(),
        model_identity=identity(),
        build_visible_prompt=prompt,
        generate_visible=generate,
        score_report=scorer,
        catalog={},
        on_prediction=lambda report: saved.append(copy.deepcopy(report)),
    )
    assert len(seen) == len(saved) == len(raw["samples"]) == len(scored["samples"]) == 200
    assert raw["samples"][0]["prediction_generation_success"] is False
    assert raw["samples"][1]["output_truncated"] is True
    assert raw["samples"][2]["raw_output"] == "A\r\n\r\n<|im_end|>"
    assert scored["split"] == "eval"
    assert scored["fresh_final_used_for_selection"] is False


def test_final_stage_scorer_cannot_drop_failures_or_claim_success_after_a_failed_call():
    module = helper()
    stage = rows()
    for mutation in ("drop", "success", "split"):

        def bad(data, raw, catalog, mutation=mutation):
            result = {
                "split": "dev" if mutation == "split" else "eval",
                "samples": [
                    {
                        "id": row["id"],
                        "behavior_success": mutation == "success",
                        "ordinary_correct": mutation == "success",
                    }
                    for row in data
                ],
            }
            if mutation == "drop":
                result["samples"].pop()
            return result

        with pytest.raises(ValueError):
            module.generate_and_score_final_stages(
                stage,
                dataset_sha256="a" * 64,
                generation_config=configuration(),
                model_identity=identity(),
                build_visible_prompt=lambda row: row["messages"][0]["content"],
                generate_visible=lambda prompt, identifier: (_ for _ in ()).throw(
                    RuntimeError("failed")
                ),
                score_report=bad,
                catalog={},
            )


def test_output_reservation_refuses_an_existing_directory_or_preexisting_file(tmp_path):
    reserve = helper().reserve_output
    chosen = tmp_path / "new"
    reserve(chosen)
    with pytest.raises(FileExistsError):
        reserve(chosen)
    other = tmp_path / "file"
    other.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError):
        reserve(other)


def test_source_closure_is_hashed_and_snapshot_change_is_rejected(tmp_path):
    module = helper()
    source = tmp_path / "source.py"
    source.write_bytes(b"original\r\n")
    snapshots = module.snapshot_sources([source], tmp_path / "snapshots")
    assert snapshots[0]["sha256"] == hashlib.sha256(b"original\r\n").hexdigest()
    module.verify_pinned_files(snapshots)
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        module.verify_pinned_files(snapshots)


def test_paired_final_rejects_changed_config_or_dataset_and_keeps_failed_denominator():
    module = helper()
    base = {
        "generation_config": configuration(),
        "eval_sha256": "e" * 64,
        "final_workflows_sha256": "f" * 64,
        "model_identity": identity(),
        "stage_scored": {
            "samples": [
                {
                    "id": "a",
                    "family": "tool",
                    "ordinary_retention": False,
                    "group": "read",
                    "visible_prompt_sha256": "a" * 64,
                    "behavior_success": False,
                },
            ],
        },
        "workflow_scored": {"samples": []},
    }
    candidate = copy.deepcopy(base)
    candidate["stage_scored"]["samples"][0]["behavior_success"] = True
    assert module.compare_final_reports(base, candidate)["stage"]["candidate_correct"] == 1
    for key in ("generation_config", "eval_sha256", "final_workflows_sha256"):
        changed = copy.deepcopy(candidate)
        changed[key] = {} if key == "generation_config" else "a" * 64
        with pytest.raises(ValueError, match=r"paired|Paired"):
            module.compare_final_reports(base, changed)


def test_frozen_manifest_pins_final_bytes_and_links_the_original_training_inputs():
    module = helper()
    plan = fixed_plan()
    manifest = {
        "status": "unfrozen_candidate_pending_independent_review",
        "dataset_hashes": {
            "train.jsonl": plan["train_sha256"],
            "dev.jsonl": plan["dev_sha256"],
            "dev-workflows.jsonl": plan["dev_workflows_sha256"],
            "catalog.json": plan["catalog_sha256"],
            "eval.jsonl": "f" * 64,
            "final-workflows.jsonl": "e" * 64,
        },
    }
    raw = json.dumps(manifest).encode()
    args = dict(
        expected_sha256=hashlib.sha256(raw).hexdigest(),
        plan=plan,
        eval_sha256="f" * 64,
        final_workflows_sha256="e" * 64,
        catalog_sha256=plan["catalog_sha256"],
    )
    assert module.validate_final_manifest(raw, **args)["status"] == manifest["status"]
    for key in ("expected_sha256", "eval_sha256", "final_workflows_sha256", "catalog_sha256"):
        changed = {**args, key: "0" * 64}
        with pytest.raises(ValueError):
            module.validate_final_manifest(raw, **changed)
    changed_manifest = copy.deepcopy(manifest)
    changed_manifest["dataset_hashes"]["dev.jsonl"] = "0" * 64
    changed_raw = json.dumps(changed_manifest).encode()
    with pytest.raises(ValueError, match="training"):
        module.validate_final_manifest(
            changed_raw, **{**args, "expected_sha256": hashlib.sha256(changed_raw).hexdigest()}
        )


def test_actual_environment_records_backend_versions_and_lock_bytes(tmp_path, monkeypatch):
    module = helper()
    (tmp_path / "uv.lock").write_bytes(b"locked environment\r\n")

    class Distribution:
        version = "1.2.3-test"

        def read_text(self, name):
            return name + " package metadata"

    monkeypatch.setattr(module.importlib.metadata, "distribution", lambda name: Distribution())
    evidence = module.backend_environment(tmp_path)
    assert evidence["versions"]["torch"] == "1.2.3-test"
    assert evidence["uv_lock_sha256"] == hashlib.sha256(b"locked environment\r\n").hexdigest()
    assert evidence["distribution_metadata_sha256"]["transformers"]["RECORD"]
    assert evidence["python_executable_sha256"] == module.sha256_file(Path(sys.executable))


def test_completion_patch_provenance_pins_actual_source_and_helper(tmp_path):
    module = helper()
    patch = importlib.import_module("training.patch_completion_receipt")
    source = tmp_path / "native-source"
    cpp = source / "tools/completion/completion.cpp"
    cpp.parent.mkdir(parents=True)
    cpp.write_bytes(b"actual patched native backend\n")
    evidence = {
        "archive_sha256": patch.ARCHIVE_SHA256,
        "patch_helper_sha256": module.sha256_file(Path(patch.__file__)),
        "patched_source_sha256": module.sha256_file(cpp),
        "source": str(source),
        "android_jni_modified": False,
        "model_weights_modified": False,
    }
    report = tmp_path / "patch.json"
    report.write_text(json.dumps(evidence), encoding="utf-8")
    verified, files = module.validate_completion_patch(report)
    assert verified == evidence and files == [Path(patch.__file__), cpp]
    cpp.write_bytes(b"different source")
    with pytest.raises(ValueError, match="source"):
        module.validate_completion_patch(report)


def test_actual_completion_build_is_linked_to_receipt_source_and_binary_hash(tmp_path):
    module = helper()
    executable = tmp_path / "build/bin/completion.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"actual executable")
    cache = executable.parent.parent / "CMakeCache.txt"
    cache.write_bytes(b"actual build flags")
    patch = {"patched_source_sha256": "c" * 64}
    evidence = {
        "build_passed": True,
        "completion_executable": str(executable),
        "completion_sha256": module.sha256_file(executable),
        "build_cache_sha256": module.sha256_file(cache),
        "source_patch": patch,
        "gpu_used": False,
        "android_engine_modified": False,
    }
    path = tmp_path / "backend-build.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")
    verified, files = module.validate_completion_build(path, executable, patch)
    assert verified == evidence and files == [cache]
    executable.write_bytes(b"different binary")
    with pytest.raises(ValueError, match="binary"):
        module.validate_completion_build(path, executable, patch)


class ToyTokenizer:
    eos_token_id = 99

    def __call__(self, text, *, add_special_tokens, truncation, return_tensors=None):
        assert add_special_tokens is False and truncation is False
        tokens = list(range(len(text)))
        if return_tensors:
            import torch

            class Batch(dict):
                def to(self, device):
                    assert device == "cpu"
                    return self

            return Batch(input_ids=torch.tensor([tokens]))
        return {"input_ids": tokens}

    def decode(self, tokens, *, skip_special_tokens):
        assert skip_special_tokens is False
        return "ABCD<|im_end|>" if int(tokens[-1]) == 99 else "ABCD"


def generator_configuration():
    return {
        **configuration(),
        "context_tokens": 20,
        "device": "cpu",
        "seed": 20261001,
        "eos_token_ids": [99, 98],
    }


def generator_arguments(gguf=False):
    return SimpleNamespace(
        gguf=Path("model.gguf") if gguf else None,
        completion_executable=Path("completion.exe"),
        threads=2,
        gpu_layers=0,
        process_timeout=3,
    )


@pytest.mark.parametrize("ended", [True, False])
def test_hf_archived_generator_uses_explicit_eos_and_keeps_cap_eos_complete(tmp_path, ended):
    import torch

    module = helper()
    received = []

    class Model:
        def generate(self, **kwargs):
            received.append(kwargs)
            tokens = [1, 2, 3, 99] if ended else [1, 2]
            return torch.tensor([[*kwargs["input_ids"][0].tolist(), *tokens]])

    output = tmp_path / "hf"
    module.reserve_output(output)
    generator = module.ArchivedGenerator(
        tokenizer=ToyTokenizer(),
        configuration=generator_configuration(),
        output=output,
        args=generator_arguments(),
        model=Model(),
        torch=torch,
    )
    result = generator("P" * 16, "case")
    assert received[0]["eos_token_id"] == [99, 98] and received[0]["max_new_tokens"] == 4
    assert result["prediction_generation_success"] is ended
    assert result["output_truncated"] is False
    assert (output / "generation-artifacts/0001/prompt.txt").read_bytes() == b"P" * 16
    assert len(json.loads((output / "generation-calls.json").read_bytes())["calls"]) == 1


@pytest.mark.parametrize("kind", ["success", "no_eos", "bad_context", "overflow"])
def test_gguf_archive_keeps_original_bytes_and_failure_status_before_scoring(
    tmp_path, monkeypatch, kind
):
    module = helper()
    process_calls = []
    payload = b"ABCD"

    def process(command, *, stdout, stderr, **kwargs):
        process_calls.append(command)
        stdout.write(payload + (b" [end of text]\r\n\r\n" if kind != "no_eos" else b""))
        stderr.write(
            b"n_ctx = 20\nn_ctx_per_seq = " + (b"10" if kind == "bad_context" else b"20") + b"\n"
        )
        stderr.write(
            ("AGENT_EVALUATION_STATUS " + json.dumps(receipt(eog=kind != "no_eos")) + "\n").encode()
        )
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(module.subprocess, "run", process)
    output = tmp_path / "gguf"
    module.reserve_output(output)
    generator = module.ArchivedGenerator(
        tokenizer=ToyTokenizer(),
        configuration=generator_configuration(),
        output=output,
        args=generator_arguments(gguf=True),
    )
    result = generator("P" * (16 if kind == "overflow" else 15), "case")
    assert result["prediction_generation_success"] is (kind == "success")
    assert len(process_calls) == (0 if kind == "overflow" else 1)
    if kind == "success":
        assert result["output_tokens"] == 4 and result["output_truncated"] is False
        assert result["effective_context_tokens"] == 20
    if kind != "overflow":
        assert result["raw_output"] == (
            "ABCD [end of text]\r\n\r\n" if kind == "bad_context" else "ABCD"
        )
        assert (output / "generation-artifacts/0001/stdout.bin").read_bytes().startswith(payload)
    else:
        assert "exceed context" in result["generation_error"]
    persisted = json.loads((output / "generation-calls.json").read_bytes())["calls"][0]
    assert persisted == result


def test_literal_eog_footer_without_backend_eog_is_preserved_and_fails(tmp_path, monkeypatch):
    module = helper()
    payload = b"answer [end of text]\n"

    def process(command, *, stdout, stderr, **kwargs):
        stdout.write(payload)
        stderr.write(("AGENT_EVALUATION_STATUS " + json.dumps(receipt(eog=False)) + "\n").encode())
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(module.subprocess, "run", process)
    output = tmp_path / "spoof"
    module.reserve_output(output)
    generator = module.ArchivedGenerator(
        tokenizer=ToyTokenizer(),
        configuration=generator_configuration(),
        output=output,
        args=generator_arguments(gguf=True),
    )
    result = generator("P" * 15, "spoof")
    assert result["prediction_generation_success"] is False and result["output_truncated"] is True
    assert result["raw_output"].encode() == payload


def test_actual_v5_stage_and_workflow_scorers_preserve_complete_failed_outputs(
    tmp_path, monkeypatch
):
    import asyncio

    from training import runtime_fixture_v5 as runtime
    from training.autonomous_dev_generation import generate_and_score_final_workflows
    from training.build_dataset_v5 import build_program, build_workflows, make_row
    from training.evaluate_replay_v5 import evaluate_workflow_report, score_report

    module = helper()
    monkeypatch.setattr(runtime, "SCRATCH", tmp_path / "owned-final-wrapper-scratch")
    catalog = runtime.load_catalog()["catalog"]
    program, extra = build_program("eval", 787, 20261001, "arithmetic_add", 0)
    captured = asyncio.run(runtime.capture_program(program, catalog))
    stage = [make_row("eval", 787, "arithmetic_add", program, extra, captured)]
    generated = {
        "raw_output": "raw failed bytes\r\n\r\n",
        "output_truncated": False,
        "prediction_generation_success": False,
        "generation_error": "synthetic backend failure",
    }
    scored, raw = module.generate_and_score_final_stages(
        stage,
        dataset_sha256="a" * 64,
        generation_config=configuration(),
        model_identity=identity(),
        build_visible_prompt=lambda visible: importlib.import_module(
            "training.evaluate_tools"
        ).build_evaluation_prompt(visible)[1],
        generate_visible=lambda prompt, identifier: copy.deepcopy(generated),
        score_report=score_report,
        catalog=catalog,
    )
    assert raw["samples"][0]["raw_output"] == generated["raw_output"]
    assert module.validate_final_stage_report(scored, stage)["generation_failures"] == 1
    calls = []

    def generate(prompt, identifier):
        assert "goal_files" not in prompt and "gold_history" not in prompt
        calls.append((prompt, identifier))
        return copy.deepcopy(generated)

    final = generate_and_score_final_workflows(
        build_workflows("final", 20261001),
        dataset_sha256="f" * 64,
        generation_config=configuration(),
        model_identity=identity(),
        generate_visible=generate,
        evaluate_workflow_report=evaluate_workflow_report,
        catalog=catalog,
        max_turns=10,
    )
    assert len(calls) == len(final["samples"]) == 20
    assert final["split"] == "final"
    assert all(row["behavior_success"] is False for row in final["samples"])
    assert all(row["prediction_generation_success"] is False for row in final["samples"])
    assert all(
        row["turns"][0]["generation"]["raw_output"] == generated["raw_output"]
        for row in final["samples"]
    )
    assert not list((tmp_path / "owned-final-wrapper-scratch").iterdir())
