#!/usr/bin/env bash
# AiMeru Voice Studio 起動スクリプト (macOS / Linux)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌  仮想環境が見つかりません。先に setup.sh を実行してください。"
    echo "    ./setup.sh"
    exit 1
fi

exec "$VENV_PYTHON" main.py "$@"
