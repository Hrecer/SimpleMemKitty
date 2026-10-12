"""主窗口：内存状态展示 + 一键/深度清理 + 设置 + 系统托盘。

相比原 SimpleMemKitty.py：
- 合并了 Ultra 的实用能力：自动清理（后台定时器）、设置对话框、清理结果托盘通知、
  配置持久化、语言切换，但**不**引入加速球水波动画等花哨 UI。
- 深度清理改用 core.cleaner.Cleaner（已修复慢 / 内存跳变问题）。
"""

import logging

from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QMessageBox, QSystemTrayIcon, QMenu, QAction, QStyle, QProgressBar,
)

from ..core.cleaner import Cleaner
from ..core.stats import get_memory_snapshot
from ..auto.auto_cleaner import AutoCleaner
from .settings_dialog import SettingsDialog

TRANSLATIONS = {
    "zh": {
        "window_title": "SimpleMemKitty",
        "memory_status": "内存状态",
        "total": "总计:",
        "used": "已用:",
        "available": "可用:",
        "usage": "使用率:",
        "one_click": "一键清理",
        "deep_clean": "深度清理",
        "settings": "设置",
        "show_window": "显示窗口",
        "exit": "退出",
        "language": "语言",
        "chinese": "中文",
        "english": "English",
        "insufficient": "权限不足",
        "privilege_warning": "程序未以管理员权限运行，系统级清理可能不完整。\n建议以管理员身份重启。",
        "auto_on": "自动清理：开",
        "auto_off": "自动清理：关",
        "cleaned": "清理完成，释放约 %.1f MB 内存",
        "cleaned_none": "系统内存已经很干净",
        "deep_done": "深度清理完成，释放约 %.1f MB 内存",
        "cleaning": "正在清理…",
    },
    "en": {
        "window_title": "SimpleMemKitty",
        "memory_status": "Memory Status",
        "total": "Total:",
        "used": "Used:",
        "available": "Available:",
        "usage": "Usage:",
        "one_click": "One-Click Clean",
        "deep_clean": "Deep Clean",
        "settings": "Settings",
        "show_window": "Show Window",
        "exit": "Exit",
        "language": "Language",
        "chinese": "中文",
        "english": "English",
        "insufficient": "Insufficient Privilege",
        "privilege_warning": "Not running as admin; system-level cleanup may be incomplete.\nRestart as admin is recommended.",
        "auto_on": "Auto Clean: ON",
        "auto_off": "Auto Clean: OFF",
        "cleaned": "Cleaned, freed about %.1f MB",
        "cleaned_none": "Memory is already clean",
        "deep_done": "Deep clean done, freed about %.1f MB",
        "cleaning": "Cleaning…",
    },
}


class DeepCleanThread(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, cleaner):
        super().__init__()
        self.cleaner = cleaner

    def run(self):
        result = self.cleaner.deep_clean()
        self.finished.emit(result)


