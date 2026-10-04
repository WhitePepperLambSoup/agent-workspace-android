"""Download a pinned public Qwen checkpoint into the isolated training folder."""

from __future__ import annotations

import argparse
from pathlib import Path

QWEN_REVISION = "2fc06364715b967f1860aea9cf38778875588b17"


def main() -> None:
    from huggingface_hub import snapshot_download

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    location = snapshot_download(
        repo_id="Qwen/Qwen3.5-0.8B",
        revision=QWEN_REVISION,
        local_dir=str(args.output.resolve()),
        token=False,
        allow_patterns=[
            "*.safetensors",
            "*.safetensors.index.json",
            "config.json",
            "generation_config.json",
            "tokenizer*",
            "vocab.json",
            "merges.txt",
            "chat_template.jinja",
            "*preprocessor_config.json",
            "README.md",
            "LICENSE*",
        ],
        max_workers=2,
    )
    print(location)


if __name__ == "__main__":
    main()
