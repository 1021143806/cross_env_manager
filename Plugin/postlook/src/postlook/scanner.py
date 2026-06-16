"""
postlook · 文件扫描与内容读取
"""

import fnmatch
import os
import re
from pathlib import Path
from typing import List, Dict, Optional

# ---- 下载安全管控 ----

# 允许下载的日志类文件扩展名白名单
ALLOWED_DOWNLOAD_EXTENSIONS = frozenset({
    '.log', '.out', '.txt', '.dat',
    '.gz', '.bz2', '.zip', '.tar', '.xz', '.zst',
    '.0', '.1', '.2', '.3', '.4', '.5', '.6', '.7', '.8', '.9',
    '.current',
    # 调试/诊断文件
    '.hprof',      # Java Heap Dump
    '.core',       # Core Dump (Linux)
    '.dmp',        # Crash Dump / Minidump
    '.jar',        # Java 可执行包（仅后台允许下载，前端不显示）
})


def is_allowed_download(file_path: Path) -> bool:
    """
    检查文件是否允许被下载。
    白名单制：仅允许日志类扩展名或无扩展名的文件（messages/secure 等）。
    禁止下载脚本、配置、证书、可执行文件等非日志文件。
    """
    if file_path.is_symlink():
        return False

    name = file_path.name

    # 无扩展名的文件允许（系统日志如 messages, secure, wtmp, sa08）
    if '.' not in name:
        return True

    name_lower = name.lower()

    # 匹配扩展名白名单（含 .tar.gz 等复合扩展名）
    for ext in ALLOWED_DOWNLOAD_EXTENSIONS:
        if name_lower.endswith(ext):
            return True

    # 特殊模式：core.PID 格式的 Core Dump（core.12345）
    if name_lower.startswith('core.') and name_lower.count('.') == 1:
        suffix = name_lower.split('.')[-1]
        if suffix.isdigit():
            return True

    return False


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


def expand_keyword_with_rules(keyword: str) -> str:
    """
    规则感知关键字扩展。
    如果 keyword 匹配任意规则的 name 或 annotation，
    自动将该规则的 match 模式追加为 OR 条件。
    
    例: "开门" → "开门|AB66000003030110E903|AB66000003040110E803"
         "电梯" → 匹配所有电梯相关规则的 hex 模式
    
    仅扩展第一个关键字段（管道前），保留用户指定的 grep 管道。
    """
    if not keyword:
        return keyword

    # 只扩展第一个关键字段，保留管道语法
    parts = keyword.split("|", 1)
    first = parts[0].strip()

    # 第一段已含 OR (|) → 用户明确指定，不扩展
    if "|" in first:
        return keyword

    try:
        from .config import get_rules
        rules = get_rules()
    except Exception:
        return keyword

    kw_lower = first.lower()
    expanded = [first]

    for rule in rules:
        name = (rule.get("name") or "").lower()
        annotation = (rule.get("annotation") or "").lower()
        rtype = rule.get("type", "")

        # 匹配规则名称或注解（子串匹配）
        if kw_lower not in name and kw_lower not in annotation:
            continue

        match = (rule.get("match") or "").strip()
        if not match:
            continue

        # 仅扩展 hex 和 keyword 类型规则（regex 的占位符不适合直接搜索）
        if rtype not in ("hex", "keyword"):
            continue

        # hex 类型：去掉空格便于搜索
        if rtype == "hex":
            match = match.replace(" ", "")

        if match.lower() in (e.lower() for e in expanded):
            continue  # 去重

        expanded.append(match)

    if len(expanded) == 1:
        return keyword  # 无匹配规则，原样返回

    # 重建：扩展后的第一段 + 剩余管道
    expanded_first = "|".join(expanded)
    if len(parts) > 1:
        return expanded_first + " | " + parts[1]
    return expanded_first


