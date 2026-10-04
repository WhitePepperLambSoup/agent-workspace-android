#!/data/data/com.termux/files/usr/bin/bash
# 启动 Termux 终端 CLI 交互
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$HOME/.agent-workspace-env"

if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

python3 "$SCRIPT_DIR/entrypoint.py" "$@"
