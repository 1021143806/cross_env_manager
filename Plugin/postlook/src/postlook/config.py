"""
postlook · 配置模块
从 config/app.toml（或 env.toml）+ config/rules.toml 加载配置，支持热更新
"""

import os
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH_APP = PROJECT_ROOT / "config" / "app.toml"
CONFIG_PATH_ENV = PROJECT_ROOT / "config" / "env.toml"
RULES_PATH = PROJECT_ROOT / "config" / "rules.toml"
RULES_TEMPLATE_PATH = PROJECT_ROOT / "config" / "template" / "rules.toml"
DEBUG_CONFIG_PATH = PROJECT_ROOT / "config" / "debug.toml"
DEBUG_CONFIG_TEMPLATE_PATH = PROJECT_ROOT / "config" / "template" / "debug.toml"
CONFIG_TEMPLATE_PATH = PROJECT_ROOT / "config" / "template" / "app.toml"
DATE_DIR = PROJECT_ROOT / "config" / "date"

# 线程锁
_lock = threading.Lock()

# ---- 可热更新的配置变量 ----
SERVER_HOST: str = "0.0.0.0"
SERVER_PORT: int = 5011
ROOT_DIRS: List[str] = ["/var/log"]
MAX_LINES: int = 100
DEFAULT_LINES: int = 50
DEFAULT_RECENT_FILES: int = 10
MAX_RECENT_FILES: int = 50
MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB，超过此大小的文件将拒绝全文读取
DEFAULT_THEME: str = "dark"
MAX_DOWNLOAD_SIZE: int = 200 * 1024 * 1024
DEFAULT_DOWNLOAD_SIZE: int = 200

# ---- 扩展配置缓存 ----
_cached_rules: List[Dict[str, Any]] = []
_cached_topo_categories: List[Dict[str, Any]] = []
_cached_topo_services: List[Dict[str, Any]] = []
_cached_dirs_meta: List[Dict[str, Any]] = []
_cached_date_queries: List[Dict[str, Any]] = []

# ---- 调试配置缓存 (v0.4.0) ----
_cached_debug_config: Dict[str, Any] = {
    "connection": {
        "host": "10.68.2.40",
        "port": 8899,
        "timeout": 3.0,
        "recv_timeout": 1.0,
        "recv_buffer": 4096,
    },
    "send": {
        "auto_lowercase": True,
        "auto_uppercase": False,
        "add_crlf_ascii": True,
    },
    "display": {
        "show_hex": True,
        "show_timestamp": True,
    },
}

