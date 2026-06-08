#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
平台切换路由 — AGV DVRIP 注册平台地址切换
"""

from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for
from functools import wraps

platform_switch_bp = Blueprint(
    'platform_switch', __name__,
    template_folder='../templates'
)


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


@platform_switch_bp.route('/platform-switch')
@login_required
def index():
    """平台切换页面"""
    return render_template('platform_switch/index.html')


@platform_switch_bp.route('/api/platform-switch/query', methods=['POST'])
@login_required
def api_query():
    """
    查询设备当前 DVRIP 配置。
    POST JSON: { hosts: ["10.68.178.75", ...] }
    """
    from services.platform_switch_service import PlatformSwitchService

    data = request.get_json(silent=True) or {}
    hosts = data.get('hosts', [])
    ssh_user = data.get('ssh_user') or PlatformSwitchService.DEFAULT_SSH_USER
    ssh_pass = data.get('ssh_pass') or PlatformSwitchService.DEFAULT_SSH_PASS

    if not hosts:
        return jsonify({'error': '请提供设备 IP 列表'}), 400
    if len(hosts) > 50:
        return jsonify({'error': '单次最多 50 台设备'}), 400

    svc = PlatformSwitchService()
    results = svc.batch_query(hosts, ssh_user=ssh_user, ssh_pass=ssh_pass)
    return jsonify({'results': results})


@platform_switch_bp.route('/api/platform-switch/execute', methods=['POST'])
@login_required
def api_execute():
    """
    执行平台切换。
    POST JSON: {
        hosts: ["10.68.178.75", ...],
        new_ip: "10.68.2.32",
        port: 3002,
        ssh_user: "...",
        ssh_pass: "..."
    }
    """
    from services.platform_switch_service import PlatformSwitchService

    body = request.get_json(silent=True) or {}
    hosts = body.get('hosts', [])
    new_ip = body.get('new_ip', '').strip()
    port = int(body.get('port', 3002))
    ssh_user = body.get('ssh_user') or PlatformSwitchService.DEFAULT_SSH_USER
    ssh_pass = body.get('ssh_pass') or PlatformSwitchService.DEFAULT_SSH_PASS

    if not hosts:
        return jsonify({'error': '请提供设备 IP 列表'}), 400
    if not new_ip:
        return jsonify({'error': '请提供新的平台 IP'}), 400
    if len(hosts) > 50:
        return jsonify({'error': '单次最多 50 台设备'}), 400

    svc = PlatformSwitchService()
    results = svc.batch_switch(hosts, new_ip, port,
                               ssh_user=ssh_user, ssh_pass=ssh_pass)
    return jsonify({'results': results})
