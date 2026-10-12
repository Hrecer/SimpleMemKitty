"""设置对话框：自动清理（开关/间隔/阈值）+ 语言。"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QSpinBox, QLabel, QRadioButton, QDialogButtonBox,
)
from PyQt5.QtCore import pyqtSignal


class SettingsDialog(QDialog):
    settings_saved = pyqtSignal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("设置")
        self.setMinimumWidth(340)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)

        # 自动清理
        auto_group = QGroupBox("自动清理")
        auto_layout = QVBoxLayout()
        self.enable_cb = QCheckBox("开启自动清理（内存超阈值时按间隔清理）")
        self.enable_cb.stateChanged.connect(self._toggle_controls)
        auto_layout.addWidget(self.enable_cb)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("每隔"))
        self.interval_sb = QSpinBox()
        self.interval_sb.setRange(1, 120)
        self.interval_sb.setSuffix(" 分钟")
        interval_row.addWidget(self.interval_sb)
        interval_row.addStretch()
        auto_layout.addLayout(interval_row)

        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("当内存占用超过"))
        self.threshold_sb = QSpinBox()
        self.threshold_sb.setRange(50, 99)
        self.threshold_sb.setSuffix(" %")
        threshold_row.addWidget(self.threshold_sb)
        threshold_row.addStretch()
        auto_layout.addLayout(threshold_row)

        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)

        # 语言
        lang_group = QGroupBox("语言")
        lang_layout = QHBoxLayout()
        self.zh_rb = QRadioButton("中文")
        self.en_rb = QRadioButton("English")
        lang_layout.addWidget(self.zh_rb)
        lang_layout.addWidget(self.en_rb)
        lang_layout.addStretch()
        lang_group.setLayout(lang_layout)
        layout.addWidget(lang_group)

        # 按钮
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._save)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _toggle_controls(self):
        enabled = self.enable_cb.isChecked()
        self.interval_sb.setEnabled(enabled)
        self.threshold_sb.setEnabled(enabled)

    def _load(self):
        self.enable_cb.setChecked(bool(self.settings.get("auto_clean_enabled", False)))
        self.interval_sb.setValue(int(self.settings.get("clean_interval_minutes", 5)))
        self.threshold_sb.setValue(int(self.settings.get("mem_threshold_percent", 80)))
        lang = self.settings.get("language", "zh")
        self.zh_rb.setChecked(lang != "en")
        self.en_rb.setChecked(lang == "en")
        self._toggle_controls()

    def _save(self):
        self.settings.set("auto_clean_enabled", self.enable_cb.isChecked())
        self.settings.set("clean_interval_minutes", self.interval_sb.value())
        self.settings.set("mem_threshold_percent", self.threshold_sb.value())
        self.settings.set("language", "en" if self.en_rb.isChecked() else "zh")
        self.settings.save()
        self.settings_saved.emit()
        self.accept()
