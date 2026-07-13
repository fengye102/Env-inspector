"""ui/health_banner.py — 环境健康检查结果内联横幅

扫描完成后在主界面顶部展示 HealthIssue 列表。
禁止弹窗（见 CLAUDE.md §12），全部使用内联 UI。
"""

from __future__ import annotations

import customtkinter as ctk

from core.health import HealthIssue
from ui.theme import FONTS, SPACING, get_ctk_color

_SEV_COLOR_KEY = {
    "error": "danger",
    "warning": "warning",
    "info": "text_muted",
}
_SEV_ICON = {
    "error": "✕",
    "warning": "⚠",
    "info": "ℹ",
}

# 横幅最大展开条目数，超出部分折叠提示，避免占用过多垂直空间
_MAX_EXPANDED = 20


class HealthBanner(ctk.CTkFrame):
    """可折叠的健康问题横幅。无问题时隐藏。"""

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(
            parent,
            fg_color=get_ctk_color("bg_card"),
            corner_radius=0,
            **kwargs,
        )
        self._issues: list[HealthIssue] = []
        self._collapsed = False

    # ── 公开 API ─────────────────────────────────────────

    def update_issues(self, issues: list[HealthIssue]) -> None:
        """更新问题列表；为空则隐藏，否则显示并重新渲染。"""
        self._issues = list(issues)
        if not self._issues:
            self.hide()
            return
        self.show()

    def show(self) -> None:
        if not self._issues:
            return
        self.grid()
        self._render()

    def hide(self) -> None:
        self.grid_remove()
        self._clear_children()

    # ── 内部 ─────────────────────────────────────────────

    def _clear_children(self) -> None:
        for w in self.winfo_children():
            w.destroy()

    def _render(self) -> None:
        self._clear_children()

        pad = SPACING["card_pad"]
        n_err = sum(1 for i in self._issues if i.severity == "error")
        n_warn = sum(1 for i in self._issues if i.severity == "warning")
        n_info = sum(1 for i in self._issues if i.severity == "info")

        # 顶部行：图标 + 摘要 + 折叠箭头
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=pad, pady=(pad - 2, 0))

        parts = []
        if n_err:
            parts.append(f"{n_err} 个错误")
        if n_warn:
            parts.append(f"{n_warn} 个警告")
        if n_info:
            parts.append(f"{n_info} 条提示")
        summary = "环境健康检查：" + " · ".join(parts) if parts else "环境健康检查：无问题"

        head_icon = "⚠" if (n_err or n_warn) else "ℹ"
        head_col = get_ctk_color("warning") if (n_err or n_warn) else get_ctk_color("text_muted")
        ctk.CTkLabel(
            head, text=head_icon,
            font=("Segoe UI", 14, "bold"),
            text_color=head_col, width=20,
        ).pack(side="left")
        ctk.CTkLabel(
            head, text=summary,
            font=FONTS["body"],
            text_color=get_ctk_color("text_primary"),
            anchor="w",
        ).pack(side="left", padx=(4, 0))

        arrow = "▸" if self._collapsed else "▾"
        ctk.CTkButton(
            head, text=arrow,
            font=FONTS["body"], width=28, height=24,
            corner_radius=SPACING["btn_radius"],
            fg_color="transparent",
            text_color=get_ctk_color("text_muted"),
            hover_color=get_ctk_color("bg_card_hover"),
            command=self._toggle,
        ).pack(side="right")

        # 分隔线
        ctk.CTkFrame(
            self, height=1, fg_color=get_ctk_color("separator")
        ).pack(fill="x", padx=pad, pady=(4, 0))

        # 展开时显示条目列表
        if not self._collapsed:
            body = ctk.CTkFrame(self, fg_color="transparent")
            body.pack(fill="x", padx=pad, pady=(4, pad - 2))
            for issue in self._issues[:_MAX_EXPANDED]:
                self._issue_row(body, issue)
            leftover = len(self._issues) - _MAX_EXPANDED
            if leftover > 0:
                ctk.CTkLabel(
                    body,
                    text=f"... 还有 {leftover} 条，请导出报告查看完整列表",
                    font=FONTS["small"],
                    text_color=get_ctk_color("text_muted"),
                    anchor="w",
                ).pack(fill="x", pady=(4, 0))

    def _issue_row(self, parent, issue: HealthIssue) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 4))

        sev = issue.severity
        icon = _SEV_ICON.get(sev, "•")
        col = get_ctk_color(_SEV_COLOR_KEY.get(sev, "text_muted"))
        ctk.CTkLabel(
            row, text=icon,
            font=("Segoe UI", 12, "bold"),
            text_color=col, width=18,
        ).pack(side="left")

        ctk.CTkLabel(
            row, text=issue.title,
            font=FONTS["small"],
            text_color=get_ctk_color("text_primary"),
            anchor="w",
        ).pack(side="left", padx=(2, 8))

        # 详情（路径/版本等）用等宽字体
        detail_text = issue.detail if issue.detail else ""
        if detail_text:
            ctk.CTkLabel(
                row, text=detail_text,
                font=FONTS["mono_sm"],
                text_color=get_ctk_color("text_muted"),
                anchor="w",
                wraplength=560,
                justify="left",
            ).pack(side="left", fill="x", expand=True)

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._render()
