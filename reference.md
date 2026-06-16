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
- Converted reference WAV files live under `.local/converted_voice_refs/` and must not be committed.

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

### Non-WAV reference audio

The speaker reference field accepts these extensions:

```text
.wav .mp3 .m4a .aac .flac .ogg .opus .mp4 .mov .mkv .webm
```

- `.wav` files are used directly.
- Other supported audio/video files are converted with FFmpeg to mono 24 kHz WAV.
- Converted files are written to `.local/converted_voice_refs/`.
- If FFmpeg is not available, non-WAV files show a warning and are not used.
- The original file is never overwritten.

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

## 8. Generated Audio Panel

The generation tab shows generated chunk WAV files after a script is loaded or generation finishes.

Main behavior:

- If no output folder is selected, generated chunks are saved under `Path.home() / "Downloads" / "chunks"`.
- The project screen's output field is a working chunk location, not the final master WAV save location.
- Existing generated chunk WAV files are listed from the current output directory.
- Every listed chunk is checked by default.
- Use `全選択` to check all chunks.
- Use `全解除` to clear all chunks.
- Use `再生` on each row to preview that chunk.
- The global seek bar shows current playback time and can seek within the playing chunk.
- Starting another chunk stops the previous playback.
- Use `Full Mix Preview` to create a temporary WAV and play the selected chunks without choosing a save path.
- Use `Export Full Mix` to choose a save path and write the official merged WAV.
- The merge target is only the checked chunks, in table order.
- Merged WAV files insert the configured silence duration between chunks. The default is 0.5 seconds.
- No silence is added after the final chunk.
- Individual chunk WAV files and individual chunk preview playback are unchanged.
- Save location is chosen when the button is pressed; the app does not require an output path for merged WAVs before generation.
- `full_mix.wav` uses the project `mix_pause_ms` setting. New projects default to 500 ms.
- The optional `完了後に full_mix.wav を自動作成` checkbox is not the primary export path. Prefer `Full Mix Preview` and `Export Full Mix` for deliberate review and saving.

Script state rules:

- Loading a Markdown file creates fresh `未生成` chunks.
- Showing a chunk in the script preview does not mark it as successful.
- A chunk becomes `成功` only after WAV generation succeeds.
- `既存ファイルをスキップ` skips only when the expected WAV file exists, its size is greater than 0, and `manifest.json` matches the current script id, voice id, text hash, relative WAV path, file size, and successful/skipped status.
- Status alone must not be used as the skip condition.
- This prevents a different Markdown script's `001_ai.wav` from being reused by accident.

Future collision reduction:

- A later improvement may store chunks under `chunks/<script_id>/` to reduce same-name collisions between scripts even further.

Markdown drag and drop:

- Drop `.md` or `.markdown` files onto the window to load a script.
- Non-Markdown files are rejected with a warning.
- If multiple files are dropped, the first Markdown file is loaded.
- Loading a dropped file resets chunk state to `未生成`.

Merge safety:

- Source WAV files must exist.
- WAV channel count, sample width, frame rate, and compression type must match.
- Frame count, duration, and file size do not need to match.
- Silence uses the same channel count, sample width, frame rate, and compression metadata as the merged WAV.
- If formats do not match, the app shows an error instead of writing a broken merged WAV.

## 9. Git Safety

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

## 10. Related Files

- `aimeru/adapter.py`
- `aimeru/gui/main_window.py`
- `aimeru/gui/gen_tab.py`
- `aimeru/gui/worker.py`
- `aimeru/models.py`
- `start_fast_mode.bat`
- `README.md`
- `C:\Users\koben\Dev\Irodori-TTS\irodori_openai_server.py`
- `C:\Users\koben\Dev\Irodori-TTS\run_resident_server.bat`

## 11. Future Chunk Editing Notes

Future chunk editing and regeneration should keep enough metadata to decide whether an existing WAV still matches the text:

- `index`
- `speaker_label`
- `voice_id`
- `text`
- `original_text`
- `wav_path`
- `status`
- `checked`
- `last_generated_text_hash`

The current implementation does not yet edit chunks in place. Avoid using status alone as proof that a chunk's WAV is valid.
