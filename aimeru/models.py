"""
AiMeru Voice Studio - データモデル
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional
import random


# ステータス定数
STATUS_PENDING = "pending"
STATUS_GENERATING = "generating"
STATUS_SUCCESS = "success"
STATUS_HTTP_ERROR = "http_error"
STATUS_SERVER_UNAVAILABLE = "server_unavailable"
STATUS_VOICE_NOT_FOUND = "voice_not_found"
STATUS_FILE_ERROR = "file_error"
STATUS_TOO_SHORT = "too_short"
STATUS_TOO_LONG = "too_long"
STATUS_MANUAL_NG = "manual_ng"
STATUS_SKIPPED = "skipped"

STATUS_LABELS = {
    STATUS_PENDING: "未生成",
    STATUS_GENERATING: "生成中",
    STATUS_SUCCESS: "成功",
    STATUS_HTTP_ERROR: "HTTPエラー",
    STATUS_SERVER_UNAVAILABLE: "サーバー未応答",
    STATUS_VOICE_NOT_FOUND: "voice未発見",
    STATUS_FILE_ERROR: "ファイルエラー",
    STATUS_TOO_SHORT: "短すぎ",
    STATUS_TOO_LONG: "長すぎ",
    STATUS_MANUAL_NG: "手動NG",
    STATUS_SKIPPED: "スキップ",
}

# 文字数警告しきい値
WARN_YELLOW = 80
WARN_ORANGE = 120
WARN_RED = 200

# 生成音声の長さ判定閾値（秒）
TOO_SHORT_THRESHOLD_SEC = 0.3   # これ未満 → too_short
TOO_LONG_THRESHOLD_SEC  = 120.0 # これ超過 → too_long


@dataclass
class SpeakerConfig:
    speaker_id: str
    display_name: str
    voice_id: str
    duration_scale_intent: float = 1.0
    voice_file_path: str = ""   # Reference audio path sent to compatible local API servers.

    @property
    def server_speed(self) -> float:
        """Irodori-TTS-Server に渡す speed (= 1 / duration_scale_intent)"""
        return round(1.0 / self.duration_scale_intent, 6)

    def to_dict(self) -> dict:
        return {
            "display_name": self.display_name,
            "voice_id": self.voice_id,
            "duration_scale_intent": self.duration_scale_intent,
            "server_speed": self.server_speed,
        }


@dataclass
class ScriptItem:
    index: int
    speaker_id: str
    speaker_name: str
    text: str
    voice_id: str
    duration_scale_intent: float
    seed: int
    status: str = STATUS_PENDING
    file: str = ""
    error_detail: str = ""

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def server_speed(self) -> float:
        return round(1.0 / self.duration_scale_intent, 6)

    @property
    def char_warning(self) -> str:
        n = self.char_count
        if n >= WARN_RED:
            return "手動分割推奨"
        if n >= WARN_ORANGE:
            return "品質低下リスク"
        if n >= WARN_YELLOW:
            return "やや長い"
        return ""

    def to_table_dict(self) -> dict:
        return {
            "index": self.index,
            "speaker_id": self.speaker_id,
            "speaker_name": self.speaker_name,
            "text": self.text,
            "char_count": self.char_count,
            "voice_id": self.voice_id,
            "duration_scale_intent": self.duration_scale_intent,
            "server_speed": self.server_speed,
            "status": self.status,
        }

    def to_manifest_dict(self) -> dict:
        return {
            "index": self.index,
            "speaker_id": self.speaker_id,
            "text": self.text,
            "seed": self.seed,
            "file": self.file,
            "status": self.status,
            "char_count": self.char_count,
            "error_detail": self.error_detail,
        }


@dataclass
class ProjectSettings:
    project_name: str = "my_project"
    script_path: str = ""
    output_dir: str = ""
    server_url: str = "http://localhost:8088"
    model: str = "irodori-tts"
    project_seed: int = 123456
    seed_mode: str = "deterministic"   # "deterministic" | "random"
    response_format: str = "wav"
    chunking_enabled: bool = True
    chunk_min_chars: int = 80
    num_steps: int = 40
    cfg_scale_text: float = 3.0
    cfg_scale_speaker: float = 5.0
    mix_pause_ms: int = 400
    create_full_mix: bool = True
    speakers: Dict[str, SpeakerConfig] = field(default_factory=dict)

    def __post_init__(self):
        if not self.speakers:
            self.speakers = {
                "ai": SpeakerConfig(
                    speaker_id="ai",
                    display_name="藍",
                    voice_id="ai",
                    duration_scale_intent=0.95,
                ),
                "meru": SpeakerConfig(
                    speaker_id="meru",
                    display_name="芽瑠",
                    voice_id="meru",
                    duration_scale_intent=0.90,
                ),
            }

    def resolve_seed(self, index: int) -> int:
        if self.seed_mode == "random":
            return random.randint(0, 2**31 - 1)
        return self.project_seed + index
