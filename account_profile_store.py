import os
import json
import hashlib
import threading
from datetime import datetime

CONFIG_DIR = "config"
PROFILE_FILE = os.path.join(CONFIG_DIR, "account_profiles.json")
_lock = threading.RLock()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _token_hash(raw_token):
    return hashlib.md5((raw_token or "").encode("utf-8")).hexdigest()


def _load():
    data = {}
    if os.path.exists(PROFILE_FILE):
        try:
            with open(PROFILE_FILE, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            data = {}
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        profiles = {}
    data["profiles"] = profiles
    return data


def _save(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(PROFILE_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def profiles():
    with _lock:
        return _load()["profiles"]


def save_profile(raw_token, info):
    """保存账号本地档案（姓名、手机号等）。info 必须是有效的账户信息。"""
    if not info or not info.get("ok"):
        return None
    key = _token_hash(raw_token)
    profile = {
        "phone": info.get("show_phone") or info.get("phone") or "",
        "username": info.get("username") or "",
        "school_name": info.get("school_name") or "",
        "user_id": info.get("user_id"),
        "updated_at": _now(),
        "invalid": False,
        "invalid_reason": ""
    }
    with _lock:
        cur = _load()
        cur["profiles"][key] = profile
        _save(cur)
    return profile


def get_profile(raw_token):
    key = _token_hash(raw_token)
    with _lock:
        return _load()["profiles"].get(key)


def mark_invalid(raw_token, reason):
    """标记账号失效，返回是否发生了由有效→失效的转变（用于触发一次性通知）。"""
    key = _token_hash(raw_token)
    with _lock:
        cur = _load()
        profiles_map = cur["profiles"]
        profile = profiles_map.get(key)
        became_invalid = False
        if profile is None:
            profile = {"phone": "", "username": "", "school_name": "", "user_id": "", "show_name": "", "invalid_reason": ""}
            profiles_map[key] = profile
        if not profile.get("invalid"):
            became_invalid = True
            profile["invalid"] = True
            profile["invalid_reason"] = reason or "账号失效"
            profile["invalid_time"] = _now()
            _save(cur)
        else:
            profile["invalid_reason"] = reason or profile.get("invalid_reason") or "账号失效"
            _save(cur)
        return became_invalid


def clear_invalid(raw_token):
    """账号重新有效时，清除失效标记。"""
    key = _token_hash(raw_token)
    with _lock:
        cur = _load()
        profile = cur["profiles"].get(key)
        if profile and profile.get("invalid"):
            profile["invalid"] = False
            profile["invalid_reason"] = ""
            profile["invalid_time"] = ""
            profile["updated_at"] = _now()
            _save(cur)


def invalid_profiles():
    result = []
    for key, profile in profiles().items():
        if profile.get("invalid"):
            result.append(dict(profile, _key=key))
    return result


def find_by_identity(raw_token):
    """根据新 token 的本地档案，找到同名或同手机号的失效账号 token_hash。"""
    new_profile = get_profile(raw_token)
    if not new_profile:
        return None
    new_phone = new_profile.get("phone") or ""
    new_name = new_profile.get("username") or ""
    for key, profile in profiles().items():
        if key == _token_hash(raw_token):
            continue
        if not profile.get("invalid"):
            continue
        if (new_phone and profile.get("phone") and profile.get("phone") == new_phone):
            return key
        if (new_name and profile.get("username") and profile.get("username") == new_name):
            return key
    return None


def delete_profile(raw_token):
    key = _token_hash(raw_token)
    with _lock:
        cur = _load()
        cur["profiles"].pop(key, None)
        _save(cur)
