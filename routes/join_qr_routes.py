#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交接点配置路由蓝图 - join_qr_node_info 配对管理
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from functools import wraps
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.join_qr_service import JoinQrService

join_qr_bp = Blueprint('join_qr', __name__)
_service = JoinQrService()


# ======================== 装饰器 ========================

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


# ======================== 配对列表 ========================

@join_qr_bp.route('/pair/list')
@login_required
def pair_list():
    """交接点配对列表页"""
    server = request.args.get('server', '').strip()
    area = request.args.get('area', '').strip()
    search = request.args.get('search', '').strip()

    pairs = _service.get_paired_list(server=server or None, area=area or None, search=search or None)
    servers_list = _service.get_servers()
    areas_list = _service.get_areas()

    return render_template('join_qr_nodes/list.html',
                         pairs=pairs,
                         servers=servers_list,
                         areas=areas_list,
                         filter_server=server,
                         filter_area=area,
                         filter_search=search)


# ======================== 新增配对 ========================

@join_qr_bp.route('/pair/add', methods=['GET', 'POST'])
@login_required
@admin_required
def pair_add():
    """新增交接点配对"""
    servers_list = _service.get_servers()
    areas_list = _service.get_areas()

    if request.method == 'POST':
        qr_content = request.form.get('qr_content', '').strip()
        server_a = request.form.get('server_a', '').strip()
        area_a = request.form.get('area_a', '').strip()
        server_b = request.form.get('server_b', '').strip()
        area_b = request.form.get('area_b', '').strip()

        if not qr_content:
            flash('地码值不能为空', 'error')
            return render_template('join_qr_nodes/edit.html', servers=servers_list, areas=areas_list, pair=None)

        if not server_a or not area_a or not server_b or not area_b:
            flash('请填写完整的配对信息', 'error')
            return render_template('join_qr_nodes/edit.html', servers=servers_list, areas=areas_list, pair=None)

        try:
            _service.add_pair(qr_content, server_a, int(area_a), server_b, int(area_b))
            flash(f'交接点 "{qr_content}" 配对添加成功', 'success')
            return redirect(url_for('join_qr.pair_list'))
        except Exception as e:
            flash(f'添加失败: {e}', 'error')
            return render_template('join_qr_nodes/edit.html', servers=servers_list, areas=areas_list, pair=None)

    return render_template('join_qr_nodes/edit.html', servers=servers_list, areas=areas_list, pair=None)


# ======================== 编辑配对 ========================

@join_qr_bp.route('/pair/<qr_content>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def pair_edit(qr_content):
    """编辑已有的交接点配对"""
    servers_list = _service.get_servers()
    areas_list = _service.get_areas()
    records = _service.get_pair_by_qr(qr_content)

    if not records:
        flash(f'地码值 "{qr_content}" 不存在', 'error')
        return redirect(url_for('join_qr.pair_list'))

    # 构建 form 数据
    pair_data = {
        'qr_content': qr_content,
        'records': records,
        'server_a': records[0].get('environment_ip', '') if len(records) > 0 else '',
        'area_a': records[0].get('area_id', '') if len(records) > 0 else '',
        'server_b': records[1].get('environment_ip', '') if len(records) > 1 else '',
        'area_b': records[1].get('area_id', '') if len(records) > 1 else '',
    }

    if request.method == 'POST':
        new_qr = request.form.get('qr_content', '').strip()
        server_a = request.form.get('server_a', '').strip()
        area_a = request.form.get('area_a', '').strip()
        server_b = request.form.get('server_b', '').strip()
        area_b = request.form.get('area_b', '').strip()

        if not new_qr:
            flash('地码值不能为空', 'error')
            return render_template('join_qr_nodes/edit.html', servers=servers_list, areas=areas_list, pair=pair_data)

        try:
            _service.update_pair(qr_content, new_qr, server_a, int(area_a), server_b, int(area_b))
            flash(f'交接点 "{new_qr}" 更新成功', 'success')
            return redirect(url_for('join_qr.pair_list'))
        except Exception as e:
            flash(f'更新失败: {e}', 'error')
            return render_template('join_qr_nodes/edit.html', servers=servers_list, areas=areas_list, pair=pair_data)

    return render_template('join_qr_nodes/edit.html', servers=servers_list, areas=areas_list, pair=pair_data)


# ======================== 删除配对 ========================

@join_qr_bp.route('/pair/<qr_content>/delete', methods=['POST'])
@login_required
@admin_required
def pair_delete(qr_content):
    """删除交接点配对"""
    try:
        _service.delete_pair(qr_content)
        flash(f'交接点 "{qr_content}" 已删除', 'success')
    except Exception as e:
        flash(f'删除失败: {e}', 'error')
    return redirect(url_for('join_qr.pair_list'))


# ======================== API ========================

@join_qr_bp.route('/api/pairs/delete', methods=['POST'])
@login_required
@admin_required
def api_pair_delete():
    """API 删除配对"""
    data = request.get_json() or {}
    qr_content = data.get('qr_content', '').strip()
    if not qr_content:
        return jsonify({'success': False, 'message': '请指定地码值'}), 400
    try:
        _service.delete_pair(qr_content)
        return jsonify({'success': True, 'message': f'已删除'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@join_qr_bp.route('/api/pairs/list')
@login_required
def api_pair_list():
    """API 获取配对列表"""
    server = request.args.get('server', '').strip() or None
    area = request.args.get('area', '').strip() or None
    search = request.args.get('search', '').strip() or None
    pairs = _service.get_paired_list(server=server, area=area, search=search)
    return jsonify({'success': True, 'pairs': pairs, 'count': len(pairs)})


@join_qr_bp.route('/api/pairs/areas')
@login_required
def api_pair_areas():
    """API 获取指定服务器的父区域列表（?server=10.68.2.17）"""
    server = request.args.get('server', '').strip()
    areas = _service.get_areas_by_server(server) if server else _service.get_areas()
    return jsonify({'success': True, 'areas': areas, 'count': len(areas)})
