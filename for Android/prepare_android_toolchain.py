#!/usr/bin/env python3
"""Prepare pinned official Termux launchers in Android's executable library dir.

Only libtalloc's DT_NEEDED spelling is shortened to a PackageManager-compatible
lib*.so name. The modification and both digests are recorded in the manifest.
Run before Gradle packaging; no model weights or rootfs enter the APK.
"""

from __future__ import annotations

import gzip
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
BASE = "https://packages.termux.dev/apt/termux-main/pool/main/"
TERMUX_RECIPE_COMMIT = "f62cfca293e44326f2b838e4daf36539f920798f"
PACKAGES = {
    "arm64-v8a": [
        (
            "p/proot/proot_5.1.107.95_aarch64.deb",
            98732,
            "0a1b3d0f6ef76436c5ed924cd8e8f5a6b7186e99e1650eb2d9bc734e218a74cb",
        ),
        (
            "libt/libtalloc/libtalloc_2.4.3_aarch64.deb",
            33128,
            "ac81ad623d74c209718b9f3acb2dd702cc8a88c431e820d212229910b4db29da",
        ),
        (
            "liba/libandroid-shmem/libandroid-shmem_0.7_aarch64.deb",
            7216,
            "0da3a24d558b93c92bcf8d611e0826a99ff96e396b148e6cdf33b47c47c57ff6",
        ),
    ],
    "x86_64": [
        (
            "p/proot/proot_5.1.107.95_x86_64.deb",
            108772,
            "f63ce9bd0d38715eae0163a3772f3395913587444c7ce7232091c6d359afe3c3",
        ),
        (
            "libt/libtalloc/libtalloc_2.4.3_x86_64.deb",
            33520,
            "7ca2eaae2e53b28228a01301bc410b62845403d6317c25b8e0a7f40681de0628",
        ),
        (
            "liba/libandroid-shmem/libandroid-shmem_0.7_x86_64.deb",
            7388,
            "ffa9e4c87467b158b148d0ff92dda796aa038276c2075af3269cdcdb06f25797",
        ),
    ],
}
MEMBERS = [
    (0, "bin/proot", "libagent_proot.so", True),
    (0, "libexec/proot/loader", "libagent_proot_loader.so", False),
    (1, "lib/libtalloc.so.2.4.3", "libtalloc.so", False),
    (2, "lib/libandroid-shmem.so", "libandroid-shmem.so", False),
]
SOURCE_ARCHIVES = [
    (
        "proot-5.1.107.95.zip",
        "https://github.com/termux/proot/archive/v5.1.107.95.zip",
        "dbb50381c2f0b5c342bdf3d3467d80c21d2a4677d9dadd14159fa3b32f11b319",
        "GPL-2.0-only",
    ),
    (
        "talloc-2.4.3.tar.gz",
        "https://www.samba.org/ftp/talloc/talloc-2.4.3.tar.gz",
        "dc46c40b9f46bb34dd97fe41f548b0e8b247b77a918576733c528e83abd854dd",
        "LGPL-3.0-or-later (upstream); GPL-3.0 (Termux package declaration)",
    ),
    (
        "libandroid-shmem-0.7.tar.gz",
        "https://github.com/termux/libandroid-shmem/archive/refs/tags/v0.7.tar.gz",
        "1e5ff8459bc0a8c229dd8a94b27d119987e09ef3414331c2b5ebfff20b98e867",
        "BSD-3-Clause",
    ),
    (
        "termux-packages-" + TERMUX_RECIPE_COMMIT + ".tar.gz",
        "https://codeload.github.com/termux/termux-packages/tar.gz/" + TERMUX_RECIPE_COMMIT,
        "9b59326af012166f3cfb9e1100bdf64990361d084d0350717146f40116d0c786",
        "See package recipes and patch licenses",
    ),
]
LICENSE_FILES = [
    (
        "GPL-3.0.txt",
        "https://www.gnu.org/licenses/gpl-3.0.txt",
        35149,
        "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986",
    ),
]


def read_deb_member(data: bytes, member_name: str) -> bytes:
    if not data.startswith(b"!<arch>\n"):
        raise ValueError("Invalid Debian archive")
    offset = 8
    while offset + 60 <= len(data):
        header = data[offset : offset + 60]
        if header[58:60] != b"`\n":
            raise ValueError("Invalid Debian archive header")
        size = int(header[48:58])
        if size < 0 or offset + 60 + size > len(data):
            raise ValueError("Invalid Debian archive member size")
        name = header[:16].decode("ascii").strip().rstrip("/")
        payload = data[offset + 60 : offset + 60 + size]
        offset += 60 + size + (size % 2)
        if name.startswith("data.tar"):
            with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
                for member in archive:
                    if (
                        member.name == member_name
                        and member.isfile()
                        and member.size <= 2 * 1024 * 1024
                    ):
                        stream = archive.extractfile(member)
                        assert stream is not None
                        return stream.read()
    raise ValueError("The pinned Debian archive member is absent")


