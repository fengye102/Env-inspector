markdown# CLAUDE.md — env_inspector 项目规范

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
- 关联工具间的跨工具版本兼容性检查（规则复杂、误报率高）

---

## 二、技术选型

| 层级   | 选型                                      | 理由                        |
| ---- | --------------------------------------- | ------------------------- |
| 语言   | Python 3.11+                            | subprocess 调 CLI 最自然；生态完善 |
| GUI  | CustomTkinter                           | 现代外观；比 PyQt 轻；无需商业授权      |
| 并发   | `concurrent.futures.ThreadPoolExecutor` | 扫描 IO 密集，线程池足够            |
| 打包   | PyInstaller（单文件模式）                      | `--onefile` 输出单个 exe      |
| 依赖管理 | `requirements.txt`                      | 简单项目不需要 poetry            |

**Python 版本锁定：** 3.11（PyInstaller 对 3.12+ 的支持尚不稳定）

---

## 三、目录结构
env_inspector/

├── CLAUDE.md                  # 本文件（项目规范）

├── README.md                  # 用户文档

├── requirements.txt           # Python 依赖

├── build.bat                  # 一键打包脚本

├── main.py                    # 入口，仅负责启动 App

│

├── core/

│   ├── init.py

│   ├── scanner.py             # 扫描引擎（并发调度 + 结果聚合）

│   ├── detector.py            # 单工具检测逻辑（subprocess + 注册表 + 路径）

│   ├── registry.py            # 工具定义注册表（唯一数据源）

│   ├── conflict.py            # 版本冲突检测

│   ├── exporter.py            # 扫描报告导出（JSON / HTML / 文本清单）

│   └── health.py              # 环境健康检查（冲突 / PATH / 超时 / 缺失）

│

├── ui/

│   ├── init.py

│   ├── app.py                 # 主窗口（App 类）

│   ├── home_frame.py          # 主界面（搜索栏 + 分类卡片列表）

│   ├── detail_panel.py        # 右侧详情面板（版本/路径/命令/冲突警告）

│   ├── tool_card.py           # 单个工具卡片组件

│   ├── health_banner.py       # 顶部健康提示横幅（内联展示，非弹窗）

│   └── theme.py               # 颜色/字体/尺寸常量（唯一样式来源）

│

├── assets/

│   └── icon.ico               # 应用图标

│

└── dist/                      # 打包输出目录（gitignore）

└── env_inspector.exe

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
    id: str                          # 唯一 ID，如 "python"
    display_name: str                # 展示名称，如 "Python"
    category: str                    # 分类，见下方分类表
    description: str                 # 一句话说明，面向非程序员
    commands: list[str]              # 检测命令，按优先级排列
    extra_info_cmd: str | None       # 可选：获取额外信息的命令
    docs_url: str                    # 官方文档 URL
    common_cmds: list[dict]          # 常用命令列表
    registry_keys: list[str]         # Windows 注册表查找路径（可为空）
    fallback_paths: list[str]        # 固定路径兜底
    multi_version_paths: list[str]   # 【新增】支持多版本扫描的根目录，如
                                     # ["C:\\Python*", "C:\\Users\\*\\AppData\\Local\\Programs\\Python\\Python*"]
                                     # 留空表示该工具不做多版本扫描

# common_cmds 格式：
# {"label": "查看版本", "cmd": "python --version", "desc": "显示当前 Python 版本"}
```

### 4.2 扫描结果

```python
@dataclass
class ScanResult:
    tool_id: str
    installed: bool
    version: str | None              # 解析后的版本号，如 "3.11.5"
    raw_output: str | None           # 命令原始输出
    executable_path: str | None      # 【重命名】可执行文件完整路径，如 C:\Python311\python.exe
    install_dir: str | None          # 【新增】安装根目录，如 C:\Python311
    extra_info: str | None           # 额外信息（Docker 容器数量等）
    error: str | None                # 检测失败原因
    scan_duration_ms: int            # 本次扫描耗时
    all_versions: list[VersionEntry] # 【新增】所有检测到的版本，见 4.3
    has_conflict: bool               # 【新增】是否存在版本冲突（见 §九：存在 2 个及以上不同版本）
