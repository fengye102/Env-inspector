"""单工具检测逻辑 — subprocess + 注册表 + 固定路径兜底"""

from __future__ import annotations

import os
import re
import subprocess
import time
import winreg
from pathlib import Path
from typing import Optional

from core.registry import ScanResult, ToolDefinition

# 超时控制
CMD_TIMEOUT_MS = 5000
CMD_TIMEOUT_S = CMD_TIMEOUT_MS / 1000.0


def detect_tool(tool: ToolDefinition) -> ScanResult:
    """对单个工具执行检测,按优先级: PATH → 注册表 → fallback_paths."""
    start = time.perf_counter_ns()
    result = _do_detect(tool)
    elapsed = (time.perf_counter_ns() - start) // 1_000_000
    result.scan_duration_ms = int(elapsed)
    return result


def _do_detect(tool: ToolDefinition) -> ScanResult:
    """实际检测逻辑,返回填充基本字段的 ScanResult."""
    # ————— 1. 执行版本命令 (PATH 查找) —————
    for cmd in tool.commands:
        ver, raw, exe_path = _run_command(cmd)
        if ver is not None:
            return ScanResult(
                tool_id=tool.id,
                installed=True,
                version=ver,
                raw_output=raw,
                install_path=exe_path,
            )
        # --version 可能写 stderr（如 java）,再试一次 stderr 模式
        ver, raw, exe_path = _run_command(cmd, prefer_stderr=True)
        if ver is not None:
            return ScanResult(
                tool_id=tool.id,
                installed=True,
                version=ver,
                raw_output=raw,
                install_path=exe_path,
            )

    # ————— 2. Windows 注册表查找 —————
    for reg_path in tool.registry_keys:
        exe_path = _find_in_registry(reg_path)
        if exe_path:
            # 找到路径后再尝试执行确认版本
            ver, raw = _run_executable(exe_path, tool.commands[0] if tool.commands else None)
            if ver:
                return ScanResult(
                    tool_id=tool.id,
                    installed=True,
                    version=ver,
                    raw_output=raw,
                    install_path=exe_path,
                )
            return ScanResult(
                tool_id=tool.id,
                installed=True,
                version=None,
                raw_output=None,
                install_path=exe_path,
            )

    # ————— 3. fallback_paths 固定路径兜底 —————
    for fb_path in tool.fallback_paths:
        expanded = os.path.expandvars(fb_path)
        p = Path(expanded)
        if p.exists():
            exe_str = str(p)
            ver, raw = _run_executable(exe_str, tool.commands[0] if tool.commands else None)
            if ver:
                return ScanResult(
                    tool_id=tool.id,
                    installed=True,
                    version=ver,
                    raw_output=raw,
                    install_path=exe_str,
                )
            return ScanResult(
                tool_id=tool.id,
                installed=True,
                version=None,
                raw_output=None,
                install_path=exe_str,
            )

    # ————— 全部失败 —————
    return ScanResult(
        tool_id=tool.id,
        installed=False,
        error="not found in PATH, registry, or fallback paths",
    )


