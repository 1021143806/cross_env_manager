#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模板管理路由蓝图 - 核心 CRUD 操作
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session, Response, stream_with_context
from functools import wraps
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.template_service import TemplateService
from services.device_sync_service import DeviceSyncService
from middleware.cache import cache

template_bp = Blueprint('template', __name__)
_device_sync_service = DeviceSyncService()


def _get_template_service():
    """根据 session 中活跃的 DB 服务器创建 TemplateService 实例"""
    from modules.custom_table.config_loader import CustomTableConfig
    server_key = session.get('active_db_server', '')
    db_config = None
    if server_key:
        loader = CustomTableConfig()
        db_config = loader.get_db_config(server_key)
    return TemplateService(db_config=db_config)


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

@template_bp.route('/search', methods=['GET'])
@login_required
def search():
    """渲染模板搜索页面（前端渲染）"""
    initial_q = request.args.get('search_term', '').strip()
    return render_template('template/search.html', initial_q=initial_q)


# ========== 查看模板 ==========

@template_bp.route('/template/<int:template_id>')
@login_required
def view_template(template_id):
    """查看模板详情 — 已合并到编辑页，直接跳转"""
    return redirect(url_for('template.edit_template', template_id=template_id))


# ========== 编辑模板 ==========

@template_bp.route('/edit/<int:template_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_template(template_id):
    if request.method == 'GET':
        template = _get_template_service().get_template(template_id)
        if not template:
            flash('任务模板不存在', 'error')
            return redirect(url_for('template.index'))
        details = template.pop('details', [])
        return render_template('template/edit.html', template=template, details=details)
    
    else:
        form_data = request.form
        result = _get_template_service().update_template(template_id, form_data)
        if result is not None:
            flash('任务模板更新成功', 'success')
            updated = _get_template_service().update_details_batch(template_id, form_data)
            if updated > 0:
                flash(f'成功更新 {updated} 个子任务', 'success')
            cache.clear()  # 清除全部缓存（包括统计）
        else:
            flash('任务模板更新失败', 'error')
        return redirect(url_for('template.view_template', template_id=template_id))


# ========== 编辑子任务 ==========

@template_bp.route('/edit_detail/<int:detail_id>', methods=['POST'])
@login_required
@admin_required
def edit_detail(detail_id):
    result = _get_template_service().update_detail(detail_id, request.form)
    if result is not None:
        flash('子任务更新成功', 'success')
    else:
        flash('子任务更新失败', 'error')
    
    model_id = _get_template_service().get_detail_model_id(detail_id)
    if model_id:
        return redirect(url_for('template.view_template', template_id=model_id))
    return redirect(url_for('template.index'))


# ========== 复制模板 ==========

@template_bp.route('/copy/<int:template_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def copy_template(template_id):
    if request.method == 'GET':
        template = _get_template_service().get_template(template_id)
        if not template:
            flash('任务模板不存在', 'error')
            return redirect(url_for('template.index'))
        details = template.pop('details', [])
        return render_template('template/copy.html', template=template, details=details)
    
    else:
        result, error = _get_template_service().copy_template(template_id, request.form)
        if error:
            flash(error, 'error')
            return redirect(url_for('template.copy_template', template_id=template_id))
        flash(f'模板复制成功！新模板代码: {result["code"]}, 新模板名称: {result["name"]}', 'success')
        return redirect(url_for('template.view_template', template_id=result['id']))


# ========== API 路由 ==========

@template_bp.route('/api/search', methods=['GET'])
@login_required
def api_search():
    """前端搜索 API，支持分页/筛选/排序"""
    search_term = request.args.get('q', '').strip()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    server = request.args.get('server', '').strip() or None
    status = request.args.get('status', '').strip() or None
    sort_by = request.args.get('sort_by', 'id').strip()
    sort_order = request.args.get('sort_order', 'DESC').strip()
    
    result = _get_template_service().search_paginated(
        search_term=search_term,
        page=page,
        per_page=per_page,
        server=server,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order
    )
    return jsonify({'success': True, 'data': result})


@template_bp.route('/api/search_suggestions', methods=['GET'])
@login_required
def search_suggestions():
    term = request.args.get('term', '').strip()
    return jsonify(_get_template_service().search_suggestions(term))


@template_bp.route('/api/template/<int:template_id>', methods=['GET'])
@login_required
def api_get_template(template_id):
    """获取模板详情 JSON（供前端搜索详情面板使用）"""
    template = _get_template_service().get_template(template_id)
    if not template:
        return jsonify({'success': False, 'message': '模板不存在'}), 404
    return jsonify({'success': True, 'data': template})


@template_bp.route('/api/template/<int:template_id>/details/add', methods=['POST'])
@login_required
@admin_required
def add_detail(template_id):
    try:
        detail = _get_template_service().add_detail(template_id, request.get_json())
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
        success, error = _get_template_service().delete_detail(template_id, detail_id)
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
        success, message = _get_template_service().reorder_details(template_id, data.get('order', []))
        if success:
            return jsonify({'success': True, 'message': f'成功更新 {message} 个子任务的顺序'})
        return jsonify({'success': False, 'message': message}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500


# ========== RCS 四表同步 API ==========

@template_bp.route('/api/template/<int:template_id>/rcs_sync_status', methods=['GET'])
@login_required
def rcs_sync_status(template_id):
    """查询跨环境大模板在四张表（model_process/model_process_detail/task_template/task_relation）中的同步状态"""
    try:
        status = _get_template_service().get_four_tables_status(template_id)
        if status is None:
            return jsonify({
                'success': False,
                'message': f'跨环境模板 id={template_id} 在 fy_cross_model_process 中不存在',
                'debug': {'template_id': template_id, 'table': 'fy_cross_model_process'}
            }), 404
        return jsonify({'success': True, 'data': status})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500


@template_bp.route('/api/template/<int:template_id>/rcs_sync', methods=['POST'])
@login_required
@admin_required
def rcs_sync_template(template_id):
    """同步跨环境大模板到四张表（以 xialiaoDA02-LH023_521 为模板复制新增）"""
    try:
        result = _get_template_service().sync_template_to_rcs(template_id)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500


# ========== 设备同步 ==========

@template_bp.route('/template/device-sync')
@login_required
@admin_required
def device_sync_page():
    """设备同步向导页面"""
    servers = _device_sync_service.get_available_servers()
    return render_template('template/device_sync.html', servers=servers)


@template_bp.route('/template/device-sync/servers')
@login_required
@admin_required
def device_sync_servers():
    """获取可用服务器 IP 列表"""
    servers = _device_sync_service.get_available_servers()
    return jsonify({'success': True, 'servers': servers})


@template_bp.route('/template/device-sync/test-connection', methods=['POST'])
@login_required
@admin_required
def device_sync_test_connection():
    """测试到指定 IP 的数据库连接"""
    data = request.get_json() or {}
    ip = data.get('ip', '').strip()
    if not ip:
        return jsonify({'success': False, 'message': '请输入服务器 IP'}), 400
    ok, info, error = _device_sync_service.test_connection(ip)
    if ok:
        return jsonify({'success': True, 'info': info})
    else:
        return jsonify({'success': False, 'message': error}), 500


@template_bp.route('/template/device-sync/groups', methods=['POST'])
@login_required
@admin_required
def device_sync_groups():
    """从指定服务器获取设备组列表"""
    data = request.get_json() or {}
    ip = data.get('ip', '').strip()
    if not ip:
        return jsonify({'success': False, 'message': '请输入服务器 IP'}), 400
    groups = _device_sync_service.get_device_groups(ip)
    return jsonify({'success': True, 'groups': groups})


@template_bp.route('/template/device-sync/areas', methods=['POST'])
@login_required
@admin_required
def device_sync_areas():
    """从指定服务器获取 bms_area LEVEL=1 区域列表"""
    data = request.get_json() or {}
    ip = data.get('ip', '').strip()
    if not ip:
        return jsonify({'success': False, 'message': '请输入服务器 IP'}), 400
    areas = _device_sync_service.get_level1_areas(ip)
    return jsonify({'success': True, 'areas': areas})


@template_bp.route('/template/device-sync/execute', methods=['POST'])
@login_required
@admin_required
def device_sync_execute():
    """执行设备同步，SSE 流式返回实时日志"""
    data = request.get_json() or {}
    source_ip = data.get('source_ip', '').strip()
    target_ip = data.get('target_ip', '').strip()
    sync_types = data.get('sync_types', [])
    params = data.get('params', {})

    if not source_ip or not target_ip:
        return jsonify({'success': False, 'message': '请指定源和目标服务器 IP'}), 400
    if source_ip == target_ip:
        return jsonify({'success': False, 'message': '源和目标服务器不能相同'}), 400
    if not sync_types:
        return jsonify({'success': False, 'message': '请至少选择一种同步类型'}), 400

    def generate():
        yield from _device_sync_service.execute_sync_stream(source_ip, target_ip, sync_types, params)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


# ========== 交接点检查 ==========

@template_bp.route('/api/template/<int:template_id>/join_qr_check')
@login_required
def join_qr_check(template_id):
    """检查模板涉及的服务器是否已配置对应区域的交接点"""
    try:
        from services.join_qr_service import JoinQrService
        svc = JoinQrService()
        data, error = svc.check_template_join_qr(template_id)
        if error:
            return jsonify({'success': False, 'message': error}), 404
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
