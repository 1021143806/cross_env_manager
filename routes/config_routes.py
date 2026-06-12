#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理路由 - 提供页面路由 + RESTful API
API 前缀统一为 /api/config，返回 JSON
"""

import json
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.config_service import ConfigService

config_bp = Blueprint('config', __name__)
_config_service = ConfigService()


# ─── 鉴权装饰器 ─────────────────────────────────────────────

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


# ═══════════════════════════════════════════════════════════════
# 页面路由（传统 SSR 页面）
# ═══════════════════════════════════════════════════════════════

@config_bp.route('/addtask')
@login_required
def addtask():
    """任务下发 - 桌面版（带侧边栏布局）"""
    return render_template('addTask/index.html')


@config_bp.route('/addtask/config-view')
@login_required
def addtask_config_view():
    """任务下发配置编辑 - 独立页面（与 /addtask 拆分，避免高亮冲突）"""
    return render_template('addTask/index.html', show_config_view=True)


@config_bp.route('/addtask/pad')
@login_required
def addtask_pad():
    """任务下发 - Pad/平板版（独立全宽布局）"""
    return render_template('addTask/addtask.html')


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


@config_bp.route('/config-editor')
@login_required
def config_editor():
    """统一跳转到 /addtask/config-view（内联配置编辑器）"""
    return redirect(url_for('config.addtask_config_view'))


# ═══════════════════════════════════════════════════════════════
# RESTful API — 配置 CRUD
# 统一前缀 /api/config，前后端分离
# ═══════════════════════════════════════════════════════════════

@config_bp.route('/api/config', methods=['GET'])
@login_required
def api_get_config():
    """获取完整配置 (JSON)"""
    try:
        config = _config_service.load_config()
        return jsonify({'success': True, 'data': config})
    except Exception as e:
        return jsonify({'success': False, 'error': f'读取配置失败: {e}'}), 500


@config_bp.route('/api/config', methods=['POST'])
@login_required
@admin_required
def api_save_config():
    """
    保存完整配置
    请求体: { data: {...}, message: '提交说明' }
    版本冲突检测: 请求体中需包含 _client_version
    """
    try:
        body = request.get_json(force=True)
        if not body:
            return jsonify({'success': False, 'error': '请求体不能为空'}), 400

        new_config = body.get('data') or body
        message = body.get('message', '')

        # ── 版本冲突检测 ──
        client_version = new_config.get('_client_version') or body.get('_client_version')
        is_import = body.get('_is_import', False)
        force_overwrite = body.get('_force_overwrite', False)

        if client_version is not None and not (is_import or force_overwrite):
            current_config = _config_service.load_config()
            current_version = current_config.get('_version', 0)
            if int(client_version) != current_version:
                return jsonify({
                    'success': False,
                    'error': '版本冲突',
                    'message': f'当前版本 {current_version}，提交版本 {client_version}，请刷新后重试',
                    'current_version': current_version
                }), 409

        # ── 保存 ──
        # 清理前端传入的版本控制字段
        for key in ('_client_version', '_is_import', '_force_overwrite', '_commit_message'):
            new_config.pop(key, None)

        result = _config_service.save_config(new_config, commit_message=message)
        return jsonify({'success': True, **result})

    except Exception as e:
        return jsonify({'success': False, 'error': f'保存配置失败: {e}'}), 500


# ═══════════════════════════════════════════════════════════════
# RESTful API — 备份管理
# ═══════════════════════════════════════════════════════════════

@config_bp.route('/api/config/backups', methods=['GET'])
@login_required
def api_list_backups():
    """获取备份列表"""
    try:
        backups = _config_service.list_backups()
        return jsonify({'success': True, 'data': backups})
    except Exception as e:
        return jsonify({'success': False, 'error': f'获取备份列表失败: {e}'}), 500


@config_bp.route('/api/config/backup', methods=['POST'])
@login_required
@admin_required
def api_create_backup():
    """手动创建备份"""
    try:
        body = request.get_json(force=True) or {}
        message = body.get('message', '')
        backup_type = body.get('type', 'manual')

        config_data = _config_service.load_config()
        current_version = config_data.get('_version', 0)
        backup_name = _config_service._create_backup_file(config_data, current_version, message)

        return jsonify({
            'success': True,
            'backup_name': backup_name,
            'version': current_version,
            'message': message
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'创建备份失败: {e}'}), 500


@config_bp.route('/api/config/backup/<backup_name>', methods=['GET'])
@login_required
@admin_required
def api_get_backup(backup_name):
    """获取备份内容"""
    try:
        content = _config_service.get_backup_content(backup_name)
        if content is None:
            return jsonify({'success': False, 'error': '备份文件不存在'}), 404
        return jsonify({'success': True, 'data': json.loads(content)})
    except Exception as e:
        return jsonify({'success': False, 'error': f'读取备份失败: {e}'}), 500


@config_bp.route('/api/config/backup/<backup_name>/restore', methods=['POST'])
@login_required
@admin_required
def api_restore_backup(backup_name):
    """从备份恢复"""
    try:
        ok = _config_service.restore_backup(backup_name)
        if not ok:
            return jsonify({'success': False, 'error': '备份文件不存在'}), 404
        return jsonify({'success': True, 'message': f'已从 {backup_name} 恢复'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'恢复备份失败: {e}'}), 500


@config_bp.route('/api/config/backup/<backup_name>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_backup(backup_name):
    """删除备份"""
    try:
        ok = _config_service.delete_backup(backup_name)
        if not ok:
            return jsonify({'success': False, 'error': '备份文件不存在'}), 404
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': f'删除备份失败: {e}'}), 500


# ═══════════════════════════════════════════════════════════════
# 兼容旧版路由（重定向到 API）
# ═══════════════════════════════════════════════════════════════

@config_bp.route('/addtask/config', methods=['GET'])
@login_required
def legacy_get_config():
    """兼容旧版：重定向到 JSON API"""
    return jsonify({'success': True, 'data': _config_service.load_config()})


@config_bp.route('/addtask/config', methods=['POST'])
@login_required
@admin_required
def legacy_save_config():
    """兼容旧版：重定向到新 API 保存逻辑"""
    return api_save_config()
