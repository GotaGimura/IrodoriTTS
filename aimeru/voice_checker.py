"""
AiMeru Voice Studio - 参照音声品質チェッカー (§20)

チェック項目:
  - ファイルの存在・ファイル名 (ASCII)
  - 長さ (推奨 10〜30 秒)
  - チャンネル数 (モノラル推奨)
  - サンプルレート (表示のみ)
  - ピーク音量 (極端に小さくないか)
"""
from __future__ import annotations
import math
import struct
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# チェック基準値
DURATION_MIN_SEC = 10.0
DURATION_MAX_SEC = 30.0
PEAK_MIN_DBFS    = -20.0  # これ未満は音量不足とみなす


@dataclass
class VoiceCheckResult:
    ok: bool = False
    duration_sec: Optional[float] = None
    channels: Optional[int] = None
    sample_rate: Optional[int] = None
    peak_dbfs: Optional[float] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def summary_html(self) -> str:
        """QLabel に渡せる HTML サマリーを返す。"""
        if self.errors:
            joined = "　".join(
                f'<span style="color:red">❌ {e}</span>' for e in self.errors
            )
            return joined

        parts: List[str] = []

        # 長さ
        if self.duration_sec is not None:
            ok = DURATION_MIN_SEC <= self.duration_sec <= DURATION_MAX_SEC
            icon, color = ("✅", "green") if ok else ("⚠", "darkorange")
            parts.append(
                f'<span style="color:{color}">{icon} {self.duration_sec:.1f}s</span>'
            )

        # チャンネル
        if self.channels is not None:
            ok = self.channels == 1
            icon, color = ("✅", "green") if ok else ("⚠", "darkorange")
            label = "モノラル" if self.channels == 1 else f"ステレオ ({self.channels}ch)"
            parts.append(f'<span style="color:{color}">{icon} {label}</span>')

        # サンプルレート（参考表示）
        if self.sample_rate is not None:
            parts.append(
                f'<span style="color:gray">ℹ {self.sample_rate:,} Hz</span>'
            )

        # ピーク音量
        if self.peak_dbfs is not None and not math.isinf(self.peak_dbfs):
            ok = self.peak_dbfs >= PEAK_MIN_DBFS
            icon, color = ("✅", "green") if ok else ("⚠", "darkorange")
            parts.append(
                f'<span style="color:{color}">{icon} peak {self.peak_dbfs:.1f} dBFS</span>'
            )

        # 警告
        for w in self.warnings:
            parts.append(f'<span style="color:darkorange">⚠ {w}</span>')

        return "　　".join(parts) if parts else "（チェック項目なし）"


def check_voice_file(path: str) -> VoiceCheckResult:
    """
    WAV ファイルを解析して VoiceCheckResult を返す。
    path が空文字のときは「未設定」として errors を返す。
    """
    r = VoiceCheckResult()
    if not path:
        r.errors.append("参照音声ファイルが未設定です")
        return r

    p = Path(path)

    # ファイル名チェック
    if not p.name.isascii():
        r.warnings.append(f"非ASCII文字のファイル名 ({p.name}) → 動作しない可能性あり")

    if not p.exists():
        r.errors.append(f"ファイルが見つかりません: {p}")
        return r

    try:
        with wave.open(str(p), "rb") as w:
            ch  = w.getnchannels()
            sr  = w.getframerate()
            nf  = w.getnframes()
            sw  = w.getsampwidth()
            dur = nf / sr if sr > 0 else 0.0

            r.channels     = ch
            r.sample_rate  = sr
            r.duration_sec = round(dur, 2)

            if not (DURATION_MIN_SEC <= dur <= DURATION_MAX_SEC):
                r.warnings.append(
                    f"長さが推奨範囲外 ({dur:.1f}s、推奨 {DURATION_MIN_SEC}〜{DURATION_MAX_SEC}s)"
                )
            if ch > 1:
                r.warnings.append(f"ステレオ ({ch}ch) → モノラル推奨")

            # ピーク音量（16bit PCM のみ計測）
            if sw == 2 and nf > 0:
                frames  = w.readframes(nf)
                count   = nf * ch
                samples = struct.unpack(f"<{count}h", frames)
                peak    = max(abs(s) for s in samples) if samples else 0
                if peak > 0:
                    r.peak_dbfs = round(20 * math.log10(peak / 32768.0), 1)
                else:
                    r.peak_dbfs = -math.inf
                if r.peak_dbfs < PEAK_MIN_DBFS:
                    r.warnings.append(f"音量が小さすぎます (peak {r.peak_dbfs:.1f} dBFS)")
            else:
                # 16bit 以外はスキップ（ビット深度表示のみ）
                r.warnings.append(f"ピーク計測スキップ ({sw*8}bit PCM)")

    except Exception as e:
        r.errors.append(f"WAV 読み込みエラー: {e}")
        return r

    r.ok = len(r.errors) == 0
    return r
