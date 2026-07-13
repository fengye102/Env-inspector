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
    if result.installed and tool.extra_info_cmd:
        result.extra_info = _run_extra_info(tool.extra_info_cmd)
    return result


def _run_extra_info(cmd: str) -> str | None:
    """执行额外信息命令(如 pip list / docker ps),返回截断后的输出。

    extra_info_cmd 常含 shell 语法(管道、2>nul),故用 shell=True。
    """
    try:
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
        output = (proc.stdout or proc.stderr or "").strip()
        return output[:500] if output else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def _do_detect(tool: ToolDefinition) -> ScanResult:
    """对单个工具执行检测,按优先级: PATH → 注册表 → fallback_paths."""
    timeout_seen = False

    # ————— 1. 执行版本命令 (PATH 查找) —————
    for cmd in tool.commands:
        ver, raw, exe_path, err = _run_command(cmd)
        if err == "timeout":
            timeout_seen = True
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
        exe_path = _find_in_registry(reg_path, tool)
        if exe_path:
            ver, raw, err = _run_executable(exe_path, tool.commands[0] if tool.commands else None)
            if err == "timeout":
                timeout_seen = True
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
            ver, raw, err = _run_executable(exe_str, tool.commands[0] if tool.commands else None)
            if err == "timeout":
                timeout_seen = True
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
    # 规范 §六:超时后 error="timeout";§十二:禁止静默忽略
    return ScanResult(
        tool_id=tool.id,
        installed=False,
        error="timeout" if timeout_seen else "not found in PATH, registry, or fallback paths",
    )


