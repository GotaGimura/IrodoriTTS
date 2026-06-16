"""
AiMeru Voice Studio - メインウィンドウ

4タブ構成:
  Tab 0: プロジェクト設定
  Tab 1: 話者設定
  Tab 2: 台本プレビュー
  Tab 3: 生成キュー
"""
from __future__ import annotations
import logging
import random
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QGroupBox, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QDoubleSpinBox, QSpinBox,
    QCheckBox, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy, QStatusBar,
)
from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont

from ..models import (
    ProjectSettings, SpeakerConfig, ScriptItem,
    STATUS_PENDING, STATUS_HTTP_ERROR, STATUS_SERVER_UNAVAILABLE,
    STATUS_VOICE_NOT_FOUND, STATUS_FILE_ERROR, STATUS_TOO_SHORT,
    STATUS_TOO_LONG, STATUS_MANUAL_NG, STATUS_SUCCESS, STATUS_SKIPPED,
)
from ..parser import parse_script
from ..adapter import IrodoriAdapter
from ..manifest import save_script_table, save_manifest
from ..mixer import create_full_mix
from .preview_tab import PreviewTab
from .gen_tab import GenTab
from .worker import GenerationWorker, HealthWorker
from ..voice_checker import check_voice_file
from ..reference_audio import (
    is_supported_reference_audio,
    prepare_reference_audio,
)

logger = logging.getLogger(__name__)

