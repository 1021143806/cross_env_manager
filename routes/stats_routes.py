#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计路由蓝图
"""

from flask import Blueprint, render_template, jsonify, session, redirect, url_for, request
from functools import wraps
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.stats_service import StatsService

stats_bp = Blueprint('stats', __name__)


def _get_stats_service():
    """根据 session 中活跃的 DB 服务器创建 StatsService 实例"""
    from modules.custom_table.config_loader import CustomTableConfig
    server_key = session.get('active_db_server', '')
    db_config = None
    if server_key:
        loader = CustomTableConfig()
        db_config = loader.get_db_config(server_key)
    return StatsService(db_config=db_config)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': '需要登录', 'redirect': '/login'}), 401
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated_function


@stats_bp.route('/stats')
@login_required
def show_stats():
    return render_template('stats/index.html')


@stats_bp.route('/api/stats/overview')
@login_required
def get_stats_overview():
    try:
        data = _get_stats_service().get_overview()
        if data:
            return jsonify({'success': True, 'data': data})
        return jsonify({'success': False, 'message': '无法获取统计信息'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500


@stats_bp.route('/api/stats/distribution')
@login_required
def get_stats_distribution():
    try:
        return jsonify({'success': True, 'data': _get_stats_service().get_distribution()})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500


@stats_bp.route('/api/stats/templates_by_server')
@login_required
def templates_by_server():
    try:
        return jsonify({'success': True, 'data': _get_stats_service().get_templates_by_server()})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@stats_bp.route('/api/stats/template_growth')
@login_required
def template_growth():
    try:
        return jsonify({'success': True, 'data': _get_stats_service().get_template_growth()})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@stats_bp.route('/api/stats/detailed_analysis')
@login_required
def detailed_analysis():
    try:
        return jsonify({'success': True, 'data': _get_stats_service().get_detailed_analysis()})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@stats_bp.route('/api/stats/main_task_status')
@login_required
def main_task_status():
    try:
        return jsonify({'success': True, 'data': _get_stats_service().get_main_task_status()})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
