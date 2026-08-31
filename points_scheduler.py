import logging
import os
import threading
import time
from datetime import datetime, date
from logging.handlers import TimedRotatingFileHandler
import auth_store
import points
import points_store
import notify


CHECK_INTERVAL = 30


def _setup_logger():
    logger = logging.getLogger('points_scheduler')
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    os.makedirs('logs', exist_ok=True)
    handler = TimedRotatingFileHandler('logs/points_scheduler.log', when='midnight', interval=1, backupCount=7, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    return logger


def run_scheduled_if_due(logger=None):
    logger = logger or _setup_logger()
    try:
        now = datetime.now().strftime('%H:%M')
        tokens = auth_store.load_authorizations()
        ran = 0
        errors = 0
        scheduled_count = 0
        for token in tokens:
            raw_token = points.normalize_token(token)
            if not raw_token:
                continue
            schedule = points_store.get_schedule(raw_token)
            if not schedule.get('enabled'):
                continue
            if schedule.get('time') != now:
                continue
            last_run = points_store.get_last_run(raw_token)
            if last_run and str(last_run.get('time', '')).startswith(date.today().strftime('%Y-%m-%d')):
                continue
            scheduled_count += 1
            try:
                result = points.run_account_tasks(raw_token)
                phone = (result.get('info') or {}).get('phone', '')
                if result.get('ok'):
                    logger.info(f"定时积分任务完成：{phone}，获得 {result.get('total_gain', 0)} 积分")
                    ran += 1
                else:
                    logger.warning(f"定时积分任务失败：{phone}，{result.get('error', '')}")
                    errors += 1
            except Exception as exc:
                logger.error(f"定时积分任务异常：{exc}")
                errors += 1
            time.sleep(0.5)

        if scheduled_count:
            message = f"应执行 {scheduled_count} 个，成功 {ran} 个，失败 {errors} 个"
            logger.info(f"定时积分任务本轮处理：{message}")
            try:
                notify.send_async('points', '积分定时运行结果', (
                    f"账号统计：{message}\n"
                    f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ))
            except Exception:
                pass
            return True
        return False
    except Exception as exc:
        logger.error(f"定时调度检查异常：{exc}")
        return False


def main():
    def loop():
        logger = _setup_logger()
        while True:
            try:
                run_scheduled_if_due(logger)
            except Exception:
                pass
            time.sleep(CHECK_INTERVAL)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()


if __name__ == '__main__':
    main()
    while True:
        time.sleep(60)
