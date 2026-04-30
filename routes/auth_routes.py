#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认证路由蓝图 - 登录/注销/认证状态
"""

from flask import Blueprint, render_template, request, jsonify, session
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.auth_service import AuthService

_auth_service = AuthService()


@auth_bp.route('/login')
def login_page():
    """登录页面"""
    return render_template('login.html')


@auth_bp.route('/api/login', methods=['POST'])
def login():
    """用户登录（RCS账号 + 可选管理员提权）"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        admin_username = data.get('admin_username', '').strip()
        admin_password = data.get('admin_password', '').strip()
        
        result = _auth_service.login(username, password, admin_username, admin_password)
        
        if result['success']:
            session['logged_in'] = True
            session['username'] = result['username']
            session['is_admin'] = result['is_admin']
            session['login_time'] = datetime.now().isoformat()
            return jsonify(result)
        else:
            return jsonify(result), 401
    except Exception as e:
        return jsonify({'success': False, 'error': f'登录失败: {str(e)}'}), 500


@auth_bp.route('/api/logout', methods=['POST'])
def logout():
    """用户注销"""
    username = session.get('username', 'unknown')
    print(f"[LOGOUT] 用户注销: {username}")
    session.clear()
    return jsonify({'success': True, 'message': '已注销'})


@auth_bp.route('/api/auth/status')
def auth_status():
    """获取认证状态"""
    return jsonify(_auth_service.get_auth_status(session))
