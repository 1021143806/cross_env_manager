#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务查询路由蓝图 - 1.3项目功能整合
"""

# 任务查询模块版本号（修改本文件时递增末尾数字）
TASK_VERSION = '2.3.1'

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from functools import wraps
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

task_bp = Blueprint('task', __name__)

# 尝试导入查询模块
try:
    from modules.query import task_query_extended, device_validation
    QUERY_AVAILABLE = True
except ImportError:
    QUERY_AVAILABLE = False
    task_query_extended = None
    device_validation = None


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': '需要登录', 'redirect': '/login'}), 401
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': '需要管理员权限'}), 403
            return '''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"></head>
<body><script>alert('需要管理员权限，请在首页启用管理员提权');history.back();</script></body></html>''', 403
        return f(*args, **kwargs)
    return decorated_function


# ========== 查询操作日志 ==========

import json as _json
import threading
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUERY_LOG_PATH = os.path.join(BASE_DIR, 'data', 'query', 'query_log.json')
_query_write_lock = threading.Lock()


def _load_query_log():
    """加载查询日志"""
    if not os.path.exists(QUERY_LOG_PATH):
        return []
    try:
        with open(QUERY_LOG_PATH, 'r', encoding='utf-8') as f:
            return _json.load(f)
    except:
        return []


def _save_query_log(logs):
    """保存查询日志（原子写入，保留最新200条）"""
    logs = logs[-200:]
    os.makedirs(os.path.dirname(QUERY_LOG_PATH), exist_ok=True)
    with _query_write_lock:
        tmp = QUERY_LOG_PATH + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            _json.dump(logs, f, ensure_ascii=False, indent=2)
        os.replace(tmp, QUERY_LOG_PATH)


def write_query_log(action, detail='', level='info', raw_data=None):
    """写入查询操作日志"""
    logs = _load_query_log()
    username = session.get('username', '?')
    log_entry = {
        'time': datetime.now().isoformat(),
        'action': action,
        'detail': detail,
        'level': level,
        'user': username,
        'version': TASK_VERSION
    }
    if raw_data:
        log_entry['raw_data'] = raw_data
    logs.append(log_entry)
    _save_query_log(logs)


# ========== 统一查询页面 ==========

@task_bp.route('/query')
@login_required
def query_index():
    return render_template('query/unified_home.html')


@task_bp.route('/query/legacy')
@login_required
def query_legacy():
    return render_template('query/index_optimized.html')


@task_bp.route('/query/task', methods=['GET', 'POST'])
@login_required
def query_task_extended():
    return render_template('query/task_extended.html')


@task_bp.route('/query/device', methods=['GET', 'POST'])
@login_required
def query_device():
    if not QUERY_AVAILABLE:
        return jsonify({'success': False, 'message': '查询功能不可用'}), 503
    
    if request.method == 'POST':
        device_sn = request.form.get('device_sn', '').strip()
        device_type = request.form.get('device_type', 'agv').strip()
        
        if not device_sn:
            flash('请输入设备序列号', 'warning')
            return render_template('query/device_validation.html')
        
        try:
            if device_type == 'agv':
                device_info = device_validation.validate_agv_device(device_sn, use_production=False)
            elif device_type == 'shelf':
                device_info = device_validation.validate_shelf_device(device_sn, use_production=False)
            elif device_type == 'rfid':
                device_info = device_validation.validate_rfid_device(device_sn, use_production=False)
            else:
                flash(f'不支持的设备类型: {device_type}', 'error')
                return render_template('query/device_validation.html')
            
            if device_info:
                return render_template('query/device_result.html',
                                     device_info=device_info, device_sn=device_sn, device_type=device_type)
            else:
                flash(f'未找到设备: {device_sn}', 'info')
                return render_template('query/device_validation.html')
        except Exception as e:
            flash(f'验证失败: {str(e)}', 'error')
            return render_template('query/device_validation.html')
    
    return render_template('query/device_validation.html')


# ========== 任务查询路由 ==========

@task_bp.route('/task_query')
@login_required
def task_query_home():
    return render_template('query/task_query_home.html')


@task_bp.route('/task_query/result')
@login_required
def task_query_result():
    order_id = request.args.get('order_id', '').strip()
    server_ip = request.args.get('server_ip', '').strip()
    
    if not order_id:
        flash('请输入任务单号', 'warning')
        return redirect(url_for('task.task_query_home'))
    
    try:
        if server_ip and len(server_ip) < 4:
            server_ip = f"10.68.2.{server_ip}"
        result = task_query_extended.get_task_info_by_order_id(order_id, server_ip)
        
        if 'error' in result:
            flash(result['error'], 'error')
            return redirect(url_for('task.task_query_home'))
        return render_template('query/task_query_result.html', result=result)
    except Exception as e:
        flash(f'查询失败: {str(e)}', 'error')
        return redirect(url_for('task.task_query_home'))


@task_bp.route('/task_query/cross_task_by_template')
@login_required
def cross_task_by_template():
    template_code = request.args.get('template_code', '').strip()
    if not template_code:
        flash('请输入跨环境任务模板', 'warning')
        return redirect(url_for('task.task_query_home'))
    try:
        result = task_query_extended.search_tasks_by_template(template_code)
        if 'error' in result:
            flash(result['error'], 'error')
            return redirect(url_for('task.task_query_home'))
        return render_template('query/cross_task_by_template.html', result=result, template_code=template_code)
    except Exception as e:
        flash(f'查询失败: {str(e)}', 'error')
        return redirect(url_for('task.task_query_home'))


@task_bp.route('/task_query/cross_model_process_info')
@login_required
def cross_model_process_info():
    template_code = request.args.get('template_code', '').strip()
    if not template_code:
        flash('请输入跨环境任务模板', 'warning')
        return redirect(url_for('task.task_query_home'))
    try:
        result = task_query_extended.get_cross_model_process_info(template_code)
        if 'error' in result:
            flash(result['error'], 'error')
            return redirect(url_for('task.task_query_home'))
        return render_template('query/cross_model_process_info.html', result=result)
    except Exception as e:
        flash(f'查询失败: {str(e)}', 'error')
        return redirect(url_for('task.task_query_home'))


@task_bp.route('/task_query/cross_task_info')
@login_required
def cross_task_info():
    order_id = request.args.get('order_id', '').strip()
    if not order_id:
        flash('请输入跨环境任务编号', 'warning')
        return redirect(url_for('task.task_query_home'))
    try:
        result = task_query_extended.get_cross_task_info(order_id)
        if 'error' in result:
            flash(result['error'], 'error')
            return redirect(url_for('task.task_query_home'))
        return render_template('query/cross_task_info.html', result=result)
    except Exception as e:
        flash(f'查询失败: {str(e)}', 'error')
        return redirect(url_for('task.task_query_home'))


# ========== 设备号查询 API ==========

@task_bp.route('/api/query/device_tasks', methods=['POST'])
@login_required
def api_device_tasks():
    """根据设备号查询任务单号并获取深度查询结果 + 设备实时状态"""
    import urllib.request as _urllib
    import json as _json
    import time as _time
    
    try:
        data = request.get_json() or {}
        device_num = data.get('device_num', '').strip()
        server_ip = data.get('server_ip', '').strip()
        if not device_num:
            return jsonify({'error': '请输入设备号'}), 400
        
        if server_ip and len(server_ip) < 4:
            server_ip = f"10.68.2.{server_ip}"
        if not server_ip:
            server_ip = "10.68.2.32"
        
        base_url = f"http://{server_ip}:8315"
        query_debug = {}
        
        def _api_post_with_debug(path, body, timeout=15):
            url = f"{base_url}{path}"
            t0 = _time.time()
            try:
                req = _urllib.Request(url, data=_json.dumps(body).encode('utf-8'),
                    headers={'Content-Type': 'application/json'})
                resp = _urllib.urlopen(req, timeout=timeout)
                elapsed_ms = round((_time.time() - t0) * 1000, 1)
                raw = resp.read().decode('utf-8')
                data = _json.loads(raw)
                return data, {"request_url": url, "request_body": body, "response_body": data,
                    "http_status": resp.getcode(), "elapsed_ms": elapsed_ms, "success": True}
            except Exception as e:
                elapsed_ms = round((_time.time() - t0) * 1000, 1)
                return None, {"request_url": url, "request_body": body, "response_body": None,
                    "http_status": None, "elapsed_ms": elapsed_ms, "success": False, "error": str(e)}
        
        order_id = None
        device_code = None
        status_priority = ['6', '7', '5', '9', '4', '3', '2', '1', '8']
        step1_attempts = []
        recent_tasks = []  # 最近任务列表
        seen_order_ids = set()
        MAX_RECENT = 5
        
        for status in status_priority:
            if len(recent_tasks) >= MAX_RECENT:
                break
            res, debug = _api_post_with_debug('/crossTask/query', {
                "taskStatus": status, "deviceNum": device_num, "pageSize": MAX_RECENT, "pageNo": 1
            })
            debug['query_status'] = status
            step1_attempts.append(debug)
            if res and res.get('code') == 1000 and res.get('data', {}).get('list'):
                for task in res['data']['list']:
                    oid = task.get('orderId', '')
                    if oid and oid not in seen_order_ids:
                        seen_order_ids.add(oid)
                        recent_tasks.append({
                            "orderId": oid,
                            "deviceCode": task.get('deviceCode', ''),
                            "taskStatus": task.get('taskStatus', status),
                            "taskStatusName": task.get('taskStatusName', ''),
                            "createTime": task.get('createTime', ''),
                            "modelProcessName": task.get('modelProcessName', ''),
                            "areaId": task.get('areaId', '')
                        })
                        if len(recent_tasks) >= MAX_RECENT:
                            break
        
        # 默认取第一条作为当前查询目标
        if recent_tasks:
            order_id = recent_tasks[0]['orderId']
            device_code = recent_tasks[0]['deviceCode']
        
        query_debug['step1_find_order'] = {
            "description": f"按设备号 {device_num} 查询任务单号（最近{MAX_RECENT}条）",
            "attempts": step1_attempts, "result_order_id": order_id, "result_device_code": device_code,
            "recent_tasks_count": len(recent_tasks)
        }
        
        if not order_id:
            return jsonify({'error': f'未找到设备 {device_num} 的任务记录', 'query_debug': query_debug}), 404
        
        main_task = None
        main_res, step2_debug = _api_post_with_debug('/crossTask/query', {"orderId": order_id, "pageSize": 1, "pageNo": 1})
        query_debug['step2_main_task'] = {"description": f"查询主任务 orderId={order_id}", **step2_debug}
        if main_res and main_res.get('code') == 1000 and main_res.get('data', {}).get('list'):
            main_task = main_res['data']['list'][0]
        
        if not main_task:
            write_query_log('device_query',
                f'设备号查询(部分失败): {device_num} → 任务 {order_id}, step2主任务查询失败',
                'warning', {'device_num': device_num, 'order_id': order_id, 'step2_error': step2_debug.get('error', '')})
            return jsonify({
                'success': False,
                'error': f'未找到该任务单号 {order_id} 对应的主任务（远程API step2返回空）',
                'device_num': device_num,
                'device_code': device_code,
                'order_id': order_id,
                'baseUrl': base_url,
                'query_debug': query_debug
            }), 404
        
        # ========== 从本地数据库补充 main_task 和子任务的缺失字段 ==========
        task_query_extended.enrich_task_dict(main_task, device_code)
        
        sub_tasks_sorted = []
        detail_res, step3_debug = _api_post_with_debug('/crossTask/detail', {"id": main_task['id']})
        query_debug['step3_sub_tasks'] = {"description": f"查询子任务 main_task.id={main_task['id']}", **step3_debug}
        if detail_res and detail_res.get('code') == 1000 and detail_res.get('data'):
            sub_tasks_sorted = sorted(detail_res['data'], key=lambda x: x.get('taskSeq', 0))
        
        for task in sub_tasks_sorted:
            task_query_extended.enrich_task_dict(task)
        
        device_statuses = []
        seen_servers = set()
        step4_details = []
        
        for task in sub_tasks_sorted:
            service_url = task.get('serviceUrl', task.get('service_url', ''))
            if not service_url or service_url in seen_servers:
                continue
            seen_servers.add(service_url)
            try:
                from urllib.parse import urlparse
                parsed = urlparse(service_url)
                task_server_ip = parsed.hostname
            except:
                task_server_ip = server_ip
            area_id = task.get('areaId', task.get('area_id', '0'))
            area_id_source = 'sub_task'
            # 方案A：从 agv_robot_ext 表查询正确的 DEVICE_AREA 修正 area_id
            if area_id == '0' and device_code:
                try:
                    area_info = task_query_extended.get_device_area_from_server(task_server_ip, device_code)
                    if area_info and not area_info.get('error') and area_info.get('area_id') is not None:
                        db_area = str(area_info['area_id'])
                        if db_area != '0':
                            area_id = db_area
                            area_id_source = 'agv_robot_ext'
                except Exception:
                    pass
            status_info = task_query_extended.query_device_status_via_service(service_url, area_id, device_code)
            status_info['service_url'] = service_url
            status_info['server_ip'] = task_server_ip
            status_info['area_id'] = area_id
            status_info['area_id_source'] = area_id_source
            device_statuses.append(status_info)
            step4_details.append({
                "server_ip": task_server_ip, "service_url": service_url, "area_id": area_id,
                "area_id_source": area_id_source,
                "device_code": device_code, "request_url": status_info.get('request_url', ''),
                "request_body": status_info.get('request_body', {}),
                "response_body": status_info.get('response_body'),
                "http_status": status_info.get('http_status'),
                "elapsed_ms": status_info.get('elapsed_ms'),
                "state": status_info.get('state', '查询失败'),
                "error": status_info.get('error', '')
            })
        
        query_debug['step4_device_status'] = {
            "description": f"查询设备实时状态（{len(step4_details)}个服务器）", "servers": step4_details
        }
        
        total_elapsed = sum(d.get('elapsed_ms', 0) for d in [step2_debug, step3_debug])
        total_elapsed += sum(s.get('elapsed_ms', 0) for s in step4_details)
        query_debug['total_elapsed_ms'] = round(total_elapsed, 1)
        
        write_query_log('device_query',
            f'设备号查询: {device_num} → 任务 {order_id}, 子任务 {len(sub_tasks_sorted)}个, 设备状态 {len(device_statuses)}个服务器',
            'info', {'device_num': device_num, 'order_id': order_id, 'sub_task_count': len(sub_tasks_sorted)})
        
        return jsonify({
            'success': True, 'device_num': device_num, 'device_code': device_code,
            'order_id': order_id, 'baseUrl': base_url, 'mainTask': main_task,
            'subTasks': sub_tasks_sorted, 'device_statuses': device_statuses, 'query_debug': query_debug,
            'recent_tasks': recent_tasks
        })
    except Exception as e:
        return jsonify({'error': f'查询失败: {str(e)}'}), 500

# ========== 深度查询辅助函数（step2~step4，供 device_task_detail 和 order_tasks 复用） ==========

def _deep_query_by_order_id(order_id, base_url, device_code=None, server_ip="10.68.2.32"):
    """根据 orderId 执行 step2~step4 深度查询，返回完整结果字典"""
    import urllib.request as _urllib
    import json as _json
    import time as _time
    
    query_debug = {}
    
    def _api_post_with_debug(path, body, timeout=15):
        url = f"{base_url}{path}"
        t0 = _time.time()
        try:
            req = _urllib.Request(url, data=_json.dumps(body).encode('utf-8'),
                headers={'Content-Type': 'application/json'})
            resp = _urllib.urlopen(req, timeout=timeout)
            elapsed_ms = round((_time.time() - t0) * 1000, 1)
            raw = resp.read().decode('utf-8')
            data = _json.loads(raw)
            return data, {"request_url": url, "request_body": body, "response_body": data,
                "http_status": resp.getcode(), "elapsed_ms": elapsed_ms, "success": True}
        except Exception as e:
            elapsed_ms = round((_time.time() - t0) * 1000, 1)
            return None, {"request_url": url, "request_body": body, "response_body": None,
                "http_status": None, "elapsed_ms": elapsed_ms, "success": False, "error": str(e)}
    
    # step2: 查询主任务
    main_task = None
    main_res, step2_debug = _api_post_with_debug('/crossTask/query', {"orderId": order_id, "pageSize": 1, "pageNo": 1})
    query_debug['step2_main_task'] = {"description": f"查询主任务 orderId={order_id}", **step2_debug}
    if main_res and main_res.get('code') == 1000 and main_res.get('data', {}).get('list'):
        main_task = main_res['data']['list'][0]
    
    if not main_task:
        return {
            'success': False,
            'error': f'未找到该任务单号 {order_id} 对应的主任务（远程API step2返回空）',
            'order_id': order_id,
            'baseUrl': base_url,
            'query_debug': query_debug
        }
    
    # 从主任务提取 device_code（如果未传入）
    if not device_code:
        device_code = main_task.get('deviceCode') or main_task.get('device_code') or ''
    
    # enrich 主任务
    task_query_extended.enrich_task_dict(main_task, device_code)
    
    # step3: 查询子任务
    sub_tasks_sorted = []
    detail_res, step3_debug = _api_post_with_debug('/crossTask/detail', {"id": main_task['id']})
    query_debug['step3_sub_tasks'] = {"description": f"查询子任务 main_task.id={main_task['id']}", **step3_debug}
    if detail_res and detail_res.get('code') == 1000 and detail_res.get('data'):
        sub_tasks_sorted = sorted(detail_res['data'], key=lambda x: x.get('taskSeq', 0))
    
    for task in sub_tasks_sorted:
        task_query_extended.enrich_task_dict(task)
    
    # step4: 查询设备实时状态
    device_statuses = []
    seen_servers = set()
    step4_details = []
    
    for task in sub_tasks_sorted:
        service_url = task.get('serviceUrl', task.get('service_url', ''))
        if not service_url or service_url in seen_servers:
            continue
        seen_servers.add(service_url)
        try:
            from urllib.parse import urlparse
            parsed = urlparse(service_url)
            task_server_ip = parsed.hostname
        except:
            task_server_ip = server_ip
        area_id = task.get('areaId', task.get('area_id', '0'))
        area_id_source = 'sub_task'
        if area_id == '0' and device_code:
            try:
                area_info = task_query_extended.get_device_area_from_server(task_server_ip, device_code)
                if area_info and not area_info.get('error') and area_info.get('area_id') is not None:
                    db_area = str(area_info['area_id'])
                    if db_area != '0':
                        area_id = db_area
                        area_id_source = 'agv_robot_ext'
            except Exception:
                pass
        status_info = task_query_extended.query_device_status_via_service(service_url, area_id, device_code)
        status_info['service_url'] = service_url
        status_info['server_ip'] = task_server_ip
        status_info['area_id'] = area_id
        status_info['area_id_source'] = area_id_source
        device_statuses.append(status_info)
        step4_details.append({
            "server_ip": task_server_ip, "service_url": service_url, "area_id": area_id,
            "area_id_source": area_id_source,
            "device_code": device_code, "request_url": status_info.get('request_url', ''),
            "request_body": status_info.get('request_body', {}),
            "response_body": status_info.get('response_body'),
            "http_status": status_info.get('http_status'),
            "elapsed_ms": status_info.get('elapsed_ms'),
            "state": status_info.get('state', '查询失败'),
            "error": status_info.get('error', '')
        })
    
    query_debug['step4_device_status'] = {
        "description": f"查询设备实时状态（{len(step4_details)}个服务器）", "servers": step4_details
    }
    
    total_elapsed = sum(d.get('elapsed_ms', 0) for d in [step2_debug, step3_debug])
    total_elapsed += sum(s.get('elapsed_ms', 0) for s in step4_details)
    query_debug['total_elapsed_ms'] = round(total_elapsed, 1)
    
    return {
        'success': True,
        'order_id': order_id,
        'device_code': device_code,
        'baseUrl': base_url,
        'mainTask': main_task,
        'subTasks': sub_tasks_sorted,
        'device_statuses': device_statuses,
        'query_debug': query_debug
    }


@task_bp.route('/api/query/device_task_detail', methods=['POST'])
@login_required
def api_device_task_detail():
    """根据 orderId 获取深度查询结果（需求1：设备号查询切换任务时使用）"""
    try:
        data = request.get_json() or {}
        order_id = data.get('order_id', '').strip()
        server_ip = data.get('server_ip', '').strip()
        device_code = data.get('device_code', '').strip()
        
        if not order_id:
            return jsonify({'error': '请输入任务单号'}), 400
        
        if server_ip and len(server_ip) < 4:
            server_ip = f"10.68.2.{server_ip}"
        if not server_ip:
            server_ip = "10.68.2.32"
        
        base_url = f"http://{server_ip}:8315"
        result = _deep_query_by_order_id(order_id, base_url, device_code, server_ip)
        
        if not result.get('success'):
            return jsonify(result), 404
        
        write_query_log('device_task_detail',
            f'设备任务详情查询: order_id={order_id}, 子任务 {len(result.get("subTasks", []))}个',
            'info', {'order_id': order_id})
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'查询失败: {str(e)}'}), 500


@task_bp.route('/api/query/order_tasks', methods=['POST'])
@login_required
def api_order_tasks():
    """按 orderId 查询任务详情 + 设备实时状态（需求3：任务单号查询展示设备状态）"""
    try:
        data = request.get_json() or {}
        order_id = data.get('order_id', '').strip()
        server_ip = data.get('server_ip', '').strip()
        
        if not order_id:
            return jsonify({'error': '请输入任务单号'}), 400
        
        if server_ip and len(server_ip) < 4:
            server_ip = f"10.68.2.{server_ip}"
        if not server_ip:
            server_ip = "10.68.2.32"
        
        base_url = f"http://{server_ip}:8315"
        result = _deep_query_by_order_id(order_id, base_url, server_ip=server_ip)
        
        if not result.get('success'):
            return jsonify(result), 404
        
        write_query_log('order_tasks',
            f'任务单号查询: {order_id}, 子任务 {len(result.get("subTasks", []))}个, 设备状态 {len(result.get("device_statuses", []))}个服务器',
            'info', {'order_id': order_id})
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'查询失败: {str(e)}'}), 500


# ========== 任务重发 API ==========

@task_bp.route('/api/task_group/<order_id>')
@login_required
def get_task_group(order_id):
    try:
        result = task_query_extended.get_task_info_by_order_id(order_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@task_bp.route('/api/task/local_detail/<order_id>')
@login_required
def get_local_task_detail(order_id):
    """从本地数据库直接查询 fy_cross_task + fy_cross_task_detail 完整字段"""
    try:
        result = task_query_extended.get_local_cross_task_detail(order_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@task_bp.route('/api/query/latest_order')
@login_required
def api_latest_order():
    """获取最近一条任务单号（用于页面打开时自动查询）"""
    try:
        conn = task_query_extended._get_production_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT orderId FROM fy_cross_task ORDER BY update_time DESC LIMIT 1")
            row = cursor.fetchone()
        conn.close()
        if row and row.get('orderId'):
            return jsonify({'success': True, 'order_id': row['orderId']})
        return jsonify({'success': False, 'error': '无最近任务'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@task_bp.route('/api/query/enrich_tasks', methods=['POST'])
@login_required
def api_enrich_tasks():
    """用本地数据库补充任务字典中的缺失字段（区域ID、设备IP、设备类型、货架型号等）"""
    try:
        data = request.get_json() or {}
        main_task = data.get('mainTask') or {}
        sub_tasks = data.get('subTasks') or []
        
        task_query_extended.enrich_task_dict(main_task)
        for task in sub_tasks:
            task_query_extended.enrich_task_dict(task)
        
        return jsonify({
            'success': True,
            'mainTask': main_task,
            'subTasks': sub_tasks
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@task_bp.route('/api/task/resend', methods=['POST'])
@login_required
@admin_required
def resend_task():
    try:
        data = request.get_json()
        sub_order_id = data.get('sub_order_id')
        order_id = data.get('order_id')
        task_seq = data.get('task_seq')
        result = task_query_extended.resend_cross_task(sub_order_id, order_id, task_seq)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@task_bp.route('/api/task/resend/stream')
@login_required
@admin_required
def resend_task_stream():
    """
    SSE 端点：任务重发实时流
    每步推送一条 SSE 消息，前端实时展示进度动画
    """
    from flask import Response, stream_with_context
    
    order_id = request.args.get('order_id', '').strip()
    sub_order_id = request.args.get('sub_order_id', '').strip()
    task_seq = request.args.get('task_seq', type=int)
    server_ip = request.args.get('server_ip', '').strip()
    
    if not order_id or not sub_order_id or task_seq is None:
        return jsonify({'error': '缺少参数'}), 400
    
    def generate():
        import json as _json
        import traceback as _traceback
        try:
            for msg in task_query_extended.resend_cross_task_stream(sub_order_id, order_id, task_seq, server_ip):
                line = f"data: {_json.dumps(msg, ensure_ascii=False)}\n\n"
                yield line
        except Exception as e:
            # 捕获生成器中的异常并推送给前端
            error_msg = {"type": "done", "success": False, "message": f"重发异常: {str(e)}", "total_elapsed_ms": 0}
            yield f"data: {_json.dumps(error_msg, ensure_ascii=False)}\n\n"
            # 打印到日志
            print(f"[SSE Error] resend_task_stream: {e}")
            _traceback.print_exc()
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-transform',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@task_bp.route('/api/query/tasks_by_error', methods=['POST'])
@login_required
def api_tasks_by_error():
    """根据错误描述查询当天的问题任务列表"""
    try:
        data = request.get_json() or {}
        error_desc = data.get('error_desc', '').strip()
        status = data.get('status')
        if status is not None:
            try:
                status = int(status)
            except (ValueError, TypeError):
                status = None
        limit = int(data.get('limit', 50))
        
        if not error_desc and status is None:
            return jsonify({'error': '请提供 error_desc 或 status'}), 400
        
        result = task_query_extended.query_tasks_by_error(error_desc, status, limit)
        return jsonify({'success': True, 'tasks': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@task_bp.route('/api/query/debug_cross_task_detail', methods=['POST'])
@login_required
def api_debug_cross_task_detail():
    """查询 fy_cross_task_detail 表原始数据（调试用）"""
    try:
        data = request.get_json() or {}
        device_num = data.get('device_num', '').strip()
        device_code = data.get('device_code', '').strip()
        limit = int(data.get('limit', 10))
        
        if not device_num and not device_code:
            return jsonify({'error': '请提供 device_num 或 device_code'}), 400
        
        result = task_query_extended.query_debug_cross_task_detail(device_num, device_code, limit)
        return jsonify({'success': True, 'tasks': result, 'count': len(result)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== 查询日志 API（在 app.py 中定义，避免蓝图 endpoint 冲突） ==========

@task_bp.route('/api/task/force_complete', methods=['POST'])
@login_required
@admin_required
def force_complete_task():
    try:
        data = request.get_json()
        sub_order_id = data.get('sub_order_id')
        order_id = data.get('order_id')
        task_seq = data.get('task_seq')
        result = task_query_extended.force_complete_task(sub_order_id, order_id, task_seq)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@task_bp.route('/api/task/report_status', methods=['POST'])
@login_required
def report_task_status():
    """
    手动异常任务状态上报
    从 fy_cross_model_process.request_url 获取上报地址（逗号分隔多个），
    逐个 POST 上报报文：{orderId, status: 8, deviceCode, deviceNum, shelfNumber}
    """
    import urllib.request as _urllib
    import json as _json
    import time as _time
    
    try:
        data = request.get_json()
        order_id = data.get('orderId', '')
        model_process_code = data.get('modelProcessCode', '')
        device_code = data.get('deviceCode', '')
        device_num = data.get('deviceNum', '')
        shelf_number = data.get('shelfNumber', '')
        
        if not order_id:
            return jsonify({'success': False, 'error': '缺少 orderId'}), 400
        
        # 从数据库查询 request_url
        request_urls = []
        if model_process_code:
            try:
                import pymysql
                from pymysql.cursors import DictCursor
                conn = pymysql.connect(
                    host='10.68.2.32', port=3306, user='wms', password='CCshenda889',
                    database='wms', charset='utf8mb4', cursorclass=DictCursor,
                    connect_timeout=5
                )
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT request_url FROM fy_cross_model_process WHERE model_process_code = %s LIMIT 1",
                        (model_process_code,)
                    )
                    row = cursor.fetchone()
                    if row and row.get('request_url'):
                        raw = row['request_url'].strip()
                        # 逗号分隔多个 URL
                        request_urls = [u.strip() for u in raw.split(',') if u.strip()]
                conn.close()
            except Exception as e:
                return jsonify({'success': False, 'error': f'查询 request_url 失败: {str(e)}'}), 500
        
        if not request_urls:
            return jsonify({'success': False, 'error': f'模板 {model_process_code} 未配置 request_url'}), 400
        
        # 构建上报报文
        report_body = {
            "orderId": order_id,
            "status": 8
        }
        if device_code:
            report_body["deviceCode"] = device_code
        if device_num:
            report_body["deviceNum"] = device_num
        if shelf_number:
            report_body["shelfNumber"] = shelf_number
        
        # 逐个发送
        results = []
        for url in request_urls:
            t0 = _time.time()
            try:
                req = _urllib.Request(url,
                    data=_json.dumps(report_body).encode('utf-8'),
                    headers={'Content-Type': 'application/json'})
                resp = _urllib.urlopen(req, timeout=10)
                elapsed_ms = round((_time.time() - t0) * 1000, 1)
                raw_resp = resp.read().decode('utf-8')
                try:
                    resp_data = _json.loads(raw_resp)
                except:
                    resp_data = raw_resp
                results.append({
                    "url": url,
                    "http_status": resp.getcode(),
                    "elapsed_ms": elapsed_ms,
                    "response": resp_data,
                    "success": True
                })
            except Exception as e:
                elapsed_ms = round((_time.time() - t0) * 1000, 1)
                results.append({
                    "url": url,
                    "http_status": None,
                    "elapsed_ms": elapsed_ms,
                    "error": str(e),
                    "success": False
                })
        
        all_success = all(r['success'] for r in results)
        return jsonify({
            'success': all_success,
            'report_body': report_body,
            'results': results,
            'message': f'上报完成: {sum(1 for r in results if r["success"])}/{len(results)} 成功'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
