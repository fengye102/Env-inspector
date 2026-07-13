"""主窗口"""

from __future__ import annotations
import ctypes, os, sys
import customtkinter as ctk
from tkinter import filedialog

from core.registry import ScanResult, ToolDefinition, get_all_tools, get_tool
from core.scanner import Scanner
from core.exporter import export_json, export_html
from core.health import analyze, analyze_path
from ui.detail_panel import DetailPanel
from ui.health_banner import HealthBanner
from ui.home_frame import HomeFrame
from ui.theme import FONTS, SPACING, get_ctk_color

if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

WIN_W, WIN_H = 1140, 720
WIN_MIN_W, WIN_MIN_H = 900, 580


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Env Inspector — 环境探针")
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.minsize(WIN_MIN_W, WIN_MIN_H)
        self.configure(fg_color=get_ctk_color("bg_primary"))

        _set_icon(self)

        self._scan_results: dict[str, ScanResult] = {}
        self._scanner: Scanner | None = None

        self._build_ui()
        self.after(100, self._start_scan)

    # ── 布局 ─────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.grid_rowconfigure(0, weight=0)  # topbar
        self.grid_rowconfigure(1, weight=0)  # progress
        self.grid_rowconfigure(2, weight=0)  # health banner
        self.grid_rowconfigure(3, weight=1)  # content
        self.grid_columnconfigure(0, weight=1)

        self._build_topbar()
        self._build_progress()
        self._build_health_banner()
        self._build_content()

    def _build_topbar(self) -> None:
        bar = ctk.CTkFrame(
            self,
            height=SPACING["topbar_h"],
            fg_color=get_ctk_color("bg_topbar"),
            corner_radius=0,
        )
        bar.grid(row=0, column=0, sticky="ew")
        bar.pack_propagate(False)

        # 底部分隔线（1px）
        sep = ctk.CTkFrame(bar, height=1, corner_radius=0,
                           fg_color=get_ctk_color("separator"))
        sep.place(relx=0, rely=1.0, anchor="sw", relwidth=1.0)

        # ── 左：标题 ─────────────────────────────────────
        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.pack(side="left", padx=16, fill="y")

        ctk.CTkLabel(
            left,
            text="env_inspector",
            font=FONTS["app_title"],
            text_color=get_ctk_color("accent"),
        ).pack(side="left", pady=0)

        ctk.CTkLabel(
            left,
            text="开发环境探针",
            font=FONTS["subtitle"],
            text_color=get_ctk_color("text_muted"),
        ).pack(side="left", padx=(10, 0))

        # ── 右：统计 + 操作 ──────────────────────────────
        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.pack(side="right", padx=12, fill="y")

        # 主题切换（图标按钮）
        self._theme_btn = ctk.CTkButton(
            right,
            text="◐",
            font=("Segoe UI", 14),
            width=32, height=32,
            corner_radius=SPACING["btn_radius"],
            fg_color="transparent",
            text_color=get_ctk_color("text_muted"),
            hover_color=get_ctk_color("bg_card_hover"),
            border_width=1,
            border_color=get_ctk_color("border"),
            command=self._toggle_theme,
        )
        self._theme_btn.pack(side="right", padx=(4, 0))

        # 刷新按钮
        self._refresh_btn = ctk.CTkButton(
            right,
            text="↺  刷新",
            font=FONTS["body"],
            width=82, height=32,
            corner_radius=SPACING["btn_radius"],
            fg_color=get_ctk_color("accent"),
            text_color=get_ctk_color("text_on_accent"),
            hover_color=get_ctk_color("accent_hover"),
            command=self._start_scan,
        )
        self._refresh_btn.pack(side="right", padx=(0, 6))

        # 导出按钮
        self._export_btn = ctk.CTkButton(
            right,
            text="⤓  导出",
            font=FONTS["body"],
            width=82, height=32,
            corner_radius=SPACING["btn_radius"],
            fg_color="transparent",
            text_color=get_ctk_color("text_secondary"),
            hover_color=get_ctk_color("bg_card_hover"),
            border_width=1,
            border_color=get_ctk_color("border"),
            command=self._export_report,
            state="disabled",
        )
        self._export_btn.pack(side="right", padx=(0, 6))

        # 统计数字
        self._stats_label = ctk.CTkLabel(
            right,
            text="",
            font=FONTS["body"],
            text_color=get_ctk_color("text_secondary"),
            width=160,
            anchor="e",
        )
        self._stats_label.pack(side="right", padx=(0, 12))

    def _build_progress(self) -> None:
        self._prog_frame = ctk.CTkFrame(
            self, height=3, fg_color="transparent", corner_radius=0
        )
        self._prog_frame.grid(row=1, column=0, sticky="ew")
        self._prog_frame.grid_propagate(False)

        self._prog_bar = ctk.CTkProgressBar(
            self._prog_frame,
            mode="determinate",
            height=3,
            corner_radius=0,
            fg_color=get_ctk_color("separator"),
            progress_color=get_ctk_color("accent"),
        )
        self._prog_bar.pack(fill="x")
        self._prog_bar.set(0)

        self._prog_label = ctk.CTkLabel(
            self._prog_frame,
            text="",
            font=FONTS["small"],
            text_color=get_ctk_color("text_muted"),
        )
        # 进度标签显示在 topbar 统计位置，不占行

        self._prog_frame.grid_remove()

    def _build_health_banner(self) -> None:
        self._health_banner = HealthBanner(self)
        # 默认不显示，扫描完成后由 _update_health_banner 决定
        self._health_banner.grid(row=2, column=0, sticky="ew")
        self._health_banner.grid_remove()

    def _build_content(self) -> None:
        content = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        content.grid(row=3, column=0, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=0, minsize=SPACING["panel_w"])

        self._home = HomeFrame(content, on_card_click=self._on_card_click)
        self._home.grid(row=0, column=0, sticky="nsew")

        # 分隔线
        ctk.CTkFrame(content, width=1, corner_radius=0,
                     fg_color=get_ctk_color("separator")).grid(
            row=0, column=1, sticky="ns"
        )

        self._detail = DetailPanel(content)
        self._detail.grid(row=0, column=1, sticky="nsew")

    # ── 扫描 ─────────────────────────────────────────────

    def _start_scan(self) -> None:
        if self._scanner and self._scanner.is_running:
            return
        self._scan_results = {}
        self._stats_label.configure(text="正在扫描...")
        self._refresh_btn.configure(state="disabled")
        self._export_btn.configure(state="disabled")
        self._prog_bar.set(0)
        self._prog_frame.grid()
        self._health_banner.hide()

        self._scanner = Scanner(
            on_progress=self._on_progress,
            on_complete=self._on_complete,
            on_error=self._on_error,
            on_conflict_update=self._on_conflict_update,
        )
        self._scanner.start()

    def _on_progress(self, result: ScanResult, done: int, total: int) -> None:
        self.after(0, lambda r=result, d=done, t=total: self._ui_progress(r, d, t))

    def _ui_progress(self, result: ScanResult, done: int, total: int) -> None:
        self._prog_bar.set(done / total if total else 0)
        tool = get_tool(result.tool_id)
        name = tool.display_name if tool else result.tool_id
        self._stats_label.configure(text=f"检测中  {name}...")
        self._home.update_single_result(result)

    def _on_complete(self, results: list[ScanResult]) -> None:
        self.after(0, lambda: self._ui_complete(results))

    def _ui_complete(self, results: list[ScanResult]) -> None:
        self._scan_results = {r.tool_id: r for r in results}
        self._home.update_results(self._scan_results)

        n_installed = sum(1 for r in results if r.installed)
        total = len(results)
        n_conflict = sum(1 for r in results if r.has_conflict)

        if n_conflict > 0:
            self._stats_label.configure(
                text=f"已安装 {n_installed}/{total}  ⚠ {n_conflict} 冲突"
            )
        else:
            self._stats_label.configure(text=f"已安装  {n_installed} / {total}")

        self._refresh_btn.configure(state="normal")
        self._export_btn.configure(state="normal")
        self._prog_frame.grid_remove()
        self._update_health_banner()

    def _on_error(self, msg: str) -> None:
        self.after(0, lambda: self._ui_error(msg))

    def _ui_error(self, msg: str) -> None:
        self._stats_label.configure(text=f"出错: {msg[:32]}")
        self._refresh_btn.configure(state="normal")
        self._prog_frame.grid_remove()

    # ── 冲突更新回调 ─────────────────────────────────────

    def _on_conflict_update(self, result: ScanResult) -> None:
        """多版本扫描完成后，从后台线程回调到主线程更新 UI。"""
        self.after(0, lambda r=result: self._ui_conflict_update(r))

    def _ui_conflict_update(self, result: ScanResult) -> None:
        """在主线程中更新冲突结果并刷新顶栏计数。"""
        self._scan_results[result.tool_id] = result
        self._home.update_conflict_result(result)

        # 更新顶栏冲突计数
        n_conflict = self._home.get_conflict_count()
        if n_conflict > 0:
            installed = sum(1 for r in self._scan_results.values() if r.installed)
            total = len(self._scan_results)
            self._stats_label.configure(
                text=f"已安装 {installed}/{total}  ⚠ {n_conflict} 冲突"
            )

        # 冲突状态变化后刷新健康横幅
        self._update_health_banner()

    # ── 健康检查 / 导出 ───────────────────────────────────

    def _update_health_banner(self) -> None:
        """基于当前扫描结果与 PATH 重新计算健康问题并刷新横幅。"""
        if not self._scan_results:
            self._health_banner.hide()
            return
        tools_dict = {t.id: t for t in get_all_tools()}
        results_list = list(self._scan_results.values())
        issues = analyze(results_list, tools_dict) + analyze_path()
        self._health_banner.update_issues(issues)

    def _export_report(self) -> None:
        """导出 JSON + HTML 报告到用户选择的路径。"""
        if not self._scan_results:
            return
        tools_dict = {t.id: t for t in get_all_tools()}
        results_list = list(self._scan_results.values())

        path = filedialog.asksaveasfilename(
            title="导出扫描报告",
            defaultextension=".html",
            filetypes=[
                ("HTML 报告", "*.html"),
                ("JSON 数据", "*.json"),
                ("所有文件", "*.*"),
            ],
            initialfile="env_inspector_report.html",
        )
        if not path:
            return

        try:
            # 始终同时输出 HTML 与 JSON，便于查看与二次处理
            base, _ = os.path.splitext(path)
            html_path = base + ".html"
            json_path = base + ".json"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(export_html(results_list, tools_dict))
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(export_json(results_list, tools_dict))
            self._stats_label.configure(text=f"已导出 {os.path.basename(html_path)}")
        except OSError as e:
            self._stats_label.configure(text=f"导出失败: {str(e)[:24]}")

    # ── 卡片点击 / 主题 ──────────────────────────────────

    def _on_card_click(self, tool: ToolDefinition, result: ScanResult | None) -> None:
        self._detail.show_tool(tool, result)

    def _toggle_theme(self) -> None:
        mode = ctk.get_appearance_mode()
        ctk.set_appearance_mode("light" if mode.lower() == "dark" else "dark")


# ── 图标辅助 ─────────────────────────────────────────────

def _set_icon(win: ctk.CTk) -> None:
    ico = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")
    if os.path.isfile(ico):
        try:
            win.iconbitmap(ico)
        except Exception:
            pass
