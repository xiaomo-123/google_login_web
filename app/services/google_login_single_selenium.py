# -*- coding: utf-8 -*-
"""
Google 登录自动化 - 基于 Selenium 实现
参考 kiro_auto_login.py 的登录流程
"""
import asyncio
import time
import os
import subprocess
import psutil
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app.websocket_server import log_publisher

# 尝试导入对话框点击依赖
try:
    from pywinauto import Desktop
    DIALOG_CLICKER_AVAILABLE = True
except ImportError:
    DIALOG_CLICKER_AVAILABLE = False
    print("[WARN] pywinauto 未安装，对话框自动点击功能不可用")
    print("[WARN] 请运行: pip install pywinauto")

# ===== 对话框点击配置 =====
AUTO_CLICK_DIALOG = True  # 是否启用对话框自动点击
DIALOG_CHECK_INTERVAL = 0.5  # 检查间隔（秒）

# 对话框关键词
DIALOG_KEYWORDS = ["要打开", "URL:KIRO", "Protocol", "打开Python", "Open URL", "Launch"]
BUTTON_KEYWORDS = ["打开", "确定", "Open", "OK", "Launch", "Continue", "允许", "Allow", "是", "Yes"]
SKIP_KEYWORDS = ["取消", "Cancel", "拒绝", "Deny", "否", "No"]
# ========================


def click_dialog_for_port(port, worker_id=""):
    """点击对话框 - 使用 Desktop 扫描所有窗口"""
    if not DIALOG_CLICKER_AVAILABLE or not AUTO_CLICK_DIALOG:
        return False

    try:
        desktop = Desktop(backend="uia")
        windows = desktop.windows()

        for window in windows:
            try:
                window_title = window.window_text()
                if not window_title:
                    continue

                # 排除控制台和IDE窗口
                exclude_keywords = ['python.exe', 'cmd.exe', 'powershell', 'conhost', 'windsurf', 'vscode', 'pycharm']
                if any(kw.lower() in window_title.lower() for kw in exclude_keywords):
                    continue

                # 检查窗口标题是否包含对话框关键词
                is_target = False
                for keyword in DIALOG_KEYWORDS:
                    if keyword.lower() in window_title.lower():
                        is_target = True
                        break

                # 如果标题不匹配，扫描窗口内的文本元素
                if not is_target:
                    try:
                        texts = window.descendants(control_type="Text")
                        for text_elem in texts:
                            try:
                                text_content = text_elem.window_text()
                                if text_content:
                                    for keyword in DIALOG_KEYWORDS:
                                        if keyword.lower() in text_content.lower():
                                            is_target = True
                                            break
                                if is_target:
                                    break
                            except:
                                continue
                    except:
                        pass

                if not is_target:
                    continue

                print(f"[{worker_id}] 找到目标对话框: {window_title[:50]}")

                # 查找并点击按钮
                buttons = window.descendants(control_type="Button")
                for button in buttons:
                    try:
                        btn_text = button.window_text()

                        # 跳过取消按钮
                        if any(skip in btn_text for skip in SKIP_KEYWORDS):
                            continue

                        # 点击目标按钮
                        for btn_keyword in BUTTON_KEYWORDS:
                            if btn_keyword in btn_text:
                                print(f"[{worker_id}] 点击按钮: {btn_text}")
                                button.click()
                                return True
                    except:
                        continue

            except:
                continue

        return False
    except Exception as e:
        print(f"[{worker_id}] 对话框点击失败: {e}")
        return False


def start_dialog_monitor(port, duration, worker_id, stop_flag):
    """后台监控并点击对话框"""
    if not DIALOG_CLICKER_AVAILABLE or not AUTO_CLICK_DIALOG:
        return

    end_time = time.time() + duration
    while time.time() < end_time and not stop_flag.is_set():
        click_dialog_for_port(port, worker_id)
        time.sleep(DIALOG_CHECK_INTERVAL)


