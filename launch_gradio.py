"""
Launcher for the external Irodori-TTS Gradio UIs.

This repository contains AiMeru Voice Studio. The Irodori-TTS application
itself is expected to live in a separate checkout, by default:

    C:\\Users\\koben\\Dev\\Irodori-TTS

Ports:
    7860  TTS v3 Gradio UI
    7861  VoiceDesign Gradio UI
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

DEFAULT_REPO_DIR = Path(os.environ.get("IRODORI_TTS_DIR", Path.home() / "Dev" / "Irodori-TTS"))
PORT_V3 = 7860
PORT_VD = 7861
SERVER_NAME_DEFAULT = "127.0.0.1"


def find_uv() -> str:
    uv = shutil.which("uv")
    if uv:
        return uv

    candidates = [
        Path.home() / ".local" / "bin" / "uv",
        Path.home() / ".cargo" / "bin" / "uv.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "uv" / "uv.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    print("[ERROR] uv was not found.")
    print("        Install uv first: https://docs.astral.sh/uv/getting-started/installation/")
    print("        Windows: winget install --id=astral-sh.uv -e")
    return ""


def validate_repo(repo_dir: Path) -> bool:
    if not repo_dir.exists():
        print(f"[ERROR] Irodori-TTS checkout was not found: {repo_dir}")
        print("        Clone the upstream Irodori-TTS repository separately, for example:")
        print("        cd C:\\Users\\koben\\Dev")
        print("        git clone https://github.com/Aratako/Irodori-TTS.git")
        print("        Or set IRODORI_TTS_DIR / pass --repo-dir to its location.")
        return False

    missing = [
        name
        for name in ("gradio_app.py", "gradio_app_voicedesign.py")
        if not (repo_dir / name).exists()
    ]
    if missing:
        print(f"[ERROR] Irodori-TTS checkout is missing expected Gradio scripts: {', '.join(missing)}")
        print(f"        Checked directory: {repo_dir}")
        return False

    print(f"[OK] Irodori-TTS checkout: {repo_dir}")
    return True


def launch(uv: str, repo_dir: Path, script: str, port: int, label: str, server_name: str) -> subprocess.Popen:
    cmd = [
        uv,
        "run",
        "python",
        script,
        "--server-name",
        server_name,
        "--server-port",
        str(port),
    ]
    display_host = "localhost" if server_name == "127.0.0.1" else server_name
    print(f"[..] Starting {label}: http://{display_host}:{port}")
    return subprocess.Popen(cmd, cwd=str(repo_dir))


def open_browser(ports: list[int], delay: float = 4.0) -> None:
    time.sleep(delay)
    for port in ports:
        webbrowser.open(f"http://localhost:{port}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch external Irodori-TTS Gradio UIs.")
    parser.add_argument("--repo-dir", default=str(DEFAULT_REPO_DIR), help="Path to the external Irodori-TTS checkout.")
    parser.add_argument("--v3", action="store_true", help="Launch only the TTS v3 UI on port 7860.")
    parser.add_argument("--vd", action="store_true", help="Launch only the VoiceDesign UI on port 7861.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser tabs automatically.")
    parser.add_argument(
        "--network",
        action="store_true",
        help="Bind to 0.0.0.0 for LAN access. Default is 127.0.0.1 only.",
    )
    args = parser.parse_args()

    repo_dir = Path(args.repo_dir).expanduser().resolve()
    server_name = "0.0.0.0" if args.network else SERVER_NAME_DEFAULT
    if args.network:
        print("[WARN] --network exposes the Gradio UI on your LAN.")
        print("       Use this only on a trusted network. Default local-only binding is 127.0.0.1.")

    uv = find_uv()
    if not uv:
        return 1
    if not validate_repo(repo_dir):
        return 1

    run_v3 = args.v3 or (not args.v3 and not args.vd)
    run_vd = args.vd or (not args.v3 and not args.vd)

    procs: list[subprocess.Popen] = []
    open_ports: list[int] = []

    if run_v3:
        procs.append(launch(uv, repo_dir, "gradio_app.py", PORT_V3, "TTS v3 UI", server_name))
        open_ports.append(PORT_V3)

    if run_vd:
        procs.append(launch(uv, repo_dir, "gradio_app_voicedesign.py", PORT_VD, "VoiceDesign UI", server_name))
        open_ports.append(PORT_VD)

    print()
    print("Running:")
    if PORT_V3 in open_ports:
        print(f"  TTS v3 UI       http://localhost:{PORT_V3}")
    if PORT_VD in open_ports:
        print(f"  VoiceDesign UI  http://localhost:{PORT_VD}")
    print("Press Ctrl+C to stop.")
    print()

    if not args.no_browser:
        threading.Thread(target=open_browser, args=(open_ports,), daemon=True).start()

    try:
        while True:
            alive = [p for p in procs if p.poll() is None]
            if not alive:
                return max((p.returncode or 0) for p in procs)
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopping Gradio processes...")
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        return 0


if __name__ == "__main__":
    sys.exit(main())
