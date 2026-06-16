"""
postlook · 配置模块
从 config/app.toml（或 env.toml）+ config/rules.toml 加载配置，支持热更新
"""

import os
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH_APP = PROJECT_ROOT / "config" / "app.toml"
CONFIG_PATH_ENV = PROJECT_ROOT / "config" / "env.toml"
RULES_PATH = PROJECT_ROOT / "config" / "rules.toml"
RULES_TEMPLATE_PATH = PROJECT_ROOT / "config" / "template" / "rules.toml"

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

# ── 内置拓扑 + 服务（随代码发布，app.toml 按 id 覆盖/新增）──
_BUILTIN_CATEGORIES: List[Dict[str, Any]] = [
    {"id": "apps",      "label": "应用系统",   "color": "#0abde3", "desc": "Java/Spring 微服务"},
    {"id": "planner",   "label": "路径规划",   "color": "#f87171", "desc": "C++ 路径规划"},
    {"id": "middleware", "label": "中间件",    "color": "#fbbf24", "desc": "Nacos 等基础设施"},
    {"id": "system",    "label": "系统日志",   "color": "#4ade80", "desc": "OS 内核/安全/定时任务"},
    {"id": "database",  "label": "数据库",    "color": "#a855f7", "desc": "MariaDB"},
]

_BUILTIN_SERVICES: List[Dict[str, Any]] = [
    # 应用系统
    {"id":"gateway","name":"Gateway","category":"apps","log_dir":"/main/app/gateway/logs","log_file":"GATEWAY.log","desc":"API 网关","size_mb":48.8},
    {"id":"bms","name":"BMS","category":"apps","log_dir":"/main/app/bms/logs","log_file":"BMS.log","desc":"业务管理/订单/地图","size_mb":96.9},
    {"id":"rdms","name":"RDMS","category":"apps","log_dir":"/main/app/rdms/logs","log_file":"RDMS.log","desc":"机器人调度","size_mb":118},
    {"id":"pms","name":"PMS","category":"apps","log_dir":"/main/app/pms/logs","log_file":"PMS.log","desc":"任务管理","size_mb":43.2},
    {"id":"sps","name":"SPS","category":"apps","log_dir":"/main/app/sps/logs","log_file":"SPS.log","desc":"路径服务","size_mb":30},
    {"id":"tps","name":"TPS","category":"apps","log_dir":"/main/app/tps/logs","log_file":"TPS.log","desc":"任务处理","size_mb":27.4},
    {"id":"ics","name":"ICS","category":"apps","log_dir":"/main/app/ics/logs","log_file":"ICS.log","desc":"交叉控制","size_mb":19.3},
    {"id":"revent","name":"REVENT","category":"apps","log_dir":"/main/app/revent/logs","log_file":"REVENT.log","desc":"事件上报","size_mb":12.8},
    {"id":"wdcs","name":"WDCS","category":"apps","log_dir":"/main/app/wdcs/logs","log_file":"WDCS.log","desc":"仓库数据采集","size_mb":11},
    {"id":"gws","name":"GWS","category":"apps","log_dir":"/main/app/gws/logs","log_file":"GWS.log","desc":"WebSocket 网关","size_mb":31.3},
    {"id":"fms","name":"FMS","category":"apps","log_dir":"/main/app/fms/logs","log_file":"FMS.log","desc":"车队管理","size_mb":5},
    {"id":"cms","name":"CMS","category":"apps","log_dir":"/main/app/cms/logs","log_file":"CMS.log","desc":"配置管理","size_mb":3.7},
    # 路径规划
    {"id":"rtpsa","name":"rtpsa","category":"planner","log_dir":"/main/app/rtpsa/logs","log_file":"rtps.log","desc":"任务分配"},
    {"id":"rtpsp-2","name":"rtpsp-2","category":"planner","log_dir":"/main/app/rtpsp-2/logs","log_file":"rtps.log","desc":"路径规划"},
    {"id":"rtpsp-3","name":"rtpsp-3","category":"planner","log_dir":"/main/app/rtpsp-3/logs","log_file":"rtps.log","desc":"路径规划"},
    # 中间件
    {"id":"nacos","name":"Nacos","category":"middleware","log_dir":"/main/server/nacos/logs","log_file":"nacos.log","desc":"服务注册/配置中心","size_mb":14.2},
    # 系统日志
    {"id":"messages","name":"messages","category":"system","log_dir":"/var/log","log_file":"messages","desc":"内核/OOM/sshd","size_mb":4},
    {"id":"secure","name":"secure","category":"system","log_dir":"/var/log","log_file":"secure","desc":"SSH 登录记录","size_mb":5.1},
    {"id":"cron","name":"cron","category":"system","log_dir":"/var/log","log_file":"cron","desc":"定时任务","size_mb":1.3},
    # 数据库
    {"id":"mariadb","name":"MariaDB","category":"database","log_dir":"/main/server/mysql","log_file":"slow-sql","desc":"慢查询日志","size_mb":1.5},
]

