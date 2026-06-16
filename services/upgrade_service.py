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

# 升级日志记录最大保留数量
MAX_LOG_RECORDS = 500

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
    'deploy_iraypleos/',
    'Plugin/postlook/deploy/',
    'Plugin/postlook/venv/',
    '__pycache__/',
    '*.pyc',
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


def _get_git_commit() -> str:
    """获取当前 git commit hash（若 .git 存在）"""
    git_head = os.path.join(BASE_DIR, '.git', 'HEAD')
    if not os.path.exists(git_head):
        return ''
    try:
        with open(git_head, 'r') as f:
            ref_line = f.read().strip()
        if ref_line.startswith('ref: '):
            ref_path = os.path.join(BASE_DIR, '.git', ref_line[5:])
            if os.path.exists(ref_path):
                with open(ref_path, 'r') as f:
                    return f.read().strip()[:40]
            # packed-refs 场景
            packed_refs = os.path.join(BASE_DIR, '.git', 'packed-refs')
            if os.path.exists(packed_refs):
                with open(packed_refs, 'r') as f:
                    for line in f:
                        if ref_line[5:] in line:
                            return line.split()[0][:40]
        else:
            # detached HEAD
            return ref_line[:40]
    except Exception:
        pass
    return ''


def get_version_info() -> dict:
    """获取服务器版本信息"""
    return {
        'app_version': _get_app_version(),
        'git_commit': _get_git_commit(),
    }


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
    清理超出 MAX_BACKUPS 的旧备份目录（仅清理磁盘文件，不删日志记录）
    日志记录独立受 MAX_LOG_RECORDS 限制
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

    print(f"[Upgrade] 已清理 {len(remove_names)} 个旧备份目录（日志记录独立保留）")


def _trim_upgrade_log():
    """
    限制升级日志记录不超过 MAX_LOG_RECORDS 条
    超出时删除最旧的记录，同时清理对应备份目录
    """
    records = _read_upgrade_log()
    if len(records) <= MAX_LOG_RECORDS:
        return

    # 按 timestamp 排序，保留最新的 MAX_LOG_RECORDS 条
    to_remove = sorted(
        records,
        key=lambda r: r.get('timestamp', ''),
    )[:-MAX_LOG_RECORDS]

    # 清理被移除记录对应的备份目录（如果还存在）
    cleaned_dirs = 0
    for r in to_remove:
        backup_name = r.get('backup_name', '')
        if backup_name and backup_name.startswith('upgrade_'):
            backup_path = os.path.join(BACKUP_DIR, backup_name)
            if os.path.isdir(backup_path):
                shutil.rmtree(backup_path)
                cleaned_dirs += 1

    # 保留最新的 MAX_LOG_RECORDS 条
    records = records[-MAX_LOG_RECORDS:]
    _write_upgrade_log(records)
    print(f"[Upgrade] 已清理 {len(to_remove)} 条旧记录（{'，同步清理' + str(cleaned_dirs) + '个备份目录' if cleaned_dirs else ''}）")


def get_upgrade_records() -> list:
    """获取升级记录列表（同版本连续记录自动合并）"""
    records = _read_upgrade_log()
    if len(records) < 2:
        return records
    merged = []
    prev = None
    for r in records:
        if prev and r.get('old_version') == prev.get('old_version') and r.get('new_version') == prev.get('new_version') and r.get('status') == 'success' and prev.get('status') == 'success':
            # 合并：累加文件数，合并 release_notes
            prev['files_overlay'] = (prev.get('files_overlay', 0) or 0) + (r.get('files_overlay', 0) or 0)
            prev['files_skipped'] = (prev.get('files_skipped', 0) or 0) + (r.get('files_skipped', 0) or 0)
            if r.get('files_deleted'):
                prev['files_deleted'] = (prev.get('files_deleted', 0) or 0) + r['files_deleted']
            # 合并 release_notes：去重
            prev_notes = prev.get('release_notes') or []
            r_notes = r.get('release_notes') or []
            if r_notes:
                for note in r_notes:
                    if note not in prev_notes:
                        prev_notes.append(note)
                prev['release_notes'] = prev_notes
            prev['merged_count'] = (prev.get('merged_count', 1) + 1)
        else:
            merged.append(r)
            prev = r
    return merged


