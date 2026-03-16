import sys
import ctypes
import subprocess
import threading
import logging
from ctypes import wintypes
from collections import deque
import os

import psutil
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal, QSettings, QMutex, QMutexLocker
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QSpinBox, QDoubleSpinBox, QGroupBox, QFormLayout,
    QMessageBox, QSystemTrayIcon, QMenu, QAction, QStyle,
    QProgressBar, QInputDialog
)

# Privilege management functions
def enable_privilege(privilege_name):
    """Enable specified privilege"""
    try:
        # Open current process token
        hToken = wintypes.HANDLE()
        if not OpenProcessToken(kernel32.GetCurrentProcess(), 0x0020 | 0x0008, ctypes.byref(hToken)):
            logging.error(f"Failed to open process token: {ctypes.get_last_error()}")
            return False
        
        # Lookup privilege value
        luid = LUID()
        if not LookupPrivilegeValue(None, privilege_name, ctypes.byref(luid)):
            logging.error(f"Failed to lookup privilege value: {ctypes.get_last_error()}")
            kernel32.CloseHandle(hToken)
            return False
        
        # Adjust token privilege
        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = 0x00000002  # SE_PRIVILEGE_ENABLED
        
        if not AdjustTokenPrivileges(hToken, False, ctypes.byref(tp), 0, None, None):
            logging.error(f"Failed to adjust token privilege: {ctypes.get_last_error()}")
            kernel32.CloseHandle(hToken)
            return False
        
        kernel32.CloseHandle(hToken)
        return True
    except Exception as e:
        logging.exception(f"Exception when enabling privilege {privilege_name}: {e}")
        return False

# Disable privilege function
def disable_privilege(privilege_name):
    """Disable specified privilege"""
    try:
        # Open current process token
        hToken = wintypes.HANDLE()
        if not OpenProcessToken(kernel32.GetCurrentProcess(), 0x0020 | 0x0008, ctypes.byref(hToken)):
            logging.error(f"Failed to open process token: {ctypes.get_last_error()}")
            return False
        
        # Lookup privilege value
        luid = LUID()
        if not LookupPrivilegeValue(None, privilege_name, ctypes.byref(luid)):
            logging.error(f"Failed to lookup privilege value: {ctypes.get_last_error()}")
            kernel32.CloseHandle(hToken)
            return False
        
        # Adjust token privilege
        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = 0x00000000  # SE_PRIVILEGE_DISABLED
        
        if not AdjustTokenPrivileges(hToken, False, ctypes.byref(tp), 0, None, None):
            logging.error(f"Failed to adjust token privilege: {ctypes.get_last_error()}")
            kernel32.CloseHandle(hToken)
            return False
        
        kernel32.CloseHandle(hToken)
        return True
    except Exception as e:
        logging.exception(f"Exception when disabling privilege {privilege_name}: {e}")
        return False

# Memory status monitoring function
def get_memory_status():
    """Get current memory status"""
    mem = psutil.virtual_memory()
    return {
        "total": mem.total,
        "used": mem.used,
        "available": mem.available,
        "percent": mem.percent
    }

# Memory reclaim strategy
def memory_hook_reclaim():
    """Trigger system-wide memory reclaim by allocating large memory block"""
    try:
        # Allocate half of available memory
        mem = psutil.virtual_memory()
        reclaim_size = mem.available // 2
        if reclaim_size > 0:
            # Allocate memory
            buffer = ctypes.create_string_buffer(reclaim_size)
            # Release immediately
            del buffer
        return True
    except Exception as e:
        logging.exception(f"Memory reclaim failed: {e}")
        return False

# Deferred import of PyQtGraph, ensure QApplication is created first
pg = None

# Windows API constants and structures
PROCESS_SET_QUOTA = 0x0100
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_ALL_ACCESS = 0x1F0FFF
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Privilege constants
SE_DEBUG_NAME = "SeDebugPrivilege"
SE_PROF_SINGLE_PROCESS_NAME = "SeProfileSingleProcessPrivilege"
SE_INC_QUOTA_NAME = "SeIncreaseQuotaPrivilege"

# TOKEN_PRIVILEGES structure
class LUID(ctypes.Structure):
    _fields_ = [
        ("LowPart", wintypes.DWORD),
        ("HighPart", wintypes.LONG),
    ]