async def google_login_single(username: str, password: str, auth_url: str, headless: bool = False, task_id: int = None):
    """
    单个Google账号登录自动化 - 基于Selenium实现

    参数:
        username: Google账号邮箱
        password: Google账号密码
        auth_url: 授权地址
        headless: 是否使用无头模式（默认False显示浏览器）
        task_id: 任务ID（可选，用于发送日志）
    """
    message = "正在启动Chrome浏览器..."
    print(message)
    if task_id:
        log_publisher.publish_log(task_id, "info", message)

    # 计算窗口位置，使多个窗口横向有一定距离
    window_x = 100 + (task_id % 5) * 400  # 根据task_id计算横向位置，最多5个窗口
    window_y = 50 + (task_id // 5) * 100  # 根据task_id计算纵向位置

    # 使用唯一的调试端口
    debug_port = 9500 + (task_id % 100)
    user_data_dir = f"C:\\chrome_google_profile_{debug_port}"

    # 先尝试清理可能残留的 Chrome 进程
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline') or []
                if any(f'--remote-debugging-port={debug_port}' in arg for arg in cmdline):
                    proc.kill()
                    time.sleep(1)
            except:
                pass
    except:
        pass

    # Chrome路径
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if not os.path.exists(chrome_path):
        chrome_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

    # 启动Chrome进程
    cmd = [
        chrome_path,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={user_data_dir}",
        "--incognito",
        "--no-first-run",
        "--no-default-browser-check",
        "--autoplay-policy=no-user-gesture-required",
        "--disable-external-intent-requests=false",
        "--allow-running-insecure-content",
        "--disable-backgrounding-occluded-windows",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-web-security",
        "--ignore-certificate-errors",
        "--ignore-ssl-errors",
        "--ignore-certificate-errors-spki-list",
        "--disable-features=VizDisplayCompositor",
        f"--window-position={window_x},{window_y}",
        "--window-size=1920,1080"
    ]

    chrome_process = subprocess.Popen(cmd)
    time.sleep(3)

    driver = None
    dialog_thread = None
    dialog_stop_flag = None
    try:
        # 启动对话框监控线程
        dialog_stop_flag = threading.Event()
        if AUTO_CLICK_DIALOG and DIALOG_CLICKER_AVAILABLE:
            dialog_thread = threading.Thread(
                target=start_dialog_monitor,
                args=(debug_port, 60, f"Task-{task_id}", dialog_stop_flag),
                daemon=True
            )
            dialog_thread.start()
            message = f"对话框监控已启动 (端口 {debug_port})"
            print(message)
            if task_id:
                log_publisher.publish_log(task_id, "info", message)

        # 连接到Chrome
        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
        driver = webdriver.Chrome(options=options)

        message = f"Chrome浏览器已启动 (端口: {debug_port}, 位置: {window_x}, {window_y})"
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        # 访问授权地址
        message = f"正在访问授权地址: {auth_url}"
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)
        driver.get(auth_url)
        time.sleep(2)

        # 强制将浏览器窗口激活到前台
        try:
            driver.execute_cdp_cmd('Page.bringToFront', {})
        except:
            pass
        try:
            driver.execute_script("window.focus();")
        except:
            pass

        wait = WebDriverWait(driver, 60)

        # 填写邮箱
        message = f"[{username}] 正在输入用户名..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        email_input = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='email']"))
        )
        time.sleep(1)
        email_input.clear()
        for char in username:
            email_input.send_keys(char)
            time.sleep(0.08)
        time.sleep(1)

        # 点击下一步
        message = f"[{username}] 正在点击下一步..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        next_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "identifierNext"))
        )
        driver.execute_script("arguments[0].click();", next_btn)
        time.sleep(5)

        # 强制将浏览器窗口激活到前台
        try:
            driver.execute_cdp_cmd('Page.bringToFront', {})
        except:
            pass
        try:
            driver.execute_script("window.focus();")
        except:
            pass

        # 处理"我了解"按钮
        try:
            understand_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button//span[contains(text(), '我了解')] | //input[@value='我了解'] | //button//span[contains(text(), 'I understand')]")
                )
            )
            driver.execute_script("arguments[0].click();", understand_btn)
            time.sleep(3)
        except:
            pass

        # 填写密码
        message = f"[{username}] 正在输入密码..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        password_input = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']"))
        )
        time.sleep(1)
        try:
            password_input.click()
        except:
            pass

        password_input.clear()
        for char in password:
            password_input.send_keys(char)
            time.sleep(0.08)
        time.sleep(1)

        # 点击登录
        message = f"[{username}] 正在点击登录按钮..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        password_next = wait.until(
            EC.element_to_be_clickable((By.ID, "passwordNext"))
        )
        driver.execute_script("arguments[0].click();", password_next)
        time.sleep(5)

        # 强制将浏览器窗口激活到前台
        try:
            driver.execute_cdp_cmd('Page.bringToFront', {})
        except:
            pass
        try:
            driver.execute_script("window.focus();")
        except:
            pass

        # 处理确认页面
        try:
            confirm_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH,
                     "//span[contains(text(), 'Continue')]/ancestor::button | "
                     "//span[contains(text(), '继续')]/ancestor::button | "
                     "//button[@id='submit_approve_access']")
                )
            )
            driver.execute_script("arguments[0].click();", confirm_btn)
            time.sleep(3)
        except:
            pass

        # 处理 Allow 页面
        try:
            allow_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//span[contains(text(), 'Allow')]/ancestor::button | //button[@id='submit_approve_access']")
                )
            )
            driver.execute_script("arguments[0].click();", allow_btn)
            time.sleep(3)
        except:
            pass

        time.sleep(5)

        # 打印当前页面URL
        current_url = driver.current_url
        message = f"[{username}] 当前 URL: {current_url[:60]}..."
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        message = f"[{username}] 登录流程已完成！"
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "info", message)

        return True

    except Exception as e:
        message = f"[{username}] 登录失败: {e}"
        print(message)
        if task_id:
            log_publisher.publish_log(task_id, "error", message)
        return False
    finally:
        # 停止对话框监控
        if dialog_stop_flag:
            dialog_stop_flag.set()
        
        # 关闭浏览器
        try:
            if driver:
                driver.quit()
        except:
            pass
        try:
            if chrome_process:
                chrome_process.terminate()
                chrome_process.wait(timeout=5)
        except:
            pass