def _read_version_json(extract_dir: str) -> dict:
    """从解压目录读取 version.json（如果存在）"""
    vj_path = os.path.join(extract_dir, 'version.json')
    if not os.path.exists(vj_path):
        return {}
    try:
        with open(vj_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 删除 version.json 本身，防止覆盖到项目目录
        os.remove(vj_path)
        return data
    except Exception:
        return {}


def do_upgrade(zip_path: str, remark: str = '') -> dict:
    """
    执行升级
    zip_path: 升级包路径
    remark:   可选的升级备注（如 "修复xxx，新增xxx"）
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

        # 5. 校验增量包版本
        extract_dir = os.path.join(BACKUP_DIR, f'_extract_{timestamp}')
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            # 检查是否包含 app.py（全量包有根目录 app.py，增量包有 version.json）
            all_names = [n.replace('\\', '/') for n in zf.namelist()]
            has_app_py = any(
                n.endswith('app.py') and '/' not in n.rstrip('/')
                for n in all_names
            )
            has_version_json = 'version.json' in all_names
            if not has_app_py and not has_version_json:
                shutil.rmtree(extract_dir)
                os.remove(zip_path)
                shutil.rmtree(backup_path)
                return {'success': False, 'error': 'ZIP 包不合法：未找到 app.py 或 version.json'}

            zf.extractall(extract_dir)

        # 6. 尝试读取 version.json（升级说明 + 增量信息）
        version_info = _read_version_json(extract_dir)
        release_notes = version_info.get('changes', []) or []
        release_title = version_info.get('title', '')
        from_version = version_info.get('from_version', '')
        files_changed = version_info.get('files_changed', {})
        # 如果 version.json 没写 changes，用 remark 兜底
        if not release_notes and remark:
            release_notes = [remark]

        # 6.1 增量包：校验 from_version
        if from_version:
            current_ver = _get_app_version()
            if from_version != current_ver:
                shutil.rmtree(extract_dir)
                os.remove(zip_path)
                shutil.rmtree(backup_path)
                return {
                    'success': False,
                    'error': f'版本不匹配：升级包基线 v{from_version}，当前服务器 v{current_ver}。'
                             f'请确认服务器版本后再生成升级包。'
                }

        # 7. 逐文件覆盖（跳过排除项）
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

        # 7.0 清理 Python 字节码缓存（避免旧代码运行）
        _clear_pycache()

        # 7.1 增量包：清理被删除的文件
        deleted_paths = files_changed.get('D', []) if isinstance(files_changed, dict) else []
        delete_count = 0
        for rel_path in deleted_paths:
            dst_path = os.path.join(BASE_DIR, rel_path.replace('\\', '/'))
            if os.path.isfile(dst_path):
                os.remove(dst_path)
                delete_count += 1
            elif os.path.isdir(dst_path):
                shutil.rmtree(dst_path, ignore_errors=True)
                delete_count += 1

        # 8. 记录升级信息
        new_version = _get_app_version()  # 覆盖后可能变了
        record = {
            'backup_name': backup_name,
            'timestamp': timestamp,
            'old_version': old_version,
            'new_version': new_version,
            'files_overlay': overlay_count,
            'files_skipped': skip_count,
            'status': 'success',
            'release_title': release_title or f'从 v{old_version} 升级到 v{new_version}',
            'release_notes': release_notes,
        }
        # 增量包特有信息
        if from_version:
            record['upgrade_type'] = 'incremental'
            record['from_version'] = from_version
        if delete_count:
            record['files_deleted'] = delete_count
        # 清理空字段
        if not record['release_notes']:
            record.pop('release_notes', None)
        records = _read_upgrade_log()
        records.insert(0, record)
        _write_upgrade_log(records)

        # 9. 写入备份 meta
        meta = {
            'timestamp': timestamp,
            'old_version': old_version,
            'new_version': new_version,
            'description': release_title or f'从 v{old_version} 升级到 v{new_version}',
            'release_notes': release_notes,
        }
        with open(os.path.join(backup_path, 'meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # 10. 自动清理旧备份
        _cleanup_old_backups()
        # 11. 限制日志记录不超过 500 条
        _trim_upgrade_log()

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

    result = {
        'success': True,
        'message': f'升级完成（{old_version} → {new_version}），系统3秒后自动重启...',
        'backup': backup_name,
        'release_title': release_title,
        'release_notes': release_notes,
    }
    if from_version:
        result['upgrade_type'] = 'incremental'
    if delete_count:
        result['files_deleted'] = delete_count
    return result


def _clear_pycache():
    """清理 Plugin/postlook 下的所有 __pycache__ 目录（强制 Python 重新编译）"""
    postlook_src = os.path.join(BASE_DIR, 'Plugin', 'postlook', 'src')
    if not os.path.isdir(postlook_src):
        return
    for root, dirs, files in os.walk(postlook_src):
        for d in dirs:
            if d == '__pycache__':
                cache_dir = os.path.join(root, d)
                try:
                    shutil.rmtree(cache_dir, ignore_errors=True)
                except Exception:
                    pass


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
        _trim_upgrade_log()

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
    def _find_supervisorctl():
        for path in ['/usr/bin/supervisorctl', '/usr/local/bin/supervisorctl', '/usr/sbin/supervisorctl']:
            if os.path.exists(path):
                return path
        return 'supervisorctl'  # fallback to PATH

    def _restart():
        time.sleep(delay)
        sctl = _find_supervisorctl()
        for svc in ['cross_env_manager', 'postlook']:
            # 方法1: supervisorctl restart
            try:
                r = subprocess.run([sctl, 'restart', svc], timeout=10, capture_output=True, text=True)
                if r.returncode == 0:
                    continue
            except Exception as e:
                print(f"[Upgrade] supervisorctl {svc} 失败: {e}")
            # 方法2: 对于 postlook，用 pkill 强制重启（supervisor 会 auto-restart）
            if svc == 'postlook':
                try:
                    subprocess.run(['pkill', '-f', 'uvicorn.*postlook'], timeout=5)
                except Exception:
                    pass

    thread = threading.Thread(target=_restart, daemon=True)
    thread.start()
