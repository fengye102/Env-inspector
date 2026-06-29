"""
core/conflict.py — 多版本扫描 + 冲突检测

主扫描完成后异步调用，不阻塞首屏。
单工具总超时 10 秒，glob 展开上限 20 个路径。
"""

from __future__ import annotations

import glob
import os
import subprocess

from core.detector import _parse_version, infer_install_dir
from core.registry import ScanResult, ToolDefinition, VersionEntry

_CONFLICT_CMD_TIMEOUT = 3   # 单个版本命令超时（秒）
_MAX_GLOB_RESULTS = 20      # glob 展开结果上限


# ── 公开接口 ──────────────────────────────────────────────────

def detect_all_versions(tool_def: ToolDefinition) -> list[VersionEntry]:
    """
    收集该工具所有候选可执行文件路径，逐一执行版本命令，
    返回去重、排序后的 VersionEntry 列表。

    来源优先级：
      a. PATH 中 where 找到的路径（可能多行）
      b. glob 展开 multi_version_paths 的每个目录，在其中查找 exe
      c. fallback_paths 中实际存在的文件
    """
    exe_name = _get_exe_name(tool_def)
    version_args = _get_version_args(tool_def)

    # ── a. where 命令（PATH）──
    where_paths = _run_where(exe_name)
    active_path: str | None = where_paths[0] if where_paths else None

    candidates: list[str] = list(where_paths)

    # ── b. glob 展开 multi_version_paths ──
    for pattern in tool_def.multi_version_paths:
        expanded_pattern = os.path.expandvars(pattern)
        try:
            matches = glob.glob(expanded_pattern)
        except Exception:
            matches = []
        if len(matches) > _MAX_GLOB_RESULTS:
            matches = matches[:_MAX_GLOB_RESULTS]
        for match_dir in matches:
            if os.path.isdir(match_dir):
                exe = _find_exe_in_dir(match_dir, exe_name)
                if exe:
                    candidates.append(exe)

    # ── c. fallback_paths ──
    for fb_path in tool_def.fallback_paths:
        expanded = os.path.expandvars(fb_path)
        if os.path.isfile(expanded):
            candidates.append(expanded)

    # ── 去重（大小写不敏感，规范化路径）──
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        key = os.path.normcase(os.path.normpath(c))
        if key not in seen:
            seen.add(key)
            unique.append(c)

    # ── 逐一执行版本命令，构建 VersionEntry ──
    entries: list[VersionEntry] = []
    for exe_path in unique:
        version = _run_version_cmd(exe_path, version_args)
        if version is None:
            continue
        is_active = (
            active_path is not None
            and os.path.normcase(os.path.normpath(exe_path))
            == os.path.normcase(os.path.normpath(active_path))
        )
        entries.append(
            VersionEntry(
                version=version,
                executable_path=exe_path,
                install_dir=infer_install_dir(exe_path),
                is_active=is_active,
            )
        )

    # 按版本号字符串升序排序
    entries.sort(key=lambda e: e.version)
    return entries


def update_result_with_versions(
    result: ScanResult, tool_def: ToolDefinition
) -> ScanResult:
    """
    对已扫描到（installed=True）的工具执行多版本检测，
    原地更新 all_versions 和 has_conflict 字段并返回。
    """
    all_versions = detect_all_versions(tool_def)
    result.all_versions = all_versions
    result.has_conflict = len(all_versions) > 1
    return result


# ── 内部辅助 ──────────────────────────────────────────────────

def _get_exe_name(tool_def: ToolDefinition) -> str:
    """从 commands[0] 的首个单词推断 exe 名称，确保有 .exe 后缀。"""
    if not tool_def.commands:
        return f"{tool_def.id}.exe"
    first_word = tool_def.commands[0].split()[0]
    if not first_word.lower().endswith(".exe"):
        return f"{first_word}.exe"
    return first_word


def _get_version_args(tool_def: ToolDefinition) -> list[str]:
    """返回版本命令中 exe 之后的参数列表。"""
    if not tool_def.commands:
        return ["--version"]
    parts = tool_def.commands[0].split()
    return parts[1:] if len(parts) > 1 else ["--version"]


def _run_where(exe_name: str) -> list[str]:
    """
    用 where 命令在 PATH 中查找所有匹配路径。
    返回实际存在的文件路径列表（保持顺序）。
    """
    try:
        proc = subprocess.run(
            ["where", exe_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            lines = [line.strip() for line in proc.stdout.strip().splitlines()]
            return [ln for ln in lines if ln and os.path.isfile(ln)]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return []


def _find_exe_in_dir(dir_path: str, exe_name: str) -> str | None:
    """
    在目录中查找 exe：先查根目录，再查 bin/、Scripts/ 子目录。
    返回首个找到的完整路径，未找到返回 None。
    """
    for subdir in ("", "bin", "Scripts", "cmd"):
        candidate = os.path.join(dir_path, subdir, exe_name) if subdir else os.path.join(dir_path, exe_name)
        if os.path.isfile(candidate):
            return candidate
    return None


def _run_version_cmd(exe_path: str, args: list[str]) -> str | None:
    """
    对指定 exe 执行版本命令（3 秒超时），
    返回解析后的版本号字符串；失败返回 None。
    """
    try:
        proc = subprocess.run(
            [exe_path] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_CONFLICT_CMD_TIMEOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = proc.stdout or proc.stderr
        if not output:
            return None
        return _parse_version(output)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
