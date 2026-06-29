# CLAUDE.md — env_inspector 项目规范

> 本文件是项目的唯一权威规范。所有开发决策以此为准。
> 修改规范：先改此文件，再改实现，不得反向。

---

## 一、项目定位

**项目名：** `env_inspector`（环境探针）

**一句话定义：** 一个 Windows 桌面工具，一键扫描本机已安装的开发环境，以直观 GUI 呈现结果，面向非程序员用户。

**核心目标（按优先级）：**
1. 扫描准确 — 不漏报、不误报，覆盖 PATH + 注册表 + 常见安装路径
2. 看得懂 — 非程序员打开就明白，无需文档
3. 能分发 — 打包成单文件 exe，无需安装 Python 或任何运行时

**不做：**
- 跨平台支持（仅 Windows）
- 环境安装/卸载功能
- 远程扫描
- 云同步

---

## 二、技术选型

| 层级 | 选型 | 理由 |
|------|------|------|
| 语言 | Python 3.11+ | subprocess 调 CLI 最自然；生态完善 |
| GUI | CustomTkinter | 现代外观；比 PyQt 轻；无需商业授权 |
| 并发 | `concurrent.futures.ThreadPoolExecutor` | 扫描 IO 密集，线程池足够 |
| 打包 | PyInstaller（单文件模式） | `--onefile` 输出单个 exe |
| 依赖管理 | `requirements.txt` | 简单项目不需要 poetry |

**Python 版本锁定：** 3.11（PyInstaller 对 3.12+ 的支持尚不稳定）

---

## 三、目录结构

```
env_inspector/
├── CLAUDE.md                  # 本文件（项目规范）
├── README.md                  # 用户文档
├── requirements.txt           # Python 依赖
├── build.bat                  # 一键打包脚本
├── main.py                    # 入口，仅负责启动 App
│
├── core/
│   ├── __init__.py
│   ├── scanner.py             # 扫描引擎（并发调度 + 结果聚合）
│   ├── detector.py            # 单工具检测逻辑（subprocess + 注册表 + 路径）
│   └── registry.py            # 工具定义注册表（唯一数据源）
│
├── ui/
│   ├── __init__.py
│   ├── app.py                 # 主窗口（App 类）
│   ├── home_frame.py          # 主界面（搜索栏 + 分类卡片列表）
│   ├── detail_panel.py        # 右侧详情面板（版本/路径/命令）
│   ├── tool_card.py           # 单个工具卡片组件
│   └── theme.py               # 颜色/字体/尺寸常量（唯一样式来源）
│
├── assets/
│   └── icon.ico               # 应用图标
│
└── dist/                      # 打包输出目录（gitignore）
    └── env_inspector.exe
```

**命名规则：**
- Python 文件：`snake_case.py`
- 类名：`PascalCase`
- 常量：`UPPER_SNAKE_CASE`
- 变量/函数：`snake_case`

---

## 四、核心数据结构

### 4.1 工具定义（在 `core/registry.py` 中定义）

```python
@dataclass
class ToolDefinition:
    id: str                    # 唯一 ID，如 "python"
    display_name: str          # 展示名称，如 "Python"
    category: str              # 分类，见下方分类表
    description: str           # 一句话说明，面向非程序员
    commands: list[str]        # 检测命令，按优先级排列，如 ["python --version", "python3 --version"]
    extra_info_cmd: str | None # 可选：获取额外信息的命令，如 pip list
    docs_url: str              # 官方文档 URL
    common_cmds: list[dict]    # 常用命令列表，格式见下
    registry_keys: list[str]   # Windows 注册表查找路径（可为空）
    fallback_paths: list[str]  # 固定路径兜底，如 C:\Program Files\...

# common_cmds 格式：
# {"label": "查看版本", "cmd": "python --version", "desc": "显示当前 Python 版本"}
```

### 4.2 扫描结果

