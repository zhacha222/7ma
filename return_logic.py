import hashlib
import time
import requests
import net_util

BASE_URL = "https://newmapi.7mate.cn"


def md5_hash(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def build_headers(authorization):
    return {
        "Authorization": authorization,
        "Content-Type": "application/json"
    }


def fetch_car_authority(authorization):
    """返回 {ok, unauthorized_code, order_sn, status_code, error}"""
    try:
        response = net_util.request("GET", 
            f"{BASE_URL}/api/user/car_authority",
            headers={"Authorization": authorization},
            timeout=10
        )
        if response.status_code != 200:
            return {
                "ok": False,
                "status_code": response.status_code,
                "unauthorized_code": None,
                "order_sn": "",
                "error": f"HTTP {response.status_code}"
            }
        data = response.json()
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "unauthorized_code": None,
            "order_sn": "",
            "error": f"请求异常：{exc}"
        }

    inner = data.get("data") or {} if isinstance(data, dict) else {}
    if not isinstance(inner, dict):
        inner = {}
    order = inner.get("order") or {} if isinstance(inner.get("order"), dict) else {}
    return {
        "ok": True,
        "status_code": response.status_code,
        "unauthorized_code": inner.get("unauthorized_code"),
        "order_sn": order.get("order_sn") or "",
        "error": ""
    }


def return_bike(authorization, order_sn):
    """执行还车上报。返回 {ok, status_code, error}"""
    payload = {
        "back_type": md5_hash(f"{order_sn}:back_type:2"),
        "latitude": "34.367498",
        "longitude": "108.892286",
        "lock_status": md5_hash(f"{order_sn}:lock_status:1"),
        "action_type": md5_hash(f"{order_sn}:action_type:3"),
        "remark": "检测到骑行已结束，自动还车",
        "parking": ""
    }
    try:
        response = net_util.request("POST", 
            f"{BASE_URL}/api/order/car_notification",
            headers=build_headers(authorization),
            json=payload,
            timeout=15
        )
        if response.status_code == 200:
            return {"ok": True, "status_code": 200, "error": ""}
        return {"ok": False, "status_code": response.status_code, "error": response.text or f"HTTP {response.status_code}"}
    except Exception as exc:
        return {"ok": False, "status_code": None, "error": f"请求异常：{exc}"}


def ensure_return(authorization, deadline_seconds=60, interval=3.0):
    """解锁后持续监控还车状态一分钟。

    每间隔 interval 秒检查一次是否存在进行中订单（unauthorized_code == 6）。
    一旦检测到订单立即尝试还车并复核；即使还车成功，仍继续监控满一分钟，
    防止“假性还车”（服务端先报成功、随后又出现订单）导致超过一分钟被扣费。
    """
    deadline = time.time() + deadline_seconds
    attempts = 0
    return_attempts = 0
    confirmed_returns = 0
    order_sn_seen = ""
    saw_active = False

    while time.time() < deadline:
        attempts += 1
        authority = fetch_car_authority(authorization)
        if authority.get("ok") and authority.get("unauthorized_code") == 6:
            saw_active = True
            order_sn = authority.get("order_sn") or ""
            if order_sn:
                order_sn_seen = order_sn
                report = return_bike(authorization, order_sn)
                return_attempts += 1
                if report.get("ok"):
                    # 上报成功后再复核一次，但即使复核通过也继续监控到窗口结束
                    verify = fetch_car_authority(authorization)
                    if verify.get("ok") and verify.get("unauthorized_code") != 6:
                        confirmed_returns += 1

        # 无论是否已还车成功，都继续监控满一分钟
        time.sleep(interval)

    # 窗口结束前做最后一次确认；若仍存在订单，再尝试最后一次还车
    final = fetch_car_authority(authorization)
    still_active = bool(final.get("ok") and final.get("unauthorized_code") == 6)
    if still_active:
        last_order_sn = final.get("order_sn") or order_sn_seen
        if last_order_sn:
            report = return_bike(authorization, last_order_sn)
            return_attempts += 1
            if report.get("ok"):
                verify = fetch_car_authority(authorization)
                still_active = bool(verify.get("ok") and verify.get("unauthorized_code") == 6)

    if still_active:
        return {
            "ok": False,
            "returned": False,
            "message": f"监控 {deadline_seconds} 秒后仍存在进行中订单，请立即手动还车避免扣费",
            "attempts": attempts,
            "return_attempts": return_attempts,
            "order_sn": order_sn_seen or ""
        }

    if not saw_active and not confirmed_returns:
        return {
            "ok": True,
            "returned": False,
            "message": "监控一分钟内未检测到进行中订单，无需还车",
            "attempts": attempts,
            "return_attempts": return_attempts,
            "order_sn": order_sn_seen or ""
        }

    return {
        "ok": True,
        "returned": True,
        "message": "还车成功，已持续监控一分钟确认无进行中订单",
        "attempts": attempts,
        "return_attempts": return_attempts,
        "order_sn": order_sn_seen or ""
    }
