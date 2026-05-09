#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调车管理路由蓝图 - 空车调车模块
"""

from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for, Response
from functools import wraps
from datetime import datetime
import os, json, time, threading, subprocess

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
GLOBAL_LOG_ARCHIVE_DIR = os.path.join(DATA_DIR, 'logs')  # 大日志归档目录
DAILY_STATS_PATH = os.path.join(DATA_DIR, 'daily_stats.json')
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


def _normalize_order_id(order_id):
    """规范化 order_id：去掉跨环境子任务的后缀 _N_XXXX（仅单下划线）
    例如: DHB2-7E0FCFD938794DF0BA6A4561FF8B67BD_1_5554 -> DHB2-7E0FCFD938794DF0BA6A4561FF8B67BD
          CEM_auto_2026-05-07_09:38:49.304__4974_1_4056 -> CEM_auto_2026-05-07_09:38:49.304__4974
    """
    if not order_id:
        return order_id
    import re
    # 只匹配单下划线后跟数字的模式，保护 __ 双下划线
    return re.sub(r'(?<!_)_\d+_\d+$', '', order_id)


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
    """加载 JSON 文件，支持列表和字典"""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
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

def _get_archive_log_path(date_str=None):
    """获取大日志归档文件路径"""
    os.makedirs(GLOBAL_LOG_ARCHIVE_DIR, exist_ok=True)
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    return os.path.join(GLOBAL_LOG_ARCHIVE_DIR, f'global_log_{date_str}.json')


def _load_all_logs():
    """加载所有日志：热数据 + 2天内的大日志"""
    logs = _load_json(GLOBAL_LOG_PATH)
    # 加载最近2天的大日志
    from datetime import timedelta
    for i in range(2):
        date_str = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        archive_path = _get_archive_log_path(date_str)
        if os.path.exists(archive_path):
            archive_logs = _load_json(archive_path)
            if isinstance(archive_logs, list):
                logs.extend(archive_logs)
    return logs


def _clean_old_archive_logs():
    """清理2天前的大日志文件"""
    from datetime import timedelta
    cutoff_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
    if os.path.exists(GLOBAL_LOG_ARCHIVE_DIR):
        for f in os.listdir(GLOBAL_LOG_ARCHIVE_DIR):
            if f.startswith('global_log_') and f.endswith('.json'):
                date_part = f.replace('global_log_', '').replace('.json', '')
                if date_part < cutoff_date:
                    try:
                        os.remove(os.path.join(GLOBAL_LOG_ARCHIVE_DIR, f))
                    except:
                        pass


def write_global_log(action, region_key, detail='', level='info', raw_data=None):
    """写入全局操作日志
    
    - 热数据 global_log.json：保留最新200条，前端实时展示
    - 大日志 global_log_YYYY-MM-DD.json：满200条时批量追加旧日志，保留2天
    
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
        oid = raw_data.get('orderId') or raw_data.get('order_id', '')
        for i in range(len(logs) - 1, -1, -1):
            log = logs[i]
            if log.get('action') != 'report_status' or not log.get('raw_data'):
                continue
            rd = log['raw_data']
            r_tn = rd.get('modelProcessCode') or rd.get('template_name', '')
            r_dn = rd.get('deviceNum', '')
            r_st = rd.get('status', '')
            if r_tn == tn and r_dn == dn and str(r_st) == str(st):
                log['time'] = datetime.now().isoformat()
                r_oid = rd.get('orderId') or rd.get('order_id', '')
                if r_oid == oid:
                    dup_count = log.get('dup_count', 1) + 1
                    log['dup_count'] = dup_count
                    log['detail'] = f'(重复#{dup_count}) ' + detail
                else:
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
    
    # 超过200条：把最旧的日志批量追加到大日志，保留最新200条
    if len(logs) > 200:
        overflow = logs[:-200]  # 超出200条的部分
        logs = logs[-200:]      # 保留最新200条
        # 追加到大日志文件
        archive_path = _get_archive_log_path()
        archive_logs = _load_json(archive_path)
        if not isinstance(archive_logs, list):
            archive_logs = []
        archive_logs.extend(overflow)
        # 大日志最多500条
        if len(archive_logs) > 500:
            archive_logs = archive_logs[-500:]
        _save_json(archive_path, archive_logs)
    
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


