#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CEM 系统配置管理服务 — 管理 config/env.toml
"""
import os
import sys
import shutil
import datetime
import tomli

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SystemConfigService:
    """系统配置管理服务"""

    ENV_PATH = os.path.join(_BASE_DIR, 'config', 'env.toml')
    BACKUP_DIR = os.path.join(_BASE_DIR, 'config', 'backups')

    # ==================== 读取 ====================

    def get_config(self) -> dict:
        """读取 env.toml 全部配置"""
        if not os.path.exists(self.ENV_PATH):
            return self._defaults()
        try:
            with open(self.ENV_PATH, 'rb') as f:
                return tomli.load(f)
        except Exception:
            return self._defaults()

    def get_raw(self) -> str:
        """读取原始 TOML 文本"""
        if not os.path.exists(self.ENV_PATH):
            return '# 配置文件不存在\n'
        with open(self.ENV_PATH, 'r', encoding='utf-8') as f:
            return f.read()

    # ==================== 保存 ====================

    def save_config(self, config: dict) -> dict:
        """保存配置（合并更新，保留未知字段）"""
        current = self.get_config()
        # 递归合并
        self._deep_merge(current, config)
        self._write_toml(current)
        return {'success': True, 'message': '系统配置已保存'}

    def save_raw(self, content: str) -> dict:
        """直接保存原始 TOML 文本"""
        try:
            parsed = tomli.loads(content)
        except Exception as e:
            return {'success': False, 'error': f'TOML 格式错误: {e}'}
        # 自动创建备份
        self._auto_backup()
        with open(self.ENV_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
        return {'success': True, 'message': '系统配置已保存'}

    # ==================== 备份 ====================

    def list_backups(self) -> list:
        """列出配置备份"""
        os.makedirs(self.BACKUP_DIR, exist_ok=True)
        backups = []
        for fname in sorted(os.listdir(self.BACKUP_DIR), reverse=True):
            if not fname.endswith('.toml'):
                continue
            fpath = os.path.join(self.BACKUP_DIR, fname)
            stat = os.stat(fpath)
            backups.append({
                'name': fname,
                'timestamp': int(stat.st_mtime * 1000),
                'size': stat.st_size,
            })
        return backups

    def create_backup(self, label='manual') -> str:
        """创建备份"""
        os.makedirs(self.BACKUP_DIR, exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        name = f"env_{label}_{ts}.toml"
        shutil.copy2(self.ENV_PATH, os.path.join(self.BACKUP_DIR, name))
        return name

    def restore_backup(self, name: str) -> bool:
        """恢复备份"""
        src = os.path.join(self.BACKUP_DIR, name)
        if not os.path.exists(src):
            return False
        self._auto_backup()  # 恢复前自动备份当前配置
        shutil.copy2(src, self.ENV_PATH)
        return True

    def delete_backup(self, name: str) -> bool:
        """删除备份"""
        fpath = os.path.join(self.BACKUP_DIR, name)
        if not os.path.exists(fpath):
            return False
        os.remove(fpath)
        return True

    # ==================== 服务信息 ====================

    def get_system_info(self) -> dict:
        """获取系统信息"""
        import platform
        return {
            'python_version': sys.version.split()[0],
            'platform': platform.platform(),
            'pid': os.getpid(),
            'cwd': _BASE_DIR,
            'env_file': self.ENV_PATH,
            'env_exists': os.path.exists(self.ENV_PATH),
        }

    # ==================== 内部方法 ====================

    def _defaults(self) -> dict:
        return {
            'database': {
                'host': '127.0.0.1',
                'port': 3306,
                'user': 'root',
                'password': '',
                'name': 'wms',
                'charset': 'utf8mb4',
            },
            'flask': {
                'secret_key': 'change-me',
                'debug': False,
                'host': '0.0.0.0',
                'port': 5000,
                'login_username': 'admin',
                'login_password': 'admin123456',
            },
        }

    def _write_toml(self, config: dict):
        """写入 TOML 文件"""
        self._auto_backup()
        toml_str = self._dict_to_toml(config)
        with open(self.ENV_PATH, 'w', encoding='utf-8') as f:
            f.write(toml_str)

    @staticmethod
    def _dict_to_toml(d, prefix=''):
        """将 dict 序列化为 TOML 格式"""
        lines = []
        for key, value in d.items():
            if isinstance(value, dict):
                lines.append(f'\n[{prefix}{key}]' if prefix else f'[{key}]')
                lines.append(SystemConfigService._dict_to_toml(value, prefix=f'{prefix}{key}.'))
            elif isinstance(value, bool):
                lines.append(f'{key} = {"true" if value else "false"}')
            elif isinstance(value, int):
                lines.append(f'{key} = {value}')
            elif isinstance(value, (list, tuple)):
                items = ', '.join(repr(v) for v in value)
                lines.append(f'{key} = [{items}]')
            else:
                # string
                val_str = str(value).replace('"', '\\"')
                lines.append(f'{key} = "{val_str}"')
        return '\n'.join(lines)

    def _auto_backup(self):
        """自动创建备份（同名备份不重复）"""
        os.makedirs(self.BACKUP_DIR, exist_ok=True)
        if not os.path.exists(self.ENV_PATH):
            return
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        name = f"env_auto_{ts}.toml"
        dst = os.path.join(self.BACKUP_DIR, name)
        shutil.copy2(self.ENV_PATH, dst)

    @staticmethod
    def _deep_merge(base: dict, override: dict):
        """递归合并字典"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                SystemConfigService._deep_merge(base[key], value)
            else:
                base[key] = value
