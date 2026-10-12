"""程序入口。

修复原 SimpleMemKitty.py 的 bug：
- 原 main() 在缺少管理员权限时会 *无限循环* 弹 UAC 请求，用户点"取消"也无法退出。
  这里改为：仅在启动时询问一次；用户拒绝则以降级模式运行（仍可清理普通进程）。
- 支持无窗口深度清理模式（--deep-clean），便于自动化 / 任务计划调用。
"""

import sys
import os
import ctypes


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin() -> bool:
    try:
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        script = os.path.abspath(sys.argv[0])
        cmd = f'"{sys.executable}" "{script}" {params}'.strip()
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, cmd, None, 1
        )
        return ret > 32
    except Exception:
        return False


def main():
    # 无窗口深度清理模式（无需 GUI）
    if "--deep-clean" in sys.argv:
        from simplememkitty.core.cleaner import Cleaner

        result = Cleaner().deep_clean()
        print("Deep clean result:", result)
        return

    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5 import QtCore as _QtCore
    from simplememkitty.core.settings import Settings
    from simplememkitty.ui.main_window import MainWindow

    # 修复：部分环境下（尤其项目路径含非 ASCII 字符，如中文目录名）PyQt5 不会
    # 自动把自带的 Qt5/plugins 加入 Qt 库搜索路径，导致启动 GUI 时报
    # "Could not find the Qt platform plugin 'windows'"。这里在创建 QApplication
    # 之前显式加入该目录，确保 qwindows.dll 能被找到。
    _plugins_dir = os.path.join(os.path.dirname(_QtCore.__file__), "Qt5", "plugins")
    if os.path.isdir(_plugins_dir):
        _QtCore.QCoreApplication.addLibraryPath(_plugins_dir)
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", _plugins_dir)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    settings = Settings().load()

    # 权限询问一次（不再无限循环）
    if not is_admin():
        ans = QMessageBox.question(
            None, "权限提示",
            "清理系统级内存需要管理员权限，是否以管理员身份重启？\n"
            "（拒绝将以降级模式运行，仍可清理普通进程工作集）",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ans == QMessageBox.Yes and run_as_admin():
            sys.exit(0)

    window = MainWindow(settings)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
