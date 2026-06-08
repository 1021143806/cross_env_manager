"""
postlook · 配置模块
从 config/env.toml 和环境变量加载配置，支持热更新
"""

import os
import threading
from pathlib import Path
from typing import List, Optional

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "env.toml"

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
MAX_DOWNLOAD_SIZE: int = 200 * 1024 * 1024  # 200MB bytes
DEFAULT_DOWNLOAD_SIZE: int = 200  # 200MB for display


def _load_toml() -> dict:
    """加载 TOML 配置文件"""
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return {}

    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    return {}


def reload_config():
    """热更新：重新加载配置并更新全局变量"""
    global SERVER_HOST, SERVER_PORT, ROOT_DIRS
    global MAX_LINES, DEFAULT_LINES, DEFAULT_RECENT_FILES, DEFAULT_THEME
    global MAX_DOWNLOAD_SIZE, DEFAULT_DOWNLOAD_SIZE

    with _lock:
        cfg = _load_toml()

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


def get_config_toml() -> str:
    """读取原始 TOML 配置文件内容，不存在时返回模板"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        if content.strip():
            return content

    # 回退到模板
    template_path = PROJECT_ROOT / "config" / "template" / "env.toml"
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


def save_config_toml(content: str):
    """保存 TOML 配置并热更新"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    # 热更新
    reload_config()


# 初始加载
reload_config()
