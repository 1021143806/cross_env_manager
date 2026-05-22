#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定制表编辑蓝图
页面路由 + API 路由
"""

from flask import Blueprint, render_template, request, jsonify
from modules.custom_table import get_config, CustomTableService

custom_table_bp = Blueprint(
    'custom_table',
    __name__,
    url_prefix='/custom_table',
    template_folder='../templates'
)

CUSTOM_TABLE_VERSION = '1.0.0'


def _get_service(server_key: str, table_name: str) -> tuple:
    """
    获取 CustomTableService 实例
    返回: (service, error_response) — 成功时 error_response 为 None
    """
    cfg = get_config()
    db_config = cfg.get_db_config(server_key)
    if not db_config:
        return None, (jsonify({'error': f'服务器 "{server_key}" 不存在'}), 404)

    table_config = cfg.get_table(server_key, table_name)
    if not table_config:
        return None, (jsonify({'error': f'表 "{table_name}" 不存在'}), 404)

    try:
        service = CustomTableService(db_config, table_config)
        return service, None
    except Exception as e:
        return None, (jsonify({'error': f'连接数据库失败: {str(e)}'}), 500)


# ============================================================
# 页面路由
# ============================================================

@custom_table_bp.route('/')
def index():
    """服务器卡片选择页"""
    cfg = get_config()
    summaries = cfg.get_all_summaries()
    return render_template('custom_table/index.html', servers=summaries)


@custom_table_bp.route('/<server_key>/<table_name>')
def editor(server_key, table_name):
    """表编辑器页面"""
    cfg = get_config()
    server = cfg.get_server(server_key)
    if not server:
        return render_template('error.html', message=f'服务器 "{server_key}" 不存在'), 404

    table_config = cfg.get_table(server_key, table_name)
    if not table_config:
        return render_template('error.html', message=f'表 "{table_name}" 不存在'), 404

    return render_template(
        'custom_table/editor.html',
        server_key=server_key,
        table_name=table_name,
        server=server,
        table_config=table_config,
    )


# ============================================================
# 数据 API
# ============================================================

@custom_table_bp.route('/api/<server_key>/<table_name>/rows')
def api_query_rows(server_key, table_name):
    """查询表数据"""
    service, error = _get_service(server_key, table_name)
    if error:
        return error

    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 25, type=int)
    search = request.args.get('search', None, type=str)
    search_field = request.args.get('search_field', None, type=str)
    order_by = request.args.get('order_by', None, type=str)
    order_dir = request.args.get('order_dir', 'asc', type=str)
    group_by = request.args.get('group_by', None, type=str)

    try:
        result = service.query_rows(
            page=page,
            page_size=page_size,
            search=search,
            search_field=search_field,
            order_by=order_by,
            order_dir=order_dir,
            group_by=group_by,
        )
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@custom_table_bp.route('/api/<server_key>/<table_name>/row', methods=['POST'])
def api_insert_row(server_key, table_name):
    """新增一行"""
    service, error = _get_service(server_key, table_name)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    success, result = service.insert_row(data)
    if success:
        return jsonify({'success': True, 'id': result})
    else:
        return jsonify({'success': False, 'error': result}), 400


@custom_table_bp.route('/api/<server_key>/<table_name>/row/<pk_value>', methods=['PUT'])
def api_update_row(server_key, table_name, pk_value):
    """更新一行"""
    service, error = _get_service(server_key, table_name)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    success, result = service.update_row(pk_value, data)
    if success:
        return jsonify({'success': True, 'message': result})
    else:
        return jsonify({'success': False, 'error': result}), 400


@custom_table_bp.route('/api/<server_key>/<table_name>/row/<pk_value>', methods=['DELETE'])
def api_delete_row(server_key, table_name, pk_value):
    """删除一行"""
    service, error = _get_service(server_key, table_name)
    if error:
        return error

    success, result = service.delete_row(pk_value)
    if success:
        return jsonify({'success': True, 'message': result})
    else:
        return jsonify({'success': False, 'error': result}), 400


@custom_table_bp.route('/api/<server_key>/<table_name>/batch_update', methods=['PUT'])
def api_batch_update(server_key, table_name):
    """批量更新"""
    service, error = _get_service(server_key, table_name)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    group_field = data.pop('_group_field', None)
    group_value = data.pop('_group_value', None)

    if not group_field or group_value is None:
        return jsonify({'success': False, 'error': '缺少 _group_field 或 _group_value'}), 400

    success, result = service.batch_update(group_field, group_value, data)
    if success:
        return jsonify({'success': True, 'message': result})
    else:
        return jsonify({'success': False, 'error': result}), 400


@custom_table_bp.route('/api/<server_key>/<table_name>/export')
def api_export_csv(server_key, table_name):
    """导出 CSV"""
    service, error = _get_service(server_key, table_name)
    if error:
        return error

    search = request.args.get('search', None, type=str)
    search_field = request.args.get('search_field', None, type=str)

    try:
        csv_content = service.export_csv(search=search, search_field=search_field)
        from flask import Response
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={table_name}.csv'
            }
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@custom_table_bp.route('/api/<server_key>/<table_name>/groups')
def api_get_groups(server_key, table_name):
    """获取分组字段的去重值"""
    service, error = _get_service(server_key, table_name)
    if error:
        return error

    group_field = request.args.get('field', None, type=str)
    if not group_field:
        return jsonify({'success': False, 'error': '缺少 field 参数'}), 400

    try:
        values = service.get_group_values(group_field)
        return jsonify({'success': True, 'data': values})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
