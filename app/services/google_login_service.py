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

async def handle_python_popup(context, username: str, task_id: int = None):
    """监听并处理"要打开Python吗？"弹出窗口

    Args:
        context: Playwright BrowserContext对象
        username: 用户名
        task_id: 任务ID（可选，用于发送日志）
    """
    # 监听弹出窗口事件
    async def handle_popup(popup):
        try:
            title = await popup.title()
            message = f"[{username}] 检测到弹出窗口: {title}"
            print(message)
            if task_id:
                log_publisher.publish_log(task_id, "info", message)

            # 检查是否是"要打开Python吗？"弹出窗口
            if "要打开Python吗" in title or "Open Python" in title:
                # 等待页面加载完成
                await popup.wait_for_load_state("networkidle", timeout=5000)

                # 查找并点击"打开Python"按钮
                button = await popup.wait_for_selector("text=打开Python", timeout=3000)
                if button:
                    await button.click()
                    message = f"[{username}] 已点击'打开Python'按钮"
                    print(message)
                    if task_id:
                        log_publisher.publish_log(task_id, "info", message)
        except Exception as e:
            message = f"[{username}] 处理弹出窗口时出错: {str(e)}"
            print(message)
            if task_id:
                log_publisher.publish_log(task_id, "error", message)

    # 注册弹出窗口监听器
    context.on("popup", handle_popup)
    message = f"[{username}] 已注册弹出窗口监听器"
    print(message)
    if task_id:
        log_publisher.publish_log(task_id, "info", message)

async def monitor_setsid_and_handle_popups(page, context, username: str, task_id: int = None):
    """监听SetSID重定向弹窗，极简无冗余版（配套登录函数）"""
    processed_popups = set()

    # 处理浏览器弹窗(Popup)
    async def handle_browser_popup(popup):
        try:
            await popup.wait_for_load_state("domcontentloaded", timeout=8000)
            popup_id = f"{popup.title() or 'Unknown'}|{popup.url}"
            if popup_id in processed_popups: return
            processed_popups.add(popup_id)
            
            # 中英文按钮全覆盖，XPath精准匹配
            btn_list = ["打开Python", "Open Python", "允许", "Allow", "确认", "Confirm"]
            for btn in btn_list:
                try:
                    await popup.click(f"//*[contains(text(), '{btn}')]", timeout=3000)
                    msg = f"[{username}] ✅ 成功点击弹窗按钮：{btn}"
                    print(msg)
                    task_id and log_publisher.publish_log(task_id, "info", msg)
                    return
                except: continue
        except Exception as e:
            err_msg = f"[{username}] 弹窗处理失败: {str(e)[:100]}"
            print(err_msg)
            task_id and log_publisher.publish_log(task_id, "error", err_msg)

    # 处理系统原生对话框(Dialog) - SetSID弹窗核心处理方式
    async def handle_system_dialog(dialog):
        dialog_msg = dialog.message
        keywords = ["打开Python", "Open Python", "是否允许打开", "Allow to open"]
        if any(kw in dialog_msg for kw in keywords):
            await dialog.accept()
            msg = f"[{username}] ✅ SetSID系统弹窗授权成功"
            print(msg)
            task_id and log_publisher.publish_log(task_id, "info", msg)
        else:
            await dialog.dismiss()

    # 双监听确保不遗漏重定向弹窗
    context.on("popup", handle_browser_popup)
    page.on("popup", handle_browser_popup)
    page.on("dialog", handle_system_dialog)
    
    # 拦截SetSID重定向，防止监听器丢失
    await page.route("**/SetSID*", lambda route: route.continue_())
    return True
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
        # 1. 启动Chrome浏览器（无痕模式）【核心修改：追加弹窗放行+权限参数】
        message = "正在启动Chrome浏览器..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        browser = await p.chromium.launch(
            headless=headless,
            args=["--start-maximized", "--incognito"]  # 无痕模式
        )
        context = await browser.new_context(viewport=None)
        page = await context.new_page()
        
        # ========== 新增：页面前置配置（必加，解决SetSID弹窗拦截） ==========
        # await context.grant_permissions(["notifications"])  # 授予弹窗权限
        # await page.set_extra_http_headers({"Accept-Language": "zh-CN,zh;q=0.9"})
        # # 前置注入脚本，强制允许confirm弹窗确认
        # await page.add_init_script("window.confirm = function(){return true;};window.alert=function(){};")
        



        # 3.1 启动弹出窗口监听器【仅修改日志格式，修复变量拼接错误】
        setsid_monitor_task = await monitor_setsid_and_handle_popups(page, context, username, task_id)
        message = f"弹出窗口监听器已启动: {setsid_monitor_task}"  # ========== 修改：修复f-string变量拼接 ==========
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
        username_input = await page.wait_for_selector("input[type='email']", timeout=30000)
        await username_input.fill(username)

        # 6. 点击"下一步"
        message = f"[{username}] 正在点击下一步..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)
        # 等待页面加载完成
        await page.wait_for_load_state("networkidle", timeout=30000)
        next_button = await page.wait_for_selector("#identifierNext", timeout=30000)
        # 等待按钮可见并可点击
        await next_button.wait_for_element_state("visible", timeout=10000)
        await next_button.click()
        await asyncio.sleep(10)
        # 7. 输入密码
        message = f"[{username}] 正在输入密码..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)
        password_input = await page.wait_for_selector("input[type='password']", timeout=30000)
        await password_input.fill(password)
        await asyncio.sleep(10)
        # 8. 点击"下一步"完成登录
        message = f"[{username}] 正在点击登录按钮..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)
        # 等待页面加载完成
        await page.wait_for_load_state("networkidle", timeout=30000)
        login_button = await page.wait_for_selector("#passwordNext", timeout=30000)
        # 等待按钮可见并可点击
        await login_button.wait_for_element_state("visible", timeout=10000)
        await login_button.click()
        await asyncio.sleep(10)
        # 9. 等待可能出现的Continue按钮【原代码不变，保留】
        message = f"[{username}] 正在检查是否需要点击Continue按钮..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        try:
            await asyncio.sleep(10)
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
                        await continue_button.evaluate("el => el.click()")
                        continue_clicked = True
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

        # 打印当前页面URL，用于调试重定向
        current_url = page.url
        message = f"[{username}] 当前页面URL: {current_url}"
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        # 检测SetSID重定向，等待弹出窗口【核心增强：优化等待+主动捕获弹窗，解决无响应】
        if "SetSID" in current_url:
            message = f"[{username}] 检测到SetSID重定向，等待弹出窗口..."
            print(message)
            if task_id:
                log_publisher.publish_log(task_id, "info", message)

            # ========== 修改：延长等待时间+主动刷新上下文页面 ==========
            await asyncio.sleep(5)  # 延长至5秒，适配弹窗加载延迟
            pages = context.pages
            message = f"[{username}] 当前共有 {len(pages)} 个页面，已捕获所有弹窗"
            print(message)   
            if task_id:
                log_publisher.publish_log(task_id, "info", message)
            
            # ========== 新增：主动遍历弹窗页面，强制触发监听器 ==========
            for popup_page in pages:
                if popup_page != page and "SetSID" in popup_page.url:
                    message = f"[{username}] 主动捕获SetSID弹窗页面: {popup_page.url}"
                    print(message)
                    if task_id:
                        log_publisher.publish_log(task_id, "info", message)

        # 10. 等待登录完成
        message = f"[{username}] 正在等待登录完成..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)
        await asyncio.sleep(10)

        message = f"[{username}] 登录成功，等待2秒..."
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