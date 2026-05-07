#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务查询路由蓝图 - 1.3项目功能整合
"""

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
    """根据设备号查询任务单号并获取深度查询结果 + 设备实时状态（全部通过远程HTTP API）
    返回 query_debug 字段，包含全链路4步骤的请求/响应/耗时调试信息"""
    import urllib.request as _urllib
    import json as _json
    import time as _time
    
    try:
        data = request.get_json() or {}
        device_num = data.get('device_num', '').strip()
        server_ip = data.get('server_ip', '').strip()
        if not device_num:
            return jsonify({'error': '请输入设备号'}), 400
        
        # 处理 server_ip 简写
        if server_ip and len(server_ip) < 4:
            server_ip = f"10.68.2.{server_ip}"
        if not server_ip:
            server_ip = "10.68.2.32"
        
        base_url = f"http://{server_ip}:8315"
        query_debug = {}  # 全链路调试信息
        
        def _api_post_with_debug(path, body, timeout=15):
            """调用远程API，返回 (data, debug_info) 元组"""
            url = f"{base_url}{path}"
            t0 = _time.time()
            try:
                req = _urllib.Request(url,
                    data=_json.dumps(body).encode('utf-8'),
                    headers={'Content-Type': 'application/json'})
                resp = _urllib.urlopen(req, timeout=timeout)
                elapsed_ms = round((_time.time() - t0) * 1000, 1)
                raw = resp.read().decode('utf-8')
                data = _json.loads(raw)
                debug = {
                    "request_url": url,
                    "request_body": body,
                    "response_body": data,
                    "http_status": resp.getcode(),
                    "elapsed_ms": elapsed_ms,
                    "success": True
                }
                return data, debug
            except Exception as e:
                elapsed_ms = round((_time.time() - t0) * 1000, 1)
                debug = {
                    "request_url": url,
                    "request_body": body,
                    "response_body": None,
                    "http_status": None,
                    "elapsed_ms": elapsed_ms,
                    "success": False,
                    "error": str(e)
                }
                return None, debug
        
        # 步骤1: 通过远程API按设备号查询最近的任务（按状态优先级）
        order_id = None
        device_code = None
        status_priority = ['6', '7', '5', '9', '4', '3', '2', '1', '8']
        step1_attempts = []
        for status in status_priority:
            res, debug = _api_post_with_debug('/crossTask/query', {
                "taskStatus": status,
                "deviceNum": device_num,
                "pageSize": 1,
                "pageNo": 1
            })
            debug['query_status'] = status
            step1_attempts.append(debug)
            if res and res.get('code') == 1000 and res.get('data', {}).get('list'):
                task = res['data']['list'][0]
                order_id = task.get('orderId', '')
                device_code = task.get('deviceCode', '')
                break
        
        query_debug['step1_find_order'] = {
            "description": f"按设备号 {device_num} 查询任务单号（按状态优先级尝试）",
            "attempts": step1_attempts,
            "result_order_id": order_id,
            "result_device_code": device_code
        }
        
        if not order_id:
            return jsonify({
                'error': f'未找到设备 {device_num} 的任务记录',
                'query_debug': query_debug
            }), 404
        
        # 步骤2: 查询主任务
        main_task = None
        main_res, step2_debug = _api_post_with_debug('/crossTask/query', {
            "orderId": order_id, "pageSize": 1, "pageNo": 1
        })
        query_debug['step2_main_task'] = {
            "description": f"查询主任务 orderId={order_id}",
            **step2_debug
        }
        if main_res and main_res.get('code') == 1000 and main_res.get('data', {}).get('list'):
            main_task = main_res['data']['list'][0]
        
        if not main_task:
            return jsonify({
                'error': '未找到该任务单号对应的主任务',
                'query_debug': query_debug
            }), 404
        
        # 步骤3: 查询子任务详情
        sub_tasks_sorted = []
        detail_res, step3_debug = _api_post_with_debug('/crossTask/detail', {
            "id": main_task['id']
        })
        query_debug['step3_sub_tasks'] = {
            "description": f"查询子任务 main_task.id={main_task['id']}",
            **step3_debug
        }
        if detail_res and detail_res.get('code') == 1000 and detail_res.get('data'):
            sub_tasks_sorted = sorted(detail_res['data'], key=lambda x: x.get('taskSeq', 0))
        
        # 步骤4: 对每个子任务查询设备实时状态
        # 按 service_url 去重，同一服务器只查一次
        device_statuses = []
        seen_servers = set()
        step4_details = []
        
        for task in sub_tasks_sorted:
            service_url = task.get('serviceUrl', task.get('service_url', ''))
            if not service_url or service_url in seen_servers:
                continue
            seen_servers.add(service_url)
            
            # 从 service_url 提取服务器 IP
            try:
                from urllib.parse import urlparse
                parsed = urlparse(service_url)
                task_server_ip = parsed.hostname
            except:
                task_server_ip = server_ip
            
            # 使用子任务中的 area_id（来自远程API返回）
            area_id = task.get('areaId', task.get('area_id', '0'))
            
            # 查询设备实时状态
            status_info = task_query_extended.query_device_status_via_service(service_url, area_id, device_code)
            status_info['service_url'] = service_url
            status_info['server_ip'] = task_server_ip
            status_info['area_id'] = area_id
            device_statuses.append(status_info)
            
            step4_details.append({
                "server_ip": task_server_ip,
                "service_url": service_url,
                "area_id": area_id,
                "device_code": device_code,
                "request_url": status_info.get('request_url', ''),
                "request_body": status_info.get('request_body', {}),
                "response_body": status_info.get('response_body'),
                "http_status": status_info.get('http_status'),
                "elapsed_ms": status_info.get('elapsed_ms'),
                "state": status_info.get('state', '查询失败'),
                "error": status_info.get('error', '')
            })
        
        query_debug['step4_device_status'] = {
            "description": f"查询设备实时状态（{len(step4_details)}个服务器）",
            "servers": step4_details
        }
        
        # 计算总耗时
        total_elapsed = 0
        for d in [step2_debug, step3_debug]:
            total_elapsed += d.get('elapsed_ms', 0)
        for s in step4_details:
            total_elapsed += s.get('elapsed_ms', 0)
        query_debug['total_elapsed_ms'] = round(total_elapsed, 1)
        
        return jsonify({
            'success': True,
            'device_num': device_num,
            'device_code': device_code,
            'order_id': order_id,
            'baseUrl': base_url,
            'mainTask': main_task,
            'subTasks': sub_tasks_sorted,
            'device_statuses': device_statuses,
            'query_debug': query_debug
        })
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
