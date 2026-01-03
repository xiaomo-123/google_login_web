import asyncio
import threading
from datetime import datetime
from app.database import SessionLocal
from app.models.task import Task
from app.services.google_login_service import google_login_single

# 全局worker实例管理器
worker_instances = {}

def run_google_login_task(task_id: int):
    """运行Google登录任务"""
    db = SessionLocal()
    worker = None
    thread = None

    try:
        # 获取任务信息
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            print(f"任务ID {task_id} 不存在")
            return

        # 获取授权地址
        from app.models.auth_url import AuthUrl
        auth_url = db.query(AuthUrl).filter(AuthUrl.id == task.auth_url_id).first()
        if not auth_url:
            raise Exception(f"授权地址ID {task.auth_url_id} 不存在")

        # 获取账号信息
        from app.redis_client import account_redis_service
        accounts = account_redis_service.get_all_accounts(get_all=True)
        if not accounts:
            raise Exception("没有可用的账号")

        account = accounts[0]
        google_login_url = "https://accounts.google.com/signin"

        # 存储事件循环以便后续清理
        worker_loop = None

        def run_spider():
            nonlocal worker_loop
            import sys
            # Windows系统设置ProactorEventLoop以支持子进程
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

            worker_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(worker_loop)
            try:
                worker_loop.run_until_complete(google_login_single(
                    username=account["username"],
                    password=account["password"],
                    auth_url=google_login_url,
                    headless=False
                ))

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
            finally:
                # 关闭事件循环
                try:
                    worker_loop.close()
                except Exception as e:
                    print(f"关闭事件循环时出错: {str(e)}")

        thread = threading.Thread(target=run_spider, daemon=True)
        thread.start()
        print(f"任务 {task_id} 已启动")

        def monitor_task():
            """监控任务状态的函数，在单独线程中运行"""
            nonlocal worker_loop
            db_monitor = SessionLocal()
            try:
                # 在监控线程中重新查询task对象
                monitor_task = db_monitor.query(Task).filter(Task.id == task_id).first()
                if not monitor_task:
                    print(f"监控线程: 任务ID {task_id} 不存在")
                    return

                while thread.is_alive():
                    db_monitor.refresh(monitor_task)
                    if monitor_task.status != "running":  # 任务被停止
                        print(f"任务 {task_id} 已停止")
                        break
                    import time
                    time.sleep(1)

                # 任务结束
                if monitor_task.status == "running":  # 如果是任务自己停止的
                    monitor_task.status = "completed"
                    monitor_task.completed_at = datetime.now()
                    db_monitor.commit()
            except Exception as e:
                print(f"监控任务异常: {str(e)}")
            finally:
                db_monitor.close()

        # 启动监控线程
        monitor_thread = threading.Thread(target=monitor_task, daemon=True)
        monitor_thread.start()
        print(f"任务 {task_id} 的监控线程已启动")

        # 更新任务状态为运行中
        task.status = "running"
        task.started_at = datetime.now()
        db.commit()
        print(f"任务 {task_id} 状态已更新为运行中")

    except Exception as e:
        print(f"Google登录任务异常: {str(e)}")
        task.status = "error"
        task.error_message = str(e)
        task.completed_at = datetime.now()
        db.commit()

    finally:
        # 等待线程完成
        if thread and thread.is_alive():
            thread.join(timeout=5)

        # 从全局管理器中移除
        if task_id in worker_instances:
            del worker_instances[task_id]
        db.close()
