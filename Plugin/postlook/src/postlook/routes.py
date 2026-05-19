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
