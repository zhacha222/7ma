from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime
from functools import wraps
import requests
import time
import hashlib
import os
import glob
import re
import random
import logging
import threading
from logging.handlers import TimedRotatingFileHandler
from scheduler import main as start_scheduler
import auth_store
import account_profile_store
import settings_store
import points
import points_store
import points_scheduler
import phone_login
import device_store
import certification
import return_logic
import notify
import net_util
import maintenance


# 创建 Flask 应用对象
app = Flask(__name__)

# 启用调试模式（仅用于开发和调试）
app.debug = False
@app.after_request
def _no_cache(response):
    """前端页面即时刷新，避免浏览器缓存旧版（导致点击下单仍是旧逻辑）。"""
    if request.path in ('/', '/process') or response.mimetype == 'text/html':
        response.headers.setdefault('Cache-Control', 'no-store, no-cache, must-revalidate')
        response.headers.setdefault('Pragma', 'no-cache')
        response.headers.setdefault('Expires', '0')
    if request.path.startswith('/api/'):
        response.headers.setdefault('Access-Control-Allow-Origin', '*')
        response.headers.setdefault('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        response.headers.setdefault('Access-Control-Allow-Headers', 'Content-Type, X-API-Key')
        response.headers.setdefault('Access-Control-Max-Age', '86400')
    return response


@app.before_request
def _handle_api_preflight():
    """跨域预检：配套 App 从其它地址调用远程 API 时，浏览器会先发送 OPTIONS。"""
    if request.method == 'OPTIONS' and request.path.startswith('/api/'):
        return ('', 204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, X-API-Key',
            'Access-Control-Max-Age': '86400',
        })




def _load_secret_key():
    path = os.path.join('config', 'secret_key.txt')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as handle:
            key = handle.read().strip()
            if key:
                return key
    os.makedirs('config', exist_ok=True)
    key = os.urandom(24).hex()
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(key)
    return key


app.secret_key = _load_secret_key()


# 确保 "logs" 文件夹存在
logs_folder = 'logs'
os.makedirs(logs_folder, exist_ok=True)
# 创建一个日志记录器
app_logger = logging.getLogger('app')
# 配置日志级别
app_logger.setLevel(logging.INFO)
# 获取当前日期和时间的字符串，用作日志文件名
current_datetime = datetime.now().strftime("%Y-%m-%d")
app_filename = os.path.join(logs_folder, f'order_{current_datetime}.log')
# 创建一个 TimedRotatingFileHandler 实例，按天轮转日志文件
app_handler = TimedRotatingFileHandler(app_filename, when='midnight', interval=1, backupCount=7, encoding='utf-8')
# 创建日志格式
app_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
app_handler.setFormatter(app_formatter)
# 将处理程序添加到记录器
app_logger.addHandler(app_handler)


def send_request(url, method, body, authorization):
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json"
    }
    response = net_util.request(method, url, headers=headers, json=body, timeout=15)
    return response.json()

def place_order(bike_number, authorization):
    url = "https://newmapi.7mate.cn/api/order"
    method = "POST"
    body = {
        "card_code": "",
        "order_type": 1,
        "car_number": bike_number,
        "latitude": "",
        "price": "",
        "longitude": ""
    }
    result = send_request(url, method, body, authorization)
    return result

def unlock(authorization):
    url = "https://newmapi.7mate.cn/api/car/unlock"
    method = "POST"
    body = {
        "latitude": "34.367498",
        "action_type": 1,
        "longitude": "108.892286"
    }
    result = send_request(url, method, body, authorization)
    return result

def md5Hash(text):
    md5 = hashlib.md5()
    md5.update(text.encode('utf-8'))
    return md5.hexdigest()


# ===================== 工具函数 =====================
def _read_bytes(path):
    with open(path, 'rb') as handle:
        return handle.read()


