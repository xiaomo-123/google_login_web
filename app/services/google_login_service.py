from playwright.async_api import async_playwright, Dialog
import asyncio
import aiohttp
from datetime import datetime
from app.database import SessionLocal
from app.models.task import Task
from app.models.auth_url import AuthUrl
from app.models.proxy import Proxy
from app.redis_client import account_redis_service

async def handle_dialog(dialog: Dialog):
    """监听并处理浏览器弹出的对话框（比如"要打开Python吗？"）"""
    print(f"检测到弹窗：{dialog.message}")
    # 点击"打开Python"按钮（对应dialog.accept()）
    # 若要点击"取消"，则替换为 dialog.dismiss()
    await dialog.accept()
    print("已点击「打开Python」")

async def get_auth_url(auth_url: str, description: str):
    """
    请求授权地址

    参数:
        auth_url: 授权地址
        description: 描述参数

    返回:
        auth_url: 授权URL
    """
    try:
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

                # 返回auth_url
                return result.get("auth_url")

    except aiohttp.ClientError as e:
        print(f"请求授权地址失败: {str(e)}")
        raise Exception(f"请求授权地址失败: {str(e)}")
    except Exception as e:
        print(f"解析授权地址响应失败: {str(e)}")
        raise Exception(f"解析授权地址响应失败: {str(e)}")

async def google_login_single(username: str, password: str, auth_url: str, headless: bool = False):
    """
    单个Google账号登录自动化

    参数:
        username: Google账号邮箱
        password: Google账号密码
        auth_url: 授权地址
        headless: 是否使用无头模式（默认False显示浏览器）
    """
    async with async_playwright() as p:
        # 1. 启动Chrome浏览器（无痕模式）
        browser = await p.chromium.launch(
            headless=headless,
            args=["--start-maximized", "--incognito"]  # 无痕模式
        )

        # 2. 创建新的浏览器上下文和页面
        context = await browser.new_context(viewport=None)
        page = await context.new_page()

        # 3. 监听对话框事件
        page.on("dialog", handle_dialog)

        # 4. 访问授权地址
        print(f"访问授权地址: {auth_url}")
        await page.goto(auth_url, timeout=30000)

        # 5. 输入用户名
        print(f"[{username}] 正在输入用户名...")
        username_input = await page.wait_for_selector("input[type='email']", timeout=10000)
        await username_input.fill(username)

        # 6. 点击"下一步"
        print(f"[{username}] 点击下一步...")
        next_button = await page.wait_for_selector("#identifierNext", timeout=5000)
        await next_button.click()

        # 7. 输入密码
        print(f"[{username}] 正在输入密码...")
        password_input = await page.wait_for_selector("input[type='password']", timeout=10000)
        await password_input.fill(password)

        # 8. 点击"下一步"完成登录
        print(f"[{username}] 点击登录...")
        login_button = await page.wait_for_selector("#passwordNext", timeout=5000)
        await login_button.click()

        # 9. 等待登录完成
        print(f"[{username}] 等待登录完成...")
        await asyncio.sleep(5)

        # 10. 登录成功后等待10秒
        print(f"[{username}] 登录成功，等待10秒...")
        await asyncio.sleep(10)

        print(f"[{username}] 登录流程已完成！")

        # 11. 关闭浏览器
        await browser.close()

        return True

async def run_google_login_task(task_id: int):
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

        # 获取并打印代理信息
        proxy_info = None
        if task.proxy_id:
            proxy = db.query(Proxy).filter(Proxy.id == task.proxy_id and proxy.status == 1).first()
            if proxy:
                proxy_info = f"{proxy.proxy_type}://{proxy.username}:{proxy.password}@{proxy.url}:{proxy.port}" if proxy.username else f"{proxy.proxy_type}://{proxy.url}:{proxy.port}"
                print(f"\n代理信息:")
                print(f"  ID: {proxy.id}")
                print(f"  地址: {proxy_info}")
                print(f"  类型: {proxy.proxy_type}")
                print(f"  状态: {'正常' if proxy.status == 1 else '禁用'}")
            else:
                print(f"\n代理ID {task.proxy_id} 不存在")
        else:
            print(f"\n未配置代理")

        # 获取账号信息（从Redis）
        print(f"\n账号信息:")
        print(f"  爬虫类型: {task.account_type}")

        # 获取所有账号
        accounts = account_redis_service.get_all_accounts(get_all=True)
        total_count = len(accounts)

        print(f"  账号总数: {total_count}")

        # 逐条打印账号信息
        # print(f"\n账号列表:")
        # for idx, account in enumerate(all_accounts, 1):
        #     print(f"  [{idx}] ID: {account['id']}, 用户名: {account['username']}, 密码: {account['password']}, 状态: {'正常' if account['status'] == 1 else '禁用'}")


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
        account = accounts[0]

        # 执行登录
        try:
            if task.account_type == 1:
                # 请求授权地址
                print(f"\n正在请求授权地址...")
                google_login_url = await get_auth_url(
                    auth_url=auth_url_obj.url,
                    description=auth_url_obj.description
                )
                print(f"获取到的授权地址: {google_login_url}")

            # 调用登录函数
            #     result = await google_login_single(
            #     username=account["username"],
            #     password=account["password"],
            #     auth_url=google_login_url,
            #     headless=False  # 可以从配置中读取
            # )

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
