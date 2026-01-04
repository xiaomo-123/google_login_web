# -*- coding: utf-8 -*-
"""
Kiro Polaris Auth 自动登录脚本 - 多进程多线程版
- 启动 polaris auth 服务
- 获取 Google OAuth 授权 URL
- 自动完成 Google 登录
- 支持多进程多线程并发
- 自动点击 Windows 对话框
"""
import multiprocessing
from multiprocessing import Process, Manager
import threading
import subprocess
import time
import os
import sys
from datetime import datetime
from filelock import FileLock
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 尝试导入对话框点击依赖
try:
    from pywinauto import Desktop
    DIALOG_CLICKER_AVAILABLE = True
except ImportError:
    DIALOG_CLICKER_AVAILABLE = False
    print("[WARN] pywinauto 未安装，对话框自动点击功能不可用")
    print("[WARN] 请运行: pip install pywinauto")

# ===== 配置 =====
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
POLARIS_PORT = 5433  # Polaris Auth 服务端口
POLARIS_API = f"http://127.0.0.1:{POLARIS_PORT}"

# 代理配置 (留空则不使用代理)
PROXY_URL = ""  # 例如: "http://209.141.44.111:25565"

# 进程和线程配置
NUM_PROCESSES = 1        # 启动几个进程
THREADS_PER_PROCESS = 1  # 每个进程几个线程（浏览器）
BASE_PORT = 9500        # Chrome 调试端口起始

# 账号文件
EMAILS_FILE = "emails.txt"

# 日志文件
LOG_SUCCESS = "log_success.txt"
LOG_FAIL = "log_fail.txt"
USED_ACCOUNTS_FILE = "used_accounts.txt"
FAILED_ACCOUNTS_FILE = "failed_accounts.txt"

# 锁文件
LOCK_SUCCESS = "log_success.txt.lock"
LOCK_FAIL = "log_fail.txt.lock"
LOCK_USED = "used_accounts.txt.lock"

# 对话框自动点击配置
AUTO_CLICK_DIALOG = True  # 是否启用对话框自动点击
DIALOG_CHECK_INTERVAL = 0.5  # 检查间隔（秒）
# ================


# ===== 对话框点击功能 =====
# 对话框关键词
DIALOG_KEYWORDS = ["要打开", "URL:KIRO", "Protocol", "打开Python", "Open URL", "Launch"]
BUTTON_KEYWORDS = ["打开", "确定", "Open", "OK", "Launch", "Continue", "允许", "Allow", "是", "Yes"]
SKIP_KEYWORDS = ["取消", "Cancel", "拒绝", "Deny", "否", "No"]


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
# ================


