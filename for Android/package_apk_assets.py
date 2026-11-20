#!/usr/bin/env python3
"""Prepare Android web assets and current Python sources for APK builds.

Python itself comes from Chaquopy through Gradle; this packs the sources and the web page. The
Termux runtime that needed a separate rootfs archive is gone.
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


def should_ignore(path: Path, base: Path = PROJECT_ROOT) -> bool:
    # Only the part below the project counts: a checkout under /build/... or ~/build/... (Docker,
    # CI runners) used to drop every file of src/ and android_adapter/ without a word.
    for part in path.relative_to(base).parts:
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
    # Folders that exist but put nothing in the archive: the engine would not start without them.
    empty: list[str] = []
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. 打包 src/ 目录 (核心 agent_workspace)
        if SRC_DIR.exists():
            for root, _dirs, files in os.walk(SRC_DIR):
                for f in files:
                    file_path = Path(root) / f
                    if not should_ignore(file_path, PROJECT_ROOT):
                        arcname = str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
                        zf.write(file_path, arcname)
                        file_count += 1
            if not file_count:
                empty.append("src")

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
        # The official skill pack this version ships with (mobile_skills.BUNDLED_DIR).
        android_items.append("skills/official")
        for item in android_items:
            target = THIS_DIR / item
            if not target.exists():
                continue
            if target.is_file():
                arcname = f"for Android/{item}"
                zf.write(target, arcname)
                file_count += 1
            elif target.is_dir():
                before = file_count
                for root, _dirs, files in os.walk(target):
                    for f in files:
                        file_path = Path(root) / f
                        if not should_ignore(file_path, PROJECT_ROOT):
                            arcname = str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
                            zf.write(file_path, arcname)
                            file_count += 1
                if file_count == before:
                    empty.append(f"for Android/{item}")

        # 3. 打包根目录的关键配置 (pyproject.toml 等)
        for config_name in ["pyproject.toml"]:
            cfg_path = PROJECT_ROOT / config_name
            if cfg_path.exists() and cfg_path.is_file():
                zf.write(cfg_path, config_name)
                file_count += 1
    if empty:
        zip_path.unlink(missing_ok=True)
        raise SystemExit(f"agent_code.zip would be missing {', '.join(empty)}; nothing was packed")

    size_kb = zip_path.stat().st_size / 1024
    print(
        f"[+] 打包 Agent 源码完成: {file_count} 个文件, 大小 {size_kb:.1f} KB"
        f" -> {zip_path.relative_to(PROJECT_ROOT)}"
    )
    return file_count


def main() -> None:
    parser = argparse.ArgumentParser(description="APK 静态资源打包工具")
    parser.add_argument(
        "--runtime",
        choices=("termux", "chaquopy"),
        default="chaquopy",
        help="Python runtime provider: chaquopy (the only one the app uses)",
    )
    parser.add_argument("--clean", action="store_true", help="构建前清理旧 assets 目录")
    args = parser.parse_args()
    if args.runtime == "termux":
        # Before all the work below, not after it: the old default packed everything, then failed.
        parser.error("the Termux runtime was removed; the app runs Python through Chaquopy (--runtime chaquopy)")

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

    print("=" * 65)
    print(">>> 资源打包成功完成! 所有资产已就绪于 kotlin_app/src/main/assets/ <<<")
    print("=" * 65)


if __name__ == "__main__":
    main()
