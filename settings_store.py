import os
import json
import hashlib
import secrets
import threading
from datetime import datetime

CONFIG_DIR = "config"
PASSWORD_FILE = os.path.join(CONFIG_DIR, "admin_password.txt")
SIGN_SECRET_FILE = os.path.join(CONFIG_DIR, "app_sign_secret.txt")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")

DEFAULT_PASSWORD = "password"

DEFAULT_SETTINGS = {
    "log_retention_days": 30,
    "api_key": "",
    "notification": {
        "notify_login": True,
        "notify_order": True,
        "notify_points": True,
        "notify_account": True,
        "bindings": []
    }
}
_lock = threading.RLock()


def _hash(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _deep_merge(defaults, overrides):
    result = dict(defaults)
    if not isinstance(overrides, dict):
        return result
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _flatten_legacy_config(config, channel):
    """把旧版配置（可能是 {channel: {...}} 或扁平 dict）转换成该渠道的扁平配置。"""
    if not isinstance(config, dict):
        return {}
    nested = config.get(channel)
    if isinstance(nested, dict) and nested:
        return dict(nested)
    return {k: v for k, v in config.items() if not isinstance(v, dict)}


def _ensure_bindings(notification):
    """确保通知配置中存在 bindings 列表；将旧的单一渠道配置迁移为一条绑定。"""
    if not isinstance(notification, dict):
        notification = dict(DEFAULT_SETTINGS["notification"])
    bindings = notification.get("bindings")
    if not isinstance(bindings, list):
        bindings = []

    migrated = False
    if not bindings:
        legacy_channel = notification.get("channel")
        if legacy_channel and legacy_channel not in ("", "none"):
            bindings.append({
                "id": secrets.token_hex(8),
                "channel": legacy_channel,
                "config": _flatten_legacy_config(notification.get("config"), legacy_channel),
                "enabled": True,
                "last_status": "none",
                "last_message": "",
                "last_time": ""
            })
            migrated = True

    # 归一化每条绑定的 config（兼容旧的嵌套格式）
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        if "id" not in binding or not binding["id"]:
            binding["id"] = secrets.token_hex(8)
        binding.setdefault("channel", "none")
        binding.setdefault("enabled", True)
        binding.setdefault("last_status", "none")
        binding.setdefault("last_message", "")
        binding.setdefault("last_time", "")
        cfg = binding.get("config")
        if not isinstance(cfg, dict):
            cfg = {}
        if isinstance(cfg.get(binding["channel"]), dict):
            binding["config"] = dict(cfg[binding["channel"]])
        else:
            binding["config"] = cfg

    notification["bindings"] = bindings
    return bindings, migrated


# ---------------- 密码 ----------------
def get_password_hash():
    if not os.path.exists(PASSWORD_FILE):
        return ""
    with open(PASSWORD_FILE, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def has_password():
    return bool(get_password_hash())


def set_password(password):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(PASSWORD_FILE, "w", encoding="utf-8") as handle:
        handle.write(_hash(password))


def verify_password(password):
    stored = get_password_hash()
    if not stored:
        return password == DEFAULT_PASSWORD
    return stored == _hash(password)


def is_default_password():
    return verify_password(DEFAULT_PASSWORD)


# ---------------- 短信签名密钥 ----------------
def get_sign_secret():
    if not os.path.exists(SIGN_SECRET_FILE):
        return ""
    with open(SIGN_SECRET_FILE, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def set_sign_secret(value):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(SIGN_SECRET_FILE, "w", encoding="utf-8") as handle:
        handle.write((value or "").strip())


# ---------------- 通用设置 ----------------
def load_settings():
    with _lock:
        settings = _deep_merge(DEFAULT_SETTINGS, {})
        data = None
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, dict):
                    settings = _deep_merge(settings, data)
            except (OSError, ValueError):
                data = None

        if not isinstance(settings.get("notification"), dict):
            settings["notification"] = dict(DEFAULT_SETTINGS["notification"])
        _, migrated = _ensure_bindings(settings["notification"])
        if migrated:
            # 持久化迁移结果，避免每次加载都重新生成 id
            try:
                with open(SETTINGS_FILE, "w", encoding="utf-8") as handle:
                    json.dump(settings, handle, ensure_ascii=False, indent=2)
                os.makedirs(CONFIG_DIR, exist_ok=True)
            except OSError:
                pass
        return settings


def save_settings(settings):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with _lock:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, ensure_ascii=False, indent=2)
    return settings


def get_settings():
    return load_settings()


def update_settings(patch):
    settings = load_settings()
    settings = _deep_merge(settings, patch)
    return save_settings(settings)


# ---------------- 日志清理 ----------------
def get_log_retention_days():
    value = load_settings().get("log_retention_days", DEFAULT_SETTINGS["log_retention_days"])
    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_SETTINGS["log_retention_days"]


def set_log_retention_days(days):
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = DEFAULT_SETTINGS["log_retention_days"]
    if days < 0:
        days = 0
    update_settings({"log_retention_days": days})
    return days


# ---------------- API 密钥 ----------------
def get_api_key():
    key = (load_settings().get("api_key") or "").strip()
    if key:
        return key
    key = "7ma_" + secrets.token_hex(20)
    update_settings({"api_key": key})
    return key


def regenerate_api_key():
    key = "7ma_" + secrets.token_hex(20)
    update_settings({"api_key": key})
    return key


# ---------------- 通知 ----------------
def get_notification():
    notification = load_settings().get("notification")
    if not isinstance(notification, dict):
        return dict(DEFAULT_SETTINGS["notification"])
    _ensure_bindings(notification)
    return notification


def set_notification_toggles(notify_login=True, notify_order=True, notify_points=True, notify_account=True):
    settings = load_settings()
    notification = settings.get("notification") or {}
    _ensure_bindings(notification)
    notification["notify_login"] = bool(notify_login)
    notification["notify_order"] = bool(notify_order)
    notification["notify_points"] = bool(notify_points)
    notification["notify_account"] = bool(notify_account)
    settings["notification"] = notification
    save_settings(settings)
    return notification


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_bindings():
    notification = get_notification()
    return notification.get("bindings") or []


def get_binding(binding_id):
    for binding in get_bindings():
        if binding.get("id") == binding_id:
            return binding
    return None


def add_binding(channel, config, enabled=True):
    settings = load_settings()
    notification = settings.get("notification") or {}
    bindings, _ = _ensure_bindings(notification)
    binding = {
        "id": secrets.token_hex(8),
        "channel": channel or "none",
        "config": config if isinstance(config, dict) else {},
        "enabled": bool(enabled),
        "last_status": "none",
        "last_message": "",
        "last_time": ""
    }
    bindings.append(binding)
    notification["bindings"] = bindings
    settings["notification"] = notification
    save_settings(settings)
    return binding


def update_binding(binding_id, channel=None, config=None, enabled=None):
    settings = load_settings()
    notification = settings.get("notification") or {}
    bindings, _ = _ensure_bindings(notification)
    for binding in bindings:
        if binding.get("id") == binding_id:
            if channel is not None:
                binding["channel"] = channel
            if config is not None:
                binding["config"] = config if isinstance(config, dict) else {}
            if enabled is not None:
                binding["enabled"] = bool(enabled)
            binding["last_status"] = "none"
            binding["last_message"] = ""
            binding["last_time"] = ""
            break
    notification["bindings"] = bindings
    settings["notification"] = notification
    save_settings(settings)
    return get_binding(binding_id)


def delete_binding(binding_id):
    settings = load_settings()
    notification = settings.get("notification") or {}
    _ensure_bindings(notification)
    notification["bindings"] = [b for b in (notification.get("bindings") or []) if b.get("id") != binding_id]
    settings["notification"] = notification
    save_settings(settings)
    return True


def set_binding_status(binding_id, ok, message=""):
    settings = load_settings()
    notification = settings.get("notification") or {}
    _ensure_bindings(notification)
    for binding in notification.get("bindings") or []:
        if binding.get("id") == binding_id:
            binding["last_status"] = "ok" if ok else "failed"
            binding["last_message"] = str(message or "")
            binding["last_time"] = _now_str()
            break
    settings["notification"] = notification
    save_settings(settings)
    return True
