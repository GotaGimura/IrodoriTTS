# AiMeru Voice Studio

AiMeru Voice Studio is a local desktop GUI for preparing scripts, sending them to an OpenAI-compatible Irodori-TTS API server, and collecting generated WAV files.

This repository is the AiMeru GUI. It does not by itself guarantee that the Irodori-TTS synthesis server is running.

## Roles and URLs

| URL | Role | Started by |
| --- | --- | --- |
| `http://localhost:8088` | OpenAI-compatible Irodori-TTS API server used by AiMeru GUI (`/health`, `/v1/audio/speech`) | Irodori-TTS server command, separate from this GUI |
| `http://localhost:7860` | Irodori-TTS TTS v3 Gradio UI | `gradio_app.py` in the external Irodori-TTS checkout |
| `http://localhost:7861` | Irodori-TTS VoiceDesign Gradio UI | `gradio_app_voicedesign.py` in the external Irodori-TTS checkout |

Important: starting `run.bat` only starts the AiMeru GUI. It may still show a connection failure until an API server is running on `http://localhost:8088`.
For normal fast operation, use `start_fast_mode.bat`.

## Windows Quick Start

```bat
cd D:\LocalAI\AiMeruVoice
git clone https://github.com/GotaGimura/IrodoriTTS.git
cd IrodoriTTS
.\setup.bat
.\start_fast_mode.bat
```

`setup.bat` creates `.venv`, upgrades pip using `.venv\Scripts\python.exe -m pip`, and installs `requirements.txt`.

For the current high-speed local workflow, use `start_fast_mode.bat`. It starts or reuses the Irodori-TTS resident API on `127.0.0.1:8088`, waits for `/health`, then starts AiMeru Voice Studio. The older `run_server.bat` bridge is kept as a fallback, but it is not the recommended fast path.

Reference audio, speaker mapping, payload fields, and Git safety rules are documented in `reference.md`.

## Start The AiMeru GUI

```bat
cd D:\LocalAI\AiMeruVoice\IrodoriTTS
.\run.bat
```

The GUI default server URL is `http://localhost:8088`. This is for the OpenAI-compatible resident TTS API server, not the Gradio UI. Starting the GUI alone does not start the API server.

## Start Fast Resident Mode

Recommended daily startup:

```bat
cd D:\LocalAI\AiMeruVoice\IrodoriTTS
.\start_fast_mode.bat
```

This does the following:

- checks `http://127.0.0.1:8088/health`;
- starts the external Irodori-TTS resident API from `C:\Users\koben\Dev\Irodori-TTS` if needed;
- waits until the API is healthy;
- starts AiMeru Voice Studio.

In fast mode, AiMeru GUI connects to the resident API on `8088`. The test port `8089` is only for verification or fallback experiments.

## Start The Local API Server

This repository still includes the older AiMeru FastAPI bridge:

```bat
cd D:\LocalAI\AiMeruVoice\IrodoriTTS
.\run_server.bat
```

It calls `infer.py` through subprocess for each request. It is useful as a fallback, but the recommended high-speed path is the external Irodori-TTS resident API via `start_fast_mode.bat`.

The bridge binds to `127.0.0.1:8088` by default. Health check:

```bat
curl http://127.0.0.1:8088/health
netstat -ano | findstr :8088
```

If you use this fallback bridge, AiMeru GUI needs both processes:

```bat
.\run_server.bat
.\run.bat
```

Starting the GUI alone does not start the synthesis API server.

## Start Irodori-TTS Gradio UI

The Irodori-TTS application itself is expected to be cloned separately. On this Windows machine, the expected path is:

```bat
C:\Users\koben\Dev\Irodori-TTS
```

Manual start commands:

```bat
cd C:\Users\koben\Dev\Irodori-TTS
uv run python gradio_app.py --server-name 127.0.0.1 --server-port 7860
uv run python gradio_app_voicedesign.py --server-name 127.0.0.1 --server-port 7861
```

From this repository, you can also use:

```bat
cd D:\LocalAI\AiMeruVoice\IrodoriTTS
.\launch_gradio.bat
```

`launch_gradio.bat` checks for the external checkout and starts both Gradio UIs through `uv run`. It does not clone repositories automatically. If your checkout is somewhere else, use either:

```bat
set IRODORI_TTS_DIR=C:\path\to\Irodori-TTS
.\launch_gradio.bat
```

or:

```bat
.\launch_gradio.bat --repo-dir C:\path\to\Irodori-TTS
```

Useful options:

```bat
.\launch_gradio.bat --v3
.\launch_gradio.bat --vd
.\launch_gradio.bat --no-browser
```

## Local-Only Security Default

Gradio is launched with `--server-name 127.0.0.1` by default. This means it is reachable only from the local machine.

