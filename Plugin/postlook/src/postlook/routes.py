"""
postlook · API 路由
"""

import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from . import config as app_config
from .scanner import scan_logs, resolve_folder, is_allowed_download

router = APIRouter()


def _get_root_dirs():
    return app_config.ROOT_DIRS


def _get_max_lines():
    return app_config.MAX_LINES


def _get_default_lines():
    return app_config.DEFAULT_LINES


def _get_default_recent():
    return app_config.DEFAULT_RECENT_FILES


class LogQueryRequest(BaseModel):
    """POST /api/logs 请求体"""
    folder: str = Field(..., description="日志子目录或白名单内的绝对路径")
    pattern: str = Field(default="*.log", description="文件名通配符")
    keyword: Optional[str] = Field(default=None, description="搜索关键字（不区分大小写）")
    line_start: int = Field(default=1, ge=1, description="起始行号")
    line_end: int = Field(default=100, ge=1, description="结束行号（含）")
    tail: bool = Field(default=True, description="无关键字时从尾部读取")
    recent_files: int = Field(default=10, ge=1, le=50, description="扫描最近修改的 N 个文件")

    @field_validator("line_end")
    @classmethod
    def validate_line_range(cls, v, info):
        start = info.data.get("line_start")
        if start is not None and v is not None and v < start:
            raise ValueError("line_end 不能小于 line_start")
        return v


class LogQueryResponse(BaseModel):
    """POST /api/logs 响应体"""
    total_lines: int
    truncated: bool
    results: list
    keyword: Optional[str] = None
    error: Optional[str] = None


@router.post("/api/logs", response_model=LogQueryResponse)
async def query_logs(req: LogQueryRequest):
    """
    查询日志内容。
    在指定文件夹内按文件名、关键字、行数等条件搜索。
    """
    try:
        from .app import __version__
        result = scan_logs(
            folder=req.folder,
            root_dirs=app_config.ROOT_DIRS,
            pattern=req.pattern,
            keyword=req.keyword,
            tail=req.tail,
            recent_files=req.recent_files,
            line_start=req.line_start,
            line_end=req.line_end,
        )
        result["postlook_version"] = __version__

        if result.get("error") and not result.get("results"):
            raise HTTPException(status_code=404, detail=result["error"])

        return result

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ConfigUpdateRequest(BaseModel):
    """POST /api/config 请求体"""
    content: str = Field(..., description="TOML 配置内容")


@router.get("/api/config")
async def get_config():
    """获取当前 TOML 配置原文"""
    from .config import get_config_toml
    toml_content = get_config_toml()
    return {
        "content": toml_content,
        "root_dirs": app_config.ROOT_DIRS,
        "max_lines": app_config.MAX_LINES,
        "default_lines": app_config.DEFAULT_LINES,
        "default_recent_files": app_config.DEFAULT_RECENT_FILES,
        "max_download_size_mb": app_config.DEFAULT_DOWNLOAD_SIZE,
    }


@router.post("/api/config")
async def save_config(req: ConfigUpdateRequest):
    """保存配置并热更新"""
    from .config import save_config_toml
    try:
        save_config_toml(req.content)
        return {"status": "ok", "message": "配置已保存并热更新生效"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"无法写入配置文件: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/files")
async def list_files():
    """列出白名单目录下的文件树（按修改时间降序）"""
    import os
    from datetime import datetime
    from pathlib import Path

    dirs_info = []
    for root_dir in app_config.ROOT_DIRS:
        root_path = Path(root_dir)
        if not root_path.exists():
            dirs_info.append({
                "path": root_dir,
                "exists": False,
                "files": []
            })
            continue

        files = []
        try:
            for entry in root_path.rglob("*"):
                if entry.is_file() and not entry.is_symlink():
                    # 隐藏 .jar 文件（仅支持后台下载，前端不展示）
                    if entry.name.lower().endswith('.jar'):
                        continue
                    stat = entry.stat()
                    files.append({
                        "name": entry.name,
                        "path": str(entry),
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "mtime_str": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    })
        except PermissionError:
            pass

        # 按修改时间降序排列
        files.sort(key=lambda f: f["mtime"], reverse=True)

        dirs_info.append({
            "path": root_dir,
            "exists": True,
            "files": files,
            "file_count": len(files),
        })

    return {"directories": dirs_info}


