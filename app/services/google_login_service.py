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
    """监听并处理浏览器弹出的对话框（如"要打开Python吗？"等回调对话框）

    Args:
        dialog: Playwright Dialog对象
        task_id: 任务ID（可选，用于发送日志）
    """
    message = f"检测到对话框: {dialog.message}"
    print(message)
    if task_id:
        log_publisher.publish_log(task_id, "info", message)

    # 获取对话框类型
    dialog_type = dialog.type
    message = f"对话框类型: {dialog_type}"
    print(message)
    if task_id:
        log_publisher.publish_log(task_id, "info", message)

    # 立即接受对话框，避免阻塞页面
    try:
        await dialog.accept()
        message = "已点击对话框确认按钮"
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)
    except Exception as e:
        message = f"处理对话框时出错: {str(e)}"
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "error", message)

async def monitor_setsid_and_handle_popups(page, context, username: str, task_id: int = None):
    """监听SetSID页面并处理弹出窗口和对话框

    Args:
        page: Playwright Page对象
        context: Playwright BrowserContext对象
        username: 用户名
        task_id: 任务ID（可选，用于发送日志）
    """
    message = f"[{username}] 启动SetSID页面监听器..."
    print(message)
    if task_id:
        log_publisher.publish_log(task_id, "info", message)

    # 标记弹出窗口是否被处理
    popup_handled = False

    # 监听弹出窗口事件
    async def handle_popup(popup):
        nonlocal popup_handled
        message = f"[{username}] 检测到弹出窗口: {popup.url}"
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        try:
            await popup.wait_for_load_state("networkidle", timeout=5000)
            popup_title = await popup.title()
            message = f"[{username}] 弹出窗口标题: {popup_title}"
            print(message)
            if task_id:
                log_publisher.publish_log(task_id, "info", message)

            await popup.close()
            message = f"[{username}] 已关闭弹出窗口"
            print(message)
            if task_id:
                log_publisher.publish_log(task_id, "info", message)

            popup_handled = True
        except Exception as popup_e:
            message = f"[{username}] 处理弹出窗口时出错: {str(popup_e)}"
            print(message)
            if task_id:
                log_publisher.publish_log(task_id, "error", message)

    # 注册弹出窗口监听器
    page.on("popup", handle_popup)

    # 监听URL变化，检测是否到达SetSID页面
    async def check_url():
        while True:
            try:
                current_url = page.url
                if "SetSID" in current_url:
                    message = f"[{username}] 检测到SetSID页面"
                    print(message)
                    if task_id:
                        log_publisher.publish_log(task_id, "info", message)

                    # 等待一段时间，让弹出窗口有时间出现
                    await asyncio.sleep(2)

                    # 检查是否有弹出窗口或对话框
                    try:
                        # 先检查是否有对话框（优先处理）
                        dialog_handled = False
                        async def wait_for_dialog():
                            await page.wait_for_event("dialog", timeout=2000)
                            return "dialog"

                        try:
                            await asyncio.wait_for(wait_for_dialog(), timeout=2)
                            dialog_handled = True
                            message = f"[{username}] 对话框已处理"
                            print(message)
                            if task_id:
                                log_publisher.publish_log(task_id, "info", message)
                        except asyncio.TimeoutError:
                            pass

                        # 如果没有对话框，检查是否有弹出窗口
                        if not dialog_handled:
                            # 直接检查所有打开的页面，不使用wait_for_event
                            all_pages = context.pages
                            message = f"[{username}] 当前打开的页面数量: {len(all_pages)}"
                            print(message)
                            if task_id:
                                log_publisher.publish_log(task_id, "info", message)

                            # 如果有多个页面，尝试处理最后一个页面（弹出窗口）
                            if len(all_pages) > 1:
                                message = f"[{username}] 检测到弹出窗口"
                                print(message)
                                if task_id:
                                    log_publisher.publish_log(task_id, "info", message)

                                popup_page = all_pages[-1]
                                message = f"[{username}] 弹出窗口URL: {popup_page.url}"
                                print(message)
                                if task_id:
                                    log_publisher.publish_log(task_id, "info", message)

                                # 尝试点击弹出窗口中的按钮
                                try:
                                    # 等待页面加载完成
                                    await popup_page.wait_for_load_state("networkidle", timeout=5000)

                                    # 尝试查找并点击"打开"或"允许"按钮
                                    button_selectors = [
                                        "text=打开Python",
                                        "text=打开",
                                        "text=允许",
                                        "text=Open",
                                        "text=Allow",
                                        "button:has-text('打开Python')",
                                        "button:has-text('打开')",
                                        "button:has-text('允许')",
                                        "button:has-text('Open')",
                                        "button:has-text('Allow')",
                                        "[role='button']:has-text('打开Python')",
                                        "[role='button']:has-text('打开')",
                                        "[role='button']:has-text('允许')",
                                        "[role='button']:has-text('Open')]",
                                        "[role='button']:has-text('Allow')]",
                                        "xpath=//*[contains(text(), '打开Python')]",
                                        "xpath=//*[contains(text(), '打开')]",
                                        "xpath=//*[contains(text(), '允许')]",
                                        "xpath=//*[contains(text(), 'Open')]",
                                        "xpath=//*[contains(text(), 'Allow')]"
                                    ]

                                    button_clicked = False
                                    for selector in button_selectors:
                                        try:
                                            button = await popup_page.wait_for_selector(selector, timeout=1000)
                                            if button:
                                                message = f"[{username}] 找到按钮（选择器: {selector}），正在点击..."
                                                print(message)
                                                if task_id:
                                                    log_publisher.publish_log(task_id, "info", message)

                                                # 使用JavaScript点击按钮
                                                await button.evaluate("el => el.click()")
                                                button_clicked = True

                                                message = f"[{username}] 按钮已点击"
                                                print(message)
                                                if task_id:
                                                    log_publisher.publish_log(task_id, "info", message)
                                                await asyncio.sleep(1)
                                                break
                                        except:
                                            continue

                                    # 如果没有找到按钮，直接关闭弹出窗口
                                    if not button_clicked:
                                        message = f"[{username}] 未找到按钮，关闭弹出窗口"
                                        print(message)
                                        if task_id:
                                            log_publisher.publish_log(task_id, "info", message)
                                        await popup_page.close()
                                except Exception as click_e:
                                    message = f"[{username}] 点击按钮时出错: {str(click_e)}"
                                    print(message)
                                    if task_id:
                                        log_publisher.publish_log(task_id, "error", message)
                                    # 出错时关闭弹出窗口
                                    try:
                                        await popup_page.close()
                                    except:
                                        pass

                                popup_handled = True
                            else:
                                message = f"[{username}] 未检测到弹出窗口"
                                print(message)
                                if task_id:
                                    log_publisher.publish_log(task_id, "info", message)
                    except Exception as e:
                        message = f"[{username}] 检查弹出窗口或对话框时出错: {str(e)}"
                        print(message)
                        if task_id:
                            log_publisher.publish_log(task_id, "warning", message)

                    # 检测完成后，停止监听
                    break
            except Exception as e:
                message = f"[{username}] 检查URL时出错: {str(e)}"
                print(message)
                if task_id:
                    log_publisher.publish_log(task_id, "warning", message)

            await asyncio.sleep(0.5)

    # 启动URL检查任务
    check_task = asyncio.create_task(check_url())

    return check_task

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

        # 3. 监听对话框事件（在页面创建后立即设置）
        async def dialog_handler(dialog):
            """对话框处理包装函数"""
            message = f"对话框监听器被触发: {dialog.message}"
            print(message)
            if task_id:
                log_publisher.publish_log(task_id, "info", message)
            # 直接调用对话框处理函数
            await handle_dialog(dialog, task_id)

        # 使用更可靠的方式注册对话框处理器
        page.on("dialog", dialog_handler)

        message = "对话框监听器已设置"
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        # 3.1 启动SetSID页面监听器
        setsid_monitor_task = await monitor_setsid_and_handle_popups(page, context, username, task_id)
        message = "SetSID页面监听器已启动"
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

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

        # 9. 等待可能出现的Continue按钮
        message = f"[{username}] 正在检查是否需要点击Continue按钮..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        try:
            # 减少等待时间，快速检查页面
            await asyncio.sleep(2)

            # 检查是否存在Continue按钮（使用最有效的选择器）
            continue_selectors = [
                "text=Continue",
                "xpath=//*[contains(text(), 'Continue')]",
                "[role='button']:has-text('Continue')",
                "button:has-text('Continue')",
                "div:has-text('Continue')"
            ]

            continue_clicked = False
            for selector in continue_selectors:
                try:
                    continue_button = await page.wait_for_selector(selector, timeout=1000)
                    if continue_button:
                        message = f"[{username}] 找到Continue按钮（选择器: {selector}），正在点击..."
                        print(message)
                        if task_id:
                            log_publisher.publish_log(task_id, "info", message)

                        # 使用JavaScript点击按钮，更可靠
                        await continue_button.evaluate("el => el.click()")
                        continue_clicked = True

                        # 点击后立即打印日志并跳出循环
                        message = f"[{username}] Continue按钮已点击，等待对话框..."
                        print(message)
                        if task_id:
                            log_publisher.publish_log(task_id, "info", message)
                        await asyncio.sleep(1)
                        break
                except:
                    continue

            if not continue_clicked:
                message = f"[{username}] 未找到Continue按钮，继续执行..."
                print(message)
                if task_id:
                    log_publisher.publish_log(task_id, "info", message)

        except Exception as e:
            message = f"[{username}] 检查Continue按钮时出错: {str(e)}"
            print(message)
            if task_id:
                log_publisher.publish_log(task_id, "warning", message)

        # 9.5 SetSID页面监听器已在后台运行，等待登录完成
        message = f"[{username}] SetSID页面监听器已在后台运行，等待登录完成..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        # 10. 等待登录完成
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

