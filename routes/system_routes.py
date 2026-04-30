#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统路由蓝图 - 健康检查、测试页面等
"""

from flask import Blueprint, render_template
from functools import wraps
from flask import session, redirect, url_for, request, jsonify

system_bp = Blueprint('system', __name__)


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


@system_bp.route('/actuator/health')
def health_check():
    """健康检查接口 - 用于服务器监控"""
    return '1000', 200, {'Content-Type': 'text/plain; charset=utf-8'}


@system_bp.route('/test/version_tree')
@login_required
def test_version_tree():
    """测试版本历史树状图页面"""
    return render_template('test_version_tree.html')