@router.get("/api/scan-dirs")
async def scan_dirs(base: str = "/main/app"):
    """递归扫描指定路径下名为 log/logs 的目录"""
    from pathlib import Path

    base_path = Path(base)
    if not base_path.exists():
        return {"base": base, "exists": False, "dirs": []}

    found = []
    target_names = {"log", "logs"}

    try:
        for entry in base_path.rglob("*"):
            if entry.is_dir() and not entry.is_symlink() and entry.name.lower() in target_names:
                # 统计目录内文件数
                file_count = 0
                latest_mtime = 0
                try:
                    for f in entry.rglob("*"):
                        if f.is_file():
                            file_count += 1
                            mtime = f.stat().st_mtime
                            if mtime > latest_mtime:
                                latest_mtime = mtime
                except PermissionError:
                    pass

                found.append({
                    "path": str(entry),
                    "file_count": file_count,
                    "latest_mtime": latest_mtime,
                })
    except PermissionError:
        pass

    # 按最新修改时间降序
    found.sort(key=lambda d: d["latest_mtime"], reverse=True)

    return {"base": base, "exists": True, "dirs": found}


@router.get("/api/logs/self")
async def self_logs(lines: int = 100, keyword: str = None):
    """查看 postlook 自身日志"""
    import os
    log_path = os.environ.get("POSTLOOK_SELF_LOG", str(Path(__file__).resolve().parent.parent.parent / "logs" / "postlook.log"))
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except FileNotFoundError:
        return {"total_lines": 0, "results": [], "error": f"日志文件不存在: {log_path}"}

    total = len(all_lines)
    start = max(0, total - lines)
    selected = all_lines[start:]

    results = []
    kw_lower = keyword.lower() if keyword else None
    for i, line in enumerate(selected):
        if kw_lower and kw_lower not in line.lower():
            continue
        results.append({
            "line": start + i + 1,
            "content": line.rstrip("\n\r")
        })

    return {
        "total_lines": len(results),
        "results": results,
        "log_file": log_path,
        "log_total_lines": total,
    }


@router.get("/api/download")
async def download_file(path: str = Query(..., description="要下载的文件绝对路径（必须在白名单内）")):
    """
    下载日志文件。
    仅允许下载日志类文件（.log/.out/.txt/.gz 等），
    禁止下载脚本、配置、证书、可执行文件等非日志文件。
    """
    try:
        resolved = resolve_folder(path, app_config.ROOT_DIRS)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {path}")
    if not resolved.is_file():
        raise HTTPException(status_code=400, detail=f"路径不是文件: {path}")

    # 安全：扩展名白名单校验
    if not is_allowed_download(resolved):
        raise HTTPException(
            status_code=403,
            detail=f"文件类型不允许下载 (仅允许日志类文件): {resolved.name}"
        )

    # 安全：文件大小上限
    file_size = resolved.stat().st_size
    max_size = app_config.MAX_DOWNLOAD_SIZE
    if file_size > max_size:
        size_mb = file_size / (1024 * 1024)
        limit_mb = max_size / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"文件过大 ({size_mb:.1f}MB)，超过下载上限 {limit_mb:.0f}MB"
        )

    # 流式返回文件
    return FileResponse(
        path=resolved,
        filename=resolved.name,
        media_type="application/octet-stream",
    )


# ---- 扩展配置 API (v0.3.0) ----

@router.get("/api/rules")
async def get_rules():
    """获取所有规则（着色 + 注解 + 快捷查询）"""
    from .config import get_rules as _get_rules
    rules = _get_rules()
    return {"rules": rules, "count": len(rules)}


class RulesUpdateRequest(BaseModel):
    """POST /api/rules 请求体"""
    content: str = Field(..., description="TOML 规则配置内容")


@router.post("/api/rules")
async def save_rules(req: RulesUpdateRequest):
    """保存 rules.toml 并热更新（着色/注解规则即时生效）"""
    from .config import save_rules_toml
    try:
        save_rules_toml(req.content)
        return {"status": "ok", "message": "规则配置已保存并热更新生效"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"无法写入规则文件: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/rules-toml")
async def get_rules_toml():
    """获取 rules.toml 原文"""
    from .config import get_rules_toml as _get_rules_toml
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(_get_rules_toml())


@router.get("/api/topology-config")
async def get_topology_config():
    """获取拓扑图配置（分类+服务节点）"""
    from .config import get_topology_config as _get_topo
    return _get_topo()


@router.get("/api/dirs-meta")
async def get_dirs_meta():
    """获取日志目录元数据"""
    from .config import get_dirs_meta as _get_meta
    meta = _get_meta()
    # 转成 {path: info} 映射方便前端查找
    meta_map = {}
    for m in meta:
        meta_map[m.get("path", "")] = m
    return {"dirs": meta, "map": meta_map}


