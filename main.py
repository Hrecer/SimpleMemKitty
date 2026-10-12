"""应用入口（顶层启动文件）。

这是本项目的统一入口，放在仓库根目录，方便查找：
- 双击运行 / 命令行：  python main.py
- 等价于：              python -m simplememkitty

无窗口深度清理模式：python main.py --deep-clean
"""
from simplememkitty.__main__ import main

if __name__ == "__main__":
    main()
