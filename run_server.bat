@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"
set "HOST=127.0.0.1"
set "PORT=8088"

if not exist "%VENV_PY%" (
    echo [ERROR] Virtual environment was not found.
    echo         Run setup.bat first.
    pause
    exit /b 1
)

if /I "%~1"=="--network" (
    set "HOST=0.0.0.0"
    echo [WARN] --network exposes the API server on your LAN.
    echo        Use this only on a trusted network.
)

echo Starting AiMeru Irodori-TTS API server...
echo URL: http://%HOST%:%PORT%
echo Health: http://127.0.0.1:%PORT%/health
echo.
"%VENV_PY%" -m uvicorn aimeru.server:app --host %HOST% --port %PORT%
exit /b %errorlevel%
