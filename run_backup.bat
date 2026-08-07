@echo off
REM LMS研修システム 自動バックアップ（Windowsタスクスケジューラから呼び出す）
REM このバッチと同じフォルダの backup.py を実行する。

cd /d "%~dp0"

REM 仮想環境があれば有効化（無ければシステムのPythonを使用）
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

python backup.py >> "%~dp0backups\backup.log" 2>&1