```python
@dataclass
class ScanResult:
    tool_id: str
    installed: bool
    version: str | None        # 解析后的版本号，如 "3.11.5"
    raw_output: str | None     # 命令原始输出
    install_path: str | None   # 可执行文件路径
    extra_info: str | None     # 额外信息（Docker 容器数量等）
    error: str | None          # 检测失败原因
    scan_duration_ms: int      # 本次扫描耗时
```

---

## 五、工具分类

| 分类 ID | 展示名称 | 代表工具 |
|---------|---------|---------|
| `lang` | 编程语言 | Python、Java、Node.js、Go、Rust |
| `pkg` | 包管理器 | pip、npm、yarn、Maven、Gradle |
| `vcs` | 版本控制 | Git、SVN、GitHub CLI |
| `container` | 容器 | Docker、kubectl、Podman |
| `db` | 数据库 | MySQL、PostgreSQL、Redis、MongoDB |
| `cloud` | 云工具 | AWS CLI、Azure CLI、gcloud |
| `build` | 构建工具 | Make、CMake、Ninja |
| `runtime` | 运行时/其他 | Flutter、Android ADB、WSL、Nginx |

---

## 六、扫描引擎规范

### 检测优先级（detector.py）

```
1. 执行版本命令（PATH 查找）
   → 成功：记录版本 + 路径
2. 查找 Windows 注册表（registry_keys）
   → 找到：记录路径，再尝试执行确认版本
3. 检查 fallback_paths 固定路径
   → 文件存在：记录路径，尝试执行
4. 全部失败：installed = False
```

### 并发规范

- 最大并发：`min(32, cpu_count * 4)`，默认上限 16
- 单命令超时：**5 秒**（不是 10 秒，10 秒体验差）
- 超时后：`installed = False`，`error = "timeout"`
- 所有命令捕获 stdout + stderr（`java -version` 写 stderr）

### 版本号解析

- 用正则从 raw_output 提取第一个 `\d+\.\d+[\.\d]*` 模式
- 解析失败时保留 raw_output 前 100 字符作为 version 字段
- 不抛异常，降级处理

---

## 七、UI 规范

### 7.1 主题（theme.py 定义，不得在其他文件硬编码颜色）

```python
# 双主题，跟随系统
COLORS = {
    "bg_primary":    {"dark": "#1a1a2e", "light": "#f5f5f5"},
    "bg_card":       {"dark": "#16213e", "light": "#ffffff"},
    "bg_card_hover": {"dark": "#0f3460", "light": "#e8f0fe"},
    "accent":        {"dark": "#4fc3f7", "light": "#1976d2"},
    "success":       {"dark": "#66bb6a", "light": "#2e7d32"},
    "text_primary":  {"dark": "#e0e0e0", "light": "#212121"},
    "text_muted":    {"dark": "#9e9e9e", "light": "#757575"},
    "border":        {"dark": "#2a2a4a", "light": "#e0e0e0"},
}

FONTS = {
    "title":   ("Segoe UI", 20, "bold"),
    "heading": ("Segoe UI", 13, "bold"),
    "body":    ("Segoe UI", 11),
    "mono":    ("Consolas", 10),
    "small":   ("Segoe UI", 9),
}

SPACING = {
    "card_pad": 12,
    "section_gap": 16,
    "card_radius": 8,
}
```

### 7.2 布局

```
┌──────────────────────────────────────────────────┐
│  🔍 环境探针          已安装 32/58    [刷新] [主题] │  ← 顶部栏
├──────────────────────────────────────────────────┤
│  搜索...   [全部] [语言] [包管理] [容器] ...        │  ← 过滤栏
├────────────────────────────┬─────────────────────┤
│  编程语言 (5/7)          ▼ │                      │
│  ┌────────┐ ┌────────┐    │   点击卡片后          │
│  │✅Python │ │✅Java  │    │   显示详情面板         │
│  │ 3.14.6 │ │ 21.0.11│    │                      │
│  └────────┘ └────────┘    │   工具名称            │
│  ┌────────┐ ┌────────┐    │   版本号              │
│  │✅Node  │ │❌Go    │    │   安装路径            │
│  │20.11.0 │ │未安装  │    │   ─────────          │
│  └────────┘ └────────┘    │   常用命令（可复制）   │
│                            │   官方文档链接         │
│  包管理器 (8/10)         ▼ │                      │
│  ...                       │                      │
└────────────────────────────┴─────────────────────┘
```

