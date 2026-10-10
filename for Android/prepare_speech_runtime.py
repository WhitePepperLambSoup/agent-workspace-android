#!/usr/bin/env python3
"""Prepare the pinned offline speech recognition runtime for the APK.

The prebuilt sherpa-onnx JNI library (ONNX Runtime linked in) goes into the arm64 library dir,
and two small model files into the assets: the silero voice activity detector and SenseVoice's
token list. The 239 MB SenseVoice weights are not bundled; the app downloads them on request
(mobile_model_catalog.SPEECH_CATALOG). x86_64 devices get no offline recognizer and keep using
the phone's own speech recognition.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import struct
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SHERPA_ONNX_VERSION = "1.13.8"
RUNTIME = {
    "url": (
        f"https://github.com/k2-fsa/sherpa-onnx/releases/download/v{SHERPA_ONNX_VERSION}/"
        f"sherpa-onnx-v{SHERPA_ONNX_VERSION}-android-static-link-onnxruntime.tar.bz2"
    ),
    "size": 35101751,
    "sha256": "7583ca385ae7d981e65468455c2ea2c9f2da383921dccfc5658d0dc19d309e6f",
    "member": "./jniLibs/arm64-v8a/libsherpa-onnx-jni.so",
}
SENSEVOICE_HF_REVISION = "2365baeacb507f821a0c8120fcee3d484dba7a07"
SENSEVOICE_MODELSCOPE_REVISION = "73eca47697f980daa3d16112404174b6b950b514"
ASSETS = {
    "silero_vad.onnx": {
        "urls": [
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx"
        ],
        "size": 643854,
        "sha256": "9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6",
        "license": "MIT (Silero Team)",
    },
    "sensevoice-tokens.txt": {
        "urls": [
            "https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/"
            f"resolve/{SENSEVOICE_HF_REVISION}/tokens.txt",
            "https://modelscope.cn/models/pengzhendong/sherpa-onnx-sense-voice-zh-en-ja-ko-yue/"
            f"resolve/{SENSEVOICE_MODELSCOPE_REVISION}/tokens.txt",
        ],
        "size": 315894,
        "sha256": "f449eb28dc567533d7fa59be34e2abca8784f771850c78a47fb731a31429a1dc",
        "license": "FunASR Model License 1.1 (SenseVoice Small, FunAudioLLM / Alibaba)",
    },
}
PAGE_16K = 16 * 1024


def _download(urls: list[str], size: int, digest: str, target: Path) -> bytes:
    if target.is_file():
        value = target.read_bytes()
        if len(value) == size and hashlib.sha256(value).hexdigest() == digest:
            return value
    # Hosts are occasionally slow; each source gets three tries before the next one.
    attempts = [(url, attempt) for url in urls for attempt in range(3)]
    value = b""
    for index, (url, attempt) in enumerate(attempts):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                value = response.read(size + 1)
            if len(value) == size and hashlib.sha256(value).hexdigest() == digest:
                break
        except (OSError, urllib.error.URLError):
            pass
        if index == len(attempts) - 1:
            raise ValueError(f"{target.name} failed its pinned size or SHA256 from every source")
        time.sleep(2 * (attempt + 1))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(value)
    os.replace(temporary, target)
    return value


def check_library(data: bytes) -> None:
    """A 64-bit ARM shared object whose loadable segments fit 16 KB pages (Android 15+)."""
    if (
        len(data) < 64
        or data[:6] != b"\x7fELF\x02\x01"
        or struct.unpack_from("<H", data, 18)[0] != 183
    ):
        raise ValueError("the sherpa-onnx library is not a 64-bit ARM shared object")
    (table,) = struct.unpack_from("<Q", data, 0x20)
    entry_size, count = struct.unpack_from("<HH", data, 0x36)
    aligns = [
        struct.unpack_from("<Q", data, table + index * entry_size + 48)[0]
        for index in range(count)
        if struct.unpack_from("<I", data, table + index * entry_size)[0] == 1  # PT_LOAD
    ]
    if not aligns or min(aligns) < PAGE_16K:
        raise ValueError("the sherpa-onnx library is not aligned for 16 KB memory pages")


def prepare(root: Path = ROOT) -> dict:
    cache = root / "kotlin_app/build/speech-downloads"
    archive = _download(
        [RUNTIME["url"]],
        RUNTIME["size"],
        RUNTIME["sha256"],
        cache / RUNTIME["url"].rsplit("/", 1)[-1],
    )
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:bz2") as bundle:
        member = bundle.getmember(RUNTIME["member"])
        if not member.isfile() or member.size > 64 * 1024 * 1024:
            raise ValueError("the sherpa-onnx archive has no bounded arm64 library")
        stream = bundle.extractfile(member)
        assert stream is not None
        library = stream.read()
    check_library(library)
    libraries = root / "kotlin_app/src/main/jniLibs/arm64-v8a"
    libraries.mkdir(parents=True, exist_ok=True)
    (libraries / "libsherpa-onnx-jni.so").write_bytes(library)
    assets = root / "kotlin_app/src/main/assets/speech"
    assets.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "runtime": {
            "component": "sherpa-onnx (ONNX Runtime 1.28.2 linked in)",
            "version": SHERPA_ONNX_VERSION,
            "license": "Apache-2.0 (sherpa-onnx); MIT (ONNX Runtime)",
            "archive_url": RUNTIME["url"],
            "archive_sha256": RUNTIME["sha256"],
            "abis": {
                "arm64-v8a": {
                    "file": "libsherpa-onnx-jni.so",
                    "size": len(library),
                    "sha256": hashlib.sha256(library).hexdigest(),
                }
            },
        },
        "assets": {},
    }
    for name, metadata in ASSETS.items():
        data = _download(metadata["urls"], metadata["size"], metadata["sha256"], cache / name)
        (assets / name).write_bytes(data)
        manifest["assets"][name] = {
            "size": metadata["size"],
            "sha256": metadata["sha256"],
            "source": metadata["urls"][0],
            "license": metadata["license"],
        }
    (assets / "speech-runtime.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    print(json.dumps(prepare(), indent=2))