# ── 内置规则（随代码发布，始终可用）──
# rules.toml 中同名规则可覆盖内置规则
_BUILTIN_RULES: List[Dict[str, Any]] = [
    # ── 十六进制报文着色 + 注解 ──
    # 富阳梯博士电梯协议 — 召梯指令
    {"name":"电梯召梯到1楼","type":"hex","match":"AB 66 00 00 04 02 01 00 01 F8 03","file":"WDCS*.log","color":"#34d399","annotation":"【召梯到1楼】"},
    {"name":"电梯召梯到2楼","type":"hex","match":"AB 66 00 00 04 02 01 00 02 F7 03","file":"WDCS*.log","color":"#34d399","annotation":"【召梯到2楼】"},
    {"name":"电梯召梯到3楼","type":"hex","match":"AB 66 00 00 04 02 01 00 03 F6 03","file":"WDCS*.log","color":"#34d399","annotation":"【召梯到3楼】"},
    {"name":"电梯召梯到4楼","type":"hex","match":"AB 66 00 00 04 02 01 00 04 F5 03","file":"WDCS*.log","color":"#34d399","annotation":"【召梯到4楼】"},
    {"name":"电梯召梯到5楼","type":"hex","match":"AB 66 00 00 04 02 01 00 05 F4 03","file":"WDCS*.log","color":"#34d399","annotation":"【召梯到5楼】"},
    {"name":"电梯召梯到6楼","type":"hex","match":"AB 66 00 00 04 02 01 00 06 F3 03","file":"WDCS*.log","color":"#34d399","annotation":"【召梯到6楼】"},
    {"name":"电梯召梯到7楼","type":"hex","match":"AB 66 00 00 04 02 01 00 07 F2 03","file":"WDCS*.log","color":"#34d399","annotation":"【召梯到7楼】"},
    {"name":"电梯召梯到8楼","type":"hex","match":"AB 66 00 00 04 02 01 00 08 F1 03","file":"WDCS*.log","color":"#34d399","annotation":"【召梯到8楼】"},
    # 电梯 — 状态查询
    {"name":"获取电梯状态","type":"hex","match":"AB 66 00 00 03 01 00 FF FD 03","file":"WDCS*.log","color":"#818cf8","annotation":"【获取电梯状态】"},
    # 电梯 — 具体状态返回
    {"name":"电梯在1楼","type":"hex","match":"AB 66 00 00 05 81 00 00 01 68 11 03","file":"WDCS*.log","color":"#fbbf24","annotation":"【1楼 · 开门到位】"},
    {"name":"电梯在2楼","type":"hex","match":"AB 66 00 00 05 81 00 00 02 01 77 03","file":"WDCS*.log","color":"#fbbf24","annotation":"【2楼 · 上行】"},
    {"name":"电梯在3楼","type":"hex","match":"AB 66 00 00 05 81 00 00 03 6C 0B 03","file":"WDCS*.log","color":"#fbbf24","annotation":"【3楼 · 到达+开门】"},
    {"name":"电梯状态返回","type":"regex","match":"ab 66 00 00 05 81 00 00 [0-9a-f]{2} [0-9a-f]{2} [0-9a-f]{2} 03","file":"WDCS*.log","color":"#fbbf24","annotation":"【电梯状态返回】"},
    {"name":"电梯状态返回(1楼校准)","type":"hex","match":"AB 66 00 00 05 81 00 00 01 70 09 03","file":"WDCS*.log","color":"#fbbf24","annotation":"【1楼 · 校准状态】"},
    {"name":"电梯状态返回(2楼楼层检测)","type":"hex","match":"AB 66 00 00 05 81 00 00 02 60 18 03","file":"WDCS*.log","color":"#fbbf24","annotation":"【2楼 · 楼层检测】"},
    {"name":"电梯状态返回(3楼开门到位)","type":"hex","match":"AB 66 00 00 05 81 00 00 03 68 0f 03","file":"WDCS*.log","color":"#fbbf24","annotation":"【3楼 · 开门到位】"},
    # 电梯 — 开门/关门
    {"name":"开门报文","type":"hex","match":"AB 66 00 00 03 03 01 10 E9 03","file":"WDCS*.log","color":"#f472b6","annotation":"【开门】"},
    {"name":"关门报文","type":"hex","match":"AB 66 00 00 03 04 01 10 E8 03","file":"WDCS*.log","color":"#f472b6","annotation":"【关门】"},
    # ── 日志级别着色（全局）──
    {"name":"错误/严重","type":"keyword","match":"ERROR|FATAL","color":"#ef4444","background":"rgba(239,68,68,0.10)","bold":True},
    {"name":"警告","type":"keyword","match":"WARN","color":"#f59e0b","background":"rgba(245,158,11,0.08)"},
    {"name":"异常","type":"keyword","match":"Exception","color":"#ef4444","background":"rgba(239,68,68,0.06)"},
    # ── RTPS/ICS 算法层核心着色（全局）──
    {"name":"RTPS-路径黑障(robotBlackout)","type":"keyword","match":"robotBlackout","color":"#ef4444","background":"rgba(239,68,68,0.12)","bold":True,"annotation":"⚡ Blackout"},
    {"name":"RTPS-规划错误(algo plan error)","type":"keyword","match":"algo plan error","color":"#ef4444","background":"rgba(239,68,68,0.10)","bold":True,"annotation":"🚫 规划错误"},
    {"name":"RTPS-障碍物(Robot Obstacled)","type":"keyword","match":"Robot Obstacled","color":"#f59e0b","annotation":"🚧 障碍"},
    {"name":"RTPS-设备离线上线","type":"keyword","match":"online after offline","color":"#f59e0b","annotation":"🔌 恢复连线"},
    {"name":"ICS-未定义异常(robotBlackout_Unknown)","type":"keyword","match":"robotBlackout_Unknown","color":"#ef4444","background":"rgba(239,68,68,0.10)","bold":True,"annotation":"⚡ 未定义异常(8504)"},
    # ── 内置快捷查询（侧栏按钮）──
    {"name":"Gateway 错误","type":"keyword","match":"ERROR|Exception","folder":"/main/app/gateway/logs","pattern":"GATEWAY.log","color":"#ef4444","desc":"网关所有异常日志"},
    {"name":"系统 OOM","type":"keyword","match":"oom_kill|Out of memory|Killed process","folder":"/var/log","pattern":"messages*","color":"#dc2626","bold":True,"desc":"查找 OOM Killer 记录"},
    {"name":"MariaDB 慢查询","type":"regex","match":"Query_time: \\d+\\.\\d+","folder":"/main/server/mysql","pattern":"slow-sql","desc":"慢查询日志，定位锁等待/全表扫描"},
    {"name":"Nacos 错误","type":"keyword","match":"ERROR|Exception","folder":"/main/server/nacos/logs","pattern":"nacos.log","color":"#ef4444","desc":"Nacos 服务注册/配置异常"},
    {"name":"SSH 登录记录","type":"keyword","match":"Accepted|Failed","folder":"/var/log","pattern":"secure*","desc":"SSH 登录成功/失败"},
    {"name":"定时任务","type":"keyword","match":"CMD","folder":"/var/log","pattern":"cron*","desc":"cron 定时任务执行记录"},
    {"name":"WDCS 报文","type":"hex","match":"AB 66","color":"#06b6d4","desc":"WDCS 电梯 485 报文（通用色）"},
    {"name":"WDCS 错误","type":"keyword","match":"ERROR|Exception","folder":"/main/app/wdcs/logs","pattern":"WDCS*.log","color":"#ef4444","desc":"WDCS 异常日志"},
]


