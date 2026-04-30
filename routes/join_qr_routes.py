#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Join QR Node 路由蓝图
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from functools import wraps
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.database.connection import execute_query

join_qr_bp = Blueprint('join_qr', __name__)


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


@join_qr_bp.route('/join_qr_nodes')
@login_required
def list_nodes():
    nodes = execute_query("SELECT * FROM join_qr_node ORDER BY id DESC")
    return render_template('join_qr_nodes/list.html', nodes=nodes or [])


@join_qr_bp.route('/join_qr_nodes/search')
@login_required
def search_nodes():
    q = request.args.get('q', '').strip()
    if q:
        nodes = execute_query("SELECT * FROM join_qr_node WHERE qr_code LIKE %s OR area_id LIKE %s ORDER BY id DESC", (f'%{q}%', f'%{q}%'))
    else:
        nodes = execute_query("SELECT * FROM join_qr_node ORDER BY id DESC")
    return render_template('join_qr_nodes/list.html', nodes=nodes or [], search=q)


@join_qr_bp.route('/join_qr_nodes/<int:node_id>')
@login_required
def view_node(node_id):
    node = execute_query("SELECT * FROM join_qr_node WHERE id = %s", (node_id,))
    if not node:
        flash('节点不存在', 'error')
        return redirect(url_for('join_qr.list_nodes'))
    return render_template('join_qr_nodes/detail.html', node=node[0])


@join_qr_bp.route('/join_qr_nodes/<int:node_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_node(node_id):
    if request.method == 'GET':
        node = execute_query("SELECT * FROM join_qr_node WHERE id = %s", (node_id,))
        if not node:
            flash('节点不存在', 'error')
            return redirect(url_for('join_qr.list_nodes'))
        return render_template('join_qr_nodes/edit.html', node=node[0])
    else:
        data = request.form
        execute_query("""UPDATE join_qr_node SET qr_code=%s, area_id=%s, x=%s, y=%s, map_id=%s
            WHERE id=%s""", (data.get('qr_code'), data.get('area_id'), data.get('x'), data.get('y'), data.get('map_id'), node_id), fetch=False)
        flash('节点更新成功', 'success')
        return redirect(url_for('join_qr.view_node', node_id=node_id))


@join_qr_bp.route('/join_qr_nodes/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_node():
    if request.method == 'GET':
        return render_template('join_qr_nodes/edit.html', node=None)
    else:
        data = request.form
        execute_query("""INSERT INTO join_qr_node (qr_code, area_id, x, y, map_id)
            VALUES (%s, %s, %s, %s, %s)""",
            (data.get('qr_code'), data.get('area_id'), data.get('x'), data.get('y'), data.get('map_id')), fetch=False)
        flash('节点添加成功', 'success')
        return redirect(url_for('join_qr.list_nodes'))


@join_qr_bp.route('/api/join_qr_nodes/<int:node_id>/delete', methods=['DELETE'])
@login_required
@admin_required
def delete_node(node_id):
    result = execute_query("DELETE FROM join_qr_node WHERE id = %s", (node_id,), fetch=False)
    if result:
        return jsonify({'success': True, 'message': '节点删除成功'})
    return jsonify({'success': False, 'message': '节点删除失败'}), 500


@join_qr_bp.route('/api/join_qr_nodes/stats')
@login_required
def node_stats():
    result = execute_query("SELECT COUNT(*) as total, COUNT(DISTINCT area_id) as areas FROM join_qr_node")
    return jsonify({'success': True, 'data': result[0] if result else {}})
