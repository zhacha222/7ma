import hmac
import hashlib
import base64
import time
import urllib.parse
import threading
import requests

import settings_store

EVENT_KEYS = {
    "login": "notify_login",
    "order": "notify_order",
    "points": "notify_points",
    "account": "notify_account"
}

CHANNELS = [
    "none", "telegram", "dingtalk", "wecom", "feishu", "serverchan",
    "pushplus", "bark", "qqbot", "ntfy", "gotify", "custom"
]

CHANNEL_LABELS = {
    "none": "不启用",
    "telegram": "Telegram",
    "dingtalk": "钉钉",
    "wecom": "企业微信",
    "feishu": "飞书",
    "serverchan": "Server酱",
    "pushplus": "PushPlus",
    "bark": "Bark",
    "qqbot": "QQ机器人",
    "ntfy": "ntfy",
    "gotify": "Gotify",
    "custom": "自定义 Webhook"
}


def _text(title, content):
    text = (title or "").strip()
    if content:
        text = f"{text}\n{content}" if text else content
    return text


def _send_telegram(cfg, title, content):
    token = (cfg.get("bot_token") or "").strip()
    chat_id = (cfg.get("chat_id") or "").strip()
    if not token or not chat_id:
        return False, "Telegram 缺少 bot_token 或 chat_id"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": _text(title, content)}, timeout=10)
    try:
        data = r.json()
    except ValueError:
        data = {}
    return bool(data.get("ok")), str(data.get("description") or f"HTTP {r.status_code}")


def _send_dingtalk(cfg, title, content):
    webhook = (cfg.get("webhook") or "").strip()
    if not webhook:
        return False, "钉钉缺少 webhook"
    payload = {"msgtype": "text", "text": {"content": _text(title, content)}}
    secret = (cfg.get("secret") or "").strip()
    url = webhook
    if secret:
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        sep = "&" if "?" in webhook else "?"
        url = f"{webhook}{sep}timestamp={timestamp}&sign={sign}"
    r = requests.post(url, json=payload, timeout=10)
    try:
        data = r.json()
    except ValueError:
        data = {}
    ok = str(data.get("errcode", "0")) == "0" or r.status_code == 200
    return ok, str(data.get("errmsg") or f"HTTP {r.status_code}")


def _send_wecom(cfg, title, content):
    webhook = (cfg.get("webhook") or "").strip()
    if not webhook:
        return False, "企业微信缺少 webhook"
    r = requests.post(webhook, json={"msgtype": "text", "text": {"content": _text(title, content)}}, timeout=10)
    try:
        data = r.json()
    except ValueError:
        data = {}
    ok = str(data.get("errcode")) == "0"
    return ok, str(data.get("errmsg") or f"HTTP {r.status_code}")


def _send_feishu(cfg, title, content):
    webhook = (cfg.get("webhook") or "").strip()
    if not webhook:
        return False, "飞书缺少 webhook"
    r = requests.post(webhook, json={"msg_type": "text", "content": {"text": _text(title, content)}}, timeout=10)
    try:
        data = r.json()
    except ValueError:
        data = {}
    ok = data.get("code", 0) == 0 or data.get("StatusCode", r.status_code) == 0
    return ok, str(data.get("msg") or f"HTTP {r.status_code}")


def _send_serverchan(cfg, title, content):
    sendkey = (cfg.get("sendkey") or "").strip()
    if not sendkey:
        return False, "Server酱缺少 SendKey"
    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    r = requests.post(url, data={"title": title, "desp": content or ""}, timeout=10)
    try:
        data = r.json()
    except ValueError:
        data = {}
    ok = data.get("code") == 0 if data else r.status_code == 200
    return ok, str(data.get("message") or f"HTTP {r.status_code}")


def _send_pushplus(cfg, title, content):
    token = (cfg.get("token") or "").strip()
    if not token:
        return False, "PushPlus 缺少 token"
    payload = {"token": token, "title": title, "content": content or "", "template": "txt"}
    if (cfg.get("topic") or "").strip():
        payload["topic"] = cfg["topic"].strip()
    r = requests.post("https://www.pushplus.plus/send", json=payload, timeout=10)
    try:
        data = r.json()
    except ValueError:
        data = {}
    ok = data.get("code") == 200 if data else r.status_code == 200
    return ok, str(data.get("msg") or f"HTTP {r.status_code}")


def _send_bark(cfg, title, content):
    key = (cfg.get("key") or "").strip()
    if not key:
        return False, "Bark 缺少 Key"
    server = (cfg.get("server") or "https://api.day.app").strip().rstrip("/")
    url = f"{server}/{urllib.parse.quote(key)}/{urllib.parse.quote(title)}/{urllib.parse.quote(content or '')}"
    r = requests.get(url, timeout=10)
    try:
        data = r.json()
    except ValueError:
        data = {}
    ok = r.status_code == 200 and data.get("code") != 400
    return ok, str(data.get("message") or f"HTTP {r.status_code}")


