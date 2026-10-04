> 历史方案说明：本页保留早期 Termux/原生宿主设计供参考。当前默认 APK 使用 Chaquopy Python 3.12、CPU JNI 推理和可选 PRoot 工具链；旧页的全功能/后台保活/默认工具可用性描述不是当前验收结论。安装与构建请以 [README](README.md)、[当前架构](00_PORTING_OVERVIEW_AND_ARCHITECTURE.md) 和 [构建指南](10_APK_BUILD_AND_RELEASE_GUIDE.md) 为准。

# Android (Termux) 环境自举与依赖打包规范

> 文档编号：AW-AND-01  
> 目标：在无 Root 标准 Android 手机上，通过 Termux 完成 Python 3.12+ 运行时的快速构建与环境初始化。

---

## 1. 前置环境要求与陷阱规避

### 1.1 Termux 来源陷阱
* **严禁从 Google Play 安装 Termux**：Play 商店版本早已停更（停留在 0.101），其软件源已失效，且无法适配 Android 10+ 权限规则。
* **必须使用 F-Droid 或 GitHub Releases 版本**：推荐安装 `Termux v0.118.1+`（支持 64 位 ARM `aarch64`）。

### 1.2 Android 12+ “幽灵进程杀手” (Phantom Process Killer) 规避
* **现象**：Android 12 引入了进程监控，当单个应用派生的子进程（包括 Agent 启动的 python、git、bash 等）累计超过 32 个，或者后台消耗 CPU 过高时，系统会直接静默发送 `SIGKILL` 杀死整个 Termux。
* **规避方案**：
  1. **免电脑解锁（推荐）**：如果配置了无线调试（Wireless Debugging），直接在手机端通过 Termux 执行：
     ```bash
     adb shell device_config put activity_manager max_phantom_processes 2147483647
     ```
  2. **系统设置放行**：在部分 OEM ROM（如 MIUI/HyperOS、ColorOS、OneUI）的“开发者选项”中，直接关闭“启用后台进程限制”或“子进程监控”。

### 1.3 电池休眠与 CPU 锁 (Wakelock)
* Android 的 Doze 机制会在屏幕熄灭 3~5 分钟后彻底冻结网络和 CPU。
* **自举必须执行**：
  ```bash
  termux-wake-lock
  ```
  同时在手机系统“应用信息” -> “省电策略”中设置为“无限制”（Allow unrestricted background usage）。

---

## 2. 依赖安装与 C/Rust 扩展编译优化

本项目根目录 `pyproject.toml` 中的核心依赖包括：
* `cryptography>=50.0.0`（包含底层 Rust 和 OpenSSL 绑定）
* `httpx>=0.27,<1`（纯 Python）
* `jsonschema>=4.23,<5`（纯 Python）
* `pypdf>=6.16.0`（纯 Python）
* `tomli-w>=1.2,<2`（纯 Python）
* `websockets>=17.0.1`（包含可选 C 扩展加速）

### 2.1 依赖安装的两种策略

#### 策略 A：极速混合安装（强烈推荐）
Termux 官方源中已预编译了经过 ARM64 深度调优的 C 模块，直接用 `pkg` 安装二进制，避免在手机上经历漫长的 Rust 编译：

```bash
# 1. 更新基础源
pkg update && pkg upgrade -y

# 2. 安装基础编译工具与系统级 Python 依赖
pkg install -y \
  python \
  python-pip \
  python-cryptography \
  python-numpy \
  git \
  ripgrep \
  openssl \
  libffi \
  curl

# 3. 验证 Python 版本
python --version  # 应输出 Python 3.11.x 或 3.12.x
```

#### 策略 B：纯虚拟环境（Virtualenv）编译安装
如果需要完全隔离的 Virtualenv，必须配置编译环境变量：

```bash
pkg install -y clang rust binutils make

export CARGO_BUILD_TARGET="aarch64-linux-android"
export PYO3_CROSS_LIB_DIR="$PREFIX/lib"

python -m venv ~/.agent-venv --system-site-packages
source ~/.agent-venv/bin/activate
pip install -e . --no-build-isolation
```
> **注意**：`--system-site-packages` 允许 venv 复用 Termux 预装的 `python-cryptography`，可节省约 15 分钟的手机编译时间并杜绝内存爆掉风险。

---

## 3. 工作区与存储挂载规范

### 3.1 核心原则：工作区与数据库必须位于 `$HOME`
* **Termux 私有目录**：`$HOME` 实际路径为 `/data/data/com.termux/files/home/`。
  * 该目录位于 Linux 原生 `ext4` 分区，支持硬链接、软链接、POSIX 权限位（`chmod 0600`）以及 SQLite WAL 的文件级排他锁。
* **禁止将数据库放入 `/sdcard/`**：
  * Android 外部共享存储通过 FUSE 虚拟文件系统挂载，对 POSIX `flock()` 和 SQLite WAL 写入具有严重的兼容性缺陷，容易发生 `database disk image is malformed`。

### 3.2 访问手机公共存储（可选外设）
如果需要让 Agent 读取或写入手机公共相册、下载目录：
```bash
termux-setup-storage
```
执行后 Termux 会在 `~/storage/` 建立软链接：
* `~/storage/downloads` -> `/sdcard/Download`
* `~/storage/shared` -> `/sdcard`
Agent 可以通过读取此路径处理用户丢入的外部文件。

---

## 4. 一键安装与自举脚本实现 (`packaging/termux/bootstrap.sh`)

此脚本设计为部署端直接通过 `curl -sSL ... | bash` 运行：

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "[*] Initializing Agent Workspace on Android (Termux)..."

# 1. 唤醒锁与防止后台被杀
if command -v termux-wake-lock >/dev/null 2>&1; then
    echo "[+] Acquiring Termux WakeLock..."
    termux-wake-lock
fi

# 2. 系统源更新与必要工具链
echo "[+] Installing core system packages..."
pkg update -y
pkg install -y python python-pip python-cryptography git ripgrep openssl libffi

# 3. 目录与工作区准备
PROJECT_DIR="$HOME/agent-workspace"
if [ ! -d "$PROJECT_DIR" ]; then
    echo "[+] Cloning or copying Agent Workspace into $PROJECT_DIR..."
    # 可从本地或 Git 仓库检出
fi

# 4. 创建轻量虚拟环境
VENV_DIR="$HOME/.agent-venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[+] Creating virtual environment with system site packages..."
    python -m venv "$VENV_DIR" --system-site-packages
fi

# 5. 激活并安装项目核心依赖
source "$VENV_DIR/bin/activate"
cd "$PROJECT_DIR"

echo "[+] Installing Python dependencies..."
pip install --upgrade pip
pip install "httpx>=0.27,<1" "jsonschema>=4.23,<5" "pypdf>=6.16.0" "tomli-w>=1.2,<2" "websockets>=17.0.1"
pip install -e . --no-deps

# 6. 自检测试
echo "[+] Running verification sanity check..."
agent-workspace --help >/dev/null

echo "[✓] Agent Workspace bootstrap completed successfully!"
echo "    Run: source $VENV_DIR/bin/activate && agent-workspace run \"hello\""
```
