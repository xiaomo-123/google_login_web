import asyncio
import sys
import threading
from datetime import datetime
from app.database import SessionLocal
from app.models.task import Task
from app.models.auth_url import AuthUrl
from app.services.google_login_service import google_login_single, get_auth_url
from app.redis_client import account_redis_service

# 全局worker实例管理器
worker_instances = {}

def run_google_login_task(task_id: int):
    """运行Google登录任务"""
    # 在新线程中运行异步任务
    def run_in_thread():
        # Windows系统设置ProactorEventLoop以支持子进程
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(_run_google_login_task(task_id))
        finally:
            loop.close()

    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()
    return thread

async def _run_google_login_task(task_id: int):
    """内部异步函数，执行Google登录任务"""
    db = SessionLocal()

    try:
        # 获取任务信息
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            print(f"任务ID {task_id} 不存在")
            return

        # 获取授权地址
        auth_url_obj = db.query(AuthUrl).filter(AuthUrl.id == task.auth_url_id).first()
        if not auth_url_obj:
            raise Exception(f"授权地址ID {task.auth_url_id} 不存在")

        print(f"\n授权地址:")
        print(f"  ID: {auth_url_obj.id}")
        print(f"  名称: {auth_url_obj.name}")
        print(f"  URL: {auth_url_obj.url}")
        print(f"  描述: {auth_url_obj.description}")
        print(f"  状态: {'正常' if auth_url_obj.status == 1 else '禁用'}")

        # 获取账号信息
        accounts = account_redis_service.get_all_accounts(get_all=True)
        if not accounts:
            raise Exception("没有可用的账号")

        account = accounts[0]
        print(f"\n账号信息:")
        print(f"  用户名: {account['username']}")

        # 请求授权地址
        print(f"\n正在请求授权地址...")
        google_login_url = await get_auth_url(
            auth_url=auth_url_obj.url,
            description=auth_url_obj.description
        )
        print(f"获取到的授权地址: {google_login_url}")

        # 更新任务状态为运行中
        task.status = "running"
        task.started_at = datetime.now()
        db.commit()
        print(f"任务 {task_id} 状态已更新为运行中")

        # 执行登录
        try:
            result = await google_login_single(
                username=account["username"],
                password=account["password"],
                auth_url=google_login_url,
                headless=False
            )

            # 更新任务状态为完成
            task.status = "completed"
            task.result = "登录成功"
            task.completed_at = datetime.now()
            db.commit()
            print(f"任务 {task_id} 登录成功")

        except asyncio.CancelledError:
            print(f"任务 {task_id} 被取消")
        except Exception as e:
            # 更新任务状态为错误
            task.status = "error"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()
            print(f"执行任务失败: {str(e)}")
            raise e

    except Exception as e:
        print(f"Google登录任务异常: {str(e)}")
        if 'task' in locals():
            task.status = "error"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()
    finally:
        # 从全局管理器中移除
        if task_id in worker_instances:
            del worker_instances[task_id]
        db.close()
