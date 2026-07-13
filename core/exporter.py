"""
core/exporter.py — 扫描报告导出(纯函数,无 UI/文件 IO)

将 list[ScanResult] + dict[str, ToolDefinition] 转换为
JSON / HTML / 纯文本清单字符串。调用方负责写文件。
"""

from __future__ import annotations

import json
import html
import os
from datetime import datetime

from core.registry import (
    ScanResult,
    ToolDefinition,
    VersionEntry,
    CATEGORY_ORDER,
    CATEGORIES,
)


# 调色板对齐 theme.py 暗色
_PALETTE = {
    "bg": "#0d1117",
    "card": "#161b22",
    "text": "#e6edf3",
    "secondary": "#8d96a0",
    "accent": "#f0a500",
    "success": "#3fb950",
    "warning": "#d29922",
    "danger": "#f85149",
    "border": "#30363d",
}


def _sorted_results(
    results: list[ScanResult], tools: dict[str, ToolDefinition]
) -> list[ScanResult]:
    def key(r: ScanResult) -> tuple[int, str]:
        tool = tools.get(r.tool_id)
        category = tool.category if tool else ""
        name = tool.display_name if tool else r.tool_id
        return (CATEGORY_ORDER.get(category, 99), name)

    return sorted(results, key=key)


def export_json(results: list[ScanResult], tools: dict[str, ToolDefinition]) -> str:
    """结构化 JSON,含 scan_time / 计数 / 各工具详情"""
    tools_arr = []
    for r in _sorted_results(results, tools):
        tool = tools.get(r.tool_id)
        tools_arr.append({
            "id": r.tool_id,
            "name": tool.display_name if tool else r.tool_id,
            "category": tool.category if tool else "",
            "installed": r.installed,
            "version": r.version,
            "executable_path": r.executable_path,
            "install_dir": r.install_dir,
            "has_conflict": r.has_conflict,
            "all_versions": [
                {
                    "version": v.version,
                    "executable_path": v.executable_path,
                    "install_dir": v.install_dir,
                    "is_active": v.is_active,
                }
                for v in r.all_versions
            ],
            "extra_info": r.extra_info,
            "error": r.error,
            "scan_duration_ms": r.scan_duration_ms,
        })

    payload = {
        "scan_time": datetime.now().astimezone().isoformat(),
        "total": len(results),
        "installed": sum(1 for r in results if r.installed),
        "conflicts": sum(1 for r in results if r.has_conflict),
        "tools": tools_arr,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _render_section(
    label: str, rows: list[ScanResult], tools: dict[str, ToolDefinition]
) -> str:
    trs = []
    for r in rows:
        tool = tools.get(r.tool_id)
        name = tool.display_name if tool else r.tool_id
        if not r.installed:
            row_class = "missing"
            status = "未检测到"
            version = "-"
            path = "-"
        else:
            version = r.version or "-"
            path = r.executable_path or r.install_dir or "-"
            if r.has_conflict:
                row_class = "conflict"
                status = "版本冲突"
            else:
                row_class = "installed"
                status = "已安装"
        trs.append(
            f'<tr class="{row_class}">'
            f"<td>{html.escape(name)}</td>"
            f'<td class="status">{html.escape(status)}</td>'
            f'<td class="mono">{html.escape(version)}</td>'
            f'<td class="mono">{html.escape(path)}</td>'
            f"</tr>"
        )
    return (
        "<section>"
        f"<h2>{html.escape(label)}</h2>"
        "<table>"
        "<thead><tr><th>工具</th><th>状态</th><th>版本</th><th>安装路径</th></tr></thead>"
        f"<tbody>\n{''.join(trs)}\n</tbody>"
        "</table>"
        "</section>"
    )


def export_html(results: list[ScanResult], tools: dict[str, ToolDefinition]) -> str:
    """自包含 HTML 报告,内联 CSS,GitHub-Obsidian 暗色风格"""
    scan_time = datetime.now().astimezone().isoformat()
    total = len(results)
    installed = sum(1 for r in results if r.installed)
    conflicts = sum(1 for r in results if r.has_conflict)

    by_category: dict[str, list[ScanResult]] = {c["id"]: [] for c in CATEGORIES}
    unknown: list[ScanResult] = []
    for r in _sorted_results(results, tools):
        tool = tools.get(r.tool_id)
        cat = tool.category if tool else ""
        if cat in by_category:
            by_category[cat].append(r)
        else:
            unknown.append(r)

    sections = []
    for cat_def in CATEGORIES:
        rows = by_category.get(cat_def["id"], [])
        if rows:
            sections.append(_render_section(cat_def["label"], rows, tools))
    if unknown:
        sections.append(_render_section("其他", unknown, tools))

    body = "\n".join(sections)
    p = _PALETTE

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Env Inspector 扫描报告</title>
<style>
:root {{
  --bg: {p['bg']};
  --card: {p['card']};
  --text: {p['text']};
  --secondary: {p['secondary']};
  --accent: {p['accent']};
  --success: {p['success']};
  --warning: {p['warning']};
  --danger: {p['danger']};
  --border: {p['border']};
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  padding: 24px;
  background: var(--bg);
  color: var(--text);
  font-family: 'Segoe UI', sans-serif;
  font-size: 14px;
  line-height: 1.6;
}}
header {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px 24px;
  margin-bottom: 24px;
}}
header h1 {{
  margin: 0 0 8px 0;
  font-size: 22px;
  color: var(--accent);
}}
header .scan-time {{
  color: var(--secondary);
  font-size: 12px;
  font-family: 'Consolas', monospace;
}}
header .stats {{
  margin-top: 8px;
  color: var(--secondary);
}}
header .stats .num {{ color: var(--text); font-weight: 600; }}
header .stats .conflict-num {{ color: var(--warning); font-weight: 600; }}
section {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 16px;
}}
section h2 {{
  margin: 0 0 12px 0;
  font-size: 16px;
  color: var(--accent);
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}}
th, td {{
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}}
th {{
  color: var(--secondary);
  font-weight: 600;
  font-size: 12px;
}}
td.mono {{
  font-family: 'Consolas', monospace;
  font-size: 12px;
  color: var(--secondary);
  word-break: break-all;
}}
tr.missing td {{ color: var(--secondary); opacity: 0.6; }}
tr.missing .status {{ color: var(--danger); opacity: 1; }}
tr.conflict {{ border-left: 3px solid var(--warning); }}
tr.conflict .status {{ color: var(--warning); }}
tr.installed .status {{ color: var(--success); }}
.status {{ font-weight: 600; }}
</style>
</head>
<body>
<header>
  <h1>Env Inspector 扫描报告</h1>
  <div class="scan-time">{html.escape(scan_time)}</div>
  <div class="stats">总数 <span class="num">{total}</span> · 已安装 <span class="num">{installed}</span> · 冲突 <span class="conflict-num">{conflicts}</span></div>
</header>
{body}
</body>
</html>"""


def export_text_manifest(
    results: list[ScanResult], tools: dict[str, ToolDefinition]
) -> str:
    """纯文本环境清单,仅含已安装工具,每行 名称\t版本\t路径"""
    scan_time = datetime.now().astimezone().isoformat()
    lines = ["# Env Inspector 环境清单", scan_time, ""]
    for r in _sorted_results(results, tools):
        if not r.installed:
            continue
        tool = tools.get(r.tool_id)
        name = tool.display_name if tool else r.tool_id
        version = r.version if r.version else "-"
        path = r.executable_path or "-"
        lines.append(f"{name}\t{version}\t{path}")
    return "\n".join(lines)
