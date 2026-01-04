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
        # 不再一次性获取所有账号，而是逐个获取
        log_publisher.publish_log(task_id, "info", "准备开始处理账号...")

        # 请求授权地址
        log_publisher.publish_log(task_id, "info", "正在请求授权地址...")
        

        # 更新任务状态为运行中
        task.status = "running"
        task.started_at = datetime.now()
        db.commit()
        log_publisher.publish_log(task_id, "info", f"任务状态已更新为运行中")

        # 并发执行多个登录任务，初始同时打开两个脚本任务
        max_concurrent = 3  # 最大并发数
        running_tasks = []  # 当前运行的任务列表
        processed_count = 0
        
        async def process_account(account):
            """处理单个账号的登录任务"""
            try:
                google_login_url = await get_auth_url(
                    auth_url=auth_url_obj.url,
                    description=auth_url_obj.description
                )
                log_publisher.publish_log(task_id, "info", f"账号 {account['username']} 获取到的授权地址: {google_login_url}")
                
                result = await google_login_single(
                    username=account["username"],
                    password=account["password"],
                    auth_url=google_login_url,
                    headless=False,
                    task_id=task_id
                )
                log_publisher.publish_log(task_id, "info", f"账号 {account['username']} 登录成功")
                return True
            except asyncio.CancelledError:
                log_publisher.publish_log(task_id, "warning", f"账号 {account['username']} 任务被取消")
                raise
            except Exception as e:
                log_publisher.publish_log(task_id, "error", f"账号 {account['username']} 登录失败: {str(e)}")
                return False
        
        while True:
            # 清理已完成的任务
            running_tasks = [task for task in running_tasks if not task.done()]
            
            # 直接获取多个账号进行并发处理
            accounts = account_redis_service.get_all_accounts(skip=processed_count, limit=max_concurrent - len(running_tasks))
            if not accounts:
                # 没有新账号，等待所有运行中的任务完成
                if running_tasks:
                    await asyncio.wait(running_tasks)
                log_publisher.publish_log(task_id, "info", "所有账号已处理完成")
                break
            
            # 为每个账号创建并启动登录任务
            for account in accounts:
                # 获取账号后立即从Redis中删除
                account_redis_service.delete_account(account["id"])
                log_publisher.publish_log(task_id, "info", f"账号 {account['username']} 已从Redis中移除")
                processed_count += 1
                
                # 创建并启动登录任务
                task = asyncio.create_task(process_account(account))
                running_tasks.append(task)
            
            # 如果还有运行中的任务且已达到最大并发数，等待一个任务完成
            if len(running_tasks) >= max_concurrent:
                done, _ = await asyncio.wait(running_tasks, return_when=asyncio.FIRST_COMPLETED)
        
        # 更新任务状态为完成
        task.status = "completed"
        task.result = "所有账号处理完成"
        task.completed_at = datetime.now()
        db.commit()
        log_publisher.publish_log(task_id, "info", "所有账号处理完成！任务执行完成")

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
