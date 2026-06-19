"""
AiMeru Voice Studio - 台本プレビュータブ (Tab 3)

ScriptItem のリストをテーブル表示し、文字数警告とステータスを色分けする。
音声の確認は「生成キュー」の生成済み音声エリアに集約する。
"""
from __future__ import annotations
from typing import List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QPushButton, QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

from ..models import (
    ScriptItem,
    STATUS_SUCCESS, STATUS_GENERATING, STATUS_MANUAL_NG, STATUS_SKIPPED,
    STATUS_PENDING,
    STATUS_LABELS,
    WARN_YELLOW, WARN_ORANGE, WARN_RED,
)

# 列インデックス
COL_NO       = 0
COL_SPEAKER  = 1
COL_CHARS    = 2
COL_TEXT     = 3
COL_WARNING  = 4
COL_STATUS   = 5
COLUMNS = ["No", "話者", "文字数", "台詞", "警告", "状態"]

# 色定数
COLOR_WARN_YELLOW  = QColor("#FFF8DC")
COLOR_WARN_ORANGE  = QColor("#FFE4B5")
COLOR_WARN_RED     = QColor("#FFD0D0")
COLOR_SUCCESS      = QColor("#D4EDDA")
COLOR_GENERATING   = QColor("#CCE5FF")
COLOR_ERROR        = QColor("#F8D7DA")
COLOR_MANUAL_NG    = QColor("#E2D9F3")
COLOR_SKIPPED      = QColor("#E9ECEF")


class PreviewTab(QWidget):
    selection_changed = Signal(list)   # 選択された index リスト

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[ScriptItem] = []

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI 構築
    # ------------------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # ヒント行
        hint = QLabel(
            "🖱 クリックで1行選択　／　Shift+クリックで範囲選択　／　"
            "Cmd（Ctrl）+クリックで複数選択　／　音声再生は「生成キュー」の生成済み音声で行います"
        )
        hint.setStyleSheet("color: #555; font-size: 11px; padding: 2px 0;")
        layout.addWidget(hint)

        # 凡例 + 選択件数
        legend_layout = QHBoxLayout()
        for label, color in [
            ("やや長い (80+)",   COLOR_WARN_YELLOW),
            ("品質低下 (120+)",  COLOR_WARN_ORANGE),
            ("要分割 (200+)",    COLOR_WARN_RED),
            ("成功",             COLOR_SUCCESS),
            ("生成中",           COLOR_GENERATING),
            ("エラー",           COLOR_ERROR),
        ]:
            legend_layout.addWidget(self._make_legend(label, color))
        legend_layout.addStretch()
        self.lbl_selected = QLabel("選択: 0 行")
        self.lbl_selected.setStyleSheet("color:#aaa;")
        legend_layout.addWidget(self.lbl_selected)
        layout.addLayout(legend_layout)

        # テーブル
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.horizontalHeader().setSectionResizeMode(COL_TEXT,    QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_NO,      QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(COL_SPEAKER, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(COL_CHARS,   QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(COL_WARNING, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(COL_STATUS,  QHeaderView.ResizeMode.ResizeToContents)
        self.table.setFont(QFont("", 11))
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

        # ── 下部ボタン行 ────────────────────────────────────
        btn_layout = QHBoxLayout()
        self.btn_toggle_ng = QPushButton("選択行を 手動NG / 解除")
        self.btn_toggle_ng.clicked.connect(self._toggle_manual_ng)
        btn_layout.addWidget(self.btn_toggle_ng)
        btn_layout.addStretch()
        self.lbl_count = QLabel("0 行")
        btn_layout.addWidget(self.lbl_count)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # データ読み込み
    # ------------------------------------------------------------------
    def load_items(self, items: List[ScriptItem]):
        self._items = items
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            self._set_row(row, item)
        self.lbl_count.setText(f"{len(items)} 行")

    def update_item_status(self, index: int, status: str, error_detail: str = ""):
        for row, item in enumerate(self._items):
            if item.index == index:
                item.status = status
                item.error_detail = error_detail
                self._set_row(row, item)
                break

    def _on_double_click(self, item: QTableWidgetItem):
        main_win = self.window()
        if hasattr(main_win, "statusBar"):
            main_win.statusBar().showMessage(
                "音声再生は「生成キュー」タブの生成済み音声エリアで行ってください。"
            )

    # ------------------------------------------------------------------
    # 内部ヘルパー
    # ------------------------------------------------------------------
    def _set_row(self, row: int, item: ScriptItem):
        def cell(text: str) -> QTableWidgetItem:
            wi = QTableWidgetItem(text)
            wi.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            return wi

        self.table.setItem(row, COL_NO,      cell(f"{item.index:03d}"))
        self.table.setItem(row, COL_SPEAKER, cell(item.speaker_name))
        self.table.setItem(row, COL_CHARS,   cell(str(item.char_count)))
        self.table.setItem(row, COL_TEXT,    cell(item.text))
        self.table.setItem(row, COL_WARNING, cell(item.char_warning))
        self.table.setItem(row, COL_STATUS,  cell(STATUS_LABELS.get(item.status, item.status)))

        bg = self._row_color(item)
        for col in range(len(COLUMNS)):
            wi = self.table.item(row, col)
            if wi:
                wi.setBackground(bg)

    def _row_color(self, item: ScriptItem) -> QColor:
        if item.status == STATUS_SUCCESS:   return COLOR_SUCCESS
        if item.status == STATUS_GENERATING: return COLOR_GENERATING
        if item.status == STATUS_MANUAL_NG:  return COLOR_MANUAL_NG
        if item.status == STATUS_SKIPPED:    return COLOR_SKIPPED
        if item.status not in (STATUS_PENDING, STATUS_GENERATING, STATUS_SUCCESS,
                                STATUS_SKIPPED, STATUS_MANUAL_NG):
            return COLOR_ERROR
        n = item.char_count
        if n >= WARN_RED:    return COLOR_WARN_RED
        if n >= WARN_ORANGE: return COLOR_WARN_ORANGE
        if n >= WARN_YELLOW: return COLOR_WARN_YELLOW
        return QColor("white")

    def _make_legend(self, label: str, color: QColor) -> QLabel:
        lbl = QLabel(f"  {label}  ")
        lbl.setAutoFillBackground(True)
        p = lbl.palette()
        p.setColor(lbl.backgroundRole(), color)
        lbl.setPalette(p)
        return lbl

    def _on_selection_changed(self):
        selected_rows = set(r.row() for r in self.table.selectedIndexes())
        selected_indices = [self._items[r].index for r in sorted(selected_rows)]
        n = len(selected_rows)
        self.lbl_selected.setText(f"選択: {n} 行" if n else "選択: 0 行")
        self.lbl_selected.setStyleSheet(
            "color:#1976D2; font-weight:bold;" if n else "color:#aaa;"
        )
        self.selection_changed.emit(selected_indices)

    def _toggle_manual_ng(self):
        rows = set(r.row() for r in self.table.selectedIndexes())
        for row in rows:
            item = self._items[row]
            item.status = STATUS_PENDING if item.status == STATUS_MANUAL_NG else STATUS_MANUAL_NG
            self._set_row(row, item)

    def get_selected_items(self) -> List[ScriptItem]:
        rows = set(r.row() for r in self.table.selectedIndexes())
        return [self._items[r] for r in sorted(rows)]
