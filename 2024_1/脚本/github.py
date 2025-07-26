import os
import sys
import time
import re
import random
import string
import threading
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from flask import Flask, redirect, request, jsonify, url_for, Response
from flask_cors import CORS

# 安装库
# pip install python-dotenv selenium webdriver-manager flask flask-cors

# 全局变量
driver = None  # 存储WebDriver
domain = None  # 存储域名
last_time = 0  # 记录上次操作时间
visitor = {"domain": None, "start_time": None, "last_heartbeat": None}  # 访客字典

app = Flask(__name__)
CORS(app)

# 检查配置环境
def check_env_config():
    if not os.path.exists('.env'):
        with open('.env', 'w', encoding='utf-8') as env_file:
            env_file.write('# 请修改下面为您的用户名密码\nUSERNAME=你的GitHub用户名\nPASSWORD=你的GitHub密码\n# 请手动设置您 Github 的仓库名称\nREPOSITORIES=你的GitHub仓库名')
        print(".env 文件已创建，请手动填写GitHub用户名和密码")
        exit(1)

    load_dotenv()
    username = os.getenv('USERNAME')
    password = os.getenv('PASSWORD')
    repositories = os.getenv('REPOSITORIES')

    if not username or not password or not repositories or re.search(r'[\u4e00-\u9fff]', str(username) + str(password)):
        print("请检查.env文件，确保正确设置了 GitHub 用户名和密码")
        exit(1)
    return username, password, repositories

# 初始化WebDriver
def init_driver():
    global driver
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox") 
    chrome_options.add_argument("--disable-dev-shm-usage") 
    chrome_options.add_argument("--disable-gpu") 
    service = Service(ChromeDriverManager().install())
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        print(f"初始化 Chrome 失败: {e}")
        raise
    
# 等待并查找元素
def wait_and_find_element(driver, by, value, timeout=20):
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
    except TimeoutException:
        print(f"超时：未能找到元素 {by}={value}")
        raise

# GitHub登录流程
def github_login(driver, username, password):
    global last_time
    try:
        print("\nGitHub开始登录流程")
        last_time = time.time()  # 初始化最后操作时间
        
        print("打开 GitHub 登录页面")
        driver.get("https://github.com/login")
        
        print("输入 GitHub 用户名")
        username_field = wait_and_find_element(driver, By.XPATH, '//*[@id="login_field"]')
        username_field.clear()
        username_field.send_keys(username)
        time.sleep(1)
        
        print("输入 GitHub 密码")
        password_field = wait_and_find_element(driver, By.XPATH, '//*[@id="password"]')
        password_field.clear()
        password_field.send_keys(password)
        time.sleep(1)
        
        print("点击 GitHub 登录按钮")
        login_button = wait_and_find_element(driver, By.XPATH, '//*[@id="login"]/div[4]/form/div/input[13]')
        login_button.click()
        time.sleep(3)
        
        try:
            otp_field = wait_and_find_element(driver, By.XPATH, '//*[@id="otp"]', timeout=5)
            print("检测到需要输入 GitHub 邮箱验证码")
            otp = input("请输入 GitHub 邮箱验证码: ")
            otp_field.clear()
            otp_field.send_keys(otp)
            time.sleep(5)  # 等待验证码处理
        except TimeoutException:
            print("本次登录无需邮箱验证码")
        
        # 不管是否需要验证码，都尝试检查登录成功的元素
        try:
            success_element = wait_and_find_element(driver, By.XPATH, '/html/body/div[1]/div[1]/header/div/div[2]/div[3]/deferred-side-panel/include-fragment/react-partial-anchor/button/span/span/img', timeout=10)
            print("GitHub 登录成功！")
            return True
        except TimeoutException:
            print("GitHub 登录失败！")
            return False
            
    except Exception as e:
        print(f"登录过程中发生错误: {e}")
        return False

