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
├── build_exe.bat              # 一键打包 EXE（双击即可）
├── build_exe.py               # 打包脚本主体
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

## 打包 EXE

双击 `build_exe.bat`（或运行 `python build_exe.py`）即可生成单文件 EXE，
默认输出到项目上层目录。首次运行会自动建立构建环境并下载依赖，之后每次
重新打包约 1 分钟。

构建环境位于 `%LOCALAPPDATA%\SimpleMemKittyBuild`（全 ASCII 路径），不进入
版本库，与项目共用的 `.venv` 互不影响。

**为什么构建环境要放在 ASCII 路径下**：PyInstaller 的 PyQt5 hook 依赖 Qt 自身的
`QLibraryInfo` 来定位 Qt 插件目录，而 Qt 在含中文等非 ASCII 字符的路径下会把
路径损坏成 `G:/????/...`，导致打包在分析阶段失败。脚本自动把源码复制到 ASCII
路径下构建，再把 EXE 拷回，因此项目本身放在什么路径都可以（不需要移动项目、
不使用任何链接）。

常用参数：

```bash
python build_exe.py                    # 打包，输出到项目上层目录
python build_exe.py --outdir D:\out    # 指定输出目录
python build_exe.py --console          # 生成带控制台版本（便于排查问题）
python build_exe.py --keep-temp        # 保留中间文件（便于排查问题）
python build_exe.py --clean-venv       # 删除构建环境后重建
```

可用环境变量：`SMK_BUILD_ROOT`（构建环境目录）、`SMK_PIP_INDEX`（pip 源，
默认 `https://pypi.org/simple`）。

## 注意事项

- 清理系统级内存列表需要管理员权限；非管理员启动时会询问一次，拒绝则降级运行。
- 托盘左键单击可显示或隐藏主窗口；清理完成通知默认关闭，可在设置里开启。
- `.venv` 与 `.scratch` 等本地环境/缓存目录放在仓库外（上层文件夹），不进入版本库。
