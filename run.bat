@echo off
setlocal enabledelayedexpansion

REM SimpleMemKitty launcher for Windows. Double-click to run.
REM Priority: local .venv -> system python -> py launcher.

cd /d "%~dp0"

set "PYTHON_BIN="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_BIN=.venv\Scripts\python.exe"
    echo Using local venv: .venv
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_BIN=python"
        echo Using system python
    ) else (
        where py >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_BIN=py"
            echo Using py launcher
        )
    )
)

if not defined PYTHON_BIN (
    echo ERROR: Python was not found on this machine.
    echo.
    echo Please install Python 3.8 or newer and make sure it is on PATH,
    echo then run the following commands in this folder:
    echo.
    echo     python -m venv .venv
    echo     .venv\Scripts\activate
    echo     pip install -r requirements.txt
    echo.
    echo After that, double-click run.bat again.
    echo.
    pause
    exit /b 1
)

echo Launching SimpleMemKitty...
"%PYTHON_BIN%" main.py
set "RC=%errorlevel%"
echo.
if not "%RC%"=="0" (
    echo Launch failed with exit code %RC%.
    echo If the message says "No module named PyQt5" or "No module named psutil",
    echo run:  pip install -r requirements.txt
)
echo Press any key to exit...
pause
