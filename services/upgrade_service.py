#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
升级管理服务 - 备份、解压覆盖、回滚、记录管理
"""

import os
import sys
import json
import zipfile
import shutil
import time
import subprocess
import threading
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(BASE_DIR, 'backup')
UPGRADE_LOG_FILE = os.path.join(BACKUP_DIR, 'upgrade_log.json')

# 保留的最大备份数量（超出时自动清理最旧的）
MAX_BACKUPS = 10

# 排除覆盖的文件/目录模式（这些文件会被保留，不解压覆盖）
EXCLUDE_PATTERNS = [
    'config/env.toml',
    'config/dispatch_config.json',
    'config/postlook_servers.json',
    'config/old/',
    'venv/',
    'logs/',
    'backup/',
    'dev/',
    '.git/',
    '.gitignore',
    'skill.md',
    'README.md',
]


def _should_exclude(relative_path: str) -> bool:
    """判断文件是否应被排除（不解压覆盖）"""
    # 标准化路径分隔符
    rel = relative_path.replace('\\', '/')
    for pattern in EXCLUDE_PATTERNS:
        if pattern.endswith('/'):
            # 目录模式：匹配路径前缀
            if rel.startswith(pattern) or rel == pattern.rstrip('/'):
                return True
        else:
            # 文件模式：精确匹配
            if rel == pattern:
                return True
    return False


def _get_app_version() -> str:
    """从 app.py 读取 APP_VERSION"""
    try:
        app_path = os.path.join(BASE_DIR, 'app.py')
        with open(app_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('APP_VERSION'):
                    # APP_VERSION = 'x.x.x'
                    return line.split('=')[1].strip().strip("'").strip('"')
    except Exception:
        pass
    return 'unknown'


def _read_upgrade_log() -> list:
    """读取升级记录"""
    if not os.path.exists(UPGRADE_LOG_FILE):
        return []
    try:
        with open(UPGRADE_LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def _write_upgrade_log(records: list):
    """写入升级记录"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(UPGRADE_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def _cleanup_old_backups():
    """
    清理超出 MAX_BACKUPS 的旧备份目录和日志
    保留最新的 MAX_BACKUPS 条备份记录
    """
    records = _read_upgrade_log()

    # 只保留升级产生的备份记录（排除 prerollback 等）
    upgrade_records = [r for r in records if r.get('backup_name', '').startswith('upgrade_')]
    if len(upgrade_records) <= MAX_BACKUPS:
        return

    # 按 timestamp 排序，保留最新的 MAX_BACKUPS 个
    to_remove = sorted(
        upgrade_records,
        key=lambda r: r.get('timestamp', ''),
    )[:-MAX_BACKUPS]

    remove_names = {r['backup_name'] for r in to_remove}

    # 删除备份目录
    for name in remove_names:
        backup_path = os.path.join(BACKUP_DIR, name)
        if os.path.isdir(backup_path):
            shutil.rmtree(backup_path)

    # 清理日志记录
    records = [r for r in records if r.get('backup_name', '') not in remove_names]
    _write_upgrade_log(records)
    print(f"[Upgrade] 已清理 {len(remove_names)} 个旧备份")


def get_upgrade_records() -> list:
    """获取升级记录列表"""
    return _read_upgrade_log()


