"""Verify the public pinned HF checkpoint against its published LFS hashes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import urlopen


def main() -> None:
    from prepare_model import QWEN_REVISION
    from train_lora import sha256_file

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    url = f"https://huggingface.co/api/models/Qwen/Qwen3.5-0.8B/revision/{QWEN_REVISION}?blobs=true"
    with urlopen(url, timeout=30) as response:
        info = json.load(response)
    checks = []
    for item in info["siblings"]:
        name = item["rfilename"]
        if not name.endswith(".safetensors"):
            continue
        expected = item["lfs"]["sha256"]
        actual = sha256_file(args.model / name)
        checks.append(
            {
                "file": name,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "passed": actual == expected,
            }
        )
    report = {
        "passed": bool(checks)
        and info["sha"] == QWEN_REVISION
        and all(item["passed"] for item in checks),
        "repo_id": "Qwen/Qwen3.5-0.8B",
        "revision": QWEN_REVISION,
        "source": url,
        "weight_checks": checks,
        "tokenizer_sha256": {
            name: sha256_file(args.model / name)
            for name in ("tokenizer.json", "tokenizer_config.json", "chat_template.jinja")
        },
        "authenticated_requests_used": False,
        "private_user_data_used": False,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)
    if not report["passed"]:
        raise SystemExit("Base checkpoint hashes do not match the pinned public model")


if __name__ == "__main__":
    main()
