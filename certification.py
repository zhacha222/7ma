import base64
import json
import random
import requests
import net_util

BASE_URL = "https://newmapi.7mate.cn"
CERT_PATH = "/api/v1/cert"
CERT_SUBMIT_PATH = "/api/v1/certification"


def normalize_token(token):
    token = (token or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def _trace_id():
    return "".join(random.choices("0123456789abcdef", k=32))


def extract_user_id(raw_token):
    raw_token = normalize_token(raw_token)
    if not raw_token:
        return None
    try:
        parts = raw_token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        payload = payload + "=" * (-len(payload) % 4)
        obj = json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
        if isinstance(obj, dict):
            return obj.get("user_id")
    except Exception:
        return None
    return None


def _headers(raw_token, method="GET", user_id=None):
    raw_token = normalize_token(raw_token)
    headers = {
        "Accept": "application/vnd.ws.v1+json",
        "Client": "Wechat_MiniAPP",
        "Phone-Model": "iPhone 13<iPhone14,5>",
        "Phone-Brand": "iPhone",
        "Phone-System": "iOS",
        "Phone-System-Version": "16.5.1",
        "App-Version": "1.3.228",
        "X-App-ID": "default",
        "X-Trace-Id": _trace_id(),
        "Referer": "https://servicewechat.com/wx9a6a1a8407b04c5d/420/page-frame.html",
        "Authorization": "Bearer " + raw_token,
    }
    if method.upper() in ("POST", "PUT", "DELETE"):
        headers["Content-Type"] = "application/json"
    uid = user_id
    if uid is None:
        uid = extract_user_id(raw_token)
    if uid is not None:
        headers["U-User-Id"] = str(uid)
    return headers


def _parse(response):
    try:
        return response.json()
    except Exception:
        return {"status_code": response.status_code, "message": response.text or "无法解析响应"}


def get_cert_status(raw_token):
    empty = {
        "ok": False,
        "error": "",
        "status": None,
        "certified": False,
        "reviewing": False,
        "data": {}
    }
    raw_token = normalize_token(raw_token)
    if not raw_token:
        empty["error"] = "Authorization 为空"
        return empty

    try:
        response = net_util.request("GET", BASE_URL + CERT_PATH, params={"type": 1}, headers=_headers(raw_token, "GET"), timeout=12)
        data = _parse(response)
    except Exception as exc:
        empty["error"] = "请求异常：" + str(exc)
        return empty

    status_code = data.get("status_code") if isinstance(data, dict) else None
    if status_code == 401:
        empty["error"] = "登录失效（401）"
        return empty

    cert = data.get("data") or {} if isinstance(data, dict) else {}
    if not isinstance(cert, dict):
        cert = {}

    status = cert.get("status")
    if status == 1:
        return {
            "ok": True,
            "error": "",
            "status": status,
            "certified": False,
            "reviewing": True,
            "data": cert
        }
    if status == 3:
        return {
            "ok": True,
            "error": "",
            "status": status,
            "certified": True,
            "reviewing": False,
            "data": cert
        }

    # 没有查询到有效记录，或 status 为 0/None 等，都视为未认证
    if isinstance(data, dict) and str(data.get("message") or "").strip() and status_code not in (200, None):
        empty["error"] = str(data.get("message"))
        empty["data"] = cert
        empty["status"] = status
        return empty

    return {
        "ok": True,
        "error": "",
        "status": status,
        "certified": False,
        "reviewing": False,
        "data": cert
    }


def default_payload():
    return {
        "name": "南京大学(鼓楼校区)",
        "area_id": 90,
        "area_type": 1,
        "cert_type": 2,
        "type_text": "工号/学号/一卡通/其他",
        "real_name": "",
        "card_no": "",
        "other": "",
        "cert_photo": "",
        "is_upload_cert_photo": 0,
        "graduate_time_for_cycling_card": 0,
        "cycling_order_face_recognition": 0,
        "graduate_time": "",
        "status": 0,
        "person_type": 1,
        "student_type": "",
        "person_type_name": "学生",
        "student_type_name": "",
        "id": 90,
        "cert_mode": 1,
        "has_train": False,
        "use_must_cert": 0,
        "face_recog_identity_number": "",
        "face_recog_real_name": ""
    }


# 自动认证使用的模板：与抓包提交内容完全一致
AUTO_PAYLOAD = {
    "name": "南京大学(鼓楼校区)",
    "area_id": 90,
    "area_type": 1,
    "cert_type": 2,
    "type_text": "工号/学号/一卡通/其他",
    "real_name": "蔡徐坤",
    "card_no": "",
    "other": "20260831",
    "cert_photo": "",
    "is_upload_cert_photo": 0,
    "graduate_time_for_cycling_card": 0,
    "cycling_order_face_recognition": 0,
    "graduate_time": "",
    "status": 0,
    "person_type": 1,
    "student_type": "",
    "person_type_name": "学生",
    "student_type_name": "",
    "id": 90,
    "cert_mode": 1,
    "has_train": False,
    "use_must_cert": 0,
    "face_recog_identity_number": "",
    "face_recog_real_name": ""
}


def submit_certification(raw_token, payload):
    raw_token = normalize_token(raw_token)
    if not raw_token:
        return {"ok": False, "error": "Authorization 为空", "message": "", "data": {}}

    body = default_payload()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in body:
                body[key] = value

    # 保持与小程序提交逻辑一致：id 与 area_id 相同
    body["id"] = body.get("area_id")

    try:
        response = net_util.request("POST", BASE_URL + CERT_SUBMIT_PATH, headers=_headers(raw_token, "POST"), json=body, timeout=15)
        data = _parse(response)
    except Exception as exc:
        return {"ok": False, "error": "请求异常：" + str(exc), "message": "", "data": {}}

    status_code = data.get("status_code") if isinstance(data, dict) else None
    message = str(data.get("message") or "") if isinstance(data, dict) else ""
    if status_code == 200:
        return {"ok": True, "error": "", "message": message or "提交成功", "data": data.get("data") if isinstance(data, dict) else {}}
    if status_code == 401:
        return {"ok": False, "error": "登录失效（401）", "message": message, "data": {}}
    return {"ok": False, "error": message or "提交失败", "message": message, "data": data.get("data") if isinstance(data, dict) else {}}

