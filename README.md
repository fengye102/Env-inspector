# env_inspector — 开发环境探针

> 一键扫描本机开发环境，直观展示已安装的工具和版本，面向所有人。

## 功能

- **25 种工具覆盖**：编程语言、包管理器、版本控制、容器、数据库、云工具、构建工具、运行时
- **三级检测**：PATH 命令 → Windows 注册表 → 常见安装路径，不漏报
- **并发扫描**：后台多线程，5 秒超时，启动即扫
- **现代 UI**：GitHub-Obsidian 风格，暗色/亮色双主题
- **零依赖运行**：打包为单文件 exe，无需安装 Python

## 使用

直接运行 `dist/env_inspector.exe`，无需安装任何依赖。

## 从源码运行

```bash
pip install -r requirements.txt
python main.py
```

## 打包

```bash
pip install pyinstaller
build.bat
```

输出：`dist/env_inspector.exe`

## 支持的工具

| 分类 | 工具 |
|------|------|
| 编程语言 | Python、Java、Node.js、Go、Rust、Ruby、PHP、.NET |
| 包管理器 | pip、npm、yarn、pnpm、Maven、Gradle、cargo |
| 版本控制 | Git、GitHub CLI |
| 容器 | Docker、kubectl |
| 数据库 | MySQL、PostgreSQL、Redis、MongoDB |
| 云工具 | AWS CLI |
| 构建工具 | Make、CMake |
| 运行时 | Flutter、WSL |

## 技术栈

- Python 3.11+ · CustomTkinter · PyInstaller