def _get_config_path() -> Path:
    """优先使用 app.toml，不存在时回退到 env.toml"""
    if CONFIG_PATH_APP.exists():
        return CONFIG_PATH_APP
    return CONFIG_PATH_ENV


def _load_toml_file(path: Path) -> dict:
    """加载指定 TOML 文件"""
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return {}

    if path.exists():
        with open(path, "rb") as f:
            return tomllib.load(f)
    return {}


def reload_rules():
    """重新加载 rules.toml，与内置规则合并 → 更新 _cached_rules
    规则合并策略：
      - 内置规则始终存在
      - rules.toml 中同名（name）规则覆盖内置规则
      - rules.toml 中新增规则追加到末尾
    """
    global _cached_rules
    with _lock:
        # 从内置规则副本开始
        merged = list(_BUILTIN_RULES)

        # 加载 rules.toml 自定义规则
        cfg = _load_toml_file(RULES_PATH)
        custom_rules = cfg.get("rule", [])

        # 按 name 建立内置规则索引（只记录位置，不复制）
        builtin_names = {}
        for i, r in enumerate(merged):
            if r.get("name"):
                builtin_names[r["name"]] = i

        for cr in custom_rules:
            name = cr.get("name")
            if name and name in builtin_names:
                # 同名覆盖：替换内置规则
                merged[builtin_names[name]] = cr
            else:
                # 新增规则：追加到末尾
                merged.append(cr)

        _cached_rules.clear()
        _cached_rules.extend(merged)


def reload_config():
    """热更新：重新加载主配置并更新全局变量"""
    global SERVER_HOST, SERVER_PORT, ROOT_DIRS
    global MAX_LINES, DEFAULT_LINES, DEFAULT_RECENT_FILES, DEFAULT_THEME
    global MAX_DOWNLOAD_SIZE, DEFAULT_DOWNLOAD_SIZE, MAX_FILE_SIZE

    with _lock:
        cfg = _load_toml_file(_get_config_path())

        # server
        server = cfg.get("server", {})
        SERVER_HOST = server.get("host", "0.0.0.0")
        SERVER_PORT = int(server.get("port", 5011))

        # logs
        logs = cfg.get("logs", {})
        _root_dirs = logs.get("root_dirs", ["/var/log"])
        if isinstance(_root_dirs, str):
            ROOT_DIRS = [d.strip() for d in _root_dirs.split(",") if d.strip()]
        else:
            ROOT_DIRS = list(_root_dirs) if _root_dirs else ["/var/log"]

        # 环境变量覆盖
        env_root = os.environ.get("POSTLOOK_ROOT")
        if env_root:
            ROOT_DIRS = [d.strip() for d in env_root.split(",") if d.strip()]

        MAX_LINES = int(logs.get("max_lines", 100))
        DEFAULT_LINES = int(logs.get("default_lines", 50))
        DEFAULT_RECENT_FILES = int(logs.get("default_recent_files", 10))

        # 下载大小限制（单位 MB）
        download_size = int(logs.get("max_download_size", 200))
        MAX_DOWNLOAD_SIZE = min(download_size, 1024) * 1024 * 1024  # 上限 1GB
        DEFAULT_DOWNLOAD_SIZE = download_size
        
        # 文件读取大小限制（单位 MB）
        file_size_mb = int(logs.get("max_file_size", 100))
        MAX_FILE_SIZE = min(file_size_mb, 1024) * 1024 * 1024  # 上限 1GB

        # ui
        ui = cfg.get("ui", {})
        DEFAULT_THEME = ui.get("theme", "dark")

        # ---- 拓扑 & 目录元数据（主配置）----
        topo = cfg.get("topology", {})
        _cached_topo_categories.clear()
        _cached_topo_categories.extend(topo.get("category", []))
        _cached_topo_services.clear()
        _cached_topo_services.extend(topo.get("service", []))

        _cached_dirs_meta.clear()
        _cached_dirs_meta.extend(cfg.get("dir", []))

    # 单独加载规则文件
    reload_rules()
    # 重扫日期查询配置
    reload_date_queries()

    # 保护机制：检测拓扑是否意外丢失
    _check_topology_health()


