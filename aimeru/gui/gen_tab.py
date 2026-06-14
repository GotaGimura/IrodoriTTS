"""
AiMeru Voice Studio - 生成キュータブ (Tab 4)

生成の開始・停止・ログ表示・進捗バーを管理する。
"""
from __future__ import annotations
import shutil
import tempfile
import wave
from pathlib import Path
from typing import List, Callable, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QCheckBox, QTextEdit, QProgressBar, QLabel, QGroupBox,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QFileDialog, QMessageBox, QSlider, QDoubleSpinBox,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase, QTextCursor

from ..models import (
    ScriptItem,
    STATUS_PENDING, STATUS_HTTP_ERROR, STATUS_SERVER_UNAVAILABLE,
    STATUS_VOICE_NOT_FOUND, STATUS_FILE_ERROR, STATUS_TOO_SHORT,
    STATUS_TOO_LONG, STATUS_MANUAL_NG,
)


DEFAULT_INTER_CHUNK_SILENCE_SECONDS = 0.5


class GenTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._on_generate_all:      Optional[Callable] = None
        self._on_generate_selected: Optional[Callable] = None
        self._on_generate_failed:   Optional[Callable] = None
        self._on_generate_ng:       Optional[Callable] = None
        self._on_stop:              Optional[Callable] = None
        self._on_remix:             Optional[Callable] = None
        self._on_open_output:       Optional[Callable] = None
        self._on_open_chunks:       Optional[Callable] = None
        self._chunks: list[dict] = []
        self._output_dir: Path | None = None
        self._playing_path: Path | None = None
        self._preview_mix_path: Path | None = None
        self._seeking = False
        self._media_player = None
        self._audio_output = None
        self._setup_ui()
        self._setup_audio_player()

    # ------------------------------------------------------------------
    # UI 構築
    # ------------------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # ---- オプション ------------------------------------------------
        opt_group = QGroupBox("生成オプション")
        opt_layout = QHBoxLayout(opt_group)
        self.chk_skip_existing = QCheckBox("既存ファイルをスキップ")
        self.chk_skip_existing.setChecked(True)
        self.chk_skip_existing.setToolTip("実際のWAVファイルが存在し、サイズが0より大きい場合だけスキップします。")
        self.chk_create_mix = QCheckBox("完了後に full_mix.wav を自動作成（任意）")
        self.chk_create_mix.setChecked(False)
        self.chk_create_mix.setToolTip("通常は下の「Full Mix Preview」または「Export Full Mix」で確認・保存できます。")
        opt_layout.addWidget(self.chk_skip_existing)
        opt_layout.addSpacing(16)
        opt_layout.addWidget(self.chk_create_mix)
        opt_layout.addStretch()
        layout.addWidget(opt_group)

        # ---- ボタン行 -------------------------------------------------
        btn_group = QGroupBox("生成コントロール")
        btn_layout = QHBoxLayout(btn_group)

        self.btn_all      = QPushButton("▶ 全件生成")
        self.btn_selected = QPushButton("▶ 選択行のみ (0)")
        self.btn_failed   = QPushButton("↩ 失敗行を再生成")
        self.btn_ng       = QPushButton("↩ 手動NG を再生成")
        self.btn_stop     = QPushButton("⛔ 停止")
        self.btn_remix    = QPushButton("🎵 full_mix だけ再作成")
        self.btn_open_out = QPushButton("📂 出力フォルダ")
        self.btn_open_chunks = QPushButton("📂 chunks")

        self.btn_all.setStyleSheet("background:#4CAF50; color:white; font-weight:bold;")
        self.btn_stop.setStyleSheet("background:#f44336; color:white; font-weight:bold;")
        self.btn_stop.setEnabled(False)
        self.btn_selected.setToolTip("「台本プレビュー」タブで行を選択してからクリック\nCtrl（Mac: Cmd）+ クリックで複数選択")
        self.btn_open_out.setToolTip("現在の出力フォルダをExplorerで開きます")
        self.btn_open_chunks.setToolTip("生成された個別WAVの chunks フォルダをExplorerで開きます")

        for btn in (self.btn_all, self.btn_selected, self.btn_failed,
                    self.btn_ng, self.btn_stop, self.btn_remix,
                    self.btn_open_out, self.btn_open_chunks):
            btn_layout.addWidget(btn)

        layout.addWidget(btn_group)

        # ---- 選択ヒント ------------------------------------------------
        self.lbl_selection_hint = QLabel("💡 選択行で生成するには：「台本プレビュー」タブで行をクリック選択 → ここで「選択行のみ」")
        self.lbl_selection_hint.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.lbl_selection_hint)

        # ---- 進捗バー -------------------------------------------------
        prog_layout = QHBoxLayout()
        self.lbl_progress = QLabel("待機中")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        prog_layout.addWidget(self.lbl_progress)
        prog_layout.addWidget(self.progress_bar, 1)
        layout.addLayout(prog_layout)

        # ---- 生成済み音声 ------------------------------------------------
        generated_group = QGroupBox("生成済み音声")
        generated_layout = QVBoxLayout(generated_group)

        action_layout = QHBoxLayout()
        self.btn_select_all_chunks = QPushButton("全選択")
        self.btn_clear_chunks = QPushButton("全解除")
        self.btn_preview_mix = QPushButton("Full Mix Preview")
        self.btn_save_checked = QPushButton("Export Full Mix")
        self.btn_open_selected_file = QPushButton("選択ファイルを開く")
        self.lbl_chunk_summary = QLabel("生成済み: 0 件 / 選択: 0 件")
        self.lbl_chunk_summary.setStyleSheet("color:#666; font-size:11px;")
        self.sp_inter_chunk_silence = QDoubleSpinBox()
        self.sp_inter_chunk_silence.setRange(0.0, 3.0)
        self.sp_inter_chunk_silence.setSingleStep(0.1)
        self.sp_inter_chunk_silence.setDecimals(1)
        self.sp_inter_chunk_silence.setValue(DEFAULT_INTER_CHUNK_SILENCE_SECONDS)
        self.sp_inter_chunk_silence.setSuffix(" 秒")
        self.sp_inter_chunk_silence.setToolTip("Full Mix Preview / Export Full Mix / full_mix.wav 作成に使います。個別チャンクには追加しません。")
        action_layout.addWidget(self.btn_select_all_chunks)
        action_layout.addWidget(self.btn_clear_chunks)
        action_layout.addWidget(self.btn_preview_mix)
        action_layout.addWidget(self.btn_save_checked)
        action_layout.addWidget(self.btn_open_selected_file)
        action_layout.addStretch()
        action_layout.addWidget(QLabel("チャンク間の無音:"))
        action_layout.addWidget(self.sp_inter_chunk_silence)
        action_layout.addWidget(self.lbl_chunk_summary)
        generated_layout.addLayout(action_layout)

        self.chunk_table = QTableWidget(0, 7)
        self.chunk_table.setHorizontalHeaderLabels(
            ["選択", "No", "話者", "台詞", "時間", "ファイル", "再生"]
        )
        self.chunk_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.chunk_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.chunk_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.chunk_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.chunk_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.chunk_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.chunk_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.chunk_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.chunk_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.chunk_table.itemChanged.connect(self._update_chunk_summary)
        self.chunk_table.itemSelectionChanged.connect(self._update_chunk_summary)
        generated_layout.addWidget(self.chunk_table)

        play_layout = QHBoxLayout()
        self.lbl_now_playing = QLabel("再生待機中")
        self.lbl_now_playing.setStyleSheet("color:#1976D2; font-size:11px;")
        self.btn_stop_audio = QPushButton("停止")
        self.btn_stop_audio.setEnabled(False)
        self.slider_seek = QSlider(Qt.Orientation.Horizontal)
        self.slider_seek.setRange(0, 0)
        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setFixedWidth(92)
        play_layout.addWidget(self.lbl_now_playing, 1)
        play_layout.addWidget(self.btn_stop_audio)
        play_layout.addWidget(self.slider_seek, 2)
        play_layout.addWidget(self.lbl_time)
        generated_layout.addLayout(play_layout)

        layout.addWidget(generated_group, 1)

        # ---- ログ --------------------------------------------------------
        log_label = QLabel("生成ログ")
        layout.addWidget(log_label)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPointSize(11)
        self.log_view.setFont(mono)
        self.log_view.setStyleSheet("background:#1e1e1e; color:#d4d4d4;")
        layout.addWidget(self.log_view, 1)

        # ボタン接続
        self.btn_all.clicked.connect(lambda: self._on_generate_all and self._on_generate_all())
        self.btn_selected.clicked.connect(lambda: self._on_generate_selected and self._on_generate_selected())
        self.btn_failed.clicked.connect(lambda: self._on_generate_failed and self._on_generate_failed())
        self.btn_ng.clicked.connect(lambda: self._on_generate_ng and self._on_generate_ng())
        self.btn_stop.clicked.connect(self._handle_stop)
        self.btn_remix.clicked.connect(lambda: self._on_remix and self._on_remix())
        self.btn_open_out.clicked.connect(lambda: self._on_open_output and self._on_open_output())
        self.btn_open_chunks.clicked.connect(lambda: self._on_open_chunks and self._on_open_chunks())
        self.btn_select_all_chunks.clicked.connect(self.select_all_chunks)
        self.btn_clear_chunks.clicked.connect(self.clear_chunk_selection)
        self.btn_preview_mix.clicked.connect(self.preview_full_mix)
        self.btn_save_checked.clicked.connect(self.save_checked_chunks)
        self.btn_open_selected_file.clicked.connect(self.open_selected_chunk_file)
        self.btn_stop_audio.clicked.connect(self.stop_audio)
        self.slider_seek.sliderPressed.connect(self._on_seek_pressed)
        self.slider_seek.sliderReleased.connect(self._on_seek_released)

    # ------------------------------------------------------------------
    # 外部から接続するコールバック setter
    # ------------------------------------------------------------------
    def set_callbacks(
        self,
        on_all=None, on_selected=None, on_failed=None,
        on_ng=None, on_stop=None, on_remix=None,
        on_open_output=None, on_open_chunks=None,
    ):
        self._on_generate_all      = on_all
        self._on_generate_selected = on_selected
        self._on_generate_failed   = on_failed
        self._on_generate_ng       = on_ng
        self._on_stop              = on_stop
        self._on_remix             = on_remix
        self._on_open_output       = on_open_output
        self._on_open_chunks       = on_open_chunks

    # ------------------------------------------------------------------
    # 停止ハンドラ（2重送信防止）
    # ------------------------------------------------------------------
    def _handle_stop(self):
        if not self.btn_stop.isEnabled():
            return
        # 即座に無効化して2重クリックを防ぐ
        self.btn_stop.setEnabled(False)
        self.btn_stop.setText("停止中…（現在行完了後に停止）")
        self.btn_stop.setStyleSheet("background:#999; color:white; font-weight:bold;")
        if self._on_stop:
            self._on_stop()

    # ------------------------------------------------------------------
    # 状態制御
    # ------------------------------------------------------------------
    def set_generating(self, generating: bool):
        for btn in (self.btn_all, self.btn_selected, self.btn_failed,
                    self.btn_ng, self.btn_remix):
            btn.setEnabled(not generating)
        if generating:
            self.btn_stop.setEnabled(True)
            self.btn_stop.setText("⛔ 停止")
            self.btn_stop.setStyleSheet("background:#f44336; color:white; font-weight:bold;")
        else:
            self.btn_stop.setEnabled(False)
            self.btn_stop.setText("⛔ 停止")
            self.btn_stop.setStyleSheet("background:#f44336; color:white; font-weight:bold;")

    def set_progress(self, current: int, total: int):
        if total > 0:
            pct = int(current / total * 100)
            self.progress_bar.setValue(pct)
            self.lbl_progress.setText(f"{current} / {total}")
        else:
            self.progress_bar.setValue(0)
            self.lbl_progress.setText("待機中")

    def reset_progress(self):
        self.progress_bar.setValue(0)
        self.lbl_progress.setText("待機中")

    def set_selected_count(self, count: int):
        """プレビュータブからの選択件数を受け取ってボタンラベルを更新"""
        self.btn_selected.setText(f"▶ 選択行のみ ({count})")
        if count > 0:
            self.btn_selected.setStyleSheet("background:#1976D2; color:white; font-weight:bold;")
        else:
            self.btn_selected.setStyleSheet("")

    # ------------------------------------------------------------------
    # ログ
    # ------------------------------------------------------------------
    def append_log(self, text: str):
        self.log_view.append(text)
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def clear_log(self):
        self.log_view.clear()

    # ------------------------------------------------------------------
    # 生成済み音声
    # ------------------------------------------------------------------
    def refresh_generated_audio(self, items: List[ScriptItem], output_dir: Path | None):
        self._output_dir = output_dir
        self._chunks = []
        if output_dir is not None:
            for item in items:
                if not item.file:
                    continue
                path = Path(item.file)
                if not path.is_absolute():
                    path = output_dir / path
                if not path.is_file():
                    continue
                duration = self._wav_duration(path)
                self._chunks.append(
                    {
                        "index": item.index,
                        "speaker": item.speaker_name,
                        "voice": item.voice_id,
                        "text": item.text,
                        "path": path,
                        "duration": duration,
                    }
                )

        self.chunk_table.blockSignals(True)
        self.chunk_table.setRowCount(len(self._chunks))
        for row, chunk in enumerate(self._chunks):
            check_item = QTableWidgetItem("")
            check_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            check_item.setCheckState(Qt.CheckState.Checked)
            self.chunk_table.setItem(row, 0, check_item)
            self.chunk_table.setItem(row, 1, QTableWidgetItem(f"{chunk['index']:03d}"))
            self.chunk_table.setItem(row, 2, QTableWidgetItem(f"{chunk['speaker']} / {chunk['voice']}"))
            text = str(chunk["text"])
            self.chunk_table.setItem(row, 3, QTableWidgetItem(text[:80] + ("..." if len(text) > 80 else "")))
            self.chunk_table.setItem(row, 4, QTableWidgetItem(self._format_seconds(chunk["duration"])))
            self.chunk_table.setItem(row, 5, QTableWidgetItem(chunk["path"].name))
            play_btn = QPushButton("再生")
            play_btn.clicked.connect(lambda _checked=False, r=row: self.play_chunk(r))
            self.chunk_table.setCellWidget(row, 6, play_btn)
        self.chunk_table.blockSignals(False)
        self._update_chunk_summary()

    def select_all_chunks(self):
        self._set_all_checked(Qt.CheckState.Checked)

    def clear_chunk_selection(self):
        self._set_all_checked(Qt.CheckState.Unchecked)

    def _set_all_checked(self, state: Qt.CheckState):
        self.chunk_table.blockSignals(True)
        for row in range(self.chunk_table.rowCount()):
            item = self.chunk_table.item(row, 0)
            if item is not None:
                item.setCheckState(state)
        self.chunk_table.blockSignals(False)
        self._update_chunk_summary()

    def checked_chunks(self) -> list[dict]:
        chunks: list[dict] = []
        for row, chunk in enumerate(self._chunks):
            item = self.chunk_table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                chunks.append(chunk)
        return chunks

    def play_chunk(self, row: int):
        if row < 0 or row >= len(self._chunks):
            return
        chunk = self._chunks[row]
        path: Path = chunk["path"]
        self.play_audio_file(path)
        self.lbl_now_playing.setText(f"再生中: {path.name}")

    def play_audio_file(self, path: Path):
        if not path.is_file():
            QMessageBox.warning(self, "ファイルが見つかりません", f"WAVファイルが存在しません:\n{path}")
            return
        if self._media_player is None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            return
        self.stop_audio()
        self._playing_path = path
        self._media_player.setSource(QUrl.fromLocalFile(str(path)))
        self._media_player.play()
        self.btn_stop_audio.setEnabled(True)

    def stop_audio(self):
        if self._media_player is not None:
            self._media_player.stop()
        self._playing_path = None
        self.btn_stop_audio.setEnabled(False)
        self.lbl_now_playing.setText("再生待機中")

    def _cleanup_preview_mix(self):
        if self._preview_mix_path and self._preview_mix_path.exists():
            try:
                self._preview_mix_path.unlink()
            except OSError:
                pass
        self._preview_mix_path = None

    def save_checked_chunks(self):
        chunks = self.checked_chunks()
        if not chunks:
            QMessageBox.warning(self, "選択なし", "連結する音声をチェックしてください。")
            return
        default_dir = self._output_dir or Path.home()
        default_name = default_dir / "aimeru_merged.wav"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Full Mix",
            str(default_name),
            "WAV (*.wav)",
        )
        if not save_path:
            return
        try:
            self._merge_wav_files(
                [chunk["path"] for chunk in chunks],
                Path(save_path),
                silence_seconds=self.inter_chunk_silence_seconds,
            )
        except Exception as exc:
            QMessageBox.critical(self, "保存失敗", str(exc))
            return
        QMessageBox.information(self, "保存完了", f"連結WAVを保存しました:\n{save_path}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(save_path).parent)))

    def preview_full_mix(self):
        chunks = self.checked_chunks()
        if not chunks:
            QMessageBox.warning(self, "選択なし", "プレビューする音声をチェックしてください。")
            return
        try:
            self.stop_audio()
            self._cleanup_preview_mix()
            with tempfile.NamedTemporaryFile(prefix="aimeru_full_mix_preview_", suffix=".wav", delete=False) as tmp:
                preview_path = Path(tmp.name)
            self._merge_wav_files(
                [chunk["path"] for chunk in chunks],
                preview_path,
                silence_seconds=self.inter_chunk_silence_seconds,
            )
            self.play_audio_file(preview_path)
            self._preview_mix_path = preview_path
            self.lbl_now_playing.setText(f"Full Mix Preview: {preview_path.name}")
        except Exception as exc:
            QMessageBox.critical(self, "Preview失敗", str(exc))

    def open_selected_chunk_file(self):
        row = self.chunk_table.currentRow()
        if row < 0 or row >= len(self._chunks):
            QMessageBox.information(self, "選択なし", "開く音声行を選択してください。")
            return
        path: Path = self._chunks[row]["path"]
        if not path.is_file():
            QMessageBox.warning(self, "ファイルが見つかりません", f"WAVファイルが存在しません:\n{path}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _setup_audio_player(self):
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

            self._audio_output = QAudioOutput(self)
            self._media_player = QMediaPlayer(self)
            self._media_player.setAudioOutput(self._audio_output)
            self._audio_output.setVolume(1.0)
            self._media_player.positionChanged.connect(self._on_player_position)
            self._media_player.durationChanged.connect(self._on_player_duration)
            self._media_player.playbackStateChanged.connect(self._on_player_state)
        except Exception as exc:
            self._media_player = None
            self._audio_output = None
            self.lbl_now_playing.setText(f"Qt再生を初期化できません: {exc}")

    def _on_player_position(self, position_ms: int):
        if not self._seeking:
            self.slider_seek.setValue(position_ms)
        self.lbl_time.setText(
            f"{self._format_ms(position_ms)} / {self._format_ms(self.slider_seek.maximum())}"
        )

    def _on_player_duration(self, duration_ms: int):
        self.slider_seek.setRange(0, max(0, duration_ms))
        self.lbl_time.setText(f"00:00 / {self._format_ms(duration_ms)}")

    def _on_player_state(self, _state):
        try:
            from PySide6.QtMultimedia import QMediaPlayer
            if _state == QMediaPlayer.PlaybackState.PlayingState:
                return
        except Exception:
            return
        self.btn_stop_audio.setEnabled(False)

    def _on_seek_pressed(self):
        self._seeking = True

    def _on_seek_released(self):
        self._seeking = False
        if self._media_player is not None:
            self._media_player.setPosition(self.slider_seek.value())

    def _update_chunk_summary(self, *_args):
        selected = len(self.checked_chunks())
        total = len(self._chunks)
        self.lbl_chunk_summary.setText(f"生成済み: {total} 件 / 選択: {selected} 件")

    @staticmethod
    def _wav_duration(path: Path) -> float | None:
        try:
            with wave.open(str(path), "rb") as reader:
                rate = reader.getframerate()
                return reader.getnframes() / rate if rate else None
        except Exception:
            return None

    @staticmethod
    def _format_seconds(seconds: float | None) -> str:
        if seconds is None:
            return "--:--"
        return GenTab._format_ms(int(seconds * 1000))

    @staticmethod
    def _format_ms(ms: int) -> str:
        total_seconds = max(0, int(ms / 1000))
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _merge_wav_files(
        paths: list[Path],
        output_path: Path,
        silence_seconds: float = DEFAULT_INTER_CHUNK_SILENCE_SECONDS,
    ):
        if not paths:
            raise ValueError("連結対象のWAVがありません。")
        for path in paths:
            if not path.is_file():
                raise FileNotFoundError(f"WAVファイルが見つかりません: {path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(paths[0]), "rb") as first:
            params = first.getparams()
            format_key = (
                params.nchannels,
                params.sampwidth,
                params.framerate,
                params.comptype,
                params.compname,
            )
            frames = [first.readframes(first.getnframes())]
        silence_frames = max(0, int(round(params.framerate * silence_seconds)))
        silence_bytes = b"\x00" * silence_frames * params.nchannels * params.sampwidth
        for path in paths[1:]:
            with wave.open(str(path), "rb") as reader:
                reader_params = reader.getparams()
                reader_key = (
                    reader_params.nchannels,
                    reader_params.sampwidth,
                    reader_params.framerate,
                    reader_params.comptype,
                    reader_params.compname,
                )
                if reader_key != format_key:
                    raise ValueError(
                        "WAV形式が一致しないため連結できません: "
                        f"{path.name} {reader_key} != {format_key}"
                    )
                frames.append(reader.readframes(reader.getnframes()))
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        try:
            with wave.open(str(tmp_path), "wb") as writer:
                writer.setnchannels(params.nchannels)
                writer.setsampwidth(params.sampwidth)
                writer.setframerate(params.framerate)
                writer.setcomptype(params.comptype, params.compname)
                for idx, frame_data in enumerate(frames):
                    writer.writeframes(frame_data)
                    if silence_bytes and idx < len(frames) - 1:
                        writer.writeframes(silence_bytes)
            shutil.move(str(tmp_path), str(output_path))
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # プロパティ
    # ------------------------------------------------------------------
    @property
    def skip_existing(self) -> bool:
        return self.chk_skip_existing.isChecked()

    @property
    def create_mix(self) -> bool:
        return self.chk_create_mix.isChecked()

    @property
    def inter_chunk_silence_seconds(self) -> float:
        return float(self.sp_inter_chunk_silence.value())

    def set_inter_chunk_silence_seconds(self, seconds: float):
        self.sp_inter_chunk_silence.setValue(max(0.0, min(3.0, float(seconds))))