Do not bind Gradio or API servers to `0.0.0.0` by default. If you really need LAN access, use the explicit flag:

```bat
.\launch_gradio.bat --network
.\run_server.bat --network
```

This binds the selected service to `0.0.0.0` and prints a warning. Use it only on a trusted network.

## API Server For AiMeru GUI

AiMeru GUI sends synthesis requests to:

```text
POST http://localhost:8088/v1/audio/speech
GET  http://localhost:8088/health
```

If the GUI says it cannot connect to `http://localhost:8088`, the OpenAI-compatible API server is probably not running. The Gradio UI on `7860` or `7861` is separate and does not replace the `8088` API endpoint.

This repository provides a local FastAPI bridge:

```bat
.\run_server.bat
```

The bridge calls the external Irodori-TTS checkout at `C:\Users\koben\Dev\Irodori-TTS` through `uv run --no-sync python infer.py`. `--no-sync` is intentional: after installing a CUDA-enabled PyTorch build, plain `uv run` may sync from `pyproject.toml` / `uv.lock` and move the environment back to a CPU torch build.

You can override the path:

```bat
set IRODORI_TTS_DIR=C:\path\to\Irodori-TTS
.\run_server.bat
```

Voice IDs are mapped to local reference files in `voice_samples\`. For example, `voice=ai` uses `voice_samples\ai.wav` when present. You can also override per voice:

```bat
set IRODORI_VOICE_AI_WAV=D:\voices\ai.wav
set IRODORI_VOICE_MERU_WAV=D:\voices\meru.wav
```

When a speaker reference file is selected in the GUI, AiMeru sends it in the API payload as `reference_audio_path` and `ref_wav`. Compatible resident servers use this explicit path first. If the explicit file path does not exist, the server returns a clear `reference_audio_not_found` error instead of silently falling back to the wrong voice.

For the detailed reference audio rules, see `reference.md`.

The generation tab also includes a generated-audio panel for previewing chunk WAV files, selecting chunks, and saving a merged WAV. See `reference.md` for details.
If the output folder is left blank, chunk WAV files are saved under the current user's `Downloads\chunks` folder.
Merged WAV saves insert 0.5 seconds of silence between selected chunks, with no trailing silence after the final chunk. Individual chunk files and individual preview playback are not modified.

The default Hugging Face checkpoint is `Aratako/Irodori-TTS-500M-v3`. Override it if needed:

```bat
set IRODORI_TTS_CHECKPOINT=Aratako/Irodori-TTS-500M-v3
```

## Check Which Ports Are Running

```bat
netstat -ano | findstr :8088
netstat -ano | findstr :7860
netstat -ano | findstr :7861
```

Expected meaning:

- `:8088` is the API server for AiMeru GUI generation.
- `:7860` is the TTS v3 Gradio UI.
- `:7861` is the VoiceDesign Gradio UI.

## CUDA / RTX 4090 Check

For this AiMeru GUI virtual environment:

```bat
.\.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CUDA not available')"
```

For the external Irodori-TTS checkout when using `uv`:

```bat
uv run --no-sync python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CUDA not available')"
```

Expected RTX 4090 result:

```text
2.11.0+cu128
12.8
True
NVIDIA GeForce RTX 4090
```

You can also check through the AiMeru API server while `run_server.bat` is running:

```bat
curl http://127.0.0.1:8088/debug/cuda
```

If `cuda_available` is `false`, the environment may have CPU-only PyTorch installed or CUDA may not be visible. In that case, install the CUDA-enabled PyTorch build that matches the Irodori-TTS project and your driver/CUDA setup. Do this deliberately in the target environment only; do not remove or reinstall packages blindly.

If the AiMeru GUI environment prints `ModuleNotFoundError: No module named 'torch'`, that only means this GUI venv does not install PyTorch. The most important check is usually the external Irodori-TTS `uv run --no-sync python ...` command, because that is the environment that performs model inference.

During generation, watch GPU use with:

```bat
nvidia-smi
```

## Voice Samples And Generated Files

Reference voice files and generated audio can contain private data. Do not commit them.

The repository keeps only:

```text
voice_samples/.gitkeep
```

Ignored examples include:

```text
voice_samples/*.wav
voice_samples/*.mp3
voice_samples/*.m4a
outputs/
*.log
.env
.env.*
```

## Troubleshooting

### `setup.bat` fails while upgrading pip

Use the venv Python module form, not `pip.exe` directly:

```bat
.\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The included `setup.bat` already uses this form.

### GUI starts but cannot connect to server

Start or verify the API server on `http://localhost:8088`, then click the GUI connection check again.

```bat
netstat -ano | findstr :8088
```

### Gradio starts but GUI still cannot generate

This is expected if only ports `7860` / `7861` are running. AiMeru GUI generation uses the API server on `8088`.