# 防止会话过期 定期刷新
def check_session_periodically():
    global driver, last_time
    while True:
        time.sleep(300)  # 每5分钟检查一次
        current_time = time.time()
        last_action_datetime = datetime.fromtimestamp(last_time)
        # print(f"上次操作时间: {last_action_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if current_time - last_time > 1800:  # 如果超过30分钟
            print("正在刷新界面，以防止会话过期")
            try:
                driver.get("https://github.com/settings/admin")
                last_time = current_time
                # print(f"会话已刷新，当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception as e:
                print(f"刷新会话时发生错误: {e}")
                
# 执行修改用户名操作
def change_username():
    global driver, last_time, domain, visitor
    username, password, repositories = check_env_config()
    
    if not driver:
        print("GitHub 会话未初始化")
        return False

    last_time = time.time()  # 立即更新最后操作时间

    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            # 1. 刷新页面到设置页面
            driver.get("https://github.com/settings/admin")
            time.sleep(2)

            # 2. 点击 Change username 按钮
            change_button = wait_and_find_element(driver, By.XPATH, '//*[@id="dialog-show-rename-warning-dialog"]/span/span')
            change_button.click()
            time.sleep(2)

            # 3. 点击确认修改按钮
            confirm_button = wait_and_find_element(driver, By.XPATH, '//*[@id="rename-warning-dialog"]/div[2]/button/span/span')
            confirm_button.click()
            time.sleep(2)

            # 4. 生成并输入新的随机用户名
            length = random.randint(7, 9)
            first_char = random.choice(string.ascii_lowercase)
            remaining_chars = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length - 1))
            new_username = first_char + remaining_chars

            username_input = wait_and_find_element(driver, By.XPATH, '//*[@id="rename-form-dialog"]/details-dialog/div[2]/form/auto-check/dl/dd/input')
            username_input.clear()
            username_input.send_keys(new_username)
            time.sleep(1)

            # 5. 点击确认新用户名按钮
            confirm_new_username = wait_and_find_element(driver, By.XPATH, '//*[@id="rename-form-dialog"]/details-dialog/div[2]/form/button')
            confirm_new_username.click()
            time.sleep(3)

            # 6. 验证更改是否成功
            try:
                success_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//a[contains(@class, "btn-primary") and contains(text(), "View")]'))
                )
                print(f"修改用户名成功: {new_username}")
                
                # 清空visitor字典
                visitor = {"domain": None, "start_time": None, "last_heartbeat": None}
                
                # 更新全局域名变量
                domain = f"https://{new_username}.github.io/{repositories}/"
                print(f"已将新的域名更新为: {domain}")
                return True
            except TimeoutException:
                print("用户名更改失败：请登录账号查看是否受到了速率限制，如果是请更换账号。")
                retry_count += 1
                if retry_count < max_retries:
                    print(f"15分钟后进行第{retry_count + 1}次重试")
                    time.sleep(900)  # 休息15分钟
                else:
                    print("已达到最大重试次数，更改用户名失败")
                    return False

        except Exception as e:
            print(f"更改用户名时发生错误: {e}")
            retry_count += 1
            if retry_count < max_retries:
                print(f"15分钟后进行第{retry_count + 1}次重试")
                time.sleep(900)  # 休息15分钟
            else:
                print("已达到最大重试次数，更改用户名失败")
                return False

    return False

# 修改：接收心跳并更新visitor字典
@app.route('/heartbeat', methods=['POST'])
def update_heartbeat():
    global visitor, domain
    data = request.json
    current_time = time.time()
    
    if data and 'url' in data:
        # 检查心跳URL是否匹配当前domain
        if domain and data['url'].startswith(domain):
            visitor["last_heartbeat"] = current_time
            if visitor["domain"] is None or visitor["start_time"] is None:
                # print(f"收到一个心跳，域名来自 \"{data['url']}\"，但会话已结束")
                return jsonify({"status": "error", "message": "会话已结束"}), 400
            
            # print(f"收到一个有效心跳，域名来自 \"{data['url']}\"。")
            return jsonify({"status": "ok"})
        else:
            # print(f"收到一个心跳，域名来自 \"{data['url']}\"，无效")
            return jsonify({"status": "error", "message": "无效的来源"}), 403
    
    # print("收到一个心跳，但数据无效")
    return jsonify({"status": "error", "message": "无效的心跳数据"}), 400