# 内置根目录白名单（供 logs 查询使用）
_BUILTIN_ROOT_DIRS: List[str] = [
    "/var/log",
    "/main/log/app",
    "/main/log",
    "/main/app/gateway/logs",
    "/main/app/bms/logs",
    "/main/app/rdms/logs",
    "/main/app/pms/logs",
    "/main/app/sps/logs",
    "/main/app/tps/logs",
    "/main/app/ics/logs",
    "/main/app/revent/logs",
    "/main/app/wdcs/logs",
    "/main/app/gws/logs",
    "/main/app/fms/logs",
    "/main/app/cms/logs",
    "/main/app/rtpsa/logs",
    "/main/app/rtpsp-2/logs",
    "/main/app/rtpsp-3/logs",
    "/main/server/nacos/logs",
    "/main/server/mysql",
]

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
        MAX_LINES = int(logs.get("max_lines", 100))
        DEFAULT_LINES = int(logs.get("default_lines", 50))
        DEFAULT_RECENT_FILES = int(logs.get("default_recent_files", 2))

        # 下载大小限制（单位 MB）
        download_size = int(logs.get("max_download_size", 200))
        MAX_DOWNLOAD_SIZE = min(download_size, 1024) * 1024 * 1024
        DEFAULT_DOWNLOAD_SIZE = download_size

        # ui
        ui = cfg.get("ui", {})
        DEFAULT_THEME = ui.get("theme", "dark")

        # ---- root_dirs：内置默认 + 自定义 ----
        custom_roots = logs.get("root_dirs", [])
        if isinstance(custom_roots, str):
            custom_roots = [d.strip() for d in custom_roots.split(",") if d.strip()]
        ROOT_DIRS = list(dict.fromkeys(list(_BUILTIN_ROOT_DIRS) + list(custom_roots)))
        env_root = os.environ.get("POSTLOOK_ROOT")
        if env_root:
            ROOT_DIRS = [d.strip() for d in env_root.split(",") if d.strip()]

        # ---- 服务合并：内置 + app.toml 覆盖 ----
        merged_services, merged_categories = _merge_services(
            _BUILTIN_SERVICES,
            _BUILTIN_CATEGORIES,
            cfg.get("service", []),
            cfg.get("category", [])
        )
        _cached_topo_services.clear()
        _cached_topo_services.extend(merged_services)
        _cached_topo_categories.clear()
        _cached_topo_categories.extend(merged_categories)

        # dir 元数据从 services + 自定义 dir 合并
        _cached_dirs_meta.clear()
        seen_paths = set()
        # 从 services 自动生成 dir 元数据
        for svc in merged_services:
            d = svc.get("log_dir", "")
            if d and d not in seen_paths:
                seen_paths.add(d)
                _cached_dirs_meta.append({
                    "path": d,
                    "name": svc.get("name", ""),
                    "desc": svc.get("desc", ""),
                    "tags": [svc.get("category", "")]
                })
        # 自定义 dir 条目（按 path 去重覆盖）
        for d in cfg.get("dir", []):
            p = d.get("path", "")
            if not p: continue
            idx = next((i for i, m in enumerate(_cached_dirs_meta) if m.get("path") == p), None)
            if idx is not None:
                _cached_dirs_meta[idx] = d
            else:
                _cached_dirs_meta.append(d)

    # 单独加载规则文件
    reload_rules()


def _merge_services(builtin_services, builtin_cats, custom_services, custom_cats):
    """合并内置服务与自定义服务：按 id 覆盖，按 enabled 过滤"""
    merged = {}
    # 内置先
    for s in builtin_services:
        sid = s.get("id", "")
        if sid:
            merged[sid] = dict(s)

    # 自定义覆盖/追加
    for s in custom_services:
        sid = s.get("id", "")
        if not sid: continue
        if s.get("enabled") is False:
            merged.pop(sid, None)  # 显式禁用
        else:
            merged[sid] = dict(s)  # 覆盖或新增

    services = list(merged.values())

    # 分类：内置 + 自定义覆盖
    cat_map = {c["id"]: dict(c) for c in builtin_cats}
    for c in custom_cats:
        cid = c.get("id", "")
        if cid:
            cat_map[cid] = dict(c)

    # 只保留有服务引用的分类
    used_cat_ids = {s.get("category") for s in services}
    categories = [cat_map[cid] for cid in cat_map if cid in used_cat_ids]

    return services, categories


# ---- 公开获取器 ----

def get_rules() -> List[Dict[str, Any]]:
    """获取所有规则（含着色/注解/快捷查询）"""
    return list(_cached_rules)


def get_topology_config() -> Dict[str, Any]:
    """获取拓扑图配置，仅包含磁盘上实际存在且含文件的目录对应服务"""
    services = list(_cached_topo_services)
    filtered = []
    for svc in services:
        log_dir = svc.get("log_dir", "")
        if not log_dir:
            filtered.append(svc)
            continue
        p = Path(log_dir)
        if not p.is_dir():
            continue  # 目录不存在，跳过
        # 检查目录内是否有文件
        try:
            has_files = any(f.is_file() for f in p.iterdir())
        except (PermissionError, OSError):
            has_files = False
        if has_files:
            filtered.append(svc)
    return {
        "categories": list(_cached_topo_categories),
        "services": filtered,
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
    """保存主配置并热更新（先备份 + 校验 TOML 合法性）"""
    # 校验 TOML
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    try:
        tomllib.loads(content)
    except Exception as e:
        raise ValueError(f"TOML 语法错误: {e}")

    config_path = _get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    # 写入前备份到 old/ 目录
    if config_path.exists():
        backup_dir = config_path.parent / "old"
        backup_dir.mkdir(parents=True, exist_ok=True)
        import shutil as _shutil
        backup_name = f"{config_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.toml"
        _shutil.copy2(config_path, backup_dir / backup_name)
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
