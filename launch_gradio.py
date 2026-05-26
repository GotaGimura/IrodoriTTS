"""
AiMeru / Irodori-TTS — Gradio UI ランチャー

起動するもの:
  - TTS v3 UI      → http://localhost:7860
  - VoiceDesign UI → http://localhost:7861

使い方:
  python launch_gradio.py          # 両方起動
  python launch_gradio.py --v3     # TTS v3 だけ
  python launch_gradio.py --vd     # VoiceDesign だけ
  python launch_gradio.py --no-browser  # ブラウザ自動オープンしない
"""
from __future__ import annotations
import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# ── 設定 ────────────────────────────────────────────────
REPO_URL    = "https://github.com/Aratako/Irodori-TTS"
REPO_DIR    = Path.home() / "Dev" / "Irodori-TTS"   # clone 先
PORT_V3     = 7860
PORT_VD     = 7861
# デフォルトはループバックのみ。外部公開する場合は --network フラグを使う。
SERVER_NAME_DEFAULT = "127.0.0.1"
# ────────────────────────────────────────────────────────


def find_uv() -> str:
    """uv コマンドのパスを返す。見つからなければ終了。"""
    uv = shutil.which("uv")
    if uv:
        return uv
    # macOS / Linux: well-known install path
    candidates = [
        Path.home() / ".local" / "bin" / "uv",
        Path("/usr/local/bin/uv"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    print("❌  uv が見つかりません。")
    print("    インストール: https://docs.astral.sh/uv/getting-started/installation/")
    print("    macOS/Linux:  curl -LsSf https://astral.sh/uv/install.sh | sh")
    print("    Windows:      winget install --id=astral-sh.uv -e")
    sys.exit(1)


def ensure_repo(uv: str) -> None:
    """リポジトリが存在しなければ clone し、venv を準備する。"""
    if not REPO_DIR.exists():
        print(f"📦  Irodori-TTS を clone します → {REPO_DIR}")
        subprocess.run(["git", "clone", REPO_URL, str(REPO_DIR)], check=True)
    else:
        print(f"✅  Irodori-TTS: {REPO_DIR}")

    venv = REPO_DIR / ".venv"
    if not venv.exists():
        print("🔧  依存関係をインストール中（初回のみ）…")
        subprocess.run([uv, "sync", "--extra", "cpu"], cwd=str(REPO_DIR), check=True)
    else:
        print("✅  仮想環境: 準備済み")


def launch(uv: str, script: str, port: int, label: str, server_name: str) -> subprocess.Popen:
    """Gradio スクリプトをサブプロセスで起動して Popen を返す。"""
    script_path = REPO_DIR / script
    if not script_path.exists():
        print(f"⚠  {script} が見つかりません（スキップ）")
        return None

    cmd = [
        uv, "run", "python", str(script_path),
        "--server-name", server_name,
        "--server-port", str(port),
    ]
    display_host = "localhost" if server_name == "127.0.0.1" else server_name
    print(f"🚀  {label} 起動中 → http://{display_host}:{port}")
    # stdout/stderr はターミナルに流す
    return subprocess.Popen(cmd, cwd=str(REPO_DIR))


def open_browser(ports: list[int], delay: float = 4.0) -> None:
    """少し待ってからブラウザでタブを開く。"""
    time.sleep(delay)
    for port in ports:
        webbrowser.open(f"http://localhost:{port}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Irodori-TTS Gradio UI ランチャー")
    parser.add_argument("--v3",         action="store_true", help="TTS v3 だけ起動")
    parser.add_argument("--vd",         action="store_true", help="VoiceDesign だけ起動")
    parser.add_argument("--no-browser", action="store_true", help="ブラウザを開かない")
    parser.add_argument(
        "--network",
        action="store_true",
        help="LAN 内の他端末からアクセスできるよう 0.0.0.0 でリッスン（デフォルトは 127.0.0.1）",
    )
    args = parser.parse_args()

    server_name = "0.0.0.0" if args.network else SERVER_NAME_DEFAULT
    if args.network:
        print("⚠  --network 指定: LAN 全体に公開されます。信頼できるネットワークのみで使用してください。")

    # デフォルト: 両方
    run_v3 = args.v3 or (not args.v3 and not args.vd)
    run_vd = args.vd or (not args.v3 and not args.vd)

    uv = find_uv()
    ensure_repo(uv)
    print()

    procs: list[subprocess.Popen] = []
    open_ports: list[int] = []

    if run_v3:
        p = launch(uv, "gradio_app.py", PORT_V3, "TTS v3 UI", server_name)
        if p:
            procs.append(p)
            open_ports.append(PORT_V3)

    if run_vd:
        p = launch(uv, "gradio_app_voicedesign.py", PORT_VD, "VoiceDesign UI", server_name)
        if p:
            procs.append(p)
            open_ports.append(PORT_VD)

    if not procs:
        print("起動できるプロセスがありませんでした。")
        sys.exit(1)

    print()
    print("─" * 50)
    if PORT_V3 in open_ports:
        print(f"  TTS v3 UI      →  http://localhost:{PORT_V3}")
    if PORT_VD in open_ports:
        print(f"  VoiceDesign UI →  http://localhost:{PORT_VD}")
    print("─" * 50)
    print("  Ctrl+C で終了")
    print()

    if not args.no_browser:
        import threading
        threading.Thread(target=open_browser, args=(open_ports,), daemon=True).start()

    # 全プロセスが終わるまで待機（Ctrl+C で全終了）
    try:
        while True:
            for p in procs:
                if p.poll() is not None:
                    print(f"⚠  プロセスが終了しました (returncode={p.returncode})")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n⛔  停止中…")
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        print("✅  終了しました")


if __name__ == "__main__":
    main()
