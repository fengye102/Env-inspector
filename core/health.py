"""
core/health.py — 环境健康检查（纯分析模块）

基于本机可计算的事实分析环境问题：版本冲突 / 版本解析失败 / 检测超时 /
核心类别缺失 / PATH 重复或失效条目。

禁止做跨工具版本兼容性判断（见 CLAUDE.md §12）。
本模块不涉及任何 UI、文件 IO 或网络访问。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from core.registry import ScanResult, ToolDefinition, CATEGORIES, CATEGORY_ORDER  # noqa: F401


# 严重度排序权重：error 最先，warning 次之，info 最后
_SEVERITY_RANK: dict[str, int] = {"error": 0, "warning": 1, "info": 2}


@dataclass
class HealthIssue:
    """单条健康问题"""
    severity: str   # "error" | "warning" | "info"
    category: str   # "conflict" | "version" | "timeout" | "path" | "missing"
    tool_id: str    # 工具 id；PATH 问题固定为 "_path"
    title: str
    detail: str
    suggestion: str


def analyze(results: list[ScanResult], tools: dict[str, ToolDefinition]) -> list[HealthIssue]:
    """分析扫描结果，返回按严重度 / 分类 / tool_id 排序的问题列表。"""
    issues: list[HealthIssue] = []

    # 已安装工具 id 集合（用于 missing 判定）
    installed_tool_ids: set[str] = {r.tool_id for r in results if r.installed}

    for r in results:
        # conflict：存在版本冲突
        if r.has_conflict:
            distinct_versions: list[str] = []
            seen: set[str] = set()
            for ve in r.all_versions:
                if ve.version not in seen:
                    seen.add(ve.version)
                    distinct_versions.append(ve.version)
            issues.append(HealthIssue(
                severity="warning",
                category="conflict",
                tool_id=r.tool_id,
                title="存在版本冲突",
                detail=", ".join(distinct_versions),
                suggestion="建议卸载旧版本或调整 PATH 顺序使期望版本生效",
            ))

        # version：已安装但版本无法解析
        if r.installed and r.version is None:
            issues.append(HealthIssue(
                severity="warning",
                category="version",
                tool_id=r.tool_id,
                title="已安装但无法解析版本",
                detail="已检测到安装但版本命令未返回可解析版本",
                suggestion="检查工具版本命令输出或重新安装",
            ))

        # timeout：检测超时
        if r.error == "timeout":
            issues.append(HealthIssue(
                severity="warning",
                category="timeout",
                tool_id=r.tool_id,
                title="检测超时",
                detail="版本命令执行超时",
                suggestion="稍后重试，或检查该工具是否响应缓慢",
            ))

    # missing：核心类别全部未安装
    core_cats = ("lang", "pkg", "vcs")
    cat_label = {c["id"]: c["label"] for c in CATEGORIES}

    # 按分类归集 tools 字典中的工具 id
    tools_by_cat: dict[str, list[str]] = {}
    for tid, td in tools.items():
        tools_by_cat.setdefault(td.category, []).append(tid)

    for cat in core_cats:
        cat_tools = tools_by_cat.get(cat, [])
        if not cat_tools:
            continue
        if not any(tid in installed_tool_ids for tid in cat_tools):
            label = cat_label.get(cat, cat)
            issues.append(HealthIssue(
                severity="info",
                category="missing",
                tool_id=cat,
                title=f"{label}类工具未安装",
                detail=f"未检测到任何{label}工具",
                suggestion=f"建议安装常用{label}工具",
            ))

    issues.sort(key=lambda i: (_SEVERITY_RANK[i.severity], i.category, i.tool_id))
    return issues


def analyze_path() -> list[HealthIssue]:
    """分析 PATH 环境变量，标记重复条目与失效目录。"""
    path_str = os.environ.get("PATH", "")
    entries = path_str.split(os.pathsep)

    # 按规范化键统计出现次数，保留首次见到的原始形式
    counts: dict[str, int] = {}
    originals: dict[str, str] = {}
    order: list[str] = []
    for entry in entries:
        if not entry:
            continue
        key = os.path.normcase(entry)
        if key not in counts:
            counts[key] = 0
            originals[key] = entry
            order.append(key)
        counts[key] += 1

    issues: list[HealthIssue] = []
    for key in order:
        orig = originals[key]
        if counts[key] > 1:
            issues.append(HealthIssue(
                severity="warning",
                category="path",
                tool_id="_path",
                title="PATH 重复条目",
                detail=orig,
                suggestion="清理 PATH 中的重复条目以避免歧义",
            ))
        if not os.path.isdir(orig):
            issues.append(HealthIssue(
                severity="info",
                category="path",
                tool_id="_path",
                title="PATH 失效条目",
                detail=orig,
                suggestion="该目录不存在，可从 PATH 中移除",
            ))

    issues.sort(key=lambda i: (_SEVERITY_RANK[i.severity], i.detail))
    return issues