```

### 4.3 版本条目（多版本支持）

```python
@dataclass
class VersionEntry:
    version: str             # 版本号，如 "3.11.5"
    executable_path: str     # 该版本的可执行文件路径
    install_dir: str         # 该版本的安装根目录
    is_active: bool          # 是否是 PATH 中优先生效的版本
```

---

## 五、工具分类

| 分类 ID       | 展示名称   | 代表工具                           |
| ----------- | ------ | ------------------------------ |
| `lang`      | 编程语言   | Python、Java、Node.js、Go、Rust    |
| `pkg`       | 包管理器   | pip、npm、yarn、Maven、Gradle      |
| `vcs`       | 版本控制   | Git、SVN、GitHub CLI             |
| `container` | 容器     | Docker、kubectl、Podman          |
| `db`        | 数据库    | MySQL、PostgreSQL、Redis、MongoDB |
| `cloud`     | 云工具    | AWS CLI、Azure CLI、gcloud       |
| `build`     | 构建工具   | Make、CMake、Ninja               |
| `runtime`   | 运行时/其他 | Flutter、Android ADB、WSL        |

---

## 六、扫描引擎规范

### 检测优先级（detector.py）

执行版本命令（PATH 查找）

→ 成功：记录版本 + executable_path + install_dir
查找 Windows 注册表（registry_keys）

→ 找到：记录路径，再尝试执行确认版本
检查 fallback_paths 固定路径

→ 文件存在：记录路径，尝试执行
全部失败：installed = False


### install_dir 推断规则

`install_dir` 由 `executable_path` 推断，不单独执行命令：

```python
def infer_install_dir(executable_path: str, tool_id: str) -> str:
    # 规则：可执行文件通常在 bin/ 或 Scripts/ 子目录下
    # 向上一级即为安装根目录
    # 例：C:\Python311\python.exe → C:\Python311
    # 例：C:\Program Files\nodejs\node.exe → C:\Program Files\nodejs
    # 例：C:\Python311\Scripts\pip.exe → C:\Python311（Scripts 的上级）
    path = Path(executable_path)
    parent = path.parent
    if parent.name.lower() in ("bin", "scripts", "cmd"):
        return str(parent.parent)
    return str(parent)