def safe_log_to_file(file_path, lock_path, content):
    """带文件锁的日志写入"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        lock = FileLock(lock_path, timeout=30)
        with lock:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {content}\n")
                f.flush()
                os.fsync(f.fileno())
        return True
    except Exception as e:
        print(f"[ERROR] 写入日志失败: {file_path}, {e}")
    return False


def safe_mark_used(email):
    """带文件锁标记账号已使用"""
    try:
        lock = FileLock(LOCK_USED, timeout=30)
        with lock:
            with open(USED_ACCOUNTS_FILE, "a", encoding="utf-8") as f:
                f.write(email + "\n")
                f.flush()
                os.fsync(f.fileno())
        return True
    except Exception as e:
        print(f"[ERROR] 标记已使用失败: {email}, {e}")
    return False


def load_used_accounts():
    """加载已使用的账号"""
    used = set()
    try:
        lock = FileLock(LOCK_USED, timeout=30)
        with lock:
            if os.path.exists(USED_ACCOUNTS_FILE):
                with open(USED_ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            used.add(line)
    except Exception as e:
        print(f"[ERROR] 加载已使用账号失败: {e}")
    return used


def load_failed_accounts():
    """加载失败的账号"""
    failed = set()
    try:
        if os.path.exists(FAILED_ACCOUNTS_FILE):
            with open(FAILED_ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if "----" in line:
                        email = line.split("----", 1)[0]
                    elif "|" in line:
                        email = line.split("|", 1)[0]
                    else:
                        email = line
                    if email:
                        failed.add(email)
    except Exception as e:
        print(f"[ERROR] 加载失败账号失败: {e}")
    return failed


def load_accounts(file_path):
    """读取账号，排除已使用和已失败的"""
    used_accounts = load_used_accounts()
    failed_accounts = load_failed_accounts()
    accounts = []
    
    if not os.path.exists(file_path):
        print(f"[ERROR] 文件不存在: {file_path}")
        return accounts
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            email = None
            password = None
            
            if "----" in line:
                parts = line.split("----", 1)
                if len(parts) == 2:
                    email = parts[0].strip()
                    password = parts[1].strip()
            elif "|" in line:
                parts = line.split("|", 1)
                if len(parts) == 2:
                    email = parts[0].strip()
                    password = parts[1].strip()
            
            if email and password:
                if email not in used_accounts and email not in failed_accounts:
                    accounts.append({"email": email, "password": password})
    
    print(f"[INFO] 读取了 {len(accounts)} 个未使用账号（已使用: {len(used_accounts)}，已失败: {len(failed_accounts)}）")
    return accounts


def get_auth_url():
    """从 Polaris Auth 获取 Google 授权 URL，返回 (auth_url, state)"""
    try:
        resp = requests.post(
            f"{POLARIS_API}/generate-auth-url",
            json={"idp": "Google"},
            timeout=10,
            proxies={"http": None, "https": None}
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("auth_url"), data.get("state")
    except Exception as e:
        print(f"[ERROR] 获取授权 URL 失败: {e}")
    return None, None


def check_token_received(state, max_wait=30):
    """检查特定 state 的 token 是否成功获取并上传（多进程安全）"""
    for i in range(max_wait):
        try:
            # 使用新的 /check-state/{state} API，只检查特定 state
            resp = requests.get(
                f"{POLARIS_API}/check-state/{state}",
                timeout=5,
                proxies={"http": None, "https": None}
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("found") and data.get("uploaded"):
                    print(f"[INFO] State {state[:20]}... 验证成功")
                    return True
                # 如果 state 不存在或已过期，提前退出
                error = data.get("error", "")
                if "不存在" in error or "过期" in error:
                    print(f"[WARN] State 检查失败: {error}")
                    return False
        except Exception as e:
            pass
        time.sleep(1)
    return False


def start_chrome(port):
    """启动 Chrome 浏览器"""
    user_data_dir = f"C:\\chrome_kiro_profile_{port}"
    
    # 先尝试清理可能残留的 Chrome 进程
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline') or []
                if any(f'--remote-debugging-port={port}' in arg for arg in cmdline):
                    proc.kill()
                    time.sleep(1)
            except:
                pass
    except:
        pass
    
    cmd = [
        CHROME_PATH,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--incognito",
        "--no-first-run",
        "--no-default-browser-check",
        "--autoplay-policy=no-user-gesture-required",
        "--disable-external-intent-requests=false",
        "--allow-running-insecure-content",
        "--disable-features=ExternalProtocolDialog",  # 禁用外部协议确认对话框
        "--disable-backgrounding-occluded-windows",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-gpu",
        "--no-sandbox",
    ]
    if PROXY_URL:
        cmd.append(f"--proxy-server={PROXY_URL}")
    return subprocess.Popen(cmd)


def connect_to_chrome(port, max_retries=5):
    """连接到 Chrome，带重试"""
    for i in range(max_retries):
        try:
            options = Options()
            options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
            driver = webdriver.Chrome(options=options)
            return driver
        except Exception as e:
            if i < max_retries - 1:
                time.sleep(2)
            else:
                raise e
    return None


def close_chrome(driver, chrome_process):
    """关闭浏览器"""
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


def force_window_to_front(driver):
    """强制将浏览器窗口激活到前台"""
    try:
        driver.execute_cdp_cmd('Page.bringToFront', {})
    except:
        pass
    try:
        driver.execute_script("window.focus();")
    except:
        pass


def auto_login(driver, email, password, worker_id, port=None, state=None):
    """自动填写账号密码并登录"""
    wait = WebDriverWait(driver, 60)
    
    # 启动对话框监控线程
    dialog_stop_flag = threading.Event()
    dialog_thread = None
    if AUTO_CLICK_DIALOG and DIALOG_CLICKER_AVAILABLE and port:
        dialog_thread = threading.Thread(
            target=start_dialog_monitor,
            args=(port, 60, worker_id, dialog_stop_flag),
            daemon=True
        )
        dialog_thread.start()
        print(f"[{worker_id}] 对话框监控已启动 (端口 {port})")
    
    try:
        time.sleep(3)
        
        # 填写邮箱
        email_input = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='email']"))
        )
        time.sleep(1)
        email_input.clear()
        for char in email:
            email_input.send_keys(char)
            time.sleep(0.08)
        time.sleep(1)
        
        # 点击下一步
        next_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "identifierNext"))
        )
        driver.execute_script("arguments[0].click();", next_btn)
        time.sleep(5)
        
        force_window_to_front(driver)

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
        password_next = wait.until(
            EC.element_to_be_clickable((By.ID, "passwordNext"))
        )
        driver.execute_script("arguments[0].click();", password_next)
        time.sleep(5)
        
        force_window_to_front(driver)
        
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
        except:
            pass

        time.sleep(5)
        
        # kiro:// 回调会被 Windows 处理，等待并检查是否成功获取 token
        current_url = driver.current_url
        print(f"[{worker_id}] 当前 URL: {current_url[:60]}...")
        
        # 通过 API 检查是否成功获取了 token
        print(f"[{worker_id}] 等待 token 回调...")
        success = check_token_received(state, max_wait=30)
        
        if success:
            print(f"[{worker_id}] Token 获取并上传成功!")
        else:
            print(f"[{worker_id}] Token 获取超时")
        
        return success
        
    except Exception as e:
        print(f"[{worker_id}] 登录失败: {e}")
        return False
    finally:
        # 停止对话框监控
        if dialog_thread:
            dialog_stop_flag.set()


def process_account(driver, account, worker_id, port=None):
    """处理单个账号"""
    email = account["email"]
    password = account["password"]
    
    auth_url, state = get_auth_url()
    if not auth_url:
        print(f"[{worker_id}] 无法获取授权 URL")
        return False
    
    print(f"[{worker_id}] 获取到授权 URL (state={state[:20]}...)")
    driver.get(auth_url)
    time.sleep(2)
    force_window_to_front(driver)
    
    return auto_login(driver, email, password, worker_id, port, state)


def worker_thread(port, account_queue, status_dict, process_id, thread_id, stop_event):
    """工作线程"""
    worker_id = f"P{process_id}-T{thread_id}"
    status_dict[worker_id] = "启动中"
    
    while not stop_event.is_set():
        try:
            account = account_queue.get(timeout=2)
        except:
            if account_queue.empty():
                status_dict[worker_id] = "完成-队列空"
                break
            continue
        
        email = account["email"]
        status_dict[worker_id] = f"启动浏览器: {email[:15]}..."
        
        driver = None
        chrome_process = None
        
        try:
            chrome_process = start_chrome(port)
            time.sleep(3)
            
            options = Options()
            options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
            driver = webdriver.Chrome(options=options)
            
            driver.get("about:blank")
            time.sleep(1)
            
            status_dict[worker_id] = f"处理: {email[:20]}..."
            success = process_account(driver, account, worker_id, port)
            
            if success:
                safe_log_to_file(LOG_SUCCESS, LOCK_SUCCESS, f"{email}----{account['password']}")
                safe_mark_used(email)
                status_dict[worker_id] = f"成功: {email[:15]}..."
                print(f"[OK] {worker_id} 成功: {email}")
            else:
                safe_log_to_file(LOG_FAIL, LOCK_FAIL, f"{email}----{account['password']}")
                status_dict[worker_id] = f"失败: {email[:15]}..."
                
        except Exception as e:
            safe_log_to_file(LOG_FAIL, LOCK_FAIL, f"{email}----{account['password']} (错误: {e})")
            status_dict[worker_id] = f"错误: {str(e)[:20]}"
        finally:
            close_chrome(driver, chrome_process)
            time.sleep(2)
    
    status_dict[worker_id] = "已退出"


def worker_thread_wrapper(delay, *args):
    """线程包装器：先等待延迟"""
    if delay > 0:
        time.sleep(delay)
    worker_thread(*args)


def worker_process(process_id, account_queue, status_dict, stop_event):
    """工作进程：启动多个线程"""
    threads = []
    
    for thread_id in range(THREADS_PER_PROCESS):
        port = BASE_PORT + (process_id * THREADS_PER_PROCESS) + thread_id
        delay = (thread_id * NUM_PROCESSES + process_id) * 3
        
        t = threading.Thread(
            target=worker_thread_wrapper,
            args=(delay, port, account_queue, status_dict, process_id, thread_id, stop_event),
            daemon=True
        )
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join()


def monitor_status(status_dict, account_queue, stop_event, total_accounts):
    """监控线程"""
    start_time = time.time()
    
    while not stop_event.is_set():
        os.system('cls' if os.name == 'nt' else 'clear')
        
        current_queue = account_queue.qsize()
        elapsed = int(time.time() - start_time)
        
        success_count = 0
        fail_count = 0
        try:
            if os.path.exists(LOG_SUCCESS):
                with open(LOG_SUCCESS, 'r', encoding='utf-8') as f:
                    success_count = sum(1 for _ in f)
            if os.path.exists(LOG_FAIL):
                with open(LOG_FAIL, 'r', encoding='utf-8') as f:
                    fail_count = sum(1 for _ in f)
        except:
            pass
        
        print("=" * 60)
        print(f"  Kiro Polaris Auth 自动登录  {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 60)
        print(f"  总账号: {total_accounts} | 队列中: {current_queue}")
        print(f"  成功: {success_count} | 失败: {fail_count}")
        print(f"  耗时: {elapsed}s")
        print("-" * 60)
        
        for process_id in range(NUM_PROCESSES):
            print(f"\n  [进程 {process_id}]")
            for thread_id in range(THREADS_PER_PROCESS):
                worker_id = f"P{process_id}-T{thread_id}"
                status = status_dict.get(worker_id, "等待启动")
                print(f"    线程 {thread_id}: {status}")
        
        print("\n" + "-" * 60)
        print("  按 Ctrl+C 停止")
        print("=" * 60)
        
        time.sleep(2)


def start_polaris_service():
    """启动 Polaris Auth 服务"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    polaris_dir = os.path.join(script_dir, "polaris_auth_python")
    bat_path = os.path.join(polaris_dir, "py.bat")
    
    if not os.path.exists(bat_path):
        print(f"[WARN] py.bat 不存在: {bat_path}")
        return None
    
    print(f"[INFO] 启动 Polaris Auth 服务...")
    process = subprocess.Popen(
        f'start "Polaris Auth" cmd /c "{bat_path}"',
        shell=True,
        cwd=polaris_dir
    )
    return process


