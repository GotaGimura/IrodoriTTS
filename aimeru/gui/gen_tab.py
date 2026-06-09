"""
AiMeru Voice Studio - 生成キュータブ (Tab 4)

生成の開始・停止・ログ表示・進捗バーを管理する。
"""
from __future__ import annotations
from typing import List, Callable, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QCheckBox, QTextEdit, QProgressBar, QLabel, QGroupBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QTextCursor

from ..models import (
    ScriptItem,
    STATUS_PENDING, STATUS_HTTP_ERROR, STATUS_SERVER_UNAVAILABLE,
    STATUS_VOICE_NOT_FOUND, STATUS_FILE_ERROR, STATUS_TOO_SHORT,
    STATUS_TOO_LONG, STATUS_MANUAL_NG,
)


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
        self._setup_ui()

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
        self.chk_create_mix = QCheckBox("完了後に full_mix.wav を作成")
        self.chk_create_mix.setChecked(True)
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
    # プロパティ
    # ------------------------------------------------------------------
    @property
    def skip_existing(self) -> bool:
        return self.chk_skip_existing.isChecked()

    @property
    def create_mix(self) -> bool:
        return self.chk_create_mix.isChecked()
