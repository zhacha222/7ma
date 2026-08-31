from datetime import datetime
import threading
import requests
import net_util
import hashlib
import os
import logging
from logging.handlers import TimedRotatingFileHandler
import auth_store
import return_logic


intervalSeconds = 60  # 设置监听的时间间隔，单位为秒

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
scheduler_handler = TimedRotatingFileHandler(scheduler_filename, when='midnight', interval=1, backupCount=7, encoding='utf-8')
# 创建日志格式
scheduler_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
scheduler_handler.setFormatter(scheduler_formatter)
# 将处理程序添加到记录器
scheduler_logger.addHandler(scheduler_handler)


def md5Hash(text):
    md5 = hashlib.md5()
    md5.update(text.encode('utf-8'))
    return md5.hexdigest()

def carBack(encryptedBackType, encryptedActionType, encryptedLockStatus, authorization):
    url2 = "https://newmapi.7mate.cn/api/order/car_notification"
    headers = {
        "Authorization": authorization,
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

    response = net_util.request("POST", url2, headers=headers, json=payload)
    return response.json()


def check_single_authorization(authorization):
    authority = return_logic.fetch_car_authority(authorization)
    if not authority.get("ok") or authority.get("unauthorized_code") != 6:
        return False

    order_sn = authority.get("order_sn")
    if not order_sn:
        return False

    result = return_logic.return_bike(authorization, order_sn)
    if result.get("ok"):
        print(f"{datetime.now()}--当前订单：{order_sn}，还车成功")
        scheduler_logger.info(f"--当前订单：{order_sn}，还车成功")
        return True

    scheduler_logger.warning(f"--当前订单：{order_sn}，还车失败：{result.get('error') or result.get('status_code')}")
    return False


def main():
    # 每 60 秒执行一次
    threading.Timer(intervalSeconds, main).start()

    authorizations = auth_store.load_authorizations()
    if not authorizations:
        print(f"{datetime.now()}--未配置Authorization")
        return

    for index, authorization in enumerate(authorizations, start=1):
        try:
            if check_single_authorization(authorization):
                return
        except Exception as exc:
            scheduler_logger.warning(f"--Authorization[{index}] 检查失败: {exc}")
            continue

    print(f"{datetime.now()}--暂无订单")


if __name__ == '__main__':
    intervalSeconds = 60  # 设置监听的时间间隔，单位为秒
    main()  # 启动定时任务
