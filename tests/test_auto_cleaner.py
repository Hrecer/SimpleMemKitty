from simplememkitty.auto.auto_cleaner import AutoCleaner


class FakeSettings:
    def __init__(self, d):
        self.d = d

    def get(self, k, default=None):
        return self.d.get(k, default)


def test_disabled_never_triggers():
    ac = AutoCleaner(FakeSettings({"auto_clean_enabled": False}), lambda: None)
    assert ac.tick(99) is False


def test_threshold_gate():
    ac = AutoCleaner(
        FakeSettings({"auto_clean_enabled": True, "mem_threshold_percent": 80}),
        lambda: None,
        clock=lambda: 0,
    )
    assert ac.tick(75) is False
    assert ac.tick(85) is True


def test_cooldown():
    calls = []
    ac = AutoCleaner(
        FakeSettings({"auto_clean_enabled": True, "mem_threshold_percent": 80}),
        lambda: calls.append(1),
        clock=lambda: 100,
    )
    assert ac.tick(90) is True  # 第一次触发
    ac.clock = lambda: 105     # 5 秒后，仍在 15s 冷却内
    assert ac.tick(90) is False
    ac.clock = lambda: 120     # 20 秒后，超过冷却
    assert ac.tick(90) is True
    assert len(calls) == 2


def test_interval_ms_clamped():
    ac = AutoCleaner(FakeSettings({"clean_interval_minutes": 5}), lambda: None)
    assert ac.interval_ms() == 5 * 60 * 1000
    ac2 = AutoCleaner(FakeSettings({"clean_interval_minutes": 0}), lambda: None)
    assert ac2.interval_ms() == 60 * 1000  # 下限 1 分钟