### 7.3 交互规范

- 启动后自动开始扫描，顶部显示进度条 + "正在扫描 Python..."
- 扫描完成后进度条消失，显示统计数字
- 卡片点击：右侧详情面板展开（不弹窗，避免打断浏览）
- 命令复制：点击命令行右侧复制图标，显示 1.5 秒"已复制"提示
- 分类标题点击：折叠/展开，带 200ms 动画
- 搜索：实时过滤（不需要按回车），延迟 200ms 防抖

### 7.4 文案规范（面向非程序员）

- 卡片标题：工具名称（英文原名，非程序员也认识 Python/Java）
- 描述：一句话，说用途不说原理。例：
  - Python：「用来运行 Python 程序的解释器」
  - Docker：「容器化工具，让程序在隔离环境中运行」
  - Git：「代码版本管理工具，记录文件的修改历史」
- 状态文字：「已安装」/ 「未检测到」（不用"未安装"，因为可能安装了但未加 PATH）

---

## 八、工具注册表规范（registry.py）

**原则：registry.py 是唯一数据源。** 新增工具只改这一个文件。

最终支持工具数量目标：**60 种**，分 8 个分类。

必须覆盖的高优先级工具（第一版 MVP）：

| 分类 | 工具（共 25 种） |
|------|----------------|
| 编程语言 | Python、Java、Node.js、Go、Rust、Ruby、PHP、.NET |
| 包管理器 | pip、npm、yarn、pnpm、Maven、Gradle、cargo |
| 版本控制 | Git、GitHub CLI |
| 容器 | Docker、kubectl |
| 数据库 | MySQL、PostgreSQL、Redis、MongoDB |
| 云工具 | AWS CLI |
| 构建工具 | Make、CMake |
| 运行时 | Flutter、WSL |

---

## 九、打包规范

```bat
:: build.bat
pyinstaller ^
  --onefile ^
  --windowed ^
  --icon=assets/icon.ico ^
  --name=env_inspector ^
  --add-data "assets;assets" ^
  main.py
```

输出：`dist/env_inspector.exe`

**打包前检查清单：**
- [ ] `requirements.txt` 与实际依赖一致
- [ ] 在干净虚拟环境中测试运行
- [ ] 在无 Python 的 Windows 环境测试 exe（可用虚拟机）

---

## 十、开发阶段规划

### Phase 1 — MVP（核心功能可用）
- [ ] 项目骨架搭建（目录结构 + 空文件）
- [ ] `registry.py`：定义 25 种工具数据
- [ ] `detector.py`：单工具检测逻辑
- [ ] `scanner.py`：并发扫描引擎
- [ ] 基础 GUI：卡片列表 + 扫描进度
- [ ] 详情面板：版本/路径/命令复制

### Phase 2 — 完善体验
- [ ] 搜索 + 分类过滤
- [ ] 分类折叠/展开
- [ ] 深色/浅色主题切换
- [ ] 工具数量扩展至 60 种

### Phase 3 — 发布准备
- [ ] 图标设计
- [ ] PyInstaller 打包 + 测试
- [ ] README 用户文档
- [ ] GitHub Release 上传

---

## 十一、禁止事项

- 禁止在 `theme.py` 以外的文件硬编码颜色或字体
- 禁止在 `registry.py` 以外定义工具元数据
- 禁止扫描超时超过 **5 秒**（用户体验底线）
- 禁止弹出额外窗口（详情用面板，错误用顶部 banner）
- 禁止捕获异常后静默忽略，必须记录到 `ScanResult.error`
- 禁止修改已有规范后不更新本文件

---

*最后更新：2026-06-29*
*技术栈：Python 3.11 + CustomTkinter + PyInstaller*
