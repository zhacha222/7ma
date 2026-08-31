import os
import json
import hashlib
import time
import threading

CONFIG_DIR = "config"
CONFIG_FILE = os.path.join(CONFIG_DIR, "points_config.json")
_lock = threading.Lock()

DEFAULT_CONFIG = {
    "daily_time": "08:10",
    "last_scheduled_date": "",
    "accounts": {}
}


def account_key(token):
    return hashlib.md5(token.encode("utf-8")).hexdigest()


def _load():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                if not isinstance(config.get("accounts"), dict):
                    config["accounts"] = {}
                return config
        except (OSError, ValueError):
            pass
    return DEFAULT_CONFIG.copy()


def _save(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)


def get_config():
    with _lock:
        return _load()


def get_daily_time():
    with _lock:
        return _load().get("daily_time") or DEFAULT_CONFIG["daily_time"]


def set_daily_time(value):
    with _lock:
        config = _load()
        config["daily_time"] = value
        _save(config)
        return config


def get_last_scheduled_date():
    with _lock:
        return _load().get("last_scheduled_date") or ""


def set_last_scheduled_date(value):
    with _lock:
        config = _load()
        config["last_scheduled_date"] = value
        _save(config)
        return config


def get_account(token, create=True):
    key = account_key(token)
    with _lock:
        config = _load()
        accounts = config.get("accounts", {})
        if key not in accounts and create:
            accounts[key] = {}
        return config, key, accounts


def is_scheduled(token):
    _, _, accounts = get_account(token, create=False)
    return bool(accounts.get(key_of(token), {}).get("scheduled", False))


def set_scheduled(token, enabled):
    key = account_key(token)
    with _lock:
        config = _load()
        accounts = config.get("accounts", {})
        account = accounts.get(key, {})
        account["scheduled"] = bool(enabled)
        accounts[key] = account
        config["accounts"] = accounts
        _save(config)
    return bool(enabled)


def get_schedule(token):
    key = account_key(token)
    with _lock:
        config = _load()
        account = config.get("accounts", {}).get(key, {})
        run_time = account.get("schedule_time") or config.get("daily_time") or DEFAULT_CONFIG["daily_time"]
        return {
            "enabled": bool(account.get("scheduled", False)),
            "time": run_time
        }


def set_schedule(token, enabled, run_time=None):
    key = account_key(token)
    with _lock:
        config = _load()
        accounts = config.get("accounts", {})
        account = accounts.get(key, {})
        account["scheduled"] = bool(enabled)
        if run_time:
            account["schedule_time"] = run_time
        accounts[key] = account
        config["accounts"] = accounts
        _save(config)
    return get_schedule(token)


def record_last_run(token, result):
    key = account_key(token)
    with _lock:
        config = _load()
        accounts = config.get("accounts", {})
        account = accounts.get(key, {})
        account["last_run"] = result
        accounts[key] = account
        config["accounts"] = accounts
        _save(config)
    return result


def get_last_run(token):
    key = account_key(token)
    with _lock:
        config = _load()
        account = config.get("accounts", {}).get(key, {})
        return account.get("last_run")


def set_cached_info(token, info, ttl=120):
    key = account_key(token)
    with _lock:
        config = _load()
        accounts = config.get("accounts", {})
        account = accounts.get(key, {})
        account["cached_info"] = {"info": info, "ts": time.time(), "ttl": ttl}
        accounts[key] = account
        config["accounts"] = accounts
        _save(config)


def set_cached_credit(token, data, ttl=300):
    key = account_key(token)
    with _lock:
        config = _load()
        accounts = config.get("accounts", {})
        account = accounts.get(key, {})
        account["cached_credit"] = {"data": data, "ts": time.time(), "ttl": ttl}
        accounts[key] = account
        config["accounts"] = accounts
        _save(config)


def set_cached_cycling(token, data, ttl=300):
    key = account_key(token)
    with _lock:
        config = _load()
        accounts = config.get("accounts", {})
        account = accounts.get(key, {})
        account["cached_cycling"] = {"data": data, "ts": time.time(), "ttl": ttl}
        accounts[key] = account
        config["accounts"] = accounts
        _save(config)


def get_cached_cycling(token):
    key = account_key(token)
    with _lock:
        config = _load()
        cached = config.get("accounts", {}).get(key, {}).get("cached_cycling")
    if not cached:
        return None
    if time.time() - cached.get("ts", 0) > cached.get("ttl", 300):
        return None
    return cached.get("data")


def set_cached_cert(token, data, ttl=600):
    key = account_key(token)
    with _lock:
        config = _load()
        accounts = config.get("accounts", {})
        account = accounts.get(key, {})
        account["cached_cert"] = {"data": data, "ts": time.time(), "ttl": ttl}
        accounts[key] = account
        config["accounts"] = accounts
        _save(config)


def get_cached_cert(token):
    key = account_key(token)
    with _lock:
        config = _load()
        cached = config.get("accounts", {}).get(key, {}).get("cached_cert")
    if not cached:
        return None
    if time.time() - cached.get("ts", 0) > cached.get("ttl", 600):
        return None
    return cached.get("data")


def get_cached_credit(token):
    key = account_key(token)
    with _lock:
        config = _load()
        cached = config.get("accounts", {}).get(key, {}).get("cached_credit")
    if not cached:
        return None
    if time.time() - cached.get("ts", 0) > cached.get("ttl", 300):
        return None
    return cached.get("data")


def get_cached_info(token):
    key = account_key(token)
    with _lock:
        config = _load()
        cached = config.get("accounts", {}).get(key, {}).get("cached_info")
    if not cached:
        return None
    if time.time() - cached.get("ts", 0) > cached.get("ttl", 120):
        return None
    return cached.get("info")


def key_of(token):
    return account_key(token)
