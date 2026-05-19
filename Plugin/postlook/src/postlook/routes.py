"""
postlook · API 路由
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from .config import ROOT_DIRS, MAX_LINES, DEFAULT_LINES, DEFAULT_RECENT_FILES, MAX_RECENT_FILES
from .scanner import scan_logs

router = APIRouter()


class LogQueryRequest(BaseModel):
    """POST /api/logs 请求体"""
    folder: str = Field(..., description="日志子目录或白名单内的绝对路径")
    pattern: str = Field(default="*.log", description="文件名通配符")
    keyword: Optional[str] = Field(default=None, description="搜索关键字（不区分大小写）")
    lines: int = Field(default=DEFAULT_LINES, ge=1, le=MAX_LINES, description="返回的最大总行数")
    tail: bool = Field(default=True, description="无关键字时从尾部读取")
    recent_files: int = Field(default=DEFAULT_RECENT_FILES, ge=1, le=MAX_RECENT_FILES, description="扫描最近修改的 N 个文件")
    line_start: Optional[int] = Field(default=None, ge=1, description="起始行号")
    line_end: Optional[int] = Field(default=None, ge=1, description="结束行号")

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
            root_dirs=ROOT_DIRS,
            pattern=req.pattern,
            keyword=req.keyword,
            lines=req.lines,
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


@router.get("/api/config")
async def get_config():
    """获取当前配置（脱敏）"""
    return {
        "root_dirs": ROOT_DIRS,
        "max_lines": MAX_LINES,
        "default_lines": DEFAULT_LINES,
        "default_recent_files": DEFAULT_RECENT_FILES,
    }
