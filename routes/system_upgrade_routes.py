#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
升级管理路由 - 管理页面 + 升级 API + 回滚 API
"""

import os
import tempfile
from flask import Blueprint, render_template, request, jsonify, session, current_app

from functools import wraps

upgrade_bp = Blueprint('upgrade', __name__)

# 延迟导入 service
_upgrade_svc = None


def _get_upgrade_svc():
    global _upgrade_svc
    if _upgrade_svc is None:
        from services.upgrade_service import (
            do_upgrade, do_rollback, get_upgrade_records, trigger_restart,
            BASE_DIR, EXCLUDE_PATTERNS, MAX_BACKUPS,
        )
        _upgrade_svc = {
            'do_upgrade': do_upgrade,
            'do_rollback': do_rollback,
            'get_upgrade_records': get_upgrade_records,
            'trigger_restart': trigger_restart,
            'BASE_DIR': BASE_DIR,
            'EXCLUDE_PATTERNS': EXCLUDE_PATTERNS,
            'MAX_BACKUPS': MAX_BACKUPS,
        }
    return _upgrade_svc


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': '需要登录', 'redirect': '/login'}), 401
            from flask import redirect, url_for
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


# ========== 页面 ==========


@upgrade_bp.route('/system/upgrade', methods=['GET'])
@login_required
def upgrade_page():
    """升级管理页面"""
    svc = _get_upgrade_svc()
    records = svc['get_upgrade_records']()
    return render_template('system/upgrade.html',
        records=records,
        project_dir=svc['BASE_DIR'],
        exclude_patterns=svc['EXCLUDE_PATTERNS'],
        max_backups=svc['MAX_BACKUPS'],
    )


# ========== API ==========


@upgrade_bp.route('/api/system/upgrade', methods=['POST'])
@login_required
@admin_required
def api_upgrade():
    """
    上传并执行升级
    参数: multipart/form-data, file=升级包.zip
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '缺少 file 字段'}), 400

    file = request.files['file']
    if not file.filename or not file.filename.lower().endswith('.zip'):
        return jsonify({'success': False, 'error': '仅支持 .zip 文件'}), 400

    # 保存上传文件到临时路径
    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.zip')
    os.close(tmp_fd)
    file.save(tmp_path)

    svc = _get_upgrade_svc()
    result = svc['do_upgrade'](tmp_path)

    if result['success']:
        # 延迟重启
        svc['trigger_restart'](delay=3)
        return jsonify({
            'success': True,
            'message': result['message'],
            'backup': result.get('backup', ''),
        })
    else:
        return jsonify({'success': False, 'error': result.get('error', '升级失败')}), 500


@upgrade_bp.route('/api/system/upgrade/records', methods=['GET'])
@login_required
def api_upgrade_records():
    """获取升级记录列表"""
    svc = _get_upgrade_svc()
    records = svc['get_upgrade_records']()
    return jsonify({'success': True, 'records': records})


@upgrade_bp.route('/api/system/upgrade/rollback/<backup_name>', methods=['POST'])
@login_required
@admin_required
def api_rollback(backup_name):
    """回滚到指定备份版本"""
    svc = _get_upgrade_svc()
    result = svc['do_rollback'](backup_name)

    if result['success']:
        svc['trigger_restart'](delay=3)
        return jsonify({
            'success': True,
            'message': result['message'],
        })
    else:
        return jsonify({'success': False, 'error': result.get('error', '回滚失败')}), 500