@router.get("/api/help")
async def api_help():
    """返回模块接口文档和使用说明"""
    from .app import __version__
    return {
        "name": "postlook",
        "version": __version__,
        "description": "轻量、安全的日志 HTTP 查询服务",
        "base_url": f"http://localhost:{app_config.SERVER_PORT}",
        "endpoints": [
            {
                "method": "POST",
                "path": "/api/logs",
                "description": "查询日志内容",
                "parameters": {
                    "folder": "string (必填) - 日志目录或文件路径，相对于白名单根目录或绝对路径",
                    "pattern": "string (默认 *.log) - 文件名通配符，目录模式下生效",
                    "keyword": "string (可选) - 搜索关键字，不区分大小写",
                    "line_start": "int (默认 1) - 起始行号",
                    "line_end": "int (默认 100) - 结束行号（含）",
                    "tail": "bool (默认 true) - 无关键字时从尾部读取",
                    "recent_files": "int (默认 10, 最大 50) - 扫描最近修改的 N 个文件"
                },
                "example": 'curl -X POST http://localhost:5011/api/logs -H "Content-Type: application/json" -d \'{"folder": "/var/log", "pattern": "*.log", "line_start": 1, "line_end": 20}\''
            },
            {
                "method": "GET",
                "path": "/api/config",
                "description": "获取当前 TOML 配置"
            },
            {
                "method": "POST",
                "path": "/api/config",
                "description": "保存 TOML 配置（热更新，无需重启）",
                "parameters": {
                    "content": "string (必填) - TOML 格式配置内容"
                }
            },
            {
                "method": "GET",
                "path": "/api/scan-dirs",
                "description": "扫描指定路径下名为 log/logs 的目录",
                "parameters": {
                    "base": "string (默认 /main/app) - 扫描的基础路径"
                },
                "example": "curl http://localhost:5011/api/scan-dirs?base=/main/app/"
            },
            {
                "method": "GET",
                "path": "/api/files",
                "description": "列出白名单目录下的所有文件"
            },
            {
                "method": "GET",
                "path": "/api/logs/self",
                "description": "查看 postlook 自身日志",
                "parameters": {
                    "lines": "int (默认 100) - 返回最近 N 行",
                    "keyword": "string (可选) - 过滤关键字"
                },
                "example": "curl http://localhost:5011/api/logs/self?lines=50"
            },
            {
                "method": "GET",
                "path": "/api/download",
                "description": "下载日志文件（白名单路径 + 扩展名白名单双重管控）",
                "parameters": {
                    "path": "string (必填) - 文件绝对路径"
                },
                "example": "curl -O http://localhost:5011/api/download?path=/main/app/gateway/logs/GATEWAY.log"
            },
            {
                "method": "GET",
                "path": "/api/health",
                "description": "健康检查"
            },
            {
                "method": "GET",
                "path": "/api/help",
                "description": "接口文档和使用说明（本接口）"
            },
            {
                "method": "GET",
                "path": "/docs",
                "description": "Swagger UI 交互式 API 文档"
            },
            {
                "method": "GET",
                "path": "/api/version",
                "description": "版本号 + 关键文件 hash（升级后校验代码是否生效）"
            },
            {
                "method": "POST",
                "path": "/api/system/reload",
                "description": "重启 Postlook 进程（退出后由 supervisor 自动拉起）"
            }
        ],
        "usage": {
            "web_ui": f"浏览器访问 http://localhost:{app_config.SERVER_PORT}",
            "quick_query": 'curl -X POST http://localhost:5011/api/logs -H "Content-Type: application/json" -d \'{"folder": "/var/log", "line_start": 1, "line_end": 50}\'',
            "keyword_search": 'curl -X POST http://localhost:5011/api/logs -H "Content-Type: application/json" -d \'{"folder": "/var/log", "keyword": "error", "line_start": 1, "line_end": 500}\'',
            "view_config": "curl http://localhost:5011/api/config",
            "list_files": "curl http://localhost:5011/api/files",
            "self_logs": "curl http://localhost:5011/api/logs/self?lines=50",
            "download_file": "curl -O 'http://localhost:5011/api/download?path=/var/log/messages'"
        },
        "config": {
            "root_dirs": app_config.ROOT_DIRS,
            "max_lines": app_config.MAX_LINES,
            "default_lines": app_config.DEFAULT_LINES,
        }
    }


