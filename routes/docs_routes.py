#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档路由蓝图
"""

from flask import Blueprint, render_template
import os
from functools import wraps
from flask import session, redirect, url_for, request, jsonify

docs_bp = Blueprint('docs', __name__)


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


@docs_bp.route('/docs')
@login_required
def show_docs():
    """显示本地README.md文档"""
    return render_template('docs/index.html')


@docs_bp.route('/docs/module/<name>')
@login_required
def docs_module(name):
    """加载指定模块的readme文档"""
    try:
        module_paths = {
            'template': 'templates/template/readme.md',
            'addTask': 'templates/addTask/readme.md',
            'query': 'templates/query/readme.md',
            'stats': 'templates/stats/readme.md',
            'components': 'templates/components/readme.md',
            'api': 'doc/API.md',
            'dispatch': 'templates/dispatch/readme.md',
        }
        
        if name not in module_paths:
            return f"未找到模块: {name}", 404
        
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), module_paths[name])
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        import markdown
        html_content = markdown.markdown(content, extensions=['fenced_code', 'tables'])
        
        return f'''<!DOCTYPE html>
<html lang="zh-CN" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文档 - {name}</title>
    <link href="/static/vendor/bootstrap/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="/static/vendor/bootstrap-icons/bootstrap-icons.min.css">
    <style>
        body {{ background: #121212; color: #e9ecef; padding: 2rem; }}
        .container {{ max-width: 900px; }}
        h1, h2, h3 {{ color: #e9ecef; border-bottom: 1px solid #495057; padding-bottom: 0.3em; }}
        code {{ background: #2d2d2d; padding: 0.2em 0.4em; border-radius: 3px; }}
        pre {{ background: #2d2d2d; padding: 1rem; border-radius: 8px; overflow: auto; }}
        table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
        th, td {{ border: 1px solid #495057; padding: 8px 12px; text-align: left; }}
        th {{ background: #2d2d2d; }}
        a {{ color: #6ea8fe; }}
    </style>
</head>
<body>
    <div class="container">
        <a href="/docs" class="btn btn-outline-light btn-sm mb-3">&larr; 返回文档中心</a>
        {html_content}
    </div>
</body>
</html>'''
    except Exception as e:
        return f"无法加载文档: {str(e)}", 500