class MainWindow(QMainWindow):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.language = settings.get("language", "zh")
        self.cleaner = Cleaner()

        self.setWindowTitle(self._tr("window_title"))
        self.setMinimumSize(380, 200)

        self._setup_ui()
        self._setup_tray()
        self._check_admin()

        # 内存信息刷新
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_memory_info)
        self.timer.start(1000)

        # 自动清理
        self.auto_cleaner = AutoCleaner(self.settings, self._auto_trigger)
        self.auto_timer = QTimer()
        self.auto_timer.timeout.connect(self._auto_tick)
        self._setup_auto_timer()

        self.update_memory_info()

    # ---------------- 翻译 ----------------
    def _tr(self, key):
        return TRANSLATIONS[self.language].get(key, key)

    def _retranslate(self):
        self.setWindowTitle(self._tr("window_title"))
        self.mem_group.setTitle(self._tr("memory_status"))
        self.total_label.setText(self._tr("total"))
        self.used_label.setText(self._tr("used"))
        self.avail_label.setText(self._tr("available"))
        self.percent_label.setText(self._tr("usage"))
        self.one_click_btn.setText(self._tr("one_click"))
        self.deep_btn.setText(self._tr("deep_clean"))
        self.settings_btn.setText(self._tr("settings"))
        self._update_auto_label()

    # ---------------- UI ----------------
    def _setup_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout(central)
        self.setCentralWidget(central)

        self.mem_group = QGroupBox(self._tr("memory_status"))
        mem_layout = QVBoxLayout()

        info_layout = QHBoxLayout()
        self.total_label = QLabel(self._tr("total"))
        self.used_label = QLabel(self._tr("used"))
        self.avail_label = QLabel(self._tr("available"))
        self.percent_label = QLabel(self._tr("usage"))
        for lbl in (self.total_label, self.used_label, self.avail_label, self.percent_label):
            f = lbl.font()
            f.setPointSize(9)
            lbl.setFont(f)
            info_layout.addWidget(lbl)

        self.mem_bar = QProgressBar()
        self.mem_bar.setMaximum(100)
        self.mem_bar.setMinimumHeight(20)

        mem_layout.addLayout(info_layout)
        mem_layout.addWidget(self.mem_bar)
        self.mem_group.setLayout(mem_layout)
        main_layout.addWidget(self.mem_group)

        # 自动清理状态
        self.auto_label = QLabel()
        self._update_auto_label()
        main_layout.addWidget(self.auto_label)

        # 按钮
        btn_layout = QHBoxLayout()
        self.one_click_btn = QPushButton(self._tr("one_click"))
        self.deep_btn = QPushButton(self._tr("deep_clean"))
        self.settings_btn = QPushButton(self._tr("settings"))
        for b in (self.one_click_btn, self.deep_btn, self.settings_btn):
            b.setMinimumHeight(38)
        self.one_click_btn.clicked.connect(lambda: self.one_click_clean(notify=True))
        self.deep_btn.clicked.connect(self.deep_clean)
        self.settings_btn.clicked.connect(self.open_settings)
        btn_layout.addWidget(self.one_click_btn)
        btn_layout.addWidget(self.deep_btn)
        btn_layout.addWidget(self.settings_btn)
        main_layout.addLayout(btn_layout)

        # 语言菜单
        self._setup_language_menu()

    def _setup_language_menu(self):
        self.menuBar().clear()
        lang_menu = self.menuBar().addMenu(self._tr("language"))
        zh = QAction(self._tr("chinese"), self)
        zh.triggered.connect(lambda: self._switch_language("zh"))
        en = QAction(self._tr("english"), self)
        en.triggered.connect(lambda: self._switch_language("en"))
        lang_menu.addAction(zh)
        lang_menu.addAction(en)

    def _switch_language(self, lang):
        self.language = lang
        self.settings.set("language", lang)
        self.settings.save()
        self._retranslate()
        self._setup_language_menu()
        self._setup_tray_menu()
        self.update_memory_info()

    def _update_auto_label(self):
        if self.settings.get("auto_clean_enabled", False):
            self.auto_label.setText(self._tr("auto_on"))
        else:
            self.auto_label.setText(self._tr("auto_off"))

    # ---------------- 托盘 ----------------
    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        self._setup_tray_menu()
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _setup_tray_menu(self):
        tray_menu = QMenu()
        show_action = QAction(self._tr("show_window"), self)
        show_action.triggered.connect(self.show)
        settings_action = QAction(self._tr("settings"), self)
        settings_action.triggered.connect(self.open_settings)
        quit_action = QAction(self._tr("exit"), self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(show_action)
        tray_menu.addAction(settings_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()

    # ---------------- 权限 ----------------
    def _check_admin(self):
        try:
            is_admin = __import__("ctypes").windll.shell32.IsUserAnAdmin()
        except Exception:
            is_admin = False
        if not is_admin:
            QMessageBox.warning(self, self._tr("insufficient"), self._tr("privilege_warning"))

    # ---------------- 内存信息 ----------------
    def update_memory_info(self):
        try:
            mem = get_memory_snapshot()
        except Exception as exc:  # noqa: BLE001
            logging.debug("获取内存信息失败: %s", exc)
            return
        total_gb = mem["total"] / (1024 ** 3)
        used_gb = mem["used"] / (1024 ** 3)
        avail_gb = mem["available"] / (1024 ** 3)
        self.total_label.setText(f"{self._tr('total')} {total_gb:.2f} GB")
        self.used_label.setText(f"{self._tr('used')} {used_gb:.2f} GB")
        self.avail_label.setText(f"{self._tr('available')} {avail_gb:.2f} GB")
        self.percent_label.setText(f"{self._tr('usage')} {mem['percent']:.1f} %")
        self.mem_bar.setValue(int(mem["percent"]))

    # ---------------- 清理动作 ----------------
    def one_click_clean(self, notify=True):
        result = self.cleaner.light_clean()
        self.update_memory_info()
        if notify:
            self._notify_clean(result, self._tr("cleaned"), self._tr("cleaned_none"))

    def deep_clean(self):
        self.deep_thread = DeepCleanThread(self.cleaner)
        self.deep_thread.finished.connect(self._on_deep_finished)
        self.deep_thread.start()

    def _on_deep_finished(self, result):
        self.update_memory_info()
        self._notify_clean(result, self._tr("deep_done"), self._tr("cleaned_none"))

    def _notify_clean(self, result, fmt, none_msg):
        mb = result["freed_bytes"] / (1024 * 1024)
        if mb >= 1:
            self.tray_icon.showMessage("SimpleMemKitty", fmt % mb,
                                       QSystemTrayIcon.Information, 2000)
        else:
            self.tray_icon.showMessage("SimpleMemKitty", none_msg,
                                       QSystemTrayIcon.Information, 1500)

    def _auto_trigger(self):
        # 自动清理：轻量清理，静默（不打扰用户）
        self.one_click_clean(notify=False)

    def _auto_tick(self):
        try:
            mem = get_memory_snapshot()
        except Exception:  # noqa: BLE001
            return
        self.auto_cleaner.tick(mem["percent"])

    def _setup_auto_timer(self):
        if self.settings.get("auto_clean_enabled", False):
            self.auto_timer.start(self.auto_cleaner.interval_ms())
        else:
            self.auto_timer.stop()

    # ---------------- 设置 ----------------
    def open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        dlg.settings_saved.connect(self._on_settings_saved)
        dlg.exec()

    def _on_settings_saved(self):
        self.language = self.settings.get("language", "zh")
        self._retranslate()
        self._setup_language_menu()
        self._setup_tray_menu()
        self._setup_auto_timer()
        self.update_memory_info()

    # ---------------- 退出 ----------------
    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def quit_app(self):
        self.timer.stop()
        self.auto_timer.stop()
        self.tray_icon.hide()
        from PyQt5.QtWidgets import QApplication
        QApplication.quit()
