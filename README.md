# SimpleMemKitty

一款简单的 Windows 内存清理工具。以原 `SimpleMemKitty.py` 为本体，
重写成模块化项目，并合并了 `SimpleMemKittyUltra.py` 的实用功能
（自动清理、设置、配置持久化）。去除了花哨界面和一些低效、危险的操作。

## 主要改进

- 修复内存瞬间飙升：原深度清理里的 `memory_hook_reclaim` 会先分配大量内存再释放，
  导致内存曲线剧烈抖动，已彻底移除。
- 修复清理速度过慢：去除了 `PowerShell Enable-MMAgent`、遍历所有磁盘卷做 `FlushFileBuffers`、
  以及把系统缓存压到最小的 `SetSystemFileCacheSize` 等缓慢步骤。
- 修复权限弹窗死循环：原程序未获管理员权限时会反复弹窗，现在只询问一次，
  拒绝则以降级模式继续运行。
- 可测试：核心逻辑（`core` 与 `auto`）与界面、Windows API 解耦，可用模拟接口做单元测试。

## 项目结构

```
SimpleMemKitty/
├── main.py                    # 统一入口，双击即可启动
├── simplememkitty/
│   ├── __init__.py
│   ├── __main__.py            # 命令行入口（支持 --deep-clean 无窗口模式）
│   ├── core/                  # 纯逻辑，可测试
│   │   ├── stats.py           # 内存统计
│   │   ├── settings.py        # 配置持久化
│   │   ├── memory_api.py      # Windows API 封装
│   │   └── cleaner.py         # 清理编排
│   ├── auto/
│   │   └── auto_cleaner.py    # 自动清理控制
│   └── ui/
│       ├── main_window.py     # 主窗口 + 托盘
│       └── settings_dialog.py
├── tests/                     # 单元测试
├── pyproject.toml
├── requirements.txt
├── conftest.py
├── .gitignore
└── LICENSE                    # MIT
```

## 启动方式

推荐直接双击仓库根目录下的 `main.py`。

`main.py` 自带环境自举：若当前 Python 未安装依赖，会自动改用 `.venv`
的解释器重新运行，因此双击即可启动，无需额外脚本。`.venv` 按
「项目目录内 → 上层目录」的顺序查找。

命令行方式：

```bash
python main.py                # 带图形界面启动
python main.py --deep-clean   # 无窗口深度清理，适合任务计划
```

## 首次准备

`.venv` 放在上层目录（`内存清理\.venv`），可被同目录下多个项目共用。
如果尚未创建，或需要手动安装依赖：

```bash
cd ..                          # 回到上层「内存清理」文件夹
python -m venv .venv
.venv\Scripts\activate
pip install -r SimpleMemKitty\requirements.txt
python SimpleMemKitty\main.py
```

## 运行测试

```bash
pytest
```

核心测试不依赖图形界面；未安装界面库时，界面导入测试会自动跳过。

## 注意事项

- 清理系统级内存列表需要管理员权限；非管理员启动时会询问一次，拒绝则降级运行。
- 托盘左键单击可显示或隐藏主窗口；清理完成通知默认关闭，可在设置里开启。
- `.venv` 与 `.scratch` 等本地环境/缓存目录放在仓库外（上层文件夹），不进入版本库。
