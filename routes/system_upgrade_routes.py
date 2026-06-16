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
            get_version_info, BASE_DIR, EXCLUDE_PATTERNS, MAX_BACKUPS,
        )
        _upgrade_svc = {
            'do_upgrade': do_upgrade,
            'do_rollback': do_rollback,
            'get_upgrade_records': get_upgrade_records,
            'trigger_restart': trigger_restart,
            'get_version_info': get_version_info,
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


@upgrade_bp.route('/api/system/version-info', methods=['GET'])
@login_required
def api_version_info():
    """获取服务器版本信息（版本号 + git commit）"""
    svc = _get_upgrade_svc()
    from services.upgrade_service import get_version_info
    return jsonify({'success': True, 'info': get_version_info()})


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
    参数: multipart/form-data
      file=升级包.zip  (必需)
      remark=升级说明  (可选，如 "修复xxx，新增xxx")
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '缺少 file 字段'}), 400

    file = request.files['file']
    if not file.filename or not file.filename.lower().endswith('.zip'):
        return jsonify({'success': False, 'error': '仅支持 .zip 文件'}), 400

    # 可选：升级备注
    remark = request.form.get('remark', '').strip()

    # 保存上传文件到临时路径
    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.zip')
    os.close(tmp_fd)
    file.save(tmp_path)

    svc = _get_upgrade_svc()
    result = svc['do_upgrade'](tmp_path, remark=remark)

    if result['success']:
        # 延迟重启
        svc['trigger_restart'](delay=3)
        resp = {
            'success': True,
            'message': result['message'],
            'backup': result.get('backup', ''),
        }
        if result.get('release_notes'):
            resp['release_notes'] = result['release_notes']
        if result.get('release_title'):
            resp['release_title'] = result['release_title']
        return jsonify(resp)
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


@upgrade_bp.route('/api/system/restart-postlook', methods=['POST'])
@login_required
def restart_postlook():
    """强制重启 Postlook 服务（先从 supervisorctl，后备 pkill）"""
    import subprocess as _sp
    results = []

    # 方法1: supervisorctl
    for sctl in ['/usr/bin/supervisorctl', '/usr/local/bin/supervisorctl']:
        try:
            r = _sp.run([sctl, 'start', 'postlook'], timeout=10, capture_output=True, text=True)
            results.append(f"supervisorctl start: {r.returncode}")
            if r.returncode == 0:
                return jsonify({'success': True, 'message': 'Postlook 启动成功'})
        except Exception as e:
            results.append(f"supervisorctl error: {e}")

    # 方法2: 先清理缓存
    import os as _os
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             'Plugin', 'postlook')
    if os.path.exists(cache_dir):
        import shutil
        for root, dirs, files in os.walk(cache_dir):
            for d in dirs:
                if d == '__pycache__':
                    try:
                        shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                    except Exception:
                        pass

    # 方法3: 尝试 pgrep + kill（如果 postlook 僵死）
    try:
        r = _sp.run(['pgrep', '-f', 'uvicorn.*postlook'], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            for pid in r.stdout.strip().split('\n'):
                try:
                    import signal
                    os.kill(int(pid), signal.SIGKILL)
                except Exception:
                    pass
            results.append("killed old postlook process")
    except Exception as e:
        results.append(f"pgrep error: {e}")

    return jsonify({
        'success': False,
        'message': 'Postlook 启动失败，请手动重启',
        'details': results
    }), 500
