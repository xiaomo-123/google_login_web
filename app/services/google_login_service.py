from playwright.async_api import async_playwright, Dialog
import asyncio
import aiohttp
from datetime import datetime
from app.database import SessionLocal
from app.models.task import Task
from app.models.auth_url import AuthUrl
from app.models.proxy import Proxy
from app.redis_client import account_redis_service
from app.websocket_server import log_publisher

async def handle_dialog(dialog: Dialog, task_id: int = None):
    """监听并处理浏览器弹出的对话框（比如"要打开Python吗？"）"""
    message = f"检测到弹窗：{dialog.message}"
    print(message)
    if task_id:
        log_publisher.publish_log(task_id, "info", message)
    # 点击"打开Python"按钮（对应dialog.accept()）
    # 若要点击"取消"，则替换为 dialog.dismiss()
    await dialog.accept()
    message = "已点击「打开Python」"
    print(message)
    if task_id:
        log_publisher.publish_log(task_id, "info", message)

async def get_auth_url(auth_url: str, description: str, task_id: int = None):
    """
    请求授权地址

    参数:
        auth_url: 授权地址
        description: 描述参数
        task_id: 任务ID（可选，用于发送日志）

    返回:
        auth_url: 授权URL
    """
    try:
        message = f"正在请求授权地址: {auth_url}"
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        async with aiohttp.ClientSession() as session:
            # 发送POST请求
            async with session.post(
                auth_url,
                json={"idp": description},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                # 检查响应状态
                response.raise_for_status()

                # 解析响应
                result = await response.json()

                message = f"成功获取授权地址: {result.get('auth_url')}"
                print(message)
                if task_id:
                    log_publisher.publish_log(task_id, "info", message)

                # 返回auth_url
                return result.get("auth_url")

    except aiohttp.ClientError as e:
        message = f"请求授权地址失败: {str(e)}"
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "error", message)
        raise Exception(f"请求授权地址失败: {str(e)}")
    except Exception as e:
        message = f"解析授权地址响应失败: {str(e)}"
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "error", message)
        raise Exception(f"解析授权地址响应失败: {str(e)}")

async def google_login_single(username: str, password: str, auth_url: str, headless: bool = False, task_id: int = None):
    """
    单个Google账号登录自动化

    参数:
        username: Google账号邮箱
        password: Google账号密码
        auth_url: 授权地址
        headless: 是否使用无头模式（默认False显示浏览器）
        task_id: 任务ID（可选，用于发送日志）
    """
    async with async_playwright() as p:
        # 1. 启动Chrome浏览器（无痕模式）
        message = "正在启动Chrome浏览器..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        browser = await p.chromium.launch(
            headless=headless,
            args=["--start-maximized", "--incognito"]  # 无痕模式
        )

        # 2. 创建新的浏览器上下文和页面
        context = await browser.new_context(viewport=None)
        page = await context.new_page()

        # 3. 监听对话框事件
        page.on("dialog", lambda dialog: handle_dialog(dialog, task_id))

        # 4. 访问授权地址
        message = f"正在访问授权地址: {auth_url}"
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)
        await page.goto(auth_url, timeout=30000)

        # 5. 输入用户名
        message = f"[{username}] 正在输入用户名..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)
        username_input = await page.wait_for_selector("input[type='email']", timeout=10000)
        await username_input.fill(username)

        # 6. 点击"下一步"
        message = f"[{username}] 正在点击下一步..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)
        next_button = await page.wait_for_selector("#identifierNext", timeout=5000)
        await next_button.click()

        # 7. 输入密码
        message = f"[{username}] 正在输入密码..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)
        password_input = await page.wait_for_selector("input[type='password']", timeout=10000)
        await password_input.fill(password)

        # 8. 点击"下一步"完成登录
        message = f"[{username}] 正在点击登录按钮..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)
        login_button = await page.wait_for_selector("#passwordNext", timeout=5000)
        await login_button.click()

        # 9. 等待登录完成
        message = f"[{username}] 正在等待登录完成..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)
        await asyncio.sleep(5)

        # 10. 登录成功后等待10秒
        message = f"[{username}] 登录成功，等待10秒..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)
        await asyncio.sleep(10)

        message = f"[{username}] 登录流程已完成！"
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        # 11. 关闭浏览器
        message = "正在关闭浏览器..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)
        await browser.close()

        return True

