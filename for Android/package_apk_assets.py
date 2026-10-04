#!/usr/bin/env python3
"""Prepare Android web assets and current Python sources for APK builds.

The default Termux runtime requires a validated ARM64 rootfs. Chaquopy
provides its Python runtime through Gradle and leaves rootfs assets untouched.
"""

from __future__ import annotations

import argparse
import os
import shutil
import zipfile
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
ASSETS_DIR = THIS_DIR / "kotlin_app" / "src" / "main" / "assets"
WEB_SOURCE_DIR = THIS_DIR / "web_companion"

IGNORED_PATTERNS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".git",
    ".idea",
    ".vscode",
    "kotlin_app",
    ".gradle",
    "build",
}

IGNORED_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".zip",
    ".apk",
    ".tmp",
}


def should_ignore(path: Path) -> bool:
    for part in path.parts:
        if part in IGNORED_PATTERNS:
            return True
    return path.suffix.lower() in IGNORED_EXTENSIONS


def sync_web_assets(dest_dir: Path) -> int:
    """将 web_companion 静态资源复制到 assets/web/"""
    web_dest = dest_dir / "web"
    if web_dest.exists():
        shutil.rmtree(web_dest)
    web_dest.mkdir(parents=True, exist_ok=True)

    copied_count = 0
    for root, _dirs, files in os.walk(WEB_SOURCE_DIR):
        rel_root = Path(root).relative_to(WEB_SOURCE_DIR)
        target_dir = web_dest / rel_root
        target_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            src_file = Path(root) / f
            dst_file = target_dir / f
            shutil.copy2(src_file, dst_file)
            copied_count += 1

    print(f"[+] 同步 Web 资源完成: {copied_count} 个文件 -> {web_dest.relative_to(PROJECT_ROOT)}")
    return copied_count


def build_agent_code_zip(zip_path: Path) -> int:
    """打包 agent_code.zip (包含 src/ 以及 for Android/ 运行所需的所有核心脚本)"""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    file_count = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. 打包 src/ 目录 (核心 agent_workspace)
        if SRC_DIR.exists():
            for root, _dirs, files in os.walk(SRC_DIR):
                for f in files:
                    file_path = Path(root) / f
                    if not should_ignore(file_path):
                        arcname = str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
                        zf.write(file_path, arcname)
                        file_count += 1

        # 2. 打包 for Android/ 下的适配脚本与入口
        android_items = [
            "android_adapter",
            "web_companion",
            "entrypoint.py",
            "bootstrap.sh",
            "run_cli.sh",
            "run_server.sh",
        ]
        android_items.extend(path.name for path in sorted(THIS_DIR.glob("mobile_*.py")))
        android_items.append("mobile_toolchain_catalog.json")
        for item in android_items:
            target = THIS_DIR / item
            if not target.exists():
                continue
            if target.is_file():
                arcname = f"for Android/{item}"
                zf.write(target, arcname)
                file_count += 1
            elif target.is_dir():
                for root, _dirs, files in os.walk(target):
                    for f in files:
                        file_path = Path(root) / f
                        if not should_ignore(file_path):
                            arcname = str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
                            zf.write(file_path, arcname)
                            file_count += 1

        # 3. 打包根目录的关键配置 (pyproject.toml 等)
        for config_name in ["pyproject.toml"]:
            cfg_path = PROJECT_ROOT / config_name
            if cfg_path.exists() and cfg_path.is_file():
                zf.write(cfg_path, config_name)
                file_count += 1

    size_kb = zip_path.stat().st_size / 1024
    print(
        f"[+] 打包 Agent 源码完成: {file_count} 个文件, 大小 {size_kb:.1f} KB"
        f" -> {zip_path.relative_to(PROJECT_ROOT)}"
    )
    return file_count


def _validate_bootstrap_rootfs(path: Path) -> None:
    """Reject metadata-only starter archives before they can enter an APK."""
    if not path.is_file():
        raise ValueError(f"real Termux ARM64 bootstrap archive does not exist: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = {info.filename.rstrip("/") for info in infos}
            required_python = {"usr/bin/python3", "usr/bin/python"}
            if not names.intersection(required_python):
                raise ValueError(
                    f"bootstrap archive {path} does not contain usr/bin/python3 or usr/bin/python"
                )
            uncompressed_bytes = sum(info.file_size for info in infos)
            if len(names) < 25 or uncompressed_bytes < 1_048_576:
                raise ValueError(
                    f"bootstrap archive {path} is a placeholder; provide a real Termux ARM64 rootfs"
                )
            for python_name in required_python.intersection(names):
                payload = archive.read(python_name)[:512]
                if b"Starter Python Stub" in payload or b"starter" in payload.lower():
                    raise ValueError(
                        f"bootstrap archive {path} contains a starter Python stub, not a runtime"
                    )
    except zipfile.BadZipFile as exc:
        raise ValueError(f"bootstrap archive is not a valid ZIP file: {path}") from exc


def ensure_bootstrap_rootfs(bootstrap_zip: Path, custom_bootstrap: Path | None = None) -> None:
    """Require a validated Termux ARM64 rootfs; never create a fake runtime."""
    source = custom_bootstrap if custom_bootstrap is not None else bootstrap_zip
    _validate_bootstrap_rootfs(source)
    if custom_bootstrap is not None:
        bootstrap_zip.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(custom_bootstrap, bootstrap_zip)
        print(f"[+] Using external Bootstrap runtime: {custom_bootstrap}")
        return

    print(f"[*] Bootstrap runtime validated: {bootstrap_zip.relative_to(PROJECT_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="APK 静态资源打包工具")
    parser.add_argument(
        "--runtime",
        choices=("termux", "chaquopy"),
        default="termux",
        help="Python runtime provider (default: termux)",
    )
    parser.add_argument(
        "--bootstrap",
        type=Path,
        default=None,
        help="指定现有的 termux-bootstrap-arm64.zip 路径",
    )
    parser.add_argument("--clean", action="store_true", help="构建前清理旧 assets 目录")
    args = parser.parse_args()

    print("=" * 65)
    print("      Agent Workspace for Android: APK 资源打包流程开始")
    print("=" * 65)

    if args.clean and ASSETS_DIR.exists():
        print(f"[*] 清理旧生成资源: {ASSETS_DIR}")
        for generated in (ASSETS_DIR / "web", ASSETS_DIR / "agent_code.zip"):
            if generated.is_dir():
                shutil.rmtree(generated)
            elif generated.exists():
                generated.unlink()

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 复制 Web 资源
    sync_web_assets(ASSETS_DIR)

    # 2. 压缩代码包
    agent_code_zip = ASSETS_DIR / "agent_code.zip"
    build_agent_code_zip(agent_code_zip)

    # Only Termux requires a separate validated rootfs archive.
    if args.runtime == "termux":
        bootstrap_zip = ASSETS_DIR / "termux-bootstrap-arm64.zip"
        ensure_bootstrap_rootfs(bootstrap_zip, args.bootstrap)

    print("=" * 65)
    print(">>> 资源打包成功完成! 所有资产已就绪于 kotlin_app/src/main/assets/ <<<")
    print("=" * 65)


if __name__ == "__main__":
    main()
