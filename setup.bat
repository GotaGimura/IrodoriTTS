@echo off
REM =============================================================================
REM  AiMeru Voice Studio — セットアップスクリプト (Windows)
REM
REM  実行方法: このファイルをダブルクリック、または
REM            コマンドプロンプトで setup.bat を実行
REM =============================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ==============================================
echo   AiMeru Voice Studio — セットアップ
echo ==============================================
echo.

REM ── 1. Python バージョン確認 ──────────────────────────
set PYTHON=
for %%P in (python3.13 python3.12 python3.11 python3 python) do (
    where %%P >nul 2>&1
    if !errorlevel! == 0 (
        for /f "tokens=*" %%V in ('%%P -c "import sys; v=sys.version_info; ok=v.major>=3 and v.minor>=11; print(f'{v.major}.{v.minor}.{v.micro}' if ok else '')"') do (
            if not "%%V"=="" (
                set PYTHON=%%P
                set PYTHON_VER=%%V
                goto :found_python
            )
        )
    )
)

echo [ERROR] Python 3.11 以上が見つかりません。
echo         https://www.python.org/downloads/ からインストールしてください。
echo         インストール時に "Add Python to PATH" にチェックを入れてください。
pause
exit /b 1

:found_python
echo [OK]  Python %PYTHON_VER% (%PYTHON%)

REM ── 2. 仮想環境の作成 ──────────────────────────────────
if exist ".venv\" (
    echo [OK]  仮想環境: 既存 (.venv\)
) else (
    echo [....] 仮想環境を作成中...
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] 仮想環境の作成に失敗しました。
        pause
        exit /b 1
    )
    echo [OK]  仮想環境を作成しました (.venv\)
)

REM ── 3. pip アップグレード + 依存インストール ────────────
echo [....] 依存ライブラリをインストール中...
.venv\Scripts\pip.exe install --quiet --upgrade pip
if errorlevel 1 goto :pip_error
.venv\Scripts\pip.exe install --quiet -r requirements.txt
if errorlevel 1 goto :pip_error
echo [OK]  インストール完了
goto :after_pip

:pip_error
echo [ERROR] ライブラリのインストールに失敗しました。
echo         ネットワーク接続を確認してください。
pause
exit /b 1

:after_pip

REM ── 4. voice_samples\ の確認 ──────────────────────────
echo.
echo -- 参照音声ファイルについて ----------------------------
if exist "voice_samples\ai.wav" (
    echo [OK]  voice_samples\ai.wav   -- 検出済み
) else (
    echo [WARN] voice_samples\ai.wav が見つかりません
)
if exist "voice_samples\meru.wav" (
    echo [OK]  voice_samples\meru.wav -- 検出済み
) else (
    echo [WARN] voice_samples\meru.wav が見つかりません
    echo        Irodori-TTS-Server に登録している音声ファイルを
    echo        voice_samples\ フォルダに配置してください。
    echo        （ファイル名は任意。アプリ内の話者設定で指定します）
)

REM ── 完了 ──────────────────────────────────────────────
echo.
echo ==============================================
echo   セットアップ完了！
echo.
echo   起動方法:
echo     run.bat
echo.
echo   Irodori-TTS-Server は別途起動が必要です。
echo   詳しくは README.md を参照してください。
echo ==============================================
echo.
pause
