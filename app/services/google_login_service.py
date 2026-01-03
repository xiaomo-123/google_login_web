from playwright.sync_api import sync_playwright, Dialog
import time
from datetime import datetime
from app.database import SessionLocal
from app.models.task import Task
from app.models.auth_url import AuthUrl
from app.redis_client import account_redis_service

def handle_dialog(dialog: Dialog):
    """监听并处理浏览器弹出的对话框"""
    print(f"检测到弹窗：{dialog.message}")
    dialog.accept()
    print("已接受弹窗")

def google_login_single(username: str, password: str, auth_url: str, headless: bool = False):
    """
    单个Google账号登录自动化

    参数:
        username: Google账号邮箱
        password: Google账号密码
        auth_url: 授权地址
        headless: 是否使用无头模式（默认False显示浏览器）
    """
    with sync_playwright() as p:
        # 1. 启动Chrome浏览器（无痕模式）
        browser = p.chromium.launch(
            headless=headless,
            args=["--start-maximized", "--incognito"]  # 无痕模式
        )

        # 2. 创建新的浏览器上下文和页面
        context = browser.new_context(viewport=None)
        page = context.new_page()

        # 3. 监听对话框事件
        page.on("dialog", handle_dialog)

        # 4. 访问授权地址
        print(f"访问授权地址: {auth_url}")
        page.goto(auth_url, timeout=30000)

        # 5. 输入用户名
        print(f"[{username}] 正在输入用户名...")
        username_input = page.wait_for_selector("input[type='email']", timeout=10000)
        username_input.fill(username)

        # 6. 点击"下一步"
        print(f"[{username}] 点击下一步...")
        next_button = page.wait_for_selector("#identifierNext", timeout=5000)
        next_button.click()

        # 7. 输入密码
        print(f"[{username}] 正在输入密码...")
        password_input = page.wait_for_selector("input[type='password']", timeout=10000)
        password_input.fill(password)

        # 8. 点击"下一步"完成登录
        print(f"[{username}] 点击登录...")
        login_button = page.wait_for_selector("#passwordNext", timeout=5000)
        login_button.click()

        # 9. 等待登录完成
        print(f"[{username}] 等待登录完成...")
        time.sleep(5)

        print(f"[{username}] 登录流程已完成！")

        # 10. 关闭浏览器
        browser.close()

        return True

def run_google_login_task(task_id: int):
    """
    执行Google登录任务

    参数:
        task_id: 任务ID
    """
    db = SessionLocal()
    try:
        # 获取任务信息
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            print(f"任务ID {task_id} 不存在")
            return

        # 获取账号信息（从Redis）
        # 根据account_type从Redis中获取对应类型的账号
        account = account_redis_service.get_account(task.account_type)
        if not account:
            print(f"账号类型 {task.account_type} 不存在")
            task.status = "error"
            task.error_message = f"账号类型 {task.account_type} 不存在"
            task.completed_at = datetime.now()
            db.commit()
            return
        

        # 获取授权地址
        auth_url = db.query(AuthUrl).filter(AuthUrl.id == task.auth_url_id).first()
        if not auth_url:
            raise Exception(f"授权地址ID {task.auth_url_id} 不存在")

        # 执行登录
        try:
            # 调用登录函数
            result = google_login_single(
                username=account["username"],
                password=account["password"],
                auth_url=auth_url.url,
                headless=False  # 可以从配置中读取
            )

            # 更新任务状态为完成
            task.status = "completed"
            task.result = "登录成功"
            task.completed_at = datetime.now()
            db.commit()

        except Exception as e:
            # 更新任务状态为错误
            task.status = "error"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()
            raise e

    except Exception as e:
        print(f"执行任务失败: {str(e)}")
        # 如果任务存在，更新状态
        if 'task' in locals():
            task.status = "error"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()
    finally:
        db.close()
