"""右侧详情面板"""

from __future__ import annotations
import os
import webbrowser
import customtkinter as ctk

from core.registry import ScanResult, ToolDefinition, VersionEntry
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

        # 工具名 + 状态图标
        name_row = ctk.CTkFrame(body, fg_color="transparent")
        name_row.pack(fill="x")

        # 冲突时显示警告图标，否则正常安装/未安装图标
        if installed and result and result.has_conflict:
            icon_text = "⚠"
            icon_col = get_ctk_color("warning")
        elif installed:
            icon_text = "✓"
            icon_col = get_ctk_color("success")
        else:
            icon_text = "✗"
            icon_col = get_ctk_color("text_muted")

        ctk.CTkLabel(
            name_row,
            text=icon_text,
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
        if installed and result and result.has_conflict:
            status_text = "版本冲突"
            status_col = get_ctk_color("warning")
        elif installed:
            status_text = "已安装"
            status_col = get_ctk_color("success")
        else:
            status_text = "未检测到"
            status_col = get_ctk_color("text_muted")

        status_parts = [status_text]
        if installed and result and result.version:
            status_parts.append(result.version)

        ctk.CTkLabel(
            body,
            text=" · ".join(status_parts),
            font=FONTS["mono_sm"] if (installed and result and result.version)
                 else FONTS["small"],
            text_color=status_col,
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
        if result and result.install_dir:
            info.append(("安装位置", result.install_dir))
        # 仅在 executable_path 与 install_dir 不同时才单独展示
        if result and result.executable_path and result.install_dir:
            exe_dir = os.path.dirname(result.executable_path)
            if os.path.normcase(exe_dir) != os.path.normcase(result.install_dir):
                info.append(("可执行文件", result.executable_path))
        elif result and result.executable_path and not result.install_dir:
            info.append(("可执行文件", result.executable_path))
        if result and result.scan_duration_ms:
            info.append(("耗时", f"{result.scan_duration_ms} ms"))

        if info:
            sec = self._section(scroll, "基本信息")
            for lbl, val in info:
                self._info_row(sec, lbl, val)

        # ── 冲突警告节 ───────────────────────────────────
        if result and result.has_conflict and result.all_versions:
            self._conflict_section(scroll, result.all_versions)

        # ── 额外信息（pip 全局包 / Docker 容器数等） ──────
        if result and result.extra_info:
            self._extra_info_section(scroll, result.extra_info)

        # ── 常用命令 ─────────────────────────────────────
        if tool.common_cmds:
            sec = self._section(scroll, "常用命令")
            for item in tool.common_cmds:
                self._cmd_row(sec, item)

        # ── 快捷操作 ─────────────────────────────────────
        self._actions_row(scroll, tool, result)

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

    def _conflict_section(self, parent, versions: list[VersionEntry]) -> None:
        """渲染多版本冲突警告节。"""
        pad = SPACING["card_pad"]
        outer = ctk.CTkFrame(
            parent,
            fg_color=get_ctk_color("bg_card"),
            corner_radius=SPACING["card_radius"],
        )
        outer.pack(fill="x", padx=pad, pady=(pad, 0))

        # 节标题行（警告色）
        title_row = ctk.CTkFrame(outer, fg_color="transparent")
        title_row.pack(fill="x", padx=pad, pady=(pad - 2, 0))

        ctk.CTkLabel(
            title_row,
            text="⚠  检测到多个版本",
            font=FONTS["body"],
            text_color=get_ctk_color("warning"),
            anchor="w",
        ).pack(side="left")

        ctk.CTkLabel(
            title_row,
            text=f"共 {len(versions)} 个",
            font=FONTS["small"],
            text_color=get_ctk_color("text_muted"),
            anchor="e",
        ).pack(side="right")

        # 分隔线
        ctk.CTkFrame(outer, height=1,
                     fg_color=get_ctk_color("separator")).pack(
            fill="x", padx=pad, pady=(4, 0)
        )

        # 每个版本条目
        content = ctk.CTkFrame(outer, fg_color="transparent")
        content.pack(fill="x", padx=0, pady=(4, pad // 2))

        for entry in versions:
            self._version_entry_row(content, entry)

    def _version_entry_row(self, parent, entry: VersionEntry) -> None:
        """渲染单个 VersionEntry 行：版本号 + 安装目录 + 是否生效。"""
        pad = SPACING["card_pad"]
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=pad, pady=(0, 5))

        # 是否生效标记（左侧圆点）
        dot_col = get_ctk_color("success") if entry.is_active else get_ctk_color("border")
        ctk.CTkLabel(
            row,
            text="●",
            font=("Segoe UI", 8),
            text_color=dot_col,
            width=14,
        ).pack(side="left")

        # 版本号
        ctk.CTkLabel(
            row,
            text=entry.version,
            font=FONTS["mono_sm"],
            text_color=get_ctk_color("accent") if entry.is_active
                       else get_ctk_color("text_primary"),
            width=68,
            anchor="w",
        ).pack(side="left")

        # 安装目录（截断显示）
        dir_label = ctk.CTkLabel(
            row,
            text=entry.install_dir,
            font=FONTS["mono_sm"],
            text_color=get_ctk_color("text_muted"),
            anchor="w",
            wraplength=SPACING["panel_w"] - 140,
        )
        dir_label.pack(side="left", fill="x", expand=True)

        # 当前生效标签
        if entry.is_active:
            ctk.CTkLabel(
                row,
                text="当前生效",
                font=FONTS["small"],
                text_color=get_ctk_color("success"),
                anchor="e",
            ).pack(side="right")

    def _info_row(self, parent, label: str, value: str) -> None:
        pad = SPACING["card_pad"]
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=pad, pady=(0, 3))
        ctk.CTkLabel(
            row, text=label,
            font=FONTS["small"],
            text_color=get_ctk_color("text_muted"),
            width=56, anchor="w",
        ).pack(side="left")
        ctk.CTkLabel(
            row, text=value,
            font=FONTS["mono_sm"],
            text_color=get_ctk_color("text_primary"),
            anchor="w",
            wraplength=SPACING["panel_w"] - 84,
        ).pack(side="left", fill="x", expand=True)

    def _extra_info_section(self, parent, extra_info: str) -> None:
        """渲染额外信息节（等宽字体多行展示，只读）。"""
        pad = SPACING["card_pad"]
        outer = ctk.CTkFrame(
            parent, fg_color=get_ctk_color("bg_card"),
            corner_radius=SPACING["card_radius"],
        )
        outer.pack(fill="x", padx=pad, pady=(pad, 0))

        ctk.CTkLabel(
            outer, text="额外信息",
            font=FONTS["label"],
            text_color=get_ctk_color("text_secondary"),
            anchor="w",
        ).pack(fill="x", padx=pad, pady=(pad - 2, 0))
        ctk.CTkFrame(outer, height=1,
                     fg_color=get_ctk_color("separator")).pack(
            fill="x", padx=pad, pady=(4, 0))

        body = ctk.CTkTextbox(
            outer, height=130,
            font=FONTS["mono_sm"],
            fg_color=get_ctk_color("bg_primary"),
            text_color=get_ctk_color("text_primary"),
            corner_radius=SPACING["btn_radius"],
            wrap="word",
            activate_scrollbars=True,
        )
        body.pack(fill="x", padx=pad, pady=(4, pad // 2))
        body.insert("1.0", extra_info)
        body.configure(state="disabled")

    def _actions_row(self, parent, tool: ToolDefinition, result: ScanResult | None) -> None:
        """渲染快捷操作按钮行：打开安装目录 / 复制本工具信息。"""
        pad = SPACING["card_pad"]
        has_dir = bool(result and result.install_dir and os.path.isdir(result.install_dir))
        if not has_dir:
            return
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=pad, pady=(pad, 0))

        ctk.CTkButton(
            row, text="打开安装目录",
            font=FONTS["small"], height=30,
            corner_radius=SPACING["btn_radius"],
            fg_color=get_ctk_color("accent"),
            text_color=get_ctk_color("text_on_accent"),
            hover_color=get_ctk_color("accent_hover"),
            command=lambda: self._open_dir(result.install_dir),
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))

        copy_btn = ctk.CTkButton(
            row, text="复制信息",
            font=FONTS["small"], height=30,
            corner_radius=SPACING["btn_radius"],
            fg_color="transparent",
            text_color=get_ctk_color("accent"),
            hover_color=get_ctk_color("accent_subtle"),
            border_width=1,
            border_color=get_ctk_color("border"),
            command=lambda: self._copy_tool_info(tool, result, copy_btn),
        )
        copy_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))

    def _open_dir(self, dir_path: str) -> None:
        try:
            os.startfile(dir_path)  # Windows 资源管理器打开
        except OSError:
            pass

    def _copy_tool_info(self, tool: ToolDefinition, result: ScanResult | None, btn: ctk.CTkButton) -> None:
        lines = [tool.display_name]
        if result:
            if result.version:
                lines.append(f"版本: {result.version}")
            if result.executable_path:
                lines.append(f"路径: {result.executable_path}")
            if result.install_dir:
                lines.append(f"安装目录: {result.install_dir}")
        try:
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))
        except Exception:
            pass
        btn.configure(text="✓")
        self.after(1500, lambda: btn.configure(text="复制信息"))

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
