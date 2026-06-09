"""
postlook · FastAPI 应用入口
轻量、安全的日志 HTTP 查询服务
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .routes import router

# 版本号（唯一来源）
__version__ = "0.2.0"

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


# ── 多页面路由（干净 URL）──
_static = Path(__file__).parent / "static"


@app.get("/logs")
async def logs_page():
    return FileResponse(_static / "logs.html")


@app.get("/config")
async def config_page():
    return FileResponse(_static / "config.html")


@app.get("/status")
async def status_page():
    return FileResponse(_static / "status.html")


@app.get("/topology")
async def topology_page():
    return FileResponse(_static / "topology.html")


# 挂载静态文件（必须在所有 API 路由之后）
app.mount("/", StaticFiles(directory=_static, html=True), name="static")
