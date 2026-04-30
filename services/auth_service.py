#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认证服务 - 用户登录/注销/验证
"""

import hashlib
import os
from datetime import datetime
from pymysql.cursors import DictCursor
from modules.database.connection import get_db_connection


class AuthService:
    """认证服务"""
    
    def __init__(self):
        self._login_config = {
            'username': os.getenv('LOGIN_USERNAME') or 'admin',
            'password': os.getenv('LOGIN_PASSWORD') or 'admin123'
        }
    
    def verify_bms_user(self, username, password):
        """通过 bms_user 表验证普通用户"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
            cursor = conn.cursor(DictCursor)
            cursor.execute("SELECT PASSWORD FROM bms_user WHERE LOGIN_NAME = %s", (username,))
            row = cursor.fetchone()
            conn.close()
            if row:
                md5_password = hashlib.md5(password.encode()).hexdigest()
                return md5_password == row['PASSWORD']
            return False
        except Exception as e:
            print(f"bms_user验证失败: {e}")
            return False
    
    def login(self, username, password, admin_username='', admin_password=''):
        """
        用户登录
        
        :return: dict {success, message, username, is_admin}
        """
        if not username or not password:
            return {'success': False, 'error': '用户名和密码不能为空'}
        
        if not self.verify_bms_user(username, password):
            return {'success': False, 'error': '用户名或密码错误'}
        
        result = {
            'success': True,
            'username': username,
            'is_admin': False
        }
        
        if admin_username and admin_password:
            if (admin_username == self._login_config['username'] and 
                admin_password == self._login_config['password']):
                result['is_admin'] = True
                result['message'] = '登录成功（管理员权限）'
                print(f"[LOGIN] 管理员提权: {username} (by {admin_username})")
            else:
                result['message'] = '登录成功（管理员验证失败，普通权限）'
                print(f"[LOGIN] 管理员提权失败: {username}")
        else:
            result['message'] = '登录成功'
            print(f"[LOGIN] 普通用户登录: {username}")
        
        return result
    
    def get_auth_status(self, session):
        """获取当前认证状态"""
        return {
            'logged_in': session.get('logged_in', False),
            'is_admin': session.get('is_admin', False),
            'username': session.get('username', ''),
            'login_time': session.get('login_time', '')
        }