```

### 并发规范

- 最大并发：`min(32, cpu_count * 4)`，默认上限 16
- 单命令超时：**5 秒**
- 超时后：`installed = False`，`error = "timeout"`
- 所有命令捕获 stdout + stderr

### 版本号解析

- 用正则从 raw_output 提取第一个 `\d+\.\d+[\.\d]*` 模式
- 解析失败时保留 raw_output 前 100 字符作为 version 字段
- 不抛异常，降级处理

---

## 七、UI 规范

### 7.1 主题（theme.py 定义，不得在其他文件硬编码颜色）

```python
COLORS = {
    "bg_primary":    {"dark": "#1a1a2e", "light": "#f5f5f5"},
    "bg_card":       {"dark": "#16213e", "light": "#ffffff"},
    "bg_card_hover": {"dark": "#0f3460", "light": "#e8f0fe"},
    "accent":        {"dark": "#4fc3f7", "light": "#1976d2"},
    "success":       {"dark": "#66bb6a", "light": "#2e7d32"},
    "warning":       {"dark": "#ffa726", "light": "#e65100"},  # 【新增】冲突警告色
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
┌──────────────────────────────────────────────────┐

│  🔍 环境探针    已安装 32/58  ⚠️冲突 2   [刷新][主题] │

├──────────────────────────────────────────────────┤

│  搜索...   [全部] [语言] [包管理] [容器] [⚠️冲突]  │  ← 新增冲突筛选

├────────────────────────────┬─────────────────────┤

│  编程语言 (5/7)          ▼ │                      │

│  ┌────────┐ ┌──────────┐  │   Python             │

│  │✅Python │ │⚠️Java   │  │   版本：3.11.5        │

│  │ 3.11.5 │ │ 冲突     │  │   路径：C:\Python311  │

│  └────────┘ └──────────┘  │   ─────────────────  │

│                            │   ⚠️ 检测到多个版本   │

│                            │   3.11.5  C:\Python311│

│                            │   3.14.0  C:\Python314│

│                            │   （PATH 中生效：3.11）│

│                            │   ─────────────────  │

│                            │   常用命令（可复制）   │

└────────────────────────────┴─────────────────────┘

### 7.3 交互规范

- 启动后自动开始扫描，顶部显示进度条
- 扫描完成后显示统计：「已安装 X/Y，检测到 Z 个版本冲突」
- 卡片状态标记：
  * ✅ 已安装（无冲突）
  * ⚠️ 版本冲突（橙色边框）
  * ❌ 未检测到
- 顶部新增「⚠️ 冲突」快捷筛选 tab
- 命令复制：点击复制图标，显示 1.5 秒"已复制"提示
- 分类标题点击：折叠/展开，带 200ms 动画
- 搜索：实时过滤，延迟 200ms 防抖

### 7.4 文案规范（面向非程序员）

- 卡片标题：工具名称（英文原名）
- 路径展示文案：「安装位置：C:\Python311」（不说"install_dir"）
- 冲突说明文案：「检测到 X 个版本，当前生效版本为 Y」
- 状态文字：「已安装」/ 「版本冲突」/ 「未检测到」

---

## 八、工具注册表规范（registry.py）

**原则：registry.py 是唯一数据源。** 新增工具只改这一个文件。

支持多版本扫描的工具需填写 `multi_version_paths`（glob 格式）：

| 工具      | multi_version_paths 示例                                          |
| ------- | --------------------------------------------------------------- |
| Python  | `C:\Python*`、`%LOCALAPPDATA%\Programs\Python\Python*`           |
| Java    | `C:\Program Files\Java\*`、`C:\Program Files\Eclipse Adoptium\*` |
| Node.js | `C:\Program Files\nodejs`、`%APPDATA%\nvm\v*`（nvm 管理场景）         |
| Go      | `C:\Go`、`C:\Program Files\Go`                                   |
| Ruby    | `C:\Ruby*`                                                       |

其余工具（包管理器、容器、DB 等）`multi_version_paths` 留空，不做多版本扫描。

---

## 九、冲突检测规范（conflict.py）

### 冲突定义

**同一工具存在 2 个及以上不同版本的可执行文件** = 冲突。不跨工具比较兼容性。

### 检测流程

```python
def detect_all_versions(tool_def: ToolDefinition) -> list[VersionEntry]:
    """
    1. 收集所有候选路径：
       - PATH 中 which(tool) 找到的路径
       - glob 展开 multi_version_paths 中的所有匹配目录
       - fallback_paths 中存在的路径
    2. 对每个候选路径执行版本命令，超时 3 秒
    3. 去重（相同 executable_path 只保留一条）
    4. 标记 is_active：与 PATH 中优先找到的路径一致的条目
    5. 返回 list[VersionEntry]，按版本号排序
    """
```

### 冲突严重程度

不分级，所有冲突统一展示为 ⚠️ 警告。原因：严重程度判断依赖场景，工具无法准确判定，展示事实即可。

### 性能约束

- 多版本扫描在主扫描结束后异步执行，不阻塞首屏展示
- 单工具多版本扫描总超时：**10 秒**（允许比单命令超时长，因为要扫多个路径）
- glob 展开结果超过 20 个路径时，只取前 20 个

---

## 十、打包规范

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
- [ ] 在无 Python 的 Windows 环境测试 exe

---

## 十一、开发阶段规划

### Phase 1 — MVP（已完成）✅

- [x] 项目骨架搭建
- [x] `registry.py`：25 种工具数据
- [x] `detector.py`：单工具检测逻辑
- [x] `scanner.py`：并发扫描引擎
- [x] 基础 GUI：卡片列表 + 扫描进度
- [x] 详情面板：版本/路径/命令复制

### Phase 2 — 路径 & 冲突检测（已完成）✅

- [x] `ScanResult` 扩展：`executable_path`、`install_dir`、`all_versions`、`has_conflict`
- [x] `ToolDefinition` 扩展：`multi_version_paths`
- [x] `detector.py`：补充 `install_dir` 推断逻辑
- [x] `conflict.py`：多版本扫描 + 冲突检测（按版本号去重判断）
- [x] `detail_panel.py`：展示安装路径 + 冲突版本列表
- [x] `tool_card.py`：冲突状态 ⚠️ 展示
- [x] `home_frame.py`：冲突筛选 tab + 顶部冲突计数
- [x] `theme.py`：新增 `warning` 颜色

### Phase 3 — 体验完善（当前）

- [x] 搜索 + 分类过滤
- [x] 深色/浅色主题切换
- [ ] 工具数量扩展至 60 种
- [x] **报告导出**：`exporter.py` 导出 JSON / HTML / 文本清单，顶栏「导出」按钮
- [x] **健康检查**：`health.py` 分析冲突 / PATH 失效 / 超时 / 缺失，`health_banner.py` 顶部内联横幅展示（禁止弹窗）
- [x] **深度信息**：`detail_panel.py` 展示 `extra_info`（pip 全局包、Docker 容器数等）
- [x] **快捷操作**：`detail_panel.py` 新增「打开安装目录」「复制本工具信息」按钮

### Phase 4 — 发布

- [ ] 图标设计
- [ ] PyInstaller 打包测试
- [ ] README 更新
- [ ] GitHub Release

---

## 十二、禁止事项

- 禁止在 `theme.py` 以外的文件硬编码颜色或字体
- 禁止在 `registry.py` 以外定义工具元数据
- 禁止扫描超时超过 **5 秒**（多版本扫描单工具上限 10 秒）
- 禁止弹出额外窗口（详情用面板，错误用顶部 banner）
- 禁止捕获异常后静默忽略，必须记录到 `ScanResult.error`
- 禁止做跨工具版本兼容性判断（如"Node 版本太低导致 npm 不兼容"）
- 禁止修改已有规范后不更新本文件

---

## 十三、报告导出与健康检查规范（Phase 3）

### 13.1 报告导出（`core/exporter.py`）

纯函数模块，输入 `list[ScanResult]` 与 `dict[str, ToolDefinition]`，输出字符串，**不涉及任何 UI / 文件 IO**（写文件由调用方负责）。

- `export_json(results, tools) -> str`：结构化 JSON，含 `scan_time`、`total`、`installed`、`conflicts` 计数与各工具详情（id/name/category/installed/version/executable_path/install_dir/has_conflict/all_versions/extra_info/error/scan_duration_ms）。
- `export_html(results, tools) -> str`：自包含 HTML（内联 CSS，GitHub-Obsidian 风格，颜色取自 `theme.py` 常量而非硬编码），按类别分组的表格，冲突行与未安装行有视觉标记。
- `export_text_manifest(results, tools) -> str`：纯文本环境清单，每行 `名称\t版本\t路径`，仅含已安装工具，便于复制分享。

### 13.2 健康检查（`core/health.py`）

纯分析模块，**禁止做跨工具版本兼容性判断**（见 §十二），仅基于本机可计算的事实。

`HealthIssue` 数据结构：`severity`（`error`/`warning`/`info`）、`category`（`conflict`/`version`/`timeout`/`path`/`missing`）、`tool_id`、`title`、`detail`、`suggestion`。

- `analyze(results, tools) -> list[HealthIssue]`：
  - `conflict`：`has_conflict` 的工具，列出版本号，建议清理旧版本或调整 PATH 顺序；
  - `version`：`installed=True` 但 `version=None`，建议检查版本命令；
  - `timeout`：`error=="timeout"`，建议重试；
  - `missing`：核心类别（lang/pkg/vcs）全部未安装，info 提示。
- `analyze_path() -> list[HealthIssue]`：分析 `os.environ["PATH"]`，标记**重复条目**与**不存在的失效目录**（`tool_id="_path"`）。

### 13.3 UI 接入规范

- **导出**：顶栏「导出」按钮 → 调用 `tkinter.filedialog.asksaveasfilename` 选路径 → 写 JSON + HTML → 顶部 banner 提示「已导出」。
- **健康检查**：扫描完成后由 `ui/health_banner.py` 在主界面顶部**内联展示**问题列表（禁止弹窗，见 §十二）；每条显示严重度图标 + 标题 + 建议，可折叠/收起。
- **深度信息 / 快捷操作**：在 `detail_panel.py` 面板内新增区块，`extra_info` 用等宽字体多行展示；「打开安装目录」用 `os.startfile`，「复制本工具信息」写剪贴板（仅当前工具的名称/版本/路径）。

---

*最后更新：2026-07-14*
*技术栈：Python 3.11 + CustomTkinter + PyInstaller*