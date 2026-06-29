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

CMD_TIMEOUT_MS = 5000
CMD_TIMEOUT_S = CMD_TIMEOUT_MS / 1000.0


def infer_install_dir(executable_path: str) -> str:
    """从可执行文件路径推断安装根目录。"""
    path = Path(executable_path)
    parent = path.parent
    if parent.name.lower() in ("bin", "scripts", "cmd"):
        return str(parent.parent)
    return str(parent)


def detect_tool(tool: ToolDefinition) -> ScanResult:
    """对单个工具执行检测,按优先级: PATH → 注册表 → fallback_paths."""
    start = time.perf_counter_ns()
    result = _do_detect(tool)
    elapsed = (time.perf_counter_ns() - start) // 1_000_000
    result.scan_duration_ms = int(elapsed)
    return result


def _do_detect(tool: ToolDefinition) -> ScanResult:
    # ————— 1. 执行版本命令 (PATH 查找) —————
    for cmd in tool.commands:
        ver, raw, exe_path = _run_command(cmd)
        if ver is not None:
            install_dir = infer_install_dir(exe_path) if exe_path else None
            return ScanResult(
                tool_id=tool.id,
                installed=True,
                version=ver,
                raw_output=raw,
                executable_path=exe_path,
                install_dir=install_dir,
            )
        ver, raw, exe_path = _run_command(cmd, prefer_stderr=True)
        if ver is not None:
            install_dir = infer_install_dir(exe_path) if exe_path else None
            return ScanResult(
                tool_id=tool.id,
                installed=True,
                version=ver,
                raw_output=raw,
                executable_path=exe_path,
                install_dir=install_dir,
            )

    # ————— 2. Windows 注册表查找 —————
    for reg_path in tool.registry_keys:
        exe_path = _find_in_registry(reg_path)
        if exe_path:
            ver, raw = _run_executable(exe_path, tool.commands[0] if tool.commands else None)
            install_dir = infer_install_dir(exe_path)
            if ver:
                return ScanResult(
                    tool_id=tool.id,
                    installed=True,
                    version=ver,
                    raw_output=raw,
                    executable_path=exe_path,
                    install_dir=install_dir,
                )
            return ScanResult(
                tool_id=tool.id,
                installed=True,
                version=None,
                executable_path=exe_path,
                install_dir=install_dir,
            )

    # ————— 3. fallback_paths 固定路径兜底 —————
    for fb_path in tool.fallback_paths:
        expanded = os.path.expandvars(fb_path)
        p = Path(expanded)
        if p.exists():
            exe_str = str(p)
            ver, raw = _run_executable(exe_str, tool.commands[0] if tool.commands else None)
            install_dir = infer_install_dir(exe_str)
            if ver:
                return ScanResult(
                    tool_id=tool.id,
                    installed=True,
                    version=ver,
                    raw_output=raw,
                    executable_path=exe_str,
                    install_dir=install_dir,
                )
            return ScanResult(
                tool_id=tool.id,
                installed=True,
                version=None,
                executable_path=exe_str,
                install_dir=install_dir,
            )

    # ————— 全部失败 —————
    return ScanResult(
        tool_id=tool.id,
        installed=False,
        error="not found in PATH, registry, or fallback paths",
    )


def _run_command(cmd: str, prefer_stderr: bool = False) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """执行命令，返回 (version, raw_output, exe_path)。"""
    try:
        cmd_name = cmd.split()[0]
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CMD_TIMEOUT_S,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = proc.stderr if prefer_stderr else proc.stdout
        if not output and proc.stderr:
            output = proc.stderr
        if not output and proc.stdout:
            output = proc.stdout

        version = _parse_version(output) if output else None
        if version is None:
            return None, None, None

        exe_path = _locate_exe(cmd_name)
        return version, (output or "").strip()[:500], exe_path
    except subprocess.TimeoutExpired:
        return None, None, None
    except OSError:
        return None, None, None


def _find_in_registry(reg_path: str) -> Optional[str]:
    """在 Windows 注册表中查找路径,返回找到的可执行文件路径."""
    try:
        if "\\" not in reg_path:
            return None

        if reg_path.upper().startswith("HKLM"):
            key_path = reg_path[4:]
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
        *key_parts, value_name = key_path.rsplit("\\", 1)

        with winreg.OpenKey(root, "\\".join(key_parts)) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            if isinstance(value, str) and value:
                exe_dir = os.path.expandvars(value)
                for exe_name in _guess_exe_names(key_path):
                    candidate = os.path.join(exe_dir, exe_name)
                    if os.path.isfile(candidate):
                        return candidate
                return exe_dir
    except (FileNotFoundError, OSError, ValueError):
        pass
    return None


def _guess_exe_names(key_path: str) -> list[str]:
    parts = key_path.lower().split("\\")
    keywords = []
    for p in parts:
        if p not in ("microsoft", "windows", "currentversion", "software", ""):
            keywords.append(p)
    if not keywords:
        return []
    name = keywords[-1].replace(" ", "")
    candidates = [name, f"{name}.exe"]
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
    """对已知完整路径的可执行文件尝试执行版本命令。"""
    if not sample_cmd:
        cmd_args = [exe_path, "--version"]
    else:
        parts = sample_cmd.split()
        parts[0] = exe_path
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
    """从命令输出中提取版本号，找不到版本模式则返回 None。"""
    if not raw:
        return None
    match = re.search(r"(\d+\.\d+\.\d+(?:[.-][a-zA-Z0-9]+)?)", raw)
    if match:
        return match.group(1)
    match = re.search(r"(\d+\.\d+)", raw)
    if match:
        return match.group(1)
    return None
