#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模板管理路由蓝图 - 核心 CRUD 操作
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from functools import wraps
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.template_service import TemplateService
from middleware.cache import cache

template_bp = Blueprint('template', __name__)
_template_service = TemplateService()


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


# ========== 主页 ==========

@template_bp.route('/')
@login_required
def index():
    return render_template('index.html')


# ========== 搜索 ==========

@template_bp.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    if request.method == 'POST':
        search_term = request.form.get('search_term', '').strip()
    else:
        search_term = request.args.get('search_term', '').strip()
    
    templates, error = _template_service.search(search_term)
    if error:
        flash(error, 'info' if '未找到' in error else 'warning')
        return redirect(url_for('template.index'))
    
    return render_template('template/search_results.html', templates=templates, search_term=search_term)


# ========== 查看模板 ==========

@template_bp.route('/template/<int:template_id>')
@login_required
def view_template(template_id):
    template = _template_service.get_template(template_id)
    if not template:
        flash('任务模板不存在', 'error')
        return redirect(url_for('template.index'))
    details = template.pop('details', [])
    return render_template('template/detail.html', template=template, details=details)


# ========== 编辑模板 ==========

@template_bp.route('/edit/<int:template_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_template(template_id):
    if request.method == 'GET':
        template = _template_service.get_template(template_id)
        if not template:
            flash('任务模板不存在', 'error')
            return redirect(url_for('template.index'))
        details = template.pop('details', [])
        return render_template('template/edit.html', template=template, details=details)
    
    else:
        form_data = request.form
        result = _template_service.update_template(template_id, form_data)
        if result is not None:
            flash('任务模板更新成功', 'success')
            updated = _template_service.update_details_batch(template_id, form_data)
            if updated > 0:
                flash(f'成功更新 {updated} 个子任务', 'success')
            cache.delete_memoized(_template_service.get_template, template_id)
            cache.clear()  # 清除统计缓存
        else:
            flash('任务模板更新失败', 'error')
        return redirect(url_for('template.view_template', template_id=template_id))


# ========== 编辑子任务 ==========

@template_bp.route('/edit_detail/<int:detail_id>', methods=['POST'])
@login_required
@admin_required
def edit_detail(detail_id):
    result = _template_service.update_detail(detail_id, request.form)
    if result is not None:
        flash('子任务更新成功', 'success')
    else:
        flash('子任务更新失败', 'error')
    
    model_id = _template_service.get_detail_model_id(detail_id)
    if model_id:
        return redirect(url_for('template.view_template', template_id=model_id))
    return redirect(url_for('template.index'))


# ========== 复制模板 ==========

@template_bp.route('/copy/<int:template_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def copy_template(template_id):
    if request.method == 'GET':
        template = _template_service.get_template(template_id)
        if not template:
            flash('任务模板不存在', 'error')
            return redirect(url_for('template.index'))
        details = template.pop('details', [])
        return render_template('template/copy.html', template=template, details=details)
    
    else:
        result, error = _template_service.copy_template(template_id, request.form)
        if error:
            flash(error, 'error')
            return redirect(url_for('template.copy_template', template_id=template_id))
        flash(f'模板复制成功！新模板代码: {result["code"]}, 新模板名称: {result["name"]}', 'success')
        return redirect(url_for('template.view_template', template_id=result['id']))


# ========== API 路由 ==========

@template_bp.route('/api/search_suggestions', methods=['GET'])
@login_required
def search_suggestions():
    term = request.args.get('term', '').strip()
    return jsonify(_template_service.search_suggestions(term))


@template_bp.route('/api/template/<int:template_id>/details/add', methods=['POST'])
@login_required
@admin_required
def add_detail(template_id):
    try:
        detail = _template_service.add_detail(template_id, request.get_json())
        if detail:
            return jsonify({'success': True, 'message': '子任务添加成功', 'detail': detail})
        return jsonify({'success': False, 'message': '子任务添加失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500


@template_bp.route('/api/template/<int:template_id>/details/<int:detail_id>/delete', methods=['DELETE'])
@login_required
@admin_required
def delete_detail(template_id, detail_id):
    try:
        success, error = _template_service.delete_detail(template_id, detail_id)
        if success:
            return jsonify({'success': True, 'message': '子任务删除成功'})
        return jsonify({'success': False, 'message': error}), 404 if '不存在' in (error or '') else 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500


@template_bp.route('/api/template/<int:template_id>/details/reorder', methods=['POST'])
@login_required
@admin_required
def reorder_details(template_id):
    try:
        data = request.get_json()
        success, message = _template_service.reorder_details(template_id, data.get('order', []))
        if success:
            return jsonify({'success': True, 'message': f'成功更新 {message} 个子任务的顺序'})
        return jsonify({'success': False, 'message': message}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500
