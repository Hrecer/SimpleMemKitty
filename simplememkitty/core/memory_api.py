"""Windows 内存管理 API 封装。

设计要点：
- 定义 MemoryAPI 抽象接口；真实实现 WindowsMemoryAPI 通过 ctypes 调用
  kernel32 / advapi32 / ntdll。测试时可用任意 FakeAPI 替换，无需真实 Windows
  权限或管理员。
- 仅在与系统交互的方法里惰性导入 psutil，避免无谓依赖。
"""

import ctypes
import logging
import struct
from ctypes import wintypes

# 系统核心进程白名单（不清理，避免系统不稳定）
SYSTEM_CORE_PROCESSES = {
    "System", "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
    "lsass.exe", "winlogon.exe", "fontdrvhost.exe", "dwm.exe",
}

# 特权名
SE_DEBUG_NAME = "SeDebugPrivilege"
SE_PROF_SINGLE_PROCESS_NAME = "SeProfileSingleProcessPrivilege"
SE_INC_QUOTA_NAME = "SeIncreaseQuotaPrivilege"

# NtSetSystemInformation 的 SystemMemoryListInformation class
SYSTEM_MEMORY_LIST_INFORMATION = 0x57
MEMORY_PURGE_STANDBY_LIST = 4
MEMORY_PURGE_MODIFIED_PAGE_LIST = 5
MEMORY_PURGE_COMBINED_PAGE_LIST = 6

PROCESS_SET_QUOTA = 0x0100
PROCESS_QUERY_INFORMATION = 0x0400

SE_PRIVILEGE_ENABLED = 0x00000002

# ---- ctypes 结构 ----
class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", wintypes.DWORD),
        ("Privileges", LUID_AND_ATTRIBUTES * 1),
    ]


class MemoryAPI:
    """抽象接口，默认空实现，便于在测试中替换 / 断言调用序列。"""

    def enable_privileges(self):
        return True

    def disable_privileges(self):
        return True

    def clean_working_sets(self):
        """清理各进程工作集，返回成功清理的进程数。"""
        return 0

    def purge_standby_list(self):
        return False

    def purge_modified_list(self):
        return False

    def purge_combined_list(self):
        return False