def _run_command(cmd: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """执行命令，返回 (version, raw_output, exe_path, error)。

    单次 subprocess 同时捕获 stdout+stderr，优先用 stdout 解析版本，失败回退 stderr，
    避免对输出到 stderr 的工具(如 java -version)二次执行。
    error 为 'timeout' / 'os_error' / None。
    """
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
        output = proc.stdout or proc.stderr
        version = _parse_version(output) if output else None
        if version is None:
            return None, None, None, None
        exe_path = _locate_exe(cmd_name)
        return version, (output or "").strip()[:500], exe_path, None
    except subprocess.TimeoutExpired:
        return None, None, None, "timeout"
    except OSError:
        return None, None, None, "os_error"


# 注册表中常见的安装路径值名("" 为键的默认值)
_REG_INSTALL_VALUE_NAMES = (
    "", "InstallPath", "InstallLocation", "InstallDir",
    "JavaHome", "Path", "DisplayIcon", "Root",
    "UninstallString", "ProgramExecutablePath", "exe",
)

_REG_ROOT_PREFIXES = {
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
    "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
    "HKCU": winreg.HKEY_CURRENT_USER,
    "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
    "HKCR": winreg.HKEY_CLASSES_ROOT,
    "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
}


def _split_reg_root(reg_path: str) -> tuple[int, str]:
    """分离根键前缀,返回 (predefined_root, 剩余路径)。无前缀默认 HKLM。"""
    upper = reg_path.upper()
    for prefix, hkey in _REG_ROOT_PREFIXES.items():
        if upper.startswith(prefix + "\\"):
            return hkey, reg_path[len(prefix) + 1:]
    return winreg.HKEY_LOCAL_MACHINE, reg_path


def _find_in_registry(reg_path: str, tool: ToolDefinition) -> Optional[str]:
    """在 Windows 注册表中查找工具可执行文件路径。

    支持路径段中的 * 通配符(枚举所有子键);叶子键读取默认值及常见安装路径
    值名,并下探一层子键以适配 Java 等版本子键模式。依次尝试
    HKLM 64 位、HKLM 32 位、HKCU。
    """
    if "\\" not in reg_path:
        return None
    root, sub_path = _split_reg_root(reg_path)
    segments = [s for s in sub_path.split("\\") if s]
    if not segments:
        return None

    exe_name = _exe_name_for_tool(tool)
    roots_to_try: list[tuple[int, int]] = [
        (root, 0),
        (root, winreg.KEY_WOW64_32KEY),
    ]
    if root == winreg.HKEY_LOCAL_MACHINE:
        roots_to_try.append((winreg.HKEY_CURRENT_USER, 0))

    for hkey, access_flag in roots_to_try:
        values: list[str] = []
        _walk_reg_for_values(hkey, access_flag, segments, 0, "", values)
        for raw_value in values:
            exe = _exe_from_reg_value(raw_value, exe_name)
            if exe:
                return exe
    return None


def _walk_reg_for_values(
    predefined_root: int,
    access_flag: int,
    segments: list[str],
    idx: int,
    current_path: str,
    out: list[str],
    depth: int = 0,
) -> None:
    """递归遍历注册表,展开 * 通配符,在叶子键收集候选字符串值。"""
    if depth > 24 or len(out) > 200:
        return
    try:
        key_handle = winreg.OpenKey(
            predefined_root, current_path, access=winreg.KEY_READ | access_flag
        )
    except (FileNotFoundError, OSError):
        return

    try:
        if idx >= len(segments):
            _collect_reg_values(key_handle, out)
            return
        seg = segments[idx]
        if seg == "*":
            i = 0
            while len(out) <= 200:
                try:
                    child_name = winreg.EnumKey(key_handle, i)
                except OSError:
                    break
                child_path = f"{current_path}\\{child_name}" if current_path else child_name
                _walk_reg_for_values(
                    predefined_root, access_flag, segments, idx + 1, child_path, out, depth + 1
                )
                i += 1
        else:
            child_path = f"{current_path}\\{seg}" if current_path else seg
            _walk_reg_for_values(
                predefined_root, access_flag, segments, idx + 1, child_path, out, depth + 1
            )
    finally:
        winreg.CloseKey(key_handle)


def _collect_reg_values(key_handle, out: list[str]) -> None:
    """从当前键及其直接子键收集候选安装路径字符串值。"""
    if _read_install_values(key_handle, out):
        return
    i = 0
    while len(out) <= 200:
        try:
            child_name = winreg.EnumKey(key_handle, i)
        except OSError:
            break
        try:
            with winreg.OpenKey(key_handle, child_name) as child:
                if _read_install_values(child, out):
                    return
        except OSError:
            pass
        i += 1


def _read_install_values(key_handle, out: list[str]) -> bool:
    """读取键中常见值名,首个非空字符串值加入 out 并返回 True。"""
    for value_name in _REG_INSTALL_VALUE_NAMES:
        try:
            value, _ = winreg.QueryValueEx(key_handle, value_name)
        except (FileNotFoundError, OSError, ValueError):
            continue
        if isinstance(value, str) and value.strip():
            out.append(value)
            return True
    return False


def _exe_name_for_tool(tool: ToolDefinition) -> str:
    """从 commands[0] 推断 exe 文件名,确保带 .exe 后缀。"""
    if not tool.commands:
        return f"{tool.id}.exe"
    first = tool.commands[0].split()[0]
    return first if first.lower().endswith(".exe") else f"{first}.exe"


def _exe_from_reg_value(raw: str, exe_name: str) -> Optional[str]:
    """从注册表字符串值定位可执行文件。值可能是目录、exe 路径或带参数的命令行。"""
    s = os.path.expandvars(raw).strip().strip('"').strip()
    if not s:
        return None
    if os.path.isfile(s):
        return s
    if os.path.isdir(s):
        exe = _find_exe_near(s, exe_name)
        if exe:
            return exe
    first = s.split()[0] if s.split() else ""
    if first and os.path.isfile(first):
        return first
    if first and os.path.isdir(first):
        return _find_exe_near(first, exe_name)
    return None


def _find_exe_near(dir_path: str, exe_name: str) -> Optional[str]:
    """在目录及其 bin/Scripts/cmd 子目录中查找 exe。"""
    for sub in ("", "bin", "Scripts", "cmd"):
        candidate = os.path.join(dir_path, sub, exe_name) if sub else os.path.join(dir_path, exe_name)
        if os.path.isfile(candidate):
            return candidate
    return None


def _run_executable(exe_path: str, sample_cmd: str | None) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """对已知完整路径的可执行文件尝试执行版本命令。返回 (version, raw, error)。"""
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
            return None, None, None
        version = _parse_version(output)
        return version, output.strip()[:500], None
    except subprocess.TimeoutExpired:
        return None, None, "timeout"
    except (FileNotFoundError, OSError):
        return None, None, "os_error"


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
