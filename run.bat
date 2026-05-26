@echo off
REM AiMeru Voice Studio 起動スクリプト (Windows)
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] 仮想環境が見つかりません。先に setup.bat を実行してください。
    pause
    exit /b 1
)

.venv\Scripts\python.exe main.py %*
