"""内存 / CPU 统计信息与格式化。

设计原则：
- 纯函数（format_* / summarize）不依赖任何外部库，可直接单元测试。
- get_memory_snapshot / get_cpu_percent 仅在被调用时才 import psutil（惰性导入），
  这样即使测试环境未安装 psutil，导入本模块也不会失败。
"""

GB = 1024 ** 3


def format_gb(number_of_bytes: float) -> float:
    """把字节数转换为 GB（浮点数）。"""
    return number_of_bytes / GB


def format_gb_str(number_of_bytes: float, digits: int = 2) -> str:
    """把字节数格式化为 'x.xx GB' 字符串。"""
    return f"{number_of_bytes / GB:.{digits}f} GB"


def get_memory_snapshot() -> dict:
    """返回当前物理内存快照（字节 + 百分比）。

    返回字段：total / used / available / percent。
    """
    import psutil

    mem = psutil.virtual_memory()
    return {
        "total": mem.total,
        "used": mem.used,
        "available": mem.available,
        "percent": mem.percent,
    }


def get_cpu_percent() -> float:
    """返回当前 CPU 使用率（百分比，0-100）。"""
    import psutil

    return psutil.cpu_percent(interval=None)


def summarize(snapshot: dict) -> dict:
    """把快照转成便于界面显示的字典。"""
    return {
        "total_gb": format_gb(snapshot["total"]),
        "used_gb": format_gb(snapshot["used"]),
        "available_gb": format_gb(snapshot["available"]),
        "percent": snapshot["percent"],
    }
