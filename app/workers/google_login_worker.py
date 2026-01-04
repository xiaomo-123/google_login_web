import asyncio
import sys
import threading
from datetime import datetime
from app.database import SessionLocal
from app.models.task import Task
from app.models.auth_url import AuthUrl
from app.services.google_login_service import google_login_single, get_auth_url
from app.redis_client import account_redis_service
from app.websocket_server import log_publisher

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
            log_publisher.publish_log(task_id, "error", f"任务ID {task_id} 不存在")
            return

        # 发送任务开始日志
        log_publisher.publish_log(task_id, "info", f"任务开始执行: {task.name}")

        # 获取授权地址
        auth_url_obj = db.query(AuthUrl).filter(AuthUrl.id == task.auth_url_id).first()
        if not auth_url_obj:
            log_publisher.publish_log(task_id, "error", f"授权地址ID {task.auth_url_id} 不存在")
            raise Exception(f"授权地址ID {task.auth_url_id} 不存在")

        log_publisher.publish_log(task_id, "info", "正在获取授权地址信息...")
        log_publisher.publish_log(task_id, "info", f"授权地址ID: {auth_url_obj.id}")
        log_publisher.publish_log(task_id, "info", f"授权地址名称: {auth_url_obj.name}")
        log_publisher.publish_log(task_id, "info", f"授权地址URL: {auth_url_obj.url}")
        log_publisher.publish_log(task_id, "info", f"授权地址状态: {'正常' if auth_url_obj.status == 1 else '禁用'}")

        # 获取账号信息
        accounts = account_redis_service.get_all_accounts(get_all=True)
        if not accounts:
            log_publisher.publish_log(task_id, "error", "没有可用的账号")
            raise Exception("没有可用的账号")

        account = accounts[0]
        log_publisher.publish_log(task_id, "info", "正在获取账号信息...")
        log_publisher.publish_log(task_id, "info", f"使用账号: {account['username']}")

        # 请求授权地址
        log_publisher.publish_log(task_id, "info", "正在请求授权地址...")
        google_login_url = await get_auth_url(
            auth_url=auth_url_obj.url,
            description=auth_url_obj.description
        )
        log_publisher.publish_log(task_id, "info", f"获取到的授权地址: {google_login_url}")

        # 更新任务状态为运行中
        task.status = "running"
        task.started_at = datetime.now()
        db.commit()
        log_publisher.publish_log(task_id, "info", f"任务状态已更新为运行中")

        # 执行登录
        try:
            log_publisher.publish_log(task_id, "info", "开始执行Google登录操作...")
            result = await google_login_single(
                username=account["username"],
                password=account["password"],
                auth_url=google_login_url,
                headless=False,
                task_id=task_id
            )

            # 更新任务状态为完成
            task.status = "completed"
            task.result = "登录成功"
            task.completed_at = datetime.now()
            db.commit()
            log_publisher.publish_log(task_id, "info", "登录成功！任务执行完成")

        except asyncio.CancelledError:
            log_publisher.publish_log(task_id, "warning", f"任务被取消")
            task.status = "stopped"
            task.completed_at = datetime.now()
            db.commit()
        except Exception as e:
            # 更新任务状态为错误
            log_publisher.publish_log(task_id, "error", f"执行任务失败: {str(e)}")
            task.status = "error"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()
            raise e

    except Exception as e:
        log_publisher.publish_log(task_id, "error", f"Google登录任务异常: {str(e)}")
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
