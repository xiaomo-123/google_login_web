import os
from typing import Optional

class Settings:
    # 应用配置
    APP_NAME: str = "Google登录管理系统"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    PORT: int = 6431
    SERVER_PORT: int = 6431  # 心跳服务使用的端口配置

    # 数据库配置
    DATABASE_URL: str = "sqlite:///./google_login.db"

    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DECODE_RESPONSES: bool = True

    # CORS配置
    CORS_ORIGINS: list = [
        "http://localhost:6431",
        "http://127.0.0.1:6431",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]

    # 分页配置
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Google登录配置
    HEADLESS: bool = False  # 浏览器是否无头模式
    MAX_WORKERS: int = 3    # 最大并发数

    # 文件上传配置
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB

settings = Settings()
