"""应用入口（顶层启动文件，可直接双击运行）。

本文件做了"自举"处理：双击运行时若当前 Python 没有安装 PyQt5/psutil
（例如系统默认的 python），会自动改用项目自带 .venv 里的解释器重新运行
自己，因此无需借助 run.bat 也能正常启动。

用法：
    python main.py                # 带图形界面启动
    python main.py --deep-clean   # 无窗口深度清理（适合任务计划 / 自动化）
"""
import os
import sys
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))


def _ensure_venv_python():
    """若当前解释器缺少 GUI 依赖（PyQt5 / psutil），则改用项目 .venv 的
    解释器重新运行本脚本，并退出当前进程；避免依赖缺失导致"双击没反应"。"""
    try:
        import PyQt5, psutil  # noqa: F401
        return
    except ImportError:
        pass

    venv_python = os.path.join(HERE, ".venv", "Scripts", "python.exe")

    # 已经在 .venv 中但仍缺依赖：无法自举，提示安装后退出（防止无限重启）
    if os.path.abspath(sys.executable) == os.path.abspath(venv_python):
        sys.stderr.write(
            "ERROR: 当前 .venv 未安装依赖。请在该目录下执行：\n"
            "    .venv\\Scripts\\activate\n"
            "    pip install -r requirements.txt\n"
        )
        sys.exit(1)

    if os.path.isfile(venv_python):
        # 用 .venv 的解释器重新运行本文件，并原样传递命令行参数
        subprocess.run([venv_python, os.path.abspath(__file__)] + sys.argv[1:])
        sys.exit(0)

    sys.stderr.write(
        "ERROR: 未找到带依赖的 Python 环境（.venv）。请先执行：\n"
        "    python -m venv .venv\n"
        "    .venv\\Scripts\\activate\n"
        "    pip install -r requirements.txt\n"
    )
    sys.exit(1)


_ensure_venv_python()
from simplememkitty.__main__ import main

if __name__ == "__main__":
    main()