def _decode_text(data):
    for encoding in ('utf-8', 'gbk'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', errors='replace')


def read_log_file(path, tail=500):
    data = _read_bytes(path)
    text = _decode_text(data)
    lines = text.splitlines()
    if tail and tail > 0:
        lines = lines[-tail:]
    return '\n'.join(lines)


def read_points_log_lines(phone, tail=200):
    path = os.path.join('logs', 'points_scheduler.log')
    if not os.path.exists(path):
        return []
    data = _read_bytes(path)
    text = _decode_text(data)
    lines = [ln for ln in text.splitlines() if phone and phone in ln]
    if tail and len(lines) > tail:
        lines = lines[-tail:]
    return lines


def _order_operation(message):
    """根据日志消息提取操作类型。"""
    if '成功订单' in message:
        return '成功订单'
    if '失败订单' in message:
        return '失败订单'
    if '还车处理' in message:
        return '还车处理'
    if '还车检测异常' in message:
        return '还车异常'
    if '解锁请求异常' in message:
        return '解锁异常'
    if '请求异常' in message:
        return '请求异常'
    return '其他'


_STATUS_RANK = {'成功': 2, '失败': 1, '信息': 0}


def _account_name_map_by_index():
    """把当前 Authorization 列表的 1 基索引映射到账号姓名（来自本地档案）。"""
    mapping = {}
    tokens = auth_store.load_authorizations()
    for i, token in enumerate(tokens, start=1):
        raw_token = points.normalize_token(token) if token else ''
        profile = account_profile_store.get_profile(raw_token) if raw_token else None
        mapping[i] = (profile or {}).get('username') or ''
    return mapping


def read_order_logs():
    rows = []
    _account_name_map = _account_name_map_by_index()
    for path in sorted(glob.glob(os.path.join('logs', 'order_*.log')), reverse=True):
        data = _read_bytes(path)
        text = _decode_text(data)
        for line in text.splitlines():
            parts = line.split(' - ', 2)
            if len(parts) < 3:
                continue
            timestamp, level, message = parts
            if 'bike_number=' not in message:
                continue

            op_type = _order_operation(message)
            if '成功订单' in message:
                status = '成功'
            elif '失败订单' in message:
                status = '失败'
            else:
                status = '信息'

            bike_match = re.search(r'bike_number=([^,\s]*)', message)
            bike_number = bike_match.group(1) if bike_match else ''
            index_match = re.search(r'auth_index=(\d+)', message)
            if index_match:
                auth_index = index_match.group(1)
            else:
                auth_match = re.search(r'Authorization\[(\d+)\]', message)
                auth_index = auth_match.group(1) if auth_match else ''
            name = _account_name_map.get(int(auth_index)) if auth_index.isdigit() else ''
            account_name = name or ''
            account_label = f'账号{auth_index}：{name}' if (auth_index and name) else (f'账号{auth_index}' if auth_index else '—')
            detail = message.replace('--', '').strip()

            rows.append({
                'time': timestamp.strip(),
                'level': level.strip(),
                'status': status,
                'status_rank': _STATUS_RANK.get(status, 0),
                'op_type': op_type,
                'bike': bike_number,
                'auth_index': auth_index,
                'account_label': account_label,
                'account_name': account_name,
                'detail': detail,
                'file': os.path.basename(path),
                'raw': line
            })

    rows.sort(key=lambda item: item['time'], reverse=True)
    return rows


def delete_order_line(filename, raw_line):
    safe_name = os.path.basename(filename)
    if not safe_name or not safe_name.startswith('order_') or not safe_name.endswith('.log'):
        return False
    path = os.path.join('logs', safe_name)
    if not os.path.exists(path):
        return False
    data = _read_bytes(path)
    text = _decode_text(data)
    lines = text.splitlines(keepends=True)
    target = (raw_line or '').rstrip('\r\n')
    removed = False
    new_lines = []
    for current in lines:
        if not removed and current.rstrip('\r\n') == target:
            removed = True
            continue
        new_lines.append(current)
    if removed:
        with open(path, 'w', encoding='utf-8') as handle:
            handle.writelines(new_lines)
    return removed


# ===================== 后台鉴权 =====================
def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('admin_authenticated'):
            return redirect(url_for('admin_login'))
        return view(*args, **kwargs)
    return wrapped


# ===================== 用车前端 =====================
@app.route('/')
def index():
    return render_template('index.html', error=request.args.get('error', ''))

@app.route('/app')
def app_page():
    """配套 App：扫码/手动下单，域名与密钥在前端配置后调用远程 API。"""
    return render_template('app.html')

def start_return_monitor(bike_number, index, total, authorization):
    """后台执行持续一分钟的还车监控，并把结果写入日志和推送通知。"""
    def worker():
        try:
            return_status = return_logic.ensure_return(authorization)
            return_message = return_status.get('message') or ''
            app_logger.info(f'--还车处理: bike_number={bike_number}, auth_index={index}, returned={return_status.get("returned")}, attempts={return_status.get("attempts")}, return_attempts={return_status.get("return_attempts")}, message={return_message}')
        except Exception as exc:
            return_message = f'还车检测异常：{exc}'
            app_logger.warning(f'--还车检测异常: bike_number={bike_number}, error={exc}')

        notify.send_async('order', '还车处理结果', (
            f"单车编号：{bike_number}\n"
            f"Authorization：第 {index}/{total} 个\n"
            f"还车结果：{return_message}\n"
            f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ))

    threading.Thread(target=worker, daemon=True).start()


def _is_trip_conflict(order_result):
    """判断下单返回是否是因为“当前账号存在未完成行程”而失败。

    car_authority 接口在账号已有行程时仍返回 unauthorized_code=0、order_sn 空，
    无法可靠判断；真正可靠的信号是 place_order 返回的“当前有未完成的行程”。
    """
    message = (order_result or {}).get('message') or ''
    return bool(message) and ('未完成的行程' in message or '未完成行程' in message)


def _send_order_fail(bike_number, fail_message, notify_event='order'):
    notify.send_async(notify_event, '用车下单结果', (
        f"单车编号：{bike_number}\n"
        f"结果：{fail_message}\n"
        f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ))
    return {'message': fail_message, 'is_success': False}, False


def _run_order_flow(bike_number, notify_event='order'):
    """下单流程：先尝试下单，用下单结果判断该账号是否有未完成行程。

    - 某账号下单成功 → 开锁并返回成功；
    - 某账号返回“当前有未完成的行程” → 该账号有行程，跳过继续下一个；
    - 某账号其它原因失败 → 直接返回该失败 message；
    - 所有账号都存在未完成行程 → 等待几秒后重试，等有账号还车后再下单（最多两分钟）。
    """
    authorizations = auth_store.load_authorizations()
    if not authorizations:
        return {'message': '后台尚未配置 Authorization，请先到管理后台添加。', 'is_success': False}, False

    total = len(authorizations)
    deadline = time.time() + 120
    last_trip_msg = ''

    while time.time() < deadline:
        all_has_trip = False
        for index, authorization in enumerate(authorizations, start=1):
            if time.time() >= deadline:
                break

            try:
                order_result = place_order(bike_number, authorization)
            except Exception as exc:
                app_logger.warning(f'--Authorization[{index}] 请求异常: bike_number={bike_number}, error={exc}')
                fail_message = f'第 {index}/{total} 个 Authorization 请求异常，已尝试下一个。'
                return _send_order_fail(bike_number, fail_message, notify_event)

            if order_result.get('status_code') == 200 and order_result.get('message') == '下单成功':
                try:
                    unlock_result = unlock(authorization)
                    unlock_message = unlock_result.get('message') or ''
                except Exception as exc:
                    app_logger.warning(f'--解锁请求异常: bike_number={bike_number}, error={exc}')
                    unlock_message = '解锁请求异常'
                    unlock_result = {}

                start_return_monitor(bike_number, index, total, authorization)

                app_logger.info(f'--成功订单: bike_number={bike_number}, auth_index={index}, unlock_result={unlock_message}, return_monitoring=已启动')
                notify.send_async(notify_event, '用车下单/开锁结果', (
                    f"单车编号：{bike_number}\n"
                    f"Authorization：第 {index}/{total} 个\n"
                    f"开锁结果：{unlock_message}\n"
                    f"还车监控：已启动，结果稍后推送\n"
                    f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ))
                return {
                    'message': order_result['message'],
                    'unlock_result': unlock_message,
                    'return_result': '',
                    'is_success': True
                }, True

            if _is_trip_conflict(order_result):
                # 该账号存在未完成行程 → 标记本轮“存在有行程账号”，跳到下一个账号
                all_has_trip = True
                last_trip_msg = f'第 {index} 个账号当前有未完成的行程'
                app_logger.debug(f'--账号[{index}] 有未完成行程: bike_number={bike_number}')
                continue

            # 其它原因失败：直接返回日志 message，不再等待
            fail_message = order_result.get('message') or f'第 {index} 个 Authorization 不可用'
            app_logger.warning(f'--失败订单: bike_number={bike_number}, auth_index={index}, message={fail_message}')
            return _send_order_fail(bike_number, fail_message, notify_event)

        # 所有账号都存在未完成行程 → 等待，等有其它账号还车后再重试
        if all_has_trip and time.time() < deadline:
            time.sleep(3)

    fail_message = last_trip_msg or '所有账号均在忙碌中，未在等待时间内找到可用账号，下单失败'
    return _send_order_fail(bike_number, fail_message, notify_event)


@app.route('/process', methods=['POST'])
def process():
    bike_number = (request.form.get('bike_number') or '').strip()
    if not bike_number:
        return redirect(url_for('index', error='请输入单车编号后再下单'))
    data, _success = _run_order_flow(bike_number)
    return render_template('result.html', data=data)


def _check_api_key():
    return (request.headers.get('X-API-Key') or '').strip() == settings_store.get_api_key()


@app.route('/api/v1/status')
def api_status():
    if not _check_api_key():
        return jsonify(ok=False, error='无效的 API 密钥'), 401
    tokens = auth_store.load_authorizations()
    return jsonify(ok=True, authorizations=len(tokens), time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


@app.route('/api/v1/order', methods=['POST'])
def api_order():
    if not _check_api_key():
        return jsonify(ok=False, error='无效的 API 密钥'), 401
    payload = request.get_json(silent=True) or {}
    bike_number = (payload.get('bike_number') or '').strip()
    if not bike_number:
        return jsonify(ok=False, error='缺少 bike_number 参数'), 400
    data, success = _run_order_flow(bike_number, notify_event='order')
    return jsonify(ok=success, **data)


# ===================== 后台登录 =====================
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_authenticated'):
        return redirect(url_for('admin_accounts'))

    error = ''

    if request.method == 'POST':
        password = request.form.get('password', '')
        if settings_store.verify_password(password):
            session['admin_authenticated'] = True
            notify.send_async('login', '后台登录通知', f"有人登录了后台，时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            return redirect(url_for('admin_accounts'))
        error = '密码错误'

    is_default = settings_store.is_default_password()
    return render_template('admin_login.html', error=error, is_default=is_default, default_password=settings_store.DEFAULT_PASSWORD)

@app.route('/admin/logout', methods=['POST'])
@admin_required
def admin_logout():
    session.pop('admin_authenticated', None)
    return redirect(url_for('admin_login'))


# ===================== 后台页面 =====================
@app.route('/admin')
@admin_required
def admin_home():
    return redirect(url_for('admin_accounts'))

@app.route('/admin/accounts')
@admin_required
def admin_accounts():
    tokens = auth_store.load_authorizations()
    accounts = points.get_account_assets(tokens, force_refresh=(request.args.get('refresh') == '1'))
    force_cert = (request.args.get('refresh') == '1')
    for account in accounts:
        raw_token = account.get('token') or ''
        cert = None if force_cert else points_store.get_cached_cert(raw_token)
        if cert is None:
            cert = certification.get_cert_status(raw_token)
            points_store.set_cached_cert(raw_token, cert)
        account['cert'] = cert
        account['local_profile'] = account_profile_store.get_profile(raw_token) if raw_token else None
        account['is_invalid'] = bool(account['local_profile'] and account['local_profile'].get('invalid'))
    message = request.args.get('message', '')
    error = request.args.get('error', '')
    return render_template('admin_accounts.html', accounts=accounts, message=message, error=error, active='accounts')


def _add_account_with_overwrite(token):
    """添加账号；若本地存在同名/同手机号的已失效账号，则自动覆盖该失效账号。

    返回 (操作描述, 是否发生了覆盖)。
    """
    raw_token = points.normalize_token(token)
    if not raw_token:
        return "", False

    # 拉取账户信息以确定身份（姓名/手机号），并保存本地档案
    info = points.fetch_user_info(raw_token)
    if info.get("ok"):
        account_profile_store.save_profile(raw_token, info)
    else:
        auth_store.add_authorizations([token])
        return "", False

    old_hash = account_profile_store.find_by_identity(raw_token)
    if old_hash:
        tokens = auth_store.load_authorizations()
        new_tokens = []
        replaced = False
        old_label = "历史账号"
        old_profile = None
        for t in tokens:
            rt = points.normalize_token(t)
            if rt and account_profile_store._token_hash(rt) == old_hash:
                new_tokens.append(token)
                replaced = True
                old_profile = account_profile_store.get_profile(rt)
            else:
                new_tokens.append(t)
        if replaced:
            auth_store.save_authorizations(new_tokens)
            if old_profile:
                old_label = ((old_profile.get('username') or '') + ('/' + old_profile.get('phone') if old_profile.get('phone') else '')) or '账号'
            # 新 token 已保存档案，覆盖成功
            return (f"已覆盖失效账号 {old_label}（{info.get('show_phone') or info.get('phone') or ''}）", True)
        # 未找到对应 token（可能已被移除），直接追加
        auth_store.add_authorizations([token])
        return "", False

    auth_store.add_authorizations([token])
    return "", False


def _cert_payload_from_status(cert, info):
    payload = certification.default_payload()
    cert_data = (cert or {}).get('data') if isinstance(cert, dict) else {}
    if not isinstance(cert_data, dict):
        cert_data = {}

    if cert_data.get('school_name'):
        payload['name'] = cert_data['school_name']
    if cert_data.get('school_id') is not None:
        payload['area_id'] = cert_data['school_id']
    if cert_data.get('area_type') is not None:
        payload['area_type'] = cert_data['area_type']
    if cert_data.get('cert_type') is not None:
        payload['cert_type'] = cert_data['cert_type']
    payload['type_text'] = '身份证号' if payload['cert_type'] == 1 else '工号/学号/一卡通/其他'
    if cert_data.get('user_name'):
        payload['real_name'] = cert_data['user_name']
    if cert_data.get('identity_number'):
        payload['card_no'] = cert_data['identity_number']
    if cert_data.get('student_id'):
        payload['other'] = cert_data['student_id']
    if cert_data.get('cert_photo') or cert_data.get('cert_photo_url'):
        payload['cert_photo'] = cert_data.get('cert_photo') or cert_data.get('cert_photo_url') or ''

    info = info if isinstance(info, dict) else {}
    if info.get('ok'):
        if info.get('username') and not payload.get('real_name'):
            payload['real_name'] = info['username']
        if info.get('school_name') and not payload.get('name'):
            payload['name'] = info['school_name']

    payload['id'] = payload['area_id']
    return payload


@app.route('/admin/cert/<int:index>')
@admin_required
def admin_cert(index):
    tokens = auth_store.load_authorizations()
    if not (0 <= index < len(tokens)):
        return redirect(url_for('admin_accounts', error='账户不存在'))
    raw_token = points.normalize_token(tokens[index])
    cert = certification.get_cert_status(raw_token)
    info = points.fetch_user_info(raw_token)
    payload = _cert_payload_from_status(cert, info)
    return render_template(
        'admin_certification.html',
        index=index,
        masked=points.mask_token(raw_token),
        cert=cert,
        info=info,
        payload=payload,
        message=request.args.get('message', ''),
        error=request.args.get('error', ''),
        active='accounts'
    )


@app.route('/admin/cert/<int:index>', methods=['POST'])
@admin_required
def admin_cert_submit(index):
    tokens = auth_store.load_authorizations()
    if not (0 <= index < len(tokens)):
        return redirect(url_for('admin_accounts', error='账户不存在'))
    raw_token = points.normalize_token(tokens[index])

    def _int(name, default):
        value = (request.form.get(name) or '').strip()
        try:
            return int(value) if value != '' else default
        except ValueError:
            return default

    cert_type = _int('cert_type', 2)
    person_type = _int('person_type', 1)
    student_type_value = (request.form.get('student_type') or '').strip()

    person_type_names = {1: '学生', 2: '教职工', 3: '服务保障人员', 4: '其他人员'}
    student_type_names = {1: '本科新生', 2: '研究生新生', 3: '其他'}

    payload = {
        'name': (request.form.get('name') or '').strip(),
        'area_id': _int('area_id', 90),
        'area_type': _int('area_type', 1),
        'cert_type': cert_type,
        'type_text': '身份证号' if cert_type == 1 else '工号/学号/一卡通/其他',
        'real_name': (request.form.get('real_name') or '').strip(),
        'card_no': (request.form.get('card_no') or '').strip(),
        'other': (request.form.get('other') or '').strip(),
        'cert_photo': (request.form.get('cert_photo') or '').strip(),
        'is_upload_cert_photo': _int('is_upload_cert_photo', 0),
        'graduate_time': (request.form.get('graduate_time') or '').strip(),
        'person_type': person_type,
        'student_type': student_type_value,
        'person_type_name': person_type_names.get(person_type, ''),
        'student_type_name': student_type_names.get(student_type_value, ''),
        'cycling_order_face_recognition': _int('cycling_order_face_recognition', 0)
    }

    result = certification.submit_certification(raw_token, payload)
    if result.get('ok'):
        points_store.set_cached_cert(raw_token, certification.get_cert_status(raw_token))
        return redirect(url_for('admin_accounts', message=f"认证已提交：{result.get('message') or '提交成功'}"))
    return redirect(url_for('admin_cert', index=index, error=result.get('error') or '提交失败'))


@app.route('/admin/accounts/cert/batch', methods=['POST'])
@admin_required
def admin_accounts_cert_batch():
    tokens = auth_store.load_authorizations()
    raw_selected = request.form.get('selected', '')
    selected = [int(x) for x in raw_selected.replace(',', ' ').split() if x.isdigit()]
    selected = sorted(set(selected))

    certified = 0
    skipped = 0
    failures = []
    for index in selected:
        if not (0 <= index < len(tokens)):
            continue
        raw_token = points.normalize_token(tokens[index])
        status = certification.get_cert_status(raw_token)
        if status.get('certified') or status.get('reviewing'):
            skipped += 1
            continue
        result = certification.submit_certification(raw_token, certification.AUTO_PAYLOAD)
        if result.get('ok'):
            certified += 1
        else:
            failures.append(f"#{index + 1}: {result.get('error') or '未知错误'}")
        points_store.set_cached_cert(raw_token, certification.get_cert_status(raw_token))

    parts = []
    if certified:
        parts.append(f"成功认证 {certified} 个")
    if skipped:
        parts.append(f"跳过已认证/审核中 {skipped} 个")
    if failures:
        parts.append(f"失败 {len(failures)} 个")
    message = '；'.join(parts) if parts else '没有可处理的账号'

    if failures:
        return redirect(url_for('admin_accounts', message=message, error='；'.join(failures[:5])))
    return redirect(url_for('admin_accounts', message=message))


@app.route('/admin/edit/<int:index>', methods=['GET', 'POST'])
@admin_required
def admin_edit(index):
    tokens = auth_store.load_authorizations()
    if not (0 <= index < len(tokens)):
        return redirect(url_for('admin_accounts', error='账户不存在'))

    if request.method == 'POST':
        new_token = (request.form.get('authorization') or '').strip()
        if not new_token:
            return redirect(url_for('admin_edit', index=index, error='未填写 Authorization'))
        old_norm = points.normalize_token(tokens[index])
        raw_new = points.normalize_token(new_token)
        if raw_new:
            info = points.fetch_user_info(raw_new)
            if info.get('ok'):
                account_profile_store.save_profile(raw_new, info)
        if old_norm:
            account_profile_store.delete_profile(old_norm)
        tokens[index] = new_token
        auth_store.save_authorizations(tokens)
        return redirect(url_for('admin_accounts', message='Authorization 已更新'))

    return render_template(
        'admin_edit.html',
        index=index,
        masked=points.mask_token(points.normalize_token(tokens[index])),
        full=tokens[index],
        error=request.args.get('error', ''),
        active='accounts'
    )


@app.route('/admin/orders')
@admin_required
def admin_orders():
    orders = read_order_logs()
    op_types = []
    for order in orders:
        if order['op_type'] not in op_types:
            op_types.append(order['op_type'])
    preferred = ['成功订单', '失败订单', '还车处理', '还车异常', '解锁异常', '请求异常', '其他']
    op_types.sort(key=lambda item: preferred.index(item) if item in preferred else len(preferred))
    return render_template('admin_orders.html', orders=orders, op_types=op_types, message=request.args.get('message', ''), error=request.args.get('error', ''), active='orders')


@app.route('/admin/orders/delete', methods=['POST'])
@admin_required
def admin_orders_delete():
    filename = request.form.get('file', '')
    raw_line = request.form.get('line', '')
    deleted = delete_order_line(filename, raw_line)
    if deleted:
        return redirect(url_for('admin_orders', message='已删除该订单记录'))
    return redirect(url_for('admin_orders', error='删除失败或该记录不存在'))


@app.route('/admin/orders/batch-delete', methods=['POST'])
@admin_required
def admin_orders_batch_delete():
    lines = request.form.getlist('lines')
    files = request.form.getlist('files')
    deleted = 0
    for raw_line, filename in zip(lines, files):
        if delete_order_line(filename, raw_line):
            deleted += 1
    if deleted:
        return redirect(url_for('admin_orders', message=f'已删除 {deleted} 条订单记录'))
    return redirect(url_for('admin_orders', error='没有可删除的订单记录'))

def classify_log_file(name):
    """根据日志文件名归类。"""
    lower = name.lower()
    if lower.startswith('order_'):
        return '下订单'
    if lower.startswith('scheduler_'):
        return '还车'
    if lower.startswith('points_scheduler'):
        return '积分任务'
    if lower.startswith('phone_login'):
        return '手机登录'
    if lower.startswith('server_err'):
        return '服务错误'
    if lower.startswith('server_out'):
        return '服务输出'
    return '其他'


@app.route('/admin/logs')
@admin_required
def admin_logs():
    log_dir = 'logs'
    files = []
    if os.path.isdir(log_dir):
        for name in os.listdir(log_dir):
            if name.endswith('.log'):
                path = os.path.join(log_dir, name)
                files.append({
                    'name': name,
                    'type': classify_log_file(name),
                    'size': os.path.getsize(path),
                    'mtime': datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S')
                })
    files.sort(key=lambda item: item['name'], reverse=True)

    selected = request.args.get('file', '')
    content = ''
    if selected:
        safe_name = os.path.basename(selected)
        if safe_name in [item['name'] for item in files]:
            content = read_log_file(os.path.join(log_dir, safe_name), tail=500)
        else:
            content = '文件不存在'
    return render_template('admin_logs.html', files=files, selected=selected, content=content, message=request.args.get('message', ''), error=request.args.get('error', ''), active='logs')


@app.route('/admin/logs/delete', methods=['POST'])
@admin_required
def admin_logs_delete():
    safe_name = os.path.basename(request.form.get('file', ''))
    if safe_name and safe_name.endswith('.log'):
        path = os.path.join('logs', safe_name)
        try:
            if os.path.exists(path):
                os.remove(path)
                return redirect(url_for('admin_logs', message=f'已删除日志文件 {safe_name}'))
        except OSError as exc:
            return redirect(url_for('admin_logs', error=f'删除失败：{exc}'))
    return redirect(url_for('admin_logs', error='文件不存在'))


@app.route('/admin/logs/batch-delete', methods=['POST'])
@admin_required
def admin_logs_batch_delete():
    names = request.form.getlist('files')
    deleted = 0
    for name in names:
        safe_name = os.path.basename(name or '')
        if safe_name and safe_name.endswith('.log'):
            path = os.path.join('logs', safe_name)
            try:
                if os.path.exists(path):
                    os.remove(path)
                    deleted += 1
            except OSError:
                pass
    if deleted:
        return redirect(url_for('admin_logs', message=f'已删除 {deleted} 个日志文件'))
    return redirect(url_for('admin_logs', error='没有可删除的日志文件'))


@app.route('/admin/logs/content/<path:filename>')
@admin_required
def admin_logs_content(filename):
    safe_name = os.path.basename(filename)
    if not safe_name or not safe_name.endswith('.log'):
        return jsonify(ok=False, error='文件名不合法')
    path = os.path.join('logs', safe_name)
    if not os.path.exists(path):
        return jsonify(ok=False, error='文件不存在')
    return jsonify(ok=True, name=safe_name, content=read_log_file(path, tail=500))


@app.route('/admin/settings/sign', methods=['POST'])
@admin_required
def admin_settings_sign():
    secret = (request.form.get('sign_secret') or '').strip()
    settings_store.set_sign_secret(secret)
    return redirect(url_for('admin_settings', message='短信签名密钥已保存'))

@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    message = ''
    error = ''
    if request.method == 'POST':
        current = request.form.get('current', '')
        new_password = request.form.get('new_password', '')
        confirm = request.form.get('confirm', '')
        if not settings_store.verify_password(current):
            error = '当前密码错误'
        elif len(new_password) < 4:
            error = '新密码至少4位'
        elif new_password != confirm:
            error = '两次输入的新密码不一致'
        else:
            settings_store.set_password(new_password)
            message = '密码修改成功'
    settings = settings_store.get_settings()
    return render_template(
        'admin_settings.html',
        message=message,
        error=error,
        retention_days=settings_store.get_log_retention_days(),
        api_key=settings_store.get_api_key(),
        notification=settings.get('notification') or dict(settings_store.DEFAULT_SETTINGS['notification']),
        bindings=settings_store.get_bindings(),
        channels=notify.CHANNELS,
        channel_labels=notify.CHANNEL_LABELS,
        active='settings'
    )


@app.route('/admin/settings/retention', methods=['POST'])
@admin_required
def admin_settings_retention():
    try:
        days = int((request.form.get('retention_days') or '').strip())
    except (TypeError, ValueError):
        return redirect(url_for('admin_settings', error='请填写有效的保留天数'))
    settings_store.set_log_retention_days(days)
    return redirect(url_for('admin_settings', message=f'日志自动清理天数已保存为 {days} 天'))


@app.route('/admin/settings/api/regenerate', methods=['POST'])
@admin_required
def admin_settings_api_regenerate():
    key = settings_store.regenerate_api_key()
    return redirect(url_for('admin_settings', message='API 密钥已重新生成'))


def _channel_config_fields(channel):
    """根据渠道从表单提取配置项。"""
    channel = (channel or 'none').strip()
    if channel == 'telegram':
        return {
            'bot_token': request.form.get('telegram_bot_token', '').strip(),
            'chat_id': request.form.get('telegram_chat_id', '').strip()
        }
    if channel == 'dingtalk':
        return {
            'webhook': request.form.get('dingtalk_webhook', '').strip(),
            'secret': request.form.get('dingtalk_secret', '').strip()
        }
    if channel == 'wecom':
        return {'webhook': request.form.get('wecom_webhook', '').strip()}
    if channel == 'feishu':
        return {'webhook': request.form.get('feishu_webhook', '').strip()}
    if channel == 'serverchan':
        return {'sendkey': request.form.get('serverchan_sendkey', '').strip()}
    if channel == 'pushplus':
        return {
            'token': request.form.get('pushplus_token', '').strip(),
            'topic': request.form.get('pushplus_topic', '').strip()
        }
    if channel == 'bark':
        return {
            'server': request.form.get('bark_server', '').strip(),
            'key': request.form.get('bark_key', '').strip()
        }
    if channel == 'qqbot':
        return {
            'app_id': request.form.get('qqbot_app_id', '').strip(),
            'app_secret': request.form.get('qqbot_app_secret', '').strip(),
            'target_type': request.form.get('qqbot_target_type', 'private').strip(),
            'target_id': request.form.get('qqbot_target_id', '').strip()
        }
    if channel == 'ntfy':
        return {
            'server': request.form.get('ntfy_server', '').strip(),
            'topic': request.form.get('ntfy_topic', '').strip(),
            'token': request.form.get('ntfy_token', '').strip()
        }
    if channel == 'gotify':
        return {
            'server': request.form.get('gotify_server', '').strip(),
            'token': request.form.get('gotify_token', '').strip()
        }
    if channel == 'custom':
        return {'url': request.form.get('custom_url', '').strip()}
    return {}


@app.route('/admin/settings/notification/toggles', methods=['POST'])
@admin_required
def admin_settings_notification_toggles():
    notify_login = request.form.get('notify_login') == '1'
    notify_order = request.form.get('notify_order') == '1'
    notify_points = request.form.get('notify_points') == '1'
    notify_account = request.form.get('notify_account') == '1'
    settings_store.set_notification_toggles(notify_login, notify_order, notify_points, notify_account)
    return redirect(url_for('admin_settings', message='推送事件开关已保存'))


@app.route('/admin/settings/notification/binding/add', methods=['POST'])
@admin_required
def admin_settings_binding_add():
    channel = (request.form.get('channel') or 'none').strip()
    if channel in ('', 'none'):
        return redirect(url_for('admin_settings', error='请选择要绑定的通知渠道'))
    config = {k: v for k, v in _channel_config_fields(channel).items() if v}
    settings_store.add_binding(channel, config, True)
    return redirect(url_for('admin_settings', message=f'已绑定通知渠道：{notify.CHANNEL_LABELS.get(channel, channel)}'))


@app.route('/admin/settings/notification/binding/<binding_id>/update', methods=['POST'])
@admin_required
def admin_settings_binding_update(binding_id):
    binding = settings_store.get_binding(binding_id)
    if not binding:
        return redirect(url_for('admin_settings', error='绑定不存在'))
    channel = (request.form.get('channel') or binding.get('channel') or 'none').strip()
    config = {k: v for k, v in _channel_config_fields(channel).items() if v}
    settings_store.update_binding(binding_id, channel=channel, config=config)
    return redirect(url_for('admin_settings', message='通知绑定已更新'))


@app.route('/admin/settings/notification/binding/<binding_id>/delete', methods=['POST'])
@admin_required
def admin_settings_binding_delete(binding_id):
    settings_store.delete_binding(binding_id)
    return redirect(url_for('admin_settings', message='已解绑通知渠道'))


@app.route('/admin/settings/notification/binding/<binding_id>/toggle', methods=['POST'])
@admin_required
def admin_settings_binding_toggle(binding_id):
    binding = settings_store.get_binding(binding_id)
    if not binding:
        return redirect(url_for('admin_settings', error='绑定不存在'))
    settings_store.update_binding(binding_id, enabled=not binding.get('enabled', True))
    state = '启用' if not binding.get('enabled', True) else '停用'
    return redirect(url_for('admin_settings', message=f'通知渠道已{state}'))


@app.route('/admin/settings/notification/binding/<binding_id>/test', methods=['GET', 'POST'])
@admin_required
def admin_settings_binding_test(binding_id):
    result = notify.send_test(binding_id)
    if result.get('ok'):
        return redirect(url_for('admin_settings', message='测试消息发送成功'))
    return redirect(url_for('admin_settings', error=f"测试消息失败：{result.get('message') or '未知错误'}"))


@app.route('/admin/tutorials')
@admin_required
def admin_tutorials():
    return render_template('admin_tutorial.html', channels=notify.CHANNELS, channel_labels=notify.CHANNEL_LABELS, active='tutorials')


# ===================== 后台账号操作 =====================
@app.route('/admin/phone-login')
@admin_required
def admin_phone_login():
    embed = request.args.get('embed') == '1'
    layout = 'admin_embed_base.html' if embed else 'admin_base.html'
    return render_template('admin_phone_login.html', active='accounts', embed=embed, layout=layout)

@app.route('/admin/phone-login/captcha', methods=['POST'])
@admin_required
def admin_phone_login_captcha():
    payload = request.get_json(silent=True) or {}
    phone = (payload.get('phone') or '').strip()
    if not re.match(r'^1\d{10}$', phone):
        return jsonify(ok=False, error='手机号格式不正确')
    requested = (payload.get('device_id') or '').strip()
    device_id = requested or device_store.get_device_id(phone) or device_store.generate_device_id(phone)
    device_store.set_device_id(phone, device_id)
    result = phone_login.generate_captcha(device_id)
    if not result.get('ok'):
        return jsonify(ok=False, error=result.get('error'))
    session['pl_token'] = result['token']
    session['pl_device_id'] = device_id
    session['pl_phone'] = phone
    return jsonify(ok=True, background_img=result['background_img'], slider_img=result['slider_img'], slider_y=result['slider_y'])

@app.route('/admin/phone-login/verify', methods=['POST'])
@admin_required
def admin_phone_login_verify():
    payload = request.get_json(silent=True) or {}
    token = session.get('pl_token')
    device_id = session.get('pl_device_id')
    phone = session.get('pl_phone')
    if not token or not phone or not device_id:
        return jsonify(ok=False, error='请先获取验证码')

    x = payload.get('x')
    track = payload.get('track') or []
    duration = payload.get('duration') or 0
    try:
        x = int(x)
        duration = int(duration)
    except (TypeError, ValueError):
        return jsonify(ok=False, error='滑块参数不正确')

    result = phone_login.verify_captcha(token, x, 0, track, duration, device_id)
    if not result.get('ok'):
        return jsonify(ok=False, error=result.get('error'))

    sms_result = phone_login.send_sms(phone, device_id, result['sms_captcha_key'])
    session['pl_sms_sent'] = bool(sms_result.get('ok'))
    session['pl_sms_message'] = sms_result.get('message') or sms_result.get('error') or ''
    return jsonify(ok=True, sms_sent=sms_result.get('ok'), message=(sms_result.get('message') if sms_result.get('ok') else sms_result.get('error')))

@app.route('/admin/phone-login/login', methods=['POST'])
@admin_required
def admin_phone_login_submit():
    payload = request.get_json(silent=True) or {}
    phone = (payload.get('phone') or '').strip()
    code = (payload.get('code') or '').strip()
    if not phone or not code:
        return jsonify(ok=False, error='请输入手机号和验证码')
    requested = (payload.get('device_id') or '').strip()
    device_id = requested or session.get('pl_device_id') or device_store.get_device_id(phone) or device_store.generate_device_id(phone)
    device_store.set_device_id(phone, device_id)
    result = phone_login.login_with_sms(phone, code, device_id)
    if not result.get('ok'):
        return jsonify(ok=False, error=result.get('error'))
    token = result['token']
    note, replaced = _add_account_with_overwrite(f"Bearer {token}")
    for key in ('pl_token', 'pl_device_id', 'pl_phone', 'pl_sms_sent', 'pl_sms_message'):
        session.pop(key, None)
    user = result.get('user') or {}
    notify.send_async('account', '添加账号通知', (
        f"手机号登录成功，已添加 Authorization（{user.get('phone') or phone}）\n"
        f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ))
    msg = note or f"登录成功，已添加 Authorization（{user.get('phone') or phone}）"
    return jsonify(ok=True, message=msg)

@app.route('/admin/add', methods=['POST'])
@admin_required
def admin_add():
    token = (request.form.get('authorization') or '').strip()
    if not token:
        return redirect(url_for('admin_accounts', error='未填写Authorization'))
    note, replaced = _add_account_with_overwrite(token)
    masked = points.mask_token(points.normalize_token(token))
    notify.send_async('account', '添加账号通知', (
        f"已添加 1 个 Authorization：{masked}\n"
        f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ))
    message = note if replaced else '已添加1个Authorization'
    return redirect(url_for('admin_accounts', message=message))

@app.route('/admin/import', methods=['POST'])
@admin_required
def admin_import():
    raw = (request.form.get('authorizations') or '')
    parsed = []
    for line in raw.replace(';', '\n').replace(',', '\n').split('\n'):
        token = line.strip()
        if token and token not in parsed:
            parsed.append(token)
    if not parsed:
        return redirect(url_for('admin_accounts', error='没有解析到Authorization'))
    replaced_count = 0
    for token in parsed:
        _, replaced = _add_account_with_overwrite(token)
        if replaced:
            replaced_count += 1
    notify.send_async('account', '添加账号通知', (
        f"成功导入 {len(parsed)} 个 Authorization\n"
        f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ))
    extra = f"，覆盖失效账号 {replaced_count} 个" if replaced_count else ''
    return redirect(url_for('admin_accounts', message=f'成功导入{len(parsed)}个Authorization{extra}'))

@app.route('/admin/delete/<int:index>', methods=['POST'])
@admin_required
def admin_delete(index):
    tokens = auth_store.load_authorizations()
    if 0 <= index < len(tokens):
        raw_token = points.normalize_token(tokens[index])
        auth_store.remove_authorization(index)
        if raw_token:
            points_store.delete_account(raw_token)
            account_profile_store.delete_profile(raw_token)
    return redirect(url_for('admin_accounts', message='已删除'))


@app.route('/admin/accounts/batch-delete', methods=['POST'])
@admin_required
def admin_accounts_batch_delete():
    indices = request.form.getlist('indexes')
    tokens = auth_store.load_authorizations()
    delete_set = set()
    for raw in indices:
        try:
            idx = int(raw)
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(tokens):
            tok = points.normalize_token(tokens[idx])
            if tok:
                delete_set.add(tok)
    remaining = []
    removed = 0
    for tok in tokens:
        ntok = points.normalize_token(tok)
        if ntok in delete_set:
            removed += 1
        else:
            remaining.append(tok)
    if removed:
        auth_store.save_authorizations(remaining)
        for tok in delete_set:
            points_store.delete_account(tok)
            account_profile_store.delete_profile(tok)
        return redirect(url_for('admin_accounts', message=f'已删除 {removed} 个账号'))
    return redirect(url_for('admin_accounts', error='没有可删除的账号'))

@app.route('/admin/clear', methods=['POST'])
@admin_required
def admin_clear():
    auth_store.save_authorizations([])
    return redirect(url_for('admin_accounts', message='已清空所有Authorization'))

@app.route('/admin/move/<int:index>/<direction>', methods=['POST'])
@admin_required
def admin_move(index, direction):
    tokens = auth_store.load_authorizations()
    if 0 <= index < len(tokens):
        new_index = index - 1 if direction == 'up' else index + 1
        if 0 <= new_index < len(tokens):
            tokens[index], tokens[new_index] = tokens[new_index], tokens[index]
            auth_store.save_authorizations(tokens)
    return redirect(url_for('admin_accounts'))



@app.route('/admin/points')
@admin_required
def admin_points():
    tokens = auth_store.load_authorizations()
    accounts = points.get_accounts_overview(tokens, force_refresh=(request.args.get('refresh') == '1'))
    message = request.args.get('message', '')
    error = request.args.get('error', '')
    return render_template('admin_points.html', accounts=accounts, message=message, error=error, active='points')

@app.route('/admin/points/run/<int:index>', methods=['POST'])
@admin_required
def admin_points_run(index):
    tokens = auth_store.load_authorizations()
    if not (0 <= index < len(tokens)):
        return redirect(url_for('admin_points', error='账户不存在'))
    raw_token = points.normalize_token(tokens[index])
    result = points.run_account_tasks(raw_token)
    if result.get('ok'):
        info = result.get('info') or {}
        points_store.set_cached_info(raw_token, info)
        notify.send_async('points', '积分获取结果', (
            f"账号：{info.get('phone') or points.mask_token(raw_token)}\n"
            f"本次获得：{result.get('total_gain', 0)} 积分\n"
            f"当前积分：{info.get('points') if info.get('points') is not None else '-'}\n"
            f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ))
        return redirect(url_for('admin_points', message=f"运行完成：{info.get('phone') or ''}，本次获得 {result.get('total_gain', 0)} 积分"))
    notify.send_async('points', '积分获取失败', (
        f"账号：{points.mask_token(raw_token)}\n"
        f"原因：{result.get('error') or '未知错误'}\n"
        f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ))
    return redirect(url_for('admin_points', error=f"运行失败：{result.get('error') or '未知错误'}"))

@app.route('/admin/points/schedule/<int:index>', methods=['POST'])
@admin_required
def admin_points_schedule(index):
    tokens = auth_store.load_authorizations()
    if not (0 <= index < len(tokens)):
        return redirect(url_for('admin_points', error='账户不存在'))
    raw_token = points.normalize_token(tokens[index])
    enabled = request.form.get('enabled') == '1'
    run_time = (request.form.get('run_time') or '').strip()
    if enabled and not re.match(r'^([01]\d|2[0-3]):[0-5]\d$', run_time):
        return redirect(url_for('admin_points', error='请选择有效的自动运行时间'))
    points_store.set_schedule(raw_token, enabled, run_time or None)
    if enabled:
        return redirect(url_for('admin_points', message=f"已开启定时自动运行，时间 {run_time}"))
    return redirect(url_for('admin_points', message='已关闭定时自动运行'))


@app.route('/admin/points/batch/run', methods=['POST'])
@admin_required
def admin_points_batch_run():
    tokens = auth_store.load_authorizations()
    selected = sorted({int(x) for x in re.split(r'[\s,]+', request.form.get('selected', '')) if x.isdigit()})
    if not selected:
        return redirect(url_for('admin_points', error='请先勾选要运行的账户'))

    ok_count = 0
    fail_count = 0
    total_gain = 0
    for pos, index in enumerate(selected):
        if not (0 <= index < len(tokens)):
            continue
        raw_token = points.normalize_token(tokens[index])
        result = points.run_account_tasks(raw_token)
        if result.get('ok'):
            ok_count += 1
            total_gain += result.get('total_gain', 0)
            info = result.get('info') or {}
            if info.get('ok'):
                points_store.set_cached_info(raw_token, info)
        else:
            fail_count += 1
        if pos < len(selected) - 1:
            time.sleep(random.randint(2, 5))

    message = f"批量运行完成：成功 {ok_count} 个，失败 {fail_count} 个，共获得 {total_gain} 积分"
    notify.send_async('points', '积分批量运行结果', (
        f"账号统计：共处理 {len(selected)} 个\n"
        f"成功 {ok_count} 个，失败 {fail_count} 个\n"
        f"累计获得 {total_gain} 积分\n"
        f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ))
    return redirect(url_for('admin_points', message=message, error=('部分账户运行失败，请查看日志' if fail_count else '')))


@app.route('/admin/points/batch/exchange', methods=['POST'])
@admin_required
def admin_points_batch_exchange():
    tokens = auth_store.load_authorizations()
    selected = sorted({int(x) for x in re.split(r'[\s,]+', request.form.get('selected', '')) if x.isdigit()})
    if not selected:
        return redirect(url_for('admin_points', error='请先勾选要自动兑换的账户'))

    ok_count = 0
    fail_count = 0
    total_cards = 0
    for pos, index in enumerate(selected):
        if not (0 <= index < len(tokens)):
            continue
        raw_token = points.normalize_token(tokens[index])
        result = points.auto_exchange_ride_card(raw_token)
        if result.get('ok'):
            ok_count += 1
            total_cards += result.get('exchanged', 0)
        else:
            fail_count += 1
        if pos < len(selected) - 1:
            time.sleep(random.randint(2, 5))

    message = f"批量自动兑换完成：成功 {ok_count} 个，失败 {fail_count} 个，共兑换 {total_cards} 张骑行卡"
    notify.send_async('points', '积分批量兑换结果', (
        f"账号统计：共处理 {len(selected)} 个\n"
        f"成功 {ok_count} 个，失败 {fail_count} 个\n"
        f"累计兑换 {total_cards} 张骑行卡\n"
        f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ))
    return redirect(url_for('admin_points', message=message, error=('部分账户兑换失败，请查看日志' if fail_count else '')))


@app.route('/admin/points/batch/schedule', methods=['POST'])
@admin_required
def admin_points_batch_schedule():
    tokens = auth_store.load_authorizations()
    selected = sorted({int(x) for x in re.split(r'[\s,]+', request.form.get('selected', '')) if x.isdigit()})
    run_time = (request.form.get('run_time') or '').strip()
    if not re.match(r'^([01]\d|2[0-3]):[0-5]\d$', run_time):
        return redirect(url_for('admin_points', error='请选择有效的自动运行时间'))
    if not selected:
        return redirect(url_for('admin_points', error='请先勾选要定时运行的账户'))

    ok_count = 0
    for pos, index in enumerate(selected):
        if not (0 <= index < len(tokens)):
            continue
        raw_token = points.normalize_token(tokens[index])
        points_store.set_schedule(raw_token, True, run_time)
        ok_count += 1
        if pos < len(selected) - 1:
            time.sleep(random.randint(2, 5))

    return redirect(url_for('admin_points', message=f"批量定时运行已设置：已为 {ok_count} 个账号开启每日 {run_time} 自动运行"))

@app.route('/admin/points/exchange/<int:index>', methods=['POST'])
@admin_required
def admin_points_exchange(index):
    tokens = auth_store.load_authorizations()
    if not (0 <= index < len(tokens)):
        return redirect(url_for('admin_points', error='账户不存在'))
    raw_token = points.normalize_token(tokens[index])
    result = points.auto_exchange_ride_card(raw_token)
    if result.get('ok'):
        notify.send_async('points', '自动兑换成功', (
            f"账号：{points.mask_token(raw_token)}\n"
            f"已兑换 {result.get('exchanged', 0)} 张骑行卡\n"
            f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ))
        return redirect(url_for('admin_points', message=f"自动兑换完成，已兑换 {result.get('exchanged', 0)} 张骑行卡"))
    notify.send_async('points', '自动兑换失败', (
        f"账号：{points.mask_token(raw_token)}\n"
        f"原因：{result.get('error') or '未知错误'}\n"
        f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ))
    return redirect(url_for('admin_points', error=f"自动兑换失败：{result.get('error') or '未知错误'}"))

@app.route('/admin/points/settings', methods=['POST'])
@admin_required
def admin_points_settings():
    daily_time = request.form.get('daily_time', '').strip()
    if re.match(r'^([01]\d|2[0-3]):[0-5]\d$', daily_time):
        points_store.set_daily_time(daily_time)
        return redirect(url_for('admin_points', message='定时运行时间已保存'))
    return redirect(url_for('admin_points', error='时间格式不正确，请使用 HH:MM'))


@app.route('/admin/points/log/<int:index>')
@admin_required
def admin_points_log(index):
    tokens = auth_store.load_authorizations()
    if not (0 <= index < len(tokens)):
        return redirect(url_for('admin_points', error='账户不存在'))
    raw_token = points.normalize_token(tokens[index])
    last_run = points_store.get_last_run(raw_token) or {}
    info = last_run.get('info') or {}
    phone = info.get('phone') or ''
    log_lines = read_points_log_lines(phone) if phone else []
    return render_template(
        'admin_points_log.html',
        index=index,
        masked=points.mask_token(raw_token),
        last_run=last_run,
        log_lines=log_lines,
        active='points'
    )


if __name__ == '__main__':
    intervalSeconds = 60  # 设置监听的时间间隔，单位为秒
    start_scheduler()  # 启动定时任务
    points_scheduler.main()  # 启动积分定时任务
    maintenance.main()  # 启动日志自动清理
    app.run(host='0.0.0.0', port=4321, debug=False)
