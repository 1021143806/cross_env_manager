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
__version__ = "0.16.0"

# CEM 来源（嵌入 iframe 时使用）
_CEM_ORIGIN = "http://10.68.2.40:5000"
_CEM_ORIGIN_ALT = "http://172.31.43.181:5001"  # 旧地址兼容
# HTTPS 变体（如果 CEM 或直接访问升级到 HTTPS）
_CEM_ORIGIN_HTTPS = "https://10.68.2.40:5000"
_CEM_ORIGIN_ALT_HTTPS = "https://172.31.43.181:5001"
# 直接 HTTPS 访问 postlook 自身
_CEM_ORIGIN_SELF = "https://10.68.2.40:5011"
_CEM_ORIGIN_SELF_ALT = "https://172.31.43.181:5011"

app = FastAPI(
    title="postlook",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[_CEM_ORIGIN, _CEM_ORIGIN_ALT, _CEM_ORIGIN_HTTPS, _CEM_ORIGIN_ALT_HTTPS, _CEM_ORIGIN_SELF, _CEM_ORIGIN_SELF_ALT],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── CSP 中间件：允许 CEM 通过 iframe 嵌入页面 ──
class FrameAncestorsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = \
            f"frame-ancestors 'self' {_CEM_ORIGIN} {_CEM_ORIGIN_ALT} {_CEM_ORIGIN_HTTPS} {_CEM_ORIGIN_ALT_HTTPS} {_CEM_ORIGIN_SELF} {_CEM_ORIGIN_SELF_ALT}"
        return response


app.add_middleware(FrameAncestorsMiddleware)

# API 路由需在静态文件挂载之前定义
app.include_router(router)


@app.on_event("startup")
async def startup():
    """启动后台任务"""
    from .routes import start_stats_collector
    await start_stats_collector()


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
