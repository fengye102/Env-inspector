"""右侧详情面板"""

from __future__ import annotations
import webbrowser
import customtkinter as ctk

from core.registry import ScanResult, ToolDefinition
from ui.theme import FONTS, SPACING, get_category_ctk_color, get_ctk_color


class DetailPanel(ctk.CTkFrame):
    """固定宽度详情面板，无选中时显示引导，有选中时显示完整信息。"""

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(
            parent,
            width=SPACING["panel_w"],
            fg_color=get_ctk_color("bg_sidebar"),
            corner_radius=0,
            **kwargs,
        )
        self.pack_propagate(False)
        self._show_placeholder()

    # ── 公开 API ─────────────────────────────────────────

    def show_tool(self, tool: ToolDefinition, result: ScanResult | None) -> None:
        self._clear()
        self._render(tool, result)

    def clear(self) -> None:
        self._clear()
        self._show_placeholder()

    # ── 内部 ─────────────────────────────────────────────

    def _clear(self) -> None:
        for w in self.winfo_children():
            w.destroy()

    def _show_placeholder(self) -> None:
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.place(relx=0.5, rely=0.48, anchor="center")
        ctk.CTkLabel(
            outer, text="←",
            font=("Segoe UI", 28),
            text_color=get_ctk_color("border"),
        ).pack()
        ctk.CTkLabel(
            outer, text="点击卡片查看详情",
            font=FONTS["body"],
            text_color=get_ctk_color("text_muted"),
        ).pack(pady=(6, 0))

    def _render(self, tool: ToolDefinition, result: ScanResult | None) -> None:
        installed = bool(result and result.installed)
        pad = SPACING["card_pad"]

        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=get_ctk_color("border"),
            scrollbar_button_hover_color=get_ctk_color("text_muted"),
        )
        scroll.pack(fill="both", expand=True)

        # ── 头部卡片 ─────────────────────────────────────
        header = ctk.CTkFrame(
            scroll,
            fg_color=get_ctk_color("bg_card"),
            corner_radius=SPACING["card_radius"],
        )
        header.pack(fill="x", padx=pad, pady=(pad, 0))

        # 顶部分类彩条
        bar_col = (get_category_ctk_color(tool.category)
                   if installed else get_ctk_color("border_muted"))
        ctk.CTkFrame(header, height=4, corner_radius=0,
                     fg_color=bar_col).pack(fill="x")

        body = ctk.CTkFrame(header, fg_color="transparent")
        body.pack(fill="x", padx=pad, pady=(10, pad))

        # 工具名 + 状态
        name_row = ctk.CTkFrame(body, fg_color="transparent")
        name_row.pack(fill="x")

        icon_col = get_ctk_color("success") if installed else get_ctk_color("text_muted")
        ctk.CTkLabel(
            name_row,
            text="✓" if installed else "✗",
            font=("Segoe UI", 14, "bold"),
            text_color=icon_col, width=20,
        ).pack(side="left")
        ctk.CTkLabel(
            name_row,
            text=tool.display_name,
            font=("Segoe UI", 14, "bold"),
            text_color=get_ctk_color("text_primary"),
            anchor="w",
        ).pack(side="left", padx=(4, 0))

        # 状态标签 · 版本
        status_parts = ["已安装" if installed else "未检测到"]
        if installed and result and result.version:
            status_parts.append(result.version)
        ctk.CTkLabel(
            body,
            text=" · ".join(status_parts),
            font=FONTS["mono_sm"] if (installed and result and result.version)
                 else FONTS["small"],
            text_color=icon_col,
            anchor="w",
        ).pack(fill="x", pady=(3, 0))

        # 描述
        ctk.CTkLabel(
            body,
            text=tool.description,
            font=FONTS["small"],
            text_color=get_ctk_color("text_secondary"),
            anchor="w",
            wraplength=SPACING["panel_w"] - pad * 4,
            justify="left",
        ).pack(fill="x", pady=(8, 0))

        if not installed:
            self._docs_btn(scroll, tool)
            return

        # ── 基本信息 ─────────────────────────────────────
        info: list[tuple[str, str]] = []
        if result and result.version:
            info.append(("版本", result.version))
        if result and result.install_path:
            info.append(("路径", result.install_path))
        if result and result.scan_duration_ms:
            info.append(("耗时", f"{result.scan_duration_ms} ms"))

        if info:
            sec = self._section(scroll, "基本信息")
            for lbl, val in info:
                self._info_row(sec, lbl, val)

        # ── 常用命令 ─────────────────────────────────────
        if tool.common_cmds:
            sec = self._section(scroll, "常用命令")
            for item in tool.common_cmds:
                self._cmd_row(sec, item)

        self._docs_btn(scroll, tool)

    # ── 子构建器 ─────────────────────────────────────────

    def _section(self, parent, title: str) -> ctk.CTkFrame:
        pad = SPACING["card_pad"]
        outer = ctk.CTkFrame(
            parent, fg_color=get_ctk_color("bg_card"),
            corner_radius=SPACING["card_radius"],
        )
        outer.pack(fill="x", padx=pad, pady=(pad, 0))

        # 节标题
        ctk.CTkLabel(
            outer, text=title,
            font=FONTS["label"],
            text_color=get_ctk_color("text_secondary"),
            anchor="w",
        ).pack(fill="x", padx=pad, pady=(pad - 2, 0))

        # 分隔线
        ctk.CTkFrame(outer, height=1,
                     fg_color=get_ctk_color("separator")).pack(
            fill="x", padx=pad, pady=(4, 0)
        )

        content = ctk.CTkFrame(outer, fg_color="transparent")
        content.pack(fill="x", padx=0, pady=(4, pad // 2))
        return content

    def _info_row(self, parent, label: str, value: str) -> None:
        pad = SPACING["card_pad"]
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=pad, pady=(0, 3))
        ctk.CTkLabel(
            row, text=label,
            font=FONTS["small"],
            text_color=get_ctk_color("text_muted"),
            width=48, anchor="w",
        ).pack(side="left")
        ctk.CTkLabel(
            row, text=value,
            font=FONTS["mono_sm"],
            text_color=get_ctk_color("text_primary"),
            anchor="w",
            wraplength=SPACING["panel_w"] - 76,
        ).pack(side="left", fill="x", expand=True)

    def _cmd_row(self, parent, item: dict) -> None:
        pad = SPACING["card_pad"]
        outer = ctk.CTkFrame(
            parent,
            fg_color=get_ctk_color("bg_primary"),
            corner_radius=SPACING["btn_radius"],
        )
        outer.pack(fill="x", padx=pad, pady=(0, 4))

        left = ctk.CTkFrame(outer, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=7)

        ctk.CTkLabel(
            left, text=item.get("label", ""),
            font=FONTS["small"],
            text_color=get_ctk_color("text_muted"),
            anchor="w",
        ).pack(fill="x")

        cmd = item.get("cmd", "")
        ctk.CTkLabel(
            left, text=cmd,
            font=FONTS["mono_sm"],
            text_color=get_ctk_color("accent"),
            anchor="w",
        ).pack(fill="x")

        copy_btn = ctk.CTkButton(
            outer, text="复制",
            font=FONTS["small"],
            width=42, height=26,
            corner_radius=SPACING["btn_radius"],
            fg_color=get_ctk_color("accent"),
            text_color=get_ctk_color("text_on_accent"),
            hover_color=get_ctk_color("accent_hover"),
            command=lambda: None,
        )
        copy_btn.configure(command=lambda c=cmd: self._copy(c, copy_btn))
        copy_btn.pack(side="right", padx=6, pady=6)

    def _copy(self, cmd: str, btn: ctk.CTkButton) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(cmd)
        except Exception:
            pass
        btn.configure(text="✓")
        self.after(1500, lambda: btn.configure(text="复制"))

    def _docs_btn(self, parent, tool: ToolDefinition) -> None:
        if not tool.docs_url:
            return
        pad = SPACING["card_pad"]
        ctk.CTkButton(
            parent,
            text="查看官方文档  →",
            font=FONTS["body"],
            height=32,
            fg_color="transparent",
            text_color=get_ctk_color("accent"),
            hover_color=get_ctk_color("accent_subtle"),
            border_width=1,
            border_color=get_ctk_color("border"),
            corner_radius=SPACING["btn_radius"],
            command=lambda: webbrowser.open(tool.docs_url),
        ).pack(fill="x", padx=pad, pady=(SPACING["section_gap"], pad))