class WindowsMemoryAPI(MemoryAPI):
    """基于 ctypes 的 Windows 实现。"""

    def __init__(self):
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self.ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
        self.psapi = ctypes.WinDLL("Psapi", use_last_error=True)
        self._define_api()

    def _define_api(self):
        k, a, n = self.kernel32, self.advapi32, self.ntdll

        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.GetCurrentProcess.argtypes = []

        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]

        k.CloseHandle.restype = wintypes.BOOL
        k.CloseHandle.argtypes = [wintypes.HANDLE]

        k.SetProcessWorkingSetSize.restype = wintypes.BOOL
        k.SetProcessWorkingSetSize.argtypes = [wintypes.HANDLE, ctypes.c_size_t, ctypes.c_size_t]

        a.OpenProcessToken.restype = wintypes.BOOL
        a.OpenProcessToken.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
        ]
        a.LookupPrivilegeValueW.restype = wintypes.BOOL
        a.LookupPrivilegeValueW.argtypes = [
            wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(LUID)
        ]
        a.AdjustTokenPrivileges.restype = wintypes.BOOL
        a.AdjustTokenPrivileges.argtypes = [
            wintypes.HANDLE, wintypes.BOOL,
            ctypes.POINTER(TOKEN_PRIVILEGES), wintypes.DWORD,
            ctypes.c_void_p, ctypes.c_void_p,
        ]

        n.NtSetSystemInformation.restype = wintypes.LONG
        n.NtSetSystemInformation.argtypes = [wintypes.INT, wintypes.LPVOID, wintypes.ULONG]

        # EmptyWorkingSet 位于 Psapi.dll（部分系统会经 kernel32 转发，但显式从 Psapi 取最稳妥）
        self.psapi.EmptyWorkingSet.restype = wintypes.BOOL
        self.psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]

    # ---- 特权 ----
    def _adjust_privileges(self, attributes):
        privs = [SE_DEBUG_NAME, SE_PROF_SINGLE_PROCESS_NAME, SE_INC_QUOTA_NAME]
        TOKEN_ADJUST_PRIVILEGES = 0x0020
        TOKEN_QUERY = 0x0008
        h_token = wintypes.HANDLE()
        if not self.advapi32.OpenProcessToken(
            self.kernel32.GetCurrentProcess(),
            TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
            ctypes.byref(h_token),
        ):
            logging.warning("OpenProcessToken 失败: %s", ctypes.get_last_error())
            return False
        ok = True
        try:
            for name in privs:
                luid = LUID()
                if not self.advapi32.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
                    ok = False
                    continue
                tp = TOKEN_PRIVILEGES()
                tp.PrivilegeCount = 1
                tp.Privileges[0].Luid = luid
                tp.Privileges[0].Attributes = attributes
                if not self.advapi32.AdjustTokenPrivileges(
                    h_token, False, ctypes.byref(tp), 0, None, None
                ):
                    ok = False
                elif ctypes.get_last_error() != 0:
                    # 返回成功但特权未全部授予（例如非管理员）
                    logging.warning("特权 %s 未能完全启用 (err=%s)", name, ctypes.get_last_error())
                    ok = False
        finally:
            self.kernel32.CloseHandle(h_token)
        return ok

    def enable_privileges(self):
        return self._adjust_privileges(SE_PRIVILEGE_ENABLED)

    def disable_privileges(self):
        return self._adjust_privileges(0x00000000)

    # ---- 进程工作集 ----
    def clean_working_sets(self):
        try:
            import psutil
        except ImportError:
            logging.warning("psutil 未安装，跳过进程工作集清理")
            return 0

        count = 0
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                info = proc.info
                name = info.get("name") or "Unknown"
                if name in SYSTEM_CORE_PROCESSES:
                    continue
                pid = info.get("pid")
                h = self.kernel32.OpenProcess(
                    PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION, False, pid
                )
                if not h:
                    continue
                try:
                    if not self.psapi.EmptyWorkingSet(h):
                        # 备选方案
                        size_max = ctypes.c_size_t(-1).value
                        self.kernel32.SetProcessWorkingSetSize(h, size_max, size_max)
                    count += 1
                finally:
                    self.kernel32.CloseHandle(h)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception as exc:  # noqa: BLE001 - 单个进程失败不应中断整体
                logging.debug("清理进程工作集异常: %s", exc)
                continue
        return count

    # ---- 系统内存列表回收 ----
    def _purge(self, command):
        """回收系统内存列表（standby / modified / combined）。

        兼容性说明：不同 Windows 版本对 SystemMemoryListInformation 的输入缓冲长度
        要求不同——实测部分系统仅接受 8 字节（前 4 字节为命令），而旧实现只传 4 字节，
        会导致在新系统上调用直接失败（STATUS_INFO_LENGTH_MISMATCH），系统级清理形同虚设。
        这里优先尝试 8 字节，失败再回退 4 字节，以兼顾新旧系统。
        """
        for length in (8, 4):
            buf = ctypes.create_string_buffer(length)
            struct.pack_into("<I", buf, 0, command)
            try:
                status = self.ntdll.NtSetSystemInformation(
                    SYSTEM_MEMORY_LIST_INFORMATION,
                    buf,
                    length,
                )
            except Exception as exc:  # noqa: BLE001
                logging.debug("purge %s (len=%d) 失败: %s", command, length, exc)
                continue
            if status == 0:
                return True
            logging.debug("purge %s (len=%d) 返回 0x%08X", command, length, status & 0xFFFFFFFF)
        return False

    def purge_standby_list(self):
        return self._purge(MEMORY_PURGE_STANDBY_LIST)

    def purge_modified_list(self):
        return self._purge(MEMORY_PURGE_MODIFIED_PAGE_LIST)

    def purge_combined_list(self):
        return self._purge(MEMORY_PURGE_COMBINED_PAGE_LIST)
