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


@upgrade_bp.route('/system/plugins', methods=['GET'])
@login_required
def plugins_page():
    """插件管理页面"""
    return render_template('system/plugins.html')
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
    """强制重启 Postlook 服务（先 supervisorctl restart，再 start，最后 pkill）"""
    import subprocess as _sp, os as _os, shutil, signal

    results = []

    # 方法1: supervisorctl restart（进程在跑时用 restart）
    for sctl in ['/usr/bin/supervisorctl', '/usr/local/bin/supervisorctl', 'supervisorctl']:
        try:
            r = _sp.run([sctl, 'restart', 'postlook'], timeout=10, capture_output=True, text=True)
            results.append(f"{sctl} restart: rc={r.returncode} out={r.stdout[:80]}")
            if r.returncode == 0:
                return jsonify({'success': True, 'message': 'Postlook 已重启 (supervisorctl restart)'})
        except Exception as e:
            results.append(f"{sctl} restart error: {e}")

    # 方法2: supervisorctl start（进程已死时用 start）
    for sctl in ['/usr/bin/supervisorctl', '/usr/local/bin/supervisorctl', 'supervisorctl']:
        try:
            r = _sp.run([sctl, 'start', 'postlook'], timeout=10, capture_output=True, text=True)
            results.append(f"{sctl} start: rc={r.returncode} out={r.stdout[:80]}")
            if r.returncode == 0:
                return jsonify({'success': True, 'message': 'Postlook 已启动 (supervisorctl start)'})
        except Exception as e:
            results.append(f"{sctl} start error: {e}")

    # 方法3: 清理 __pycache__ + 强制 pkill
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache_dir = os.path.join(root_dir, 'Plugin', 'postlook')
    try:
        for rt, dirs, _ in os.walk(cache_dir):
            for d in dirs:
                if d == '__pycache__':
                    try:
                        shutil.rmtree(os.path.join(rt, d), ignore_errors=True)
                        results.append(f"cleaned pycache: {os.path.join(rt, d)}")
                    except Exception:
                        pass
    except Exception as e:
        results.append(f"pycache cleanup error: {e}")

    # 方法4: 强制 pkill（多种模式匹配）
    for pattern in ['uvicorn.*postlook', 'python.*postlook', 'postlook']:
        try:
            r = _sp.run(['pkill', '-f', pattern], timeout=5, capture_output=True, text=True)
            if r.returncode == 0:
                results.append(f"pkill -f '{pattern}' OK")
        except Exception as e:
            results.append(f"pkill '{pattern}' error: {e}")

    return jsonify({
        'success': False,
        'message': '所有重启方式均失败，请手动 SSH 重启',
        'details': results
    }), 500


# ═══════════════════════════════════════════════════
#  插件管理 API
# ═══════════════════════════════════════════════════

@upgrade_bp.route('/api/system/plugins/status', methods=['GET'])
@login_required
def api_plugins_status():
    """获取所有插件运行状态"""
    import urllib.request
    plugins = []

    # Postlook 健康检查
    postlook_status = {
        'name': 'Postlook',
        'key': 'postlook',
        'url': 'http://127.0.0.1:5011',
        'status': 'stopped',
        'version': '-',
        'uptime': '-',
    }
    try:
        req = urllib.request.Request('http://127.0.0.1:5011/api/health', method='GET')
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = resp.read().decode()
            import json
            health = json.loads(data)
            postlook_status['status'] = 'running' if health.get('status') == 'ok' else 'error'
            postlook_status['version'] = health.get('version', '-')
    except Exception:
        pass

    # 尝试获取 Postlook 版本（如果 health 没有）
    if postlook_status['version'] == '-':
        try:
            req = urllib.request.Request('http://127.0.0.1:5011/api/help', method='GET')
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                postlook_status['version'] = data.get('version', '-')
        except Exception:
            pass

    plugins.append(postlook_status)

    return jsonify({
        'success': True,
        'plugins': plugins,
        'count': len(plugins),
        'running': sum(1 for p in plugins if p['status'] == 'running'),
    })


@upgrade_bp.route('/api/system/plugins/postlook/logs', methods=['GET'])
@login_required
def api_postlook_logs():
    """代理获取 Postlook 自身日志"""
    import urllib.request
    lines = request.args.get('lines', 100, type=int)
    keyword = request.args.get('keyword', '')

    url = f'http://127.0.0.1:5011/api/logs/self?lines={lines}'
    if keyword:
        url += f'&keyword={keyword}'

    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode()
            import json
            return jsonify({'success': True, 'data': json.loads(data)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 502
    }), 500
