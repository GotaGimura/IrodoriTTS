"""
AiMeru Voice Studio - 音声ミキサー

個別 WAV ファイルを pause_ms 間隔で結合して full_mix.wav を生成する。
pydub + ffmpeg を使用。
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Callable, Optional

logger = logging.getLogger(__name__)


def create_full_mix(
    wav_files: List[str],
    output_path: Path,
    pause_ms: int = 400,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> tuple[bool, str]:
    """
    wav_files を順番に結合し pause_ms の無音を挿入して output_path へ書き出す。
    progress_cb(current, total) が渡された場合は進捗コールバックを呼ぶ。
    Returns: (success: bool, error_message: str)
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        return False, "pydub がインストールされていません (pip install pydub)"

    existing = [f for f in wav_files if Path(f).exists() and Path(f).stat().st_size > 0]
    if not existing:
        return False, "結合対象の WAV ファイルが見つかりません"

    total = len(existing)
    pause = AudioSegment.silent(duration=pause_ms)
    mix = AudioSegment.empty()

    for i, wav_path in enumerate(existing):
        if progress_cb:
            progress_cb(i + 1, total)
        try:
            seg = AudioSegment.from_wav(wav_path)
        except Exception as e:
            logger.warning("スキップ %s: %s", wav_path, e)
            continue
        if i > 0:
            mix += pause
        mix += seg

    if len(mix) == 0:
        return False, "結合結果が空です"

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mix.export(str(output_path), format="wav")
    except Exception as e:
        return False, f"ファイル書き出しエラー: {e}"

    logger.info("full_mix 生成完了: %s (%.1fs)", output_path, len(mix) / 1000)
    return True, ""


def get_wav_duration_seconds(wav_path: str) -> Optional[float]:
    """WAV の再生時間（秒）を返す。失敗時は None。"""
    try:
        from pydub import AudioSegment
        seg = AudioSegment.from_wav(wav_path)
        return len(seg) / 1000.0
    except Exception:
        return None
