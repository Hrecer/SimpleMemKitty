# SimpleMemKitty（项目版 / 可测试）

以原 `SimpleMemKitty.py` 为主体重写而成的模块化内存清理工具，合并了
`SimpleMemKittyUltra.py` 的实用功能（自动清理、设置、配置持久化、清理结果通知），
并移除了花哨 UI 与危险/低效步骤。

## 相比原版的关键改进

- **修复"内存突然跳一大截又掉回来"**：原深度清理里的 `memory_hook_reclaim`
  会分配半个可用内存再释放，是内存瞬时飙升的根因，已彻底移除。
- **修复"清理非常慢"**：移除了慢且损害性能的
  `PowerShell Enable-MMAgent`、遍历所有磁盘卷 `FlushFileBuffers`、
  以及把系统文件缓存压到最小的 `SetSystemFileCacheSize`。
- **修复管理员权限无限循环弹窗**：改为启动时只询问一次，拒绝则以降级模式运行。
- **核心逻辑与 GUI / Windows API 解耦**：`core` 与 `auto` 不依赖 PyQt5，
  可用 FakeAPI 注入进行单元测试。

## 项目结构

```
SimpleMemKitty/
├── main.py                # ★ 统一入口（仓库根目录，双击/命令行 python main.py）
├── simplememkitty/
│   ├── __init__.py
│   ├── __main__.py          # 入口（含 --deep-clean 无窗口模式）
│   ├── core/                # 纯逻辑，可测试
│   │   ├── stats.py         # 内存/CPU 统计与格式化
│   │   ├── settings.py      # JSON 配置持久化
│   │   ├── memory_api.py    # Windows API 封装（可替换接口）
│   │   └── cleaner.py       # 轻量/深度清理编排
│   ├── auto/
│   │   └── auto_cleaner.py  # 自动清理控制器（阈值/冷却/间隔）
│   └── ui/
│       ├── main_window.py   # 主窗口 + 托盘 + 通知
│       └── settings_dialog.py
├── tests/                   # pytest 单元测试
├── pyproject.toml
├── requirements.txt
└── conftest.py
├── .gitignore               # 忽略缓存/虚拟环境/构建产物
└── .scratch/                # 专用临时/缓存文件夹（pytest 缓存等，自动忽略）
```

## 临时文件夹 `.scratch`

`.scratch/` 是本项目的**专用临时/缓存文件夹**，用来集中存放工具运行产生的临时文件，保持仓库根目录整洁：

- pytest 的缓存现写在 `.scratch/.pytest_cache`（由 `pyproject.toml` 的 `cache_dir` 配置）；
- 其它临时文件、日志、调试导出等也请放这里；
- 该文件夹整体被 `.gitignore` 忽略（只保留 `.gitkeep` 占位），**不会进入 Git**；
- 可随时安全删除，下次运行会自动重建。

> 说明：Python 自身的 `__pycache__/`、构建产物 `build/`、`dist/`、`*.egg-info/` 属标准缓存/产物，
> 同样已在 `.gitignore` 中忽略，仍按惯例留在各自位置，无需挪动。

## 运行测试

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
pytest
```

核心测试（stats / settings / auto_cleaner / cleaner）不依赖 GUI，可在任意环境运行；
UI 导入测试在未安装 PyQt5/psutil 时会自动跳过。

## 入口与启动（重要：找不到入口看这里）

程序真正的入口逻辑在 `simplememkitty/__main__.py` 的 `main()`，但**不要去包里找**，
仓库根目录已经放好了直观入口：

1. **`main.py`（唯一入口，可直接双击，跨平台）**
   `main.py` 内置"自举"逻辑：双击运行时若发现当前 Python 没装 PyQt5/psutil，
   会自动改用项目 `.venv` 的解释器重新运行自己，因此**双击即可启动**。
   ```bash
   # 在仓库根目录执行（或直接在资源管理器双击 main.py）
   python main.py                # 带图形界面启动
   python main.py --deep-clean   # 无窗口深度清理（适合任务计划 / 自动化）
   ```

2. **安装后作为命令运行（可选）**
   ```bash
   pip install .          # 安装本项目（含控制台入口）
   simplememkitty         # 之后可直接用命令启动
   ```

> 等价写法（不推荐，藏得深）：`python -m simplememkitty`

### 首次运行准备

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows（Linux/macOS: source .venv/bin/activate）
pip install -r requirements.txt
python main.py                # 启动
```

> 注意：清理系统级内存（standby/modified/combined 列表）需要**管理员权限**。
> 启动时若不是管理员，会询问一次是否以管理员重启；拒绝则以降级模式运行
> （仍可清理普通进程工作集）。
