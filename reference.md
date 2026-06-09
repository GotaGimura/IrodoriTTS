# Reference Audio Guide

## 1. Purpose

This document defines how AiMeru Voice Studio handles speaker IDs, reference audio files, and the payload sent to the local Irodori-TTS resident API.

Keep startup and overall architecture notes in `README.md`. Keep speaker, reference audio, payload, and Git safety rules here.

## 2. Current Speaker Mapping

| Speaker ID | Display Name | Reference Audio Path | Fallback Path | Notes |
| --- | --- | --- | --- | --- |
| `ai` | Ai | `G:\マイドライブ\YouTube\VoiceRef\Ai.wav` | `D:\LocalAI\AiMeruVoice\IrodoriTTS\voice_samples\ai.wav` | Main Ai voice |
| `meru` | Meru | `G:\マイドライブ\YouTube\VoiceRef\Meru.wav` | `D:\LocalAI\AiMeruVoice\IrodoriTTS\voice_samples\meru.wav` | Main Meru voice |

The GUI should show whether the selected reference audio path exists. If a path is explicitly set but missing, generation should stop before sending the request.

## 3. Payload Format

AiMeru sends the selected reference audio path to compatible local API servers as both `reference_audio_path` and `ref_wav`.

```json
{
  "model": "irodori-v3",
  "input": "こんにちは、メルです。",
  "voice": "meru",
  "response_format": "wav",
  "speed": 1.0,
  "reference_audio_path": "G:\\マイドライブ\\YouTube\\VoiceRef\\Meru.wav",
  "ref_wav": "G:\\マイドライブ\\YouTube\\VoiceRef\\Meru.wav",
  "irodori": {
    "seed": 123463,
    "num_steps": 16,
    "cfg_scale_text": 3.0,
    "cfg_scale_speaker": 5.0
  }
}
```

`ref_wav` is kept as a compatibility alias. New code should prefer `reference_audio_path`.

## 4. Resident API Resolution Order

The resident API resolves reference audio in this order:

1. Payload `reference_audio_path` or `ref_wav`.
2. Environment variable `IRODORI_VOICE_<VOICE>_WAV`.
3. Environment variable `AIMERU_VOICE_SAMPLES_DIR`.
4. Default fallback `D:\LocalAI\AiMeruVoice\IrodoriTTS\voice_samples\<voice>.wav`.

If the payload explicitly provides a reference path and that file does not exist, the server returns `reference_audio_not_found`. It must not silently fall back to a different voice.

## 5. File Placement Rules

- Source reference audio lives in `G:\マイドライブ\YouTube\VoiceRef`.
- Local fallback copies live in `D:\LocalAI\AiMeruVoice\IrodoriTTS\voice_samples`.
- `voice_samples/*.wav`, `voice_samples/*.mp3`, and `voice_samples/*.m4a` must not be committed.
- The only tracked file under `voice_samples` should be `voice_samples/.gitkeep`.
- Generated files under `outputs/` must not be committed.

## 6. Quality Checklist

Use short, clean reference clips:

- About 5 to 15 seconds is usually easy to manage.
- One speaker only.
- No BGM.
- Low noise.
- Clear voice and stable volume.
- WAV format is preferred.
- Avoid long silence at the beginning or end.
- Match the intended character tone as closely as possible.

## 7. Troubleshooting

### Meru sounds wrong

Check:

- GUI `reference_audio_path` is `G:\マイドライブ\YouTube\VoiceRef\Meru.wav`.
- `D:\LocalAI\AiMeruVoice\IrodoriTTS\voice_samples\meru.wav` is the correct fallback copy.
- `curl.exe http://127.0.0.1:8088/debug/runtime` reports `backend_mode` as `resident`.
- The generation log shows `reference_audio_path` for `meru`.

### GUI path is selected but not reflected

Check:

- `aimeru/adapter.py` includes `reference_audio_path` and `ref_wav` in `_build_payload()`.
- The resident API accepts `reference_audio_path` and `ref_wav`.
- The generation log shows the expected payload reference path.

### 8088 does not respond

Check:

```powershell
cd D:\LocalAI\AiMeruVoice\IrodoriTTS
.\start_fast_mode.bat
curl.exe http://127.0.0.1:8088/health
netstat -ano | findstr :8088
```

Do not run the old `run_server.bat` at the same time as the resident API on `8088`.

## 8. Git Safety

Use these checks before committing:

```powershell
git status --short
git status --ignored --short
git ls-files voice_samples
```

Expected tracked voice sample output:

```text
voice_samples/.gitkeep
```

Actual reference audio, generated WAV files, logs, and `.env` files must stay out of Git.

## 9. Related Files

- `aimeru/adapter.py`
- `aimeru/gui/main_window.py`
- `aimeru/gui/gen_tab.py`
- `aimeru/gui/worker.py`
- `aimeru/models.py`
- `start_fast_mode.bat`
- `README.md`
- `C:\Users\koben\Dev\Irodori-TTS\irodori_openai_server.py`
- `C:\Users\koben\Dev\Irodori-TTS\run_resident_server.bat`