def patch_talloc_needed(data: bytes) -> bytes:
    expected = b"libtalloc.so.2\x00"
    if data.count(expected) != 1:
        raise ValueError("The expected talloc soname is absent or ambiguous")
    return data.replace(expected, b"libtalloc.so\x00\x00\x00", 1)


def validate_elf(data: bytes, abi: str) -> None:
    expected = {"arm64-v8a": 183, "x86_64": 62}.get(abi)
    if (
        len(data) < 64
        or data[:6] != b"\x7fELF\x02\x01"
        or struct.unpack_from("<H", data, 18)[0] != expected
    ):
        raise ValueError("The launcher ELF architecture is invalid")


def _fetch(url: str, digest: str, target: Path, size: int | None = None) -> bytes:
    if target.is_file():
        value = target.read_bytes()
        if hashlib.sha256(value).hexdigest() == digest and (size is None or len(value) == size):
            return value
    urls = [url]
    if url.startswith("https://github.com/") and "/archive/" in url:
        project, ref = url.removeprefix("https://github.com/").split("/archive/", 1)
        extension = "zip" if ref.endswith(".zip") else "tar.gz"
        ref = ref.removesuffix("." + extension)
        if not ref.startswith("refs/"):
            ref = "refs/tags/" + ref
        urls.append(f"https://codeload.github.com/{project}/{extension}/{ref}")
    # Upstream hosts (samba.org, gnu.org, GitHub) are occasionally slow; one stalled read used to
    # fail the whole build. Each mirror gets three tries with a longer timeout and a short backoff.
    attempts = [(candidate, attempt) for candidate in urls for attempt in range(3)]
    for index, (candidate, attempt) in enumerate(attempts):
        try:
            with urllib.request.urlopen(candidate, timeout=60) as response:
                value = response.read(16 * 1024 * 1024 + 1)
            break
        except (OSError, urllib.error.URLError):
            if index == len(attempts) - 1:
                raise
            time.sleep(2 * (attempt + 1))
    if (
        len(value) > 16 * 1024 * 1024
        or hashlib.sha256(value).hexdigest() != digest
        or (size is not None and len(value) != size)
    ):
        raise ValueError("The official launcher download failed its pinned size or SHA256")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(value)
    os.replace(temporary, target)
    return value


def _prepare_source_asset(
    filename: str, url: str, digest: str, source_dir: Path
) -> tuple[str, bytes]:
    # AGP expands *.gz inputs before packaging and removes their extension.
    # *.tgz preserves the exact upstream compressed archive and its digest.
    compressed_tar = filename.endswith(".tar.gz")
    asset_name = filename.removesuffix(".tar.gz") + ".tgz" if compressed_tar else filename
    target = source_dir / asset_name
    legacy = source_dir / filename
    if compressed_tar and legacy.is_file() and not target.exists():
        data = legacy.read_bytes()
        if hashlib.sha256(data).hexdigest() == digest:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_bytes(data)
            os.replace(temporary, target)
    blob = _fetch(url, digest, target)
    if compressed_tar:
        directory = source_dir.resolve()
        if not directory.is_relative_to(ROOT.resolve()):
            raise ValueError(
                "Refusing to remove legacy source assets outside the Android source root"
            )
        verified = []
        # Check every identity before removing any old generated asset. These
        # exact names belong to this builder; other files remain untouched.
        for path, expected in (
            (legacy, blob),
            (source_dir / filename.removesuffix(".gz"), gzip.decompress(blob)),
        ):
            if not path.exists():
                continue
            if path.is_symlink() or path.resolve().parent != directory or not path.is_file():
                raise ValueError("Refusing to remove an unsafe legacy source asset")
            actual = path.read_bytes()
            if (
                len(actual) != len(expected)
                or hashlib.sha256(actual).digest() != hashlib.sha256(expected).digest()
            ):
                raise ValueError("Refusing to remove a legacy source asset with changed identity")
            verified.append(path)
        for path in verified:
            path.unlink()
    return asset_name, blob


