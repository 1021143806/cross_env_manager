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
DEFAULT_THEME: str = "dark"
MAX_DOWNLOAD_SIZE: int = 200 * 1024 * 1024
DEFAULT_DOWNLOAD_SIZE: int = 200

# ---- 扩展配置缓存 ----
_cached_rules: List[Dict[str, Any]] = []
_cached_topo_categories: List[Dict[str, Any]] = []
_cached_topo_services: List[Dict[str, Any]] = []
_cached_dirs_meta: List[Dict[str, Any]] = []

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
    global MAX_DOWNLOAD_SIZE, DEFAULT_DOWNLOAD_SIZE

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


def save_config_toml(content: str):
    """保存主配置并热更新"""
    config_path = _get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)
    reload_config()


def save_rules_toml(content: str):
    """保存 rules.toml 并热更新（独立热更）"""
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RULES_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    reload_rules()


# 初始加载
reload_config()
reload_debug_config()