def _run_command(cmd: str, prefer_stderr: bool = False) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """执行命令，返回 (version, raw_output, exe_path)。
    使用 shell=True 以便在 Windows 上正确执行 .cmd / .bat 脚本
    （npm、mvn、gradle 等工具均以脚本形式存在，直接调用会 FileNotFoundError）。
    """
    try:
        cmd_name = cmd.split()[0]   # 取首个词用于 where 定位
        proc = subprocess.run(
            cmd,
            shell=True,             # 让 cmd.exe 处理 .cmd/.bat 脚本
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CMD_TIMEOUT_S,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = proc.stderr if prefer_stderr else proc.stdout
        # java -version 写入 stderr，自动补偿
        if not output and proc.stderr:
            output = proc.stderr
        if not output and proc.stdout:
            output = proc.stdout

        version = _parse_version(output) if output else None
        if version is None:
            return None, None, None   # 命令不存在或输出无版本号，早期返回

        exe_path = _locate_exe(cmd_name)
        return version, (output or "").strip()[:500], exe_path
    except subprocess.TimeoutExpired:
        return None, None, None
    except OSError:
        return None, None, None


def _find_in_registry(reg_path: str) -> Optional[str]:
    """在 Windows 注册表中查找路径,返回找到的可执行文件路径."""
    try:
        # 格式: HKLM\SOFTWARE\...\value_name 或 HKLM\SOFTWARE\...
        if "\\" not in reg_path:
            return None

        if reg_path.upper().startswith("HKLM"):
            key_path = reg_path[4:]  # 去掉 HKLM
            root = winreg.HKEY_LOCAL_MACHINE
        elif reg_path.upper().startswith("HKCU"):
            key_path = reg_path[4:]
            root = winreg.HKEY_CURRENT_USER
        elif reg_path.upper().startswith("HKCR"):
            key_path = reg_path[4:]
            root = winreg.HKEY_CLASSES_ROOT
        else:
            key_path = reg_path
            root = winreg.HKEY_LOCAL_MACHINE

        key_path = key_path.strip("\\")
        # 分割出 key 和 value name
        *key_parts, value_name = key_path.rsplit("\\", 1)

        with winreg.OpenKey(root, "\\".join(key_parts)) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            if isinstance(value, str) and value:
                # 可能是 InstallPath 的子目录
                exe_dir = os.path.expandvars(value)
                # 尝试找常见 exe 名称
                for exe_name in _guess_exe_names(key_path):
                    candidate = os.path.join(exe_dir, exe_name)
                    if os.path.isfile(candidate):
                        return candidate
                # 直接返回目录
                return exe_dir
    except (FileNotFoundError, OSError, ValueError):
        pass
    return None


def _guess_exe_names(key_path: str) -> list[str]:
    """根据注册表路径猜测可能的 exe 名称."""
    # 从路径中提取关键词
    parts = key_path.lower().split("\\")
    keywords = []
    for p in parts:
        if p not in ("microsoft", "windows", "currentversion", "software", ""):
            keywords.append(p)
    if not keywords:
        return []
    # 以最后一个有意义的名字作为 exe 名
    name = keywords[-1].replace(" ", "")
    candidates = [name, f"{name}.exe"]
    # 一些常见映射
    mapping = {
        "nodejs": "node.exe",
        "python": "python.exe",
        "javadevelopmentkit": "javac.exe",
        "docker": "docker.exe",
        "git": "git.exe",
    }
    for k, v in mapping.items():
        if k in key_path.lower():
            candidates.insert(0, v)
    return candidates


def _run_executable(exe_path: str, sample_cmd: str | None) -> tuple[Optional[str], Optional[str]]:
    """对已知完整路径的可执行文件尝试执行版本命令。
    使用列表传参以正确处理路径中的空格（如 C:\\Program Files\\...）。
    """
    if not sample_cmd:
        cmd_args = [exe_path, "--version"]
    else:
        parts = sample_cmd.split()
        parts[0] = exe_path          # 将命令名替换为完整路径
        cmd_args = parts
    try:
        proc = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CMD_TIMEOUT_S,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = proc.stdout or proc.stderr
        if not output:
            return None, None
        version = _parse_version(output)
        return version, output.strip()[:500]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None, None


def _locate_exe(cmd_name: str) -> Optional[str]:
    """在 PATH 中定位可执行文件."""
    try:
        where_proc = subprocess.run(
            ["where", cmd_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if where_proc.returncode == 0 and where_proc.stdout.strip():
            return where_proc.stdout.strip().split("\n")[0].strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _parse_version(raw: str) -> Optional[str]:
    """从命令输出中提取版本号，找不到版本模式则返回 None（不降级为错误文本）。"""
    if not raw:
        return None
    # 优先匹配 x.y.z 或 x.y.z-tag
    match = re.search(r"(\d+\.\d+\.\d+(?:[.-][a-zA-Z0-9]+)?)", raw)
    if match:
        return match.group(1)
    # 降级匹配 x.y
    match = re.search(r"(\d+\.\d+)", raw)
    if match:
        return match.group(1)
    # 找不到版本号：说明是错误信息或无关输出，返回 None
    return None