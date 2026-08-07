@echo off
REM LMS training system - automated backup (called by Windows Task Scheduler).
REM Runs backup.py located in the same folder as this batch file.

cd /d "%~dp0"

REM Activate the virtualenv if present; otherwise use the system Python.
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

if not exist "%~dp0backups" mkdir "%~dp0backups"
python backup.py >> "%~dp0backups\backup.log" 2>&1
