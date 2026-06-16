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


# ════════════════════════════════════════════════════════════
#  进程监控 (CEM + Postlook)
# ════════════════════════════════════════════════════════════

import time as _time
import subprocess as _sp
import threading as _th

# CPU 计算缓存
_cpu_cache = {'cem': {}, 'postlook': {}}
_cpu_lock = _th.Lock()


def _read_proc_status(pid):
    """读取 /proc/{pid}/status 中的 VmRSS 和 VmSize（单位 KB）"""
    try:
        with open(f'/proc/{pid}/status', 'r') as f:
            content = f.read()
        rss = vm = 0
        for line in content.split('\n'):
            if line.startswith('VmRSS:'):
                rss = int(line.split()[1])
            elif line.startswith('VmSize:'):
                vm = int(line.split()[1])
        return rss, vm
    except Exception:
        return 0, 0


def _read_proc_stat(pid):
    """读取 /proc/{pid}/stat 中的 utime, stime, starttime（单位：jiffies）"""
    try:
        with open(f'/proc/{pid}/stat', 'r') as f:
            fields = f.read().split()
        # field 13=utime, 14=stime, 21=starttime
        utime = int(fields[13])
        stime = int(fields[14])
        starttime = int(fields[21])
        return utime, stime, starttime
    except Exception:
        return 0, 0, 0


def _get_clock_ticks():
    """获取系统时钟频率（通常 100 Hz）"""
    try:
        return os.sysconf(os.sysconf_names['SC_CLK_TCK'])
    except Exception:
        return 100


def _find_postlook_pid():
    """扫描 /proc 查找 Postlook 进程 PID"""
    try:
        # 优先用 pgrep
        result = _sp.run(['pgrep', '-f', 'uvicorn.*5011'],
                        capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split('\n')[0])
    except Exception:
        pass

    # 兜底：扫 /proc
    try:
        for entry in os.listdir('/proc'):
            if not entry.isdigit():
                continue
            try:
                with open(f'/proc/{entry}/cmdline', 'rb') as f:
                    cmdline = f.read().decode(errors='replace')
                if '5011' in cmdline and 'uvicorn' in cmdline.lower():
                    return int(entry)
            except Exception:
                continue
    except Exception:
        pass
    return None


def _calc_cpu_percent(label, pid):
    """计算进程 CPU 占用百分比（基于两次采样差值）"""
    ticks = _get_clock_ticks()
    now = _time.time()
    utime, stime, _ = _read_proc_stat(pid)
    total = utime + stime

    with _cpu_lock:
        prev = _cpu_cache[label]
        prev_total = prev.get('total', 0)
        prev_time = prev.get('time', now)
        prev_cpu = prev.get('cpu', 0.0)

    delta_total = total - prev_total
    delta_time = now - prev_time

    if delta_time < 0.5 or delta_total <= 0:
        # 采样间隔太短，返回上次值
        return prev_cpu

    cpu = (delta_total / ticks) / delta_time * 100

    # 衰减平滑
    smoothed = prev_cpu * 0.6 + cpu * 0.4 if prev_cpu > 0 else cpu
    smoothed = round(min(smoothed, 100 * os.cpu_count()), 1)

    with _cpu_lock:
        _cpu_cache[label] = {'total': total, 'time': now, 'cpu': smoothed}

    return smoothed


def _fmt_uptime(starttime_jiffies):
    """格式化运行时长（starttime_jiffies = /proc/pid/stat field 21，相对系统启动时间）"""
    ticks = _get_clock_ticks()
    if ticks == 0:
        return '-'
    # 读取系统启动以来的秒数
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_sys = float(f.read().split()[0])
    except Exception:
        return '-'
    # 进程已运行秒数 = 系统已运行秒数 - 进程启动时的系统秒数
    proc_uptime_s = int(uptime_sys - starttime_jiffies / ticks)
    if proc_uptime_s < 0:
        return '-'
    if proc_uptime_s < 60:
        return f'{proc_uptime_s}s'
    if proc_uptime_s < 3600:
        return f'{proc_uptime_s // 60}m {proc_uptime_s % 60}s'
    if proc_uptime_s < 86400:
        return f'{proc_uptime_s // 3600}h {(proc_uptime_s % 3600) // 60}m'
    d = proc_uptime_s // 86400
    h = (proc_uptime_s % 86400) // 3600
    return f'{d}d {h}h'


def _get_cem_stats():
    """获取 CEM 自身进程统计"""
    pid = os.getpid()
    rss_kb, vm_kb = _read_proc_status(pid)
    utime, stime, starttime = _read_proc_stat(pid)

    return {
        'pid': pid,
        'status': 'running',
        'memory_rss_mb': round(rss_kb / 1024, 1),
        'memory_vm_mb': round(vm_kb / 1024, 1),
        'cpu_percent': _calc_cpu_percent('cem', pid),
        'uptime': _fmt_uptime(starttime),
        'version': getattr(sys.modules.get('app'), 'APP_VERSION', '-'),
    }


def _get_postlook_stats():
    """获取 Postlook 进程统计"""
    pid = _find_postlook_pid()
    if pid is None:
        return {
            'pid': None,
            'status': 'stopped',
            'health': 'unreachable',
            'version': '-',
            'memory_rss_mb': 0,
            'memory_vm_mb': 0,
            'cpu_percent': 0,
            'uptime': '-',
        }

    rss_kb, vm_kb = _read_proc_status(pid)
    utime, stime, starttime = _read_proc_stat(pid)

    # HTTP 健康检查
    health = 'unreachable'
    version = '-'
    try:
        import urllib.request
        req = urllib.request.Request('http://127.0.0.1:5011/api/health')
        resp = urllib.request.urlopen(req, timeout=3)
        data = json.loads(resp.read().decode())
        health = 'ok' if data.get('status') == 'ok' else 'error'
        version = data.get('version', '-')
    except Exception:
        pass

    return {
        'pid': pid,
        'status': 'running',
        'health': health,
        'version': version,
        'memory_rss_mb': round(rss_kb / 1024, 1),
        'memory_vm_mb': round(vm_kb / 1024, 1),
        'cpu_percent': _calc_cpu_percent('postlook', pid),
        'uptime': _fmt_uptime(starttime),
    }


@monitor_bp.route('/api/system/process-monitor')
@login_required
def api_process_monitor():
    """进程监控数据"""
    return jsonify({
        'cem': _get_cem_stats(),
        'postlook': _get_postlook_stats(),
    })
