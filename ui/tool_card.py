"""工具卡片 — 左侧分类彩条 + 清晰的状态/版本层次"""

from __future__ import annotations
from typing import Callable
import customtkinter as ctk

from core.registry import ScanResult, ToolDefinition
from ui.theme import FONTS, SPACING, get_category_ctk_color, get_ctk_color


class ToolCard(ctk.CTkFrame):
    """
    固定尺寸卡片:
      [彩条] [工具名]
             [版本 / 未检测到]
    彩条颜色 = 分类色（已安装）或边框色（未安装）。
    """

    def __init__(
        self,
        parent,
        tool: ToolDefinition,
        result: ScanResult | None,
        on_click: Callable[[ToolDefinition, ScanResult | None], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            width=SPACING["card_w"],
            height=SPACING["card_h"],
            corner_radius=SPACING["card_radius"],
            fg_color=get_ctk_color("bg_card"),
            border_width=1,
            border_color=get_ctk_color("border_muted"),
            **kwargs,
        )
        self._tool = tool
        self._result = result
        self._on_click = on_click
        self._selected = False

        self.pack_propagate(False)
        # grid_propagate stays True so grid placement can resize the card width
        self._build()
        self._bind_events()

    # ── 构建 ─────────────────────────────────────────────

    def _build(self) -> None:
        installed = bool(self._result and self._result.installed)

        # 左侧分类彩条
        bar_color = (
            get_category_ctk_color(self._tool.category)
            if installed else get_ctk_color("border_muted")
        )
        bar = ctk.CTkFrame(self, width=SPACING["cat_bar_w"],
                           corner_radius=0, fg_color=bar_color)
        bar.pack(side="left", fill="y")
        bar.pack_propagate(False)

        # 主内容
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True,
                  padx=(9, 8), pady=(10, 8))

        # 工具名
        ctk.CTkLabel(
            body,
            text=self._tool.display_name,
            font=FONTS["heading"],
            text_color=get_ctk_color("text_primary"),
            anchor="w",
        ).pack(fill="x")

        # 版本 / 状态
        if installed:
            ver = self._result.version or "已安装"
            ctk.CTkLabel(
                body,
                text=ver,
                font=FONTS["mono_sm"],
                text_color=get_ctk_color("success"),
                anchor="w",
            ).pack(fill="x", pady=(2, 0))
        else:
            ctk.CTkLabel(
                body,
                text="未检测到",
                font=FONTS["small"],
                text_color=get_ctk_color("text_muted"),
                anchor="w",
            ).pack(fill="x", pady=(2, 0))

    # ── 事件 ─────────────────────────────────────────────

    def _bind_events(self) -> None:
        self._bind_recursive(self)

    def _bind_recursive(self, w) -> None:
        w.bind("<Button-1>", self._handle_click)
        w.bind("<Enter>", self._handle_enter)
        w.bind("<Leave>", self._handle_leave)
        for child in w.winfo_children():
            self._bind_recursive(child)

    def _handle_click(self, _e=None) -> None:
        if self._on_click:
            self._on_click(self._tool, self._result)

    def _handle_enter(self, _e=None) -> None:
        if not self._selected:
            self.configure(fg_color=get_ctk_color("bg_card_hover"))

    def _handle_leave(self, _e=None) -> None:
        if not self._selected:
            self.configure(fg_color=get_ctk_color("bg_card"))

    def set_selected(self, v: bool) -> None:
        self._selected = v
        if v:
            self.configure(fg_color=get_ctk_color("bg_card_hover"),
                           border_color=get_ctk_color("border_accent"),
                           border_width=2)
        else:
            self.configure(fg_color=get_ctk_color("bg_card"),
                           border_color=get_ctk_color("border_muted"),
                           border_width=1)

    def update_result(self, result: ScanResult | None) -> None:
        self._result = result
        for c in self.winfo_children():
            c.destroy()
        self._build()
        self._bind_events()
