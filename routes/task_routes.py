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
    """根据设备号查询任务单号并获取深度查询结果 + 设备实时状态"""
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
        
        # 步骤1: 根据设备号查询最近的任务单号
        task_info = task_query_extended.get_order_id_by_device_num(device_num, server_ip)
        if 'error' in task_info:
            return jsonify({'error': task_info['error']}), 404
        
        order_id = task_info['order_id']
        device_code = task_info['device_code']
        
        # 步骤2: 用 order_id 走深度查询（复用 get_cross_task_info）
        cross_info = task_query_extended.get_cross_task_info(order_id, server_ip)
        if 'error' in cross_info:
            return jsonify({'error': cross_info['error']}), 500
        
        sub_tasks = cross_info.get('cross_task_details', [])
        
        # 步骤3: 对每个子任务，查询设备区域和设备实时状态
        # 按 service_url 去重，同一服务器只查一次
        device_statuses = []
        seen_servers = set()
        
        for task in sub_tasks:
            service_url = task.get('service_url', '')
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
            
            # 查询设备区域
            area_info = task_query_extended.get_device_area_from_server(task_server_ip, device_code)
            area_id = area_info.get('area_id', '0') if 'error' not in area_info else '0'
            
            # 查询设备实时状态
            status_info = task_query_extended.query_device_status_via_service(service_url, area_id, device_code)
            status_info['service_url'] = service_url
            status_info['server_ip'] = task_server_ip
            status_info['area_id'] = area_id
            device_statuses.append(status_info)
        
        return jsonify({
            'success': True,
            'device_num': device_num,
            'device_code': device_code,
            'order_id': order_id,
            'task_info': task_info,
            'cross_info': cross_info,
            'device_statuses': device_statuses
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
