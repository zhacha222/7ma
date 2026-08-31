import os
import json
import hashlib

CONFIG_DIR = "config"
DEVICE_FILE = os.path.join(CONFIG_DIR, "device_ids.json")


def _read():
    if not os.path.exists(DEVICE_FILE):
        return {}
    try:
        with open(DEVICE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def _write(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(DEVICE_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def generate_device_id(phone):
    digest = hashlib.md5(phone.encode("utf-8")).hexdigest()[:12]
    return f"7ma_web_{digest}"


def get_device_id(phone):
    return _read().get(phone, "")


def set_device_id(phone, device_id):
    device_id = (device_id or "").strip()
    data = _read()
    if device_id:
        data[phone] = device_id
    else:
        data.pop(phone, None)
    _write(data)
    return device_id
