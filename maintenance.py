import os
import glob
import time
import threading

import settings_store

CHECK_INTERVAL = 3600


def cleanup_logs(retention_days):
    deleted = 0
    if retention_days <= 0:
        return deleted
    cutoff = time.time() - retention_days * 86400
    for path in glob.glob(os.path.join("logs", "*.log")):
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                deleted += 1
        except OSError:
            continue
    return deleted


def main():
    def loop():
        # 启动时先执行一次，之后每小时检查
        while True:
            try:
                days = settings_store.get_log_retention_days()
                cleanup_logs(days)
            except Exception:
                pass
            time.sleep(CHECK_INTERVAL)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()