def _update_daily_stats(region_key, field):
    """更新每20分钟统计
    field: 'empty_in' | 'empty_out' | 'load_in' | 'load_out' | 'dispatch_in' | 'dispatch_out'
    """
    now = datetime.now()
    # 分钟取整到 0/20/40
    minute_block = (now.minute // 20) * 20
    slot_key = now.strftime('%Y-%m-%dT%H:') + f'{minute_block:02d}'
    stats = _load_json(DAILY_STATS_PATH)
    if not isinstance(stats, dict):
        stats = {}
    if slot_key not in stats:
        stats[slot_key] = {}
    if region_key not in stats[slot_key]:
        stats[slot_key][region_key] = {
            'empty_in': 0, 'empty_out': 0, 'load_in': 0, 'load_out': 0,
            'dispatch_in': 0, 'dispatch_out': 0
        }
    stats[slot_key][region_key][field] = stats[slot_key][region_key].get(field, 0) + 1
    # 只保留最近24小时
    from datetime import timedelta
    cutoff = (now - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M')
    stats = {k: v for k, v in stats.items() if k >= cutoff}
    _save_json(DAILY_STATS_PATH, stats)


@dispatch_bp.route('/api/dispatch/global_log')
@login_required
def api_global_log():
    """获取全局操作日志（支持增量拉取 ?since=timestamp）"""
    since = request.args.get('since', '')
    logs = _load_json(GLOBAL_LOG_PATH)
    
    if since:
        # 增量模式：只返回比 since 新的日志
        logs = [log for log in logs if log.get('time', '') > since]
    
    logs.sort(key=lambda x: x.get('time', ''), reverse=True)
    return jsonify({'logs': logs})


@dispatch_bp.route('/api/dispatch/global_log/export')
@login_required
def api_global_log_export():
    """导出全部日志（热数据+大日志）为JSON文件下载"""
    all_logs = _load_all_logs()
    all_logs.sort(key=lambda x: x.get('time', ''), reverse=True)
    return Response(
        json.dumps(all_logs, ensure_ascii=False, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename=dispatch_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'}
    )


# ========== 核心计算逻辑 ==========

def _get_last_calc_info(region_key):
    """从 global_log 读取该区域最近一条调度相关事件"""
    logs = _load_json(GLOBAL_LOG_PATH)
    calc_actions = {'report_status', 'execute', 'execute_balanced', 'execute_mutex', 'manual_dispatch', 'self_heal'}
    trigger_map = {
        'report_status': '状态上报',
        'execute': '自动调度',
        'execute_balanced': '计算(平衡)',
        'execute_mutex': '计算(互斥)',
        'manual_dispatch': '手动发车',
        'self_heal': '自恢复'
    }
    direction_map = {'in': '调入', 'out': '调出'}
    for log in reversed(logs):
        if log.get('region_key') == region_key and log.get('action') in calc_actions:
            action = log.get('action', '')
            trigger_source = trigger_map.get(action, action)
            # 从 raw_data 提取方向信息
            direction = ''
            rd = log.get('raw_data', {})
            if isinstance(rd, dict):
                d = rd.get('direction', '')
                if d in direction_map:
                    direction = direction_map[d]
            # 如果 raw_data 没有，尝试从 detail 解析
            if not direction:
                detail = log.get('detail', '')
                if '方向:in' in detail:
                    direction = '调入'
                elif '方向:out' in detail:
                    direction = '调出'
            if direction:
                trigger_source = f'{trigger_source}({direction})'
            return {
                "time": log.get('time', ''),
                "action": action,
                "detail": log.get('detail', ''),
                "level": log.get('level', 'info'),
                "trigger_source": trigger_source
            }
    return None


def _calc_remaining_minutes(slot):
    """计算当前时段剩余分钟数（含跨天）"""
    now = datetime.now()
    now_minutes = now.hour * 60 + now.minute
    end_str = slot.get('end', '00:00')
    eh, em = map(int, end_str.split(':'))
    end_minutes = eh * 60 + em
    # 处理跨天
    if end_minutes <= now_minutes:
        end_minutes += 24 * 60
    return end_minutes - now_minutes


def _resolve_time_slot(slots):
    """
    用优先级解析分时配置，替代旧的时间范围最小逻辑。
    返回: (active, matched_slot, matched_count, all_matched_names, remaining_minutes)
    """
    if not slots:
        return False, None, 0, [], 0
    
    now_time = datetime.now().strftime('%H:%M')
    matched = []
    
    for slot in slots:
        start = slot.get('start', '00:00')
        end = slot.get('end', '00:00')
        priority = slot.get('priority', 999)
        
        # 判断是否匹配当前时间（含跨天）
        if start <= end:
            is_match = start <= now_time <= end
        else:
            is_match = now_time >= start or now_time <= end
        
        if is_match:
            matched.append((priority, slot))
    
    if not matched:
        return False, None, 0, [], 0
    
    # 按优先级排序，选优先级最高的（priority 最小）
    matched.sort(key=lambda x: x[0])
    best = matched[0][1]
    all_names = [s.get('name') or f"{s['start']}~{s['end']}" for _, s in matched]
    remaining = _calc_remaining_minutes(best)
    
    return True, best, len(matched), all_names, remaining


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
    # 自动补全旧数据的 priority 和 name
    time_slot_active = False
    time_slot_matched = None
    time_slot_matched_count = 0
    time_slot_all_matched = []
    time_slot_remaining = 0
    time_slots_config = region_config.get('time_slots', {})
    if time_slots_config.get('enabled', False):
        slots = time_slots_config.get('slots', [])
        # 自动补全旧数据：无 priority 则按索引生成，无 name 则留空
        for idx, slot in enumerate(slots):
            if 'priority' not in slot:
                slot['priority'] = idx + 1
            if 'name' not in slot:
                slot['name'] = ''
        
        time_slot_active, best_slot, time_slot_matched_count, time_slot_all_matched, time_slot_remaining = _resolve_time_slot(slots)
        if time_slot_active and best_slot:
            xmin = best_slot.get('xmin', xmin)
            xmax = best_slot.get('xmax', xmax)
            time_slot_matched = best_slot
    
    # 分时配置中 xmin=-1, xmax=-1 表示禁用真实任务（仅在手动启用时生效）
    effective_enabled = enabled
    if enabled and time_slot_active and xmin == -1 and xmax == -1:
        effective_enabled = False  # 走模拟逻辑
    
    # 统计 a: 来区域模板中 status=6 的任务数
    a = 0
    incoming_templates = []
    outgoing_templates = []
    pending_devices = []  # 执行中设备列表（status=6 且有 deviceCode）
    
    for t in region_config.get('templates', []):
        fpath = _get_template_file_path(region_key, t)
        tasks = _load_json(fpath)
        # 普通任务（不含 _low_battery）
        normal_tasks = [task for task in tasks if task.get('status') == 6 and not task.get('_low_battery')]
        # 低电量任务
        low_battery_tasks = [task for task in tasks if task.get('status') == 6 and task.get('_low_battery')]
        count = len(normal_tasks)
        low_battery_count = len(low_battery_tasks)
        task_type = _normalize_task_type(t)
        
        # code: 模板代码（计算用），display_name: 看板显示名称（可自定义中文名）
        template_code = t.get('code') or t.get('name', '')
        display_name = t.get('display_name') or t.get('name', '')
        item = {"code": template_code, "name": display_name, "count": count,
                "low_battery_count": low_battery_count, "task_type": task_type}
        if _is_in_direction(task_type):
            a += count  # 低电量不计入 a
            incoming_templates.append(item)
        else:
            outgoing_templates.append(item)
        
        # 收集执行中设备（status=6 且有 deviceCode，不含低电量任务）
        for task in normal_tasks:
            if task.get('deviceCode'):
                pending_devices.append({
                    "deviceNum": task.get('deviceNum', ''),
                    "deviceCode": task.get('deviceCode', ''),
                    "template": template_code,
                    "task_type": task_type,
                    "order_id": task.get('order_id', ''),
                    "create_time": task.get('create_time', '')
                })
    
    # 统计 b: 离开模板中 status=6 的任务数（不含低电量）
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
            pending = [task for task in tasks if task.get('status') == 6 and not task.get('_low_battery')]
            if pending:
                # 如果要下发去空车(in)，但存在未完成的回空车(out)任务
                # 如果要下发回空车(out)，但存在未完成的去空车(in)任务
                t_direction = 'in' if _is_in_direction(task_type) else 'out'
                if t_direction != direction:
                    can_dispatch = False
                    template_code = t.get('code') or t.get('name', '')
                    mutex_reason = f"pending {template_code} task, mutex"
                    break
    
    # 最近一次调度事件
    last_calc_info = _get_last_calc_info(region_key)
    
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
        "current_devices": [
            {"deviceNum": d.get('deviceNum', ''), "deviceCode": d.get('deviceCode', ''),
             "create_time": d.get('create_time', ''), "state": d.get('state', 'pending'),
             "battery": d.get('battery', '')}
            for d in now_devices
        ],
        "pending_devices": pending_devices,
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
        "time_slot_matched_count": time_slot_matched_count,
        "time_slot_all_matched": time_slot_all_matched,
        "time_slot_remaining": time_slot_remaining,
        "last_calc_info": last_calc_info,
        "low_battery_threshold": _get_low_battery_threshold(region_config.get('self_heal', {})),
        "poll_dispatch_interval": _load_cache_index().get('poll_dispatch_interval', _POLL_DISPATCH_DEFAULT_INTERVAL),
        "poll_dispatch_last": _poll_dispatch_last.get(region_key, 0),
        "templates": {
            "incoming": incoming_templates,
            "outgoing": outgoing_templates
        },
        "daily_stats": (_load_json(DAILY_STATS_PATH) or {}).get(datetime.now().strftime('%Y-%m-%dT%H:') + f'{(datetime.now().minute // 20) * 20:02d}', {}).get(region_key, {}),
        "daily_stats_history": _load_json(DAILY_STATS_PATH) or {}
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
        "areas": areas,
        "refresh_config": {
            "data_interval": max(index.get('data_refresh_interval', 5000), 1000),
            "log_interval": max(index.get('log_refresh_interval', 2000), 500)
        }
    }


# ========== 状态上报处理 ==========

def _clean_by_order_id_across_all_regions(order_id, device_code, device_num=''):
    """当 status=8 无法匹配模板时，遍历所有区域所有模板按 order_id 清理
    
    同时根据匹配到的模板类型操作 currentCount：
    - 来方向（empty_in/load_in）：写入 currentCount
    - 回方向（empty_out/load_out）：从 currentCount 删除
    """
    index = _load_cache_index()
    cleaned = 0
    print(f"[Dispatch] _clean_by_order_id_across_all_regions: order_id={order_id}, device_code={device_code}")
    for rk, region in index.items():
        if not isinstance(region, dict) or 'templates' not in region:
            continue
        for t in region.get('templates', []):
            fpath = _get_template_file_path(rk, t)
            tasks = _load_json(fpath)
            old_count = len(tasks)
            # 按 order_id 匹配删除，同时记录被删任务的信息
            removed_tasks = [task for task in tasks if task.get('order_id') == order_id and task.get('status') == 6]
            new_tasks = [task for task in tasks if not (task.get('order_id') == order_id and task.get('status') == 6)]
            if len(new_tasks) < old_count:
                _save_json(fpath, new_tasks)
                removed = old_count - len(new_tasks)
                cleaned += removed
                print(f"[Dispatch] _clean_by_order_id: 按order_id清理 {rk}/{t.get('code', t.get('name', ''))} 删除了{removed}条")
                
                # 根据模板类型操作 currentCount
                task_type = _normalize_task_type(t)
                _dc = device_code
                _dn = device_num
                # 从被删任务中获取设备信息
                if (not _dc or not _dn) and removed_tasks:
                    rt = removed_tasks[0]
                    if not _dc: _dc = rt.get('deviceCode', '')
                    if not _dn: _dn = rt.get('deviceNum', '')
                
                if _dc:
                    now_file = _get_region_file(rk, 'currentCount.json')
                    now_devices = _load_json(now_file)
                    if _is_in_direction(task_type):
                        # 来方向：写入 currentCount
                        if not any(d.get('deviceCode') == _dc for d in now_devices):
                            now_devices.append({
                                'deviceCode': _dc, 'deviceNum': _dn or '',
                                'order_id': order_id, 'create_time': datetime.now().isoformat(),
                                'state': 'pending'
                            })
                            _save_json(now_file, now_devices)
                            print(f"[Dispatch] _clean_by_order_id: currentCount {rk} +1 (来方向)")
                    else:
                        # 回方向：从 currentCount 删除
                        old_cc = len(now_devices)
                        now_devices = [d for d in now_devices if d.get('deviceCode') != _dc]
                        if len(now_devices) < old_cc:
                            _save_json(now_file, now_devices)
                            print(f"[Dispatch] _clean_by_order_id: currentCount {rk} -1 (回方向)")
            tasks = new_tasks
            # 也按 deviceCode 匹配删除
            if device_code:
                new_tasks2 = [task for task in tasks if not (task.get('deviceCode') == device_code and task.get('status') == 6)]
                if len(new_tasks2) < len(tasks):
                    _save_json(fpath, new_tasks2)
                    removed2 = len(tasks) - len(new_tasks2)
                    cleaned += removed2
                    print(f"[Dispatch] _clean_by_order_id: 按deviceCode清理 {rk}/{t.get('code', t.get('name', ''))} 删除了{removed2}条")
    print(f"[Dispatch] _clean_by_order_id_across_all_regions: 共清理{cleaned}条")
    return cleaned


def _update_by_order_id_across_all_regions(order_id, device_code, device_num):
    """当 status=6 无法匹配模板时，遍历所有区域按 order_id 更新设备信息"""
    index = _load_cache_index()
    updated = 0
    for rk, region in index.items():
        if not isinstance(region, dict) or 'templates' not in region:
            continue
        for t in region.get('templates', []):
            fpath = _get_template_file_path(rk, t)
            tasks = _load_json(fpath)
            found = False
            for task in tasks:
                if task.get('order_id') == order_id and task.get('status') == 6:
                    task['deviceCode'] = device_code
                    task['deviceNum'] = device_num
                    task['update_time'] = datetime.now().isoformat()
                    found = True
                    updated += 1
                    break
            if found:
                _save_json(fpath, tasks)
                print(f"[Dispatch] _update_by_order_id: 更新 {rk}/{t.get('code', t.get('name', ''))} device={device_num}")
    if updated == 0:
        print(f"[Dispatch] _update_by_order_id: 未找到匹配 order_id={order_id}, device={device_num}({device_code})")
    return updated


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
    # 兼容 orderId 和 order_id，并规范化去掉跨环境子任务后缀 _N_XXXX
    order_id = _normalize_order_id(data.get('orderId') or data.get('order_id', ''))
    
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
        if order_id:
            if status == 6:
                # status=6：按 order_id 跨区域更新设备信息
                updated = _update_by_order_id_across_all_regions(order_id, device_code, device_num)
                if updated:
                    return True, f"无法匹配模板但按order_id更新了{updated}条 (region_key={region_key}, template={template_name})", True
            else:
                # status=8 等完成状态：遍历所有区域按 order_id 清理
                cleaned = _clean_by_order_id_across_all_regions(order_id, device_code, device_num)
                if cleaned:
                    return True, f"无法匹配模板但按order_id清理了{cleaned}条 (region_key={region_key}, template={template_name})", True
        # 记录未匹配上报到操作日志（方便排查）
        try:
            write_global_log('report_unmatched', region_key or '?',
                f'未匹配上报: template={template_name}, device={device_num}({device_code}), status={status}, order_id={order_id}',
                raw_data={'data': data, 'reason': '模板code在配置中不存在或无region_key'})
        except: pass
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
        if order_id:
            if status == 6:
                updated = _update_by_order_id_across_all_regions(order_id, device_code, device_num)
                if updated:
                    return True, f"模板不在区域但按order_id更新了{updated}条 (region_key={region_key}, template={template_name})", True
            else:
                cleaned = _clean_by_order_id_across_all_regions(order_id, device_code, device_num)
                if cleaned:
                    return True, f"模板不在区域但按order_id清理了{cleaned}条 (region_key={region_key}, template={template_name})", True
        # 记录未匹配上报到操作日志
        try:
            write_global_log('report_unmatched', region_key,
                f'未匹配上报(模板不在区域): template={template_name}, device={device_num}({device_code}), status={status}, order_id={order_id}',
                raw_data={'data': data, 'reason': f'模板code在区域{region_key}中不存在'})
        except: pass
        print(f"[Dispatch] report_status 模板不存在: region_key={region_key}, template={template_name}")
        return True, f"模板 {template_name} 不存在于区域 {region_key}，已接收上报", False
    
    task_type = _normalize_task_type(template_config)
    template_file = _get_template_file_path(region_key, template_config)
    now_file = _get_region_file(region_key, 'currentCount.json')
    
    now = datetime.now().isoformat()
    
    # status=7：任务下发失败（如设备已有任务），只清理模板JSON，不操作currentCount（车没走）
    if status == 7:
        tasks = _load_json(template_file)
        old_count = len(tasks)
        if order_id:
            tasks = [t for t in tasks if not (t.get('order_id') == order_id and t.get('status') == 6)]
        if device_code:
            tasks = [t for t in tasks if not (t.get('deviceCode') == device_code and t.get('status') == 6)]
        template_removed = old_count - len(tasks)
        if template_removed > 0:
            _save_json(template_file, tasks)
        return True, f'模板-{template_name} -{template_removed} (status=7下发失败，车未移动)', True
    
    if status in (6, 10):
        # 任务开始（运行中）：记录到模板 JSON
        # 匹配策略（两级）：
        #   1. 先按 deviceCode 匹配（负载任务）
        #   2. 没匹配到 → 按 order_id 匹配 deviceCode 为空的记录（空车任务，下发时无设备号）
        tasks = _load_json(template_file)
        existing = None
        match_level = ''
        for t in tasks:
            if t.get('deviceCode') == device_code and t.get('status') == 6:
                existing = t
                match_level = 'deviceCode'
                break
        # 第2级：按 order_id 匹配（空车任务，下发时可能已指定设备也可能未指定）
        if not existing and order_id:
            for t in tasks:
                if t.get('order_id') == order_id and t.get('status') == 6:
                    existing = t
                    match_level = 'order_id'
                    break
        
        if existing:
            # 覆盖更新
            old_dc = existing.get('deviceCode', '')[-8:] if existing.get('deviceCode') else '?'
            existing['deviceNum'] = device_num
            existing['deviceCode'] = device_code
            existing['order_id'] = order_id
            existing['shelfNumber'] = data.get('shelfNumber', '')
            existing['shelfCurrPosition'] = data.get('shelfCurrPosition', '')
            existing['update_time'] = now
            change_summary = f'模板更新 {template_name} (共{len(tasks)}条)'
            print(f"[ReportStatus] status={status} 覆盖更新 | 模板={template_name} device={device_num}({device_code[-8:]}) order_id={order_id} 匹配方式={match_level} 旧device={old_dc}")
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
            print(f"[ReportStatus] status={status} 新增 | 模板={template_name} device={device_num}({device_code[-8:]}) order_id={order_id}")
        _save_json(template_file, tasks)
        
    else:
        # 非 6 的状态（包括 8=完成 及其他状态）：执行清理逻辑
        # 从模板 JSON 中删除该设备记录
        # 匹配策略（三级，按优先级）：
        #   1. deviceCode + order_id 精确匹配（负载任务，同一设备可能有多个子任务）
        #   2. order_id 匹配（空车任务，deviceCode 为空）
        #   3. deviceCode 匹配（兜底）
        tasks = _load_json(template_file)
        old_count = len(tasks)
        
        # 在清理前先保存匹配到的任务信息（用于后续 currentCount 更新）
        _matched_task = None
        # 第1级：deviceCode + order_id 精确匹配
        matched = [t for t in tasks if t.get('deviceCode') == device_code and t.get('order_id') == order_id and t.get('status') == 6]
        if matched:
            _matched_task = matched[0]
            tasks = [t for t in tasks if not (t.get('deviceCode') == device_code and t.get('order_id') == order_id and t.get('status') == 6)]
        elif order_id:
            # 第2级：order_id 匹配
            for t in tasks:
                if t.get('order_id') == order_id and t.get('status') == 6:
                    _matched_task = t
                    break
            tasks = [t for t in tasks if not (t.get('order_id') == order_id and t.get('status') == 6)]
        else:
            # 第3级：deviceCode 匹配（兜底）
            for t in tasks:
                if t.get('deviceCode') == device_code and t.get('status') == 6:
                    _matched_task = t
                    break
            tasks = [t for t in tasks if not (t.get('deviceCode') == device_code and t.get('status') == 6)]
        _save_json(template_file, tasks)
        template_removed = old_count - len(tasks)
        
        # 更新 currentCount.json（所有类型都更新，因为车确实在移动）
        # 共享模板：需要遍历所有共享该模板的区域，同步清理各自的 currentCount.json
        is_shared = template_config.get('shared', False)
        regions_to_update = []
        if is_shared:
            # 收集所有共享该模板的区域
            for rk, r in index.items():
                if not isinstance(r, dict) or 'templates' not in r:
                    continue
                for rt in r.get('templates', []):
                    rt_code = rt.get('code') or rt.get('name', '')
                    if rt_code == template_name and rt.get('shared'):
                        regions_to_update.append(rk)
                        break
        if not regions_to_update:
            regions_to_update = [region_key]
        
        cc_change_parts = []
        for rk in regions_to_update:
            rk_now_file = _get_region_file(rk, 'currentCount.json')
            rk_now_devices = _load_json(rk_now_file)
            rk_cc_change = ''
            if _is_in_direction(task_type):
                # 来区域完成：写入 currentCount.json
                # 优先使用上报的设备信息，否则从匹配到的任务中获取
                _device_code = device_code or (_matched_task.get('deviceCode', '') if _matched_task else '')
                _device_num = device_num or (_matched_task.get('deviceNum', '') if _matched_task else '')
                if not _device_code and not _device_num:
                    rk_cc_change = f'{rk}:跳过(无设备信息)'
                elif not any(d.get('deviceCode') == _device_code for d in rk_now_devices):
                    rk_now_devices.append({
                        "deviceCode": _device_code,
                        "deviceNum": _device_num,
                        "order_id": order_id,
                        "shelfNumber": data.get('shelfNumber', ''),
                        "create_time": now,
                        "state": "pending"
                    })
                    rk_cc_change = f'{rk}:+1(共{len(rk_now_devices)})'
            else:
                # 离开完成：从 currentCount.json 删除
                old_cc = len(rk_now_devices)
                rk_now_devices = [d for d in rk_now_devices if d.get('deviceCode') != device_code]
                if len(rk_now_devices) < old_cc:
                    rk_cc_change = f'{rk}:-1(共{len(rk_now_devices)})'
                    # 记录设备从网格消失事件到操作日志
                    try:
                        write_global_log('device_leave', rk,
                            f'设备离开网格: {device_num}({device_code[-8:] if device_code else "?"}), '
                            f'模板:{template_name}, status:{status}, order_id:{order_id}',
                            raw_data={'deviceCode': device_code, 'deviceNum': device_num,
                                      'template': template_name, 'status': status, 'order_id': order_id,
                                      'region_key': rk, 'currentCount_after': len(rk_now_devices)})
                    except: pass
            _save_json(rk_now_file, rk_now_devices)
            if rk_cc_change:
                cc_change_parts.append(rk_cc_change)
        
        cc_change = ', currentCount ' + '; '.join(cc_change_parts) if cc_change_parts else ''
        change_summary = f'模板-{template_name} -{template_removed}{cc_change}'
        # 更新每日统计（status=8 完成时）
        if status == 8:
            _update_daily_stats(region_key, task_type)
    
    # 更新设备历史记录（记录这个区域48小时内来过哪些设备）
    if device_code:
        try:
            _touch_device_history(region_key, device_code, device_num)
        except Exception as e:
            print(f"[Dispatch] _touch_device_history 失败: {e}")
    
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


@dispatch_bp.route('/api/dispatch/device_info')
@login_required
def api_device_info():
    """获取设备详情（按 deviceNum 查询）"""
    device_num = request.args.get('deviceNum', '')
    if not device_num:
        return jsonify({'error': '缺少 deviceNum 参数'}), 400
    
    # 从所有区域查找该设备
    index = _load_cache_index()
    device_info = None
    found_region = None
    
    for rk, region in index.items():
        if not isinstance(region, dict):
            continue
        # 查 currentCount.json
        now_file = _get_region_file(rk, 'currentCount.json')
        now_devices = _load_json(now_file)
        for d in now_devices:
            if d.get('deviceNum') == device_num:
                device_info = {
                    'deviceNum': d.get('deviceNum', ''),
                    'deviceCode': d.get('deviceCode', ''),
                    'status': 'idle',
                    'region_key': rk,
                    'order_id': d.get('order_id', ''),
                    'shelfNumber': d.get('shelfNumber', ''),
                    'create_time': d.get('create_time', '')
                }
                found_region = rk
                break
        if device_info:
            break
        
        # 查模板 JSON 中的执行中任务
        for t in region.get('templates', []):
            fpath = _get_template_file_path(rk, t)
            tasks = _load_json(fpath)
            for task in tasks:
                if task.get('deviceNum') == device_num and task.get('status') == 6:
                    task_type = _normalize_task_type(t)
                    template_code = t.get('code') or t.get('name', '')
                    device_info = {
                        'deviceNum': task.get('deviceNum', ''),
                        'deviceCode': task.get('deviceCode', ''),
                        'status': 'running',
                        'region_key': rk,
                        'template': template_code,
                        'task_type': task_type,
                        'order_id': task.get('order_id', ''),
                        'shelfNumber': task.get('shelfNumber', ''),
                        'create_time': task.get('create_time', ''),
                        'update_time': task.get('update_time', '')
                    }
                    found_region = rk
                    break
            if device_info:
                break
        if device_info:
            break
    
    if not device_info:
        return jsonify({'error': f'设备 {device_num} 未找到'}), 404
    
    # 从热数据+大日志中查询该设备的操作历史
    logs = _load_all_logs()
    history = []
    for log in reversed(logs):
        detail = log.get('detail', '')
        if device_num in detail:
            history.append({
                'time': log.get('time', ''),
                'action': log.get('action', ''),
                'detail': detail,
                'level': log.get('level', 'info')
            })
        if len(history) >= 20:
            break
    
    device_info['history'] = history
    return jsonify(device_info)


@dispatch_bp.route('/api/dispatch/device_check', methods=['POST'])
@login_required
def api_device_check():
    """设备检查：查询设备实时状态，离线/下线则自动清理"""
    try:
        data = request.get_json() or {}
        region_key = data.get('region_key', '')
        device_code = data.get('deviceCode', '')
        device_num = data.get('deviceNum', '')
        if not region_key or not device_code:
            return jsonify({'error': '缺少 region_key 或 deviceCode'}), 400
        
        index = _load_cache_index()
        region = index.get(region_key)
        if not region:
            return jsonify({'error': f'区域 {region_key} 不存在'}), 404
        
        sh = region.get('self_heal', {})
        api_path = sh.get('device_query_api', SELF_HEAL_DEFAULTS['device_query_api'])
        area_id = region.get('areaId', '0')
        
        # 构造请求报文
        request_body = {"areaId": str(area_id), "deviceType": "0", "deviceCode": device_code}
        if api_path.startswith('http://') or api_path.startswith('https://'):
            request_url = api_path
        else:
            request_url = f"http://{api_path}"
        
        # 查询设备实时状态（自己发请求以获取完整响应）
        device_info = None
        response_body = None
        if 'XX' not in api_path:
            try:
                import urllib.request
                req = urllib.request.Request(request_url,
                    data=json.dumps(request_body).encode('utf-8'),
                    headers={'Content-Type': 'application/json'})
                resp = urllib.request.urlopen(req, timeout=10)
                response_body = json.loads(resp.read().decode('utf-8'))
                if response_body.get('code') == 1000 and response_body.get('data'):
                    device_info = response_body['data'][0]
            except Exception as e:
                response_body = {'error': str(e)}
        state = device_info.get('state', '查询失败') if device_info else '查询失败'
        
        cleaned = False
        if _should_clean_device(device_info, region_key, region, device_code):
            # 清理：从所有模板 JSON 和 currentCount 中删除
            for t in region.get('templates', []):
                fpath = _get_template_file_path(region_key, t)
                tasks = _load_json(fpath)
                new_tasks = [task for task in tasks if not (task.get('deviceCode') == device_code and task.get('status') == 6)]
                if len(new_tasks) < len(tasks):
                    _save_json(fpath, new_tasks)
            now_file = _get_region_file(region_key, 'currentCount.json')
            now_devices = _load_json(now_file)
            now_devices = [d for d in now_devices if d.get('deviceCode') != device_code]
            _save_json(now_file, now_devices)
            cleaned = True
            write_global_log('device_check', region_key,
                f'设备检查清理: {device_num}({device_code}) 状态={state}')
        elif device_info and state == 'Idle':
            # 设备在线且空闲：更新 currentCount 中的 state 为 idle
            now_file = _get_region_file(region_key, 'currentCount.json')
            now_devices = _load_json(now_file)
            for d in now_devices:
                if d.get('deviceCode') == device_code:
                    d['state'] = 'idle'
                    break
            _save_json(now_file, now_devices)
        
        return jsonify({
            'success': True,
            'device_code': device_code,
            'device_num': device_num,
            'state': state,
            'cleaned': cleaned,
            'message': f'设备 {device_num} 状态: {state}' + ('，已自动清理' if cleaned else '，在线保留'),
            'request_url': request_url,
            'request_body': request_body,
            'response_body': response_body
        })
    except Exception as e:
        return jsonify({'error': f'检查失败: {str(e)}'}), 500


@dispatch_bp.route('/api/dispatch/template_detail')
@login_required
def api_template_detail():
    """获取模板详情（任务列表 + 最近日志）"""
    region_key = request.args.get('region_key', '')
    template_code = request.args.get('template_code', '')
    if not region_key or not template_code:
        return jsonify({'error': '缺少参数'}), 400
    
    index = _load_cache_index()
    region = index.get(region_key)
    if not region:
        return jsonify({'error': f'区域 {region_key} 不存在'}), 404
    
    template_config = None
    for t in region.get('templates', []):
        if (t.get('code') or t.get('name', '')) == template_code:
            template_config = t
            break
    if not template_config:
        return jsonify({'error': f'模板 {template_code} 不存在'}), 404
    
    fpath = _get_template_file_path(region_key, template_config)
    tasks = _load_json(fpath)
    task_type = _normalize_task_type(template_config)
    display_name = template_config.get('display_name') or template_config.get('name', '')
    
    # 当前执行中任务
    running_tasks = [task for task in tasks if task.get('status') == 6]
    
    # 最近日志（从全局日志筛选该模板相关）
    logs = _load_json(GLOBAL_LOG_PATH)
    template_logs = []
    for log in reversed(logs):
        detail = log.get('detail', '')
        if template_code in detail:
            template_logs.append({
                'time': log.get('time', ''),
                'action': log.get('action', ''),
                'detail': detail,
                'level': log.get('level', 'info')
            })
        if len(template_logs) >= 30:
            break
    
    return jsonify({
        'region_key': region_key,
        'template_code': template_code,
        'display_name': display_name,
        'task_type': task_type,
        'total_tasks': len(tasks),
        'running_count': len(running_tasks),
        'running_tasks': running_tasks,
        'logs': template_logs
    })


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
            # 将返回报文也写入 raw_data，供前端详情展示
            log_data = dict(data) if isinstance(data, dict) else {}
            log_data['response_body'] = {'code': 1000, 'desc': 'success'}
            write_global_log('report_status', rk, detail,
                           'info' if matched else 'warning', raw_data=log_data)
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
        
        # 始终返回 1000
        return jsonify({'code': 1000, 'desc': 'success'})
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
    """保存配置（自动创建备份）"""
    try:
        data = request.get_json()
        # 先创建备份
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"dispatch_config_{timestamp}.json"
            backup_path = os.path.join(BACKUP_DIR, backup_name)
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(f"// commit: auto-save\n")
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 备份失败不影响保存
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
    date_str = now_dt.strftime('%Y-%m-%d_%H:%M:%S')
    ms = now_dt.microsecond // 1000
    rand = _random.randint(0, 9999)
    order_id = f"CEM_auto_{date_str}.{ms:03d}__{rand:04d}"
    
    # 空车下发配置：优先使用 empty_dispatch，回退到旧 server 拼接
    empty_dispatch = region.get('empty_dispatch', {})
    template_code = target_template.get('code') or target_template.get('name', '')
    # 根据方向选择对应模板：template_in（空车来）或 template_out（空车回）
    if direction == 'in':
        dispatch_template = empty_dispatch.get('template_in', '') or template_code
    else:
        dispatch_template = empty_dispatch.get('template_out', '') or template_code
    dispatch_url = empty_dispatch.get('url', '')
    
    # 空车回（direction=out）：尝试指定区域内设备（优先低电量），避免跨区域调车
    # 空车来（direction=in）：不指定设备（从外部调车，不知道具体哪个设备会来）
    # 手动下发：不指定设备（异常恢复场景，让RCS自行分配更灵活）
    is_manual = balance.get('manual_dispatch', False)
    selected_device = None
    if direction == 'out' and not is_manual:
        selected_device = _select_device_for_empty_return(region_key, region)
        # 下发前检查设备状态：非空闲则跳过，避免 RCS 返回 status=7
        if selected_device:
            sh = region.get('self_heal', {})
            api_path = sh.get('device_query_api', SELF_HEAL_DEFAULTS['device_query_api'])
            area_id = region.get('areaId', '0')
            if api_path and 'XX' not in api_path:
                device_info = _query_device_status('', api_path, area_id, selected_device['deviceCode'])
                if device_info:
                    dev_state = device_info.get('state', '')
                    if dev_state != 'Idle':
                        print(f"[Dispatch] 设备非空闲跳过下发: {selected_device['deviceNum']}({selected_device['deviceCode'][-8:]}), state={dev_state}")
                        write_global_log('execute_skip', region_key,
                            f'设备非空闲跳过下发: {selected_device["deviceNum"]}({selected_device["deviceCode"][-8:]}), state={dev_state}',
                            raw_data={'deviceCode': selected_device['deviceCode'], 'deviceNum': selected_device['deviceNum'], 'state': dev_state})
                        selected_device = None  # 跳过，回退到不指定设备
    
    task_order_detail = {"taskPath": "", "shelfNumber": ""}
    if selected_device:
        task_order_detail["deviceCode"] = selected_device['deviceCode']
        task_order_detail["deviceNum"] = selected_device.get('deviceNum', '')
    
    request_body = [{
        "modelProcessCode": dispatch_template,
        "priority": 6,
        "orderId": order_id,
        "fromSystem": "CEM_auto",
        "taskOrderDetail": task_order_detail
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
    
    # 写入模板 JSON（空车回指定设备时记录设备信息，空车来留空等待 status=6 上报填充）
    template_file = _get_template_file_path(region_key, target_template)
    tasks = _load_json(template_file)
    now = datetime.now().isoformat()
    for i in range(dispatch_count):
        task_entry = {
            "deviceCode": selected_device['deviceCode'] if selected_device and i == 0 else "",
            "deviceNum": selected_device['deviceNum'] if selected_device and i == 0 else "",
            "status": 6, "_simulated": True if simulated else False,
            "order_id": order_id, "create_time": now, "update_time": now
        }
        if selected_device and i == 0:
            task_entry['_selected_battery'] = selected_device.get('battery', '')
        tasks.append(task_entry)
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
        # 更新每日统计（下发时）
        dispatch_field = 'dispatch_in' if direction == 'in' else 'dispatch_out'
        _update_daily_stats(region_key, dispatch_field)
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
            'can_dispatch': True,
            'manual_dispatch': True  # 手动下发不指定设备（异常恢复场景）
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
def _reset_region_data(region_key):
    """清空指定区域所有数据（内部函数，供测试线程使用）"""
    index = _load_cache_index()
    region = index.get(region_key)
    if not region:
        return
    for t in region.get('templates', []):
        fpath = _get_template_file_path(region_key, t)
        _save_json(fpath, [])
    now_file = _get_region_file(region_key, 'currentCount.json')
    _save_json(now_file, [])


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


# ========== 取消空车任务 ==========

def _cancel_empty_task(order_id, server_ip):
    """调用 ICS 取消任务接口"""
    import urllib.request as _urllib
    try:
        url = f"http://{server_ip}:7000/ics/out/task/cancelTask"
        body = json.dumps([{"orderId": order_id, "destPosition": ""}]).encode()
        req = _urllib.Request(url, data=body, method='POST')
        req.add_header('Content-Type', 'application/json')
        with _urllib.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode()), None
    except Exception as e:
        return None, str(e)


def _get_task_server_info(order_id):
    """通过跨环境任务查询获取子任务信息，检查子任务状态后决定是否允许取消
    
    流程：
    1. 用主订单号查跨环境任务（LIKE 模糊匹配子任务）
    2. 找到 _1 子任务（第一个子任务）
    3. 检查 task_status：执行中(status=6)则不允许取消
    4. 返回子任务 order_id 和服务器 IP
    """
    try:
        from modules.query.task_query_extended import get_cross_task_info
        result = get_cross_task_info(order_id)
        if 'error' in result:
            return None, result['error']
        details = result.get('cross_task_details', [])
        if not details:
            return None, '未找到任务详情'
        # 找到 _1 子任务（第一个子任务）
        detail = details[0]
        sub_order_id = detail.get('order_id', '')
        task_status = detail.get('task_status')
        # 检查子任务状态：执行中(status=6)不允许取消
        if task_status == 6:
            return None, f'子任务 {sub_order_id} 正在执行中(status=6)，无法取消'
        # 从 related_tasks 获取服务器地址
        related = result.get('related_tasks', [])
        server_ip = ''
        for rt in related:
            if rt.get('orderId') == order_id:
                server_ip = rt.get('service_url', '').replace('http://', '').split(':')[0]
                break
        if not server_ip:
            server_ip = '10.68.2.32'  # 默认
        return {'sub_order_id': sub_order_id, 'server_ip': server_ip}, None
    except Exception as e:
        return None, str(e)


@dispatch_bp.route('/api/dispatch/cancel_empty_tasks/<region_key>', methods=['POST'])
@login_required
@admin_required
def api_cancel_empty_tasks(region_key):
    """取消指定区域所有空车任务"""
    try:
        index = _load_cache_index()
        region = index.get(region_key)
        if not region:
            return jsonify({'error': f'区域 {region_key} 不存在'}), 404
        
        enabled = region.get('enabled', False)
        cancelled = 0
        errors = []
        details = []
        
        for t in region.get('templates', []):
            task_type = _normalize_task_type(t)
            if not _is_empty_task(task_type):
                continue
            fpath = _get_template_file_path(region_key, t)
            tasks = _load_json(fpath)
            template_code = t.get('code') or t.get('name', '')
            
            for task in tasks:
                if task.get('status') != 6:
                    continue
                order_id = task.get('order_id', '')
                if not order_id:
                    continue
                
                detail = {'template': template_code, 'order_id': order_id, 'success': False, 'message': ''}
                if enabled:
                    # 真实取消：查询子任务信息并调用 ICS 取消接口
                    info, err = _get_task_server_info(order_id)
                    if err:
                        detail['message'] = err
                        errors.append(f'{template_code} {order_id}: {err}')
                        details.append(detail)
                        continue
                    
                    sub_order_id = info['sub_order_id']
                    server_ip = info['server_ip']
                    detail['sub_order_id'] = sub_order_id
                    detail['server_ip'] = server_ip
                    
                    result, cancel_err = _cancel_empty_task(sub_order_id, server_ip)
                    if cancel_err:
                        detail['message'] = f'ICS取消失败: {cancel_err}'
                        errors.append(f'{template_code} {sub_order_id}: {cancel_err}')
                        details.append(detail)
                        continue
                    
                    cancelled += 1
                    detail['success'] = True
                    detail['message'] = f'已取消 (server={server_ip})'
                    details.append(detail)
                    write_global_log('cancel_empty', region_key,
                        f'取消空车任务: {template_code} order={order_id} sub={sub_order_id} server={server_ip}')
                else:
                    # 模拟取消：只清理本地数据
                    cancelled += 1
                    detail['success'] = True
                    detail['message'] = '模拟取消'
                    details.append(detail)
                    write_global_log('cancel_empty', region_key,
                        f'模拟取消空车任务: {template_code} order={order_id}')
            
            # 清理本地模板 JSON
            if cancelled > 0:
                tasks = [t for t in tasks if t.get('status') != 6]
                _save_json(fpath, tasks)
        
        return jsonify({
            'success': True,
            'cancelled': cancelled,
            'errors': errors,
            'details': details,
            'message': f'已取消 {cancelled} 个空车任务' + (f', {len(errors)} 个失败' if errors else '')
        })
    except Exception as e:
        return jsonify({'error': f'取消失败: {str(e)}'}), 500


# ========== 自恢复逻辑 ==========

# 自恢复状态记录
_self_heal_status = {}  # {region_key: {last_check, cleaned_count, errors}}
_self_heal_lock = threading.Lock()

SELF_HEAL_DEFAULTS = {
    'enabled': True,
    'check_interval': 300,       # 检查间隔（秒）
    'recover_timeout_minutes': 30,  # 异常超时恢复间隔（分钟）
    'device_query_api': '10.68.2.XX:7000/ics/out/device/list/deviceInfo',
    'low_battery_threshold': 30,  # 默认低电量阈值（百分比），区域可覆盖
}


def _query_device_status(server, api_path, area_id, device_code):
    """查询设备状态
    - device_code 非空：查询单个设备，返回 dict 或 None
    - device_code 为空：查询全量设备，返回 list 或 None
    api_path 支持两种格式：
    - 相对路径: /ics/out/device/list/deviceInfo → 拼接 http://{server}{api_path}
    - 完整 URL: http://192.168.1.100:8080/ics/... → 直接使用
    """
    import urllib.request as _urllib
    # 含 XX 占位符视为未配置
    if 'XX' in api_path or 'XX' in server:
        print(f"[Dispatch] _query_device_status 跳过(含XX占位符): api_path={api_path}, server={server}, device={device_code}")
        return None
    if api_path.startswith('http://') or api_path.startswith('https://'):
        url = api_path
    else:
        url = f"http://{server}{api_path}"
    body = {"areaId": str(area_id), "deviceType": "0", "deviceCode": device_code}
    try:
        req = _urllib.Request(url,
            data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'})
        resp = _urllib.urlopen(req, timeout=30)  # 全量查询可能较慢，超时30秒
        data = json.loads(resp.read().decode('utf-8'))
        if data.get('code') == 1000 and data.get('data'):
            # device_code 为空时返回全量列表，非空时返回单条
            if device_code:
                return data['data'][0] if data['data'] else None
            return data['data']
        print(f"[Dispatch] _query_device_status 响应异常: url={url}, code={data.get('code')}, device={device_code}")
        return None
    except Exception as e:
        print(f"[Dispatch] _query_device_status 请求失败: url={url}, error={e}, device={device_code}")
        return None


def _should_clean_device(device_info, region_key='', region=None, device_code=''):
    """判断设备是否应该被清理
    
    - 查询失败 → 保留
    - 在线 → 保留
    - Offline/Downlined → 检查是否有执行中任务：
      - 无执行中任务 → 清理
      - 有执行中任务但超过1小时 → 清理
      - 有执行中任务且未超过1小时 → 保留（可能在连廊环境中）
    """
    if not device_info:
        return False  # 查询失败（车可能还没到），保留不清理
    state = device_info.get('state', '')
    if state not in ('Offline', 'Downlined'):
        return False  # 在线 → 保留
    
    # 离线/下线：检查是否有执行中任务
    if region and device_code:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
        has_active_task = False
        task_start_time = ''
        matched_template = ''
        matched_status = ''
        all_task_info = []  # 调试：记录所有遍历到的任务信息
        for t in region.get('templates', []):
            fpath = _get_template_file_path(region_key, t)
            if not os.path.exists(fpath):
                continue
            tasks = _load_json(fpath)
            tcode = t.get('code', t.get('name', ''))
            for task in tasks:
                tdc = task.get('deviceCode', '')
                ts = task.get('status', '')
                all_task_info.append(f'{tcode}:{tdc[-8:] if tdc else "?"}={ts}')
                if tdc == device_code and ts in (6, 10):
                    has_active_task = True
                    task_start_time = task.get('create_time', '')
                    matched_template = tcode
                    matched_status = str(ts)
                    break
            if has_active_task:
                break
        
        if has_active_task:
            if task_start_time and task_start_time < cutoff:
                msg = f'[SelfHeal] 设备 {device_code[-8:]} 离线但有执行中任务(status in (6,10), 超过1小时)，清理 | 模板={matched_template} status={matched_status}'
                print(msg)
                try:
                    write_global_log('self_heal_detail', region_key, msg)
                except Exception:
                    pass
                return True  # 超过1小时，清理
            msg = f'[SelfHeal] 设备 {device_code[-8:]} 离线但有执行中任务(status in (6,10), 未超过1小时)，保留 | 模板={matched_template} status={matched_status}'
            print(msg)
            try:
                write_global_log('self_heal_detail', region_key, msg)
            except Exception:
                pass
            return False  # 未超过1小时，保留（可能在连廊中）
    
    # 无执行中任务：输出调试信息
    task_summary = ', '.join(all_task_info) if all_task_info else '(无任务)'
    msg = f'[SelfHeal] 设备 {device_code[-8:]} 离线且无执行中任务(status in (6,10))，清理 | region={region_key} has_region={bool(region)} has_code={bool(device_code)} | 模板任务: {task_summary}'
    print(msg)
    try:
        write_global_log('self_heal_detail', region_key, msg)
    except Exception:
        pass
    return True  # 无执行中任务，清理


# ========== 设备历史记录 ==========

def _get_device_history_path(region_key):
    """获取设备历史记录文件路径"""
    return _get_region_file(region_key, 'device_history.json')


def _load_device_history(region_key):
    """加载设备历史记录"""
    return _load_json(_get_device_history_path(region_key))


def _save_device_history(region_key, data):
    """保存设备历史记录"""
    _save_json(_get_device_history_path(region_key), data)


def _touch_device_history(region_key, device_code, device_num='', state=''):
    """状态上报时更新设备历史记录（轻量操作）
    
    - deviceCode 已存在：更新 update_time、deviceNum、state
    - deviceCode 不存在：新增记录（设备第一次来这个区域）
    
    这是 device_history.json 的主要写入入口，
    记录这个区域48小时内来过哪些设备。
    """
    if not device_code:
        return
    
    history = _load_device_history(region_key)
    now = datetime.now().isoformat()
    
    # 查找已有记录
    for d in history:
        if d.get('deviceCode') == device_code:
            d['deviceNum'] = device_num or d.get('deviceNum', '')
            if state:
                d['state'] = state
            d['update_time'] = now
            _save_device_history(region_key, history)
            return
    
    # 新设备：新增记录
    history.append({
        'deviceCode': device_code,
        'deviceNum': device_num,
        'deviceName': device_num,
        'state': state,
        'battery': '',
        'create_time': now,
        'update_time': now
    })
    _save_device_history(region_key, history)


def _clean_stale_device_history(region_key):
    """清理超过48小时未活动的设备记录
    
    Returns:
        {'cleaned': int, 'remaining': int}
    """
    history = _load_device_history(region_key)
    if not history:
        return {'cleaned': 0, 'remaining': 0}
    
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(hours=48)).isoformat()
    
    old_count = len(history)
    history = [d for d in history if d.get('update_time', '') >= cutoff]
    new_count = len(history)
    cleaned = old_count - new_count
    
    if cleaned > 0:
        _save_device_history(region_key, history)
    
    return {'cleaned': cleaned, 'remaining': new_count}


def _sync_device_history(region_key, api_devices):
    """将API返回的设备列表同步到 device_history.json（匹配模式）
    
    - 只更新 deviceCode 在 history 中已存在的设备（匹配模式）
    - API 返回但不在 history 中的设备：抛弃不记录
    - 不删除任何记录（删除由48h清理负责）
    
    Returns:
        {'total': int, 'updated': int, 'skipped': int}
    """
    history = _load_device_history(region_key)
    now = datetime.now().isoformat()
    
    # 建立 deviceCode 索引
    history_map = {d['deviceCode']: d for d in history}
    updated_count = 0
    skipped_count = 0
    
    for dev in api_devices:
        dc = dev.get('deviceCode', '')
        if not dc:
            continue
        if dc in history_map:
            # 更新已有记录
            existing = history_map[dc]
            dev_state = dev.get('state', '')
            existing['deviceNum'] = dev.get('deviceName', existing.get('deviceNum', ''))
            existing['deviceName'] = dev.get('deviceName', '')
            existing['state'] = dev_state
            existing['battery'] = dev.get('battery', '')
            # 离线设备不更新 update_time（保持上次在线时间，48h后自动清理）
            if dev_state not in ('Offline', 'Downlined'):
                existing['update_time'] = now
            updated_count += 1
        else:
            # 不在 history 中，抛弃
            skipped_count += 1
    
    _save_device_history(region_key, history)
    return {'total': len(history), 'updated': updated_count, 'skipped': skipped_count}


def _update_current_count_from_api(region_key, api_devices):
    """用全量API返回的设备状态同步 currentCount.json（仅匹配历史设备）
    
    只处理 deviceCode 在 device_history.json 中已存在的设备：
    - 非离线设备（Idle/InTask/Charging）不在 currentCount 中：自动添加
    - 离线设备（Offline/Downlined）在 currentCount 中：自动清理
    - 已存在的设备：更新 state 和 battery
    - 不在 history 中的设备：忽略
    """
    # 加载历史设备，建立 deviceCode 白名单
    history = _load_device_history(region_key)
    history_codes = {d.get('deviceCode', '') for d in history if d.get('deviceCode')}
    if not history_codes:
        return {'updated': 0, 'added': 0, 'cleaned': 0}
    
    now_file = _get_region_file(region_key, 'currentCount.json')
    now_devices = _load_json(now_file)
    now = datetime.now().isoformat()
    
    # 建立 API 设备索引（按 deviceCode），只保留在 history 中的设备
    api_map = {}
    for d in api_devices:
        dc = d.get('deviceCode', '')
        if dc and dc in history_codes:
            api_map[dc] = d
    
    state_map = {'Idle': 'idle', 'InTask': 'busy', 'Charging': 'charging'}
    updated = 0
    added = 0
    cleaned = 0
    
    # 建立 currentCount 设备索引
    cc_codes = {d.get('deviceCode', '') for d in now_devices}
    
    # 1. 更新已有设备 + 清理离线设备
    new_now_devices = []
    for d in now_devices:
        dc = d.get('deviceCode', '')
        if dc in api_map:
            api_dev = api_map[dc]
            new_state = api_dev.get('state', '')
            # 离线设备：清理
            if new_state in ('Offline', 'Downlined'):
                cleaned += 1
                continue
            d['state'] = state_map.get(new_state, 'pending')
            d['battery'] = api_dev.get('battery', '')
            updated += 1
        new_now_devices.append(d)
    
    # 2. 非离线设备不在 currentCount 中且在白名单中：自动添加
    for dc, api_dev in api_map.items():
        new_state = api_dev.get('state', '')
        if new_state in ('Offline', 'Downlined'):
            continue
        if dc not in cc_codes:
            new_now_devices.append({
                'deviceCode': dc,
                'deviceNum': api_dev.get('deviceName', ''),
                'order_id': '',
                'shelfNumber': '',
                'create_time': now,
                'state': state_map.get(new_state, 'pending'),
                'battery': api_dev.get('battery', '')
            })
            added += 1
    
    _save_json(now_file, new_now_devices)
    
    return {'updated': updated, 'added': added, 'cleaned': cleaned}


def _fetch_all_devices_and_sync(region_key, region):
    """全量获取设备状态并同步到 device_history 和 currentCount
    
    Returns:
        {'success': bool, 'device_count': int, 'history_total': int, 'error': str}
    """
    sh = region.get('self_heal', {})
    api_path = sh.get('device_query_api', SELF_HEAL_DEFAULTS['device_query_api'])
    area_id = region.get('areaId', '0')
    
    if not api_path or 'XX' in api_path:
        return {'success': False, 'device_count': 0, 'history_total': 0, 'error': 'API未配置'}
    
    # 全量获取（deviceCode 为空）
    api_devices = _query_device_status('', api_path, area_id, '')
    
    if api_devices is None:
        return {'success': False, 'device_count': 0, 'history_total': 0, 'error': 'API请求失败'}
    
    if not isinstance(api_devices, list):
        return {'success': False, 'device_count': 0, 'history_total': 0, 'error': 'API返回格式异常'}
    
    # 同步到 device_history.json
    sync_result = _sync_device_history(region_key, api_devices)
    
    # 更新 currentCount.json 中已有设备的状态
    cc_result = _update_current_count_from_api(region_key, api_devices)
    
    return {
        'success': True,
        'device_count': len(api_devices),
        'history_total': sync_result['total'],
        'history_updated': sync_result['updated'],
        'history_skipped': sync_result['skipped'],
        'cc_updated': cc_result['updated'],
        'cc_added': cc_result['added'],
        'cc_cleaned': cc_result['cleaned']
    }


# 分时段切换全量检查防抖
_time_slot_check_last = {}  # {region_key: timestamp}
_TIME_SLOT_CHECK_DEBOUNCE = 300  # 同一区域5分钟内最多触发一次分时段切换检查


def _on_time_slot_change(region_key, region):
    """分时段切换处理：清理48h旧记录 → 全量获取设备状态 → 同步"""
    # 防抖检查
    now_ts = time.time()
    last_ts = _time_slot_check_last.get(region_key, 0)
    if now_ts - last_ts < _TIME_SLOT_CHECK_DEBOUNCE:
        return
    
    _time_slot_check_last[region_key] = now_ts
    
    try:
        # 1. 清理48h旧记录
        clean_result = _clean_stale_device_history(region_key)
        
        # 2. 全量获取并同步
        fetch_result = _fetch_all_devices_and_sync(region_key, region)
        
        if fetch_result['success']:
            write_global_log('time_slot_change', region_key,
                f'分时段切换全量检查完成: 清理{clean_result["cleaned"]}条旧记录, '
                f'获取{fetch_result["device_count"]}台设备, '
                f'历史共{fetch_result["history_total"]}条(更新{fetch_result["history_updated"]},跳过{fetch_result["history_skipped"]}), '
                f'currentCount更新{fetch_result["cc_updated"]}台,新增{fetch_result["cc_added"]}台,清理{fetch_result["cc_cleaned"]}台')
        else:
            write_global_log('time_slot_change', region_key,
                f'分时段切换全量检查失败: {fetch_result.get("error", "未知错误")}', 'warning')
    except Exception as e:
        print(f"[TimeSlotCheck] 分时段切换检查异常 {region_key}: {e}")
        try:
            write_global_log('time_slot_change', region_key,
                f'分时段切换检查异常: {str(e)}', 'error')
        except:
            pass


def _get_low_battery_threshold(sh):
    """获取低电量阈值：区域配置优先，-1 则使用全局默认"""
    t = sh.get('low_battery_threshold', -1)
    if t == -1 or t is None:
        t = SELF_HEAL_DEFAULTS['low_battery_threshold']
    return int(t)


def _check_low_battery_return(region_key, region, sh):
    """检查低电量设备并下发回空车（仅自动轮询调用）
    
    Returns:
        {'dispatched': bool, 'device_code': '', 'device_num': '', 'battery': '', 'threshold': 0}
    """
    result = {'dispatched': False, 'device_code': '', 'device_num': '', 'battery': '', 'threshold': 0}
    
    # 检查开关
    if not sh.get('low_battery_enabled', False):
        return result
    
    threshold = _get_low_battery_threshold(sh)
    result['threshold'] = threshold
    
    # 读取 currentCount.json
    now_file = _get_region_file(region_key, 'currentCount.json')
    now_devices = _load_json(now_file)
    
    # 收集当前区域设备的 deviceCode 集合（用于过滤共享模板中的其他区域设备）
    now_device_codes = {d.get('deviceCode', '') for d in now_devices if d.get('deviceCode')}
    
    # 收集 pending 中的 deviceCode（只关注当前区域设备，避免共享模板误判）
    pending_codes = set()
    for t in region.get('templates', []):
        fpath = _get_template_file_path(region_key, t)
        tasks = _load_json(fpath)
        for task in tasks:
            dc = task.get('deviceCode', '')
            if task.get('status') == 6 and dc:
                # 共享模板：只关注当前区域设备的 pending 状态
                if t.get('shared') and dc not in now_device_codes:
                    continue
                pending_codes.add(dc)
    
    # 遍历在线设备，找低电量且不在 pending 中的
    for d in now_devices:
        device_code = d.get('deviceCode', '')
        device_num = d.get('deviceNum', '')
        battery_str = d.get('battery', '')
        if not device_code or not battery_str:
            continue
        try:
            battery = int(battery_str)
        except (ValueError, TypeError):
            continue
        
        if battery >= threshold:
            continue  # 电量足够
        
        if device_code in pending_codes:
            continue  # 已在执行任务
        
        # 找到低电量空闲设备，下发回空车
        dispatch_result = _execute_low_battery_return(region_key, region, device_code, device_num, battery)
        result['dispatched'] = True
        result['device_code'] = device_code
        result['device_num'] = device_num
        result['battery'] = battery_str
        return result  # 每次只处理一台
    
    return result


def _select_device_for_empty_return(region_key, region):
    """从当前区域设备中选择最适合回空车的设备
    
    选择策略：
    1. 排除已在 pending 中的设备（任何模板 status=6 且有 deviceCode）
    2. 优先选低电量设备（电量最低的）
    3. 电量相同时选 state=idle 的
    4. 都没有则返回 None（回退到不指定设备）
    
    Returns:
        {'deviceCode': '...', 'deviceNum': '...', 'battery': 80} or None
    """
    now_file = _get_region_file(region_key, 'currentCount.json')
    now_devices = _load_json(now_file)
    
    # 收集当前区域设备的 deviceCode 集合（用于过滤共享模板中的其他区域设备）
    now_device_codes = {d.get('deviceCode', '') for d in now_devices if d.get('deviceCode')}
    
    # 收集 pending 中的 deviceCode（只关注当前区域设备）
    pending_codes = set()
    for t in region.get('templates', []):
        fpath = _get_template_file_path(region_key, t)
        tasks = _load_json(fpath)
        for task in tasks:
            dc = task.get('deviceCode', '')
            if task.get('status') == 6 and dc:
                # 共享模板：只关注当前区域设备的 pending 状态
                if t.get('shared') and dc not in now_device_codes:
                    continue
                pending_codes.add(dc)
    
    # 收集每台设备最近一次被下发的时间（从所有模板JSON中查找）
    last_dispatch_time = {}
    for t in region.get('templates', []):
        fpath = _get_template_file_path(region_key, t)
        tasks = _load_json(fpath)
        for task in tasks:
            dc = task.get('deviceCode', '')
            ct = task.get('create_time', '')
            if dc and ct:
                if dc not in last_dispatch_time or ct > last_dispatch_time[dc]:
                    last_dispatch_time[dc] = ct
    
    # 筛选可用设备：有 deviceCode、不在 pending 中
    available = []
    for d in now_devices:
        dc = d.get('deviceCode', '')
        if not dc or dc in pending_codes:
            continue
        battery_str = d.get('battery', '')
        try:
            battery = int(battery_str)
        except (ValueError, TypeError):
            battery = 999  # 无电量信息排最后
        state = d.get('state', 'pending')
        # 最近下发时间（越早越好，没被下发过的最优先）
        last_dt = last_dispatch_time.get(dc, '')
        available.append({
            'deviceCode': dc,
            'deviceNum': d.get('deviceNum', ''),
            'battery': battery,
            'state': state,
            'last_dispatch': last_dt
        })
    
    if not available:
        return None
    
    # 排序：最近未被下发过的优先 → 电量低优先 → state=idle 优先
    # 最近下发时间越早（或从未下发），排在越前面
    def _sort_key(item):
        # 最近下发过（1小时内）的排后面，没下发过的排前面
        recently_dispatched = 1 if item['last_dispatch'] else 0
        battery_score = item['battery']
        state_score = 0 if item['state'] == 'idle' else 1
        return (recently_dispatched, battery_score, state_score)
    
    available.sort(key=_sort_key)
    return available[0]


def _execute_low_battery_return(region_key, region, device_code, device_num, battery):
    """执行低电量回空车下发（指定设备，使用 template_out，不检查互斥）"""
    import random as _random
    
    # 找到空车回模板
    target_template = None
    for t in region.get('templates', []):
        task_type = _normalize_task_type(t)
        if _is_empty_task(task_type) and not _is_in_direction(task_type):
            target_template = t
            break
    if not target_template:
        print(f"[LowBattery] 区域 {region_key} 没有空车回模板")
        return {'success': False, 'error': '没有空车回模板'}
    
    empty_dispatch = region.get('empty_dispatch', {})
    dispatch_template = empty_dispatch.get('template_out', '') or target_template.get('code') or target_template.get('name', '')
    dispatch_url = empty_dispatch.get('url', '')
    
    now_dt = datetime.now()
    date_str = now_dt.strftime('%Y-%m-%d_%H:%M:%S')
    ms = now_dt.microsecond // 1000
    rand = _random.randint(0, 9999)
    order_id = f"CEM_low_battery_{date_str}.{ms:03d}__{rand:04d}"
    
    request_body = [{
        "modelProcessCode": dispatch_template,
        "priority": 6,
        "orderId": order_id,
        "fromSystem": "CEM_low_battery",
        "taskOrderDetail": {
            "taskPath": "",
            "deviceCode": device_code,
            "deviceNum": "",
            "shelfNumber": ""
        }
    }]
    
    simulated = not region.get('enabled', False)
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
    
    # 写入模板 JSON（标记 _low_battery: true）
    template_file = _get_template_file_path(region_key, target_template)
    tasks = _load_json(template_file)
    now = datetime.now().isoformat()
    tasks.append({
        "deviceCode": device_code, "deviceNum": device_num,
        "status": 6, "_simulated": True if simulated else False,
        "_low_battery": True,
        "order_id": order_id, "create_time": now, "update_time": now
    })
    _save_json(template_file, tasks)
    
    # 记录日志
    template_code = target_template.get('code') or target_template.get('name', '')
    log_url = dispatch_url if not simulated else f'(模拟-未实际请求)\n真实地址: {dispatch_url}'
    try:
        write_dispatch_log(
            region_key=region_key, template_name=template_code,
            direction='out', dispatch_url=log_url, request_body=request_body,
            simulated=simulated, device_code=device_code,
            device_num=device_num, result=result, response_body=response_body,
            reason='low_battery'
        )
    except Exception as e:
        print(f"[LowBattery] 写入下发记录失败: {e}")
    
    try:
        dispatch_raw = {
            'dispatch_url': dispatch_url,
            'request_body': request_body,
            'response_body': response_body,
            'simulated': simulated,
            'result': result,
            'dispatch_count': 1,
            'template_code': template_code,
            'direction': 'out',
            'reason': 'low_battery',
            'battery': battery
        }
        write_global_log('low_battery_return', region_key,
            f'低电量回空车: {device_num}({device_code[-8:]}), 电量{battery}% < 阈值{_get_low_battery_threshold(region.get("self_heal", {}))}%, '
            f'{"模拟" if simulated else "真实"}下发',
            raw_data=dispatch_raw)
    except Exception as e:
        print(f"[LowBattery] 写入操作日志失败: {e}")
    
    print(f"[LowBattery] 下发完成: region={region_key}, device={device_num}({device_code[-8:]}), battery={battery}%, simulated={simulated}, result={result}")
    return {'success': True, 'simulated': simulated, 'result': result}


def _self_heal_check_region(region_key, region, force=False, template_code=None):
    """检查单个区域的异常任务并清理
    
    Args:
        force: 强制模式，忽略超时判断，检查所有 status=6 任务
        template_code: 指定模板 code，为空则检查所有模板；
                      特殊值 '__current_devices__' 表示检查 currentCount.json 中的空闲设备
    Returns:
        {'cleaned': int, 'errors': list, 'steps': list}
        steps: [{device_code, device_num, state, action, reason}]
    """
    sh = region.get('self_heal', {})
    if not sh.get('enabled', SELF_HEAL_DEFAULTS['enabled']) and not force:
        return {'cleaned': 0, 'errors': [], 'steps': []}
    
    timeout_minutes = sh.get('recover_timeout_minutes', SELF_HEAL_DEFAULTS['recover_timeout_minutes'])
    area_id = region.get('areaId', '0')
    api_path = sh.get('device_query_api', SELF_HEAL_DEFAULTS['device_query_api'])
    
    # 未配置查询API或含 XX 占位符则跳过
    if not api_path or 'XX' in api_path:
        return {'cleaned': 0, 'errors': [], 'steps': []}
    
    from datetime import timedelta
    threshold = (datetime.now() - timedelta(minutes=timeout_minutes)).isoformat()
    cleaned = 0
    errors = []
    steps = []
    
    check_current_devices = (template_code == '__current_devices__')
    
    # 自动定时检查（template_code=None, force=False）：只检查 currentCount.json 中的空闲设备
    # 强制检查"当前设备"（template_code='__current_devices__'）：只检查 currentCount.json
    # 强制检查模板（template_code=具体模板, force=True）：只检查模板任务
    if template_code is None or check_current_devices:
        now_file = _get_region_file(region_key, 'currentCount.json')
        now_devices = _load_json(now_file)
        # 过滤掉 deviceCode 为空的无效记录
        valid_devices = [d for d in now_devices if d.get('deviceCode')]
        for d in valid_devices:
            device_code = d.get('deviceCode', '')
            device_num = d.get('deviceNum', '')
            if not device_code:
                continue
            device_info = _query_device_status('', api_path, area_id, device_code)
            state = device_info.get('state', '查询失败') if device_info else '查询失败'
            battery = device_info.get('battery', '') if device_info else ''
            # 更新 currentCount.json 中的 battery 和 state
            # 映射 API state 到前端状态：Idle→idle, InTask→busy, Charging→charging, 其他→pending
            state_map = {'Idle': 'idle', 'InTask': 'busy', 'Charging': 'charging'}
            d['state'] = state_map.get(state, 'pending') if state not in ('查询失败', 'Offline', 'Downlined') else state
            d['battery'] = battery
            if _should_clean_device(device_info, region_key, region, device_code):
                now_devices = [nd for nd in now_devices if nd.get('deviceCode') != device_code]
                cleaned += 1
                steps.append({
                    'device_code': device_code, 'device_num': device_num,
                    'state': state, 'action': '清理',
                    'reason': f'当前设备离线: {state}'
                })
                # 记录设备离开网格事件
                try:
                    write_global_log('device_leave', region_key,
                        f'设备离开网格(自恢复清理): {device_num}({device_code[-8:] if device_code else "?"}), '
                        f'状态:{state}',
                        raw_data={'deviceCode': device_code, 'deviceNum': device_num,
                                  'state': state, 'region_key': region_key, 'reason': 'self_heal'})
                except: pass
            else:
                steps.append({
                    'device_code': device_code, 'device_num': device_num,
                    'state': state, 'action': '保留',
                    'reason': f'当前设备在线: {state}'
                })
        _save_json(now_file, now_devices)
    
    # 自动定时检查只检查当前设备，不检查模板任务（避免查询执行中的负载设备）
    if template_code is None and not force:
        # [低电量检查] 仅自动轮询时触发
        low_battery_result = _check_low_battery_return(region_key, region, sh)
        if low_battery_result.get('dispatched'):
            steps.append({
                'device_code': low_battery_result.get('device_code', ''),
                'device_num': low_battery_result.get('device_num', ''),
                'state': f'电量{low_battery_result.get("battery", "?")}%',
                'action': '低电量回空车',
                'reason': f'电量{low_battery_result.get("battery", "?")}% < 阈值{low_battery_result.get("threshold", "?")}%'
            })
        return {'cleaned': cleaned, 'errors': errors, 'steps': steps,
                'low_battery': low_battery_result}
    
    # 如果只检查当前设备，跳过模板检查
    if check_current_devices:
        return {'cleaned': cleaned, 'errors': errors, 'steps': steps}
    
    # 强制检查模板 JSON 中的 status=6 任务（仅手动触发）
    for t in region.get('templates', []):
        tpl_code = t.get('code') or t.get('name', '')
        # 如果指定了模板，只检查该模板
        if template_code and tpl_code != template_code:
            continue
        
        fpath = _get_template_file_path(region_key, t)
        tasks = _load_json(fpath)
        
        if force:
            # 强制模式：检查所有 status=6 的非模拟任务
            check_tasks = [task for task in tasks
                          if task.get('status') == 6
                          and not task.get('_simulated')]
        else:
            # 正常模式：只检查超时任务
            check_tasks = [task for task in tasks
                          if task.get('status') == 6
                          and not task.get('_simulated')
                          and task.get('create_time', '') < threshold]
        
        if not check_tasks:
            continue
        
        # 最多检查20个任务（强制模式放宽上限）
        max_check = 20 if force else 10
        for task in check_tasks[:max_check]:
            device_code = task.get('deviceCode', '')
            device_num = task.get('deviceNum', '')
            if not device_code:
                continue
            
            device_info = _query_device_status('', api_path, area_id, device_code)
            state = device_info.get('state', '查询失败') if device_info else '查询失败'
            
            if _should_clean_device(device_info, region_key, region, device_code):
                # 从模板 JSON 删除
                tasks = [t for t in tasks if t.get('deviceCode') != device_code or t.get('status') != 6]
                # 从 currentCount 删除
                now_file = _get_region_file(region_key, 'currentCount.json')
                now_devices = _load_json(now_file)
                now_devices = [d for d in now_devices if d.get('deviceCode') != device_code]
                _save_json(now_file, now_devices)
                cleaned += 1
                steps.append({
                    'device_code': device_code, 'device_num': device_num,
                    'state': state, 'action': '清理',
                    'reason': f'设备状态: {state}'
                })
            else:
                steps.append({
                    'device_code': device_code, 'device_num': device_num,
                    'state': state, 'action': '保留',
                    'reason': f'设备状态: {state}（任务中/故障）'
                })
        
        # 保存模板 JSON（在循环外统一保存，避免多次 I/O）
        _save_json(fpath, tasks)
    
    return {'cleaned': cleaned, 'errors': errors, 'steps': steps}


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
        # 启动后等待15秒，让积压的状态上报先处理，避免误判设备离线
        time.sleep(15)
        # 清理2天前的大日志文件
        try:
            _clean_old_archive_logs()
        except: pass
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


# ========== 定时轮询调度 ==========

_POLL_DISPATCH_DEFAULT_INTERVAL = 60  # 默认轮询间隔（秒）
_poll_dispatch_last = {}  # 记录每个区域上次轮询调度时间

def _start_poll_dispatch_thread():
    """启动定时轮询调度后台线程（兜底机制）"""
    # 记录每个区域上次生效的分时配置标识，用于检测切换
    _time_slot_identity = {}
    
    def _loop():
        # 启动后等待30秒，让自恢复先清理幽灵任务，避免防抖丢失导致重复下发
        time.sleep(30)
        while True:
            try:
                index = _load_cache_index()
                interval = index.get('poll_dispatch_interval', _POLL_DISPATCH_DEFAULT_INTERVAL)
                if interval < 10:
                    interval = _POLL_DISPATCH_DEFAULT_INTERVAL
                
                for rk, region in index.items():
                    if not isinstance(region, dict) or 'templates' not in region:
                        continue
                    
                    # 计算平衡
                    balance = calculate_area_balance(rk, region)
                    
                    # [分时段切换检测] 比较当前生效的 slot 是否与上次不同
                    if balance.get('time_slot_active') and balance.get('time_slot_matched'):
                        slot = balance['time_slot_matched']
                        slot_id = f"{slot.get('name','')}_{slot.get('priority','')}_{slot.get('start','')}_{slot.get('end','')}"
                        last_slot_id = _time_slot_identity.get(rk, '')
                        if slot_id != last_slot_id:
                            _time_slot_identity[rk] = slot_id
                            # 异步执行分时段切换检查
                            def _do_slot_check(rk=rk, region=region):
                                try:
                                    _on_time_slot_change(rk, region)
                                except Exception as e:
                                    print(f"[TimeSlotCheck] 分时段切换检查失败 {rk}: {e}")
                            threading.Thread(target=_do_slot_check, daemon=True).start()
                    
                    if balance['direction'] == 'none':
                        continue
                    if not balance['can_dispatch']:
                        continue
                    
                    # 防抖检查（与状态上报触发共用）
                    now = time.time()
                    last = _auto_dispatch_last.get(rk, 0)
                    if now - last < _AUTO_DISPATCH_DEBOUNCE:
                        continue
                    
                    _auto_dispatch_last[rk] = now
                    _poll_dispatch_last[rk] = now
                    
                    # 异步执行调度
                    def _do_dispatch(rk=rk, region=region, balance=balance):
                        try:
                            _execute_dispatch(rk, region, balance)
                        except Exception as e:
                            print(f"[PollDispatch] 调度失败 {rk}: {e}")
                    threading.Thread(target=_do_dispatch, daemon=True).start()
                
                time.sleep(interval)
            except Exception as e:
                print(f"[PollDispatch] 后台线程异常: {e}")
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


@dispatch_bp.route('/api/dispatch/self_heal/force_check/<region_key>', methods=['POST'])
@login_required
@admin_required
def api_self_heal_force_check(region_key):
    """强制检查指定模板的所有设备（忽略超时，逐个查询服务器）"""
    try:
        template_code = request.args.get('template_code', '')
        index = _load_cache_index()
        region = index.get(region_key)
        if not region:
            return jsonify({'error': f'区域 {region_key} 不存在'}), 404
        
        if not template_code:
            return jsonify({'error': '缺少 template_code 参数'}), 400
        
        # 验证模板存在（__current_devices__ 是特殊值，跳过验证）
        if template_code != '__current_devices__':
            tpl_found = False
            for t in region.get('templates', []):
                if (t.get('code') or t.get('name', '')) == template_code:
                    tpl_found = True
                    break
            if not tpl_found:
                return jsonify({'error': f'模板 {template_code} 不存在于区域 {region_key}'}), 404
        
        start_time = time.time()
        result = _self_heal_check_region(region_key, region, force=True, template_code=template_code)
        elapsed = round(time.time() - start_time, 1)
        
        # 更新自恢复状态
        with _self_heal_lock:
            _self_heal_status[region_key] = {
                'last_check': datetime.now().isoformat(),
                'cleaned_count': result['cleaned'],
                'errors': result['errors']
            }
        
        # 记录详细日志
        steps_detail = '; '.join([f"{s['device_num']}({s['device_code'][-8:]}) {s['state']}→{s['action']}" for s in result['steps']])
        write_global_log('self_heal', region_key,
            f'强制检查 {template_code}: 清理 {result["cleaned"]} 个, 保留 {len(result["steps"]) - result["cleaned"]} 个, 耗时 {elapsed}s | {steps_detail}')
        
        return jsonify({
            'success': True,
            'region_key': region_key,
            'template_code': template_code,
            'cleaned': result['cleaned'],
            'total_checked': len(result['steps']),
            'elapsed': elapsed,
            'steps': result['steps'],
            'errors': result['errors']
        })
    except Exception as e:
        return jsonify({'error': f'强制检查失败: {str(e)}'}), 500


# ========== 设备历史记录 API ==========

@dispatch_bp.route('/api/dispatch/device_history/<region_key>')
@login_required
def api_device_history(region_key):
    """获取设备历史记录"""
    index = _load_cache_index()
    if region_key not in index:
        return jsonify({'error': f'区域 {region_key} 不存在'}), 404
    
    history = _load_device_history(region_key)
    return jsonify({'region_key': region_key, 'devices': history, 'total': len(history)})


@dispatch_bp.route('/api/dispatch/device_history/<region_key>/clean', methods=['POST'])
@login_required
@admin_required
def api_device_history_clean(region_key):
    """手动触发48h清理"""
    index = _load_cache_index()
    if region_key not in index:
        return jsonify({'error': f'区域 {region_key} 不存在'}), 404
    
    result = _clean_stale_device_history(region_key)
    write_global_log('device_history', region_key,
        f'手动48h清理: 清理{result["cleaned"]}条, 剩余{result["remaining"]}条')
    return jsonify({'success': True, 'region_key': region_key, **result})


@dispatch_bp.route('/api/dispatch/device_history/<region_key>/check', methods=['POST'])
@login_required
def api_device_history_check(region_key):
    """检查48h内活动（不清理，仅返回检查结果）"""
    index = _load_cache_index()
    if region_key not in index:
        return jsonify({'error': f'区域 {region_key} 不存在'}), 404
    
    history = _load_device_history(region_key)
    if not history:
        return jsonify({'region_key': region_key, 'total': 0, 'stale': 0, 'active': 0})
    
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(hours=48)).isoformat()
    
    stale = [d for d in history if d.get('update_time', '') < cutoff]
    active = [d for d in history if d.get('update_time', '') >= cutoff]
    
    return jsonify({
        'region_key': region_key,
        'total': len(history),
        'stale': len(stale),
        'active': len(active),
        'stale_devices': [{'deviceCode': d['deviceCode'], 'deviceNum': d.get('deviceNum', ''), 'update_time': d.get('update_time', '')} for d in stale]
    })


# 全量获取防抖
_fetch_all_last = {}  # {region_key: timestamp}
_FETCH_ALL_DEBOUNCE = 5  # 5秒防抖


@dispatch_bp.route('/api/dispatch/device_history/<region_key>/fetch_all', methods=['POST'])
@login_required
@admin_required
def api_device_history_fetch_all(region_key):
    """手动触发全量获取设备状态（5s防抖）"""
    # 防抖检查
    now_ts = time.time()
    last_ts = _fetch_all_last.get(region_key, 0)
    if now_ts - last_ts < _FETCH_ALL_DEBOUNCE:
        remaining = round(_FETCH_ALL_DEBOUNCE - (now_ts - last_ts), 1)
        return jsonify({'success': False, 'error': f'请等待 {remaining} 秒后再试', 'debounce': True}), 429
    
    _fetch_all_last[region_key] = now_ts
    
    index = _load_cache_index()
    region = index.get(region_key)
    if not region:
        return jsonify({'error': f'区域 {region_key} 不存在'}), 404
    
    # 先清理48h旧记录
    clean_result = _clean_stale_device_history(region_key)
    
    # 全量获取并同步
    fetch_result = _fetch_all_devices_and_sync(region_key, region)
    
    if fetch_result['success']:
        write_global_log('device_history', region_key,
            f'手动全量获取: 清理{clean_result["cleaned"]}条, '
            f'获取{fetch_result["device_count"]}台设备, '
            f'历史共{fetch_result["history_total"]}条(更新{fetch_result["history_updated"]},跳过{fetch_result["history_skipped"]}), '
            f'currentCount更新{fetch_result["cc_updated"]}台,新增{fetch_result["cc_added"]}台,清理{fetch_result["cc_cleaned"]}台')
    
    return jsonify({
        'success': fetch_result['success'],
        'region_key': region_key,
        'clean_result': clean_result,
        **fetch_result
    })


# ========== Supervisor 日志查看 API ==========

import glob as _glob_module

@dispatch_bp.route('/api/dispatch/logs')
@login_required
@admin_required
def api_supervisor_logs():
    """查看 supervisor 控制台日志（print 输出）
    
    Query params:
        lines: 返回最后 N 行，默认 200
        filter: 过滤关键词（如 SelfHeal）
    """
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    log_file = os.path.join(log_dir, 'cross_env_manager.log')
    
    if not os.path.exists(log_file):
        return jsonify({'error': f'日志文件不存在: {log_file}', 'logs': []}), 404
    
    max_lines = request.args.get('lines', 200, type=int)
    keyword = request.args.get('filter', '', type=str)
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
        
        # 取最后 N 行
        recent = all_lines[-max_lines:] if len(all_lines) > max_lines else all_lines
        
        # 过滤
        if keyword:
            recent = [l for l in recent if keyword in l]
        
        return jsonify({
            'success': True,
            'log_file': log_file,
            'total_lines': len(all_lines),
            'returned_lines': len(recent),
            'filter': keyword or None,
            'logs': [l.rstrip('\n\r') for l in recent]
        })
    except Exception as e:
        return jsonify({'error': f'读取日志失败: {str(e)}', 'logs': []}), 500


# ========== 自动驾驶测试 API ==========

_test_thread = None
_test_stop_flag = threading.Event()
_test_state = {
    'running': False,
    'start_time': None,
    'total_ops': {'load_in': 0, 'load_out': 0, 'done_load': 0, 'done_empty': 0, 'exec': 0},
    'pool_stats': '',
    'region_devices_count': 0,
    'pending_count': 0,
    'logs': [],  # 最近50条日志
    'round_num': 0,
    'elapsed': 0
}
_test_state_lock = threading.Lock()


def _test_log(msg):
    """记录测试日志（最多保留50条）"""
    with _test_state_lock:
        _test_state['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        if len(_test_state['logs']) > 50:
            _test_state['logs'] = _test_state['logs'][-50:]


def _update_test_stats(line):
    """从子进程日志行解析并更新测试统计数据"""
    import re
    with _test_state_lock:
        ops = _test_state['total_ops']
        # 来负载
        if '来负载' in line and '池→任务' in line:
            ops['load_in'] = ops.get('load_in', 0) + 1
        # 回负载
        elif '回负载' in line and '池→任务' in line:
            ops['load_out'] = ops.get('load_out', 0) + 1
        # 完成来负载/回负载
        elif '完成来负载' in line:
            ops['done_load'] = ops.get('done_load', 0) + 1
        elif '完成回负载' in line:
            ops['done_load'] = ops.get('done_load', 0) + 1
        # 完成来空车/回空车
        elif '完成来空车' in line or '完成回空车' in line:
            ops['done_empty'] = ops.get('done_empty', 0) + 1
        # 执行下发
        elif '执行' in line and ('下发' in line or '模拟' in line):
            ops['exec'] = ops.get('exec', 0) + 1
        # 设备池（取已创建数）
        m = re.search(r'已创建[：:]\s*(\d+)', line)
        if m:
            _test_state['pool_stats'] = m.group(1)
        # 进行中
        m = re.search(r'进行中[：:]\s*(\d+)', line)
        if m:
            _test_state['pending_count'] = int(m.group(1))


def _run_test_thread(params):
    """启动独立子进程运行 dispatch_auto_pilot.py，走真实 HTTP 请求"""
    import sys, subprocess, traceback
    
    global _test_state
    
    try:
        _test_log("正在启动测试子进程...")
        
        # 构建命令行参数
        script = os.path.join(BASE_DIR, 'test', '调车模块压力测试', 'dispatch_auto_pilot.py')
        cmd = [sys.executable, script]
        
        pool_size = params.get('pool_size', 20)
        load_interval_min = params.get('load_interval_min', 1.0)
        load_interval_max = params.get('load_interval_max', 20.0)
        load_dur_min = params.get('load_dur_min', 30.0)
        load_dur_max = params.get('load_dur_max', 120.0)
        empty_dur_min = params.get('empty_dur_min', 30.0)
        empty_dur_max = params.get('empty_dur_max', 120.0)
        duration = params.get('duration', 0)
        
        cmd.extend(['--pool-size', str(pool_size)])
        cmd.extend(['--load-interval-min', str(load_interval_min)])
        cmd.extend(['--load-interval-max', str(load_interval_max)])
        cmd.extend(['--task-duration', f'{load_dur_min}-{load_dur_max}'])
        cmd.extend(['--empty-duration', f'{empty_dur_min}-{empty_dur_max}'])
        if duration > 0:
            cmd.extend(['--duration', str(duration)])
        
        _test_log(f"启动: {' '.join(cmd)}")
        
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=BASE_DIR,
            env={**os.environ, 'PYTHONUNBUFFERED': '1'}
        )
        
        with _test_state_lock:
            _test_state['_proc'] = proc
        
        _test_log("子进程已启动")
        
        for line in iter(proc.stdout.readline, ''):
            if _test_stop_flag.is_set():
                proc.terminate()
                _test_log("已停止")
                break
            line = line.strip()
            if line:
                _test_log(line)
                # 解析日志更新统计数据
                _update_test_stats(line)
        
        proc.wait()
        _test_log(f"子进程退出 (code={proc.returncode})")
    
    except Exception as e:
        _test_log(f"错误: {str(e)}")
        traceback.print_exc()
    
    with _test_state_lock:
        _test_state['running'] = False


@dispatch_bp.route('/dispatch/test')
@login_required
def test_page():
    """自动驾驶测试页面"""
    return render_template('dispatch/test.html')


@dispatch_bp.route('/api/dispatch/test/start', methods=['POST'])
@login_required
def api_test_start():
    """启动自动驾驶测试"""
    global _test_thread, _test_stop_flag, _test_state
    
    with _test_state_lock:
        if _test_state['running']:
            # 检查线程是否还活着，如果已死则允许重新启动
            if _test_thread and _test_thread.is_alive():
                return jsonify({'error': '测试已在运行中'}), 409
            # 线程已死，重置状态
            _test_state['running'] = False
        
        # 重置状态
        _test_state = {
            'running': True,
            'start_time': datetime.now().isoformat(),
            'total_ops': {'load_in': 0, 'load_out': 0, 'done_load': 0, 'done_empty': 0, 'exec': 0},
            'pool_stats': '',
            'region_devices_count': 0,
            'pending_count': 0,
            'logs': [],
            'round_num': 0,
            'elapsed': 0
        }
    
    _test_stop_flag.clear()
    
    params = request.get_json() or {}
    _test_thread = threading.Thread(target=_run_test_thread, args=(params,), daemon=True)
    _test_thread.start()
    
    return jsonify({'success': True, 'message': '测试已启动'})


@dispatch_bp.route('/api/dispatch/test/stop', methods=['POST'])
@login_required
def api_test_stop():
    """停止自动驾驶测试并重启项目"""
    global _test_stop_flag, _test_state
    
    _test_stop_flag.set()
    
    with _test_state_lock:
        _test_state['running'] = False
        proc = _test_state.get('_proc')
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except:
                pass
    
    # 延迟重启，先返回响应
    def _restart():
        time.sleep(0.5)
        import sys
        os.execv(sys.executable, [sys.executable] + sys.argv)
    
    threading.Thread(target=_restart, daemon=True).start()
    
    return jsonify({'success': True, 'message': '正在重启服务...'})


@dispatch_bp.route('/api/dispatch/test/batch', methods=['POST'])
@login_required
def api_test_batch():
    """批量下发任务（测试运行中快速注入一批任务）"""
    import random as _random
    params = request.get_json() or {}
    batch_count = params.get('batch_count', 20)
    
    if not _test_state.get('running'):
        return jsonify({'error': '测试未运行，请先启动测试'}), 400
    
    index = _load_cache_index()
    regions_list = [(rk, r) for rk, r in index.items() if isinstance(r, dict) and 'templates' in r]
    if not regions_list:
        return jsonify({'error': '没有可用区域'}), 400
    
    # 收集所有负载模板
    all_load_in = []
    all_load_out = []
    for rk, region in regions_list:
        for t in region.get('templates', []):
            task_type = _normalize_task_type(t)
            tpl_code = t.get('code') or t.get('name', '')
            if task_type == 'load_in':
                all_load_in.append((rk, tpl_code))
            elif task_type == 'load_out':
                all_load_out.append((rk, tpl_code))
    
    if not all_load_in and not all_load_out:
        return jsonify({'error': '没有负载模板'}), 400
    
    count = 0
    for _ in range(batch_count):
        is_in = _random.random() < 0.5
        if is_in and all_load_in:
            rk, tpl = _random.choice(all_load_in)
            dev_num = f"DJC{_random.randint(1, 99)}"
            dev_code = f"BL{_random.randint(10000, 99999)}BAK{_random.randint(10000, 99999)}"
            order_id = f"pad_html{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_{_random.randint(100, 999)}_{_random.randint(1000, 9999)}"
            data = {
                'region_key': rk, 'template_name': tpl,
                'deviceNum': dev_num, 'deviceCode': dev_code,
                'status': 6, 'order_id': order_id
            }
            handle_status_report(data)
            _test_log(f"  [{rk}] 来负载 {tpl} {dev_num} (池→任务, 批量下发)")
            count += 1
        elif not is_in and all_load_out:
            rk, tpl = _random.choice(all_load_out)
            dev_num = f"DJC{_random.randint(1, 99)}"
            dev_code = f"BL{_random.randint(10000, 99999)}BAK{_random.randint(10000, 99999)}"
            order_id = f"pad_html{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_{_random.randint(100, 999)}_{_random.randint(1000, 9999)}"
            data = {
                'region_key': rk, 'template_name': tpl,
                'deviceNum': dev_num, 'deviceCode': dev_code,
                'status': 6, 'order_id': order_id
            }
            handle_status_report(data)
            _test_log(f"  [{rk}] 回负载 {tpl} {dev_num} (区域→任务, 批量下发)")
            count += 1
    
    _test_log(f"批量下发完成: {count}个任务")
    return jsonify({'success': True, 'count': count})


@dispatch_bp.route('/api/dispatch/test/status')
@login_required
def api_test_status():
    """获取测试状态"""
    with _test_state_lock:
        # 过滤掉不可序列化的对象（如 Popen）
        safe_state = {k: v for k, v in _test_state.items() if k != '_proc'}
        return jsonify(safe_state)
