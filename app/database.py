from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# 创建数据库引擎
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 60,
    } if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基础模型类
Base = declarative_base()

# 获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 初始化数据库
def init_db():
    try:
        Base.metadata.create_all(bind=engine)

        # 如果是SQLite，启用WAL模式以支持更好的并发
        if "sqlite" in settings.DATABASE_URL:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL"))
                conn.execute(text("PRAGMA synchronous=NORMAL"))
                conn.commit()
    except Exception as e:
        if "already exists" in str(e):
            print("数据库已存在，跳过初始化")
        else:
            raise e