class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Luid", LUID),
        ("Attributes", wintypes.DWORD),
    ]

class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", wintypes.DWORD),
        ("Privileges", LUID_AND_ATTRIBUTES * 1),
    ]

# Load advapi32.dll
advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)

# Open process token
OpenProcessToken = advapi32.OpenProcessToken
OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
OpenProcessToken.restype = wintypes.BOOL

# Lookup privilege value
LookupPrivilegeValue = advapi32.LookupPrivilegeValueW
LookupPrivilegeValue.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(LUID)]
LookupPrivilegeValue.restype = wintypes.BOOL

# Adjust token privilege
AdjustTokenPrivileges = advapi32.AdjustTokenPrivileges
AdjustTokenPrivileges.argtypes = [wintypes.HANDLE, wintypes.BOOL, ctypes.POINTER(TOKEN_PRIVILEGES), wintypes.DWORD, ctypes.POINTER(TOKEN_PRIVILEGES), ctypes.POINTER(wintypes.DWORD)]
AdjustTokenPrivileges.restype = wintypes.BOOL

# NtSetSystemInformation definitions
ntdll = ctypes.WinDLL('ntdll', use_last_error=True)
NtSetSystemInformation = ntdll.NtSetSystemInformation
NtSetSystemInformation.argtypes = [wintypes.INT, wintypes.LPVOID, wintypes.ULONG]
NtSetSystemInformation.restype = wintypes.LONG

# System memory list commands
class SYSTEM_MEMORY_LIST_COMMAND:
    MemoryPurgeStandbyList = 4      # Purge standby list
    MemoryPurgeModifiedPageList = 5 # Purge modified page list
    MemoryPurgeCombinedPageList = 6 # Purge combined page list

# System core processes whitelist (non-modifiable)
SYSTEM_CORE_PROCESSES = [
    "System", "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
    "lsass.exe", "winlogon.exe", "fontdrvhost.exe", "dwm.exe"
]

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')







