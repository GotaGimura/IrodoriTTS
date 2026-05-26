"""
AiMeru Voice Studio - クロスプラットフォーム WAV プレイヤー

macOS  : afplay (OS ネイティブ、追加依存なし、-v で音量制御)
Windows: QMediaPlayer + QAudioOutput (PySide6 内蔵)
Linux  : aplay (ALSA) または QMediaPlayer フォールバック
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from typing import Optional


class AudioPlayer:
    """シンプルな WAV プレイヤー。音量 0.0〜1.0 を統一インターフェースで制御。"""

    def __init__(self):
        self._volume: float = 1.0
        self._current_path: Optional[str] = None
        self._proc: Optional[subprocess.Popen] = None   # macOS / Linux
        self._qt_player = None                          # Windows / fallback
        self._qt_audio  = None

        if sys.platform != "darwin":
            self._init_qt()

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------
    def play(self, path: str) -> bool:
        """再生開始。再生中なら先に停止してから開始。"""
        self.stop()
        self._current_path = path
        if sys.platform == "darwin":
            return self._play_afplay(path)
        elif sys.platform == "win32":
            return self._play_qt(path)
        else:
            # Linux: aplay が使えれば使う、なければ Qt
            if self._which("aplay"):
                return self._play_aplay(path)
            return self._play_qt(path)

    def stop(self):
        """再生停止。"""
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=1)
            except Exception:
                pass
            self._proc = None
        if self._qt_player:
            self._qt_player.stop()
        self._current_path = None

    def is_playing(self) -> bool:
        """再生中かどうかを返す。"""
        if self._proc is not None:
            return self._proc.poll() is None
        if self._qt_player is not None:
            try:
                from PySide6.QtMultimedia import QMediaPlayer
                return self._qt_player.playbackState() == \
                       QMediaPlayer.PlaybackState.PlayingState
            except Exception:
                pass
        return False

    def set_volume(self, volume: float):
        """音量設定（0.0〜1.0）。再生中は即時反映されない（次回 play から反映）。
        Qt backend は即時反映。"""
        self._volume = max(0.0, min(1.0, volume))
        if self._qt_audio is not None:
            self._qt_audio.setVolume(self._volume)

    @property
    def volume(self) -> float:
        return self._volume

    @property
    def current_path(self) -> Optional[str]:
        return self._current_path

    # ------------------------------------------------------------------
    # 内部実装
    # ------------------------------------------------------------------
    def _init_qt(self):
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            self._qt_audio  = QAudioOutput()
            self._qt_player = QMediaPlayer()
            self._qt_player.setAudioOutput(self._qt_audio)
            self._qt_audio.setVolume(self._volume)
        except Exception as e:
            print(f"[AudioPlayer] Qt Multimedia 初期化失敗: {e}")

    def _play_afplay(self, path: str) -> bool:
        """macOS 標準の afplay を使って再生。-v で音量制御。"""
        try:
            self._proc = subprocess.Popen(
                ["afplay", "-v", str(self._volume), path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except FileNotFoundError:
            return False

    def _play_aplay(self, path: str) -> bool:
        """Linux の aplay (ALSA) で再生。"""
        try:
            self._proc = subprocess.Popen(
                ["aplay", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except FileNotFoundError:
            return False

    def _play_qt(self, path: str) -> bool:
        """QMediaPlayer で再生（Windows / Linux fallback）。"""
        if self._qt_player is None:
            return False
        try:
            from PySide6.QtCore import QUrl
            self._qt_player.setSource(QUrl.fromLocalFile(path))
            self._qt_player.play()
            return True
        except Exception:
            return False

    @staticmethod
    def _which(cmd: str) -> bool:
        import shutil
        return shutil.which(cmd) is not None
