"""
AiMeru Voice Studio - Markdown 台本パーサー

対応フォーマット:
  インライン形式:  藍：台詞本文
  ブロック形式:   藍：
                  台詞本文（次行以降）

話者名マッピング: 藍 → ai, 芽瑠 → meru
"""
from __future__ import annotations
import re
from typing import List

from .models import ProjectSettings, ScriptItem

# 行頭話者パターン  例: "藍：本文" or "芽瑠：" (コロンはJIS全角・半角どちらも可)
_SPEAKER_RE = re.compile(r'^(藍|芽瑠)\s*[：:]\s*(.*)$')

# 話者名 → speaker_id マッピング (MVP)
_NAME_TO_ID = {
    "藍": "ai",
    "芽瑠": "meru",
}


def parse_script(text: str, settings: ProjectSettings) -> List[ScriptItem]:
    """
    Markdown テキストを ScriptItem のリストに変換する。
    1 非空行 = 1 TTSジョブ が基本単位。
    """
    items: List[ScriptItem] = []
    index = 1
    current_speaker_name: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()

        # 空行・Markdownヘッダーはスキップ
        if not line or line.startswith('#'):
            continue

        m = _SPEAKER_RE.match(line)
        if m:
            speaker_name = m.group(1)
            text_part = m.group(2).strip()
            current_speaker_name = speaker_name

            if text_part:
                # インライン形式: "藍：本文"
                items.append(_make_item(index, speaker_name, text_part, settings))
                index += 1
            # else: ブロック形式の話者行 → 次行待ち
        else:
            # 話者行ではない → 直前の話者に帰属（ブロック形式の台詞行）
            if current_speaker_name:
                items.append(_make_item(index, current_speaker_name, line, settings))
                index += 1
            # current_speaker_name が None なら不明行としてスキップ

    return items


def _make_item(
    index: int,
    speaker_name: str,
    text: str,
    settings: ProjectSettings,
) -> ScriptItem:
    speaker_id = _NAME_TO_ID.get(speaker_name, speaker_name)
    speaker_cfg = settings.speakers.get(speaker_id)

    if speaker_cfg:
        voice_id = speaker_cfg.voice_id
        duration_scale = speaker_cfg.duration_scale_intent
    else:
        voice_id = speaker_id
        duration_scale = 1.0

    seed = settings.resolve_seed(index)

    return ScriptItem(
        index=index,
        speaker_id=speaker_id,
        speaker_name=speaker_name,
        text=text,
        voice_id=voice_id,
        duration_scale_intent=duration_scale,
        seed=seed,
    )
