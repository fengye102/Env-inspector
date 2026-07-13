"""并发扫描引擎 — 调度所有工具检测，汇总结果，并在主扫描后异步执行多版本冲突检测"""

from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.conflict import update_result_with_versions
from core.detector import detect_tool
from core.registry import ScanResult, ToolDefinition, get_all_tools

MAX_WORKERS = min(16, (os.cpu_count() or 4) * 4)
MAX_CONFLICT_WORKERS = min(8, MAX_WORKERS)

_CONFLICT_TOOL_TIMEOUT = 15  # 安全护栏；实际 10s 总超时由 conflict.detect_all_versions 强制（见 §九）


class Scanner:
    """
    并发扫描引擎。

    用法:
        scanner = Scanner(on_progress=callback, on_complete=callback)
        scanner.start()          # 非阻塞，在线程池中执行

    两阶段扫描:
        1. 主扫描：并发检测所有工具，完成后触发 on_complete。
        2. 冲突扫描：对 installed=True 且有 multi_version_paths 的工具做多版本探测，
           每个工具完成后触发 on_conflict_update，不阻塞首屏展示。
    """

    def __init__(
        self,
        on_progress: Callable[[ScanResult, int, int], None] | None = None,
        on_complete: Callable[[list[ScanResult]], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_conflict_update: Callable[[ScanResult], None] | None = None,
    ) -> None:
        """
        Args:
            on_progress:      (result, done_count, total_count) → None
            on_complete:      (results) → None，主扫描完成后触发
            on_error:         (error_message) → None
            on_conflict_update: (updated_result) → None，每个工具冲突扫描完成后触发
        """
        self._on_progress = on_progress
        self._on_complete = on_complete
        self._on_error = on_error
        self._on_conflict_update = on_conflict_update
        self._tools: list[ToolDefinition] = get_all_tools()
        self._results: dict[str, ScanResult] = {}
        self._conflict_results: dict[str, ScanResult] = {}
        self._is_running = False
        self._executor: ThreadPoolExecutor | None = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def results(self) -> dict[str, ScanResult]:
        return dict(self._results)

    @property
    def conflict_results(self) -> dict[str, ScanResult]:
        """已完成冲突扫描的工具结果（主扫描结束后逐步填充）。"""
        return dict(self._conflict_results)

    def start(self) -> None:
        """启动扫描（在后台线程中运行，立即返回）。"""
        if self._is_running:
            return
        self._is_running = True
        self._results = {}
        self._conflict_results = {}
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scanner-main")
        self._executor = executor
        executor.submit(self._run_scan)
        executor.shutdown(wait=False)

    def _run_scan(self) -> None:
        total = len(self._tools)
        done = 0

        try:
            # ── 主扫描阶段 ──────────────────────────────────────
            with ThreadPoolExecutor(
                max_workers=MAX_WORKERS, thread_name_prefix="detect"
            ) as pool:
                future_map = {
                    pool.submit(detect_tool, tool): tool for tool in self._tools
                }
                for future in as_completed(future_map):
                    tool = future_map[future]
                    try:
                        result: ScanResult = future.result()
                    except Exception as exc:
                        result = ScanResult(
                            tool_id=tool.id, installed=False, error=str(exc)
                        )
                    self._results[tool.id] = result
                    done += 1
                    if self._on_progress:
                        self._on_progress(result, done, total)

            # 主扫描完成，触发 on_complete 回调（首屏展示）
            if self._on_complete:
                self._on_complete(list(self._results.values()))

            # ── 多版本冲突扫描阶段（不阻塞首屏）──────────────────
            conflict_targets: list[tuple[ToolDefinition, ScanResult]] = [
                (tool, self._results[tool.id])
                for tool in self._tools
                if tool.multi_version_paths
                and tool.id in self._results
                and self._results[tool.id].installed
            ]

            if conflict_targets:
                with ThreadPoolExecutor(
                    max_workers=MAX_CONFLICT_WORKERS,
                    thread_name_prefix="conflict",
                ) as cpool:
                    cf_future_map = {
                        cpool.submit(
                            update_result_with_versions, result, tool
                        ): (tool, result)
                        for tool, result in conflict_targets
                    }
                    for future in as_completed(cf_future_map):
                        tool, _ = cf_future_map[future]
                        try:
                            updated: ScanResult = future.result(
                                timeout=_CONFLICT_TOOL_TIMEOUT
                            )
                        except Exception:
                            # 超时或出错跳过该工具，保留主扫描结果
                            continue
                        self._results[tool.id] = updated
                        self._conflict_results[tool.id] = updated
                        if self._on_conflict_update:
                            self._on_conflict_update(updated)

        except Exception as exc:
            if self._on_error:
                self._on_error(str(exc))
        finally:
            self._is_running = False

    def get_summary(self) -> dict:
        """返回扫描摘要统计，包含冲突计数。"""
        results = list(self._results.values())
        installed = [r for r in results if r.installed]
        conflicts = [r for r in results if r.has_conflict]
        return {
            "total": len(results),
            "installed": len(installed),
            "not_found": len(results) - len(installed),
            "conflicts": len(conflicts),
        }
