@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"

if exist "%VENV_PY%" (
    "%VENV_PY%" launch_gradio.py %*
    exit /b %errorlevel%
)

where py >nul 2>&1
if not errorlevel 1 (
    py -3 launch_gradio.py %*
    exit /b %errorlevel%
)

where python >nul 2>&1
if not errorlevel 1 (
    python launch_gradio.py %*
    exit /b %errorlevel%
)

echo [ERROR] Python was not found. Run setup.bat first.
pause
exit /b 1
