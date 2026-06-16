"""
postlook · FastAPI 应用入口
轻量、安全的日志 HTTP 查询服务
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .routes import router

# 版本号（唯一来源）
__version__ = "0.6.0"

# CEM 来源（嵌入 iframe 时使用）
_CEM_ORIGIN = "http://10.68.2.40:5000"
_CEM_ORIGIN_ALT = "http://172.31.43.181:5001"  # 旧地址兼容

app = FastAPI(
    title="postlook",
    description="轻量、安全的日志 HTTP 查询服务",
    version=__version__
)

# ── CORS 中间件：允许 CEM 跨域调用 API ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_CEM_ORIGIN, _CEM_ORIGIN_ALT],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── CSP 中间件：允许 CEM 通过 iframe 嵌入页面 ──
class FrameAncestorsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = \
            f"frame-ancestors 'self' {_CEM_ORIGIN} {_CEM_ORIGIN_ALT}"
        return response


app.add_middleware(FrameAncestorsMiddleware)

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


@app.get("/debug")
async def debug_page():
    return FileResponse(_static / "debug.html")


# 挂载静态文件（必须在所有 API 路由之后）
app.mount("/", StaticFiles(directory=_static, html=True), name="static")