@router.get("/api/version")
async def api_version():
    """返回版本号 + 关键文件 hash（用于升级后校验代码是否生效）"""
    import hashlib
    from pathlib import Path as _Path
    from .app import __version__

    _src = _Path(__file__).resolve().parent
    key_files = {
        "routes.py": _src / "routes.py",
        "scanner.py": _src / "scanner.py",
        "config.py": _src / "config.py",
        "debug_service.py": _src / "debug_service.py",
        "app.py": _src / "app.py",
    }
    hashes = {}
    for name, path in key_files.items():
        try:
            if path.exists():
                h = hashlib.md5(path.read_bytes()).hexdigest()[:8]
                hashes[name] = h
        except Exception:
            pass

    return {
        "version": __version__,
        "file_hashes": hashes,
        "hash": hashlib.md5(
            "".join(hashes.values()).encode()
        ).hexdigest()[:8],
    }


@router.post("/api/system/reload")
async def reload_postlook():
    """重启 Postlook 进程（退出后依赖 supervisor auto-restart 拉起新代码）"""
    import os as _os, signal as _signal
    from threading import Timer

    def _do_exit():
        _os.kill(_os.getpid(), _signal.SIGTERM)

    # 延迟 500ms 退出，确保 HTTP 响应先发出去
    Timer(0.5, _do_exit).start()
    return {"status": "ok", "message": "Postlook 正在重启，新代码即将生效"}


# ════════════════════════════════════════════════════════════
#  报文调试 API (v0.4.0)
# ════════════════════════════════════════════════════════════

class TestConnectionRequest(BaseModel):
    """POST /api/debug/test-connection 请求体"""
    host: str = Field(..., description="目标主机 IP 或域名")
    port: int = Field(..., ge=1, le=65535, description="目标端口")


class SendMessageRequest(BaseModel):
    """POST /api/debug/send 请求体"""
    hex: str = Field(..., description="十六进制报文内容")


class ConfigContentRequest(BaseModel):
    """配置保存请求体（复用）"""
    content: str = Field(..., description="TOML 配置内容")


@router.post("/api/debug/test-connection")
async def debug_test_connection(req: TestConnectionRequest):
    """Ping + TCP 端口检测"""
    from .debug_service import test_connection
    try:
        result = test_connection(req.host, req.port)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/debug/messages")
async def debug_get_messages():
    """获取报文分组数据（JSON）"""
    from .debug_service import load_messages
    return load_messages()


@router.get("/api/debug/messages-toml")
async def debug_get_messages_toml():
    """获取 messages.toml 原文"""
    from fastapi.responses import PlainTextResponse
    from .debug_service import MESSAGES_PATH
    if MESSAGES_PATH.exists():
        with open(MESSAGES_PATH, "r", encoding="utf-8") as f:
            return PlainTextResponse(f.read())
    return PlainTextResponse("# messages.toml 不存在\n", status_code=404)


@router.post("/api/debug/messages")
async def debug_save_messages(req: ConfigContentRequest):
    """保存报文数据（热更新）"""
    from .debug_service import save_messages
    try:
        result = save_messages(req.content)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return {"status": "ok", "message": "报文数据已保存并热更新生效", "data": result}
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"无法写入: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/debug/reload")
async def debug_reload():
    """热重新加载报文配置"""
    from .debug_service import reload_messages
    result = reload_messages()
    return {"status": "ok" if result.get("success") else "error", "message": "报文配置已重新加载", "data": result}


@router.get("/api/debug/config")
async def debug_get_config():
    """获取 TCP 连接配置"""
    from .config import get_debug_config, get_debug_config_toml
    return {
        "config": get_debug_config(),
        "toml": get_debug_config_toml(),
    }


@router.post("/api/debug/config")
async def debug_save_config(req: ConfigContentRequest):
    """保存连接配置（热更新）"""
    from .config import save_debug_config_toml
    try:
        save_debug_config_toml(req.content)
        return {"status": "ok", "message": "调试配置已保存并热更新生效"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"无法写入: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/debug/send")
async def debug_send(req: SendMessageRequest):
    """发送单条 hex 报文（连接→发送→接收→断开）"""
    from .debug_service import send_hex_message
    cfg = app_config.get_debug_config()
    conn = cfg["connection"]
    send_opts = cfg["send"]

    result = send_hex_message(
        host=conn["host"],
        port=conn["port"],
        hex_str=req.hex,
        connect_timeout=conn["timeout"],
        recv_timeout=conn["recv_timeout"],
        recv_buffer=conn["recv_buffer"],
        auto_lowercase=send_opts["auto_lowercase"],
        auto_uppercase=send_opts["auto_uppercase"],
    )

    if not result["success"] and result["error"]:
        raise HTTPException(status_code=502, detail=result["error"])

    return result
