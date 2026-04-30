#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理服务
"""

import os, re, json, datetime


class ConfigService:
    """配置管理服务"""
    
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    def _get_config_path(self):
        return os.path.join(self.base_dir, 'static', 'js', 'config.js')
    
    def _get_backup_dir(self):
        return os.path.join(self.base_dir, 'static', 'js', 'backups')
    
    def save_config(self, config_content):
        """保存配置"""
        config_path = self._get_config_path()
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)
    
    def list_backups(self):
        """列出所有备份"""
        backup_dir = self._get_backup_dir()
        os.makedirs(backup_dir, exist_ok=True)
        
        backups = []
        for filename in sorted(os.listdir(backup_dir), reverse=True):
            if not filename.endswith('.js'):
                continue
            filepath = os.path.join(backup_dir, filename)
            stat = os.stat(filepath)
            version_match = re.search(r'_(\d+)\.js$', filename)
            
            message = ''
            parent_version = None
            config_version = 0
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines and lines[0].startswith('// commit:'):
                        message = lines[0][10:].strip()
                    if len(lines) > 1 and lines[1].startswith('// parent_version:'):
                        ps = lines[1][18:].strip()
                        if ps and ps != 'None':
                            try:
                                parent_version = int(ps)
                            except ValueError:
                                pass
            except Exception:
                pass
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    match = re.search(r'const config = ({.*?});', content, re.DOTALL)
                    if match:
                        config_obj = json.loads(match.group(1))
                        config_version = config_obj.get('_version', 0)
            except Exception:
                pass
            
            backups.append({
                'name': filename,
                'version': version_match,
                'config_version': config_version,
                'message': message,
                'parent_version': parent_version,
                'timestamp': stat.st_mtime * 1000,
                'size': stat.st_size
            })
        
        return backups
    
    def create_backup(self, backup_type='manual', message=''):
        """创建备份"""
        config_path = self._get_config_path()
        backup_dir = self._get_backup_dir()
        os.makedirs(backup_dir, exist_ok=True)
        
        current_version = 0
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'const config = ({.*?});', content, re.DOTALL)
                if match:
                    try:
                        config_obj = json.loads(match.group(1))
                        current_version = config_obj.get('_version', 0)
                    except json.JSONDecodeError:
                        pass
        
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"config_{backup_type}_{timestamp}.js"
        backup_path = os.path.join(backup_dir, backup_name)
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            commit_line = f"// commit: {message}\n" if message else "// commit: (no message)\n"
            parent_line = f"// parent_version: {current_version}\n"
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(commit_line + parent_line + content)
        
        return backup_name, current_version
    
    def get_backup_content(self, backup_name):
        """获取备份内容"""
        backup_path = os.path.join(self._get_backup_dir(), backup_name)
        if not os.path.exists(backup_path):
            return None
        with open(backup_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def restore_backup(self, backup_name):
        """恢复备份"""
        backup_path = os.path.join(self._get_backup_dir(), backup_name)
        if not os.path.exists(backup_path):
            return False
        with open(backup_path, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(self._get_config_path(), 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    
    def delete_backup(self, backup_name):
        """删除备份"""
        backup_path = os.path.join(self._get_backup_dir(), backup_name)
        if not os.path.exists(backup_path):
            return False
        os.remove(backup_path)
        return True
