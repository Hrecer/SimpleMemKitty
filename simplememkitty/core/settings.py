"""配置持久化（JSON 文件，不依赖 Qt，便于单元测试）。

相比原版使用 QSettings，这里改用纯 JSON + 临时目录友好的实现，
使得配置逻辑可以完全脱离 GUI / 注册表进行单元测试。
"""

import json
import os

DEFAULTS = {
    "auto_clean_enabled": False,
    "clean_interval_minutes": 5,
    "mem_threshold_percent": 80,
    "language": "zh",
    "deep_clean_on_startup": False,
}


class Settings:
    """简单的键值配置，带默认值合并与类型校正，可持久化到 JSON 文件。"""

    def __init__(self, path=None):
        if path is None:
            base = os.path.expanduser("~")
            path = os.path.join(base, ".simplememkitty", "settings.json")
        self.path = path
        self._data = dict(DEFAULTS)

    # ---- 持久化 ----
    def load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                if isinstance(raw, dict):
                    for key, default in DEFAULTS.items():
                        if key in raw:
                            # 类型校正（防止手动改成字符串等）
                            try:
                                self._data[key] = type(default)(raw[key])
                            except (TypeError, ValueError):
                                self._data[key] = default
        except Exception:
            # 配置损坏 -> 回退到默认
            self._data = dict(DEFAULTS)
        return self

    def save(self):
        try:
            parent = os.path.dirname(self.path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except Exception:
            # 保存失败不应影响程序运行
            pass
        return self

    # ---- 访问 ----
    def get(self, key, default=None):
        if key in DEFAULTS:
            return self._data.get(key, DEFAULTS[key])
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def update(self, mapping):
        self._data.update(mapping)

    def as_dict(self):
        return dict(self._data)
