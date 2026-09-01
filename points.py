import requests
import net_util
import account_profile_store
import time
from datetime import datetime, timedelta
import points_store

BASE_URL = "https://newmapi.7mate.cn"
REFERER = "https://servicewechat.com/wx9a6a1a8407b04c5d/143/page-frame.html"

TASK_SIGNIN = "每日签到"
TASK_EXTRA_AD = "签到后看广告"
TASK_AD = "看广告得积分"
EXCHANGE_ITEM_ID = 49
EXCHANGE_POINTS_REQUIRED = 188


def normalize_token(token):
    token = (token or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def mask_token(token):
    token = normalize_token(token)
    if len(token) <= 14:
        return token
    return token[:8] + "..." + token[-4:]


def _get_headers(raw_token):
    return {
        "Host": "newmapi.7mate.cn",
        "Authorization": f"Bearer {raw_token}",
        "Referer": REFERER,
        "Content-Type": "application/json",
        "Accept": "application/vnd.ws.v1+json"
    }


def _post_headers(raw_token):
    headers = _get_headers(raw_token)
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    return headers


def _parse_json(response):
    try:
        return response.json()
    except Exception:
        return {"status_code": response.status_code, "message": response.text or "无法解析响应"}


def _empty_info():
    return {
        "ok": False,
        "error": "",
        "phone": "",
        "show_phone": "",
        "user_id": None,
        "username": "",
        "school_name": "",
        "register_time": "",
        "points": None
    }


def fetch_user_info(raw_token):
    if not raw_token:
        info = _empty_info()
        info["error"] = "Authorization 为空"
        return info

    try:
        response = net_util.request("GET", f"{BASE_URL}/api/v1/user", headers=_get_headers(raw_token), timeout=10)
        data = _parse_json(response)
    except Exception as exc:
        info = _empty_info()
        info["error"] = f"请求异常：{exc}"
        return info

    user = data.get("data") or {} if isinstance(data, dict) else {}
    if isinstance(data, dict) and user and (user.get("id") is not None or user.get("phone")):
        return {
            "ok": True,
            "error": "",
            "phone": user.get("phone") or "",
            "show_phone": user.get("show_phone") or user.get("phone") or "",
            "user_id": user.get("id"),
            "username": user.get("username") or user.get("name") or "",
            "school_name": user.get("school_name") or "",
            "register_time": user.get("register_time") or "",
            "points": user.get("points")
        }

    error = ""
    if isinstance(data, dict):
        if data.get("status_code") == 401:
            error = "登录失效（401）"
        else:
            error = str(data.get("message") or "未知错误")

    info = _empty_info()
    info["error"] = error or "未知错误"
    return info


def fetch_credit_scores(raw_token):
    empty = {
        "ok": False,
        "error": "",
        "credit_scores": None,
        "update_time": "",
        "credit_score_level": None
    }
    if not raw_token:
        empty["error"] = "Authorization 为空"
        return empty

    try:
        response = net_util.request("GET", f"{BASE_URL}/api/v1/user/credit_scores", headers=_get_headers(raw_token), timeout=10)
        data = _parse_json(response)
    except Exception as exc:
        empty["error"] = f"请求异常：{exc}"
        return empty

    credit = data.get("data") or {} if isinstance(data, dict) else {}
    if isinstance(data, dict) and credit and "credit_scores" in credit:
        return {
            "ok": True,
            "error": "",
            "credit_scores": credit.get("credit_scores"),
            "update_time": credit.get("update_time") or "",
            "credit_score_level": credit.get("credit_score_level")
        }

    error = ""
    if isinstance(data, dict):
        if data.get("status_code") == 401:
            error = "登录失效（401）"
        else:
            error = str(data.get("message") or "未知错误")
    empty["error"] = error or "未知错误"
    return empty


def exchange_ride_card(raw_token, item_id=EXCHANGE_ITEM_ID):
    try:
        headers = _get_headers(raw_token)
        response = net_util.request("POST", f"{BASE_URL}/api/v1/points/exchange", headers=headers, json={"id": item_id}, timeout=15)
        data = _parse_json(response)
    except Exception as exc:
        return {"ok": False, "error": f"请求异常：{exc}", "message": ""}

    status = data.get("status_code") if isinstance(data, dict) else None
    message = data.get("message") if isinstance(data, dict) else ""
    if status == 200:
        return {"ok": True, "error": "", "message": message or "兑换成功"}
    return {"ok": False, "error": message or "兑换失败", "message": message}


def auto_exchange_ride_card(raw_token, max_cards=20):
    result = {"ok": False, "error": "", "exchanged": 0, "latest_points": None}

    info = fetch_user_info(raw_token)
    if not info.get("ok"):
        result["error"] = info.get("error") or "登录失败"
        return result

    points = info.get("points")
    result["latest_points"] = points
    if points is None:
        result["error"] = "未能读取当前积分"
        return result

    if points < EXCHANGE_POINTS_REQUIRED:
        result["error"] = f"积分不足（当前 {points}，每张需 {EXCHANGE_POINTS_REQUIRED}）"
        return result

    while points is not None and points >= EXCHANGE_POINTS_REQUIRED and result["exchanged"] < max_cards:
        exchange = exchange_ride_card(raw_token)
        if not exchange.get("ok"):
            result["error"] = exchange.get("error") or "兑换失败"
            break

        result["exchanged"] += 1
        time.sleep(1)

        info = fetch_user_info(raw_token)
        if info.get("ok"):
            points = info.get("points")
            result["latest_points"] = points
        else:
            points = None

    if result["exchanged"] > 0:
        result["ok"] = True
        result["error"] = ""

    if info and info.get("ok"):
        points_store.set_cached_info(raw_token, info)
    return result


def fetch_cycling_cards(raw_token):
    empty = {"ok": False, "error": "", "cards": [], "total_cards": 0}
    if not raw_token:
        empty["error"] = "Authorization 为空"
        return empty

    try:
        response = net_util.request("GET", f"{BASE_URL}/api/v1/user/cycling_card/lists", headers=_get_headers(raw_token), timeout=10)
        data = _parse_json(response)
    except Exception as exc:
        empty["error"] = f"请求异常：{exc}"
        return empty

    card_data = data.get("data") or {} if isinstance(data, dict) else {}
    cards = []
    if isinstance(card_data, dict):
        for model_key in ("carmodel1", "carmodel2", "carmodel3"):
            for item in card_data.get(model_key) or []:
                if not isinstance(item, dict):
                    continue
                cards.append({
                    "id": item.get("id"),
                    "code": item.get("code"),
                    "name": item.get("name"),
                    "type_name": item.get("type_name"),
                    "carmodel_name": item.get("carmodel_name"),
                    "times": item.get("times"),
                    "remaining": item.get("total_remaining_free_times"),
                    "each_free_time": item.get("each_free_time"),
                    "state": item.get("state"),
                    "desc": item.get("desc")
                })

    return {"ok": True, "error": "", "cards": cards, "total_cards": len(cards)}


def get_account_assets(tokens, force_refresh=False):
    assets = []
    for index, token in enumerate(tokens):
        raw_token = normalize_token(token)
        if not raw_token:
            continue

        info = None if force_refresh else points_store.get_cached_info(raw_token)
        if info is None:
            info = fetch_user_info(raw_token)
            points_store.set_cached_info(raw_token, info)

        # 保存/维护本地档案：账号有效时持久化姓名、手机号；失效时标记并记录
        if info.get("ok"):
            account_profile_store.save_profile(raw_token, info)
            account_profile_store.clear_invalid(raw_token)
        else:
            became_invalid = account_profile_store.mark_invalid(raw_token, info.get("error") or "账号失效")
            if became_invalid:
                profile = account_profile_store.get_profile(raw_token) or {}
                try:
                    import notify
                    notify.send_async('account', '账号失效通知', (
                        f"账号已失效：{profile.get('phone') or profile.get('username') or mask_token(raw_token)}\n"
                        f"原因：{info.get('error') or '账号失效'}\n"
                        f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    ))
                except Exception:
                    pass

        credit = None if force_refresh else points_store.get_cached_credit(raw_token)
        if credit is None:
            if info.get("ok"):
                credit = fetch_credit_scores(raw_token)
            else:
                credit = {"ok": False, "error": info.get("error") or "账户信息不可用", "credit_scores": None, "update_time": "", "credit_score_level": None}
            points_store.set_cached_credit(raw_token, credit)

        cycling = None if force_refresh else points_store.get_cached_cycling(raw_token)
        if cycling is None:
            if info.get("ok"):
                cycling = fetch_cycling_cards(raw_token)
            else:
                cycling = {"ok": False, "error": info.get("error") or "账户信息不可用", "cards": [], "total_cards": 0}
            points_store.set_cached_cycling(raw_token, cycling)

        assets.append({
            "index": index,
            "token": raw_token,
            "masked": mask_token(raw_token),
            "info": info,
            "credit": credit,
            "cycling": cycling,
            "cards": cycling.get("cards", []),
            "cards_count": cycling.get("total_cards", 0)
        })
    return assets


def run_account_tasks(raw_token):
    result = {
        "ok": False,
        "error": "",
        "info": {"phone": "", "show_phone": "", "user_id": None, "username": "", "school_name": "", "register_time": "", "points": None},
        "tasks": [],
        "total_gain": 0,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    info = fetch_user_info(raw_token)
    result["info"] = info
    if not info.get("ok"):
        result["error"] = info.get("error") or "登录失败"
        points_store.record_last_run(raw_token, result)
        return result

    total_gain = 0
    tasks = []

    # 1. 每日签到，+1
    signin_task = {"name": TASK_SIGNIN, "estimate": 1, "gain": 0, "status": "pending", "detail": ""}
    try:
        response = net_util.request("POST", f"{BASE_URL}/api/signin", headers=_post_headers(raw_token), data="", timeout=10)
        data = _parse_json(response)
    except Exception as exc:
        data = {"status_code": None, "message": f"请求异常：{exc}"}

    status = data.get("status_code") if isinstance(data, dict) else None
    if status == 200:
        signin_task["gain"] = 1
        signin_task["status"] = "done"
        signin_task["detail"] = "签到成功，+1"
    elif status == 406:
        signin_task["gain"] = 0
        signin_task["status"] = "watched"
        signin_task["detail"] = "今日已签到"
    elif status == 401:
        signin_task["status"] = "failed"
        signin_task["detail"] = "登录失效"
        tasks.append(signin_task)
        result["tasks"] = tasks
        result["total_gain"] = total_gain
        result["error"] = "签到登录失效"
        points_store.record_last_run(raw_token, result)
        return result
    else:
        signin_task["status"] = "failed"
        signin_task["detail"] = str(data.get("message") or "未知错误") if isinstance(data, dict) else "未知错误"
        tasks.append(signin_task)
        result["tasks"] = tasks
        result["total_gain"] = total_gain
        result["error"] = signin_task["detail"]
        points_store.record_last_run(raw_token, result)
        return result

    total_gain += signin_task["gain"]
    tasks.append(signin_task)
    time.sleep(0.5)

    # 2. 签到后看广告，+7
    extra_task = {"name": TASK_EXTRA_AD, "estimate": 7, "gain": 0, "status": "pending", "detail": ""}
    try:
        response = net_util.request("POST", f"{BASE_URL}/api/adResult", headers=_post_headers(raw_token), data="is_sign=1&finish=1", timeout=10)
        data = _parse_json(response)
    except Exception as exc:
        data = {"status_code": None, "message": f"请求异常：{exc}"}

    status = data.get("status_code") if isinstance(data, dict) else None
    if status == 200:
        extra_task["gain"] = 7
        extra_task["status"] = "done"
        extra_task["detail"] = "签到额外任务完成，+7"
    elif status == 512:
        extra_task["gain"] = 0
        extra_task["status"] = "watched"
        extra_task["detail"] = "今日已观看"
    elif status == 401:
        extra_task["status"] = "failed"
        extra_task["detail"] = "登录失效"
        tasks.append(extra_task)
        result["tasks"] = tasks
        result["total_gain"] = total_gain
        result["error"] = "签到广告登录失效"
        points_store.record_last_run(raw_token, result)
        return result
    else:
        extra_task["status"] = "failed"
        extra_task["detail"] = str(data.get("message") or "未知错误") if isinstance(data, dict) else "未知错误"

    total_gain += extra_task["gain"]
    tasks.append(extra_task)

    # 3. 看广告，最多 10 次，每次 +1
    ad_task = {"name": TASK_AD, "estimate": 10, "gain": 0, "status": "pending", "detail": ""}
    ad_success_count = 0
    ad_total_gain = 0
    if extra_task["status"] in ("done", "watched"):
        for _ in range(10):
            try:
                response = net_util.request("POST", f"{BASE_URL}/api/adResult", headers=_post_headers(raw_token), data="finish=1", timeout=10)
                data = _parse_json(response)
            except Exception as exc:
                data = {"status_code": None, "message": f"请求异常：{exc}"}

            status = data.get("status_code") if isinstance(data, dict) else None
            if status == 200:
                ad_success_count += 1
                ad_total_gain += 1
            elif status == 512:
                break
            elif status == 401:
                break
            else:
                break
            time.sleep(0.5)

        ad_task["gain"] = ad_total_gain
        if ad_success_count >= 10:
            ad_task["status"] = "done"
            ad_task["detail"] = "已完成全部 10 次广告，+10"
        elif ad_success_count > 0:
            ad_task["status"] = "partial"
            ad_task["detail"] = f"完成 {ad_success_count} 次广告，+{ad_total_gain}"
        else:
            ad_task["status"] = "failed"
            ad_task["detail"] = "今日广告任务未获得积分"
    else:
        ad_task["status"] = "skipped"
        ad_task["detail"] = "签到广告未完成，跳过广告任务"

    total_gain += ad_task["gain"]
    tasks.append(ad_task)

    # 重新拉取一次账户信息，拿到最新积分
    latest_info = fetch_user_info(raw_token)
    result["info"] = latest_info

    result["ok"] = True
    result["error"] = ""
    result["tasks"] = tasks
    result["total_gain"] = total_gain
    points_store.record_last_run(raw_token, result)
    return result


def _default_tasks():
    return [
        {"name": TASK_SIGNIN, "estimate": 1, "gain": None, "status": "pending", "detail": "待完成"},
        {"name": TASK_EXTRA_AD, "estimate": 7, "gain": None, "status": "pending", "detail": "待完成"},
        {"name": TASK_AD, "estimate": 10, "gain": None, "status": "pending", "detail": "待完成"}
    ]


def overview_tasks(last_run):
    if last_run and last_run.get("tasks"):
        return last_run["tasks"], last_run.get("total_gain")
    return _default_tasks(), None


def next_run_display(schedule):
    if not isinstance(schedule, dict) or not schedule.get("enabled"):
        return ""
    run_time = schedule.get("time") or "08:10"
    try:
        now = datetime.now()
        target = datetime.strptime(f"{now.date().isoformat()} {run_time}", "%Y-%m-%d %H:%M")
        if target <= now:
            target += timedelta(days=1)
        return target.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return f"每天 {run_time}"


def get_accounts_overview(tokens, force_refresh=False):
    accounts = []
    for index, token in enumerate(tokens):
        raw_token = normalize_token(token)
        if not raw_token:
            continue

        info = None if force_refresh else points_store.get_cached_info(raw_token)
        if info is None:
            info = fetch_user_info(raw_token)
            points_store.set_cached_info(raw_token, info)

        credit = None if force_refresh else points_store.get_cached_credit(raw_token)
        if credit is None:
            if info.get("ok"):
                credit = fetch_credit_scores(raw_token)
            else:
                credit = {"ok": False, "error": info.get("error") or "账户信息不可用", "credit_scores": None, "update_time": "", "credit_score_level": None}
            points_store.set_cached_credit(raw_token, credit)

        last_run = points_store.get_last_run(raw_token)
        tasks, last_gain = overview_tasks(last_run)
        schedule = points_store.get_schedule(raw_token)

        cycling = None if force_refresh else points_store.get_cached_cycling(raw_token)
        if cycling is None:
            if info.get("ok"):
                cycling = fetch_cycling_cards(raw_token)
            else:
                cycling = {"ok": False, "error": info.get("error") or "账户信息不可用", "cards": [], "total_cards": 0}
            points_store.set_cached_cycling(raw_token, cycling)

        accounts.append({
            "index": index,
            "masked": mask_token(raw_token),
            "info": info,
            "credit": credit,
            "cycling": cycling,
            "cards": cycling.get("cards", []),
            "cards_count": cycling.get("total_cards", 0),
            "scheduled": schedule.get("enabled"),
            "schedule_time": schedule.get("time"),
            "next_run": next_run_display(schedule),
            "tasks": tasks,
            "last_gain": last_gain,
            "last_time": (last_run or {}).get("time", "")
        })
    return accounts
