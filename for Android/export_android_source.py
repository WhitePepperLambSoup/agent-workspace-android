#!/usr/bin/env python3
"""Export current Android build source with an explicit allowlist and no device/build state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from pathlib import Path

_EXCLUDED_DIRS = {
    ".git",
    ".gradle",
    ".cxx",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "build",
    "dist",
    "output",
    "tmp",
    "backups",
    "device-backups",
    "device_backups",
    "agent-data",
    "credentials",
    "private",
    "models",
    "runs",
    "downloads",
    "jnilibs",
    "node_modules",
}
_SOURCE_SUFFIXES = {
    ".py",
    ".kt",
    ".java",
    ".kts",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cmake",
    ".html",
    ".css",
    ".js",
    ".mjs",
    ".cjs",
    ".json",
    ".toml",
    ".md",
    ".sh",
    ".bat",
    ".properties",
    ".txt",
    ".xml",
}
_ROOT_FILES = {
    "pyproject.toml",
    "uv.lock",
    "LICENSE",
    "README.md",
    ".gitignore",
    ".gitattributes",
    # Android web tooling and docs live under "for Android/"; the walk below collects them.
    "tests/test_runner_image_compaction.py",
    "tests/test_context_manifest.py",
    "tests/test_context_summary_integrity.py",
    "tests/test_context_summary_accounting.py",
    "tests/test_context_history_recovery.py",
    "tests/test_session_history_tool.py",
    "tests/test_runner.py",
    "docs/superpowers/specs/2026-10-02-local-model-device-settings-design.md",
    "docs/superpowers/plans/2026-10-02-context-summary-integrity.md",
    "docs/superpowers/specs/2026-10-02-session-history-recovery-design.md",
    "docs/superpowers/plans/2026-10-02-session-history-recovery.md",
}
_TRAINING_SOURCE_SUFFIXES = (_SOURCE_SUFFIXES - {".json"}) | {".ps1"}
_TRAINING_CONFIG_FILES = {
    "for Android/training/v4-critical-minima.json",
    "for Android/training/v4-training-plan.json",
    "for Android/training/v5-critical-minima.json",
    "for Android/training/v5-training-plan.json",
}
_TRAINING_DATA_FILES = {
    "for Android/training/data/train.jsonl",
    "for Android/training/data/eval.jsonl",
    "for Android/training/data/catalog.json",
    "for Android/training/data/manifest.json",
    "for Android/training/data/README.md",
    "for Android/training/data-v2/train.jsonl",
    "for Android/training/data-v2/dev.jsonl",
    "for Android/training/data-v2/eval.jsonl",
    "for Android/training/data-v2/catalog.json",
    "for Android/training/data-v2/manifest.json",
    "for Android/training/data-v2/README.md",
    "for Android/training/data-v3/train.jsonl",
    "for Android/training/data-v3/dev.jsonl",
    "for Android/training/data-v3/eval.jsonl",
    "for Android/training/data-v3/catalog.json",
    "for Android/training/data-v3/manifest.json",
    "for Android/training/data-v3/README.md",
    "for Android/training/data-v3/FROZEN.md",
    "for Android/training/data-v4/train.jsonl",
    "for Android/training/data-v4/dev.jsonl",
    "for Android/training/data-v4/eval.jsonl",
    "for Android/training/data-v4/catalog.json",
    "for Android/training/data-v4/manifest.json",
    "for Android/training/data-v4/README.md",
    "for Android/training/data-v4/FROZEN.md",
    "for Android/training/data-v4/android-catalog-source.json",
    "for Android/training/data-v4/android-system-source.json",
    "for Android/training/data-v5/train.jsonl",
    "for Android/training/data-v5/dev.jsonl",
    "for Android/training/data-v5/eval.jsonl",
    "for Android/training/data-v5/catalog.json",
    "for Android/training/data-v5/manifest.json",
    "for Android/training/data-v5/README.md",
    "for Android/training/data-v5/FROZEN.md",
    "for Android/training/data-v5/android-catalog-source.json",
    "for Android/training/data-v5/android-system-source.json",
    "for Android/training/data-v5/dev-workflows.jsonl",
    "for Android/training/data-v5/final-workflows.jsonl",
}


def included_file(relative):
    name, parts = relative.name, relative.parts
    if (
        any(part.lower() in _EXCLUDED_DIRS for part in parts)
        or name.lower() == "local.properties"
        or name.lower().startswith(".env")
    ):
        return False
    if name.lower() in {
        "keys.json",
        "credentials.json",
        "provider-config.json",
        "signing.properties",
    } or name.lower().endswith(
        (".jks", ".keystore", ".pem", ".p12", ".db", ".db-wal", ".db-shm", ".log")
    ):
        return False
    path = relative.as_posix()
    if path in _ROOT_FILES or path == ".github/workflows/android.yml":
        return True
    if parts[:2] == ("src", "agent_workspace"):
        return relative.suffix in {".py", ".json", ".txt"} or name == "py.typed"
    if not parts or parts[0] != "for Android":
        return False
    if "assets" in parts:
        return False  # all APK assets are reproducibly generated before Gradle
    if len(parts) > 1 and parts[1].lower() == "training":
        if path in _TRAINING_CONFIG_FILES:
            return True
        if len(parts) > 2 and (parts[2].lower() == "data" or parts[2].lower().startswith("data-v")):
            # These frozen synthetic records and their schema/hash manifests
            # reproduce SFT. Candidate and future datasets require explicit
            # entries; their Markdown cannot bypass the frozen-data allowlist.
            return path in _TRAINING_DATA_FILES
        # Local probes, provenance dumps, and training reports are generated JSON;
        # keep the training source and dependency declarations instead.
        return relative.suffix in _TRAINING_SOURCE_SUFFIXES or name == ".gitattributes"
    if path == "for Android/kotlin_app/gradle/wrapper/gradle-wrapper.jar":
        return True
    return relative.suffix in _SOURCE_SUFFIXES or name in {"gradlew", ".gitattributes"}


def export_source(source_root, output):
    source_root, output = Path(source_root).resolve(), Path(output).resolve()
    files = []
    paths = [source_root / name for name in sorted(_ROOT_FILES)]
    paths.append(source_root / ".github/workflows/android.yml")
    for relative_root in (Path("src/agent_workspace"), Path("for Android")):
        directory_root = source_root / relative_root
        if not directory_root.is_dir() or any(
            (source_root / Path(*relative_root.parts[:count])).is_symlink()
            for count in range(1, len(relative_root.parts) + 1)
        ):
            continue
        for directory, directories, names in os.walk(directory_root, followlinks=False):
            directories[:] = sorted(
                name
                for name in directories
                if name.lower() not in _EXCLUDED_DIRS
                and name != "assets"
                and not (Path(directory) / name).is_symlink()
            )
            paths.extend(Path(directory) / name for name in sorted(names))
    for path in paths:
        relative = path.relative_to(source_root)
        if (
            not path.is_file()
            or path == output
            or not included_file(relative)
            or any(
                (source_root / Path(*relative.parts[:count])).is_symlink()
                for count in range(1, len(relative.parts) + 1)
            )
        ):
            continue
        files.append((relative.as_posix(), path.read_bytes()))
    if not files:
        raise ValueError("no Android source was found")
    manifest = {
        "schema_version": 1,
        "scope": (
            "current Android and shared Python source with frozen synthetic training data; "
            "generated dependencies and private state excluded"
        ),
        "files": {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            for name, data in files
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (
                0o100755 if name.endswith(".sh") or name.endswith("/gradlew") else 0o100644
            ) << 16
            archive.writestr(info, data)
        info = zipfile.ZipInfo("ANDROID_SOURCE_MANIFEST.json", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False))
    temporary.replace(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parent.parent)
    arguments = parser.parse_args()
    manifest = export_source(arguments.source, arguments.output)
    print(
        f"Exported {len(manifest['files'])} source files; "
        "inspect the archive before public distribution"
    )


if __name__ == "__main__":
    main()
