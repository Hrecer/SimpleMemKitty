"""自动清理控制器（纯逻辑，可测试）。

职责：
- 根据配置判断"是否应该清理"（开关 + 阈值）。
- 按冷却时间避免频繁触发（合并自 Ultra 的 15s 冷却）。
- 通过 on_trigger 回调真正执行清理，自身不依赖 GUI / 定时器实现，
  以便在不同环境（Qt 定时器、测试中的假时钟）下复用。

与原 Ultra 实现差异：
- 阈值/间隔/冷却都来自 Settings，行为更清晰。
- 逻辑与 UI 解耦，便于单元测试（见 tests/test_auto_cleaner.py）。
"""

import time


class AutoCleaner:
    def __init__(self, settings, on_trigger, clock=None, cooldown_seconds=15):
        """
        :param settings: 提供 get(key, default) 的对象（如 core.settings.Settings）
        :param on_trigger: 触发清理时调用的回调（无参数）
        :param clock: 返回当前时间戳（秒）的可调用对象，便于测试注入假时钟
        :param cooldown_seconds: 两次自动清理之间的最小间隔
        """
        self.settings = settings
        self.on_trigger = on_trigger
        self.clock = clock or time.time
        self.cooldown_seconds = cooldown_seconds
        # 初始化为一个足够早的时间，保证首次触发不会被误判为"冷却中"
        self.last_trigger = -1e18

    # ---- 配置读取 ----
    def is_enabled(self) -> bool:
        return bool(self.settings.get("auto_clean_enabled", False))

    def threshold(self) -> int:
        try:
            return int(self.settings.get("mem_threshold_percent", 80))
        except (TypeError, ValueError):
            return 80

    def interval_ms(self) -> int:
        try:
            minutes = max(1, int(self.settings.get("clean_interval_minutes", 5)))
        except (TypeError, ValueError):
            minutes = 5
        return minutes * 60 * 1000

    # ---- 判断 ----
    def should_clean(self, mem_percent: float) -> bool:
        if not self.is_enabled():
            return False
        return mem_percent > self.threshold()

    # ---- 触发 ----
    def tick(self, mem_percent: float) -> bool:
        """由定时器周期性调用。返回本次是否真正触发了清理。"""
        if not self.should_clean(mem_percent):
            return False
        now = self.clock()
        if now - self.last_trigger < self.cooldown_seconds:
            return False
        self.last_trigger = now
        self.on_trigger()
        return True