def prepare() -> dict:
    cache = ROOT / "kotlin_app/build/toolchain-downloads"
    # A local official-package research cache may seed development; CI uses the
    # same public, exact URL and digest checks and does not depend on that cache.
    # The repository also vendors the pinned packages, because Termux removes old versions upstream.
    seeds = (ROOT / "third_party/termux-packages", ROOT.parent / "output/android-toolchain-research")
    manifest = {
        "schema_version": 1,
        "proot_version": "5.1.107.95",
        "abis": {},
        "sources": [],
        "recipe_commit": TERMUX_RECIPE_COMMIT,
        "source_scope": (
            "Pinned upstream sources and Termux recipes/patches; official .deb hashes "
            "are verified, without a bit-identical rebuild guarantee"
        ),
    }
    for abi, records in PACKAGES.items():
        binaries = []
        for filename, size, digest in records:
            target = cache / filename.rsplit("/", 1)[-1]
            for seed in seeds:
                if target.exists() or not (seed / target.name).is_file():
                    continue
                candidate = (seed / target.name).read_bytes()
                if len(candidate) == size and hashlib.sha256(candidate).hexdigest() == digest:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(candidate)
            binaries.append(_fetch(BASE + filename, digest, target, size))
        target_dir = ROOT / "kotlin_app/src/main/jniLibs" / abi
        target_dir.mkdir(parents=True, exist_ok=True)
        files = {}
        for package, member, name, modify in MEMBERS:
            original = read_deb_member(
                binaries[package], "./data/data/com.termux/files/usr/" + member
            )
            validate_elf(original, abi)
            installed = patch_talloc_needed(original) if modify else original
            (target_dir / name).write_bytes(installed)
            files[name] = {
                "size": len(installed),
                "sha256": hashlib.sha256(installed).hexdigest(),
                "original_sha256": hashlib.sha256(original).hexdigest(),
                "package_url": BASE + records[package][0],
                "package_size": records[package][1],
                "package_sha256": records[package][2],
                "modification": "DT_NEEDED libtalloc.so.2 renamed libtalloc.so; unchanged ABI"
                if modify
                else None,
            }
        manifest["abis"][abi] = {
            "architecture": "aarch64" if abi == "arm64-v8a" else "x86_64",
            "files": files,
        }
    source_dir = ROOT / "kotlin_app/src/main/assets/toolchain/corresponding-source"
    for filename, url, digest, license_id in SOURCE_ARCHIVES:
        asset_name, blob = _prepare_source_asset(filename, url, digest, source_dir)
        manifest["sources"].append(
            {
                "file": "corresponding-source/" + asset_name,
                "upstream_file": filename,
                "url": url,
                "size": len(blob),
                "sha256": digest,
                "license": license_id,
            }
        )
    assets = ROOT / "kotlin_app/src/main/assets/toolchain"
    assets.mkdir(parents=True, exist_ok=True)
    manifest["licenses"] = []
    for name, url, size, digest in LICENSE_FILES:
        vendored = ROOT / "licenses" / name
        if vendored.exists():
            data = vendored.read_bytes()
            if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f"The vendored {name} license failed its pinned size or SHA256")
            temporary = (assets / name).with_suffix(".txt.tmp")
            temporary.write_bytes(data)
            os.replace(temporary, assets / name)
        else:
            _fetch(url, digest, assets / name, size)
        manifest["licenses"].append({"file": name, "url": url, "size": size, "sha256": digest})
    (assets / "launchers.json").write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
    (assets / "NOTICE.txt").write_text(
        "Agent Workspace's optional toolchain starts a separate PRoot process.\n"
        "PRoot: Termux v5.1.107.95, GPL-2.0; talloc 2.4.3: upstream LGPL-3.0-or-later, "
        "Termux package declaration GPL-3.0; "
        "libandroid-shmem 0.7: BSD-3-Clause. Complete pinned upstream source archives, "
        "including their license texts, accompany this APK in corresponding-source/. "
        "Gzip source archives use .tgz asset names to preserve their original compressed bytes. "
        "The complete GPL v3 text accompanying LGPL v3 is also bundled as GPL-3.0.txt.\n"
        "The sole executable modification changes the DT_NEEDED spelling libtalloc.so.2 "
        "to libtalloc.so for Android APK native-library extraction. It changes no source or ABI. "
        "Exact original and modified digests and official sources appear in launchers.json.\n"
        "Complete Termux build recipes, patches, and build scripts are bundled at commit "
        + TERMUX_RECIPE_COMMIT
        + ". Package versions and upstream hashes match that commit; "
        "no bit-identical reproduction of the official .deb artifacts is asserted. "
        "See https://github.com/termux/termux-packages/tree/"
        + TERMUX_RECIPE_COMMIT
        + "/packages/proot and respective libtalloc/libandroid-shmem packages. "
        "Rootfs/packages are optional "
        "downloads whose separate licenses and sources are in mobile_toolchain_catalog.json.\n",
        "utf-8",
    )
    return manifest


if __name__ == "__main__":
    result = prepare()
    print(json.dumps({"abis": list(result["abis"]), "source_archives": len(result["sources"])}))
