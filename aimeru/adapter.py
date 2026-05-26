"""
AiMeru Voice Studio - Irodori-TTS-Server HTTP アダプター

アプリ内部の duration_scale_intent を
Irodori-TTS-Server の speed (= 1/duration_scale_intent) に変換して送信する。
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional

import httpx

from .models import ProjectSettings, ScriptItem

logger = logging.getLogger(__name__)

TIMEOUT_HEALTH = 5.0      # /health タイムアウト (秒)
TIMEOUT_SYNTHESIS = 300.0 # TTS 生成タイムアウト (秒) — 長文は時間がかかる


class IrodoriAdapter:
    def __init__(self, settings: ProjectSettings):
        self.settings = settings

    # ------------------------------------------------------------------
    # 接続確認
    # ------------------------------------------------------------------
    def health_check(self) -> tuple[bool, str]:
        """
        GET /health を叩いてサーバー状態を確認する。
        Returns: (ok: bool, message: str)
        """
        url = f"{self.settings.server_url}/health"
        try:
            resp = httpx.get(url, timeout=TIMEOUT_HEALTH)
            if resp.status_code == 200:
                return True, f"接続OK (HTTP {resp.status_code})"
            else:
                return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        except httpx.ConnectError:
            return False, f"接続失敗: {self.settings.server_url} に到達できません"
        except httpx.TimeoutException:
            return False, "タイムアウト"
        except Exception as e:
            return False, f"エラー: {e}"

    # ------------------------------------------------------------------
    # 音声合成
    # ------------------------------------------------------------------
    def synthesize(self, item: ScriptItem, output_path: Path) -> tuple[bool, str]:
        """
        POST /v1/audio/speech で音声を生成し output_path に保存する。
        Returns: (success: bool, error_message: str)
        """
        url = f"{self.settings.server_url}/v1/audio/speech"
        payload = self._build_payload(item)

        logger.debug("POST %s  payload=%s", url, payload)

        try:
            with httpx.stream(
                "POST", url, json=payload, timeout=TIMEOUT_SYNTHESIS
            ) as resp:
                if resp.status_code == 404:
                    # voice が見つからない場合など
                    body = resp.read().decode("utf-8", errors="replace")
                    if "voice" in body.lower():
                        return False, f"voice_not_found: {body[:200]}"
                    return False, f"HTTP 404: {body[:200]}"
                if resp.status_code == 503:
                    body = resp.read().decode("utf-8", errors="replace")
                    return False, f"server_unavailable (503): {body[:200]}"
                if resp.status_code != 200:
                    body = resp.read().decode("utf-8", errors="replace")
                    return False, f"HTTP {resp.status_code}: {body[:200]}"

                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_bytes():
                        f.write(chunk)

        except httpx.ConnectError:
            return False, "server_unavailable: サーバーに接続できません"
        except httpx.TimeoutException:
            return False, "タイムアウト: 生成に時間がかかりすぎました"
        except Exception as e:
            return False, f"例外: {e}"

        # ファイルサイズチェック
        if not output_path.exists() or output_path.stat().st_size == 0:
            return False, "file_error: 保存されたファイルが空です"

        return True, ""

    # ------------------------------------------------------------------
    # ペイロード構築
    # ------------------------------------------------------------------
    def _build_payload(self, item: ScriptItem) -> dict:
        s = self.settings
        return {
            "model": s.model,
            "input": item.text,
            "voice": item.voice_id,
            "response_format": s.response_format,
            "speed": item.server_speed,
            "irodori": {
                "num_steps": s.num_steps,
                "cfg_scale_text": s.cfg_scale_text,
                "cfg_scale_speaker": s.cfg_scale_speaker,
                "seed": item.seed,
                "chunking_enabled": s.chunking_enabled,
                "chunk_min_chars": s.chunk_min_chars,
            },
        }
