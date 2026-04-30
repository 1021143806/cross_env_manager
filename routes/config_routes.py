#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理路由蓝图 - addtask/config 相关
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.config_service import ConfigService

config_bp = Blueprint('config', __name__)
_config_service = ConfigService()


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


@config_bp.route('/addtask')
@login_required
def addtask():
    return render_template('addTask/index.html')


@config_bp.route('/help')
@login_required
def help_page():
    return render_template('help.html')


@config_bp.route('/query/help')
@login_required
def query_help():
    return render_template('query/help.html')


@config_bp.route('/addtask/help')
@login_required
def addtask_help():
    return render_template('addTask/help.html')


@config_bp.route('/config')
@login_required
def config_page():
    return render_template('config_editor.html')


@config_bp.route('/addtask/config')
@login_required
def addtask_config():
    return render_template('config_editor.html')


@config_bp.route('/addtask/config', methods=['POST'])
@login_required
@admin_required
def save_config():
    try:
        data = request.get_json()
        _config_service.save_config(data.get('config', ''))
        return jsonify({'success': True, 'message': '配置保存成功'})
    except Exception as e:
        return jsonify({'error': f'保存配置失败: {str(e)}'}), 500


@config_bp.route('/addtask/config/backups')
@login_required
def list_backups():
    try:
        return jsonify(_config_service.list_backups())
    except Exception as e:
        return jsonify({'error': f'无法列出备份: {str(e)}'}), 500


@config_bp.route('/addtask/config/backup', methods=['POST'])
@login_required
@admin_required
def create_backup():
    try:
        backup_type = request.json.get('type', 'manual')
        message = request.json.get('message', '').strip()
        backup_name, parent_version = _config_service.create_backup(backup_type, message)
        return jsonify({'success': True, 'backup_name': backup_name, 'parent_version': parent_version})
    except Exception as e:
        return jsonify({'error': f'创建备份失败: {str(e)}'}), 500


@config_bp.route('/addtask/config/backup/<backup_name>')
@login_required
@admin_required
def get_backup(backup_name):
    try:
        content = _config_service.get_backup_content(backup_name)
        if content is None:
            return jsonify({'error': '备份文件不存在'}), 404
        return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except Exception as e:
        return jsonify({'error': f'无法读取备份: {str(e)}'}), 500


@config_bp.route('/addtask/config/backup/<backup_name>/restore', methods=['POST'])
@login_required
@admin_required
def restore_backup(backup_name):
    try:
        if _config_service.restore_backup(backup_name):
            return jsonify({'success': True})
        return jsonify({'error': '备份文件不存在'}), 404
    except Exception as e:
        return jsonify({'error': f'恢复备份失败: {str(e)}'}), 500


@config_bp.route('/addtask/config/backup/<backup_name>', methods=['DELETE'])
@login_required
@admin_required
def delete_backup(backup_name):
    try:
        if _config_service.delete_backup(backup_name):
            return jsonify({'success': True})
        return jsonify({'error': '备份文件不存在'}), 404
    except Exception as e:
        return jsonify({'error': f'删除备份失败: {str(e)}'}), 500
