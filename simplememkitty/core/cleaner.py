"""清理编排层：把底层 MemoryAPI 组合成"轻量清理"与"深度清理"。

设计要点（对照原 SimpleMemKitty.py 的 bug 修复）：
1. 移除原 memory_hook_reclaim：它会分配"半个可用内存"再释放，正是用户观察到的
   "内存突然往上跳一大截又掉回来"的根因，且对释放内存毫无帮助 -> 已删除。
2. 移除原深度清理里慢且损害性能的步骤：
   - PowerShell Enable-MMAgent -MemoryCompression（最多 15s 超时，且对本次清理无即时收益）
   - 遍历所有磁盘卷 FlushFileBuffers（只刷盘、不释放内存，且慢）
   - SetSystemFileCacheSize(0,0,MIN)（把系统文件缓存压到最小，会显著降低系统性能）
3. 每步独立 try，单步失败不影响整体；特权启用失败则降级运行。
4. 通过注入 MemoryAPI（默认 WindowsMemoryAPI）实现与 Windows / 测试的解耦。
"""

import logging


class Cleaner:
    def __init__(self, api=None):
        if api is None:
            from .memory_api import WindowsMemoryAPI

            api = WindowsMemoryAPI()
        self.api = api
        # 内存快照函数（可注入，便于测试；默认惰性导入 stats）
        self.snapshot_fn = None

    def _snapshot(self) -> dict:
        if self.snapshot_fn is not None:
            return self.snapshot_fn()
        from . import stats

        return stats.get_memory_snapshot()

    # ------------------------------------------------------------------
    def light_clean(self) -> dict:
        """轻量清理：清进程工作集 + 回收备用列表。

        快速、平滑，适合一键清理与自动清理的周期性调用。
        尽力启用特权（非管理员时失败也无妨，仅影响系统进程清理范围）。
        """
        before = self._snapshot()
        try:
            self.api.enable_privileges()
        except Exception as exc:  # noqa: BLE001
            logging.debug("轻量清理启用特权失败（降级）: %s", exc)

        cleaned = 0
        try:
            cleaned = self.api.clean_working_sets()
        except Exception as exc:  # noqa: BLE001
            logging.debug("清工作集失败: %s", exc)
        try:
            self.api.purge_standby_list()
        except Exception as exc:  # noqa: BLE001
            logging.debug("回收备用列表失败: %s", exc)
        try:
            self.api.disable_privileges()
        except Exception:  # noqa: BLE001
            pass

        after = self._snapshot()
        freed = max(0, after["available"] - before["available"])
        return {"freed_bytes": freed, "cleaned_processes": cleaned}

    # ------------------------------------------------------------------
    def deep_clean(self) -> dict:
        """深度清理：启用特权 -> 清工作集 -> 回收三个系统列表 -> 禁用特权。

        不做任何大块内存分配，也不调用慢速外部命令，因此快且不会造成内存瞬时飙升。
        每一步独立容错：单步失败（如某列表回收不支持）不影响其余步骤与最终收尾。
        """
        before = self._snapshot()
        try:
            self.api.enable_privileges()
        except Exception as exc:  # noqa: BLE001
            logging.warning("启用特权失败（将以降级模式清理）: %s", exc)

        cleaned = 0
        try:
            cleaned = self.api.clean_working_sets()
        except Exception as exc:  # noqa: BLE001
            logging.debug("清工作集失败: %s", exc)

        for step_name, step in (
            ("purge_standby_list", self.api.purge_standby_list),
            ("purge_modified_list", self.api.purge_modified_list),
            ("purge_combined_list", self.api.purge_combined_list),
        ):
            try:
                step()
            except Exception as exc:  # noqa: BLE001
                logging.debug("%s 失败: %s", step_name, exc)

        try:
            self.api.disable_privileges()
        except Exception:  # noqa: BLE001
            pass

        after = self._snapshot()
        freed = max(0, after["available"] - before["available"])
        return {"freed_bytes": freed, "cleaned_processes": cleaned}
