"""主界面 — 搜索 + 分类过滤 + 卡片网格"""

from __future__ import annotations
from typing import Callable
import customtkinter as ctk

from core.registry import CATEGORIES, ScanResult, ToolDefinition, get_all_tools
from ui.theme import (
    FONTS, SPACING,
    get_category_ctk_color, get_ctk_color,
)
from ui.tool_card import ToolCard

# 分类中文名映射
_CAT_LABELS = {c["id"]: c["label"] for c in CATEGORIES}


class HomeFrame(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        on_card_click: Callable[[ToolDefinition, ScanResult | None], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, fg_color="transparent", corner_radius=0, **kwargs)

        self._on_card_click = on_card_click
        self._results: dict[str, ScanResult] = {}
        self._all_tools: list[ToolDefinition] = get_all_tools()
        self._active_cat: str = "all"
        self._search_q: str = ""
        self._debounce_id: str | None = None
        self._cards: dict[str, ToolCard] = {}
        self._selected_id: str | None = None
        self._collapsed: dict[str, bool] = {}

        self._build()

    # ── 公开 API ─────────────────────────────────────────

    def update_results(self, results: dict[str, ScanResult]) -> None:
        self._results = results
        self._refresh_cards()

    def update_single_result(self, result: ScanResult) -> None:
        self._results[result.tool_id] = result
        card = self._cards.get(result.tool_id)
        if card:
            card.update_result(result)

    def update_conflict_result(self, result: ScanResult) -> None:
        """主扫描完成后，冲突扫描阶段更新单张卡片"""
        self._results[result.tool_id] = result
        card = self._cards.get(result.tool_id)
        if card:
            card.update_result(result)

    def get_conflict_count(self) -> int:
        """返回检测到冲突的工具数量，供顶栏统计使用"""
        return sum(1 for r in self._results.values() if r.has_conflict)

    # ── 构建 ────────────────────────────────────────────

    def _build(self) -> None:
        self._build_toolbar()
        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=get_ctk_color("border"),
            scrollbar_button_hover_color=get_ctk_color("text_muted"),
        )
        self._scroll.pack(fill="both", expand=True)
        self._render_cards()

    def _build_toolbar(self) -> None:
        pad = SPACING["card_pad"]

        # ── 第一行：搜索框（紧凑，左对齐）────────────────────
        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.pack(fill="x", padx=pad, pady=(pad, 6))

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search_change)
        ctk.CTkEntry(
            search_row,
            placeholder_text="搜索工具...",
            textvariable=self._search_var,
            font=FONTS["small"],
            width=200,
            height=30,
            corner_radius=SPACING["input_radius"],
            fg_color=get_ctk_color("bg_input"),
            border_color=get_ctk_color("border"),
            text_color=get_ctk_color("text_primary"),
            placeholder_text_color=get_ctk_color("text_muted"),
        ).pack(side="left")

        # ── 第二行：分类 Tab（可横向滚动，防止截断）──────────
        tab_row = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            orientation="horizontal",
            height=46,
            scrollbar_button_color=get_ctk_color("border"),
            scrollbar_button_hover_color=get_ctk_color("text_muted"),
        )
        tab_row.pack(fill="x", padx=pad, pady=(0, 2))

        self._tab_btns: dict[str, ctk.CTkButton] = {}
        # 基础 tabs：全部 + 各分类 + 冲突筛选
        tabs = (
            [{"id": "all", "label": "全部"}]
            + list(CATEGORIES)
            + [{"id": "conflict", "label": "⚠ 冲突"}]
        )
        for tab in tabs:
            tid = tab["id"]
            active = tid == "all"
            btn = ctk.CTkButton(
                tab_row,
                text=tab["label"],
                font=FONTS["heading"],
                height=32,
                corner_radius=SPACING["btn_radius"],
                fg_color=get_ctk_color("accent") if active else "transparent",
                text_color=(get_ctk_color("text_on_accent") if active
                            else get_ctk_color("text_secondary")),
                hover_color=(get_ctk_color("accent_hover") if active
                             else get_ctk_color("bg_card_hover")),
                border_width=0,
                command=lambda t=tid: self._on_filter_click(t),
            )
            btn.pack(side="left", padx=(0, 6))
            self._tab_btns[tid] = btn

    # ── 卡片渲染 ─────────────────────────────────────────

    def _render_cards(self) -> None:
        for w in self._scroll.winfo_children():
            w.destroy()
        self._cards = {}

        tools = self._filtered_tools()
        if not tools:
            self._show_empty()
            return

        # 冲突筛选视图：不分组，直接平铺
        if self._active_cat == "conflict":
            grid = ctk.CTkFrame(self._scroll, fg_color="transparent")
            grid.pack(fill="x", padx=SPACING["card_pad"],
                      pady=(SPACING["section_gap"], 4))
            self._fill_grid(grid, tools)
            return

        grouped: dict[str, list[ToolDefinition]] = {}
        for t in tools:
            grouped.setdefault(t.category, []).append(t)

        for cat_meta in CATEGORIES:
            cid = cat_meta["id"]
            cat_tools = grouped.get(cid, [])
            if not cat_tools:
                continue
            n_installed = sum(
                1 for t in cat_tools
                if self._results.get(t.id) and self._results[t.id].installed
            )
            self._render_section(cid, cat_meta["label"], cat_tools, n_installed)

    def _show_empty(self) -> None:
        ctk.CTkLabel(
            self._scroll,
            text="没有匹配的工具",
            font=FONTS["body"],
            text_color=get_ctk_color("text_muted"),
        ).pack(pady=60)

    def _render_section(
        self,
        cat_id: str,
        label: str,
        tools: list[ToolDefinition],
        n_installed: int,
    ) -> None:
        collapsed = self._collapsed.get(cat_id, False)
        pad = SPACING["card_pad"]

        section = ctk.CTkFrame(self._scroll, fg_color="transparent")
        section.pack(fill="x", padx=pad, pady=(SPACING["section_gap"], 4))

        # ── 分类标题行 ───────────────────────────────────
        hdr = ctk.CTkFrame(section, fg_color="transparent")
        hdr.pack(fill="x")

        # 分类彩点
        ctk.CTkFrame(
            hdr, width=8, height=8, corner_radius=4,
            fg_color=get_category_ctk_color(cat_id),
        ).pack(side="left", padx=(0, 7), pady=7)

        # 分类名（可点击折叠）
        arrow = "▾" if not collapsed else "▸"
        ctk.CTkButton(
            hdr,
            text=f"{label}",
            font=FONTS["heading"],
            fg_color="transparent",
            text_color=get_ctk_color("text_primary"),
            hover_color=get_ctk_color("bg_card_hover"),
            anchor="w",
            height=28,
            command=lambda cid=cat_id: self._toggle_cat(cid),
        ).pack(side="left")

        # 折叠箭头
        ctk.CTkLabel(
            hdr, text=arrow, font=FONTS["body"],
            text_color=get_ctk_color("text_muted"), width=16,
        ).pack(side="left")

        # 已安装/总数徽章（右对齐）
        all_ok = n_installed == len(tools)
        badge_color = "success" if all_ok else "text_muted"
        ctk.CTkLabel(
            hdr,
            text=f"{n_installed} / {len(tools)}",
            font=FONTS["small"],
            text_color=get_ctk_color(badge_color),
        ).pack(side="right")

        # 水平分隔线
        ctk.CTkFrame(
            section, height=1,
            fg_color=get_ctk_color("separator"),
        ).pack(fill="x", pady=(4, 6))

        # ── 卡片网格 ─────────────────────────────────────
        if not collapsed:
            grid = ctk.CTkFrame(section, fg_color="transparent")
            grid.pack(fill="x")
            self._fill_grid(grid, tools)

    def _fill_grid(self, parent, tools: list[ToolDefinition]) -> None:
        COLS = 4
        GAP = 10

        for c in range(COLS):
            parent.grid_columnconfigure(c, weight=1, uniform="card_col")

        for i, tool in enumerate(tools):
            r, c = divmod(i, COLS)
            card = ToolCard(
                parent,
                tool=tool,
                result=self._results.get(tool.id),
                on_click=self._handle_card_click,
            )
            card.grid(row=r, column=c, sticky="ew",
                      padx=(0 if c == 0 else GAP // 2, 0 if c == COLS - 1 else GAP // 2),
                      pady=(0, GAP))
            self._cards[tool.id] = card

    def _refresh_cards(self) -> None:
        curr = set(self._cards.keys())
        want = {t.id for t in self._filtered_tools()}
        if curr != want:
            self._render_cards()
        else:
            for tid, card in self._cards.items():
                card.update_result(self._results.get(tid))

    # ── 过滤 ─────────────────────────────────────────────

    def _filtered_tools(self) -> list[ToolDefinition]:
        tools = self._all_tools
        if self._active_cat == "conflict":
            tools = [t for t in tools
                     if self._results.get(t.id) and self._results[t.id].has_conflict]
        elif self._active_cat != "all":
            tools = [t for t in tools if t.category == self._active_cat]
        if self._search_q:
            q = self._search_q.lower()
            tools = [t for t in tools
                     if q in t.display_name.lower() or q in t.description.lower()]
        return tools

    def _on_search_change(self, *_) -> None:
        if self._debounce_id:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(200, self._apply_search)

    def _apply_search(self) -> None:
        self._search_q = self._search_var.get().strip()
        self._render_cards()

    def _on_filter_click(self, cat_id: str) -> None:
        self._active_cat = cat_id
        for tid, btn in self._tab_btns.items():
            if tid == cat_id:
                btn.configure(
                    fg_color=get_ctk_color("accent"),
                    text_color=get_ctk_color("text_on_accent"),
                    font=FONTS["heading"],
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=get_ctk_color("text_secondary"),
                    font=FONTS["heading"],
                )
        self._render_cards()

    def _toggle_cat(self, cat_id: str) -> None:
        self._collapsed[cat_id] = not self._collapsed.get(cat_id, False)
        self._render_cards()

    # ── 卡片点击 ─────────────────────────────────────────

    def _handle_card_click(self, tool: ToolDefinition, result: ScanResult | None) -> None:
        if self._selected_id and self._selected_id in self._cards:
            self._cards[self._selected_id].set_selected(False)
        self._selected_id = tool.id
        card = self._cards.get(tool.id)
        if card:
            card.set_selected(True)
        if self._on_card_click:
            self._on_card_click(tool, result)