def wait_for_service(timeout=30):
    """等待服务启动"""
    print(f"[INFO] 等待服务启动 (最多 {timeout} 秒)...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            resp = requests.get(f"{POLARIS_API}/docs", timeout=2, proxies={"http": None, "https": None})
            if resp.status_code == 200:
                print("[INFO] 服务已启动")
                return True
        except:
            pass
        time.sleep(1)
    
    print("[ERROR] 服务启动超时")
    return False


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    emails_path = os.path.join(script_dir, EMAILS_FILE)
    accounts = load_accounts(emails_path)
    
    if not accounts:
        print("[ERROR] 没有可用账号，退出")
        return
    
    # 启动 Polaris Auth 服务
    start_polaris_service()
    if not wait_for_service():
        print("[ERROR] 服务启动失败，退出")
        return
    
    # 创建共享资源
    manager = Manager()
    account_queue = manager.Queue()
    status_dict = manager.dict()
    stop_event = manager.Event()
    
    for acc in accounts:
        account_queue.put(acc)
    
    print(f"[INFO] 共 {len(accounts)} 个账号")
    print(f"[INFO] 启动 {NUM_PROCESSES} 个进程，每进程 {THREADS_PER_PROCESS} 个线程")
    print(f"[INFO] 总计 {NUM_PROCESSES * THREADS_PER_PROCESS} 个并发浏览器")
    time.sleep(2)
    
    # 启动监控线程
    monitor_thread = threading.Thread(
        target=monitor_status,
        args=(status_dict, account_queue, stop_event, len(accounts)),
        daemon=True
    )
    monitor_thread.start()
    
    # 启动工作进程
    processes = []
    for process_id in range(NUM_PROCESSES):
        p = Process(
            target=worker_process,
            args=(process_id, account_queue, status_dict, stop_event)
        )
        p.start()
        processes.append(p)
        time.sleep(0.1)
    
    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n[INFO] 收到停止信号...")
        stop_event.set()
        for p in processes:
            p.terminate()
    
    print("\n[完成] 所有进程已结束")
    print(f"成功日志: {LOG_SUCCESS}")
    print(f"失败日志: {LOG_FAIL}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