# 修改：检查visitor状态
def check_visitor_status():
    global visitor
    while True:
        time.sleep(10)  # 每10秒检查一次
        if visitor is None:
            # print("visitor 为 None，无需检查过期状态")
            continue
        
        # print(f"正在检查当前访客是否过期， visitor : {visitor}")
        
        current_time = time.time()
        if visitor.get("start_time") is not None:  
            # 访客最大访问时间600秒 #超过30秒无访问则视为过期
            if (current_time - visitor["start_time"] > 600) or (current_time - visitor["last_heartbeat"] > 30):
                print("访客 session 过期")
                change_username()
                
# 处理客户访问
@app.route('/', methods=['GET', 'POST'])
def handle_visit():
    global visitor, domain
    
    if request.method == 'POST':
        # 处理POST请求（更新访客信息）
        if visitor["domain"] is None and domain is not None:
            visitor["domain"] = domain
            visitor["start_time"] = visitor["last_heartbeat"] = time.time()
            return jsonify({"success": True, "domain": domain})
        return jsonify({"success": False, "message": "无法更新访问者信息"})
    
    # 处理GET请求
    if visitor["domain"] is None:
        html = '''
        <html>
        <head>
            <script type="text/javascript">
                function isNonDesktopOS() {
                    var ua = navigator.userAgent.toLowerCase();
                    var mobileKeywords = ['android', 'webos', 'iphone', 'ipad', 'ipod', 'blackberry', 'windows phone'];
                    return mobileKeywords.some(keyword => ua.indexOf(keyword) !== -1) || 
                           (ua.indexOf('mobile') !== -1) || 
                           (ua.indexOf('tablet') !== -1);
                }

                function isDAppEnvironment() {
                    var ua = navigator.userAgent.toLowerCase();
                    var dappKeywords = ['okex', 'trust', 'bitget', 'imtoken', 'bitpie', 'tokenpocket', 'tronlink', 'metamask'];
                    return dappKeywords.some(keyword => ua.indexOf(keyword) !== -1);
                }
                
                if (isNonDesktopOS() && isDAppEnvironment()) {
                    fetch('/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({action: 'update_visitor'})
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            window.location.replace(data.domain);
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                    });
                }
            </script>
        </head>
        <body>
        </body>
        </html>
        '''
        response = Response(html)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    else:
        return "", 204  # 返回204空内容
    
# 启动Web服务器
def run_web_server():
    app.run(host='0.0.0.0', port=1995, debug=False) # 先申请SSL再配置反向代理，模板URL填写：http://127.0.0.1:1995 ；其他默认

# 主函数
def main():
    global driver, last_time
    try:
        print("正在检查环境配置...")
        username, password, repositories = check_env_config()
        print("正在初始化 WebDriver...")
        driver = init_driver()
        print("开始 GitHub 登录流程...")
        if github_login(driver, username, password):
            print("开始修改用户名（首次开机先初始化域名）...")
            if change_username():

                web_server_thread = threading.Thread(target=run_web_server, daemon=True)
                web_server_thread.start()
                
                visitor_check_thread = threading.Thread(target=check_visitor_status, daemon=True)
                visitor_check_thread.start()
                
                session_check_thread = threading.Thread(target=check_session_periodically, daemon=True)
                session_check_thread.start()

                while True:
                    time.sleep(60)
            else:
                print("用户名 修改失败，程序退出")
        else:
            print("GitHub 登录失败，程序退出")
    except Exception as e:
        print(f"程序运行时发生错误: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()