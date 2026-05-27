@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

echo ==============================================
echo   AiMeru Voice Studio setup for Windows
echo ==============================================
echo.

call :find_python
if errorlevel 1 exit /b 1

if exist "%VENV_PY%" (
    echo [OK] Virtual environment already exists: %VENV_DIR%
    "%VENV_PY%" -c "import sys; print(sys.executable)" >nul 2>&1
    if errorlevel 1 (
        echo [WARN] Existing virtual environment is not runnable. Repairing it with the detected Python.
        call %PYTHON_CMD% -m venv --upgrade "%VENV_DIR%"
        if errorlevel 1 (
            echo [ERROR] Failed to repair the existing virtual environment.
            echo         If this venv was copied from another machine, remove .venv and run setup.bat again.
            pause
            exit /b 1
        )
    )
) else (
    echo [..] Creating virtual environment: %VENV_DIR%
    call %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        echo         Check that Python 3.11+ is installed and available on PATH.
        pause
        exit /b 1
    )
)

if not exist "%VENV_PY%" (
    echo [ERROR] Virtual environment Python was not found: %VENV_PY%
    pause
    exit /b 1
)

echo [..] Upgrading pip with venv Python
"%VENV_PY%" -m pip install --quiet --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    echo         Retry manually:
    echo         %VENV_PY% -m pip install --upgrade pip
    pause
    exit /b 1
)

echo [..] Installing requirements
"%VENV_PY%" -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.txt.
    echo         Check your network connection and the error messages above.
    pause
    exit /b 1
)

echo.
echo [OK] Python dependencies are ready.
echo.
echo Reference voice files:
if exist "voice_samples\ai.wav" (
    echo [OK] voice_samples\ai.wav found
) else (
    echo [INFO] voice_samples\ai.wav not found
)
if exist "voice_samples\meru.wav" (
    echo [OK] voice_samples\meru.wav found
) else (
    echo [INFO] voice_samples\meru.wav not found
)
echo.
echo Next:
echo   run_server.bat       starts the local API server on 127.0.0.1:8088
echo   run.bat              starts AiMeru Voice Studio GUI
echo   launch_gradio.bat    starts Irodori-TTS Gradio UI, if the external repo exists
echo.
pause
exit /b 0

:find_python
set "PYTHON_CMD="
set "PYTHON_VER="

for %%P in (python3.13 python3.12 python3.11 python3 python) do (
    where %%P >nul 2>&1
    if not errorlevel 1 (
        %%P -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
        if not errorlevel 1 (
            for /f "usebackq delims=" %%V in (`%%P -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"` ) do (
                set "PYTHON_CMD=%%P"
                set "PYTHON_VER=%%V"
                goto :python_found
            )
        )
    )
)

where py >nul 2>&1
if not errorlevel 1 (
    for %%V in (3.13 3.12 3.11) do (
        py -%%V -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_CMD=py -%%V"
            for /f "usebackq delims=" %%R in (`py -%%V -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"` ) do set "PYTHON_VER=%%R"
            goto :python_found
        )
    )
)

echo [ERROR] Python 3.11 or newer was not found.
echo         Install Python from https://www.python.org/downloads/
echo         Enable "Add Python to PATH" during installation.
pause
exit /b 1

:python_found
echo [OK] Python %PYTHON_VER% found: %PYTHON_CMD%
exit /b 0
