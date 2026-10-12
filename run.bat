@echo off
REM ============================================================
REM  SimpleMemKitty 启动脚本（Windows 双击即可运行）
REM  优先使用本目录的 .venv 虚拟环境，否则回退到系统 python
REM ============================================================
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    echo 使用虚拟环境 .venv ...
    .venv\Scripts\python.exe main.py
) else (
    echo 未找到 .venv，尝试系统 python ...
    python main.py
)

echo.
echo 程序已退出。若窗口一闪而过，请确认已安装依赖：
echo   pip install -r requirements.txt
pause
