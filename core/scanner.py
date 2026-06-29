"""并发扫描引擎 — 调度所有工具检测,汇总结果"""

from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.detector import detect_tool
from core.registry import ScanResult, ToolDefinition, get_all_tools

MAX_WORKERS = min(16, (os.cpu_count() or 4) * 4)


class Scanner:
    """
    并发扫描引擎。

    用法:
        scanner = Scanner(on_progress=callback, on_complete=callback)
        scanner.start()          # 非阻塞，在线程池中执行
    """

    def __init__(
        self,
        on_progress: Callable[[ScanResult, int, int], None] | None = None,
        on_complete: Callable[[list[ScanResult]], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        """
        Args:
            on_progress: (result, done_count, total_count) → None
            on_complete: (results) → None
            on_error:   (error_message) → None
        """
        self._on_progress = on_progress
        self._on_complete = on_complete
        self._on_error = on_error
        self._tools: list[ToolDefinition] = get_all_tools()
        self._results: dict[str, ScanResult] = {}
        self._is_running = False
        self._executor: ThreadPoolExecutor | None = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def results(self) -> dict[str, ScanResult]:
        return dict(self._results)

    def start(self) -> None:
        """启动扫描（在后台线程中运行，立即返回）。"""
        if self._is_running:
            return
        self._is_running = True
        self._results = {}
        # 用单个线程启动整个扫描流程，避免阻塞 UI 主线程
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scanner-main")
        self._executor = executor
        executor.submit(self._run_scan)
        executor.shutdown(wait=False)

    def _run_scan(self) -> None:
        total = len(self._tools)
        done = 0

        try:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="detect") as pool:
                future_map = {pool.submit(detect_tool, tool): tool for tool in self._tools}

                for future in as_completed(future_map):
                    tool = future_map[future]
                    try:
                        result: ScanResult = future.result()
                    except Exception as exc:
                        result = ScanResult(
                            tool_id=tool.id,
                            installed=False,
                            error=str(exc),
                        )

                    self._results[tool.id] = result
                    done += 1

                    if self._on_progress:
                        self._on_progress(result, done, total)

            if self._on_complete:
                self._on_complete(list(self._results.values()))

        except Exception as exc:
            if self._on_error:
                self._on_error(str(exc))
        finally:
            self._is_running = False

    def get_summary(self) -> dict:
        """返回扫描摘要统计。"""
        results = list(self._results.values())
        installed = [r for r in results if r.installed]
        return {
            "total": len(results),
            "installed": len(installed),
            "not_found": len(results) - len(installed),
        }
