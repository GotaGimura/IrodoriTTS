@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

set "AIMERU_DIR=%~dp0"
set "IRODORI_DIR=C:\Users\koben\Dev\Irodori-TTS"
set "API_URL=http://127.0.0.1:8088"
set "HEALTH_URL=%API_URL%/health"

echo AiMeru fast mode
echo API: %API_URL%
echo.

if not exist "%IRODORI_DIR%\run_resident_server.bat" (
    echo [ERROR] Irodori-TTS resident launcher was not found:
    echo         %IRODORI_DIR%\run_resident_server.bat
    exit /b 1
)

call :check_resident
if "%RESIDENT_OK%"=="1" goto start_gui

netstat -ano | findstr :8088 >nul 2>nul
if not errorlevel 1 (
    echo [ERROR] Port 8088 is already in use, but it is not the Irodori-TTS Resident API.
    echo         Stop the process using 8088, then run this file again.
    echo.
    netstat -ano | findstr :8088
    exit /b 1
)

echo Starting Irodori-TTS Resident API on 127.0.0.1:8088...
start "Irodori-TTS Resident API" cmd /k "cd /d %IRODORI_DIR% && .\run_resident_server.bat"

for /l %%I in (1,1,30) do (
    timeout /t 1 /nobreak >nul
    call :check_resident
    if "!RESIDENT_OK!"=="1" goto start_gui
)

echo [ERROR] Resident API did not become healthy within 30 seconds.
echo         Check the Irodori-TTS Resident API window for details.
exit /b 1

:start_gui
echo Resident API is ready.
echo Starting AiMeru Voice Studio...
start "AiMeru Voice Studio" cmd /k "cd /d %AIMERU_DIR% && .\run.bat"
exit /b 0

:check_resident
set "RESIDENT_OK=0"
curl.exe -fsS "%HEALTH_URL%" 2>nul | findstr /C:"Irodori-TTS Resident API" >nul 2>nul
if not errorlevel 1 set "RESIDENT_OK=1"
exit /b 0
