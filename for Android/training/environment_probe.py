"""Record the local training runtime without inspecting user conversations or secrets."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    versions = {}
    for name in ("torch", "transformers", "peft", "accelerate", "huggingface-hub", "safetensors"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    report = {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "versions": versions,
        "private_data_used": False,
    }
    if versions["torch"]:
        import torch

        report["cuda_version"] = torch.version.cuda
        report["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info()
            report["gpu"] = {
                "name": torch.cuda.get_device_name(0),
                "free_bytes": free,
                "total_bytes": total,
                "bf16_supported": torch.cuda.is_bf16_supported(),
            }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
