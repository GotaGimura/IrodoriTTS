#!/usr/bin/env bash
# =============================================================================
# AiMeru Voice Studio — セットアップスクリプト (macOS / Linux)
#
# 実行方法:
#   chmod +x setup.sh
#   ./setup.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=============================================="
echo "  AiMeru Voice Studio — セットアップ"
echo "=============================================="
echo ""

# ── 1. Python バージョン確認 ────────────────────────────
PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌  Python 3.11 以上が見つかりません。"
    echo "    https://www.python.org/downloads/ からインストールしてください。"
    exit 1
fi

PYTHON_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
echo "✅  Python $PYTHON_VER ($PYTHON)"

# ── 2. 仮想環境の作成 ────────────────────────────────────
VENV_DIR="$SCRIPT_DIR/.venv"
if [ -d "$VENV_DIR" ]; then
    echo "✅  仮想環境: 既存 (.venv/)"
else
    echo "🔧  仮想環境を作成中…"
    "$PYTHON" -m venv "$VENV_DIR"
    echo "✅  仮想環境を作成しました (.venv/)"
fi

# ── 3. pip アップグレード + 依存インストール ────────────────
echo "📦  依存ライブラリをインストール中…"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r requirements.txt
echo "✅  インストール完了"

# ── 4. voice_samples/ の確認 ────────────────────────────
echo ""
echo "── 参照音声ファイルについて ──────────────────────────"
if [ -f "$SCRIPT_DIR/voice_samples/ai.wav" ] && [ -f "$SCRIPT_DIR/voice_samples/meru.wav" ]; then
    echo "✅  voice_samples/ai.wav   — 検出済み"
    echo "✅  voice_samples/meru.wav — 検出済み"
else
    echo "⚠   voice_samples/ に参照音声ファイルが見つかりません。"
    echo "    Irodori-TTS-Server に登録している音声ファイルを"
    echo "    voice_samples/ フォルダに配置してください。"
    echo "    （ファイル名は任意。アプリ内の話者設定で指定します）"
fi

# ── 完了 ────────────────────────────────────────────────
echo ""
echo "=============================================="
echo "  セットアップ完了！"
echo ""
echo "  起動方法:"
echo "    ./run.sh"
echo ""
echo "  Irodori-TTS-Server は別途起動が必要です。"
echo "  詳しくは README.md を参照してください。"
echo "=============================================="
