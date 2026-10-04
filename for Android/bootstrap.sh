#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Agent Workspace for Android (Termux) - 一键环境配置与自举脚本
# ==============================================================================

set -euo pipefail

echo "============================================================"
echo "   🤖 Agent Workspace Android (Termux) 自动初始化程序"
echo "============================================================"

# 1. 阻止系统锁屏杀死 CPU
if command -v termux-wake-lock >/dev/null 2>&1; then
    echo "[+] 正在申请 Termux WakeLock 防止休眠..."
    termux-wake-lock
fi

# 2. 检查并安装核心包与 Python 预编译依赖
echo "[+] 正在配置 Termux Linux 系统软件包..."
pkg update -y
pkg install -y python python-pip python-cryptography git ripgrep openssl libffi curl

# 3. 检查 Termux:API 是否存在并推荐安装
if ! command -v termux-clipboard-get >/dev/null 2>&1; then
    echo "[!] 提示: 未检测到 termux-api 命令。正在为您自动安装..."
    pkg install -y termux-api || echo "[!] 警告: 请确保已在手机安装 Termux:API 官方 App。"
fi

# 4. 创建专用的 Python 虚拟环境 (带 system-site-packages 以复用预编译 C 扩展)
VENV_DIR="$HOME/.agent-workspace-env"
if [ ! -d "$VENV_DIR" ]; then
    echo "[+] 正在创建轻量虚拟环境: $VENV_DIR ..."
    python -m venv "$VENV_DIR" --system-site-packages
fi

source "$VENV_DIR/bin/activate"

# 5. 安装纯 Python 核心依赖
echo "[+] 正在安装 Agent Workspace 纯 Python 依赖项..."
pip install --upgrade pip
pip install "httpx>=0.27,<1" "jsonschema>=4.23,<5" "pypdf>=6.16.0" "tomli-w>=1.2,<2" "websockets>=17.0.1"

# 6. 配置可执行权限
chmod +x run_cli.sh run_server.sh entrypoint.py

echo "============================================================"
echo "   [✓] 部署成功！您可以开始使用："
echo "   1. 运行终端交互：  bash run_cli.sh"
echo "   2. 启动手机Web界面：bash run_server.sh"
echo "============================================================"
