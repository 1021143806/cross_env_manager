#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调车管理路由蓝图 - 空车调车模块
"""

from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for, Response
from functools import wraps
from datetime import datetime
import os, json, time, threading

dispatch_bp = Blueprint('dispatch', __name__, template_folder='../templates')


def _json_resp(data, status=200):
    """返回 JSON 响应，支持中文"""
    return Response(
        json.dumps(data, ensure_ascii=False),
        status=status,
        mimetype='application/json'
    )


def login_required(f):
    """登录验证装饰器（普通用户或管理员均可）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': '需要登录', 'redirect': '/login'}), 401
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """管理员验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': '需要管理员权限，请在首页启用管理员提权'}), 403
            return '''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"></head>
<body><script>alert('需要管理员权限，请在首页启用管理员提权');history.back();</script></body></html>''', 403
        return f(*args, **kwargs)
    return decorated_function

# 数据目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'dispatch')
CACHE_INDEX_PATH = os.path.join(DATA_DIR, 'cache_index.json')
BACKUP_DIR = os.path.join(DATA_DIR, 'backups')
GLOBAL_LOG_PATH = os.path.join(DATA_DIR, 'global_log.json')
SHARED_DIR = os.path.join(DATA_DIR, '_shared')  # 跨区域共享模板目录

# 线程锁
_write_lock = threading.Lock()

# 自动调度防抖：记录每个区域上次自动调度时间
_auto_dispatch_last = {}
_AUTO_DISPATCH_DEBOUNCE = 5  # 同一区域5秒内最多自动调度一次


# ========== task_type 兼容 ==========

def _normalize_task_type(t):
    """兼容旧配置：无 task_type 时根据 direction 和 code/name 推断"""
    if 'task_type' in t:
        return t['task_type']
    # 旧配置兼容：direction + 名称推断
    direction = t.get('direction', 'in')
    template_code = t.get('code') or t.get('name', '')
    if template_code in ('DKCqu', 'DKCback'):
        return 'empty_in' if direction == 'in' else 'empty_out'
    return 'load_in' if direction == 'in' else 'load_out'


def _is_empty_task(task_type):
    """是否为空车任务（参与自动下发和互斥检查）"""
    return task_type in ('empty_in', 'empty_out')


def _is_in_direction(task_type):
    """是否为来方向"""
    return task_type in ('empty_in', 'load_in')


def _get_template_file_path(region_key, t):
    """获取模板文件路径，支持共享模板"""
    # 兼容 code 和 name 字段
    template_code = t.get('code') or t.get('name', '')
    if t.get('shared') and template_code:
        # 共享模板：按模板代码存储在 _shared/ 目录
        os.makedirs(SHARED_DIR, exist_ok=True)
        return os.path.join(SHARED_DIR, f"{template_code}.json")
    return _get_region_file(region_key, t['file'])


# ========== 数据读写 ==========

def _load_cache_index():
    """加载 cache_index.json"""
    if not os.path.exists(CACHE_INDEX_PATH):
        return {}
    try:
        with open(CACHE_INDEX_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[Dispatch] 加载配置失败: {e}")
        return {}


def _save_cache_index(data):
    """保存 cache_index.json"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with _write_lock:
        with open(CACHE_INDEX_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _load_json(filepath):
    """加载 JSON 文件，确保返回列表"""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 如果不是列表，返回空列表
        return data if isinstance(data, list) else []
    except:
        return []


def _save_json(filepath, data):
    """保存 JSON 文件（原子写入）"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with _write_lock:
        tmp = filepath + '.tmp'
        try:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, filepath)
        except UnicodeEncodeError as e:
            print(f"[Dispatch] _save_json 编码错误: {e}, 尝试使用 repr 转义")
            with open(tmp, 'w', encoding='utf-8') as f:
                # 将数据中的字符串用 repr 处理
                def _safe_str(obj):
                    if isinstance(obj, str):
                        return obj.encode('utf-8', errors='replace').decode('utf-8')
                    return obj
                safe_data = json.loads(json.dumps(data, default=_safe_str, ensure_ascii=False))
                json.dump(safe_data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, filepath)


def _get_region_file(region_key, filename):
    """获取区域文件路径（按区域文件夹存放）"""
    return os.path.join(DATA_DIR, region_key, filename)


# ========== 全局操作日志 ==========

def write_global_log(action, region_key, detail='', level='info', raw_data=None):
    """写入全局操作日志（超过100条自动清理，保留最新100条）
    
    report_status 去重逻辑：
    - 完全一致（同模板+设备+状态+订单ID）：修改已有日志，追加重复次数
    - 有偏差（同模板+设备+状态，但订单ID不同）：覆盖已有日志内容
    """
    logs = _load_json(GLOBAL_LOG_PATH)
    
    # report_status 去重：查找最近一条同模板+设备+状态的日志
    if action == 'report_status' and raw_data:
        tn = raw_data.get('modelProcessCode') or raw_data.get('template_name', '')
        dn = raw_data.get('deviceNum', '')
        st = raw_data.get('status', '')
        # 统一规范化 orderId：兼容 orderId 和 order_id 两种字段名
        oid = raw_data.get('orderId') or raw_data.get('order_id', '')
        # 从后往前找最近一条匹配的 report_status 日志
        for i in range(len(logs) - 1, -1, -1):
            log = logs[i]
            if log.get('action') != 'report_status' or not log.get('raw_data'):
                continue
            rd = log['raw_data']
            r_tn = rd.get('modelProcessCode') or rd.get('template_name', '')
            r_dn = rd.get('deviceNum', '')
            r_st = rd.get('status', '')
            if r_tn == tn and r_dn == dn and str(r_st) == str(st):
                # 找到匹配：更新时间和内容
                log['time'] = datetime.now().isoformat()
                # 统一规范化旧日志的 orderId 后再比较
                r_oid = rd.get('orderId') or rd.get('order_id', '')
                if r_oid == oid:
                    # 完全一致：追加重复次数（放在开头，避免冒号前空格问题）
                    dup_count = log.get('dup_count', 1) + 1
                    log['dup_count'] = dup_count
                    log['detail'] = f'(重复#{dup_count}) ' + detail
                else:
                    # 有偏差：覆盖内容，重置重复计数
                    log['detail'] = detail
                    log['raw_data'] = raw_data
                    log['level'] = level
                    log.pop('dup_count', None)
                _save_json(GLOBAL_LOG_PATH, logs)
                return
        # 没找到匹配，走正常追加逻辑
    
    entry = {
        "time": datetime.now().isoformat(),
        "action": action,
        "region_key": region_key,
        "detail": detail,
        "level": level
    }
    if raw_data is not None:
        entry["raw_data"] = raw_data
    logs.append(entry)
    # 超过100条保留最新100条
    if len(logs) > 100:
        logs = logs[-100:]
    _save_json(GLOBAL_LOG_PATH, logs)
    
    # 监控采样：每5次调车操作采样一次
    _dispatch_sample_counter[0] += 1
    if _dispatch_sample_counter[0] % 5 == 0:
        try:
            from app import _dispatch_samples
            _dispatch_samples.append({
                'time': datetime.now().isoformat(),
                'action': action,
                'region_key': region_key,
                'level': level
            })
            if len(_dispatch_samples) > 3600:
                _dispatch_samples.pop(0)
        except ImportError:
            pass

# 调车采样计数器
_dispatch_sample_counter = [0]


@dispatch_bp.route('/api/dispatch/global_log')
@login_required
def api_global_log():
    """获取全局操作日志"""
    logs = _load_json(GLOBAL_LOG_PATH)
    logs.sort(key=lambda x: x.get('time', ''), reverse=True)
    return jsonify({'logs': logs})


# ========== 核心计算逻辑 ==========

def calculate_area_balance(region_key, region_config):
    """
    计算区域设备平衡
    
    公式:
      a = 所有来区域模板中 status=6 的任务数之和
      b = 所有离开模板中 status=6 的任务数之和
      currentCount = now.json 中的设备数
      expectedCount = currentCount + a - b
      
      if expectedCount > xmax: need = expectedCount - xmax (正数, 车过多, 下发回空车)
      if expectedCount < xmin: need = expectedCount - xmin (负数, 车不够, 下发调空车)
      else: need = 0 (平衡)
    """
    xmin = region_config.get('xmin', 2)
    xmax = region_config.get('xmax', 4)
    max_once = region_config.get('max_dispatch_once', 3)
    enabled = region_config.get('enabled', False)
    
    # 分时段配置解析（始终解析，不受手动开关影响，用于展示）
    time_slot_active = False
    time_slot_matched = None
    time_slots_config = region_config.get('time_slots', {})
    if time_slots_config.get('enabled', False):
        now_time = datetime.now().strftime('%H:%M')
        matched_slots = []
        for slot in time_slots_config.get('slots', []):
            start = slot.get('start', '00:00')
            end = slot.get('end', '00:00')
            # 处理跨天时段（如 20:00 ~ 08:00）
            if start <= end:
                matched = start <= now_time <= end
            else:
                matched = now_time >= start or now_time <= end
            if matched:
                # 计算时段长度（分钟），用于选择最精确的时段
                if start <= end:
                    duration = (int(end[:2])*60 + int(end[3:])) - (int(start[:2])*60 + int(start[3:]))
                else:
                    duration = (24*60 - (int(start[:2])*60 + int(start[3:]))) + (int(end[:2])*60 + int(end[3:]))
                matched_slots.append((duration, slot))
        
        if matched_slots:
            # 选择时间范围最小的时段（最精确匹配）
            matched_slots.sort(key=lambda x: x[0])
            best_slot = matched_slots[0][1]
            xmin = best_slot.get('xmin', xmin)
            xmax = best_slot.get('xmax', xmax)
            time_slot_active = True
            time_slot_matched = best_slot
    
    # 分时配置中 xmin=-1, xmax=-1 表示禁用真实任务（仅在手动启用时生效）
    effective_enabled = enabled
    if enabled and time_slot_active and xmin == -1 and xmax == -1:
        effective_enabled = False  # 走模拟逻辑
    
    # 统计 a: 来区域模板中 status=6 的任务数
    a = 0
    incoming_templates = []
    outgoing_templates = []
    
    for t in region_config.get('templates', []):
        fpath = _get_template_file_path(region_key, t)
        tasks = _load_json(fpath)
        count = len([task for task in tasks if task.get('status') == 6])
        task_type = _normalize_task_type(t)
        
        # code: 模板代码（计算用），display_name: 看板显示名称（可自定义中文名）
        template_code = t.get('code') or t.get('name', '')
        display_name = t.get('display_name') or t.get('name', '')
        item = {"code": template_code, "name": display_name, "count": count, "task_type": task_type}
        if _is_in_direction(task_type):
            a += count
            incoming_templates.append(item)
        else:
            outgoing_templates.append(item)
    
    # 统计 b: 离开模板中 status=6 的任务数
    b = sum(t['count'] for t in outgoing_templates)
    
    # currentCount: currentCount.json 中的设备数
    now_file = _get_region_file(region_key, 'currentCount.json')
    now_devices = _load_json(now_file)
    currentCount = len(now_devices)
    
    # expectedCount = currentCount + a - b
    expectedCount = currentCount + a - b
    
    # 计算 need
    if expectedCount > xmax:
        need = expectedCount - xmax  # 正数：车过多，下发回空车
        direction = "out"
        direction_text = f"车过多，需调出{need}辆"
        direction_icon = "bi-arrow-up"
        direction_color = "danger"
    elif expectedCount < xmin:
        need = expectedCount - xmin  # 负数：车不够，下发调空车
        direction = "in"
        direction_text = f"车不够，需调入{abs(need)}辆"
        direction_icon = "bi-arrow-down"
        direction_color = "warning"
    else:
        need = 0
        direction = "none"
        direction_text = "平衡"
        direction_icon = "bi-check-circle"
        direction_color = "success"
    
    # 容量管控：限制每次下发数量
    dispatch_count = min(abs(need), max_once) if need != 0 else 0
    
    # 互斥检查：只检查空车模板（empty_in/empty_out）之间的互斥
    # 负载模板不影响空车下发
    can_dispatch = True
    mutex_reason = ""
    if need != 0:
        for t in region_config.get('templates', []):
            task_type = _normalize_task_type(t)
            # 只检查空车模板
            if not _is_empty_task(task_type):
                continue
            fpath = _get_template_file_path(region_key, t)
            tasks = _load_json(fpath)
            pending = [task for task in tasks if task.get('status') == 6]
            if pending:
                # 如果要下发去空车(in)，但存在未完成的回空车(out)任务
                # 如果要下发回空车(out)，但存在未完成的去空车(in)任务
                t_direction = 'in' if _is_in_direction(task_type) else 'out'
                if t_direction != direction:
                    can_dispatch = False
                    template_code = t.get('code') or t.get('name', '')
                    mutex_reason = f"pending {template_code} task, mutex"
                    break
    
    return {
        "region_key": region_key,
        "areaId": region_config.get('areaId', '0'),
        "name": region_key,
        "server": region_config.get('server', ''),
        "enabled": enabled,  # 手动开关状态（前端显示用）
        "effective_enabled": effective_enabled,  # 实际生效状态（计算用）
        "xmin": xmin,
        "xmax": xmax,
        "max_dispatch_once": max_once,
        "currentCount": currentCount,
        "a": a,
        "b": b,
        "expectedCount": expectedCount,
        "need": need,
        "dispatch_count": dispatch_count if need != 0 else 0,
        "direction": direction,
        "direction_text": direction_text,
        "direction_icon": direction_icon,
        "direction_color": direction_color,
        "can_dispatch": can_dispatch,
        "mutex_reason": mutex_reason,
        "time_slot_active": time_slot_active,
        "time_slot_matched": time_slot_matched,
        "templates": {
            "incoming": incoming_templates,
            "outgoing": outgoing_templates
        }
    }


def get_all_areas_status():
    """获取所有区域状态"""
    index = _load_cache_index()
    areas = []
    total_devices = 0
    need_dispatch = 0
    balanced = 0
    
    for region_key, region in index.items():
        if not isinstance(region, dict) or 'templates' not in region:
            continue
        balance = calculate_area_balance(region_key, region)
        areas.append(balance)
        total_devices += balance['currentCount']
        if balance['direction'] != 'none':
            need_dispatch += 1
        else:
            balanced += 1
    
    return {
        "summary": {
            "total_areas": len(areas),
            "total_devices": total_devices,
            "need_dispatch": need_dispatch,
            "balanced": balanced
        },
        "areas": areas
    }


# ========== 状态上报处理 ==========

def handle_status_report(data):
    """
    处理任务状态上报（兼容两种报文格式）
    
    格式1（内部格式）:
      - region_key: 区域标识 (如 region_1)
      - template_name: 模板代码 (如 DKCqu)
      - deviceNum: 设备编号 (如 C185)
      - deviceCode: 设备序列号 (如 BL11637BAK00010)
      - status: 任务状态 (6=开始, 8=完成)
      - order_id: 任务单号 (可选)
    
    格式2（外部上报格式）:
      - deviceCode: 设备序列号
      - deviceNum: 设备编号 (如 DJC5)
      - modelProcessCode: 任务模板 (如 JuSheng_HJQ2_4-23)
      - subTaskStatus: 子任务状态 (字符串 "3"=执行中, "8"=完成)
      - status: 任务状态 (数字 8=完成)
      - orderId: 任务单号
      - shelfNumber: 货架编号 (可选)
      - shelfCurrPosition: 货架当前点位 (可选)
    
    处理逻辑:
      status=6/subTaskStatus="3": 记录到模板 JSON
      status=8/subTaskStatus="8": 
        来区域模板 → 从模板 JSON 删除, 写入 currentCount.json
        离开模板 → 从模板 JSON 删除, 从 currentCount.json 删除
    """
    # === 兼容两种报文格式 ===
    
    # 1. 解析 status：直接使用报文中的 status 字段
    # 报文示例: "status": 8 (完成)
    # 内部定义: 6=开始, 8=完成
    raw_status = data.get('status', 0)
    try:
        status = int(raw_status)
    except (ValueError, TypeError):
        status = 0
    
    # 3. 解析设备信息
    device_code = data.get('deviceCode', '')
    device_num = data.get('deviceNum', '')
    
    # 4. 解析 order_id
    # 兼容 orderId 和 order_id
    order_id = data.get('orderId') or data.get('order_id', '')
    
    # 5. 解析 template_name
    # 兼容 modelProcessCode 和 template_name
    template_name = data.get('modelProcessCode') or data.get('template_name', '')
    
    # 6. 解析 region_key
    # 优先使用传入的 region_key，否则通过 modelProcessCode 自动匹配
    region_key = data.get('region_key', '')
    if not region_key and template_name:
        # 遍历所有区域，查找包含该模板的区域
        # 优先精确匹配 code，再回退到文件名匹配
        index = _load_cache_index()
        fallback_rk = None
        for rk, region in index.items():
            if not isinstance(region, dict) or 'templates' not in region:
                continue
            for t in region.get('templates', []):
                template_code = t.get('code') or t.get('name', '')
                if template_code == template_name:
                    region_key = rk
                    break
                if not fallback_rk and t['file'].replace('.json', '') == template_name:
                    fallback_rk = rk
            if region_key:
                break
        if not region_key and fallback_rk:
            region_key = fallback_rk
    
    if not region_key or not template_name:
        # 无法匹配区域/模板，静默接受上报（不返回错误，避免 ICS 重试）
        print(f"[Dispatch] report_status 无法匹配: region_key={region_key}, template_name={template_name}, deviceNum={device_num}")
        return True, f"无法匹配区域/模板，已接收上报 (region_key={region_key}, template={template_name})", False
    
    # 查找模板配置
    index = _load_cache_index()
    region = index.get(region_key)
    if not region:
        # 区域不存在，静默接受上报
        print(f"[Dispatch] report_status 区域不存在: {region_key}, template={template_name}")
        return True, f"区域 {region_key} 不存在，已接收上报", False
    
    template_config = None
    for t in region.get('templates', []):
        template_code = t.get('code') or t.get('name', '')
        if template_code == template_name:
            template_config = t
            break
    
    if not template_config:
        # 尝试通过文件名匹配
        for t in region.get('templates', []):
            if t['file'].replace('.json', '') == template_name:
                template_config = t
                break
    
    if not template_config:
        # 模板不存在于该区域，静默接受上报
        print(f"[Dispatch] report_status 模板不存在: region_key={region_key}, template={template_name}")
        return True, f"模板 {template_name} 不存在于区域 {region_key}，已接收上报", False
    
    task_type = _normalize_task_type(template_config)
    template_file = _get_template_file_path(region_key, template_config)
    now_file = _get_region_file(region_key, 'currentCount.json')
    
    now = datetime.now().isoformat()
    
    if status == 6:
        # 任务开始（运行中）：记录到模板 JSON
        tasks = _load_json(template_file)
        # 查找是否已有该设备的记录，有则覆盖，无则新增
        existing = None
        for t in tasks:
            if t.get('deviceCode') == device_code and t.get('status') == 6:
                existing = t
                break
        
        if existing:
            # 覆盖更新
            existing['deviceNum'] = device_num
            existing['order_id'] = order_id
            existing['shelfNumber'] = data.get('shelfNumber', '')
            existing['shelfCurrPosition'] = data.get('shelfCurrPosition', '')
            existing['update_time'] = now
            change_summary = f'模板更新 {template_name} (共{len(tasks)}条)'
        else:
            # 新增
            tasks.append({
                "deviceCode": device_code,
                "deviceNum": device_num,
                "status": 6,
                "order_id": order_id,
                "shelfNumber": data.get('shelfNumber', ''),
                "shelfCurrPosition": data.get('shelfCurrPosition', ''),
                "create_time": now,
                "update_time": now
            })
            change_summary = f'模板+{template_name} +1 (共{len(tasks)}条)'
        _save_json(template_file, tasks)
        
    else:
        # 非 6 的状态（包括 8=完成 及其他状态）：执行清理逻辑
        # 从模板 JSON 中删除该设备记录
        tasks = _load_json(template_file)
        old_count = len(tasks)
        tasks = [t for t in tasks if not (t.get('deviceCode') == device_code and t.get('status') == 6)]
        _save_json(template_file, tasks)
        template_removed = old_count - len(tasks)
        
        # 更新 currentCount.json（所有类型都更新，因为车确实在移动）
        now_devices = _load_json(now_file)
        cc_change = ''
        if _is_in_direction(task_type):
            # 来区域完成：写入 currentCount.json
            if not any(d.get('deviceCode') == device_code for d in now_devices):
                now_devices.append({
                    "deviceCode": device_code,
                    "deviceNum": device_num,
                    "order_id": order_id,
                    "shelfNumber": data.get('shelfNumber', ''),
                    "create_time": now
                })
                cc_change = f', currentCount +1 (共{len(now_devices)}条)'
        else:
            # 离开完成：从 currentCount.json 删除
            old_cc = len(now_devices)
            now_devices = [d for d in now_devices if d.get('deviceCode') != device_code]
            if len(now_devices) < old_cc:
                cc_change = f', currentCount -1 (共{len(now_devices)}条)'
        
        _save_json(now_file, now_devices)
        change_summary = f'模板-{template_name} -{template_removed}{cc_change}'
    
    return True, change_summary, True


# ========== 路由 ==========

@dispatch_bp.route('/dispatch')
@login_required
def dashboard():
    """调车管理主看板"""
    return render_template('dispatch/dashboard.html')


@dispatch_bp.route('/dispatch/config')
@login_required
@admin_required
def config_page():
    """配置管理页"""
    return render_template('dispatch/config.html')


@dispatch_bp.route('/dispatch/area/<int:area_id>')
@login_required
def area_detail(area_id):
    """区域详情页"""
    data = get_all_areas_status()
    area = next((a for a in data['areas'] if a['areaId'] == str(area_id)), None)
    if not area:
        return "区域不存在", 404
    return render_template('dispatch/area_detail.html', area=area)


# ========== API ==========

@dispatch_bp.route('/api/dispatch/status')
@login_required
def api_status():
    """获取所有区域状态"""
    return jsonify(get_all_areas_status())


@dispatch_bp.route('/api/dispatch/report_status', methods=['POST'])
def api_report_status():
    """任务状态上报接口（外部设备上报，无需登录）
    始终返回 {"code": 1000, "desc": "success"}，即使 orderId 不存在也返回 1000，
    否则服务器会尝试重新上报。
    """
    try:
        data = request.get_json()
        if not data:
            # 即使请求体为空也返回 1000，避免服务器重试
            return jsonify({'code': 1000, 'desc': 'success'})
        
        success, message, matched = handle_status_report(data)
        # 记录日志（不阻塞主流程）
        try:
            rk = data.get('region_key') or 'auto'
            tn = data.get('modelProcessCode') or data.get('template_name', '?')
            dn = data.get('deviceNum', '?')
            st = data.get('status', '?')
            oid = data.get('orderId') or data.get('order_id', '')
            detail = f'{tn} {dn} status={st}'
            if oid:
                detail += f' orderId={oid}'
            detail += f': {message}'
            write_global_log('report_status', rk, detail,
                           'info' if matched else 'warning', raw_data=data)
        except:
            pass
        
        # 自动调度：仅匹配成功时触发
        if matched:
            try:
                rk = data.get('region_key') or ''
                if rk:
                    # 从配置读取防抖时间
                    index = _load_cache_index()
                    debounce = index.get('auto_dispatch_debounce', _AUTO_DISPATCH_DEBOUNCE)
                    now = time.time()
                    last = _auto_dispatch_last.get(rk, 0)
                    if now - last >= debounce:
                        _auto_dispatch_last[rk] = now
                        # 异步执行调度（不阻塞上报响应）
                        def _auto_dispatch():
                            try:
                                # 在线程内重新加载最新配置，避免使用闭包中的旧 index
                                fresh_index = _load_cache_index()
                                region = fresh_index.get(rk)
                                if not region: return
                                balance = calculate_area_balance(rk, region)
                                if balance['direction'] == 'none':
                                    return
                                if not balance['can_dispatch']:
                                    return
                                # 调用 execute 的核心逻辑
                                _execute_dispatch(rk, region, balance)
                            except Exception as e:
                                print(f"[Dispatch] 自动调度失败: {e}")
                        threading.Thread(target=_auto_dispatch, daemon=True).start()
            except: pass
        
        # 始终返回 1000，额外返回 matched 标识是否匹配到模板
        return jsonify({'code': 1000, 'desc': 'success', 'matched': matched})
    except Exception as e:
        # 即使异常也返回 1000，避免服务器重试
        print(f"[Dispatch] report_status 异常: {e}")
        return jsonify({'code': 1000, 'desc': 'success'})


@dispatch_bp.route('/api/dispatch/config')
@login_required
def get_config():
    """获取配置"""
    return jsonify(_load_cache_index())


@dispatch_bp.route('/api/dispatch/config', methods=['POST'])
@login_required
@admin_required
def save_config():
    """保存配置"""
    try:
        data = request.get_json()
        _save_cache_index(data)
        return jsonify({'success': True, 'message': '配置保存成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== 备份 API ==========

@dispatch_bp.route('/api/dispatch/config/backups')
@login_required
def list_backups():
    """列出备份"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backups = []
    for filename in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if filename.endswith('.json'):
            filepath = os.path.join(BACKUP_DIR, filename)
            stat = os.stat(filepath)
            message = ''
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    first = f.readline()
                    if first.startswith('// commit:'):
                        message = first[10:].strip()
            except:
                pass
            backups.append({
                'name': filename,
                'message': message,
                'timestamp': stat.st_mtime * 1000,
                'size': stat.st_size
            })
    return jsonify(backups)


@dispatch_bp.route('/api/dispatch/config/backup', methods=['POST'])
@login_required
@admin_required
def create_backup():
    """创建备份"""
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        message = request.json.get('message', '').strip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"dispatch_config_{timestamp}.json"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        
        config = _load_cache_index()
        commit_line = f"// commit: {message}\n" if message else "// commit: (no message)\n"
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(commit_line)
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return jsonify({'success': True, 'backup_name': backup_name})
    except Exception as e:
        return jsonify({'error': f'创建备份失败: {str(e)}'}), 500


@dispatch_bp.route('/api/dispatch/config/backup/<backup_name>')
@login_required
def get_backup(backup_name):
    """获取备份内容"""
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not os.path.exists(backup_path):
        return jsonify({'error': '备份文件不存在'}), 404
    with open(backup_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}


@dispatch_bp.route('/api/dispatch/config/backup/<backup_name>/restore', methods=['POST'])
@login_required
@admin_required
def restore_backup(backup_name):
    """恢复备份"""
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not os.path.exists(backup_path):
        return jsonify({'error': '备份文件不存在'}), 404
    with open(backup_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    content = ''.join(line for line in lines if not line.startswith('// '))
    try:
        data = json.loads(content)
        _save_cache_index(data)
        return jsonify({'success': True})
    except json.JSONDecodeError as e:
        return jsonify({'error': f'备份文件格式错误: {str(e)}'}), 500


@dispatch_bp.route('/api/dispatch/config/backup/<backup_name>', methods=['DELETE'])
@login_required
@admin_required
def delete_backup(backup_name):
    """删除备份"""
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not os.path.exists(backup_path):
        return jsonify({'error': '备份文件不存在'}), 404
    os.remove(backup_path)
    return jsonify({'success': True})


# ========== 区域 JSON 文件查看/编辑 API ==========

@dispatch_bp.route('/api/dispatch/region_files/<region_key>')
@login_required
def api_region_files(region_key):
    """获取区域关联的文件列表"""
    index = _load_cache_index()
    region = index.get(region_key)
    if not region:
        return _json_resp({'error': f'区域 {region_key} 不存在'}, 404)

    files = []
    for t in region.get('templates', []):
        fpath = _get_template_file_path(region_key, t)
        exists = os.path.exists(fpath)
        task_type = _normalize_task_type(t)
        template_code = t.get('code') or t.get('name', '')
        files.append({
            'filename': t['file'],
            'name': template_code,
            'display_name': t.get('display_name', ''),
            'task_type': task_type,
            'shared': t.get('shared', False),
            'exists': exists,
            'size': os.path.getsize(fpath) if exists else 0
        })
    now_path = _get_region_file(region_key, 'currentCount.json')
    now_exists = os.path.exists(now_path)
    files.append({
        'filename': 'currentCount.json',
        'name': '当前设备',
        'task_type': 'system',
        'shared': False,
        'exists': now_exists,
        'size': os.path.getsize(now_path) if now_exists else 0
    })

    return jsonify({'region_key': region_key, 'files': files})


def _resolve_region_file_path(region_key, filename):
    """解析文件路径，支持共享模板"""
    # 先尝试区域目录
    fpath = _get_region_file(region_key, filename)
    if os.path.exists(fpath):
        return fpath
    # 再尝试共享目录
    shared_path = os.path.join(SHARED_DIR, filename)
    if os.path.exists(shared_path):
        return shared_path
    # 检查配置中该文件是否为共享模板
    index = _load_cache_index()
    region = index.get(region_key)
    if region:
        for t in region.get('templates', []):
            if t['file'] == filename and t.get('shared'):
                return shared_path
    return fpath


@dispatch_bp.route('/api/dispatch/region_file/<region_key>/<filename>')
@login_required
def api_region_file_get(region_key, filename):
    """获取区域文件内容"""
    fpath = _resolve_region_file_path(region_key, filename)
    if not os.path.exists(fpath):
        return jsonify({
            'region_key': region_key,
            'filename': filename,
            'content': '[]',
            'size': 0,
            'exists': False
        })
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({
            'region_key': region_key,
            'filename': filename,
            'content': content,
            'size': os.path.getsize(fpath),
            'exists': True
        })
    except Exception as e:
        return jsonify({'error': f'读取文件失败: {str(e)}'}), 500


@dispatch_bp.route('/api/dispatch/region_file/<region_key>/<filename>', methods=['POST'])
@login_required
@admin_required
def api_region_file_save(region_key, filename):
    """保存区域文件内容"""
    try:
        data = request.get_json()
        content = data.get('content', '')
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            return jsonify({'error': f'JSON 格式错误: {str(e)}'}), 400

        fpath = _resolve_region_file_path(region_key, filename)
        _save_json(fpath, json.loads(content))
        return jsonify({'success': True, 'message': f'{filename} 保存成功'})
    except Exception as e:
        return jsonify({'error': f'保存失败: {str(e)}'}), 500


# ========== 下发记录 API ==========

def write_dispatch_log(region_key, template_name, direction, dispatch_url, request_body, simulated, device_code='', device_num='', result='success', response_body=None, reason='manual'):
    """写入下发记录到 dispatch_log.json"""
    log_file = _get_region_file(region_key, 'dispatch_log.json')
    logs = _load_json(log_file)
    logs.append({
        "time": datetime.now().isoformat(),
        "template_name": template_name,
        "direction": direction,
        "dispatch_url": dispatch_url,
        "request_body": request_body,
        "response_body": response_body,
        "simulated": simulated,
        "deviceCode": device_code,
        "deviceNum": device_num,
        "result": result,
        "reason": reason
    })
    # 仅保留最新10条
    if len(logs) > 10:
        logs = logs[-10:]
    _save_json(log_file, logs)
    return True


@dispatch_bp.route('/api/dispatch/dispatch_log/<region_key>')
@login_required
def api_dispatch_log(region_key):
    """获取下发记录"""
    log_file = _get_region_file(region_key, 'dispatch_log.json')
    logs = _load_json(log_file)
    logs.sort(key=lambda x: x.get('time', ''), reverse=True)
    return jsonify({'region_key': region_key, 'logs': logs})


@dispatch_bp.route('/api/dispatch/dispatch_log/<region_key>', methods=['POST'])
@login_required
@admin_required
def api_dispatch_log_write(region_key):
    """写入下发记录"""
    try:
        data = request.get_json()
        write_dispatch_log(
            region_key=region_key,
            template_name=data.get('template_name', ''),
            direction=data.get('direction', ''),
            dispatch_url=data.get('dispatch_url', ''),
            request_body=data.get('request_body', {}),
            simulated=data.get('simulated', False),
            device_code=data.get('deviceCode', ''),
            device_num=data.get('deviceNum', ''),
            result=data.get('result', 'success')
        )
        return jsonify({'success': True, 'message': '下发记录已保存'})
    except Exception as e:
        return jsonify({'error': f'写入失败: {str(e)}'}), 500


# ========== 执行计算核心逻辑 ==========

def _execute_dispatch(region_key, region, balance):
    """执行下发核心逻辑（供 api_execute 和自动调度共用）"""
    import random as _random
    
    enabled = region.get('enabled', False)
    dispatch_count = balance['dispatch_count']
    direction = balance['direction']
    
    # 选择对应方向的空车模板（只下发空车任务）
    target_template = None
    for t in region.get('templates', []):
        task_type = _normalize_task_type(t)
        if not _is_empty_task(task_type):
            continue
        t_direction = 'in' if _is_in_direction(task_type) else 'out'
        if t_direction == direction:
            target_template = t
            break
    if not target_template:
        return
    
    sim_id = datetime.now().strftime('%Y%m%d%H%M%S')
    simulated = not balance.get('effective_enabled', enabled)
    
    now_dt = datetime.now()
    date_str = now_dt.strftime('%Y-%m-%d %H:%M:%S')
    ms = now_dt.microsecond // 1000
    rand = _random.randint(0, 9999)
    order_id = f"CEM_auto_{date_str}.{ms:03d}__{rand:04d}"
    
    # 空车下发配置：优先使用 empty_dispatch，回退到旧 server 拼接
    empty_dispatch = region.get('empty_dispatch', {})
    template_code = target_template.get('code') or target_template.get('name', '')
    dispatch_template = empty_dispatch.get('template', '') or template_code
    dispatch_url = empty_dispatch.get('url', '')
    if not dispatch_url:
        server = region.get('server', '')
        dispatch_url = f"http://{server}/ics/taskOrder/addTask" if server else ''
    
    request_body = [{
        "modelProcessCode": dispatch_template,
        "priority": 6,
        "orderId": order_id,
        "fromSystem": "CEM_auto",
        "taskOrderDetail": {"taskPath": "", "shelfNumber": ""}
    }]
    
    result = 'simulated'
    response_body = None
    if not simulated and dispatch_url:
        try:
            import urllib.request
            req = urllib.request.Request(dispatch_url,
                data=json.dumps(request_body).encode('utf-8'),
                headers={'Content-Type': 'application/json'})
            resp = urllib.request.urlopen(req, timeout=10)
            resp_raw = resp.read().decode('utf-8')
            response_body = json.loads(resp_raw)
            result = 'success' if response_body.get('code') == 1000 else f'code={response_body.get("code")}'
        except Exception as e:
            result = f'请求失败: {str(e)}'
            response_body = {"error": str(e)}
    
    # 写入模板 JSON
    template_file = _get_template_file_path(region_key, target_template)
    tasks = _load_json(template_file)
    now = datetime.now().isoformat()
    # 模拟下发时：来空车生成新设备，回空车从 currentCount 取真实设备
    now_devices = _load_json(_get_region_file(region_key, 'currentCount.json'))
    for i in range(dispatch_count):
        if simulated and direction == 'out' and now_devices:
            # 回空车模拟：从 currentCount 取真实设备
            dev = now_devices[i % len(now_devices)]
            device_code = dev.get('deviceCode', f'SIM_{sim_id}_{i}')
            device_num = dev.get('deviceNum', f'SIM_D{i}')
        else:
            device_code = f"SIM_{sim_id}_{i}" if simulated else f"DISP_{sim_id}_{i}"
            device_num = f"SIM_D{i}" if simulated else f"DISP_D{i}"
        tasks.append({
            "deviceCode": device_code, "deviceNum": device_num,
            "status": 6, "_simulated": True if simulated else False,
            "order_id": order_id, "create_time": now, "update_time": now
        })
    _save_json(template_file, tasks)
    
    # 判断 reason
    log_url = dispatch_url if not simulated else f'(模拟-未实际请求)\n真实地址: {dispatch_url}'
    if not region.get('enabled', False):
        reason = 'manual_disabled'
    elif balance.get('time_slot_active') and balance['time_slot_matched'] and \
         balance['time_slot_matched'].get('xmin') == -1 and balance['time_slot_matched'].get('xmax') == -1:
        reason = 'time_slot_disabled'
    elif balance.get('time_slot_active'):
        reason = 'time_slot'
    else:
        reason = 'manual'
    
    try:
        write_dispatch_log(
            region_key=region_key, template_name=template_code,
            direction=direction, dispatch_url=log_url, request_body=request_body,
            simulated=simulated, device_code=f"SIM_{sim_id}" if simulated else f"DISP_{sim_id}",
            device_num=f"共{dispatch_count}台", result=result, response_body=response_body, reason=reason
        )
    except Exception as e:
        print(f"[Dispatch] 写入下发记录失败: {e}")
    
    try:
        template_code = target_template.get('code') or target_template.get('name', '')
        # 构造下发报文数据（请求+响应），供前端详情查看
        dispatch_raw = {
            'dispatch_url': dispatch_url,
            'request_body': request_body,
            'response_body': response_body,
            'simulated': simulated,
            'result': result,
            'dispatch_count': dispatch_count,
            'template_code': template_code,
            'direction': direction,
            'reason': reason
        }
        write_global_log('execute', region_key,
            f'{"模拟" if simulated else "真实"}下发 {dispatch_count} 台, 模板:{template_code}, 方向:{direction}, 原因:{reason}',
            raw_data=dispatch_raw)
    except Exception as e:
        print(f"[Dispatch] 写入操作日志失败: {e}")
    
    return {
        'success': True, 'message': f'{"模拟" if simulated else "真实"}下发 {dispatch_count} 台设备',
        'balance': balance, 'dispatched': True, 'simulated': simulated,
        'dispatch_count': dispatch_count, 'template_name': template_code, 'direction': direction
    }


# ========== 执行计算 API ==========

@dispatch_bp.route('/api/dispatch/execute/<region_key>', methods=['POST'])
@login_required
def api_execute(region_key):
    """执行单区域全流程：检查→计算→下发"""
    try:
        index = _load_cache_index()
        region = index.get(region_key)
        if not region:
            return _json_resp({'error': f'区域 {region_key} 不存在'}, 404)
        
        # 1. 计算平衡
        balance = calculate_area_balance(region_key, region)
        
        if balance['direction'] == 'none':
            write_global_log('execute_balanced', region_key, '区域平衡，无需下发')
            return _json_resp({
                'success': True, 'message': '区域平衡，无需下发',
                'balance': balance, 'dispatched': False
            })
        
        # 2. 互斥检查
        if not balance['can_dispatch']:
            write_global_log('execute_mutex', region_key, balance['mutex_reason'], 'warning')
            return _json_resp({'success': False, 'error': balance['mutex_reason'], 'balance': balance}, 409)
        
        # 3. 执行下发
        result = _execute_dispatch(region_key, region, balance)
        if result:
            return _json_resp(result)
        return _json_resp({'error': '下发失败'}, 500)
        
    except Exception as e:
        return _json_resp({'error': f'执行失败: {str(e)}'}, 500)


# ========== 手动发空车 API ==========

@dispatch_bp.route('/api/dispatch/manual_dispatch/<region_key>', methods=['POST'])
@login_required
@admin_required
def api_manual_dispatch(region_key):
    """手动下发空车任务（指定方向），跳过平衡计算和互斥检查"""
    try:
        direction = request.args.get('direction', 'in')
        if direction not in ('in', 'out'):
            return _json_resp({'error': 'direction 必须是 in 或 out'}, 400)
        
        index = _load_cache_index()
        region = index.get(region_key)
        if not region:
            return _json_resp({'error': f'区域 {region_key} 不存在'}, 404)
        
        # 找到对应方向的空车模板
        target_template = None
        for t in region.get('templates', []):
            task_type = _normalize_task_type(t)
            if not _is_empty_task(task_type):
                continue
            t_direction = 'in' if _is_in_direction(task_type) else 'out'
            if t_direction == direction:
                target_template = t
                break
        
        if not target_template:
            return _json_resp({'error': f'区域 {region_key} 没有{direction}方向的空车模板'}, 400)
        
        # 构造一个简单的 balance 用于 _execute_dispatch
        # 手动下发跳过平衡计算，但需要传入真实的 time_slot 状态用于 reason 判断
        time_slot_active = False
        time_slot_matched = None
        time_slots_config = region.get('time_slots', {})
        if time_slots_config.get('enabled', False):
            now_time = datetime.now().strftime('%H:%M')
            for slot in time_slots_config.get('slots', []):
                start = slot.get('start', '00:00')
                end = slot.get('end', '00:00')
                if start <= end:
                    matched = start <= now_time <= end
                else:
                    matched = now_time >= start or now_time <= end
                if matched:
                    time_slot_active = True
                    time_slot_matched = slot
                    break
        balance = {
            'region_key': region_key,
            'direction': direction,
            'dispatch_count': 1,  # 手动下发1台
            'effective_enabled': region.get('enabled', False),
            'time_slot_active': time_slot_active,
            'time_slot_matched': time_slot_matched,
            'can_dispatch': True
        }
        
        result = _execute_dispatch(region_key, region, balance)
        if result:
            template_code = target_template.get('code') or target_template.get('name', '')
            write_global_log('manual_dispatch', region_key,
                f'手动下发 1 台空车, 模板:{template_code}, 方向:{direction}, '
                f'{"模拟" if result.get("simulated") else "真实"}')
            return _json_resp(result)
        return _json_resp({'error': '下发失败'}, 500)
        
    except Exception as e:
        return _json_resp({'error': f'手动下发失败: {str(e)}'}, 500)


# ========== 清理模拟数据 API ==========

@dispatch_bp.route('/api/dispatch/reset_all/<region_key>', methods=['POST'])
@login_required
def api_reset_all(region_key):
    """清空指定区域所有数据（模板JSON + currentCount.json）"""
    try:
        index = _load_cache_index()
        region = index.get(region_key)
        if not region:
            return jsonify({'error': f'区域 {region_key} 不存在'}), 404
        
        cleared = 0
        # 清空所有模板 JSON 文件
        for t in region.get('templates', []):
            fpath = _get_template_file_path(region_key, t)
            if os.path.exists(fpath):
                _save_json(fpath, [])
                cleared += 1
        
        # 清空 currentCount.json
        now_file = _get_region_file(region_key, 'currentCount.json')
        _save_json(now_file, [])
        cleared += 1
        
        write_global_log('reset_all', region_key, f'清空了 {cleared} 个文件')
        return jsonify({'success': True, 'message': f'已清空 {cleared} 个文件', 'cleared': cleared})
    except Exception as e:
        return jsonify({'error': f'清空失败: {str(e)}'}), 500


@dispatch_bp.route('/api/dispatch/clean_simulated/<region_key>', methods=['POST'])
@login_required
def api_clean_simulated(region_key):
    """清理指定区域所有模板 JSON 中的模拟数据"""
    try:
        index = _load_cache_index()
        region = index.get(region_key)
        if not region:
            return jsonify({'error': f'区域 {region_key} 不存在'}), 404
        
        cleaned_count = 0
        
        # 清理所有模板 JSON 文件
        for t in region.get('templates', []):
            fpath = _get_region_file(region_key, t['file'])
            tasks = _load_json(fpath)
            old_len = len(tasks)
            tasks = [task for task in tasks if not task.get('_simulated')]
            new_len = len(tasks)
            if old_len != new_len:
                _save_json(fpath, tasks)
                cleaned_count += (old_len - new_len)
        
        # 清理 currentCount.json
        now_file = _get_region_file(region_key, 'currentCount.json')
        now_devices = _load_json(now_file)
        old_len = len(now_devices)
        now_devices = [d for d in now_devices if not d.get('_simulated')]
        if old_len != len(now_devices):
            _save_json(now_file, now_devices)
            cleaned_count += (old_len - len(now_devices))
        
        write_global_log('clean_simulated', region_key, f'清理了 {cleaned_count} 条模拟数据')
        
        return jsonify({
            'success': True,
            'message': f'已清理 {cleaned_count} 条模拟数据',
            'cleaned_count': cleaned_count
        })
        
    except Exception as e:
        write_global_log('clean_simulated_error', region_key, str(e), 'error')
        return jsonify({'error': f'清理失败: {str(e)}'}), 500


# ========== 自恢复逻辑 ==========

# 自恢复状态记录
_self_heal_status = {}  # {region_key: {last_check, cleaned_count, errors}}
_self_heal_lock = threading.Lock()

SELF_HEAL_DEFAULTS = {
    'enabled': False,
    'check_interval': 300,       # 检查间隔（秒）
    'recover_timeout_minutes': 30,  # 异常超时恢复间隔（分钟）
    'device_query_api': '/ics/out/device/list/deviceInfo'
}


def _query_device_status(server, api_path, area_id, device_code):
    """查询单个设备状态
    api_path 支持两种格式：
    - 相对路径: /ics/out/device/list/deviceInfo → 拼接 http://{server}{api_path}
    - 完整 URL: http://192.168.1.100:8080/ics/... → 直接使用
    """
    if api_path.startswith('http://') or api_path.startswith('https://'):
        url = api_path
    else:
        url = f"http://{server}{api_path}"
    body = {"areaId": str(area_id), "deviceType": "0", "deviceCode": device_code}
    try:
        req = urllib.request.Request(url,
            data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode('utf-8'))
        if data.get('code') == 1000 and data.get('data'):
            return data['data'][0]
        return None
    except Exception as e:
        return None


def _should_clean_device(device_info):
    """判断设备是否应该被清理"""
    if not device_info:
        return True  # 查询失败，保守清理
    state = device_info.get('state', '')
    # 离线/下线/空闲/充电 → 清理
    if state in ('Offline', 'Downlined', 'Idle', 'InCharging'):
        return True
    # 任务中/故障/升级中 → 保留
    return False


def _self_heal_check_region(region_key, region):
    """检查单个区域的异常任务并清理"""
    sh = region.get('self_heal', {})
    if not sh.get('enabled', SELF_HEAL_DEFAULTS['enabled']):
        return {'cleaned': 0, 'errors': []}
    
    timeout_minutes = sh.get('recover_timeout_minutes', SELF_HEAL_DEFAULTS['recover_timeout_minutes'])
    server = region.get('server', '')
    area_id = region.get('areaId', '0')
    api_path = sh.get('device_query_api', SELF_HEAL_DEFAULTS['device_query_api'])
    
    if not server:
        return {'cleaned': 0, 'errors': ['无服务器配置']}
    
    from datetime import timedelta
    threshold = (datetime.now() - timedelta(minutes=timeout_minutes)).isoformat()
    cleaned = 0
    errors = []
    
    for t in region.get('templates', []):
        fpath = _get_template_file_path(region_key, t)
        tasks = _load_json(fpath)
        stale_tasks = [task for task in tasks
                       if task.get('status') == 6
                       and not task.get('_simulated')
                       and task.get('create_time', '') < threshold]
        
        if not stale_tasks:
            continue
        
        # 最多检查10个异常任务
        for task in stale_tasks[:10]:
            device_code = task.get('deviceCode', '')
            if not device_code:
                continue
            device_info = _query_device_status(server, api_path, area_id, device_code)
            if _should_clean_device(device_info):
                # 从模板 JSON 删除
                tasks = [t for t in tasks if t.get('deviceCode') != device_code or t.get('status') != 6]
                # 从 currentCount 删除
                now_file = _get_region_file(region_key, 'currentCount.json')
                now_devices = _load_json(now_file)
                now_devices = [d for d in now_devices if d.get('deviceCode') != device_code]
                _save_json(now_file, now_devices)
                cleaned += 1
        
        # 保存模板 JSON（在循环外统一保存，避免多次 I/O）
        _save_json(fpath, tasks)
    
    return {'cleaned': cleaned, 'errors': errors}


def _self_heal_check_all():
    """检查所有区域（后台线程调用）"""
    index = _load_cache_index()
    total_cleaned = 0
    for rk, region in index.items():
        if not isinstance(region, dict) or 'templates' not in region:
            continue
        sh = region.get('self_heal', {})
        if not sh.get('enabled', SELF_HEAL_DEFAULTS['enabled']):
            continue
        result = _self_heal_check_region(rk, region)
        total_cleaned += result['cleaned']
        with _self_heal_lock:
            _self_heal_status[rk] = {
                'last_check': datetime.now().isoformat(),
                'cleaned_count': result['cleaned'],
                'errors': result['errors']
            }
        if result['cleaned'] > 0:
            write_global_log('self_heal', rk,
                f'自恢复清理 {result["cleaned"]} 个异常任务')
    return total_cleaned


def _start_self_heal_thread():
    """启动自恢复后台线程"""
    def _loop():
        while True:
            try:
                index = _load_cache_index()
                for rk, region in index.items():
                    if not isinstance(region, dict):
                        continue
                    sh = region.get('self_heal', {})
                    if not sh.get('enabled', SELF_HEAL_DEFAULTS['enabled']):
                        continue
                    interval = sh.get('check_interval', SELF_HEAL_DEFAULTS['check_interval'])
                    # 检查是否需要执行
                    with _self_heal_lock:
                        last = _self_heal_status.get(rk, {}).get('last_check', '')
                    if last:
                        elapsed = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
                        if elapsed < interval:
                            continue
                    _self_heal_check_region(rk, region)
                time.sleep(30)  # 每30秒检查一次是否需要执行
            except Exception as e:
                print(f"[SelfHeal] 后台线程异常: {e}")
                time.sleep(60)
    
    t = threading.Thread(target=_loop, daemon=True)
    t.start()


# ========== 自恢复 API ==========

@dispatch_bp.route('/api/dispatch/self_heal/status')
@login_required
def api_self_heal_status():
    """获取自恢复状态"""
    with _self_heal_lock:
        return jsonify({'status': dict(_self_heal_status)})


@dispatch_bp.route('/api/dispatch/self_heal/check', methods=['POST'])
@login_required
@admin_required
def api_self_heal_check():
    """手动触发自恢复检查"""
    try:
        region_key = request.args.get('region_key', '')
        if region_key:
            index = _load_cache_index()
            region = index.get(region_key)
            if not region:
                return jsonify({'error': f'区域 {region_key} 不存在'}), 404
            result = _self_heal_check_region(region_key, region)
            with _self_heal_lock:
                _self_heal_status[region_key] = {
                    'last_check': datetime.now().isoformat(),
                    'cleaned_count': result['cleaned'],
                    'errors': result['errors']
                }
            return jsonify({'success': True, 'region_key': region_key, **result})
        else:
            total = _self_heal_check_all()
            return jsonify({'success': True, 'total_cleaned': total})
    except Exception as e:
        return jsonify({'error': f'自恢复检查失败: {str(e)}'}), 500
