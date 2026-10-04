#!/usr/bin/env python3
"""Prepare verified Android inputs and build an unsigned or explicitly signed release APK."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KOTLIN_ROOT = ROOT / "kotlin_app"
LLAMA_REVISION = "7fe450e19305b828c199d602c23a8337aaa1f03b"
LLAMA_SHA256 = "a6861d549427f814dc591c439e08206f67ffaba0248344d421589abf18199e67"
LLAMA_URL = f"https://codeload.github.com/ggml-org/llama.cpp/tar.gz/{LLAMA_REVISION}"
WRAPPER_SHA256 = "2db75c40782f5e8ba1fc278a5574bab070adccb2d21ca5a6e5ed840888448046"
LICENSE_INPUTS = {
    "Chaquopy-17.0.0": {
        "file": "Chaquopy-17.0.0-LICENSE.txt",
        "asset": "Chaquopy-17.0.0-MIT.txt",
        "sha256": "345a9fdfeed355d37b18569ef277ba56eb0ab7c0b17a08a90163ce8d33d2b862",
        "source": "https://raw.githubusercontent.com/chaquo/chaquopy/17.0.0/LICENSE.txt",
    },
    "nlohmann-json-3.12.0": {
        "file": "nlohmann-json-3.12.0-LICENSE.txt",
        "asset": "nlohmann-json-MIT.txt",
        "sha256": "46a65cffd1ea955132d95a8dd921640714a8d6b537d2e4e482d31145ae95b603",
        "source": "https://raw.githubusercontent.com/nlohmann/json/v3.12.0/LICENSE.MIT",
    },
}
SIGNING_FIELDS = (
    "AGENT_ANDROID_KEYSTORE",
    "AGENT_ANDROID_KEY_ALIAS",
    "AGENT_ANDROID_STORE_PASSWORD",
    "AGENT_ANDROID_KEY_PASSWORD",
)


def validate_signing(environment, *, signed):
    present = [bool(environment.get(field)) for field in SIGNING_FIELDS]
    if any(present) and not all(present):
        raise ValueError("release signing requires all four complete signing environment variables")
    if signed and not all(present):
        raise ValueError("signed release requires all four signing environment variables")
    if all(present) and not signed:
        raise ValueError("signing variables are present; select --signed explicitly")
    if signed and not Path(environment[SIGNING_FIELDS[0]]).is_file():
        raise ValueError("release keystore path does not exist")
    return signed


def verify_wrapper(kotlin_root=KOTLIN_ROOT):
    jar = kotlin_root / "gradle/wrapper/gradle-wrapper.jar"
    if not jar.is_file() or hashlib.sha256(jar.read_bytes()).hexdigest() != WRAPPER_SHA256:
        raise ValueError("Gradle 8.11.1 wrapper JAR failed its published SHA256 check")


def gradle_command(kotlin_root, *, signed):
    wrapper = kotlin_root / ("gradlew.bat" if sys.platform.startswith("win") else "gradlew")
    return [str(wrapper), "assembleRelease", "--no-daemon", "--stacktrace"]


def prepare_native_source():
    target = KOTLIN_ROOT / f"build/tooling/llama.cpp-{LLAMA_REVISION}.tar.gz"
    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != LLAMA_SHA256:
        with urllib.request.urlopen(LLAMA_URL, timeout=60) as response:
            data = response.read(128 * 1024 * 1024 + 1)
        if len(data) > 128 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != LLAMA_SHA256:
            raise ValueError("pinned llama.cpp source failed its SHA256 or size limit")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(target)
    assets = KOTLIN_ROOT / "src/main/assets/licenses"
    assets.mkdir(parents=True, exist_ok=True)
    with tarfile.open(target, "r:gz") as archive:
        license_entry = next(
            (
                item
                for item in archive
                if item.isfile() and item.name.endswith("/LICENSE") and item.name.count("/") == 1
            ),
            None,
        )
        if license_entry is None or license_entry.size > 1024 * 1024:
            raise ValueError("pinned llama.cpp source has no bounded upstream license")
        stream = archive.extractfile(license_entry)
        if stream is None:
            raise ValueError("cannot read llama.cpp upstream license")
        (assets / "llama.cpp-MIT.txt").write_bytes(stream.read())
    (assets / "llama.cpp-source.json").write_text(
        json.dumps(
            {
                "component": "llama.cpp",
                "revision": LLAMA_REVISION,
                "sha256": LLAMA_SHA256,
                "source": LLAMA_URL,
                "license": "MIT",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def prepare_license_assets():
    verified = []
    for component, metadata in LICENSE_INPUTS.items():
        path = ROOT / "licenses" / metadata["file"]
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != metadata["sha256"]:
            raise ValueError(f"{component} upstream license failed its SHA256 check")
        verified.append((metadata, data))
    assets = KOTLIN_ROOT / "src/main/assets/licenses"
    assets.mkdir(parents=True, exist_ok=True)
    for metadata, data in verified:
        (assets / metadata["asset"]).write_bytes(data)
    (assets / "vendored-license-sources.json").write_text(
        json.dumps({"schema_version": 1, "components": LICENSE_INPUTS}, indent=2) + "\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signed", action="store_true")
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="verify/download public build inputs and package assets without running Gradle",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify wrapper/signing configuration without downloading or building",
    )
    arguments = parser.parse_args()
    validate_signing(os.environ, signed=arguments.signed)
    verify_wrapper()
    if arguments.check:
        print("Gradle wrapper verified; release signing configuration valid")
        return 0
    if sys.version_info[:2] != (3, 12):
        parser.error("release preparation requires Python 3.12; use the pinned build interpreter")
    from prepare_android_toolchain import prepare

    prepare()
    native_source = prepare_native_source()
    prepare_license_assets()
    subprocess.run(
        [sys.executable, str(ROOT / "package_apk_assets.py"), "--runtime", "chaquopy"],
        cwd=ROOT,
        check=True,
    )
    if arguments.prepare_only:
        print("Verified launchers, corresponding source, llama.cpp and Chaquopy assets prepared")
        return 0
    environment = {
        **os.environ,
        "AGENT_WORKSPACE_BUILD_PYTHON": sys.executable,
        "AGENT_LLAMA_ARCHIVE": str(native_source),
    }
    subprocess.run(
        gradle_command(KOTLIN_ROOT, signed=arguments.signed),
        cwd=KOTLIN_ROOT,
        env=environment,
        check=True,
    )
    print(
        "Release APK generated in kotlin_app/build/outputs/apk/release; "
        "validate signatures and install identity before distribution"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
