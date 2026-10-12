"""UI 导入 smoke 测试。

若环境未安装 PyQt5 / psutil（如最小化测试环境），则用 importorskip 跳过，
不会影响核心逻辑的测试结果。
"""

import pytest

pytest.importorskip("PyQt5")
pytest.importorskip("psutil")


def test_import_ui_modules():
    from simplememkitty.ui import main_window, settings_dialog  # noqa: F401
    from simplememkitty import __main__ as entry  # noqa: F401

    assert hasattr(entry, "main")
