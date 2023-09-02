from flask import Flask, render_template, request, jsonify
from datetime import datetime
import requests
import time
import hashlib
import threading
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from scheduler import main as start_scheduler


# 创建 Flask 应用对象
app = Flask(__name__)

# 启用调试模式（仅用于开发和调试）
app.debug = True


# 确保 "logs" 文件夹存在
logs_folder = 'logs'
os.makedirs(logs_folder, exist_ok=True)
# 创建一个日志记录器
app_logger = logging.getLogger('app')
# 配置日志级别
app_logger.setLevel(logging.INFO)
# 获取当前日期和时间的字符串，用作日志文件名
current_datetime = datetime.now().strftime("%Y-%m-%d")
app_filename = os.path.join(logs_folder, f'order_{current_datetime}.log')
# 创建一个 TimedRotatingFileHandler 实例，按天轮转日志文件
app_handler = TimedRotatingFileHandler(app_filename, when='midnight', interval=1, backupCount=7)
# 创建日志格式
app_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
app_handler.setFormatter(app_formatter)
# 将处理程序添加到记录器
app_logger.addHandler(app_handler)


# 读取Authorization
with open('config/Authorization.txt', 'r') as auth_file:
    Authorization = auth_file.read().strip()

# 记录上次成功提交订单的时间
last_successful_order_time = 0

def send_request(url, method, body):
    headers = {
        "Authorization": Authorization,
        "Content-Type": "application/json"
    }
    response = requests.request(method, url, headers=headers, json=body)
    return response.json()

def place_order(bike_number):
    url = "https://newmapi.7mate.cn/api/order"
    method = "POST"
    body = {
        "card_code": "",
        "order_type": 1,
        "car_number": bike_number,
        "latitude": "",
        "price": "",
        "longitude": ""
    }
    result = send_request(url, method, body)
    return result

def unlock():
    url = "https://newmapi.7mate.cn/api/car/unlock"
    method = "POST"
    body = {
        "latitude": "34.367498",
        "action_type": 1,
        "longitude": "108.892286"
    }
    result = send_request(url, method, body)
    return result

def md5Hash(text):
    md5 = hashlib.md5()
    md5.update(text.encode('utf-8'))
    return md5.hexdigest()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    global last_successful_order_time
    current_time = time.time()

    # 检查是否在一分钟内
    if current_time - last_successful_order_time < 60:
        remaining_time = int(60 - (current_time - last_successful_order_time))
        return render_template('result.html', data={
            'message': f'一分钟内只能提交一次订单，请稍后再试。还剩余 {remaining_time} 秒。',
            'is_success': False
        })

    bike_number = request.form.get('bike_number')

    order_result = place_order(bike_number)

    if order_result["status_code"] == 200 and order_result["message"] == "下单成功":
        unlock_result = unlock()
        last_successful_order_time = current_time
        # 记录成功订单到日志
        app_logger.info(f'--成功订单: bike_number={bike_number}, unlock_result={unlock_result["message"]}')
        return render_template('result.html', data={
            'message': order_result['message'],
            'unlock_result': unlock_result['message'],
            'is_success': True
        })
    else:
        # 记录失败订单到日志
        app_logger.warning(f'--失败订单: bike_number={bike_number}, message={order_result["message"]}')
        return render_template('result.html', data={
            'message': order_result['message'],
            'is_success': False
        })

if __name__ == '__main__':
    intervalSeconds = 60  # 设置监听的时间间隔，单位为秒
    start_scheduler()  # 启动定时任务
    app.run(host='0.0.0.0', port=4321, debug=True)
