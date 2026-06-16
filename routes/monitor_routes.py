#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CEM 系统监控路由蓝图
"""
from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for
from functools import wraps
from datetime import datetime, timedelta
import json
import os
import sys
import resource
# tracemalloc 已移除 — 生产环境长时间运行导致内存泄漏

monitor_bp = Blueprint('monitor', __name__, template_folder='../templates')


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


@monitor_bp.route('/monitor')
@login_required
def monitor_page():
    """监控页面"""
    return render_template('monitor/index.html')


@monitor_bp.route('/api/system/monitor')
@login_required
def api_monitor():
    """获取系统监控数据"""
    window = request.args.get('window', 300, type=int)  # 时间窗口（秒）
    threshold = (datetime.now() - timedelta(seconds=window)).isoformat()
    
    # 获取采样数据
    try:
        from app import _monitor_samples, _dispatch_samples
    except ImportError:
        _monitor_samples = []
        _dispatch_samples = []
    
    # 过滤时间窗口内的请求采样
    req_samples = [s for s in _monitor_samples if s.get('time', '') >= threshold]
    
    # 过滤时间窗口内的调车采样
    disp_samples = [s for s in _dispatch_samples if s.get('time', '') >= threshold]
    
    # 计算请求频率（次/分钟）
    if req_samples:
        first_time = datetime.fromisoformat(req_samples[0]['time'])
        last_time = datetime.fromisoformat(req_samples[-1]['time'])
        elapsed = max((last_time - first_time).total_seconds(), 1)
        request_rate = round(len(req_samples) / elapsed * 60, 1)
    else:
        request_rate = 0
    
    # 错误统计
    error_count = sum(1 for s in req_samples if s.get('status_code', 200) >= 500)
    
    # 状态码分布
    status_dist = {'2xx': 0, '3xx': 0, '4xx': 0, '5xx': 0}
    for s in req_samples:
        code = s.get('status_code', 200)
        if code < 300: status_dist['2xx'] += 1
        elif code < 400: status_dist['3xx'] += 1
        elif code < 500: status_dist['4xx'] += 1
        else: status_dist['5xx'] += 1
    
    # 端点访问排名
    endpoint_count = {}
    for s in req_samples:
        path = s.get('path', '/')
        # 简化路径：去掉查询参数和动态部分
        simple_path = path.split('?')[0]
        endpoint_count[simple_path] = endpoint_count.get(simple_path, 0) + 1
    endpoint_ranking = sorted(
        [{'endpoint': k, 'count': v} for k, v in endpoint_count.items()],
        key=lambda x: x['count'], reverse=True
    )[:10]
    
    # 请求流量时间线（按30秒聚合）
    timeline = {}
    for s in req_samples:
        t = s.get('time', '')[:19]  # 精确到秒
        bucket = t[:16] + '0' if len(t) >= 16 else t  # 按10秒分桶
        if bucket not in timeline:
            timeline[bucket] = {'time': bucket[11:19], 'count': 0, 'total_duration': 0}
        timeline[bucket]['count'] += 1
        timeline[bucket]['total_duration'] += s.get('duration_ms', 0)
    request_timeline = sorted(timeline.values(), key=lambda x: x['time'])
    for item in request_timeline:
        item['avg_duration'] = round(item['total_duration'] / item['count'], 1) if item['count'] > 0 else 0
        del item['total_duration']
    
    # 调车模块统计
    disp_report_count = sum(1 for s in disp_samples if s.get('action') == 'report_status')
    disp_execute_count = sum(1 for s in disp_samples if s.get('action') in ('execute', 'manual_dispatch'))
    disp_error_count = sum(1 for s in disp_samples if s.get('level') in ('error', 'warning'))
    
    if disp_samples:
        first_disp = datetime.fromisoformat(disp_samples[0]['time'])
        last_disp = datetime.fromisoformat(disp_samples[-1]['time'])
        disp_elapsed = max((last_disp - first_disp).total_seconds(), 1)
        dispatch_report_rate = round(disp_report_count / disp_elapsed * 60, 1)
        dispatch_execute_rate = round(disp_execute_count / disp_elapsed * 60, 1)
    else:
        dispatch_report_rate = 0
        dispatch_execute_rate = 0
    
    # 调车时间线
    disp_timeline = {}
    for s in disp_samples:
        t = s.get('time', '')[:19]
        bucket = t[:16] + '0' if len(t) >= 16 else t
        if bucket not in disp_timeline:
            disp_timeline[bucket] = {'time': bucket[11:19], 'report': 0, 'execute': 0}
        if s.get('action') == 'report_status':
            disp_timeline[bucket]['report'] += 1
        elif s.get('action') in ('execute', 'manual_dispatch'):
            disp_timeline[bucket]['execute'] += 1
    dispatch_timeline = sorted(disp_timeline.values(), key=lambda x: x['time'])
    
    # 数据库统计（缓存30秒）
    db_stats = _get_db_stats()
    
    # 内存统计
    memory_stats = _get_memory_stats()
    
    return jsonify({
        'summary': {
            'request_rate': request_rate,
            'error_count': error_count,
            'dispatch_report_rate': dispatch_report_rate,
            'dispatch_execute_rate': dispatch_execute_rate,
            'dispatch_error_count': disp_error_count
        },
        'request_timeline': request_timeline,
        'status_code_distribution': [
            {'code': k, 'count': v} for k, v in status_dist.items()
        ],
        'endpoint_ranking': endpoint_ranking,
        'dispatch_timeline': dispatch_timeline,
        'db_stats': db_stats,
        'memory_stats': memory_stats
    })


# 数据库统计缓存
_db_stats_cache = {'data': None, 'time': None}
_DB_CACHE_TTL = 30  # 缓存30秒


def _get_db_stats():
    """获取数据库统计（带缓存）"""
    global _db_stats_cache
    now = datetime.now()
    if _db_stats_cache['time'] and (now - _db_stats_cache['time']).total_seconds() < _DB_CACHE_TTL:
        return _db_stats_cache['data']
    
    try:
        from app import execute_query
        result = execute_query(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN enable=1 THEN 1 ELSE 0 END) as enabled, "
            "SUM(CASE WHEN enable=0 THEN 1 ELSE 0 END) as disabled "
            "FROM fy_cross_model_process"
        )
        subtask_result = execute_query(
            "SELECT COUNT(*) as total, "
            "ROUND(AVG(cnt),1) as avg_per_template "
            "FROM (SELECT COUNT(*) as cnt FROM fy_cross_model_process_detail GROUP BY model_process_id) t"
        )
        if result and subtask_result:
            _db_stats_cache['data'] = {
                'total_templates': result[0]['total'],
                'enabled': result[0]['enabled'],
                'disabled': result[0]['disabled'],
                'total_subtasks': subtask_result[0]['total'],
                'avg_subtasks': subtask_result[0]['avg_per_template']
            }
            _db_stats_cache['time'] = now
            return _db_stats_cache['data']
    except Exception as e:
        pass
    
    return {
        'total_templates': 0, 'enabled': 0, 'disabled': 0,
        'total_subtasks': 0, 'avg_subtasks': 0
    }


def _get_memory_stats():
    """获取内存占用统计"""
    stats = {'process_current_mb': 0, 'process_peak_mb': 0,
             'sample_queue_kb': 0, 'dispatch_queue_kb': 0,
             'log_file_kb': 0, 'dispatch_data_kb': 0}
    
    try:
        # Python 进程内存（resource.getrusage，替代 tracemalloc 避免泄漏）
        usage = resource.getrusage(resource.RUSAGE_SELF)
        current_kb = usage.ru_maxrss  # Linux: KB, macOS: bytes
        # macOS 上 ru_maxrss 单位是 bytes，需要转换
        if sys.platform == 'darwin':
            current_kb = current_kb // 1024
        stats['process_current_mb'] = round(current_kb / 1024, 1)
        stats['process_peak_mb'] = round(current_kb / 1024, 1)  # ru_maxrss 即最大 RSS
    except Exception:
        pass
    
    try:
        # 采样队列大小
        from app import _monitor_samples, _dispatch_samples
        stats['sample_queue_kb'] = round(sys.getsizeof(_monitor_samples) / 1024, 1)
        stats['dispatch_queue_kb'] = round(sys.getsizeof(_dispatch_samples) / 1024, 1)
    except Exception:
        pass
    
    try:
        # 日志文件大小
        log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                'data', 'dispatch', 'global_log.json')
        if os.path.exists(log_path):
            stats['log_file_kb'] = round(os.path.getsize(log_path) / 1024, 1)
    except Exception:
        pass
    
    try:
        # 调车数据文件总大小
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                'data', 'dispatch')
        total = 0
        for root, dirs, files in os.walk(data_dir):
            for f in files:
                if f.endswith('.json') and f != 'global_log.json':
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except Exception:
                        pass
        stats['dispatch_data_kb'] = round(total / 1024, 1)
    except Exception:
        pass
    
    return stats
