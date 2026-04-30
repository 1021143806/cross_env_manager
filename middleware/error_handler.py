#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一异常处理中间件

提供:
- AppError 异常基类及子类
- Flask 错误处理器注册函数
- 统一 JSON 错误响应格式
"""

from flask import jsonify, render_template, request


class AppError(Exception):
    """应用级异常基类"""
    def __init__(self, message, status_code=400, code=None):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(self.message)


class NotFoundError(AppError):
    """资源不存在 (404)"""
    def __init__(self, message="资源不存在"):
        super().__init__(message, status_code=404)


class AuthError(AppError):
    """权限不足 (403)"""
    def __init__(self, message="权限不足"):
        super().__init__(message, status_code=403)


class ValidationError(AppError):
    """参数验证失败 (400)"""
    def __init__(self, message="参数验证失败", errors=None):
        super().__init__(message, status_code=400)
        self.errors = errors


class DatabaseError(AppError):
    """数据库操作错误 (500)"""
    def __init__(self, message="数据库操作失败"):
        super().__init__(message, status_code=500)


class BusinessError(AppError):
    """业务逻辑错误 (400)"""
    def __init__(self, message="业务处理失败"):
        super().__init__(message, status_code=400)


def register_error_handlers(app):
    """注册统一异常处理器到 Flask 应用"""
    
    @app.errorhandler(AppError)
    def handle_app_error(error):
        """处理应用级异常"""
        # AJAX/fetch 请求返回 JSON
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = jsonify({
                'success': False,
                'error': error.message,
                'code': error.code
            })
            response.status_code = error.status_code
            return response
        
        # 页面请求返回 HTML
        return render_template('error.html',
                             error_message=error.message,
                             status_code=error.status_code), error.status_code
    
    @app.errorhandler(404)
    def handle_404(error):
        """处理 404"""
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': '接口不存在'}), 404
        return render_template('error.html',
                             error_message='页面不存在',
                             status_code=404), 404
    
    @app.errorhandler(500)
    def handle_500(error):
        """处理 500"""
        app.logger.exception("服务器内部错误")
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': '服务器内部错误'}), 500
        return render_template('error.html',
                             error_message='服务器内部错误',
                             status_code=500), 500
    
    @app.errorhandler(401)
    def handle_401(error):
        """处理 401 未授权"""
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': '需要登录', 'redirect': '/login'}), 401
        from flask import redirect, url_for
        return redirect(url_for('login_page'))
    
    @app.errorhandler(403)
    def handle_403(error):
        """处理 403 禁止访问"""
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': '需要管理员权限'}), 403
        return render_template('error.html',
                             error_message='需要管理员权限',
                             status_code=403), 403
