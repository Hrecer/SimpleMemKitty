"""一键把 SimpleMemKitty 打包为单文件 EXE。

为什么要这么绕一层（而不是直接跑 PyInstaller）：
    项目路径可能包含中文（例如 G:\\内存清理\\SimpleMemKitty）。PyInstaller 的
    PyQt5 hook 依赖 Qt 自身的 QLibraryInfo 来定位 Qt 插件目录，而 Qt 在含非
    ASCII 字符的路径下会把路径损坏成 "G:/????/..."，导致打包在分析阶段直接失败。
    本脚本自动在**全 ASCII 的构建环境**里完成「建 venv -> 装依赖 -> 复制源码 ->
    打包 -> 把 EXE 拷回」，因此项目放在什么路径下都能打包成功，且不需要移动
    项目本身，也不使用任何链接（junction/symlink）。

用法：
    python build_exe.py                  # 打包，EXE 默认输出到项目上层目录
    python build_exe.py --outdir D:\\x    # 指定输出目录
    python build_exe.py --console        # 生成带控制台窗口的版本（排查问题用）
    python build_exe.py --keep-temp      # 保留中间文件（排查问题用）
    python build_exe.py --clean-venv     # 先删除构建环境再重建

可用环境变量：
    SMK_BUILD_ROOT  构建环境目录（默认 %LOCALAPPDATA%\\SimpleMemKittyBuild）
    SMK_PIP_INDEX   pip 源（默认 https://pypi.org/simple）
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTDIR = PROJECT_DIR.parent

BUILD_ROOT = Path(
    os.environ.get("SMK_BUILD_ROOT")
    or (Path(os.environ.get("LOCALAPPDATA", PROJECT_DIR)) / "SimpleMemKittyBuild")
)
VENV_DIR = BUILD_ROOT / "venv"
SRC_DIR = BUILD_ROOT / "src" / "SimpleMemKitty"
WORK_DIR = BUILD_ROOT / "work"
DIST_DIR = BUILD_ROOT / "dist"
SPEC_DIR = BUILD_ROOT

PIP_INDEX = os.environ.get("SMK_PIP_INDEX", "https://pypi.org/simple")
REQUIRED = ["PyQt5", "psutil", "PyInstaller"]
APP_NAME = "SimpleMemKitty"

# 复制源码时排除的内容
EXCLUDE = (".git", "__pycache__", ".pytest_cache", ".venv", ".scratch",
           "dist", "build", "*.pyc", f"{APP_NAME}.exe")


def log(msg):
    print(f"[build] {msg}", flush=True)


def _force_utf8_output():
    """统一输出为 UTF-8 并容错，避免控制台代码页不一致导致中文乱码或报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def run(cmd, **kwargs):
    log("执行: " + " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kwargs)


def venv_python() -> Path:
    return VENV_DIR / "Scripts" / "python.exe"


def ensure_venv():
    """在 ASCII 路径下准备构建专用 venv（与项目共用的 .venv 互不影响）。"""
    if venv_python().exists():
        return
    log(f"创建构建环境（ASCII 路径）: {VENV_DIR}")
    VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
    run([sys.executable, "-m", "venv", str(VENV_DIR)])


def ensure_deps():
    py = venv_python()
    probe = subprocess.run(
        [str(py), "-c", "import PyQt5, psutil, PyInstaller"],
        capture_output=True,
    )
    if probe.returncode == 0:
        log("构建依赖已就绪")
        return
    log("安装构建依赖（首次运行需要下载，请耐心等待）")
    run([py, "-m", "pip", "install", "-q", "--index-url", PIP_INDEX, "--upgrade"] + REQUIRED)


def sanity_check_qt():
    """确认构建环境里的 Qt 能正确定位插件目录（ASCII 路径的核心意义所在）。"""
    code = (
        "from PyQt5.QtCore import QLibraryInfo; import os, sys; "
        "p = QLibraryInfo.location(QLibraryInfo.PluginsPath); "
        "sys.exit(0 if os.path.isdir(p) else 1)"
    )
    if subprocess.run([str(venv_python()), "-c", code]).returncode != 0:
        raise SystemExit(
            "错误：构建环境中的 Qt 仍无法定位插件目录，说明构建路径包含非 ASCII 字符。\n"
            f"        构建环境应在 ASCII 路径下，当前为：{VENV_DIR}\n"
            "        可用环境变量 SMK_BUILD_ROOT 指定一个纯英文路径后重试。"
        )


def copy_sources():
    if SRC_DIR.exists():
        shutil.rmtree(SRC_DIR, ignore_errors=True)
    SRC_DIR.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PROJECT_DIR, SRC_DIR, ignore=shutil.ignore_patterns(*EXCLUDE))
    log(f"已复制源码到构建区: {SRC_DIR}")


def build(console: bool):
    args = [
        venv_python(), "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile",
        "--name", APP_NAME,
        "--distpath", DIST_DIR,
        "--workpath", WORK_DIR,
        "--specpath", SPEC_DIR,
    ]
    if not console:
        args.append("--windowed")
    args.append("main.py")
    run(args, cwd=SRC_DIR)


def deliver(outdir: Path) -> Path:
    exe = DIST_DIR / f"{APP_NAME}.exe"
    if not exe.exists():
        raise SystemExit(f"错误：未找到生成的 EXE：{exe}")
    outdir.mkdir(parents=True, exist_ok=True)
    target = outdir / f"{APP_NAME}.exe"
    shutil.copy2(exe, target)
    return target


def cleanup(keep_temp: bool):
    if keep_temp:
        log("已保留中间文件（--keep-temp）")
        return
    # 删除中间产物（work 目录、复制过去的源码）；venv 与 dist 保留以便下次快速重建
    for path in (WORK_DIR, SRC_DIR.parent, SRC_DIR):
        shutil.rmtree(path, ignore_errors=True)


def main():
    _force_utf8_output()
    parser = argparse.ArgumentParser(description="一键打包 SimpleMemKitty 为单文件 EXE")
    parser.add_argument("--outdir", default=str(DEFAULT_OUTDIR),
                        help="EXE 输出目录（默认：项目上层目录）")
    parser.add_argument("--console", action="store_true",
                        help="生成带控制台窗口的版本（便于排查问题）")
    parser.add_argument("--keep-temp", action="store_true", help="保留中间文件")
    parser.add_argument("--clean-venv", action="store_true", help="先删除构建环境再重建")
    args = parser.parse_args()

    start = time.time()
    log(f"项目目录: {PROJECT_DIR}")
    log(f"构建环境: {BUILD_ROOT}")

    if args.clean_venv and BUILD_ROOT.exists():
        log("删除旧构建环境")
        shutil.rmtree(BUILD_ROOT, ignore_errors=True)

    ensure_venv()
    ensure_deps()
    sanity_check_qt()
    copy_sources()
    build(args.console)
    target = deliver(Path(args.outdir))
    cleanup(args.keep_temp)

    log(f"打包完成，用时 {time.time() - start:.0f} 秒")
    log(f"EXE: {target}  ({target.stat().st_size / 2 ** 20:.1f} MB)")


if __name__ == "__main__":
    main()
