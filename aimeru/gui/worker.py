"""
AiMeru Voice Studio - 生成ワーカー (QThread)

GUI をブロックせずに TTS 生成をバックグラウンドで実行する。
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List

from PySide6.QtCore import QThread, Signal

from ..models import (
    ProjectSettings, ScriptItem,
    STATUS_GENERATING, STATUS_SUCCESS, STATUS_SKIPPED,
    STATUS_HTTP_ERROR, STATUS_SERVER_UNAVAILABLE, STATUS_VOICE_NOT_FOUND,
    STATUS_FILE_ERROR, STATUS_TOO_SHORT, STATUS_TOO_LONG,
    TOO_SHORT_THRESHOLD_SEC, TOO_LONG_THRESHOLD_SEC,
)
from ..adapter import IrodoriAdapter
from ..manifest import load_manifest, save_manifest, script_id_from_path
from ..mixer import create_full_mix, get_wav_duration_seconds

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# 起動時ヘルスチェック用ワーカー (①)
# ──────────────────────────────────────────────────────────────────────
class HealthWorker(QThread):
    """非同期で /health を叩き、結果をシグナルで返す。"""
    result = Signal(bool, str)   # ok, message

    def __init__(self, settings: ProjectSettings, parent=None):
        super().__init__(parent)
        self.settings = settings

    def run(self):
        adapter = IrodoriAdapter(self.settings)
        ok, msg = adapter.health_check()
        self.result.emit(ok, msg)


# ──────────────────────────────────────────────────────────────────────
# 音声生成ワーカー
# ──────────────────────────────────────────────────────────────────────
class GenerationWorker(QThread):
    item_started  = Signal(int)
    item_done     = Signal(int, str, str)   # index, status, error_detail
    log_message   = Signal(str)
    mix_started   = Signal()
    mix_done      = Signal(bool, str)
    progress      = Signal(int, int)
    all_done      = Signal()

    def __init__(
        self,
        items: List[ScriptItem],
        settings: ProjectSettings,
        output_dir: Path,
        all_items: List[ScriptItem],
        skip_existing: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.items        = items
        self.settings     = settings
        self.output_dir   = output_dir
        self.all_items    = all_items
        self.skip_existing = skip_existing
        self._stop_flag   = False
        self._manifest = load_manifest(self.output_dir / "manifest.json") or {}
        self._manifest_items = {
            int(row.get("index")): row
            for row in self._manifest.get("items", [])
            if row.get("index") is not None
        }

    def stop(self):
        self._stop_flag = True

    # ------------------------------------------------------------------
    def run(self):
        adapter = IrodoriAdapter(self.settings)
        total   = len(self.items)

        for i, item in enumerate(self.items):
            if self._stop_flag:
                self.log_message.emit("⛔ 停止しました")
                break

            self.progress.emit(i + 1, total)
            self.item_started.emit(item.index)
            item.status = STATUS_GENERATING

            # ファイルパス決定
            fname     = f"{item.index:03d}_{item.voice_id}.wav"
            file_path = self.output_dir / "chunks" / fname
            item.file = str(
                file_path.relative_to(self.output_dir)
                if file_path.is_relative_to(self.output_dir)
                else file_path
            )

            # スキップ判定
            if self._can_skip_existing(item, file_path):
                item.status = STATUS_SKIPPED
                self.log_message.emit(f"  ⏭ [{item.index:03d}] スキップ（manifest一致）")
                self.item_done.emit(item.index, STATUS_SKIPPED, "")
                self._save_manifest()
                continue

            self.log_message.emit(
                f"  🎙 [{item.index:03d}] {item.speaker_name}："
                f"{item.text[:30]}{'…' if len(item.text) > 30 else ''}"
            )
            speaker = self.settings.speakers.get(item.speaker_id)
            if speaker and speaker.voice_file_path.strip():
                self.log_message.emit(
                    f"    payload voice={item.voice_id} "
                    f"reference_audio_path={speaker.voice_file_path.strip()}"
                )
            else:
                self.log_message.emit(
                    f"    payload voice={item.voice_id} reference_audio_path未設定（server fallback）"
                )

            ok, err = adapter.synthesize(item, file_path)

            if ok:
                # ─── ③ 生成音声の長さ検証 ───────────────────────────
                dur = get_wav_duration_seconds(str(file_path))
                if dur is None:
                    # duration 取得失敗 → 成功扱い（ファイルは存在する）
                    item.status = STATUS_SUCCESS
                    item.error_detail = ""
                    self.log_message.emit(f"    ✅ 成功 → {file_path.name}")
                elif dur < TOO_SHORT_THRESHOLD_SEC:
                    item.status = STATUS_TOO_SHORT
                    item.error_detail = f"生成音声が短すぎます ({dur:.2f}s < {TOO_SHORT_THRESHOLD_SEC}s)"
                    self.log_message.emit(
                        f"    ⚠ too_short ({dur:.2f}s) → {file_path.name}"
                    )
                elif dur > TOO_LONG_THRESHOLD_SEC:
                    item.status = STATUS_TOO_LONG
                    item.error_detail = f"生成音声が長すぎます ({dur:.1f}s > {TOO_LONG_THRESHOLD_SEC}s)"
                    self.log_message.emit(
                        f"    ⚠ too_long ({dur:.1f}s) → {file_path.name}"
                    )
                else:
                    item.status = STATUS_SUCCESS
                    item.error_detail = ""
                    self.log_message.emit(
                        f"    ✅ 成功 ({dur:.1f}s) → {file_path.name}"
                    )
            else:
                item.error_detail = err
                if "voice_not_found" in err:
                    item.status = STATUS_VOICE_NOT_FOUND
                elif "server_unavailable" in err or "503" in err:
                    item.status = STATUS_SERVER_UNAVAILABLE
                elif "file_error" in err:
                    item.status = STATUS_FILE_ERROR
                else:
                    item.status = STATUS_HTTP_ERROR
                self.log_message.emit(f"    ❌ 失敗: {err[:80]}")

            self.item_done.emit(item.index, item.status, item.error_detail)
            self._save_manifest()

        # ── full_mix 生成 ─────────────────────────────────────────────
        if not self._stop_flag and self.settings.create_full_mix:
            success_files = [
                str(self.output_dir / it.file)
                for it in self.all_items
                if it.status in (STATUS_SUCCESS, STATUS_SKIPPED)
                and it.file
                and (self.output_dir / it.file).exists()
                and (self.output_dir / it.file).stat().st_size > 0
            ]
            if success_files:
                self.mix_started.emit()
                self.log_message.emit("🎵 full_mix.wav を生成中…")
                mix_path = self.output_dir / "exports" / "full_mix.wav"
                ok, err  = create_full_mix(
                    success_files, mix_path,
                    pause_ms=self.settings.mix_pause_ms,
                )
                if ok:
                    self.log_message.emit(f"  ✅ full_mix.wav → {mix_path}")
                    self.mix_done.emit(True, str(mix_path))
                else:
                    self.log_message.emit(f"  ❌ full_mix 失敗: {err}")
                    self.mix_done.emit(False, err)
                self._save_manifest(full_mix=str(mix_path) if ok else "")

        self.all_done.emit()

    def _can_skip_existing(self, item: ScriptItem, file_path: Path) -> bool:
        if not self.skip_existing:
            return False
        try:
            file_size = file_path.stat().st_size
        except OSError:
            return False
        if file_size <= 0:
            return False

        expected_script_id = script_id_from_path(self.settings.script_path)
        if self._manifest.get("source_script_id") != expected_script_id:
            return False

        saved = self._manifest_items.get(item.index)
        if not saved:
            return False
        if saved.get("status") not in (STATUS_SUCCESS, STATUS_SKIPPED):
            return False
        if saved.get("voice_id") != item.voice_id:
            return False
        if saved.get("text_hash") != item.text_hash:
            return False

        saved_file = saved.get("file") or saved.get("wav_path")
        if saved_file != item.file:
            return False
        if int(saved.get("file_size") or 0) != file_size:
            return False
        return True

    # ------------------------------------------------------------------
    def _save_manifest(self, full_mix: str = ""):
        """
        ⑤ full_mix パス保持:
        引数が空のとき、既存ファイルが outputs/exports/full_mix.wav に
        あればそのパスを自動で引き継ぐ。
        """
        if not full_mix:
            candidate = self.output_dir / "exports" / "full_mix.wav"
            if candidate.exists():
                full_mix = str(candidate)

        try:
            manifest_path = self.output_dir / "manifest.json"
            save_manifest(
                self.all_items,
                self.settings,
                manifest_path,
                full_mix_path=full_mix,
            )
        except Exception as e:
            logger.warning("manifest 保存失敗: %s", e)
