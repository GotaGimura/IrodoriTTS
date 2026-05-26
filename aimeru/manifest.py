"""
AiMeru Voice Studio - manifest.json / script_table.json の読み書き
"""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List

from .models import ProjectSettings, ScriptItem

JST = timezone(timedelta(hours=9))


# ------------------------------------------------------------------
# script_table.json
# ------------------------------------------------------------------
def save_script_table(items: List[ScriptItem], settings: ProjectSettings, path: Path) -> None:
    data = {
        "project_name": settings.project_name,
        "source_script": settings.script_path,
        "items": [item.to_table_dict() for item in items],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ------------------------------------------------------------------
# manifest.json
# ------------------------------------------------------------------
def save_manifest(
    items: List[ScriptItem],
    settings: ProjectSettings,
    path: Path,
    full_mix_path: str = "",
) -> None:
    speakers_dict = {
        sid: cfg.to_dict()
        for sid, cfg in settings.speakers.items()
    }
    data = {
        "project_name": settings.project_name,
        "created_at": datetime.now(JST).isoformat(timespec="seconds"),
        "irodori_server": {
            "base_url": settings.server_url,
            "model": settings.model,
        },
        "settings": {
            "project_seed": settings.project_seed,
            "seed_mode": settings.seed_mode,
            "response_format": settings.response_format,
            "chunking_enabled": settings.chunking_enabled,
            "chunk_min_chars": settings.chunk_min_chars,
            "num_steps": settings.num_steps,
            "cfg_scale_text": settings.cfg_scale_text,
            "cfg_scale_speaker": settings.cfg_scale_speaker,
            "mix_pause_ms": settings.mix_pause_ms,
        },
        "speakers": speakers_dict,
        "items": [item.to_manifest_dict() for item in items],
        "exports": {
            "full_mix_wav": full_mix_path,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_manifest(path: Path) -> dict | None:
    """manifest.json を読み込んで辞書で返す。失敗時は None。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def restore_statuses_from_manifest(items: List[ScriptItem], manifest: dict) -> None:
    """
    既存 manifest.json から各行のステータス・ファイルパスを復元する。
    プロジェクト再開時に使う。
    """
    index_map = {m["index"]: m for m in manifest.get("items", [])}
    for item in items:
        saved = index_map.get(item.index)
        if saved:
            item.status = saved.get("status", item.status)
            item.file = saved.get("file", item.file)
            item.error_detail = saved.get("error_detail", "")
            item.seed = saved.get("seed", item.seed)
