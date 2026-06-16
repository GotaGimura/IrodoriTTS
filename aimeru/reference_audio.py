"""
Reference audio preparation helpers.

Non-WAV audio/video files are converted with FFmpeg into a local ignored folder.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import shutil
import subprocess
from pathlib import Path


SUPPORTED_REFERENCE_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
    ".opus",
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
}


@dataclass(frozen=True)
class PreparedReferenceAudio:
    source_path: Path
    wav_path: Path
    converted: bool
    format_label: str


def is_supported_reference_audio(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_REFERENCE_EXTENSIONS


def prepare_reference_audio(path: Path, speaker_id: str, project_root: Path) -> PreparedReferenceAudio:
    path = path.expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"参照音声ファイルが見つかりません: {path}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_REFERENCE_EXTENSIONS:
        raise ValueError(f"非対応ファイル形式です: {suffix}")
    if suffix == ".wav":
        return PreparedReferenceAudio(
            source_path=path,
            wav_path=path,
            converted=False,
            format_label="wav",
        )

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "この形式を参照音声として使うにはFFmpegが必要です。"
            ".wavファイルを指定するか、FFmpegをインストールしてください。"
        )

    out_dir = project_root / ".local" / "converted_voice_refs"
    out_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:10]
    stem = _safe_stem(path.stem)
    out_path = out_dir / f"{speaker_id}_{stem}_{digest}.wav"

    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-ac",
        "1",
        "-ar",
        "24000",
        str(out_path),
    ]
    result = subprocess.run(
        command,
        cwd=str(project_root),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"FFmpeg変換に失敗しました: {detail[:500]}")

    return PreparedReferenceAudio(
        source_path=path,
        wav_path=out_path,
        converted=True,
        format_label=f"{suffix.lstrip('.')} -> wav",
    )


def _safe_stem(stem: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._")
    return safe or "reference"