# ---- 调试配置（v0.4.0）----

def reload_debug_config():
    """热更新：重新加载 debug.toml 并更新调试配置缓存"""
    global _cached_debug_config
    with _lock:
        cfg = _load_toml_file(DEBUG_CONFIG_PATH)

        conn = cfg.get("connection", {})
        send_cfg = cfg.get("send", {})
        display_cfg = cfg.get("display", {})

        _cached_debug_config = {
            "connection": {
                "host": conn.get("host", "10.68.2.40"),
                "port": int(conn.get("port", 8899)),
                "timeout": float(conn.get("timeout", 3.0)),
                "recv_timeout": float(conn.get("recv_timeout", 1.0)),
                "recv_buffer": int(conn.get("recv_buffer", 4096)),
            },
            "send": {
                "auto_lowercase": bool(send_cfg.get("auto_lowercase", True)),
                "auto_uppercase": bool(send_cfg.get("auto_uppercase", False)),
                "add_crlf_ascii": bool(send_cfg.get("add_crlf_ascii", True)),
            },
            "display": {
                "show_hex": bool(display_cfg.get("show_hex", True)),
                "show_timestamp": bool(display_cfg.get("show_timestamp", True)),
            },
        }


def get_debug_config() -> Dict[str, Any]:
    """获取调试连接配置"""
    return _cached_debug_config


