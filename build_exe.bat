@echo off
rem One-click build: SimpleMemKitty -> single-file EXE
rem This file is intentionally pure ASCII: cmd.exe reads .bat using the OEM code
rem page, so any non-ASCII literal here could get garbled. All paths are derived
rem from %~dp0 (this file's own folder) instead of being hard-coded.
setlocal
rem Force UTF-8 output so non-ASCII text stays readable under any console code page
chcp 65001 >nul 2>nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "HERE=%~dp0"
set "PYEXE="

if exist "%HERE%..\.venv\Scripts\python.exe" set "PYEXE=%HERE%..\.venv\Scripts\python.exe"
if not defined PYEXE if exist "%HERE%.venv\Scripts\python.exe" set "PYEXE=%HERE%.venv\Scripts\python.exe"
if not defined PYEXE set "PYEXE=python"

"%PYEXE%" "%HERE%build_exe.py" %*

if errorlevel 1 (
    echo.
    echo [build] FAILED. See the messages above.
    pause
)
endlocal
