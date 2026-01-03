from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from app.api import accounts, auth_urls, tasks, proxies
from app.config import settings
from app.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    print("正在初始化数据库...")
    init_db()
    print("数据库初始化完成")

    # 初始化Redis连接
    print("正在初始化Redis连接...")
    try:
        from app.redis_client import redis_pool
        import redis
        # 测试Redis连接
        test_redis = redis.Redis(connection_pool=redis_pool)
        test_redis.ping()
        print("Redis连接成功")
    except Exception as e:
        print(f"Redis连接失败: {str(e)}")
        print("警告: 账号管理功能将无法使用，请确保Redis服务正在运行")

    yield
    # 关闭时执行
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

    # 挂载静态文件
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # 根路径返回首页
    @app.get("/", response_class=HTMLResponse)
    async def read_root():
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    return app

# 创建应用实例
app = create_app()
