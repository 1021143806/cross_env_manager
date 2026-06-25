#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统路由蓝图 - 健康检查、系统配置、测试页面等
"""

from flask import Blueprint, render_template
from functools import wraps
from flask import session, redirect, url_for, request, jsonify, current_app
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

system_bp = Blueprint('system', __name__)

# 延迟加载 - 避免服务类导入失败导致蓝图注册失败
_sys_config_svc = None
def _get_sys_config():
    global _sys_config_svc
    if _sys_config_svc is None:
        from services.system_config_service import SystemConfigService
        # 使用启动时传入的实际配置文件路径
        config_path = current_app.config.get('CEM_CONFIG_PATH')
        _sys_config_svc = SystemConfigService(config_path=config_path)
    return _sys_config_svc


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': '需要登录', 'redirect': '/login'}), 401
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return jsonify({'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated_function


@system_bp.route('/actuator/health')
def health_check():
    """健康检查接口 - 用于服务器监控"""
    return '1000', 200, {'Content-Type': 'text/plain; charset=utf-8'}


@system_bp.route('/system/config')
@login_required
def system_config_page():
    """系统配置页面"""
    return render_template('system/config.html')


@system_bp.route('/api/system/config', methods=['GET'])
@login_required
@admin_required
def api_get_system_config():
    """获取系统配置（JSON）"""
    return jsonify({
        'success': True,
        'config': _get_sys_config().get_config(),
    })


@system_bp.route('/api/system/config', methods=['POST'])
@login_required
@admin_required
def api_save_system_config():
    """保存系统配置（JSON 对象合并）"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求体为空'}), 400
    return jsonify(_get_sys_config().save_config(data))


@system_bp.route('/api/system/config/raw', methods=['GET'])
@login_required
@admin_required
def api_get_raw_config():
    """获取原始 TOML 内容"""
    return jsonify({'success': True, 'content': _get_sys_config().get_raw()})


@system_bp.route('/api/system/config/raw', methods=['POST'])
@login_required
@admin_required
def api_save_raw_config():
    """保存原始 TOML 内容"""
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'success': False, 'error': '缺少 content 字段'}), 400
    return jsonify(_get_sys_config().save_raw(data['content']))


@system_bp.route('/api/system/config/backups', methods=['GET'])
@login_required
@admin_required
def api_list_backups():
    """列出配置备份"""
    return jsonify({'success': True, 'backups': _get_sys_config().list_backups()})


@system_bp.route('/api/system/config/backup', methods=['POST'])
@login_required
@admin_required
def api_create_backup():
    """创建配置备份"""
    label = request.get_json().get('label', 'manual') if request.is_json else 'manual'
    name = _get_sys_config().create_backup(label=label)
    return jsonify({'success': True, 'name': name})


@system_bp.route('/api/system/config/backup/<name>/restore', methods=['POST'])
@login_required
@admin_required
def api_restore_backup(name):
    """恢复配置备份"""
    if _get_sys_config().restore_backup(name):
        return jsonify({'success': True, 'message': '配置已恢复'})
    return jsonify({'success': False, 'error': '备份文件不存在'}), 404


@system_bp.route('/api/system/config/backup/<name>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_backup(name):
    """删除配置备份"""
    if _get_sys_config().delete_backup(name):
        return jsonify({'success': True, 'message': '备份已删除'})
    return jsonify({'success': False, 'error': '备份文件不存在'}), 404


@system_bp.route('/api/system/info', methods=['GET'])
@login_required
def api_system_info():
    """获取系统信息"""
    return jsonify({'success': True, 'info': _get_sys_config().get_system_info()})


# ========== 数据库服务器切换 ==========

@system_bp.route('/api/db/servers', methods=['GET'])
@login_required
def api_list_db_servers():
    """列出可用的数据库服务器"""
    try:
        from modules.custom_table.config_loader import CustomTableConfig
        loader = CustomTableConfig()
        servers = []
        for s in loader.get_servers():
            servers.append({
                'key': s.get('key'),
                'name': s.get('name'),
                'host': s.get('host'),
                'port': s.get('port'),
                'database': s.get('database'),
            })
        return jsonify({'success': True, 'servers': servers})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@system_bp.route('/api/db/current', methods=['GET'])
@login_required
def api_get_current_db():
    """获取当前使用的服务器 key"""
    return jsonify({
        'success': True,
        'key': session.get('active_db_server', ''),
    })


@system_bp.route('/api/db/switch', methods=['POST'])
@login_required
def api_switch_db():
    """切换数据库服务器"""
    data = request.get_json() or {}
    server_key = data.get('key', '').strip()
    
    # 清除缓存，确保切换后读取新的数据
    try:
        from middleware.cache import cache
        cache.clear()
    except Exception:
        pass
    
    if not server_key:
        session.pop('active_db_server', None)
        return jsonify({'success': True, 'message': '已恢复默认数据库'})
    
    # 验证服务器 key 是否存在
    try:
        from modules.custom_table.config_loader import CustomTableConfig
        loader = CustomTableConfig()
        server = loader.get_server(server_key)
        if not server:
            return jsonify({'success': False, 'error': f'服务器 "{server_key}" 不存在'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
    session['active_db_server'] = server_key
    return jsonify({'success': True, 'message': f'已切换到 {server.get("name", server_key)}'})


@system_bp.route('/test/version_tree')
@login_required
def test_version_tree():
    """测试版本历史树状图页面"""
    return render_template('test_version_tree.html')


# ========== 系统重启 ==========

@system_bp.route('/api/system/restart', methods=['POST'])
@login_required
@admin_required
def api_restart_cem():
    """重启 CEM 服务（通过 supervisorctl，延迟 2 秒确保响应返回）"""
    import threading
    import subprocess as sp
    import time as _time

    def _do_restart():
        _time.sleep(2)
        for sctl in ['/usr/local/bin/supervisorctl', '/usr/bin/supervisorctl', 'supervisorctl']:
            try:
                sp.run([sctl, 'restart', 'cross_env_manager'], timeout=10, capture_output=True)
                break
            except Exception:
                continue

    threading.Thread(target=_do_restart, daemon=True).start()
    return jsonify({'success': True, 'message': 'CEM 服务将在 2 秒后重启'})
