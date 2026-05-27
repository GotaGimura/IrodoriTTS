from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

APP_VERSION = "0.1.0"
DEFAULT_IRODORI_DIR = Path.home() / "Dev" / "Irodori-TTS"
DEFAULT_CHECKPOINT = "Aratako/Irodori-TTS-500M-v3"
UV_RUN_ARGS = ["run", "--no-sync"]
VOICE_SAMPLE_DIR = Path(__file__).resolve().parents[1] / "voice_samples"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs" / "api_server"

app = FastAPI(title="AiMeru Irodori-TTS API", version=APP_VERSION)


class IrodoriOptions(BaseModel):
    num_steps: int = Field(default=40, ge=1)
    cfg_scale_text: float = Field(default=3.0)
    cfg_scale_speaker: float = Field(default=5.0)
    seed: int | None = None
    chunking_enabled: bool = True
    chunk_min_chars: int = 80


class SpeechRequest(BaseModel):
    model: str = "irodori-tts"
    input: str
    voice: str = "default"
    response_format: str = "wav"
    speed: float = Field(default=1.0, gt=0)
    irodori: IrodoriOptions = Field(default_factory=IrodoriOptions)


def _irodori_dir() -> Path:
    return Path(os.environ.get("IRODORI_TTS_DIR", str(DEFAULT_IRODORI_DIR))).expanduser()


def _checkpoint() -> str:
    return os.environ.get("IRODORI_TTS_CHECKPOINT", DEFAULT_CHECKPOINT).strip() or DEFAULT_CHECKPOINT


def _find_uv() -> str | None:
    uv = shutil.which("uv")
    if uv:
        return uv
    candidates = [
        Path.home() / ".local" / "bin" / "uv.exe",
        Path.home() / ".local" / "bin" / "uv",
        Path.home() / ".cargo" / "bin" / "uv.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _voice_reference_path(voice: str) -> Path | None:
    voice_key = "".join(ch for ch in voice.upper() if ch.isalnum() or ch == "_")
    env_value = os.environ.get(f"IRODORI_VOICE_{voice_key}_WAV")
    if env_value:
        path = Path(env_value).expanduser()
        if path.is_file():
            return path

    for suffix in (".wav", ".mp3", ".m4a", ".flac"):
        candidate = VOICE_SAMPLE_DIR / f"{voice}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def _backend_status() -> dict[str, Any]:
    repo_dir = _irodori_dir()
    uv = _find_uv()
    return {
        "repo_dir": str(repo_dir),
        "repo_exists": repo_dir.is_dir(),
        "infer_py_exists": (repo_dir / "infer.py").is_file(),
        "uv_exists": uv is not None,
        "uv_run_args": UV_RUN_ARGS,
        "checkpoint": _checkpoint(),
        "voice_sample_dir": str(VOICE_SAMPLE_DIR),
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "AiMeru Irodori-TTS API",
        "version": APP_VERSION,
        "backend": _backend_status(),
    }


@app.get("/debug/cuda")
def debug_cuda() -> JSONResponse:
    repo_dir = _irodori_dir()
    uv = _find_uv()
    if uv is None:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "error": "uv_not_found",
                "detail": "uv was not found. Install uv or add it to PATH.",
                "backend": _backend_status(),
            },
        )
    if not repo_dir.is_dir():
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "error": "irodori_repo_not_found",
                "detail": f"Irodori-TTS checkout was not found: {repo_dir}",
                "backend": _backend_status(),
            },
        )

    code = (
        "import torch, json; "
        "available=torch.cuda.is_available(); "
        "print(json.dumps({"
        "'ok': True, "
        "'torch_version': torch.__version__, "
        "'cuda_version': torch.version.cuda, "
        "'cuda_available': available, "
        "'device': torch.cuda.get_device_name(0) if available else 'CUDA not available'"
        "}))"
    )
    completed = subprocess.run(
        [uv, *UV_RUN_ARGS, "python", "-c", code],
        cwd=str(repo_dir),
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "error": "cuda_check_failed",
                "detail": "uv run --no-sync CUDA check failed.",
                "stdout": completed.stdout[-2000:],
                "stderr": completed.stderr[-2000:],
                "backend": _backend_status(),
            },
        )

    try:
        import json

        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except Exception:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "cuda_check_parse_failed",
                "stdout": completed.stdout[-2000:],
                "stderr": completed.stderr[-2000:],
            },
        )
    payload["command"] = "uv run --no-sync python -c <torch cuda check>"
    return JSONResponse(content=payload)


@app.post("/v1/audio/speech", response_model=None)
def audio_speech(request: SpeechRequest) -> Response:
    repo_dir = _irodori_dir()
    infer_py = repo_dir / "infer.py"
    uv = _find_uv()

    if not repo_dir.is_dir() or not infer_py.is_file():
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "error": "TTS backend is not wired yet",
                "detail": "External Irodori-TTS checkout was not found or infer.py is missing.",
                "backend": _backend_status(),
            },
        )
    if uv is None:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "error": "TTS backend is not wired yet",
                "detail": "uv was not found. Install uv or add it to PATH.",
                "backend": _backend_status(),
            },
        )

    ref_wav = _voice_reference_path(request.voice)
    if ref_wav is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": "voice_not_found",
                "detail": (
                    f"Voice '{request.voice}' needs a reference file such as "
                    f"{VOICE_SAMPLE_DIR / (request.voice + '.wav')}."
                ),
            },
        )

    if request.response_format.lower() != "wav":
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "unsupported_response_format",
                "detail": "Only response_format='wav' is supported by this local bridge.",
            },
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    duration_scale = 1.0 / float(request.speed)

    with tempfile.NamedTemporaryFile(
        prefix="aimeru_", suffix=".wav", dir=str(OUTPUT_DIR), delete=False
    ) as tmp:
        out_path = Path(tmp.name)

    cmd = [
        uv,
        *UV_RUN_ARGS,
        "python",
        "infer.py",
        "--hf-checkpoint",
        _checkpoint(),
        "--text",
        request.input,
        "--ref-wav",
        str(ref_wav),
        "--output-wav",
        str(out_path),
        "--duration-scale",
        f"{duration_scale:.6f}",
        "--num-steps",
        str(request.irodori.num_steps),
        "--cfg-scale-text",
        str(request.irodori.cfg_scale_text),
        "--cfg-scale-speaker",
        str(request.irodori.cfg_scale_speaker),
    ]
    if request.irodori.seed is not None:
        cmd.extend(["--seed", str(request.irodori.seed)])

    try:
        completed = subprocess.run(
            cmd,
            cwd=str(repo_dir),
            check=False,
            capture_output=True,
            text=True,
            timeout=float(os.environ.get("IRODORI_TTS_TIMEOUT_SEC", "600")),
        )
    except subprocess.TimeoutExpired:
        out_path.unlink(missing_ok=True)
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "error": "server_unavailable",
                "detail": "Irodori-TTS inference timed out.",
            },
        )

    if completed.returncode != 0:
        out_path.unlink(missing_ok=True)
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "error": "server_unavailable",
                "detail": "Irodori-TTS inference failed.",
                "stdout": completed.stdout[-2000:],
                "stderr": completed.stderr[-2000:],
            },
        )

    if not out_path.is_file() or out_path.stat().st_size == 0:
        out_path.unlink(missing_ok=True)
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "file_error",
                "detail": "Irodori-TTS completed but did not produce a WAV file.",
            },
        )

    return FileResponse(
        path=str(out_path),
        media_type="audio/wav",
        filename=f"{request.voice}.wav",
    )
