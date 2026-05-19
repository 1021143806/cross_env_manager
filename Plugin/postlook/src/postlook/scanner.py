"""
postlook · 文件扫描与内容读取
"""

import fnmatch
import os
from pathlib import Path
from typing import List, Dict, Optional


def resolve_folder(folder: str, root_dirs: List[str]) -> Path:
    """
    解析 folder 参数，返回实际路径。
    安全检查：必须在 root_dirs 白名单内。
    """
    folder_path = Path(folder)

    # 如果是绝对路径
    if folder_path.is_absolute():
        resolved = folder_path.resolve()
        # 检查是否在任一白名单目录内
        for root in root_dirs:
            root_path = Path(root).resolve()
            try:
                resolved.relative_to(root_path)
                return resolved
            except ValueError:
                continue
        raise PermissionError(
            f"目录 '{folder}' 不在允许的白名单内。"
            f" 白名单: {root_dirs}"
        )

    # 相对路径：依次尝试每个 root_dir
    for root in root_dirs:
        candidate = (Path(root) / folder_path).resolve()
        root_path = Path(root).resolve()
        try:
            candidate.relative_to(root_path)
            if candidate.exists():
                return candidate
        except ValueError:
            continue

    # 如果都不存在，返回第一个 root_dir 下的路径（后续会报文件不存在）
    return (Path(root_dirs[0]) / folder_path).resolve()


def find_files(
    folder: Path,
    pattern: str = "*.log",
    recent_files: int = 10
) -> List[Path]:
    """
    在 folder 中递归查找匹配 pattern 的文件，
    按修改时间降序排列，返回最近 recent_files 个。
    """
    if not folder.exists() or not folder.is_dir():
        return []

    files = []
    for entry in folder.rglob("*"):
        if entry.is_file() and fnmatch.fnmatch(entry.name, pattern):
            # 不跟随符号链接到外部
            if entry.is_symlink():
                continue
            files.append(entry)

    # 按修改时间降序
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files[:recent_files]


def search_lines(
    file_path: Path,
    keyword: Optional[str] = None,
    max_lines: int = 100,
    tail: bool = True,
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
) -> List[Dict]:
    """
    从文件中搜索匹配行。
    - keyword: 不区分大小写搜索
    - max_lines: 最大返回行数
    - tail: 无关键字时从尾部读取
    - line_start/line_end: 指定行号范围
    """
    results = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError):
        return results

    total = len(lines)

    # 行号范围过滤
    if line_start is not None or line_end is not None:
        start = (line_start or 1) - 1  # 转为 0-based
        end = line_end if line_end else total
        start = max(0, start)
        end = min(total, end)
        lines = lines[start:end]
        line_offset = start  # 原始行号偏移
    else:
        line_offset = 0

    if keyword:
        # 关键字搜索（不区分大小写）
        kw_lower = keyword.lower()
        for i, line in enumerate(lines):
            if kw_lower in line.lower():
                results.append({
                    "file": file_path.name,
                    "line": line_offset + i + 1,
                    "content": line.rstrip("\n\r")
                })
                if len(results) >= max_lines:
                    break
    else:
        # 无关键字：tail 或 head
        if tail:
            selected = lines[-max_lines:]
            start_idx = max(0, len(lines) - max_lines)
        else:
            selected = lines[:max_lines]
            start_idx = 0

        for i, line in enumerate(selected):
            results.append({
                "file": file_path.name,
                "line": line_offset + start_idx + i + 1,
                "content": line.rstrip("\n\r")
            })

    return results


def scan_logs(
    folder: str,
    root_dirs: List[str],
    pattern: str = "*.log",
    keyword: Optional[str] = None,
    lines: int = 50,
    tail: bool = True,
    recent_files: int = 10,
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
) -> Dict:
    """
    主扫描函数，返回符合 API 规范的 JSON 结构。
    """
    max_lines = min(lines, 100)

    # 解析目录
    try:
        folder_path = resolve_folder(folder, root_dirs)
    except PermissionError as e:
        return {
            "total_lines": 0,
            "truncated": False,
            "results": [],
            "error": str(e)
        }

    # 查找文件
    files = find_files(folder_path, pattern, recent_files)
    if not files:
        return {
            "total_lines": 0,
            "truncated": False,
            "results": [],
            "error": f"在 '{folder}' 中未找到匹配 '{pattern}' 的文件"
        }

    # 搜索内容
    all_results = []
    remaining = max_lines

    for file_path in files:
        if remaining <= 0:
            break
        file_results = search_lines(
            file_path,
            keyword=keyword,
            max_lines=remaining,
            tail=tail,
            line_start=line_start,
            line_end=line_end,
        )
        all_results.extend(file_results)
        remaining = max_lines - len(all_results)

    truncated = len(all_results) >= max_lines
    all_results = all_results[:max_lines]

    return {
        "total_lines": len(all_results),
        "truncated": truncated,
        "results": all_results,
        "keyword": keyword,
    }