class DeepCleanThread(QThread):
    """Background deep clean thread"""
    finished = pyqtSignal()
    update_memory = pyqtSignal()

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def run(self):
        """Execute deep clean"""
        # Import necessary modules
        import os
        import sys
        import time
        
        # 1. Check and get admin privilege
        admin_status = is_admin()
        if not admin_status:
            # Try to restart with admin privilege and execute deep clean
            script = os.path.abspath(sys.argv[0])
            command = f'"{script}" --deep-clean'
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, command, None, 1
            )
            return

        # 2. Enable core privileges
        privileges = [SE_DEBUG_NAME, SE_PROF_SINGLE_PROCESS_NAME, SE_INC_QUOTA_NAME]
        for priv in privileges:
            enable_privilege(priv)

        try:
            # 3. Record memory status before clean
            before = get_memory_status()
            logging.info(f"Memory status before clean: Used {before['used']/1024**3:.2f}GB, Available {before['available']/1024**3:.2f}GB")

            # 4. Clean all processes working set
            process_names = {}
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    pinfo = proc.info
                    pid = pinfo['pid']
                    name = pinfo['name'] or "Unknown"
                    process_names[pid] = name
                    # Exclude system core processes
                    if name in SYSTEM_CORE_PROCESSES:
                        continue
                    # Clean process working set
                    hProcess = kernel32.OpenProcess(
                        PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION,
                        False, pid
                    )
                    if hProcess:
                        try:
                            # Try to use EmptyWorkingSet
                            try:
                                EmptyWorkingSet = kernel32.EmptyWorkingSet
                                EmptyWorkingSet.argtypes = [ctypes.c_void_p]
                                EmptyWorkingSet.restype = ctypes.c_bool
                                # Execute multiple times to ensure thorough cleaning
                                for _ in range(3):
                                    EmptyWorkingSet(hProcess)
                            except AttributeError:
                                # Alternative method
                                SetProcessWorkingSetSize = kernel32.SetProcessWorkingSetSize
                                SetProcessWorkingSetSize.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t]
                                SetProcessWorkingSetSize.restype = ctypes.c_bool
                                size_max = ctypes.c_size_t(-1).value
                                # Execute multiple times to ensure thorough cleaning
                                for _ in range(3):
                                    SetProcessWorkingSetSize(hProcess, size_max, size_max)
                        finally:
                            kernel32.CloseHandle(hProcess)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                except Exception as e:
                    logging.exception(f"Exception when cleaning process {pid} working set: {e}")
                    continue

            # Update memory information
            self.update_memory.emit()
            time.sleep(0.1)

            # 5. Purge standby list
            try:
                # Execute multiple times to ensure thorough cleaning
                for _ in range(3):
                    NtSetSystemInformation(0x57, ctypes.byref(wintypes.ULONG(SYSTEM_MEMORY_LIST_COMMAND.MemoryPurgeStandbyList)), ctypes.sizeof(wintypes.ULONG))
            except Exception as e:
                logging.exception(f"Failed to purge standby list: {e}")

            # Update memory information
            self.update_memory.emit()
            time.sleep(0.1)

            # 6. Purge modified page list
            try:
                # Execute multiple times to ensure thorough cleaning
                for _ in range(3):
                    NtSetSystemInformation(0x57, ctypes.byref(wintypes.ULONG(SYSTEM_MEMORY_LIST_COMMAND.MemoryPurgeModifiedPageList)), ctypes.sizeof(wintypes.ULONG))
            except Exception as e:
                logging.exception(f"Failed to purge modified page list: {e}")

            # Update memory information
            self.update_memory.emit()
            time.sleep(0.1)

            # 7. Clean system cache
            # 7.1 Flush all disk volumes
            try:
                import win32file
                import win32api
                # Enumerate all disk volumes
                for drive in win32api.GetLogicalDriveStrings().split('\\\\?\\'):
                    drive = drive.strip()
                    if drive and (drive.endswith(':\\') or drive.endswith(':')):
                        try:
                            # Flush volume cache
                            hVolume = win32file.CreateFile(
                                f"\\\\?\\{drive}",
                                win32file.GENERIC_READ,
                                win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
                                None,
                                win32file.OPEN_EXISTING,
                                0,
                                None
                            )
                            if hVolume != win32file.INVALID_HANDLE_VALUE:
                                try:
                                    # Execute multiple times to ensure thorough cleaning
                                    for _ in range(3):
                                        win32file.FlushFileBuffers(hVolume)
                                finally:
                                    win32file.CloseHandle(hVolume)
                        except Exception as e:
                            logging.exception(f"Failed to flush volume {drive} cache: {e}")
            except ImportError:
                # No win32api, skip this step
                pass
            
            # 7.2 Clean system file cache
            try:
                # Call SetSystemFileCacheSize to clean file cache
                SetSystemFileCacheSize = kernel32.SetSystemFileCacheSize
                SetSystemFileCacheSize.argtypes = [ctypes.c_size_t, ctypes.c_size_t, ctypes.c_uint]
                SetSystemFileCacheSize.restype = ctypes.c_bool
                # Set cache size to minimum
                result = SetSystemFileCacheSize(0, 0, 0x00000001)  # 0x00000001 = FILE_CACHE_SIZE_MIN
                if not result:
                    logging.error(f"Failed to clean system file cache, error code: {ctypes.get_last_error()}")
            except AttributeError:
                # SetSystemFileCacheSize function not found, skip this step
                pass
            except Exception as e:
                logging.exception(f"Exception when cleaning system file cache: {e}")

            # Update memory information
            self.update_memory.emit()
            time.sleep(0.1)

            # 8. Memory compression
            try:
                # Enable memory compression if not enabled
                import subprocess
                result = subprocess.run(
                    ["powershell", "-Command", "Enable-MMAgent -MemoryCompression"],
                    capture_output=True, text=True, timeout=15,  # Increase timeout to 15 seconds
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode != 0:
                    logging.error(f"Failed to enable memory compression: {result.stderr}")
            except subprocess.TimeoutExpired:
                logging.warning("Enable memory compression timeout, skip this step")
            except Exception as e:
                logging.exception(f"Exception when enabling memory compression: {e}")

            # Update memory information
            self.update_memory.emit()
            time.sleep(0.1)

            # 9. Memory merge and reclaim
            # 9.1 Memory merge (Windows 10+)
            try:
                # Execute multiple times to ensure thorough cleaning
                for _ in range(3):
                    NtSetSystemInformation(0x57, ctypes.byref(wintypes.ULONG(SYSTEM_MEMORY_LIST_COMMAND.MemoryPurgeCombinedPageList)), ctypes.sizeof(wintypes.ULONG))
            except Exception as e:
                logging.exception(f"Failed to merge memory: {e}")
            
            # Update memory information
            self.update_memory.emit()
            time.sleep(0.1)
            
            # 9.2 Memory reclaim strategy
            # Execute multiple times to ensure thorough cleaning
            for _ in range(3):
                memory_hook_reclaim()
                # Short delay to allow system to process memory reclaim
                time.sleep(0.5)
                # Update memory information
                self.update_memory.emit()

            # 10. Clean system working set
            try:
                # Clean current process working set
                hProcess = kernel32.OpenProcess(
                    PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION,
                    False, os.getpid()
                )
                if hProcess:
                    try:
                        try:
                            EmptyWorkingSet = kernel32.EmptyWorkingSet
                            EmptyWorkingSet.argtypes = [ctypes.c_void_p]
                            EmptyWorkingSet.restype = ctypes.c_bool
                            EmptyWorkingSet(hProcess)
                        except AttributeError:
                            SetProcessWorkingSetSize = kernel32.SetProcessWorkingSetSize
                            SetProcessWorkingSetSize.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t]
                            SetProcessWorkingSetSize.restype = ctypes.c_bool
                            size_max = ctypes.c_size_t(-1).value
                            SetProcessWorkingSetSize(hProcess, size_max, size_max)
                    finally:
                        kernel32.CloseHandle(hProcess)
            except Exception as e:
                logging.exception(f"Failed to clean system working set: {e}")

            # Update memory information
            self.update_memory.emit()
            time.sleep(0.1)

            # 11. Record memory status after clean
            after = get_memory_status()
            logging.info(f"Memory status after clean: Used {after['used']/1024**3:.2f}GB, Available {after['available']/1024**3:.2f}GB")
            freed = (after['available'] - before['available']) / 1024**3
            logging.info(f"Freed memory: {freed:.2f}GB")

        finally:
            # 12. Disable all enabled privileges
            for priv in privileges:
                disable_privilege(priv)

        # Send finished signal
        self.finished.emit()

