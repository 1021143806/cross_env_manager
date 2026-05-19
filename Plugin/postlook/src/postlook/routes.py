"""
postlook · API 路由
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from . import config as app_config
from .scanner import scan_logs

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
    """列出白名单目录下的文件树"""
    import os
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
            for entry in sorted(root_path.rglob("*")):
                if entry.is_file() and not entry.is_symlink():
                    stat = entry.stat()
                    files.append({
                        "name": entry.name,
                        "path": str(entry),
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                    })
        except PermissionError:
            pass

        dirs_info.append({
            "path": root_dir,
            "exists": True,
            "files": files,
            "file_count": len(files),
        })

    return {"directories": dirs_info}


@router.get("/api/help")
async def api_help():
    """返回模块接口文档和使用说明"""
    return {
        "name": "postlook",
        "version": "0.1.0",
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
                "path": "/api/files",
                "description": "列出白名单目录下的所有文件"
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
            }
        ],
        "usage": {
            "web_ui": f"浏览器访问 http://localhost:{app_config.SERVER_PORT}",
            "quick_query": 'curl -X POST http://localhost:5011/api/logs -H "Content-Type: application/json" -d \'{"folder": "/var/log", "line_start": 1, "line_end": 50}\'',
            "keyword_search": 'curl -X POST http://localhost:5011/api/logs -H "Content-Type: application/json" -d \'{"folder": "/var/log", "keyword": "error", "line_start": 1, "line_end": 500}\'',
            "view_config": "curl http://localhost:5011/api/config",
            "list_files": "curl http://localhost:5011/api/files"
        },
        "config": {
            "root_dirs": app_config.ROOT_DIRS,
            "max_lines": app_config.MAX_LINES,
            "default_lines": app_config.DEFAULT_LINES,
        }
    }
