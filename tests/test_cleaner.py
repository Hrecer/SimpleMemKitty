"""Cleaner 测试：用 FakeAPI 验证清理编排，尤其确认深度清理
不再调用任何"大块内存分配 / reclaim / flush / powershell / 压缩"等
会造成"内存瞬间跳升又回落"或"卡顿缓慢"的步骤。
"""

from simplememkitty.core.cleaner import Cleaner

FORBIDDEN = ("reclaim", "flush", "powershell", "allocate", "compress", "cache")


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.priv = False

    def enable_privileges(self):
        self.calls.append("enable")
        self.priv = True
        return True

    def disable_privileges(self):
        self.calls.append("disable")
        self.priv = False
        return True

    def clean_working_sets(self):
        self.calls.append("clean_ws")
        return 42

    def purge_standby_list(self):
        self.calls.append("purge_standby")
        return True

    def purge_modified_list(self):
        self.calls.append("purge_modified")
        return True

    def purge_low_priority_standby_list(self):
        self.calls.append("purge_low_standby")
        return True


class FlakyAPI(FakeAPI):
    def purge_modified_list(self):
        raise RuntimeError("boom")


def _make(snaps):
    api = FakeAPI()
    c = Cleaner(api=api)
    c.snapshot_fn = lambda: snaps.pop(0)
    return c, api


def test_light_clean_sequence():
    snaps = [
        {"available": 1000, "used": 5000, "total": 6000, "percent": 80},
        {"available": 2000, "used": 4000, "total": 6000, "percent": 70},
    ]
    c, api = _make(list(snaps))
    res = c.light_clean()

    assert "enable" in api.calls
    assert "clean_ws" in api.calls
    assert "purge_standby" in api.calls
    assert "disable" in api.calls
    assert res["cleaned_processes"] == 42
    assert res["freed_bytes"] == 1000

    # 关键：轻量清理绝不分配大块内存或调用慢速外部命令
    assert not any(any(b in call for b in FORBIDDEN) for call in api.calls), api.calls


def test_deep_clean_sequence_and_no_jump():
    snaps = [
        {"available": 1000, "used": 5000, "total": 6000, "percent": 80},
        {"available": 3500, "used": 2500, "total": 6000, "percent": 40},
    ]
    c, api = _make(list(snaps))
    res = c.deep_clean()

    # 期望顺序：启用特权 -> 清工作集 -> 回收三个列表 -> 禁用特权
    assert api.calls == [
        "enable",
        "clean_ws",
        "purge_standby",
        "purge_modified",
        "purge_low_standby",
        "disable",
    ]
    assert res["freed_bytes"] == 2500

    # 关键修复：深度清理不会让内存先暴涨再回落
    assert not any(any(b in call for b in FORBIDDEN) for call in api.calls), api.calls


def test_memory_list_constants_are_correct():
    """回归测试：这些常量曾经写错（class=0x57、命令 5/6），导致系统级回收
    全部静默失败却返回成功，深度清理名存实亡。已在本机实测验证正确值。"""
    from simplememkitty.core import memory_api

    assert memory_api.SYSTEM_MEMORY_LIST_INFORMATION == 0x50
    assert memory_api.MEMORY_PURGE_STANDBY_LIST == 4
    assert memory_api.MEMORY_FLUSH_MODIFIED_LIST == 3
    assert memory_api.MEMORY_PURGE_LOW_PRIORITY_STANDBY_LIST == 5


def test_exception_safety():
    snaps = [
        {"available": 1000, "used": 5000, "total": 6000, "percent": 80},
        {"available": 2000, "used": 4000, "total": 6000, "percent": 70},
    ]
    api = FlakyAPI()
    c = Cleaner(api=api)
    c.snapshot_fn = lambda: snaps.pop(0)

    # 单步失败不应导致整个清理崩溃，且 finally 的 disable 必须执行
    res = c.deep_clean()
    assert "disable" in api.calls
    assert res["freed_bytes"] == 1000
