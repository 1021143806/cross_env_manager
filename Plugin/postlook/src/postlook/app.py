"""
postlook · FastAPI 应用入口
轻量、安全的日志 HTTP 查询服务
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import router

# 版本号（唯一来源）
__version__ = "0.1.0"

app = FastAPI(
    title="postlook",
    description="轻量、安全的日志 HTTP 查询服务",
    version=__version__
)

# API 路由需在静态文件挂载之前定义
app.include_router(router)


@app.get("/api/health")
async def health():
    """健康检查端点"""
    return {"status": "ok", "version": __version__}


# 挂载静态文件（必须在所有 API 路由之后）
static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
