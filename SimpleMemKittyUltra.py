# -*- coding: utf-8 -*-
"""
SimpleMemKittyUltra
"""

import sys
import os
import math
import time
import json
import psutil
import ctypes
import subprocess
import winreg as reg
from typing import Tuple, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QSystemTrayIcon, QMenu, QCheckBox, QSpinBox, QGroupBox,
    QRadioButton, QDialog, QFrame
)
from PySide6.QtCore import (
    Qt, Signal, QTimer, QObject, QThread, QRect, QPoint,
    QPropertyAnimation, QEasingCurve, QEvent
)
from PySide6.QtGui import (
    QPainter, QColor, QFont, QIcon, QPixmap, QPen, QBrush,
    QLinearGradient, QRadialGradient, QPainterPath, QAction
)
# 内存中的默认配置
DEFAULT_CONFIG = {
    "auto_clean_enabled": False,
    "clean_interval_minutes": 5,
    "mem_threshold_percent": 80,
    "display_metric": "mem"
}

psutil.cpu_percent(interval=None)

def get_system_stats() -> Dict[str, Any]:
    return {
        'cpu_percent': psutil.cpu_percent(interval=None),
        'mem_info': psutil.virtual_memory()
    }

def clean_memory_windows() -> Tuple[bool, Any]:
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_SET_QUOTA = 0x0100
    system_whitelist = {
        'system', 'smss.exe', 'csrss.exe', 'wininit.exe', 'winlogon.exe',
        'services.exe', 'lsass.exe'
    }
    own_pid = os.getpid()
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    ntdll = ctypes.WinDLL('ntdll.dll')

    try:
        ntdll.NtSetSystemInformation.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
        ntdll.NtSetSystemInformation.restype = ctypes.c_long
    except AttributeError:
        return (False, "无法访问系统内核")

    mem_before = psutil.virtual_memory().used
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() in system_whitelist or proc.pid == own_pid:
                continue
            handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, False, proc.pid)
            if handle:
                psapi.EmptyWorkingSet(handle)
                kernel32.CloseHandle(handle)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    system_memory_list_info = 80
    modified_page_list_class = ctypes.c_int(8)
    ntdll.NtSetSystemInformation(system_memory_list_info, ctypes.byref(modified_page_list_class), ctypes.sizeof(modified_page_list_class))

    system_purge_standby_list = 3
    ntdll.NtSetSystemInformation(system_purge_standby_list, None, 0)

    time.sleep(0.5)
    mem_after = psutil.virtual_memory().used
    freed_mb = (mem_before - mem_after) / (1024 * 1024)
    if freed_mb < 0:
        freed_mb = 0
    return (True, {'freed_mb': freed_mb})

def clean_memory() -> Tuple[bool, Any]:
    platform = sys.platform
    if platform == "win32":
        try:
            success, result = clean_memory_windows()
            if success:
                result['cleaned_count'] = result.get('cleaned_count', 'N/A')
                return True, result
            else:
                return False, result
        except Exception as e:
            return (False, f"Windows清理错误: {e}")
    elif platform == "linux":
        try:
            mem_before = psutil.virtual_memory().used
            subprocess.run(['sync'], check=True, capture_output=True)
            with open('/proc/sys/vm/drop_caches', 'w') as f:
                f.write('3\n')
            time.sleep(0.5)
            mem_after = psutil.virtual_memory().used
            freed_mb = (mem_before - mem_after) / (1024 * 1024)
            if freed_mb < 0:
                freed_mb = 0
            return (True, {'freed_mb': freed_mb, 'cleaned_count': 'N/A'})
        except (PermissionError, subprocess.CalledProcessError) as e:
            return (False, f"Linux清理失败: {e}")
    elif platform == "darwin":
        return (False, "macOS无需手动清理内存")
    else:
        return (False, f"不支持的系统: {platform}")

APP_NAME = "SimpleMemKittyUltra"



def show_message(title: str, text: str, icon_type=QMessageBox.Information, parent=None):
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setIcon(icon_type)
    msg_box.setStandardButtons(QMessageBox.Ok)
    msg_box.exec()

class NotificationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.Tool |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 30, 30, 0.9);
                color: white;
                border-radius: 6px;
            }
        """)

        self.layout = QVBoxLayout(self)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("padding: 8px 12px; font-size: 10pt;")
        self.layout.addWidget(self.label)

        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(400)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.finished.connect(self.close)

    def show_notification(self, text: str, position_rect: QRect, duration=2500):
        self.label.setText(text)
        self.adjustSize()

        x = position_rect.x() + (position_rect.width() - self.width()) / 2
        y = position_rect.y() - self.height() - 10

        screen = self.screen()
        if screen:
            screen_geo = screen.availableGeometry()
            if x < screen_geo.left():
                x = screen_geo.left()
            if x + self.width() > screen_geo.right():
                x = screen_geo.right() - self.width()
            if y < screen_geo.top():
                y = position_rect.bottom() + 10

        self.move(int(x), int(y))
        self.show()
        QTimer.singleShot(duration, self.animation.start)



class AcceleratorBall(QWidget):
    show_main_window_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(90, 90)

        self._is_dragging = False
        self._drag_start_position = QPoint()

        self.raw_cpu = 0
        self.raw_mem = 0
        self.smoothed_cpu = 0.0
        self.smoothed_mem = 0.0
        self.wave1_offset = 0
        self.wave2_offset = 0.8

        self._setup_drawing_resources()

        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.update_system_data)
        self.data_timer.start(1000)

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.tick_animation)
        self.animation_timer.start(16)

        self.update_system_data()

    def _setup_drawing_resources(self):
        self.bg_brush = QBrush(QColor("#E0E0E0"))
        self.text_pen = QPen(QColor(50, 50, 50))
        self.mem_font = QFont("Arial", 14, QFont.Bold)
        self.cpu_font = QFont("Arial", 8)
        self.wave_highlight_pen = QPen(QColor(100, 180, 255, 180), 1.5)
        self.outer_border_pen = QPen(QColor(0, 0, 0, 30), 2)

    def update_system_data(self):
        stats = get_system_stats()
        self.raw_cpu = stats['cpu_percent']
        self.raw_mem = stats['mem_info'].percent

    def tick_animation(self):
        self.smoothed_cpu = self.smoothed_cpu * 0.95 + self.raw_cpu * 0.05
        self.smoothed_mem = self.smoothed_mem * 0.95 + self.raw_mem * 0.05
        self.wave1_offset = (self.wave1_offset + 0.05) % (2 * math.pi)
        self.wave2_offset = (self.wave2_offset + 0.07) % (2 * math.pi)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        painter.setPen(Qt.NoPen)
        painter.setBrush(self.bg_brush)
        painter.drawEllipse(rect)

        inner_shadow_gradient = QRadialGradient(rect.center(), rect.width() / 2)
        inner_shadow_gradient.setColorAt(0.85, QColor(0, 0, 0, 0))
        inner_shadow_gradient.setColorAt(1.0, QColor(0, 0, 0, 40))
        painter.setBrush(inner_shadow_gradient)
        painter.drawEllipse(rect)

        clip_path = QPainterPath()
        clip_path.addEllipse(rect)
        painter.setClipPath(clip_path)

        water_level = rect.height() * (1 - self.smoothed_mem / 100.0)
        water_path = QPainterPath()
        water_path.moveTo(rect.left(), rect.bottom())
        water_path.lineTo(rect.left(), water_level)

        for x in range(rect.width() + 1):
            wave1 = 3 * math.sin(x * 0.04 + self.wave1_offset)
            wave2 = 2 * math.sin(x * 0.06 + self.wave2_offset)
            water_path.lineTo(x, water_level + wave1 + wave2)

        water_path.lineTo(rect.right(), rect.bottom())
        water_path.closeSubpath()

        water_gradient = QLinearGradient(rect.center().x(), water_level, rect.center().x(), rect.bottom())
        water_gradient.setColorAt(0, QColor(60, 170, 255, 200))
        water_gradient.setColorAt(1, QColor(20, 120, 230, 255))
        painter.fillPath(water_path, water_gradient)

        highlight_path = QPainterPath()
        highlight_path.moveTo(rect.left(), water_level)
        for x in range(rect.width() + 1):
            wave1 = 3 * math.sin(x * 0.04 + self.wave1_offset)
            wave2 = 2 * math.sin(x * 0.06 + self.wave2_offset)
            highlight_path.lineTo(x, water_level + wave1 + wave2)
        painter.setPen(self.wave_highlight_pen)
        painter.drawPath(highlight_path)

        painter.setClipping(False)

        painter.setPen(self.text_pen)
        painter.setFont(self.mem_font)
        painter.drawText(rect, Qt.AlignCenter, f"{int(self.smoothed_mem)}%")
        painter.setFont(self.cpu_font)
        painter.drawText(rect.adjusted(0, -25, 0, -25), Qt.AlignCenter, f"CPU: {int(self.smoothed_cpu)}%")

        painter.setBrush(Qt.NoBrush)
        painter.setPen(self.outer_border_pen)
        painter.drawEllipse(rect.adjusted(1, 1, -1, -1))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._drag_start_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._is_dragging:
            self.move(event.globalPosition().toPoint() - self._drag_start_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.perform_cleanup()
        event.accept()

    def perform_cleanup(self):
        success, result_data = clean_memory()
        if success:
            if isinstance(result_data, dict) and 'freed_mb' in result_data:
                freed = result_data['freed_mb']
                message = f"深度清理完成！\n成功释放了约 {freed:.1f} MB 内存。" if freed >= 1 else "系统状态良好，无需深度清理。"
                show_message("内存清理", message, QMessageBox.Information, self)
            else:
                show_message("内存清理", "操作成功！", QMessageBox.Information, self)
        else:
            show_message("清理失败", str(result_data), QMessageBox.Warning, self)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        show_main_action = menu.addAction("显示主窗口")
        quit_action = menu.addAction("退出程序")
        action = menu.exec(self.mapToGlobal(event.pos()))

        if action == show_main_action:
            self.show_main_window_requested.emit()
        elif action == quit_action:
            QApplication.quit()

class SettingsWindow(QWidget):
    settings_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.setFixedSize(350, 300)

        main_layout = QVBoxLayout(self)

        display_group = QGroupBox("托盘图标显示设置")
        display_layout = QHBoxLayout()
        display_layout.addWidget(QLabel("优先显示:"))
        self.mem_radio = QRadioButton("内存使用率")
        self.cpu_radio = QRadioButton("CPU使用率")
        display_layout.addWidget(self.mem_radio)
        display_layout.addWidget(self.cpu_radio)
        display_layout.addStretch()
        display_group.setLayout(display_layout)
        main_layout.addWidget(display_group)

        auto_clean_group = QGroupBox("自动清理设置")
        group_layout = QVBoxLayout()
        self.enable_checkbox = QCheckBox("开启自动清理")
        self.enable_checkbox.stateChanged.connect(self.toggle_controls)
        group_layout.addWidget(self.enable_checkbox)

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("当内存占用超过阈值时，每隔"))
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setMinimum(1)
        self.interval_spinbox.setMaximum(120)
        self.interval_spinbox.setSuffix(" 分钟")
        interval_layout.addWidget(self.interval_spinbox)
        interval_layout.addStretch()
        group_layout.addLayout(interval_layout)

        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("清理阈值：内存占用超过"))
        self.threshold_spinbox = QSpinBox()
        self.threshold_spinbox.setMinimum(50)
        self.threshold_spinbox.setMaximum(99)
        self.threshold_spinbox.setSuffix(" %")
        threshold_layout.addWidget(self.threshold_spinbox)
        threshold_layout.addStretch()
        group_layout.addLayout(threshold_layout)

        auto_clean_group.setLayout(group_layout)
        main_layout.addWidget(auto_clean_group)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.save_button = QPushButton("保存")
        self.cancel_button = QPushButton("取消")
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

        self.save_button.clicked.connect(self.save_and_close)
        self.cancel_button.clicked.connect(self.close)

        self.load_settings()

    def load_settings(self):
        # 从主应用程序的配置中加载设置
        app = QApplication.instance()
        if hasattr(app, 'config'):
            config = app.config
        else:
            config = DEFAULT_CONFIG.copy()
        
        self.enable_checkbox.setChecked(config.get("auto_clean_enabled", False))
        self.interval_spinbox.setValue(config.get("clean_interval_minutes", 5))
        self.threshold_spinbox.setValue(config.get("mem_threshold_percent", 80))

        if config.get("display_metric", "mem") == "cpu":
            self.cpu_radio.setChecked(True)
        else:
            self.mem_radio.setChecked(True)

        self.toggle_controls()

    def save_and_close(self):
        # 直接修改主应用程序的配置
        from SimpleMemKittyUltra import MainApplication
        # 假设主应用程序实例是QApplication.instance()
        app = QApplication.instance()
        if hasattr(app, 'config'):
            app.config.update({
                "auto_clean_enabled": self.enable_checkbox.isChecked(),
                "clean_interval_minutes": self.interval_spinbox.value(),
                "mem_threshold_percent": self.threshold_spinbox.value(),
                "display_metric": "cpu" if self.cpu_radio.isChecked() else "mem"
            })
        self.settings_saved.emit()
        self.close()

    def toggle_controls(self):
        is_enabled = self.enable_checkbox.isChecked()
        self.interval_spinbox.setEnabled(is_enabled)
        self.threshold_spinbox.setEnabled(is_enabled)

    def showEvent(self, event):
        self.load_settings()
        super().showEvent(event)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("系统性能监视器")
        self.setGeometry(200, 200, 320, 180)

        self.layout = QVBoxLayout(self)
        self.cpu_label = QLabel()
        self.mem_label = QLabel()
        self.clean_button = QPushButton("一键加速")

        self.layout.addWidget(self.cpu_label)
        self.layout.addWidget(self.mem_label)
        self.layout.addWidget(self.clean_button)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_info)
        self.timer.start(1000)

        self.update_info()

    def update_info(self):
        stats = get_system_stats()
        cpu = stats['cpu_percent']
        mem = stats['mem_info']
        mem_total_gb = mem.total / (1024 ** 3)
        mem_used_gb = mem.used / (1024 ** 3)

        self.cpu_label.setText(f"CPU 使用率: {cpu}%")
        self.mem_label.setText(f"内存: {mem_used_gb:.2f} GB / {mem_total_gb:.2f} GB ({mem.percent}%)")

    def show_and_raise(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

class StatsWorker(QObject):
    stats_updated = Signal(float, float)

    def __init__(self):
        super().__init__()
        self.running = True

    def run(self):
        while self.running:
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory().percent
            if not self.running:
                break
            self.stats_updated.emit(cpu, mem)

    def stop(self):
        self.running = False

class TrayManager(QSystemTrayIcon):
    show_main_window_requested = Signal()
    show_settings_requested = Signal()
    cleanup_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_notification = None

        self.font = QFont("Segoe UI", 22, QFont.Bold)
        self.bg_color = QColor(0, 0, 0, 0)
        self.progress_bg_pen = QPen(QColor(0, 0, 0, 50), 5)
        self.progress_pen = QPen(QColor(), 5.5)
        self.text_pen = QPen(QColor(0, 0, 0))

        self.menu = QMenu()
        self.menu.addAction("显示主窗口").triggered.connect(self.show_main_window_requested.emit)
        self.menu.addAction("设置").triggered.connect(self.show_settings_requested.emit)
        self.menu.addSeparator()
        self.menu.addAction("退出").triggered.connect(self.quit_requested.emit)
        self.setContextMenu(self.menu)

        self.activated.connect(self.on_activated)

        self.thread = QThread()
        self.worker = StatsWorker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.stats_updated.connect(self.update_icon)
        self.thread.start()

        self.update_icon(0, 0)
        self.show()

    def on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.cleanup_requested.emit()

    def show_custom_notification(self, message):
        if self.current_notification:
            self.current_notification.close()

        tray_icon_rect = self.geometry()
        if not tray_icon_rect.isValid():
            screen = self.parent().primaryScreen()
            if screen:
                screen_geo = screen.geometry()
                tray_icon_rect = QRect(screen_geo.width() - 150, screen_geo.height() - 60, 22, 22)

        notification = NotificationWidget()
        self.current_notification = notification
        notification.destroyed.connect(self._clear_notification_ref)
        notification.show_notification(message, tray_icon_rect)

    def _clear_notification_ref(self):
        self.current_notification = None

    def update_icon(self, cpu_val, mem_val):
        # 从主应用程序获取配置
        app = QApplication.instance()
        if hasattr(app, 'config'):
            display_metric = app.config.get("display_metric", "mem")
        else:
            display_metric = "mem"

        if display_metric == "cpu":
            primary_val, primary_name, secondary_val, secondary_name = cpu_val, "CPU", mem_val, "内存"
        else:
            primary_val, primary_name, secondary_val, secondary_name = mem_val, "内存", cpu_val, "CPU"

        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = pixmap.rect().adjusted(8, 8, -8, -8)

        bg_pen = QPen(QColor(0, 0, 0, 50), 5)
        painter.setPen(bg_pen)
        painter.drawEllipse(rect)

        if primary_val < 60:
            progress_color = QColor("#27AE60")
        elif primary_val < 85:
            progress_color = QColor("#F39C12")
        else:
            progress_color = QColor("#C0392B")

        progress_pen = QPen(progress_color, 5.5)
        painter.setPen(progress_pen)
        span_angle = primary_val / 100.0 * 360 * 16
        painter.drawArc(rect, 90 * 16, -span_angle)

        text_pen = QPen(QColor(0, 0, 0))
        painter.setPen(text_pen)
        font = QFont("Segoe UI", 22, QFont.Bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, str(int(primary_val)))
        painter.end()

        self.setIcon(QIcon(pixmap))
        self.setToolTip(f"{primary_name}: {int(primary_val)}%\n{secondary_name}: {int(secondary_val)}%\n(双击加速)")

    def stop_worker_thread(self):
        if hasattr(self, 'thread') and self.thread.isRunning():
            if hasattr(self, 'worker'):
                self.worker.stop()
            self.thread.quit()
            self.thread.wait(2000)

    def stop_and_quit(self):
        self.parent().quit()

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    if sys.platform == 'win32' and not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit(0)

class MainApplication(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)  # 关闭窗口后不退出程序

        self.is_cleaning = False
        self.last_cleanup_time = 0
        self.cleanup_cooldown_seconds = 15

        self.config = DEFAULT_CONFIG.copy()
        self.main_window = MainWindow()
        self.settings_window = SettingsWindow()
        self.tray_manager = TrayManager(self)
        
        # 启动时显示主窗口
        self.main_window.show_and_raise()
        
        # 连接信号
        self.tray_manager.show_main_window_requested.connect(self.main_window.show_and_raise)
        self.tray_manager.show_settings_requested.connect(self.show_settings)
        self.tray_manager.cleanup_requested.connect(self.perform_cleanup_action)
        self.tray_manager.quit_requested.connect(self.quit)
        self.main_window.clean_button.clicked.connect(self.perform_cleanup_action)
        self.settings_window.settings_saved.connect(self.reload_config_and_timer)

        self.auto_clean_timer = QTimer(self)
        self.auto_clean_timer.timeout.connect(self.check_and_auto_clean)
        self.update_timer_interval()

    def perform_cleanup_action(self):
        current_time = time.time()

        if self.is_cleaning:
            self.tray_manager.show_custom_notification("正在清理中，请稍候...")
            return

        if current_time - self.last_cleanup_time < self.cleanup_cooldown_seconds:
            self.tray_manager.show_custom_notification("系统已经很干净啦，休息一下吧~")
            return

        self.is_cleaning = True
        success, result_data = clean_memory()

        if success:
            self.last_cleanup_time = current_time
            if isinstance(result_data, dict) and 'freed_mb' in result_data:
                freed = result_data['freed_mb']
                if freed >= 1:
                    message = f"已腾出 <font color='#3498DB'><b>{freed:.1f}MB</b></font> 内存"
                else:
                    message = "系统状态良好，无需清理"
                self.tray_manager.show_custom_notification(message)
        else:
            message = f"清理失败: {str(result_data)}"
            self.tray_manager.show_custom_notification(message)

        QTimer.singleShot(3000, lambda: setattr(self, 'is_cleaning', False))

    def show_settings(self):
        self.settings_window.show()
        self.settings_window.activateWindow()

    def reload_config_and_timer(self):
        # 配置已经在内存中，无需重新加载
        self.update_timer_interval()

    def update_timer_interval(self):
        if self.config.get("auto_clean_enabled", False):
            interval_ms = self.config.get("clean_interval_minutes", 5) * 60 * 1000
            self.auto_clean_timer.start(interval_ms)
        else:
            self.auto_clean_timer.stop()

    def check_and_auto_clean(self):
        if not self.config.get("auto_clean_enabled", False):
            return

        current_mem = psutil.virtual_memory().percent
        threshold = self.config.get("mem_threshold_percent", 80)

        if current_mem > threshold:
            self.is_cleaning = True
            clean_memory()
            QTimer.singleShot(3000, lambda: setattr(self, 'is_cleaning', False))

    def quit(self):
        self.tray_manager.stop_worker_thread()
        super().quit()

if __name__ == "__main__":
    run_as_admin()

    app = MainApplication(sys.argv)

    sys.exit(app.exec())
