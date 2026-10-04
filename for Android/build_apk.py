#!/usr/bin/env python3
"""Android APK 一键打包与构建辅助工具 (One-click APK Build Helper)。

功能:
1. 运行 package_apk_assets.py 完成 Web 前端与 Python 源码的资产同步;
2. 运行 test_android_stack.py 校验 Python 适配层运行健全性;
3. 检测系统环境中的 JDK 17+ 与 Android SDK;
4. 若环境就绪, 自动调用 Gradle 编译生成 Debug APK;
5. 若本地环境未安装 JDK/Android SDK, 生成详细的 Android Studio / CI 构建指引。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent
KOTLIN_APP_DIR = THIS_DIR / "kotlin_app"


_JAVA_VERSION_RE = re.compile(r'version\s+"(?:(?P<legacy>1\.)?(?P<major>\d+))', re.IGNORECASE)


def detect_java_major(java_cmd: str) -> int | None:
    """Return the Java major version reported by ``java -version``."""
    try:
        result = subprocess.run(
            [java_cmd, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    match = _JAVA_VERSION_RE.search(output)
    if match is None:
        return None
    try:
        return int(match.group("major"))
    except (TypeError, ValueError):
        return None


def is_supported_java(java_cmd: str) -> bool:
    """Gradle Android builds require a JDK 17 or newer runtime."""
    major = detect_java_major(java_cmd)
    return major is not None and major >= 17


def java_command() -> str | None:
    """Resolve a working Java executable, preferring JAVA_HOME when valid."""
    candidates: list[str] = []
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidate = Path(java_home) / (
            "bin/java.exe" if sys.platform.startswith("win") else "bin/java"
        )
        if candidate.is_file():
            candidates.append(str(candidate))
    path_java = shutil.which("java")
    if path_java and path_java not in candidates:
        candidates.append(path_java)
    for candidate in candidates:
        if detect_java_major(candidate) is not None:
            return candidate
    return candidates[0] if candidates else None


def run_cmd(cmd: list[str], cwd: Path) -> int:
    print(f"[*] 执行命令: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=cwd)
    return res.returncode


def main() -> None:
    print("=" * 70)
    print("      Agent Workspace for Android: 一键构建与打包流水线")
    print("=" * 70)

    # 第一步: 打包 APK 内置资产 (Web UI + Agent Code + Bootstrap Rootfs)
    print("\n>>> [步骤 1/3] 同步与打包 APK Assets...")
    asset_packer = THIS_DIR / "package_apk_assets.py"
    ret = run_cmd([sys.executable, str(asset_packer)], cwd=THIS_DIR)
    if ret != 0:
        print("[!] 资产打包失败，终止构建。")  # noqa: RUF001
        sys.exit(ret)

    # 第二步: 运行全栈单元与集成测试
    print("\n>>> [步骤 2/3] 验证 Android 适配层与 Web 伴侣健全性...")
    test_runner = THIS_DIR / "test_android_stack.py"
    ret = run_cmd([sys.executable, str(test_runner)], cwd=THIS_DIR)
    if ret != 0:
        print("[!] 适配层测试未完全通过，终止构建。")  # noqa: RUF001
        sys.exit(ret)

    # 第三步: 检查 Gradle 与 Java 环境并尝试编译
    print("\n>>> [步骤 3/3] 检查 Android 编译环境并生成 APK...")
    java_cmd = java_command()
    has_supported_java = java_cmd is not None and is_supported_java(java_cmd)
    is_windows = sys.platform.startswith("win")
    gradle_wrapper = KOTLIN_APP_DIR / ("gradlew.bat" if is_windows else "gradlew")

    if has_supported_java and gradle_wrapper.exists():
        print("[+] 检测到 JDK 17+，尝试直接调用 Gradle 构建 APK...")  # noqa: RUF001
        cmd = [str(gradle_wrapper), "assembleDebug"]
        try:
            ret = subprocess.run(cmd, cwd=KOTLIN_APP_DIR).returncode
            if ret == 0:
                print("\n" + "=" * 70)
                print(">>> 恭喜! APK 构建成功完成! <<<")
                print(f"APK 输出目录: {KOTLIN_APP_DIR / 'build' / 'outputs' / 'apk' / 'debug'}")
                print("=" * 70)
                return
            else:
                print(f"[!] Gradle 构建退出码: {ret}")
        except Exception as e:
            print(f"[!] 启动 Gradle 失败: {e}")

    if java_cmd is not None and not has_supported_java:
        print(f"[!] 检测到 {java_cmd}，但版本低于 JDK 17；当前构建不会调用 Gradle。")  # noqa: RUF001

    # 若未直接完成, 输出标准构建指导
    print("\n" + "=" * 70)
    print(">>> 提示: 本地未配置全局 JDK 17 / Android SDK 或构建需要图形化 IDE <<<")
    print("=" * 70)
    print("你现在可以通过以下两种方式在 1 分钟内完成 APK 最终打包输出：\n")  # noqa: RUF001
    print("【方法 A：使用 Android Studio (最简单推荐)】")  # noqa: RUF001
    print("  1. 打开 Android Studio；")  # noqa: RUF001
    print(f"  2. 点击 'Open' 选择工程目录: {KOTLIN_APP_DIR.resolve()}；")  # noqa: RUF001
    print(
        "  3. 等待 Gradle 同步完成，点击菜单 "  # noqa: RUF001
        "'Build' -> 'Build Bundle(s) / APK(s)' -> 'Build APK(s)'；"  # noqa: RUF001
    )
    print("  4. 构建完成即可将安装包直接部署到真实手机或模拟器！\n")  # noqa: RUF001
    print("【方法 B：命令行 Gradle (适合 CI/CD 或终端高手)】")  # noqa: RUF001
    print("  确保已安装 JDK 17+ 并配置 ANDROID_HOME 环境变量，随后在终端执行：")  # noqa: RUF001
    if is_windows:
        print(f'  cd "{KOTLIN_APP_DIR}" && .\\gradlew.bat assembleDebug')
    else:
        print(f'  cd "{KOTLIN_APP_DIR}" && ./gradlew assembleDebug')
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