def do_upgrade(zip_path: str) -> dict:
    """
    执行升级
    返回: {"success": True/False, "message": "...", "backup": "backup_dir_name"}
    """
    # 1. 校验文件
    if not os.path.exists(zip_path):
        return {'success': False, 'error': '上传文件不存在'}

    if not zipfile.is_zipfile(zip_path):
        os.remove(zip_path)
        return {'success': False, 'error': '文件不是有效的 ZIP 格式'}

    # 2. 读取当前版本
    old_version = _get_app_version()

    # 3. 创建备份目录
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f'upgrade_{timestamp}'
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    os.makedirs(backup_path, exist_ok=True)

    try:
        # 4. 备份项目文件（代码部分，不含排除项）
        _backup_project_files(backup_path)

        # 5. 解压到临时目录
        extract_dir = os.path.join(BACKUP_DIR, f'_extract_{timestamp}')
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            # 检查是否包含 app.py（粗略验证是合法的升级包）
            all_names = [n.replace('\\', '/') for n in zf.namelist()]
            has_app_py = any(
                n.endswith('app.py') and '/' not in n.rstrip('/')
                for n in all_names
            )
            if not has_app_py:
                shutil.rmtree(extract_dir)
                os.remove(zip_path)
                shutil.rmtree(backup_path)
                return {'success': False, 'error': 'ZIP 包不合法：未找到 app.py（请确认是项目根目录打包）'}

            zf.extractall(extract_dir)

        # 6. 逐文件覆盖（跳过排除项）
        overlay_count = 0
        skip_count = 0
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, extract_dir)

                # 排除检查
                if _should_exclude(rel_path):
                    skip_count += 1
                    continue

                dst_path = os.path.join(BASE_DIR, rel_path)
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)
                overlay_count += 1

        # 7. 记录升级信息
        new_version = _get_app_version()  # 覆盖后可能变了
        record = {
            'backup_name': backup_name,
            'timestamp': timestamp,
            'old_version': old_version,
            'new_version': new_version,
            'files_overlay': overlay_count,
            'files_skipped': skip_count,
            'status': 'success',
        }
        records = _read_upgrade_log()
        records.insert(0, record)
        _write_upgrade_log(records)

        # 8. 写入备份 meta
        meta = {
            'timestamp': timestamp,
            'old_version': old_version,
            'new_version': new_version,
            'description': f'从 v{old_version} 升级到 v{new_version}',
        }
        with open(os.path.join(backup_path, 'meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # 9. 自动清理旧备份
        _cleanup_old_backups()

    except Exception as e:
        # 清理临时目录
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.remove(zip_path)
        return {'success': False, 'error': f'升级失败: {str(e)}'}

    finally:
        # 清理临时目录和 ZIP
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        if os.path.exists(zip_path):
            os.remove(zip_path)

    return {
        'success': True,
        'message': f'升级完成（{old_version} → {new_version}），系统3秒后自动重启...',
        'backup': backup_name,
    }


def _backup_project_files(backup_path: str):
    """备份当前项目文件（保留目录结构）"""
    for root, dirs, files in os.walk(BASE_DIR):
        for file in files:
            src_path = os.path.join(root, file)
            rel_path = os.path.relpath(src_path, BASE_DIR)

            # 跳过排除项
            if _should_exclude(rel_path):
                continue

            dst_path = os.path.join(backup_path, 'files', rel_path)
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.copy2(src_path, dst_path)


def do_rollback(backup_name: str) -> dict:
    """
    回滚到指定备份版本
    返回: {"success": True/False, "message": "..."}
    """
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    files_path = os.path.join(backup_path, 'files')

    if not os.path.exists(files_path):
        return {'success': False, 'error': f'备份 "{backup_name}" 不存在或已损坏'}

    try:
        # 1. 先备份当前代码（防止意外）
        pre_rollback_dir = os.path.join(
            BACKUP_DIR, f'prerollback_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        )
        _backup_project_files(pre_rollback_dir)

        # 2. 恢复备份文件
        count = 0
        for root, dirs, files in os.walk(files_path):
            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, files_path)
                dst_path = os.path.join(BASE_DIR, rel_path)
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)
                count += 1

        # 3. 读取 meta 获取版本信息
        meta = {}
        meta_path = os.path.join(backup_path, 'meta.json')
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)

        old_version = meta.get('old_version', 'unknown')
        new_version = meta.get('new_version', 'unknown')

        # 4. 自动清理旧备份
        _cleanup_old_backups()

        # 5. 记录回滚日志
        record = {
            'backup_name': f'restore_from_{backup_name}',
            'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'old_version': new_version,
            'new_version': old_version,
            'files_overlay': count,
            'status': 'rollback',
            'description': f'从 {backup_name} 回滚',
        }
        records = _read_upgrade_log()
        records.insert(0, record)
        _write_upgrade_log(records)

    except Exception as e:
        return {'success': False, 'error': f'回滚失败: {str(e)}'}

    return {
        'success': True,
        'message': f'已从 {backup_name} 回滚，共恢复 {count} 个文件，系统3秒后自动重启...',
    }


def trigger_restart(delay: int = 3):
    """延迟触发 supervisor 重启（后台线程）"""
    def _restart():
        time.sleep(delay)
        try:
            subprocess.run(
                ['/usr/local/bin/supervisorctl', 'restart', 'cross_env_manager'],
                timeout=10,
                capture_output=True,
            )
        except Exception as e:
            print(f"[Upgrade] 重启失败: {e}")

    thread = threading.Thread(target=_restart, daemon=True)
    thread.start()
