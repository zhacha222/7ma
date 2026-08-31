import json
import time
import hashlib
import random
import string
import requests
import net_util
import settings_store

BASE_URL = "https://newmapi.7mate.cn"
SMS_SIGN_SECRET = "f9A3k7Pz2R8sT5wQe1bN4mU6yV9xZ0dG"




def _common_headers():
    return {
        "Content-Type": "application/json",
        "Accept": "application/vnd.ws.v1+json",
        "Referer": "https://servicewechat.com/wx9a6a1a8407b04c5d/420/page-frame.html",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.66(0x18004237) NetType/WIFI Language/zh_CN"
    }


def _rand(n):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))


def generate_captcha(device_id):
    body = {
        "scene": "sms_send",
        "device_id": device_id,
        "client_info": {
            "user_agent": "WeChat/MiniProgram (ios; iOS 16.5.1)",
            "screen": "390x844",
            "language": "zh_CN"
        },
        "type": "slider"
    }
    try:
        response = net_util.request("POST", f"{BASE_URL}/auth/sms/captcha/generate", json=body, headers=_common_headers(), timeout=15)
        data = response.json()
    except Exception as exc:
        return {"ok": False, "error": f"请求异常：{exc}"}

    payload = data.get("data") if isinstance(data, dict) else None
    if data.get("code") == 0 and payload:
        return {
            "ok": True,
            "token": payload.get("token"),
            "type": payload.get("type"),
            "background_img": payload.get("background_img"),
            "slider_img": payload.get("slider_img"),
            "slider_y": payload.get("slider_y"),
            "expire_time": payload.get("expire_time")
        }
    return {"ok": False, "error": str(data.get("message") or "生成验证码失败")}


def verify_captcha(token, x, y, track, duration, device_id):
    body = {
        "token": token,
        "position": {"x": int(x), "y": int(y)},
        "track": track,
        "device_id": device_id,
        "duration": int(duration)
    }
    try:
        response = net_util.request("POST", f"{BASE_URL}/auth/sms/captcha/verify", json=body, headers=_common_headers(), timeout=15)
        data = response.json()
    except Exception as exc:
        return {"ok": False, "error": f"请求异常：{exc}"}

    payload = data.get("data") if isinstance(data, dict) else {}
    if data.get("status_code") == 200 and payload.get("sms_captcha_key"):
        return {"ok": True, "sms_captcha_key": payload["sms_captcha_key"]}
    return {"ok": False, "error": str(data.get("message") or "滑块验证失败")}


def send_sms(phone, device_id, sms_captcha_key):
    body = {
        "phone": phone,
        "type": "login",
        "device_id": device_id,
        "sms_captcha_key": sms_captcha_key
    }
    secret = settings_store.get_sign_secret() or SMS_SIGN_SECRET

    # 与小程序 GatewaySmsSignSDK 保持一致：
    # signingString = secretKey + timestamp + nonce + METHOD + path + query + body
    # signature = sha256(signingString)
    body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    timestamp = str(int(time.time()))
    nonce = f"sms_{_rand(8)}{int(time.time() * 1000)}"
    method = "POST"
    path = "/auth/sms/send"
    query = ""
    raw = secret + timestamp + nonce + method + path + query + body_str
    signature = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    headers = _common_headers()
    headers.update({
        "X-Signature": signature,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-App-ID": "default"
    })

    try:
        response = net_util.request("POST", 
            f"{BASE_URL}/auth/sms/send",
            data=body_str.encode("utf-8"),
            headers=headers,
            timeout=15
        )
        data = response.json()
    except Exception as exc:
        return {"ok": False, "error": f"请求异常：{exc}"}

    if data.get("status_code") == 200:
        return {"ok": True, "message": str(data.get("message") or "验证码发送成功")}
    return {"ok": False, "error": str(data.get("message") or "验证码发送失败")}


def login_with_sms(phone, code, device_id):
    body = {
        "phone": phone,
        "code": code,
        "login_type": "sms_code",
        "device_id": device_id,
        "force_new_account": False,
        "restore_confirm": False,
        "bind_token": ""
    }
    try:
        response = net_util.request("POST", f"{BASE_URL}/auth/login", json=body, headers=_common_headers(), timeout=15)
        data = response.json()
    except Exception as exc:
        return {"ok": False, "error": f"请求异常：{exc}"}

    payload = data.get("data") if isinstance(data, dict) else {}
    if data.get("status_code") == 200 and payload.get("token"):
        return {
            "ok": True,
            "token": payload["token"],
            "user": payload.get("user") or {},
            "phone": phone
        }
    return {"ok": False, "error": str(data.get("message") or "登录失败")}