def _send_qqbot(cfg, title, content):
    base_url = (cfg.get("base_url") or "").strip().rstrip("/")
    target_type = (cfg.get("target_type") or "private").strip()
    target_id = (cfg.get("target_id") or "").strip()
    if not base_url or not target_id:
        return False, "QQ机器人缺少 API 地址或接收对象"
    action = "send_group_msg" if target_type == "group" else "send_private_msg"
    url = f"{base_url}/{action}"
    field = "group_id" if target_type == "group" else "user_id"
    try:
        target_id_value = int(target_id)
    except ValueError:
        target_id_value = target_id
    payload = {field: target_id_value, "message": _text(title, content)}
    headers = {"Content-Type": "application/json"}
    token = (cfg.get("token") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.post(url, json=payload, headers=headers, timeout=10)
    try:
        data = r.json()
    except ValueError:
        data = {}
    ok = data.get("status") in ("ok", "async") or data.get("retcode") in (0, "0")
    return ok, str(data.get("wording") or data.get("message") or f"HTTP {r.status_code}")


def _send_ntfy(cfg, title, content):
    topic = (cfg.get("topic") or "").strip()
    if not topic:
        return False, "ntfy 缺少 topic"
    server = (cfg.get("server") or "https://ntfy.sh").strip().rstrip("/")
    headers = {"Title": title or "通知"}
    token = (cfg.get("token") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.post(f"{server}/{topic}", data=(content or "").encode("utf-8"), headers=headers, timeout=10)
    return r.status_code == 200, f"HTTP {r.status_code}"


def _send_gotify(cfg, title, content):
    server = (cfg.get("server") or "").strip().rstrip("/")
    token = (cfg.get("token") or "").strip()
    if not server or not token:
        return False, "Gotify 缺少 server 或 token"
    r = requests.post(f"{server}/message?token={token}", json={"title": title, "message": content or "", "priority": 5}, timeout=10)
    try:
        data = r.json()
    except ValueError:
        data = {}
    ok = data.get("id") is not None or r.status_code == 200
    return ok, str(data.get("errorDescription") or f"HTTP {r.status_code}")


def _send_custom(cfg, title, content):
    url = (cfg.get("url") or "").strip()
    if not url:
        return False, "自定义 Webhook 缺少 URL"
    payload = {"title": title, "content": content or "", "text": _text(title, content)}
    headers = {"Content-Type": "application/json"}
    token = (cfg.get("token") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.post(url, json=payload, headers=headers, timeout=10)
    return r.status_code < 400, f"HTTP {r.status_code}"


PROVIDERS = {
    "telegram": _send_telegram,
    "dingtalk": _send_dingtalk,
    "wecom": _send_wecom,
    "feishu": _send_feishu,
    "serverchan": _send_serverchan,
    "pushplus": _send_pushplus,
    "bark": _send_bark,
    "qqbot": _send_qqbot,
    "ntfy": _send_ntfy,
    "gotify": _send_gotify,
    "custom": _send_custom
}


def _send_one(binding, title, content):
    """发送到单条绑定，并更新该绑定的状态。"""
    binding_id = binding.get("id")
    channel = (binding.get("channel") or "none").strip()
    provider = PROVIDERS.get(channel)
    if not provider:
        ok, message = False, f"不支持的渠道 {channel}"
    else:
        try:
            ok, message = provider(binding.get("config") or {}, title, content)
        except Exception as exc:
            ok, message = False, f"发送异常：{exc}"
    if binding_id:
        settings_store.set_binding_status(binding_id, ok, message)
    return {"channel": channel, "ok": ok, "message": message}


def send(event, title, content=""):
    notification = settings_store.get_notification()
    toggle_key = EVENT_KEYS.get(event)
    if toggle_key and notification.get(toggle_key) is False:
        return {"ok": False, "skipped": True, "message": f"事件 {event} 已关闭推送"}

    bindings = [b for b in settings_store.get_bindings() if b.get("enabled", True)]
    if not bindings:
        return {"ok": False, "skipped": True, "message": "尚未绑定可用通知渠道"}

    results = []
    for binding in bindings:
        results.append(_send_one(binding, title, content))

    ok = bool(results) and all(item["ok"] for item in results)
    message = "；".join(f"[{item['channel']}] {item['message']}" for item in results)
    return {"ok": ok, "skipped": False, "message": message, "results": results}


def send_test(binding_id):
    """发送测试消息到指定绑定并更新状态。"""
    binding = settings_store.get_binding(binding_id)
    if not binding:
        return {"ok": False, "message": "绑定不存在"}
    result = _send_one(binding, "7MA 测试通知", "这是一条测试消息，收到表示通知配置成功。")
    result["binding_id"] = binding_id
    return result


def send_async(event, title, content=""):
    def worker():
        try:
            send(event, title, content)
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()