class MemoryMonitor(QMainWindow):
    def __init__(self, app):
        try:
            self.app = app  # Save application instance
            # Ensure QApplication instance exists
            if app is None:
                raise Exception("QApplication instance is None")
            
            super().__init__()
            
            # Initialize translation dictionary
            self.translations = {
                'zh': {
                    'window_title': 'SimpleMemKitty',
                    'memory_status': '内存状态',
                    'total': '总计:',
                    'used': '已用:',
                    'available': '可用:',
                    'usage': '使用率:',
                    'one_click_clean': '一键清理',
                    'deep_clean': '深度清理',
                    'show_window': '显示窗口',
                    'exit': '退出',
                    'insufficient_privilege': '权限不足',
                    'privilege_warning': '程序未以管理员权限运行，部分功能（深度清理、系统压缩控制）可能失败。\n建议以管理员权限重启。',
                    'language_menu': '语言',
                    'chinese': '中文',
                    'english': 'English'
                },
                'en': {
                    'window_title': 'SimpleMemKitty',
                    'memory_status': 'Memory Status',
                    'total': 'Total:',
                    'used': 'Used:',
                    'available': 'Available:',
                    'usage': 'Usage:',
                    'one_click_clean': 'One-Click Clean',
                    'deep_clean': 'Deep Clean',
                    'show_window': 'Show Window',
                    'exit': 'Exit',
                    'insufficient_privilege': 'Insufficient Privilege',
                    'privilege_warning': 'Program is not running with admin privilege, some functions (deep clean, system compression control) may fail.\nIt is recommended to restart with admin privilege.',
                    'language_menu': 'Language',
                    'chinese': '中文',
                    'english': 'English'
                }
            }
            
            # Default language
            self.language = 'zh'
            
            print("Initializing MemoryMonitor...")
            self.setWindowTitle(self._tr('window_title'))
            self.setMinimumSize(380, 160)  # Reduce window size

            # UI initialization
            print("Setting up UI...")
            self.setup_ui()
            print("Setting up system tray...")
            self.setup_tray()
            print("Checking admin privilege...")
            self.check_admin()

            # Timer: Update memory information (every second)
            print("Setting up timer...")
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_memory_info)
            self.timer.start(1000)

            # Initialize data
            print("Updating memory information...")
            self.update_memory_info()
            print("Initialization completed")
        except Exception as e:
            print(f"MemoryMonitor initialization error: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _tr(self, key):
        """Translate text based on current language"""
        return self.translations[self.language].get(key, key)

    def setup_ui(self):
        """Build main UI"""
        print("Starting UI setup...")
        
        # Main layout
        print("Creating central widget...")
        central_widget = QWidget()
        print("Creating main layout...")
        main_layout = QVBoxLayout(central_widget)
        print("Setting central widget...")
        self.setCentralWidget(central_widget)

        # Memory information area
        print("Creating memory information area...")
        mem_group = QGroupBox(self._tr('memory_status'))
        mem_layout = QVBoxLayout()  # Use vertical layout
        
        # Memory information labels
        print("Creating memory information labels...")
        # Create horizontal layout for memory information labels
        mem_info_layout = QHBoxLayout()
        self.mem_total_label = QLabel(self._tr('total') + ' ')
        self.mem_used_label = QLabel(self._tr('used') + ' ')
        self.mem_avail_label = QLabel(self._tr('available') + ' ')
        self.mem_percent_label = QLabel(self._tr('usage') + ' ')
        
        # Set label font size
        label_font = self.mem_total_label.font()
        label_font.setPointSize(9)
        self.mem_total_label.setFont(label_font)
        self.mem_used_label.setFont(label_font)
        self.mem_avail_label.setFont(label_font)
        self.mem_percent_label.setFont(label_font)
        
        # Add to horizontal layout
        mem_info_layout.addWidget(self.mem_total_label)
        mem_info_layout.addWidget(self.mem_used_label)
        mem_info_layout.addWidget(self.mem_avail_label)
        mem_info_layout.addWidget(self.mem_percent_label)
        
        # Progress bar
        self.mem_bar = QProgressBar()
        self.mem_bar.setMaximum(100)
        self.mem_bar.setMinimumHeight(20)  # Reduce progress bar height
        
        # Add to vertical layout
        mem_layout.addLayout(mem_info_layout)
        mem_layout.addWidget(self.mem_bar)
        mem_group.setLayout(mem_layout)
        main_layout.addWidget(mem_group)

        # Clean buttons
        print("Creating clean buttons...")
        button_layout = QHBoxLayout()
        
        # One-click clean button (simple clean)
        self.one_click_clean_btn = QPushButton(self._tr('one_click_clean'))
        # Set button font size
        button_font = self.one_click_clean_btn.font()
        button_font.setPointSize(12)
        self.one_click_clean_btn.setFont(button_font)
        self.one_click_clean_btn.setMinimumHeight(40)  # Increase button height
        self.one_click_clean_btn.clicked.connect(self.one_click_clean)  # Connect to simple clean method
        button_layout.addWidget(self.one_click_clean_btn)
        
        # Deep clean button (current deep clean function)
        self.deep_clean_btn = QPushButton(self._tr('deep_clean'))
        self.deep_clean_btn.setFont(button_font)
        self.deep_clean_btn.setMinimumHeight(40)  # Increase button height
        self.deep_clean_btn.clicked.connect(self.deep_clean)  # Connect to deep clean method
        button_layout.addWidget(self.deep_clean_btn)
        
        main_layout.addLayout(button_layout)

        # Add language menu
        self.create_language_menu()

        print("UI setup completed")
    
    def create_language_menu(self):
        """Create language menu"""
        # Clear existing menus to avoid duplication
        self.menuBar().clear()
        
        # Add language menu to menubar
        language_menu = self.menuBar().addMenu(self._tr('language_menu'))
        
        # Chinese language action
        chinese_action = QAction(self._tr('chinese'), self)
        chinese_action.triggered.connect(lambda: self.switch_language('zh'))
        language_menu.addAction(chinese_action)
        
        # English language action
        english_action = QAction(self._tr('english'), self)
        english_action.triggered.connect(lambda: self.switch_language('en'))
        language_menu.addAction(english_action)

    def setup_tray(self):
        """Set up system tray"""
        try:
            self.tray_icon = QSystemTrayIcon(self)
            # Get system icon correctly
            icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
            self.tray_icon.setIcon(icon)
            
            # Tray menu
            tray_menu = QMenu()
            
            # Show/hide window
            show_action = QAction(self._tr('show_window'), self)
            show_action.triggered.connect(self.show)
            tray_menu.addAction(show_action)
            
            # Exit
            quit_action = QAction(self._tr('exit'), self)
            quit_action.triggered.connect(self.quit_app)
            tray_menu.addAction(quit_action)
            
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self.on_tray_activated)
            self.tray_icon.show()
            print("System tray setup successful")
        except Exception as e:
            print(f"Error setting up system tray: {e}")
            # If setting system tray fails, ignore this error and continue running the program
            pass

    def check_admin(self):
        """Check admin privilege, warn if insufficient"""
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except:
            is_admin = False
        if not is_admin:
            QMessageBox.warning(self, self._tr('insufficient_privilege'),
                self._tr('privilege_warning'))
    
    def switch_language(self, lang):
        """Switch language and rebuild UI"""
        self.language = lang
        # Rebuild UI to apply new language
        self.setup_ui()
        # Update tray menu
        self.setup_tray()
        # Update window title
        self.setWindowTitle(self._tr('window_title'))
        # Update memory information
        self.update_memory_info()



    def update_memory_info(self):
        """Update memory display"""
        mem = psutil.virtual_memory()
        total_gb = mem.total / (1024**3)
        used_gb = mem.used / (1024**3)
        avail_gb = mem.available / (1024**3)

        self.mem_total_label.setText(f"{self._tr('total')} {total_gb:.2f} GB")
        self.mem_used_label.setText(f"{self._tr('used')} {used_gb:.2f} GB")
        self.mem_avail_label.setText(f"{self._tr('available')} {avail_gb:.2f} GB")
        self.mem_percent_label.setText(f"{self._tr('usage')} {mem.percent:.1f} %")
        self.mem_bar.setValue(int(mem.percent))





    def one_click_clean(self):
        """Simple memory clean (can be clicked repeatedly)"""
        try:
            # 1. Record memory status before clean
            before = get_memory_status()
            logging.info(f"Memory status before one-click clean: Used {before['used']/1024**3:.2f}GB, Available {before['available']/1024**3:.2f}GB")

            # 2. Clean all processes working set
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    pinfo = proc.info
                    pid = pinfo['pid']
                    name = pinfo['name'] or "Unknown"
                    # Exclude system core processes
                    if name in SYSTEM_CORE_PROCESSES:
                        continue
                    # Clean process working set
                    hProcess = kernel32.OpenProcess(
                        PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION,
                        False, pid
                    )
                    if hProcess:
                        try:
                            # Try to use EmptyWorkingSet
                            try:
                                EmptyWorkingSet = kernel32.EmptyWorkingSet
                                EmptyWorkingSet.argtypes = [ctypes.c_void_p]
                                EmptyWorkingSet.restype = ctypes.c_bool
                                EmptyWorkingSet(hProcess)
                            except AttributeError:
                                # Alternative method
                                SetProcessWorkingSetSize = kernel32.SetProcessWorkingSetSize
                                SetProcessWorkingSetSize.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t]
                                SetProcessWorkingSetSize.restype = ctypes.c_bool
                                size_max = ctypes.c_size_t(-1).value
                                SetProcessWorkingSetSize(hProcess, size_max, size_max)
                        finally:
                            kernel32.CloseHandle(hProcess)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                except Exception as e:
                    logging.exception(f"Exception when cleaning process {pid} working set: {e}")
                    continue

            # 3. Purge standby list
            try:
                NtSetSystemInformation(0x57, ctypes.byref(wintypes.ULONG(SYSTEM_MEMORY_LIST_COMMAND.MemoryPurgeStandbyList)), ctypes.sizeof(wintypes.ULONG))
            except Exception as e:
                logging.exception(f"Failed to purge standby list: {e}")

            # 4. Record memory status after clean
            after = get_memory_status()
            logging.info(f"Memory status after one-click clean: Used {after['used']/1024**3:.2f}GB, Available {after['available']/1024**3:.2f}GB")
            freed = (after['available'] - before['available']) / 1024**3
            logging.info(f"Freed memory: {freed:.2f}GB")

        except Exception as e:
            logging.exception(f"Exception during one-click clean: {e}")

        # Update memory information
        self.update_memory_info()

    def deep_clean(self):
        """One-step deep memory clean"""
        # Start background thread to execute deep clean
        self.deep_clean_thread = DeepCleanThread(self)
        self.deep_clean_thread.finished.connect(self.on_deep_clean_finished)
        self.deep_clean_thread.update_memory.connect(self.update_memory_info)
        self.deep_clean_thread.start()

    def on_deep_clean_finished(self):
        """Update memory information after deep clean"""
        # Update memory information
        self.update_memory_info()
        # Force immediate update to ensure latest status
        self.update_memory_info()



    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        # No notification, directly minimize to tray
        pass

    def quit_app(self):
        """Exit program, release resources"""
        logging.info("Starting program exit...")
        # Stop timer
        self.timer.stop()
        
        self.tray_icon.hide()
        QApplication.quit()
        logging.info("Program exit completed")

