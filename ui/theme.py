"""主题常量 — 唯一样式来源

设计方向: GitHub-Obsidian
暗色: #0d1117 基调 + 琥珀金 #f0a500 强调
亮色: #f6f8fa 基调 + 纯白卡片 + 深琥珀 #bf8700 强调
"""

from __future__ import annotations
import customtkinter as ctk

# ── 主色板（GitHub 色系 + 琥珀强调） ─────────────────────
COLORS: dict[str, dict[str, str]] = {
    # 背景层次（暗色 3 层深度，亮色 2 层深度）
    "bg_primary":     {"dark": "#0d1117", "light": "#f6f8fa"},
    "bg_card":        {"dark": "#161b22", "light": "#ffffff"},
    "bg_card_hover":  {"dark": "#1c2128", "light": "#f0f6fc"},
    "bg_sidebar":     {"dark": "#161b22", "light": "#ffffff"},
    "bg_topbar":      {"dark": "#161b22", "light": "#ffffff"},
    "bg_input":       {"dark": "#0d1117", "light": "#ffffff"},

    # 强调色 — 琥珀金，区别于通用蓝色
    "accent":         {"dark": "#f0a500", "light": "#bf8700"},
    "accent_hover":   {"dark": "#fbbf24", "light": "#9a6700"},
    "accent_subtle":  {"dark": "#1f1a00", "light": "#fff8e1"},

    # 语义色
    "success":        {"dark": "#3fb950", "light": "#1a7f37"},
    "success_subtle": {"dark": "#0d2b0d", "light": "#d1fadf"},
    "warning":        {"dark": "#d29922", "light": "#9a6700"},
    "danger":         {"dark": "#f85149", "light": "#cf222e"},

    # 文字层次
    "text_primary":   {"dark": "#e6edf3", "light": "#1f2328"},
    "text_secondary": {"dark": "#8d96a0", "light": "#636c76"},
    "text_muted":     {"dark": "#6e7681", "light": "#818b98"},
    "text_on_accent": {"dark": "#0d1117", "light": "#ffffff"},
    "text_on_success":{"dark": "#0d1117", "light": "#ffffff"},

    # 边框 / 分隔
    "border":         {"dark": "#30363d", "light": "#d0d7de"},
    "border_muted":   {"dark": "#21262d", "light": "#d8dee4"},
    "border_accent":  {"dark": "#f0a500", "light": "#bf8700"},
    "separator":      {"dark": "#21262d", "light": "#d8dee4"},
}

# ── 分类专属色（GitHub 色板，每类独立色相） ────────────────
CATEGORY_COLORS: dict[str, dict[str, str]] = {
    "lang":      {"dark": "#79c0ff", "light": "#0969da"},   # 蓝
    "pkg":       {"dark": "#d2a8ff", "light": "#8250df"},   # 紫
    "vcs":       {"dark": "#3fb950", "light": "#1a7f37"},   # 绿
    "container": {"dark": "#ff7b72", "light": "#cf222e"},   # 红
    "db":        {"dark": "#ffa657", "light": "#bc4c00"},   # 橙
    "cloud":     {"dark": "#39c5cf", "light": "#0550ae"},   # 青
    "build":     {"dark": "#e3b341", "light": "#9a6700"},   # 金
    "runtime":   {"dark": "#7ee787", "light": "#2da44e"},   # 浅绿
}

# ── 字体 ────────────────────────────────────────────────
# 层级：app_title > heading > body > small，差距拉开 2pt 以上
FONTS: dict[str, tuple] = {
    "app_title": ("Segoe UI", 18, "bold"),   # 顶栏标题
    "subtitle":  ("Segoe UI", 11),           # 顶栏副标题
    "heading":   ("Segoe UI", 13, "bold"),   # 分类标题 / 详情工具名
    "body":      ("Segoe UI", 12),           # 正文 / 按钮
    "small":     ("Segoe UI", 11),           # 次要说明
    "label":     ("Segoe UI", 10, "bold"),   # 节标题（大写感）
    "mono":      ("Consolas", 11),           # 版本号 / 路径
    "mono_sm":   ("Consolas", 10),           # 命令行
    "tag":       ("Segoe UI", 10, "bold"),   # 徽章
}

# ── 间距 / 尺寸 ──────────────────────────────────────────
SPACING: dict[str, int] = {
    "card_pad":    14,
    "section_gap": 20,
    "card_radius": 8,
    "btn_radius":  6,
    "input_radius":8,
    "topbar_h":    58,
    "card_w":      175,   # 卡片加宽适配更大字体
    "card_h":      88,    # 卡片加高
    "panel_w":     320,
    "cat_bar_w":   4,     # 左侧分类彩条稍宽
}


# ── 工具函数 ─────────────────────────────────────────────

def get_color(key: str) -> str:
    """按当前主题返回单色字符串。"""
    mode = ctk.get_appearance_mode().lower()
    entry = COLORS.get(key, {"dark": "#ff00ff", "light": "#ff00ff"})
    return entry.get(mode, entry["dark"])


def get_ctk_color(key: str) -> list[str]:
    """返回 CTK 双色列表 [dark, light]。"""
    entry = COLORS.get(key, {"dark": "#ff00ff", "light": "#ff00ff"})
    return [entry["dark"], entry["light"]]


def get_category_color(cat: str) -> str:
    """按当前主题返回分类单色。"""
    mode = ctk.get_appearance_mode().lower()
    entry = CATEGORY_COLORS.get(cat, {"dark": "#6e7681", "light": "#818b98"})
    return entry.get(mode, entry["dark"])


def get_category_ctk_color(cat: str) -> list[str]:
    """返回分类颜色 CTK 双色列表。"""
    entry = CATEGORY_COLORS.get(cat, {"dark": "#6e7681", "light": "#818b98"})
    return [entry["dark"], entry["light"]]
