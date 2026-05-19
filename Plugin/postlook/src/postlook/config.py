"""
postlook · 配置模块
从 config/env.toml 和环境变量加载配置
"""

import os
from pathlib import Path
from typing import List

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 尝试加载 TOML 配置
_config = {}
_toml_path = PROJECT_ROOT / "config" / "env.toml"
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

if tomllib and _toml_path.exists():
    with open(_toml_path, "rb") as f:
        _config = tomllib.load(f)


def _get(key: str, default=None):
    """从 TOML 配置或环境变量获取值"""
    # 环境变量优先
    env_key = f"POSTLOOK_{key.upper()}"
    env_val = os.environ.get(env_key)
    if env_val is not None:
        return env_val

    # TOML 嵌套键 (如 server.port)
    parts = key.split(".")
    val = _config
    for p in parts:
        if isinstance(val, dict):
            val = val.get(p)
        else:
            return default
    return val if val is not None else default


# ---- 服务配置 ----
SERVER_HOST = _get("server.host", "0.0.0.0")
SERVER_PORT = int(_get("server.port", 5011))

# ---- 日志配置 ----
# 允许访问的根目录列表
_root_dirs = _get("logs.root_dirs", ["/var/log"])
if isinstance(_root_dirs, str):
    ROOT_DIRS = [d.strip() for d in _root_dirs.split(",") if d.strip()]
else:
    ROOT_DIRS = list(_root_dirs) if _root_dirs else ["/var/log"]

# 也支持环境变量 POSTLOOK_ROOT（逗号分隔）
env_root = os.environ.get("POSTLOOK_ROOT")
if env_root:
    ROOT_DIRS = [d.strip() for d in env_root.split(",") if d.strip()]

MAX_LINES = int(_get("logs.max_lines", 100))
DEFAULT_LINES = int(_get("logs.default_lines", 50))
DEFAULT_RECENT_FILES = int(_get("logs.default_recent_files", 10))
MAX_RECENT_FILES = 50

# ---- UI 配置 ----
DEFAULT_THEME = _get("ui.theme", "dark")