def get_debug_config_toml() -> str:
    """读取 debug.toml 原文，不存在时返回模板"""
    if DEBUG_CONFIG_PATH.exists():
        with open(DEBUG_CONFIG_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        if content.strip():
            return content

    if DEBUG_CONFIG_TEMPLATE_PATH.exists():
        with open(DEBUG_CONFIG_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()

    return "# debug.toml\n"


def save_debug_config_toml(content: str):
    """保存 debug.toml 并热更新"""
    DEBUG_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DEBUG_CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    reload_debug_config()


# ---- 公开获取器 ----

def get_rules() -> List[Dict[str, Any]]:
    """获取所有规则（含着色/注解/快捷查询）"""
    return list(_cached_rules)


def get_topology_config() -> Dict[str, Any]:
    """获取拓扑图配置"""
    return {
        "categories": list(_cached_topo_categories),
        "services": list(_cached_topo_services),
    }


def get_dirs_meta() -> List[Dict[str, Any]]:
    """获取日志目录元数据列表"""
    return list(_cached_dirs_meta)


def get_config_toml() -> str:
    """读取主配置 TOML 原文，不存在时返回模板"""
    config_path = _get_config_path()
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
        if content.strip():
            return content

    # 回退到模板
    template_path = PROJECT_ROOT / "config" / "template" / "app.toml"
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()

    # 硬编码默认配置
    return """[server]
host = "0.0.0.0"
port = 5011

[logs]
root_dirs = ["/var/log"]
max_lines = 100
default_lines = 50
default_recent_files = 10

[ui]
theme = "dark"
"""


def get_rules_toml() -> str:
    """读取 rules.toml 原文，不存在时返回模板"""
    if RULES_PATH.exists():
        with open(RULES_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        if content.strip():
            return content

    # 回退到模板
    if RULES_TEMPLATE_PATH.exists():
        with open(RULES_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()

    return "# rules.toml\n"


def _write_op_log(action: str, detail: str = ""):
    """写入操作日志到 Postlook 自身日志文件"""
    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [OpLog] {action}"
    if detail:
        line += f" | {detail}"
    line += "\n"
    # 写入 POSTLOOK_SELF_LOG 指向的日志文件
    log_path = os.environ.get("POSTLOOK_SELF_LOG", "")
    if log_path:
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass
    # 同时输出到 stdout（supervisor 日志也会捕获）
    print(line.rstrip())


def save_config_toml(content: str):
    """保存主配置并热更新（原子写入 + 备份保护）"""
    config_path = _get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # 记录操作日志
    lines_count = content.count('\n') + 1
    _write_op_log("保存配置", f"路径={config_path.name}, 大小={len(content)}字节, {lines_count}行")

    # 1. 备份旧文件（如果存在且非空）
    bak_path = config_path.with_suffix('.toml.bak')
    if config_path.exists() and config_path.stat().st_size > 0:
        try:
            import shutil
            shutil.copy2(config_path, bak_path)
        except Exception as e:
            print(f"[Config] 备份失败: {e}")

    # 2. 原子写入：先写临时文件，再 rename
    import tempfile
    tmp_fd, tmp_path = tempfile.mkstemp(
        suffix='.toml', prefix='postlook_', dir=str(config_path.parent)
    )
    try:
        with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
            f.write(content)
        os.replace(tmp_path, config_path)  # 原子替换（Linux 保证不丢数据）
    except Exception:
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise

    # 3. 热更新
    reload_config()


def save_rules_toml(content: str):
    """保存 rules.toml 并热更新（原子写入 + 操作日志）"""
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)

    lines_count = content.count('\n') + 1
    _write_op_log("保存规则", f"路径={RULES_PATH.name}, 大小={len(content)}字节, {lines_count}行")

    # 原子写入
    import tempfile
    tmp_fd, tmp_path = tempfile.mkstemp(
        suffix='.toml', prefix='rules_', dir=str(RULES_PATH.parent)
    )
    try:
        with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
            f.write(content)
        os.replace(tmp_path, RULES_PATH)
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise

    reload_rules()


# ---- 快捷查询配置 (date/) ----


def _sanitize_filename(name: str) -> str:
    """将名称转为安全文件名（仅保留中文/字母/数字/下划线/连字符）"""
    import re
    safe = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', name).strip('_')
    return safe if safe else 'unnamed'


def _seed_date_queries():
    """从内置规则中提取含 folder 的条目，写入 date/ 目录作为初始种子"""
    DATE_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    for rule in _BUILTIN_RULES:
        if not rule.get("folder"):
            continue
        name = rule.get("name", "未命名")
        filename = _sanitize_filename(name) + ".toml"
        filepath = DATE_DIR / filename
        if filepath.exists():
            continue  # 同名文件已存在，跳过
        query = {
            "name": name,
            "folder": rule.get("folder", ""),
            "pattern": rule.get("pattern", "*.log"),
            "keyword": rule.get("match", ""),
            "line_count": DEFAULT_LINES,
            "tail": True,
            "recent_files": DEFAULT_RECENT_FILES,
            "desc": rule.get("desc", ""),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        _write_date_file(filepath, query)


def _write_date_file(filepath: Path, query: dict):
    """写入单个 date/{name}.toml 文件"""
    lines = ["[query]"]
    # 保证顺序
    keys = ["name", "folder", "pattern", "keyword", "line_count", "tail", "recent_files", "desc", "created_at"]
    for k in keys:
        v = query.get(k)
        if v is None:
            continue
        if isinstance(v, str):
            # TOML 转义：\ → \\ 和 " → \"
            escaped = v.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{k} = "{escaped}"')
        elif isinstance(v, bool):
            lines.append(f"{k} = {'true' if v else 'false'}")
        else:
            lines.append(f"{k} = {v}")
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def reload_date_queries():
    """重新扫描 date/ 目录，若为空则种子化，更新 _cached_date_queries"""
    global _cached_date_queries
    DATE_DIR.mkdir(parents=True, exist_ok=True)

    # 检查是否有文件，没有则种子化
    existing = list(DATE_DIR.glob("*.toml"))
    if not existing:
        _seed_date_queries()
        existing = list(DATE_DIR.glob("*.toml"))

    queries = []
    for fp in sorted(existing, key=lambda p: p.stat().st_mtime, reverse=True):
        cfg = _load_toml_file(fp)
        q = cfg.get("query", {})
        if not q.get("name"):
            q["name"] = fp.stem
        q["filename"] = fp.name  # 附加文件名，用于删除/更新
        queries.append(q)

    with _lock:
        _cached_date_queries = queries


def save_date_query(data: dict) -> dict:
    """保存一条快捷查询（新增或覆盖），返回更新后的完整条目"""
    name = data.get("name", "").strip()
    if not name:
        raise ValueError("查询名称不能为空")
    filename = _sanitize_filename(name) + ".toml"
    filepath = DATE_DIR / filename

    from datetime import datetime
    query = {
        "name": name,
        "folder": data.get("folder", ""),
        "pattern": data.get("pattern", "*.log"),
        "keyword": data.get("keyword", ""),
        "line_count": int(data.get("line_count", DEFAULT_LINES)),
        "tail": bool(data.get("tail", True)),
        "recent_files": int(data.get("recent_files", DEFAULT_RECENT_FILES)),
        "desc": data.get("desc", ""),
        "created_at": data.get("created_at") or datetime.now().isoformat(timespec="seconds"),
    }
    _write_date_file(filepath, query)

    # 即时更新缓存
    query["filename"] = filename
    with _lock:
        # 覆盖或追加
        for i, q in enumerate(_cached_date_queries):
            if q.get("filename") == filename:
                _cached_date_queries[i] = query
                break
        else:
            _cached_date_queries.insert(0, query)

    return query


def delete_date_query(filename: str) -> bool:
    """删除一条快捷查询，返回是否成功"""
    filepath = DATE_DIR / filename
    if not filepath.exists() or filepath.suffix != ".toml":
        return False
    filepath.unlink()

    with _lock:
        global _cached_date_queries
        _cached_date_queries = [q for q in _cached_date_queries if q.get("filename") != filename]
    return True


def get_date_queries() -> List[Dict[str, Any]]:
    """获取所有快捷查询"""
    return list(_cached_date_queries)


_topology_health_checked = False


def _check_topology_health():
    """检测拓扑/目录配置是否意外丢失，尝试从备份或模板恢复"""
    global _topology_health_checked
    if _topology_health_checked:
        return
    _topology_health_checked = True
    has_server = bool(ROOT_DIRS)
    has_topo = bool(_cached_topo_categories or _cached_topo_services)
    has_dirs = bool(_cached_dirs_meta)

    # 如果有服务配置但无拓扑/目录 → 配置可能损坏
    if has_server and not has_topo and not has_dirs:
        print("[Config] 检测到拓扑和目录配置为空，尝试自动恢复...")
        recovered = False

        # 1. 尝试从备份恢复
        config_path = _get_config_path()
        bak_path = config_path.with_suffix('.toml.bak')
        if bak_path.exists():
            try:
                bak_cfg = _load_toml_file(bak_path)
                bak_topo = bak_cfg.get("topology", {})
                if bak_topo.get("category") or bak_topo.get("service") or bak_cfg.get("dir"):
                    print(f"[Config] 从备份恢复: {bak_path}")
                    import shutil
                    shutil.copy2(bak_path, config_path)
                    reload_config()  # 重载
                    recovered = True
            except Exception as e:
                print(f"[Config] 备份恢复失败: {e}")

        # 2. 从模板恢复
        if not recovered:
            template_path = CONFIG_TEMPLATE_PATH
            if template_path.exists():
                try:
                    tpl_cfg = _load_toml_file(template_path)
                    tpl_topo = tpl_cfg.get("topology", {})
                    if tpl_topo.get("category") or tpl_topo.get("service") or tpl_cfg.get("dir"):
                        print(f"[Config] 从模板恢复: {template_path}")
                        import shutil
                        shutil.copy2(template_path, config_path)
                        reload_config()  # 重载
                        recovered = True
                except Exception as e:
                    print(f"[Config] 模板恢复失败: {e}")

        if not recovered:
            print("[Config] 警告: 拓扑/目录配置丢失，且备份和模板均不可用")


# 初始加载
reload_config()
reload_debug_config()
