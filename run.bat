@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [ERROR] Virtual environment was not found.
    echo         Run setup.bat first.
    pause
    exit /b 1
)

echo Starting AiMeru Voice Studio GUI...
echo Note: this GUI expects an OpenAI-compatible Irodori-TTS API server, usually http://localhost:8088.
echo       The Gradio UIs are separate: http://localhost:7860 and http://localhost:7861.
"%VENV_PY%" main.py %*
exit /b %errorlevel%