def parse_grep_pipeline(keyword: Optional[str]) -> tuple:
    """
    解析 grep 管道语法，返回 (filters, shell_cmd)
    filters: [(pattern, invert, case_insensitive), ...]
    示例:
      "ERROR" → ([("ERROR", False, True)], "grep -i 'ERROR'")
      "ERROR|Exception" → ([("ERROR|Exception", False, True)], "grep -iE '(ERROR|Exception)'")
      "ERROR | grep timeout" → ([("ERROR", False, True), ("timeout", False, True)], "grep -i 'ERROR' | grep -i 'timeout'")
      "ERROR | grep -v debug" → ([("ERROR", False, True), ("debug", True, True)], "grep -i 'ERROR' | grep -iv 'debug'")
    """
    if not keyword:
        return [], ""
    
    keyword = keyword.strip()
    
    # 检测是否含 grep 管道语法（非普通 OR）
    has_grep = bool(re.search(r'\|\s*grep\b', keyword, re.IGNORECASE))
    
    if has_grep:
        # 管道模式：按 grep 边界拆分
        parts = re.split(r'\|\s*(?=grep\b)', keyword, flags=re.IGNORECASE)
        parts = [p.strip() for p in parts]
    else:
        # 普通模式：整体作为一个 pattern（支持内部 | 作为 OR）
        parts = [keyword]
    
    filters = []
    cmd_parts = []
    
    for p in parts:
        invert = False
        case_insensitive = True
        pattern = p
        
        # 检查是否是 grep 命令段
        grep_match = re.match(r'^grep\s+(-[a-z]*)?\s*(.+)$', p, re.IGNORECASE)
        if grep_match:
            flags = grep_match.group(1) or ""
            pattern = grep_match.group(2).strip()
            if 'v' in flags.lower():
                invert = True
            if 'i' in flags.lower():
                case_insensitive = True
            # build cmd
            cmd_flags = "-i" if case_insensitive else ""
            if invert:
                cmd_flags += "v" if cmd_flags else "-v"
            cmd_parts.append(f"grep {cmd_flags} '{pattern}'" if cmd_flags else f"grep '{pattern}'")
        else:
            # 普通关键字，支持内部 | 作为 OR
            cmd_flags = "-iE" if "|" in pattern else "-i"
            quoted = f"'{pattern}'"
            cmd_parts.append(f"grep {cmd_flags} {quoted}")
        
        filters.append((pattern, invert, case_insensitive))
    
    shell_cmd = " | ".join(cmd_parts) if cmd_parts else ""
    return filters, shell_cmd


