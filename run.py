import asyncio
import sys
import uvicorn
from app.main import app

if __name__ == "__main__":
    # Windows系统设置ProactorEventLoop以支持子进程
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=6431,
        reload=True
    )