def is_admin():
    """Check if running with admin privilege"""
    try:
        result = ctypes.windll.shell32.IsUserAnAdmin()
        print(f"IsUserAnAdmin return value: {result}")
        return result
    except Exception as e:
        print(f"Error checking admin privilege: {e}")
        return False

def run_as_admin():
    """Restart program with admin privilege"""
    try:
        # Get current script path
        script = os.path.abspath(sys.argv[0])
        # Build command line parameters
        params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
        if params:
            command = f'"{script}" {params}'
        else:
            command = f'"{script}"'
        
        # Use ShellExecute to restart with admin privilege
        print(f"Attempting to restart program with admin privilege: {command}")
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, command, None, 1
        )
        print(f"ShellExecute return value: {result}")
        return result > 32
    except Exception as e:
        print(f"Error requesting admin privilege: {e}")
        return False

def main():
    """Main function"""
    print("Program starting...")
    print(f"Python version: {sys.version}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Script path: {os.path.abspath(sys.argv[0])}")
    print(f"Command line arguments: {sys.argv}")
    
    # Check admin privilege
    admin_status = is_admin()
    print(f"Admin status: {admin_status}")
    
    # Check for deep clean mode
    if "--deep-clean" in sys.argv:
        print("Executing deep clean mode...")
        # Create application instance
        app = QApplication(sys.argv)
        # Create main window
        window = MemoryMonitor(app)
        # Execute deep clean
        window.deep_clean()
        # Exit program
        sys.exit(0)
    
    # Force admin privilege if not available
    if not admin_status:
        print("Not running as admin, requesting privilege...")
        # Loop to request admin privilege until successful or cancelled
        while True:
            if run_as_admin():
                print("Admin privilege requested, program will restart")
                # Wait for new process to start
                import time
                time.sleep(2)
                print("Original process exiting")
                return  # Exit current process
            else:
                # Show warning message
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    None, 
                    "Memory cleaning program requires admin privilege to work properly.\nPlease click 'Yes' to restart as admin.", 
                    "Insufficient Privilege", 
                    0x40000 | 0x1  # MB_ICONEXCLAMATION | MB_OK
                )
                # Recheck privilege
                admin_status = is_admin()
                if admin_status:
                    break

    # Continue running regardless of admin status
    try:
        print("Initializing application...")
        # Ensure QApplication is created before any QWidget
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        print("QApplication created successfully")
        
        # Import PyQtGraph
        global pg
        try:
            import pyqtgraph as pg
            print("PyQtGraph imported successfully")
        except Exception as e:
            print(f"Failed to import PyQtGraph: {e}")
            pg = None

        print("Creating MemoryMonitor instance...")
        window = MemoryMonitor(app)
        print("Showing window...")
        window.show()
        
        # Check for auto deep clean
        if "--deep-clean" in sys.argv:
            print("--deep-clean parameter detected, executing auto deep clean...")
            # Delay deep clean to ensure window is displayed
            import threading
            def auto_deep_clean():
                import time
                time.sleep(1)
                window.deep_clean()
            threading.Thread(target=auto_deep_clean).start()
        
        print("Starting event loop...")
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Program error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")

if __name__ == "__main__":
    import os
    main()