def _line_matches_pipeline(line: str, filters: list) -> bool:
    """检查一行是否通过所有过滤器。同时支持空格敏感和忽略空格的匹配。"""
    for pattern, invert, ci in filters:
        test_line = line.lower() if ci else line
        test_pat = pattern.lower() if ci else pattern
        
        # 也准备忽略空格的版本（用于 hex 模式匹配）
        test_line_nosp = test_line.replace(" ", "")
        
        # 支持 | (OR) 在单个 pattern 中
        if "|" in pattern:
            or_patterns = [p.strip() for p in pattern.split("|")]
            matched = any(
                (p.lower() if ci else p) in test_line
                or (p.lower() if ci else p) in test_line_nosp
                for p in or_patterns
            )
        else:
            matched = test_pat in test_line or test_pat in test_line_nosp
        
        if invert:
            if matched:
                return False
        else:
            if not matched:
                return False
    return True


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
    - keyword: 不区分大小写搜索（先 grep 全文件，再按行号范围截取）
    - max_lines: 最大返回行数
    - tail: 无关键字时从尾部读取
    - line_start/line_end: 无关键字时指定行号范围；有关键字时作为结果索引范围
    """
    results = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError):
        return results

    total = len(lines)

    if keyword:
        # 管道解析
        filters, _ = parse_grep_pipeline(keyword)
        all_matches = []
        for i, line in enumerate(lines):
            if _line_matches_pipeline(line, filters):
                all_matches.append({
                    "file": file_path.name,
                    "line": i + 1,  # 原始行号
                    "content": line.rstrip("\n\r")
                })

        # line_start/line_end 作为匹配结果的索引范围（1-based）
        if tail and not line_start:
            # tail 模式：取最后 line_end 条
            start_idx = max(0, len(all_matches) - (line_end or max_lines))
            end_idx = len(all_matches)
        else:
            start_idx = (line_start or 1) - 1
            end_idx = line_end if line_end else len(all_matches)
        start_idx = max(0, start_idx)
        end_idx = min(len(all_matches), end_idx)

        results = all_matches[start_idx:end_idx]
        # 限制最大返回数
        if len(results) > max_lines:
            results = results[:max_lines]
    else:
        # 无关键字
        if tail:
            # tail 模式：直接从全文尾部取，忽略 line_start
            end = line_end if line_end else total
            selected = lines[-min(end, len(lines)):]
            line_offset = max(0, len(lines) - len(selected))
            if len(selected) > max_lines:
                selected = selected[-max_lines:]
        elif line_start is not None or line_end is not None:
            # head / 指定范围
            start = (line_start or 1) - 1
            end = line_end if line_end else total
            start = max(0, start)
            end = min(total, end)
            selected = lines[start:end]
            line_offset = start
            if tail:
                selected = selected[-max_lines:]
        else:
            line_offset = 0
            if tail:
                selected = lines[-max_lines:]
                line_offset = max(0, len(lines) - len(selected))

        for i, line in enumerate(selected):
            results.append({
                "file": file_path.name,
                "line": line_offset + i + 1,
                "content": line.rstrip("\n\r")
            })

    return results


def _build_shell_cmd(keyword: Optional[str], folder_path: Path, pattern: str, line_end: int, tail: bool, files: list) -> str:
    """生成等效的 shell 命令字符串"""
    _, grep_part = parse_grep_pipeline(keyword)
    # 构建 find 部分
    file_list_cmd = f"find {folder_path} -name '{pattern}' | sort | tail -10"
    if len(files) == 1:
        file_list_cmd = str(files[0])
    
    parts = []
    if grep_part:
        parts.append(grep_part)
    
    # tail/head
    tail_flag = "-n " + str(line_end)
    if tail:
        parts.append(f"tail {tail_flag}")
    else:
        parts.append(f"head {tail_flag}")
    
    if parts:
        return file_list_cmd + " | " + " | ".join(parts)
    elif tail:
        return f"tail -n {line_end} {file_list_cmd}"
    else:
        return f"head -n {line_end} {file_list_cmd}"


def scan_logs(
    folder: str,
    root_dirs: List[str],
    pattern: str = "*.log",
    keyword: Optional[str] = None,
    tail: bool = True,
    recent_files: int = 10,
    line_start: int = 1,
    line_end: int = 100,
) -> Dict:
    """
    主扫描函数，返回符合 API 规范的 JSON 结构。
    - 有关键字时：在行号范围内搜索所有匹配行（上限500行）
    - 无关键字时：返回行号范围内的内容
    """
    # 关键字搜索上限
    MAX_KEYWORD_RESULTS = 500

    # 规则感知关键字扩展（将 "开门" 自动展开为 "开门|AB6600...|AB6600..."）
    expanded_keyword = expand_keyword_with_rules(keyword) if keyword else None

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

    # 如果 folder 直接指向一个文件，直接读取该文件
    if folder_path.is_file():
        files = [folder_path]
    elif not folder_path.exists():
        return {
            "total_lines": 0,
            "truncated": False,
            "results": [],
            "error": f"路径不存在: '{folder}'"
        }
    elif not folder_path.is_dir():
        return {
            "total_lines": 0,
            "truncated": False,
            "results": [],
            "error": f"路径不是目录也不是文件: '{folder}'"
        }
    else:
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
    limit = MAX_KEYWORD_RESULTS if expanded_keyword else None

    for file_path in files:
        if limit and len(all_results) >= limit:
            break
        remaining = (limit - len(all_results)) if limit else None
        file_results = search_lines(
            file_path,
            keyword=expanded_keyword,
            max_lines=remaining if remaining else (line_end - line_start + 1),
            tail=tail,
            line_start=line_start,
            line_end=line_end,
        )
        all_results.extend(file_results)

    truncated = bool(expanded_keyword and len(all_results) >= MAX_KEYWORD_RESULTS)
    if truncated:
        all_results = all_results[:MAX_KEYWORD_RESULTS]

    return {
        "total_lines": len(all_results),
        "truncated": truncated,
        "results": all_results,
        "shell_cmd": _build_shell_cmd(expanded_keyword, folder_path, pattern, line_end, tail, files),
    }
