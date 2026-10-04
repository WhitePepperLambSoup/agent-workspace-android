"""Compare raw base/LoRA tool generations against independent synthetic tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_workspace.core.models import ProviderRequest


def strip_completion_footer(stdout: str) -> tuple[str, bool]:
    """Remove at most one pinned CLI status footer, preserving generated text.

    subprocess text mode normalizes the CLI's line endings. The footer and final
    blank lines are output by the CLI, whereas earlier identical text belongs to
    the model and must remain available to the atomic protocol parser.
    """
    for footer in (" [end of text]\n\n\n", " [end of text]\n\n", " [end of text]\n"):
        if stdout.endswith(footer):
            return stdout[: -len(footer)], True
    return stdout, False


def build_evaluation_prompt(
    record: dict[str, Any], *, prompt_source: str = "runtime", tokenizer: Any = None
) -> tuple[ProviderRequest, str]:
    """Build the shared evaluation input from visible messages and tools only."""
    from android_adapter.local_provider import build_qwen_prompt

    from agent_workspace.core.models import ChatMessage, ProviderRequest, Role, ToolCall, ToolSpec

    specs = tuple(
        ToolSpec(
            name=tool["function"]["name"],
            description=tool["function"].get("description", ""),
            input_schema=tool["function"]["parameters"],
            side_effect="read",
        )
        for tool in record.get("tools", [])
    )
    messages = []
    for message in record["messages"]:
        calls = []
        for call in message.get("tool_calls", []):
            function = call.get("function", call)
            arguments = function["arguments"]
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            calls.append(ToolCall(call.get("id", "history"), function["name"], arguments))
        messages.append(
            ChatMessage(
                role=Role(message["role"]),
                content=message.get("content", ""),
                tool_calls=tuple(calls),
                tool_call_id=message.get("tool_call_id"),
            )
        )
    request = ProviderRequest("qwen3.5-0.8b-q4-k-m", tuple(messages), tools=specs)
    if prompt_source == "runtime":
        prompt = build_qwen_prompt(request)
    elif prompt_source == "official" and tokenizer is not None:
        prompt = tokenizer.apply_chat_template(
            record["messages"],
            tools=record.get("tools") or None,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    else:
        raise ValueError("Choose runtime prompts or provide the official tokenizer")
    return request, prompt


def _write_report(path: Path, report: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_completion_process(command: list[str], folder: Path, timeout: int = 240) -> dict:
    """Keep CLI diagnostics and count bounded process failures as failed predictions."""
    stdout_file, stderr_file = folder / "stdout.txt", folder / "stderr.txt"
    error, timed_out, returncode = None, False, None
    with stdout_file.open("wb") as output, stderr_file.open("wb") as errors:
        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=errors,
                timeout=timeout,
                check=True,
            )
            returncode = result.returncode
        except subprocess.TimeoutExpired as failure:
            timed_out = True
            error = f"{type(failure).__name__}: completion timed out after {timeout} seconds"
        except subprocess.CalledProcessError as failure:
            returncode = failure.returncode
            error = f"{type(failure).__name__}: completion exited with code {returncode}"
    return {
        "stdout": stdout_file.read_text(encoding="utf-8", errors="replace"),
        "stderr": stderr_file.read_text(encoding="utf-8", errors="replace"),
        "error": error,
        "timed_out": timed_out,
        "returncode": returncode,
    }


def load_evaluation_model(directory: Path, *, dtype: Any, device: str, adapter: Path | None):
    """Use the same untouched FP32 gates/norms for the base and LoRA comparison."""
    from transformers import Qwen3_5ForConditionalGeneration

    from training.train_lora import restore_source_fp32_parameters

    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        directory,
        dtype=dtype,
        attn_implementation="sdpa",
        local_files_only=True,
    )
    restored = restore_source_fp32_parameters(model, directory)
    if adapter is not None:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter, local_files_only=True)
    return model.to(device).eval(), restored


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--gguf", type=Path)
    parser.add_argument("--completion-executable", type=Path)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--eval", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--prompt-source", choices=("runtime", "official"), default="runtime")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("use a fresh output report to preserve previous evaluation evidence")
    if args.gguf and (not args.completion_executable or args.adapter):
        parser.error("GGUF evaluation requires a completion executable and no HF adapter")

    import sys

    root = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(root / "src"), str(root / "for Android")]
    import torch
    from android_adapter.local_provider import parse_qwen_output
    from transformers import AutoTokenizer

    from agent_workspace.core.models import DeltaKind

    records = [
        json.loads(line)
        for line in args.eval.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if not 0 <= args.start_index < len(records):
        parser.error("start-index must select an existing held-out record")
    records = records[args.start_index :]
    if args.limit > 0:
        records = records[: args.limit]
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    dtype = torch.bfloat16 if args.device == "cuda" else torch.float32
    model = None
    source_fp32_restored = []
    if not args.gguf:
        model, source_fp32_restored = load_evaluation_model(
            args.model,
            dtype=dtype,
            device=args.device,
            adapter=args.adapter,
        )
    if model is not None:
        model.config.text_config.use_cache = True
    report = {
        "model": str((args.gguf or args.model).resolve()),
        "tokenizer": str(args.model.resolve()),
        "adapter": str(args.adapter.resolve()) if args.adapter else None,
        "gguf": str(args.gguf.resolve()) if args.gguf else None,
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "parser_sha256": hashlib.sha256(
            (root / "for Android/android_adapter/local_provider.py").read_bytes()
        ).hexdigest(),
        "fixed_gguf_context_tokens": 4096 if args.gguf else None,
        "gguf_automatic_memory_fitting": False if args.gguf else None,
        "eval_sha256": hashlib.sha256(args.eval.read_bytes()).hexdigest(),
        "prompt_source": args.prompt_source,
        "device": args.device,
        "dtype": "GGUF" if args.gguf else str(dtype),
        "source_fp32_restored_before_inference": source_fp32_restored,
        "max_new_tokens": args.max_new_tokens,
        "evaluation_start_index": args.start_index,
        "decoding": "greedy",
        "expected_answers_given_to_model": False,
        "private_user_data_used": False,
        "samples": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for index, record in enumerate(records):
        request, prompt = build_evaluation_prompt(
            record, prompt_source=args.prompt_source, tokenizer=tokenizer
        )
        inputs = tokenizer(prompt, add_special_tokens=False, return_tensors="pt")
        started = time.monotonic()
        if args.gguf:
            with tempfile.TemporaryDirectory(
                prefix="gguf-prompts-", dir=args.output.parent
            ) as folder:
                prompt_file = Path(folder) / "prompt.txt"
                prompt_file.write_text(prompt, encoding="utf-8")
                # File handles avoid Windows pipe-reader hangs across repeated launches.
                process = run_completion_process(
                    [
                        str(args.completion_executable),
                        "-m",
                        str(args.gguf),
                        "-f",
                        str(prompt_file),
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
                        "20261001",
                        "-c",
                        "4096",
                        "-n",
                        str(args.max_new_tokens),
                        "-t",
                        str(args.threads),
                        "-tb",
                        str(args.threads),
                    ],
                    Path(folder),
                )
                cli_stdout, cli_stderr = process["stdout"], process["stderr"]
            # The pinned completion executable prints this status message on EOG;
            # it is not a generated model token. Preserve stdout as separate evidence.
            raw, cli_eog_footer = strip_completion_footer(cli_stdout)
            generated_count = len(tokenizer(raw, add_special_tokens=False)["input_ids"])
            input_count = inputs["input_ids"].shape[-1]
        else:
            inputs = inputs.to(args.device)
            with torch.inference_mode():
                generated = model.generate(
                    **inputs,
                    max_new_tokens=args.max_new_tokens,
                    do_sample=False,
                    use_cache=True,
                    eos_token_id=[
                        tokenizer.convert_tokens_to_ids("<|im_end|>"),
                        tokenizer.convert_tokens_to_ids("<|endoftext|>"),
                    ],
                    pad_token_id=tokenizer.eos_token_id,
                )
            generated_ids = generated[0, inputs["input_ids"].shape[-1] :]
            raw = tokenizer.decode(generated_ids, skip_special_tokens=False)
            generated_count = len(generated_ids)
            input_count = inputs["input_ids"].shape[-1]
        # llama.cpp stops before EOG; match that boundary without removing tool tags.
        text = raw.split("<|im_end|>", 1)[0].split("<|endoftext|>", 1)[0]
        sample = {
            "id": record["id"],
            "metadata": record.get("metadata", {}),
            "raw_output": raw,
            "elapsed_seconds": time.monotonic() - started,
            "input_tokens": input_count,
            "generated_tokens": generated_count,
            "token_counts_estimated": args.gguf is not None,
            "output_limit_reached": generated_count >= args.max_new_tokens,
            "protocol_valid": False,
            "correct": False,
        }
        if args.gguf:
            sample["completion_stdout"] = cli_stdout
            sample["completion_eog_footer"] = cli_eog_footer
            sample["completion_stderr"] = cli_stderr
            sample["completion_process_returncode"] = process["returncode"]
            sample["completion_process_timed_out"] = process["timed_out"]
        try:
            if args.gguf and process["error"] is not None:
                raise RuntimeError(process["error"])
            deltas = parse_qwen_output(text, request, f"heldout-{index}")
            actual_calls = [
                {"name": delta.tool_call.name, "arguments": delta.tool_call.arguments}
                for delta in deltas
                if delta.kind is DeltaKind.TOOL_CALL
            ]
            actual_text = "".join(
                delta.text or "" for delta in deltas if delta.kind is DeltaKind.TEXT
            )
            expected = record["expected"]
            sample.update(protocol_valid=True, calls=actual_calls, text=actual_text)
            if expected["kind"] == "tool_call":
                sample["correct"] = actual_calls == expected["calls"]
            else:
                sample["correct"] = (
                    not actual_calls
                    and all(value in actual_text for value in expected.get("must_contain", []))
                    and all(value not in actual_text for value in expected.get("forbidden", []))
                )
        except Exception as failure:
            sample["error"] = f"{type(failure).__name__}: {failure}"
        report["samples"].append(sample)
        report["completed_samples"] = len(report["samples"])
        report["protocol_valid_count"] = sum(row["protocol_valid"] for row in report["samples"])
        report["correct_count"] = sum(row["correct"] for row in report["samples"])
        _write_report(args.output, report)
        print(
            json.dumps(
                {
                    "event": "evaluated",
                    "id": sample["id"],
                    "protocol_valid": sample["protocol_valid"],
                    "correct": sample["correct"],
                    "elapsed_seconds": sample["elapsed_seconds"],
                }
            ),
            flush=True,
        )
    report["finished"] = True
    _write_report(args.output, report)


if __name__ == "__main__":
    main()
