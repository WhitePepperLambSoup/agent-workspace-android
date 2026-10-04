#!/data/data/com.termux/files/usr/bin/bash
# 启动后台移动端 Web 伴侣控制台
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$HOME/.agent-workspace-env"

if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

echo "[+] 正在启动 Agent Workspace 移动 Web 伴侣..."
python3 "$SCRIPT_DIR/entrypoint.py" serve-mobile --port 8080 "$@"