APP_TITLE = "AiMeru Voice Studio"
WINDOW_W, WINDOW_H = 1000, 720
DEFAULT_OUTPUT_ROOT = Path.home() / "Downloads"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ReferenceAudioLineEdit(QLineEdit):
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = [url for url in event.mimeData().urls() if url.isLocalFile()]
        if not urls:
            event.ignore()
            return
        self.file_dropped.emit(urls[0].toLocalFile())
        event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(WINDOW_W, WINDOW_H)

        self.settings = ProjectSettings()
        self.items: List[ScriptItem] = []
        self._worker: Optional[GenerationWorker] = None
        self._health_worker: Optional[HealthWorker] = None

        self.setAcceptDrops(True)
        self._setup_ui()
        self._connect_signals()

        # 起動後 0.8s で自動ヘルスチェック
        QTimer.singleShot(800, self._auto_health_check)

    # ==================================================================
    # UI 構築
    # ==================================================================
    def _setup_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_project  = self._build_project_tab()
        self.tab_speaker  = self._build_speaker_tab()
        self.preview_tab  = PreviewTab()
        self.gen_tab      = GenTab()
        self.gen_tab.set_inter_chunk_silence_seconds(self.settings.mix_pause_ms / 1000.0)

        self.tabs.addTab(self.tab_project, "⚙ プロジェクト設定")
        self.tabs.addTab(self.tab_speaker, "🎤 話者設定")
        self.tabs.addTab(self.preview_tab, "📄 台本プレビュー")
        self.tabs.addTab(self.gen_tab,     "▶ 生成キュー")

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("準備完了")

    # ------------------------------------------------------------------
    # Tab 0: プロジェクト設定
    # ------------------------------------------------------------------
    def _build_project_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(12, 12, 12, 12)

        # ---- プロジェクト情報 ------------------------------------------
        grp_proj = QGroupBox("プロジェクト情報")
        form_proj = QFormLayout(grp_proj)
        self.ed_project_name = QLineEdit(self.settings.project_name)
        form_proj.addRow("プロジェクト名:", self.ed_project_name)
        outer.addWidget(grp_proj)

        # ---- ファイルパス ----------------------------------------------
        grp_files = QGroupBox("ファイル・フォルダ")
        form_files = QFormLayout(grp_files)

        # 台本 Markdown
        row_script = QHBoxLayout()
        self.ed_script = QLineEdit()
        self.ed_script.setPlaceholderText("台本 Markdown ファイルを選択、または .md / .markdown をドラッグ&ドロップ")
        btn_script = QPushButton("参照")
        btn_script.clicked.connect(self._browse_script)
        row_script.addWidget(self.ed_script)
        row_script.addWidget(btn_script)
        form_files.addRow("台本 Markdown:", row_script)

        # 出力フォルダ
        row_out = QHBoxLayout()
        self.ed_output = QLineEdit()
        self.ed_output.setPlaceholderText(
            f"未指定時は {DEFAULT_OUTPUT_ROOT / 'chunks'} に保存します"
        )
        btn_out = QPushButton("参照")
        btn_out.clicked.connect(self._browse_output)
        row_out.addWidget(self.ed_output)
        row_out.addWidget(btn_out)
        form_files.addRow("作業用チャンク保存先:", row_out)
        btn_open_out = QPushButton("作業用保存先を開く")
        btn_open_out.clicked.connect(self._open_output_folder)
        form_files.addRow("", btn_open_out)
        self.lbl_default_output = QLabel(
            f"生成中の個別WAVを保存する場所です。未指定時は {DEFAULT_OUTPUT_ROOT / 'chunks'} を使います。"
            "完成音声は「Export Full Mix」から保存先を選びます。"
        )
        self.lbl_default_output.setWordWrap(True)
        self.lbl_default_output.setStyleSheet("color:#666; font-size:11px;")
        form_files.addRow("", self.lbl_default_output)
        outer.addWidget(grp_files)

        # ---- サーバー設定 -----------------------------------------------
        grp_server = QGroupBox("Irodori-TTS-Server")
        form_server = QFormLayout(grp_server)
        self.ed_server_url = QLineEdit(self.settings.server_url)
        btn_health = QPushButton("接続確認")
        btn_health.clicked.connect(self._check_health)
        row_server = QHBoxLayout()
        row_server.addWidget(self.ed_server_url)
        row_server.addWidget(btn_health)
        form_server.addRow("Server URL:", row_server)
        self.lbl_health = QLabel("（未確認）")
        form_server.addRow("", self.lbl_health)
        self.lbl_api_mode = QLabel(f"API Server: {self.settings.server_url} / Mode: 未確認")
        self.lbl_api_mode.setStyleSheet("color:#666; font-size:11px;")
        form_server.addRow("", self.lbl_api_mode)
        outer.addWidget(grp_server)

        # ---- 詳細パラメータ ---------------------------------------------
        grp_adv = QGroupBox("詳細パラメータ（推論）")
        form_adv = QFormLayout(grp_adv)

        self.sp_num_steps = QSpinBox()
        self.sp_num_steps.setRange(1, 200)
        self.sp_num_steps.setValue(self.settings.num_steps)
        form_adv.addRow("num_steps:", self.sp_num_steps)

        self.sp_cfg_text = QDoubleSpinBox()
        self.sp_cfg_text.setRange(0.1, 20.0)
        self.sp_cfg_text.setSingleStep(0.1)
        self.sp_cfg_text.setValue(self.settings.cfg_scale_text)
        form_adv.addRow("cfg_scale_text:", self.sp_cfg_text)

        self.sp_cfg_speaker = QDoubleSpinBox()
        self.sp_cfg_speaker.setRange(0.1, 20.0)
        self.sp_cfg_speaker.setSingleStep(0.1)
        self.sp_cfg_speaker.setValue(self.settings.cfg_scale_speaker)
        form_adv.addRow("cfg_scale_speaker:", self.sp_cfg_speaker)

        self.sp_project_seed = QSpinBox()
        self.sp_project_seed.setRange(0, 2**30)
        self.sp_project_seed.setValue(self.settings.project_seed)
        self.sp_project_seed.setSingleStep(1)
        form_adv.addRow("project_seed:", self.sp_project_seed)

        self.cb_seed_mode = QComboBox()
        self.cb_seed_mode.addItems(["deterministic", "random"])
        form_adv.addRow("seed_mode:", self.cb_seed_mode)

        self.sp_chunk_min = QSpinBox()
        self.sp_chunk_min.setRange(10, 500)
        self.sp_chunk_min.setValue(self.settings.chunk_min_chars)
        form_adv.addRow("chunk_min_chars:", self.sp_chunk_min)

        lbl_silence_note = QLabel(
            "チャンク間の無音は「生成キュー」タブの生成済み音声エリアで調整します。"
        )
        lbl_silence_note.setWordWrap(True)
        lbl_silence_note.setStyleSheet("color:#666; font-size:11px;")
        form_adv.addRow("チャンク間の無音:", lbl_silence_note)

        outer.addWidget(grp_adv)

        # ---- 台本読み込みボタン -----------------------------------------
        btn_load = QPushButton("📂 台本を読み込んでプレビューを更新")
        btn_load.setStyleSheet("font-weight:bold; padding:6px;")
        btn_load.clicked.connect(self._load_script)
        outer.addWidget(btn_load)
        outer.addStretch()

        return w

    # ------------------------------------------------------------------
    # Tab 1: 話者設定
    # ------------------------------------------------------------------
    def _build_speaker_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(12, 12, 12, 12)

        label = QLabel(
            "各話者の voice ID と読み上げ速度補正（duration scale）を設定します。\n"
            "speed は自動計算されます（speed = 1 / duration_scale）。"
        )
        label.setWordWrap(True)
        outer.addWidget(label)

        # ---- 藍 -------------------------------------------------------
        self._ai_widgets   = self._build_speaker_form(outer, "藍 (ai)",   "ai")
        # ---- 芽瑠 -------------------------------------------------------
        self._meru_widgets = self._build_speaker_form(outer, "芽瑠 (meru)", "meru")

        # デフォルト値を設定
        ai   = self.settings.speakers["ai"]
        meru = self.settings.speakers["meru"]
        self._ai_widgets["voice"].setText(ai.voice_id)
        self._ai_widgets["scale"].setValue(ai.duration_scale_intent)
        self._ai_widgets["speed"].setText(f"{ai.server_speed:.4f}")
        self._ai_widgets["voice_file"].setText(ai.voice_file_path)
        self._meru_widgets["voice"].setText(meru.voice_id)
        self._meru_widgets["scale"].setValue(meru.duration_scale_intent)
        self._meru_widgets["speed"].setText(f"{meru.server_speed:.4f}")
        self._meru_widgets["voice_file"].setText(meru.voice_file_path)
        self._update_reference_payload_hint("ai")
        self._update_reference_payload_hint("meru")

        outer.addStretch()
        return w

    def _build_speaker_form(self, parent_layout, title: str, speaker_id: str) -> dict:
        grp = QGroupBox(title)
        form = QFormLayout(grp)

        voice_ed = QLineEdit()
        voice_ed.textChanged.connect(lambda _text: self._update_reference_payload_hint(speaker_id))
        form.addRow("voice ID:", voice_ed)

        scale_sp = QDoubleSpinBox()
        scale_sp.setRange(0.1, 4.0)
        scale_sp.setSingleStep(0.01)
        scale_sp.setDecimals(3)
        scale_sp.setValue(1.0)
        form.addRow("duration scale:", scale_sp)

        speed_lbl = QLineEdit()
        speed_lbl.setReadOnly(True)
        speed_lbl.setStyleSheet("background:#f0f0f0;")
        form.addRow("server speed（自動）:", speed_lbl)

        def _update_speed(v):
            speed_lbl.setText(f"{1.0/v:.4f}" if v > 0 else "—")

        scale_sp.valueChanged.connect(_update_speed)

        # ── 参照音声ファイル ─────────────────────────────────
        row_vf = QHBoxLayout()
        voice_file_ed = ReferenceAudioLineEdit()
        voice_file_ed.setPlaceholderText("参照音声または動画ファイルを選択 / ドロップ…")
        voice_file_ed.textChanged.connect(lambda _text: self._update_reference_payload_hint(speaker_id))
        voice_file_ed.file_dropped.connect(lambda path: self._set_reference_audio_file(speaker_id, path))
        btn_browse_vf = QPushButton("参照")
        btn_browse_vf.setFixedWidth(56)
        btn_browse_vf.clicked.connect(lambda: self._browse_voice_file(speaker_id))
        row_vf.addWidget(voice_file_ed)
        row_vf.addWidget(btn_browse_vf)
        form.addRow("参照音声:", row_vf)

        btn_check_vf = QPushButton("🔍 音声チェック実行")
        btn_check_vf.clicked.connect(lambda: self._run_voice_check(speaker_id))
        form.addRow("", btn_check_vf)

        lbl_check_result = QLabel("（未チェック）")
        lbl_check_result.setWordWrap(True)
        lbl_check_result.setTextFormat(Qt.TextFormat.RichText)
        lbl_check_result.setStyleSheet("color:#888; font-size:11px; padding:2px 0;")
        form.addRow("チェック結果:", lbl_check_result)

        lbl_payload = QLabel("")
        lbl_payload.setWordWrap(True)
        lbl_payload.setStyleSheet("color:#666; font-size:11px; padding:2px 0;")
        form.addRow("payload:", lbl_payload)

        lbl_source = QLabel("")
        lbl_source.setWordWrap(True)
        lbl_source.setStyleSheet("color:#666; font-size:11px; padding:2px 0;")
        form.addRow("source:", lbl_source)

        parent_layout.addWidget(grp)
        return {
            "voice": voice_ed,
            "scale": scale_sp,
            "speed": speed_lbl,
            "voice_file": voice_file_ed,
            "check_result": lbl_check_result,
            "payload": lbl_payload,
            "source": lbl_source,
        }

    # ==================================================================
    # シグナル接続
    # ==================================================================
    def _connect_signals(self):
        self.gen_tab.set_callbacks(
            on_all      = self._generate_all,
            on_selected = self._generate_selected,
            on_failed   = self._generate_failed,
            on_ng       = self._generate_ng,
            on_stop     = self._stop_generation,
            on_remix    = self._remix_only,
            on_open_output = self._open_output_folder,
            on_open_chunks = self._open_chunks_folder,
        )
        # プレビュータブの選択件数を生成タブのボタンにリアルタイム反映
        self.preview_tab.selection_changed.connect(
            lambda indices: self.gen_tab.set_selected_count(len(indices))
        )

    # ==================================================================
    # 設定収集
    # ==================================================================
    def _collect_settings(self):
        s = self.settings
        s.project_name    = self.ed_project_name.text().strip() or "my_project"
        s.script_path     = self.ed_script.text().strip()
        output_dir = self.ed_output.text().strip()
        s.output_dir      = output_dir or str(DEFAULT_OUTPUT_ROOT)
        s.server_url      = self.ed_server_url.text().strip().rstrip("/")
        s.num_steps       = self.sp_num_steps.value()
        s.cfg_scale_text  = self.sp_cfg_text.value()
        s.cfg_scale_speaker = self.sp_cfg_speaker.value()
        s.project_seed    = self.sp_project_seed.value()
        s.seed_mode       = self.cb_seed_mode.currentText()
        s.chunk_min_chars = self.sp_chunk_min.value()
        s.mix_pause_ms    = int(round(self.gen_tab.inter_chunk_silence_seconds * 1000))
        s.create_full_mix = self.gen_tab.create_mix

        # 話者設定
        ai_scale   = self._ai_widgets["scale"].value()
        meru_scale = self._meru_widgets["scale"].value()
        s.speakers["ai"].voice_id               = self._ai_widgets["voice"].text().strip() or "ai"
        s.speakers["ai"].duration_scale_intent  = ai_scale
        s.speakers["ai"].voice_file_path        = self._ai_widgets["voice_file"].text().strip()
        s.speakers["meru"].voice_id             = self._meru_widgets["voice"].text().strip() or "meru"
        s.speakers["meru"].duration_scale_intent = meru_scale
        s.speakers["meru"].voice_file_path      = self._meru_widgets["voice_file"].text().strip()

    # ==================================================================
    # アクション
    # ==================================================================
    def _browse_script(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "台本 Markdown を選択", "", "Markdown (*.md *.markdown);;All files (*)"
        )
        if path:
            self.ed_script.setText(path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = self._markdown_paths_from_drop(event.mimeData())
        if not paths:
            QMessageBox.warning(self, "非対応ファイル", ".md / .markdown ファイルをドロップしてください。")
            return
        if len(paths) > 1:
            QMessageBox.information(self, "複数ファイル", "複数ファイルがドロップされたため、最初の1つだけ読み込みます。")
        if self.items:
            reply = QMessageBox.question(
                self,
                "台本を読み込み直しますか？",
                "現在の台本状態をリセットして、新しいMarkdownを未生成状態で読み込みます。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.ed_script.setText(str(paths[0]))
        self._load_script()
        event.acceptProposedAction()

    @staticmethod
    def _markdown_paths_from_drop(mime_data) -> list[Path]:
        if not mime_data.hasUrls():
            return []
        paths: list[Path] = []
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.suffix.lower() in {".md", ".markdown"}:
                paths.append(path)
        return paths

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "出力フォルダを選択")
        if path:
            self.ed_output.setText(path)

    def _open_folder(self, folder: Path, label: str):
        if not folder.exists() or not folder.is_dir():
            QMessageBox.warning(self, "フォルダが見つかりません", f"{label} が存在しません:\n{folder}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _open_output_folder(self):
        self._collect_settings()
        folder = Path(self.settings.output_dir)
        folder.mkdir(parents=True, exist_ok=True)
        self._open_folder(folder, "出力フォルダ")

    def _open_chunks_folder(self):
        self._collect_settings()
        folder = Path(self.settings.output_dir) / "chunks"
        folder.mkdir(parents=True, exist_ok=True)
        self._open_folder(folder, "chunks フォルダ")

    def _speaker_widgets(self, speaker_id: str) -> dict:
        return self._ai_widgets if speaker_id == "ai" else self._meru_widgets

    def _update_reference_payload_hint(self, speaker_id: str):
        if not hasattr(self, "_ai_widgets") or not hasattr(self, "_meru_widgets"):
            return
        widgets = self._speaker_widgets(speaker_id)
        payload_lbl: QLabel | None = widgets.get("payload")
        if payload_lbl is None:
            return

        voice_id = widgets["voice"].text().strip() or speaker_id
        path = widgets["voice_file"].text().strip()
        if path:
            exists = Path(path).is_file()
            color = "green" if exists else "red"
            exists_text = "true" if exists else "false"
            payload_lbl.setText(
                f'<span style="color:{color}">reference_audio_path = {path}<br>'
                f'exists = {exists_text}</span><br>'
                f'<span style="color:#666">voice = {voice_id} / ref_wav = same path</span>'
            )
        else:
            payload_lbl.setText(
                f'<span style="color:#666">reference_audio_path 未設定。'
                f'生成時は voice={voice_id} のサーバー側fallbackを使用します。</span>'
            )

    def _validate_reference_audio_paths(self) -> bool:
        for speaker_id in ("ai", "meru"):
            widgets = self._speaker_widgets(speaker_id)
            path = widgets["voice_file"].text().strip()
            if path and not Path(path).is_file():
                self.tabs.setCurrentIndex(1)
                QMessageBox.warning(
                    self,
                    "参照音声が見つかりません",
                    f"{speaker_id} の参照音声ファイルが存在しません:\n{path}\n\n"
                    "このまま生成すると別の声へfallbackする可能性があるため、生成を止めました。",
                )
                return False
            if path and Path(path).suffix.lower() != ".wav":
                self._set_reference_audio_file(speaker_id, path)
                converted_path = widgets["voice_file"].text().strip()
                if not converted_path or Path(converted_path).suffix.lower() != ".wav" or not Path(converted_path).is_file():
                    self.tabs.setCurrentIndex(1)
                    return False
        return True

    def _auto_health_check(self):
        """起動直後に非同期でヘルスチェックを実行する（① 自動チェック）。"""
        self._collect_settings()
        self._health_worker = HealthWorker(self.settings, parent=self)
        self._health_worker.result.connect(self._on_health_result)
        self._health_worker.start()

    def _on_health_result(self, ok: bool, msg: str):
        if ok:
            self.lbl_health.setText(f"✅ {msg}")
            self.lbl_health.setStyleSheet("color:green;")
            mode = "resident" if "Resident" in msg else "bridge/fallback"
            self.lbl_api_mode.setText(f"API Server: {self.settings.server_url} / Mode: {mode} / Health: OK")
            self.status_bar.showMessage("サーバー接続OK（自動チェック）")
        else:
            self.lbl_health.setText(f"❌ {msg}")
            self.lbl_health.setStyleSheet("color:red;")
            self.lbl_api_mode.setText(f"API Server: {self.settings.server_url} / Health: NG")
            self.status_bar.showMessage("サーバー未応答（自動チェック）— URL を確認してください")

    def _check_health(self):
        self._collect_settings()
        adapter = IrodoriAdapter(self.settings)
        ok, msg = adapter.health_check()
        if ok:
            self.lbl_health.setText(f"✅ {msg}")
            self.lbl_health.setStyleSheet("color:green;")
            mode = "resident" if "Resident" in msg else "bridge/fallback"
            self.lbl_api_mode.setText(f"API Server: {self.settings.server_url} / Mode: {mode} / Health: OK")
            self.status_bar.showMessage("サーバー接続OK")
        else:
            self.lbl_health.setText(f"❌ {msg}")
            self.lbl_health.setStyleSheet("color:red;")
            self.lbl_api_mode.setText(f"API Server: {self.settings.server_url} / Health: NG")
            self.status_bar.showMessage("サーバー接続失敗")

    # ------------------------------------------------------------------
    # ② 参照音声チェック
    # ------------------------------------------------------------------
    def _browse_voice_file(self, speaker_id: str):
        """話者の参照音声 WAV ファイルをファイルダイアログで選択する。"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "参照音声/動画を選択",
            "",
            "Supported media (*.wav *.mp3 *.m4a *.aac *.flac *.ogg *.opus *.mp4 *.mov *.mkv *.webm);;All files (*)",
        )
        if not path:
            return
        self._set_reference_audio_file(speaker_id, path)

    def _set_reference_audio_file(self, speaker_id: str, path: str):
        source_path = Path(path)
        widgets = self._speaker_widgets(speaker_id)
        if not is_supported_reference_audio(source_path):
            QMessageBox.warning(
                self,
                "非対応ファイル",
                "参照音声として使えるのは .wav/.mp3/.m4a/.aac/.flac/.ogg/.opus/.mp4/.mov/.mkv/.webm です。",
            )
            return
        try:
            prepared = prepare_reference_audio(source_path, speaker_id, PROJECT_ROOT)
        except Exception as exc:
            QMessageBox.warning(self, "参照音声の準備に失敗", str(exc))
            widgets["source"].setText(f'<span style="color:red">{exc}</span>')
            return
        widgets["voice_file"].setText(str(prepared.wav_path))
        if prepared.converted:
            widgets["source"].setText(
                f"元ファイル: {prepared.source_path}<br>"
                f"変換後WAV: {prepared.wav_path}<br>"
                f"format: {prepared.format_label}"
            )
        else:
            widgets["source"].setText(
                f"元ファイル: {prepared.source_path}<br>"
                "format: wav"
            )
        self._run_voice_check(speaker_id)

    def _run_voice_check(self, speaker_id: str):
        """参照音声の品質チェックを実行し、結果を HTML ラベルに反映する。"""
        widgets = self._ai_widgets if speaker_id == "ai" else self._meru_widgets
        path = widgets["voice_file"].text().strip()
        result = check_voice_file(path)
        self._update_reference_payload_hint(speaker_id)
        lbl: QLabel = widgets["check_result"]
        lbl.setText(result.summary_html())
        lbl.setStyleSheet("font-size:11px; padding:2px 0;")

    def _load_script(self):
        self._collect_settings()
        script_path = self.settings.script_path
        if not script_path:
            QMessageBox.warning(self, "エラー", "台本 Markdown ファイルを指定してください。")
            return
        try:
            text = Path(script_path).read_text(encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "読み込みエラー", str(e))
            return

        self.items = parse_script(text, self.settings)
        if not self.items:
            QMessageBox.warning(self, "パース結果なし",
                                "台本から台詞を抽出できませんでした。\n"
                                "フォーマット: 「藍：台詞」または「芽瑠：台詞」")
            return

        self.preview_tab.load_items(self.items)
        self._refresh_generated_audio()
        self.tabs.setCurrentIndex(2)   # プレビュータブへ
        self.status_bar.showMessage(f"{len(self.items)} 行の台詞を読み込みました")

        # script_table.json 保存
        if self.settings.output_dir:
            try:
                save_script_table(
                    self.items, self.settings,
                    Path(self.settings.output_dir) / "script_table.json"
                )
            except Exception as e:
                logger.warning("script_table.json 保存失敗: %s", e)

    # ==================================================================
    # 生成アクション
    # ==================================================================
    def _validate_before_generate(self) -> bool:
        self._collect_settings()
        if not self.items:
            QMessageBox.warning(self, "エラー", "台本を先に読み込んでください。")
            return False
        if not self._validate_reference_audio_paths():
            return False
        return True

    def _generate_all(self):
        if not self._validate_before_generate():
            return
        self._start_worker(self.items)

    def _generate_selected(self):
        if not self._validate_before_generate():
            return
        targets = self.preview_tab.get_selected_items()
        if not targets:
            # 未選択のときはプレビュータブへ自動的に切り替えて案内
            self.tabs.setCurrentIndex(2)
            self.status_bar.showMessage(
                "行を選択してください（クリック or Shift+クリック or Cmd+クリック）"
            )
            return
        self._start_worker(targets)

    def _generate_failed(self):
        if not self._validate_before_generate():
            return
        failed_statuses = {
            STATUS_HTTP_ERROR, STATUS_SERVER_UNAVAILABLE,
            STATUS_VOICE_NOT_FOUND, STATUS_FILE_ERROR,
            STATUS_TOO_SHORT, STATUS_TOO_LONG,
        }
        targets = [it for it in self.items if it.status in failed_statuses]
        if not targets:
            QMessageBox.information(self, "対象なし", "失敗行がありません。")
            return
        self._start_worker(targets)

    def _generate_ng(self):
        if not self._validate_before_generate():
            return
        targets = [it for it in self.items if it.status == STATUS_MANUAL_NG]
        if not targets:
            QMessageBox.information(self, "対象なし", "手動NG 行がありません。")
            return
        self._start_worker(targets)

    def _stop_generation(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self.gen_tab.append_log("⛔ 停止リクエスト送信…")

    def _remix_only(self):
        if not self._validate_before_generate():
            return
        out_dir = Path(self.settings.output_dir)
        success_files = [
            str(out_dir / it.file)
            for it in self.items
            if it.status in (STATUS_SUCCESS, STATUS_SKIPPED)
            and it.file
            and (out_dir / it.file).exists()
            and (out_dir / it.file).stat().st_size > 0
        ]
        if not success_files:
            QMessageBox.warning(self, "エラー", "成功した音声ファイルがありません。")
            return
        self.gen_tab.append_log("🎵 full_mix.wav を再作成中…")
        mix_path = out_dir / "exports" / "full_mix.wav"
        ok, err = create_full_mix(
            success_files, mix_path, pause_ms=self.settings.mix_pause_ms
        )
        if ok:
            self.gen_tab.append_log(f"  ✅ full_mix.wav 生成完了 → {mix_path}")
            self.status_bar.showMessage(f"full_mix.wav 生成完了")
        else:
            self.gen_tab.append_log(f"  ❌ 失敗: {err}")

    # ==================================================================
    # ワーカー起動
    # ==================================================================
    def _start_worker(self, targets: list):
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "生成中", "生成が既に実行中です。停止してから再試行してください。")
            return

        self._collect_settings()
        out_dir = Path(self.settings.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        self.settings.create_full_mix = self.gen_tab.create_mix
        skip = self.gen_tab.skip_existing

        self.gen_tab.clear_log()
        self.gen_tab.reset_progress()
        self.gen_tab.set_generating(True)
        self.tabs.setCurrentIndex(3)
        self.gen_tab.append_log(f"🚀 生成開始: {len(targets)} 行 / skip_existing={skip}")
        self.gen_tab.append_log(f"API URL: {self.settings.server_url}")
        for speaker_id, speaker in self.settings.speakers.items():
            ref_path = speaker.voice_file_path.strip()
            if ref_path:
                exists = Path(ref_path).is_file()
                self.gen_tab.append_log(
                    f"payload {speaker_id}: voice={speaker.voice_id}, "
                    f"reference_audio_path={ref_path}, exists={exists}"
                )
            else:
                self.gen_tab.append_log(
                    f"payload {speaker_id}: voice={speaker.voice_id}, "
                    "reference_audio_path未設定（server fallback）"
                )

        self._worker = GenerationWorker(
            items        = targets,
            settings     = self.settings,
            output_dir   = out_dir,
            all_items    = self.items,
            skip_existing= skip,
            parent       = self,
        )
        self._worker.item_started.connect(self._on_item_started)
        self._worker.item_done.connect(self._on_item_done)
        self._worker.log_message.connect(self.gen_tab.append_log)
        self._worker.progress.connect(self.gen_tab.set_progress)
        self._worker.mix_done.connect(self._on_mix_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    # ==================================================================
    # ワーカーシグナルハンドラ
    # ==================================================================
    def _on_item_started(self, index: int):
        self.preview_tab.update_item_status(index, "generating")

    def _on_item_done(self, index: int, status: str, error: str):
        self.preview_tab.update_item_status(index, status, error)
        self._refresh_generated_audio()

    def _on_mix_done(self, ok: bool, msg: str):
        if ok:
            self.status_bar.showMessage(f"full_mix.wav: {msg}")
        else:
            self.status_bar.showMessage(f"full_mix エラー: {msg}")

    def _on_all_done(self):
        self.gen_tab.set_generating(False)
        success_count = sum(1 for it in self.items if it.status == STATUS_SUCCESS)
        self._refresh_generated_audio()
        self.gen_tab.append_log(f"\n✨ 完了 ({success_count}/{len(self.items)} 成功)")
        self.status_bar.showMessage(f"生成完了: {success_count}/{len(self.items)} 成功")

    def _refresh_generated_audio(self):
        output_dir = Path(self.settings.output_dir) if self.settings.output_dir else None
        self.gen_tab.refresh_generated_audio(self.items, output_dir)
