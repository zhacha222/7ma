from datetime import datetime
import threading
import requests
import hashlib
import time
import os
import logging
from logging.handlers import TimedRotatingFileHandler


intervalSeconds = 60  # 设置监听的时间间隔，单位为秒
# 读取Authorization
with open('config/Authorization.txt', 'r') as auth_file:
    Authorization = auth_file.read().strip()
    
# 确保 "logs" 文件夹存在
logs_folder = 'logs'
os.makedirs(logs_folder, exist_ok=True)
# 创建一个日志记录器
scheduler_logger = logging.getLogger('scheduler')
# 配置日志级别
scheduler_logger.setLevel(logging.INFO)
# 获取当前日期和时间的字符串，用作日志文件名
current_datetime = datetime.now().strftime("%Y-%m-%d")
scheduler_filename = os.path.join(logs_folder, f'scheduler_{current_datetime}.log')
# 创建一个 TimedRotatingFileHandler 实例，按天轮转日志文件
scheduler_handler = TimedRotatingFileHandler(scheduler_filename, when='midnight', interval=1, backupCount=7)
# 创建日志格式
scheduler_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
scheduler_handler.setFormatter(scheduler_formatter)
# 将处理程序添加到记录器
scheduler_logger.addHandler(scheduler_handler)


def md5Hash(text):
    md5 = hashlib.md5()
    md5.update(text.encode('utf-8'))
    return md5.hexdigest()

def carBack(encryptedBackType, encryptedActionType, encryptedLockStatus):
    url2 = "https://newmapi.7mate.cn/api/order/car_notification"
    headers = {
        "Authorization": Authorization,
        "Content-Type": "application/json"
    }
    payload = {
        "parking": "",
        "remark": "检测到车锁状态为关",
        "longitude": "108.892286",
        "back_type": encryptedBackType,
        "latitude": "34.367498",
        "action_type": encryptedActionType,
        "lock_status": encryptedLockStatus
    }

    options = {
        "method": "POST",
        "url": url2,
        "headers": headers,
        "json": payload
    }

    response = requests.post(url2, headers=headers, json=payload)
    return response.json()
    
# 定时任务代码
def main():
    threading.Timer(intervalSeconds, main).start()

    url = "https://newmapi.7mate.cn/api/user/car_authority"
    headers = {"Authorization": Authorization}

    response = requests.get(url, headers=headers, json=True)

    if response.status_code == 200 and response.json().get("data", {}).get("unauthorized_code") == 6:
        orderSn = response.json().get("data", {}).get("order", {}).get("order_sn")
        if orderSn:
            lockStatus = f"{orderSn}:lock_status:1"
            encryptedLockStatus = md5Hash(lockStatus)
            actionType = f"{orderSn}:action_type:3"
            encryptedActionType = md5Hash(actionType)
            backType = f"{orderSn}:back_type:2"
            encryptedBackType = md5Hash(backType)
            carBack(encryptedBackType, encryptedActionType, encryptedLockStatus)
            print(f"{datetime.now()}--当前订单：{orderSn}，还车成功")
            # 记录还车成功到日志
            scheduler_logger.info(f"--当前订单：{orderSn}，还车成功")
    else:
        print(f"{datetime.now()}--暂无订单")
        # 记录还车成功到日志
        # scheduler_logger.info(f"--暂无订单")

if __name__ == '__main__':
    intervalSeconds = 60  # 设置监听的时间间隔，单位为秒
    main()  # 启动定时任务
