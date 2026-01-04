from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from app.api import accounts, auth_urls, tasks, proxies, websocket, logs
from app.websocket_server import log_manager
from app.config import settings
from app.database import init_db
from app.services.heartbeat import heartbeat_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    init_db()

    # 初始化心跳服务
    heartbeat_service.init_app(app)
    heartbeat_service.start()
    print("心跳服务已启动")

    # 启动Redis日志订阅者
    import asyncio
    asyncio.create_task(log_manager.start_redis_subscriber())

    yield
    # 关闭时执行
    print("正在关闭心跳服务...")
    heartbeat_service.stop()
    await log_manager.stop_redis_subscriber()
    print("应用关闭")

def create_app():
    """创建FastAPI应用"""
    # 创建FastAPI应用
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        description="Google登录管理系统",
        debug=settings.DEBUG,
        lifespan=lifespan
    )

    # 配置CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    # 注册API路由
    app.include_router(accounts.router)
    app.include_router(auth_urls.router)
    app.include_router(tasks.router)
    app.include_router(proxies.router)
    app.include_router(websocket.router)
    app.include_router(logs.router)

    # 挂载静态文件
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # 根路径返回首页
    @app.get("/", response_class=HTMLResponse)
    async def read_root():
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    # 日志查看器页面
    @app.get("/logs", response_class=HTMLResponse)
    async def log_viewer():
        with open("templates/log-viewer.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    # 健康检查端点
    @app.get("/health")
    async def health_check():
        """健康检查端点，用于心跳保活"""
        return {
            "status": "ok",
            "service": settings.APP_NAME,
            "version": settings.VERSION
        }

    return app

# 创建应用实例
app = create_app()
