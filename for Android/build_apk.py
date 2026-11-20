#!/usr/bin/env python3
"""Android APK 一键构建 (One-step debug APK build).

1. 运行 build_release.py --prepare-only: 打包 Web 页面与 Python 源码, 准备原生源码、
   工具链与许可文件 (与 README 和 CI 相同的准备步骤);
2. 检查 JDK 17+、Android SDK 与 Gradle wrapper, 缺少时给出指引并以退出码 2 结束;
3. 运行 Gradle assembleDebug, 以它的退出码结束。

任何一步失败, 进程都以非零退出码结束, 脚本和 CI 不会把失败当成成功。
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


def android_sdk() -> str | None:
    """Where Gradle finds the Android SDK: ANDROID_HOME, ANDROID_SDK_ROOT or local.properties."""
    for name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(name):
            return os.environ[name]
    properties = KOTLIN_APP_DIR / "local.properties"
    if properties.is_file():
        for line in properties.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith("sdk.dir="):
                return line.split("=", 1)[1].strip()
    return None


def print_guide(is_windows: bool) -> None:
    print("\n" + "=" * 70)
    print("【方法 A：Android Studio】")  # noqa: RUF001
    print(f"  先运行 python build_release.py --prepare-only, 再在 Android Studio 打开 {KOTLIN_APP_DIR.resolve()}")
    print("  并选择 Build -> Build Bundle(s) / APK(s) -> Build APK(s)。")
    print("【方法 B：命令行】")  # noqa: RUF001
    print("  安装 JDK 17+ 并设置 ANDROID_HOME 后执行：")  # noqa: RUF001
    print("  python build_release.py --prepare-only")
    if is_windows:
        print(f'  cd "{KOTLIN_APP_DIR}" && .\\gradlew.bat assembleDebug')
    else:
        print(f'  cd "{KOTLIN_APP_DIR}" && ./gradlew assembleDebug')
    print("=" * 70 + "\n")


def main() -> None:
    print("=" * 70)
    print("      Agent Workspace for Android: 一键构建 Debug APK")
    print("=" * 70)

    # 第一步: 与 README、CI 相同的准备 (Web 页面、Python 源码、原生源码、工具链、许可文件)。
    print("\n>>> [步骤 1/2] 准备 APK 所需的资源...")
    ret = run_cmd([sys.executable, str(THIS_DIR / "build_release.py"), "--prepare-only"], cwd=THIS_DIR)
    if ret != 0:
        print("[!] 准备步骤失败，终止构建。")  # noqa: RUF001
        sys.exit(ret)

    # 第二步: 检查编译环境并调用 Gradle; 它的退出码就是本脚本的退出码。
    print("\n>>> [步骤 2/2] 检查编译环境并生成 APK...")
    java_cmd = java_command()
    has_supported_java = java_cmd is not None and is_supported_java(java_cmd)
    is_windows = sys.platform.startswith("win")
    gradle_wrapper = KOTLIN_APP_DIR / ("gradlew.bat" if is_windows else "gradlew")
    missing = []
    if not has_supported_java:
        missing.append(f"JDK 17+（找到的是 {java_cmd}）" if java_cmd else "JDK 17+")  # noqa: RUF001
    if android_sdk() is None:
        missing.append("Android SDK（ANDROID_HOME 或 kotlin_app/local.properties 的 sdk.dir）")  # noqa: RUF001
    if not gradle_wrapper.exists():
        missing.append(f"Gradle wrapper {gradle_wrapper}")
    if missing:
        print(f"[!] 缺少：{'、'.join(missing)}；没有构建 APK。")  # noqa: RUF001
        print_guide(is_windows)
        sys.exit(2)
    ret = run_cmd([str(gradle_wrapper), "assembleDebug"], cwd=KOTLIN_APP_DIR)
    if ret != 0:
        print(f"[!] Gradle 构建失败，退出码 {ret}。")  # noqa: RUF001
        sys.exit(ret)
    print("\n" + "=" * 70)
    print(f"APK 输出目录: {KOTLIN_APP_DIR / 'build' / 'outputs' / 'apk' / 'debug'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
